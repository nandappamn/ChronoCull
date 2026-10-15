"""Vision Language Model (VLM) client for AI curation."""

import base64
import json
import logging
import os
import urllib.request
import urllib.error
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

from chronocull.config import GEMINI_BASE_URL, GEMINI_MODEL

logger = logging.getLogger("chronocull.vlm")


class GeminiClient:
    """A lightweight, zero-dependency REST client for Gemini Vision."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set to use AI curation.")
        self.base_url = (base_url or os.environ.get("GEMINI_BASE_URL", GEMINI_BASE_URL)).rstrip("/")
        self.model = model or os.environ.get("GEMINI_MODEL", GEMINI_MODEL)

    def _resize_and_encode(self, image_path: Path, max_size: int = 1024) -> tuple[str, str]:
        """Resize image to save bandwidth and encode as Base64."""
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (e.g., for RGBA or HEIC if PIL supports it)
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # Resize while preserving aspect ratio
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            img_bytes = buffer.getvalue()
            
        b64_data = base64.b64encode(img_bytes).decode("utf-8")
        return b64_data, "image/jpeg"

    def analyze_image(self, image_path: Path) -> Dict[str, Any]:
        """Analyze an image using Gemini to extract aesthetic score, tags, and caption."""
        b64_data, mime_type = self._resize_and_encode(image_path)

        prompt = (
            "You are a professional travel photography curator. Analyze this image and respond in strict JSON format.\n"
            "Extract the following:\n"
            "1. aesthetic_score: integer from 1 to 10 based on composition, lighting, and emotional engagement.\n"
            "2. is_reject: boolean, true if it's an accidental pocket shot, heavily blurred, or completely dark/useless.\n"
            "3. tags: list of 2-4 semantic scene tags (e.g., 'mountain', 'street_food', 'group_portrait', 'architecture').\n"
            "4. caption: A descriptive 1-sentence caption.\n"
            "Ensure the output is raw JSON without markdown code blocks."
        )

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": b64_data}}
                ]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json",
            }
        }

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        for attempt in range(12):
            try:
                with urllib.request.urlopen(req) as response:
                    resp_data = json.loads(response.read().decode())
                    
                text_response = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                # Clean up potential markdown formatting if model ignores response_mime_type
                if text_response.startswith("```json"):
                    text_response = text_response[7:-3].strip()
                elif text_response.startswith("```"):
                    text_response = text_response[3:-3].strip()
                    
                return json.loads(text_response)
                
            except urllib.error.HTTPError as e:
                error_msg = e.read().decode()
                logger.error(f"Gemini API error (Attempt {attempt+1}): {error_msg}")
                if e.code in [429, 503]:
                    import time
                    time.sleep(5)
                    continue
                raise RuntimeError(f"Failed to analyze image: {e.code} {e.reason}")
            except (KeyError, json.JSONDecodeError) as e:
                logger.error(f"Failed to parse Gemini response: {e}")
                return {
                    "aesthetic_score": 5,
                    "is_reject": False,
                    "tags": [],
                    "caption": "Parsing error during analysis."
                }
        raise RuntimeError("Failed to analyze image after 12 retries.")

    def generate_travelogue(self, trip_context: str) -> str:
        """Generate a Markdown travelogue based on the structured trip data."""
        prompt = (
            "You are an expert travel writer. I will provide you with a structured JSON representation "
            "of a trip, including daily stops, geographical context, times, and AI-generated photo captions. "
            "Write a compelling, chronological travelogue in Markdown format. "
            "Include descriptive headers for each day, weave the historical/POI facts naturally into the narrative, "
            "and describe the scenes captured in the photos. Make it engaging, evocative, and well-structured.\n\n"
            f"Trip Data:\n{trip_context}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7}
        }

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        for attempt in range(12):
            try:
                with urllib.request.urlopen(req) as response:
                    resp_data = json.loads(response.read().decode())
                return resp_data["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                logger.error(f"Failed to generate travelogue (Attempt {attempt+1}): {e.code}")
                if e.code in [429, 503]:
                    import time
                    time.sleep(5)
                    continue
                raise RuntimeError("Narrative generation failed.")
        raise RuntimeError("Narrative generation failed after retries.")

