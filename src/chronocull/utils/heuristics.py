import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image
from scipy.fftpack import dct


def compute_phash(image: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    """Compute 64-bit DCT perceptual hash (pHash) as a 16-character hex string.

    1. Convert to grayscale and downsample to (hash_size * factor, hash_size * factor).
    2. Compute 2D Discrete Cosine Transform (DCT).
    3. Retain top-left low frequency coefficients (excluding DC term).
    4. Binarize against median value.
    """
    img_size = hash_size * highfreq_factor
    gray = image.convert("L").resize((img_size, img_size), Image.Resampling.LANCZOS)
    arr = np.array(gray, dtype=float)

    # 2D DCT
    dct_mat = dct(dct(arr, axis=0), axis=1)
    dct_low = dct_mat[:hash_size, :hash_size]
    med = float(np.median(dct_low))

    diff = dct_low > med
    packed = np.packbits(diff)
    return "".join(f"{b:02x}" for b in packed)


def compute_dhash(image: Image.Image, hash_size: int = 8) -> str:
    """Compute 64-bit difference hash (dHash) as a 16-character hex string.

    Compares horizontal pixel gradients after downsampling to (hash_size + 1, hash_size).
    """
    gray = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    arr = np.array(gray, dtype=float)
    diff = arr[:, 1:] > arr[:, :-1]
    packed = np.packbits(diff)
    return "".join(f"{b:02x}" for b in packed)


def hamming_distance(hash1: str, hash2: str) -> int:
    """Calculate the Hamming distance (number of bit differences) between two hex hashes."""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 64
    try:
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        return bin(val1 ^ val2).count("1")
    except ValueError:
        return 64


def compute_sharpness_score(image: Image.Image, max_dim: int = 1024) -> Tuple[float, bool]:
    """Calculate Laplacian variance Var(∇²I) to quantify sharpness and detect motion blur.

    Returns:
        (sharpness_score, is_blurry): Higher variance indicates crisper edges.
        Typical blurry photos have variance < 100.0.
    """
    # Downsample if image is extremely high-res to keep execution fast (<15ms)
    w, h = image.size
    if max(w, h) > max_dim:
        scale = max_dim / float(max(w, h))
        target_size = (int(w * scale), int(h * scale))
        eval_img = image.resize(target_size, Image.Resampling.BILINEAR)
    else:
        eval_img = image

    gray = eval_img.convert("L")
    arr = np.array(gray, dtype=float)

    if arr.shape[0] < 3 or arr.shape[1] < 3:
        return 0.0, True

    # Discrete 2D Laplacian operator via vectorized slicing
    # [ 0,  1,  0]
    # [ 1, -4,  1]
    # [ 0,  1,  0]
    laplacian = (
        arr[1:-1, 2:]
        + arr[1:-1, :-2]
        + arr[2:, 1:-1]
        + arr[:-2, 1:-1]
        - 4.0 * arr[1:-1, 1:-1]
    )

    variance = float(np.var(laplacian))
    is_blurry = variance < 100.0
    return round(variance, 1), is_blurry


def compute_exposure_and_color_metrics(image: Image.Image) -> Dict[str, Any]:
    """Calculate mean brightness, contrast, highlight/shadow clipping, and colorfulness.

    Colorfulness uses the Hasler and Süsstrunk metric:
    M = sqrt(std(rg)^2 + std(yb)^2) + 0.3 * sqrt(mean(rg)^2 + mean(yb)^2)
    """
    rgb = image.convert("RGB")
    arr = np.array(rgb, dtype=float)

    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    luminance = 0.299 * r + 0.587 * g + 0.114 * b

    total_pixels = float(arr.shape[0] * arr.shape[1])
    highlight_clipped = float(np.sum(luminance > 250.0)) / total_pixels
    shadow_clipped = float(np.sum(luminance < 5.0)) / total_pixels

    # Hasler & Süsstrunk Colorfulness
    rg = r - g
    yb = 0.5 * (r + g) - b
    std_rgyb = np.sqrt(np.var(rg) + np.var(yb))
    mean_rgyb = np.sqrt(np.mean(rg) ** 2 + np.mean(yb) ** 2)
    colorfulness = float(std_rgyb + 0.3 * mean_rgyb)

    return {
        "mean_brightness": round(float(np.mean(luminance)), 1),
        "contrast": round(float(np.std(luminance)), 1),
        "highlight_clipping_ratio": round(highlight_clipped, 4),
        "shadow_clipping_ratio": round(shadow_clipped, 4),
        "colorfulness": round(colorfulness, 1),
    }


def classify_media_orientation(width: int, height: int) -> Dict[str, Any]:
    """Classify aspect ratio and social format suitability.

    Returns:
        {
            "width": width,
            "height": height,
            "aspect_ratio": round(width / height, 2),
            "orientation": "vertical" | "horizontal" | "square",
            "social_format": "story_9_16" | "carousel_4_5" | "square_1_1" | "landscape_16_9"
        }
    """
    if height <= 0 or width <= 0:
        return {
            "width": width,
            "height": height,
            "aspect_ratio": 1.0,
            "orientation": "square",
            "social_format": "square_1_1",
        }

    ratio = width / height
    if ratio < 0.65:
        social_format = "story_9_16"
        orientation = "vertical"
    elif ratio < 0.90:
        social_format = "carousel_4_5"
        orientation = "vertical"
    elif 0.90 <= ratio <= 1.10:
        social_format = "square_1_1"
        orientation = "square"
    else:
        social_format = "landscape_16_9"
        orientation = "horizontal"

    return {
        "width": width,
        "height": height,
        "aspect_ratio": round(ratio, 2),
        "orientation": orientation,
        "social_format": social_format,
    }


def find_ffmpeg() -> Optional[str]:
    """Find ffmpeg binary if available on system."""
    tool = shutil.which("ffmpeg")
    if tool:
        return tool
    common_paths = [
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
    ]
    for p in common_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def analyze_video_heuristics(
    file_path: Path,
    duration_seconds: Optional[float] = None,
    ffmpeg_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Analyze video by extracting up to 3 keyframes with ffmpeg.

    Extracts frames using thumbnail/fps filtering.
    Computes pHash, dHash, peak sharpness, exposure metrics, and orientation.
    Returns None gracefully if ffmpeg is not installed or execution fails.
    """
    ffmpeg_bin = ffmpeg_path or find_ffmpeg()
    if not ffmpeg_bin:
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            out_pattern = str(tmp_path / "frame_%02d.jpg")

            dur = duration_seconds or 3.0
            if dur > 3.0:
                cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-v", "error",
                    "-i", str(file_path),
                    "-vf", "thumbnail,scale=1024:-1",
                    "-frames:v", "3",
                    out_pattern,
                ]
            else:
                cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-v", "error",
                    "-i", str(file_path),
                    "-vf", "fps=2,scale=1024:-1",
                    "-frames:v", "3",
                    out_pattern,
                ]

            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            if proc.returncode != 0:
                return None

            frame_files = sorted(tmp_path.glob("frame_*.jpg"))
            if not frame_files:
                return None

            best_sharpness = 0.0
            best_sharp_blurry = True
            best_exposure: Dict[str, Any] = {}
            primary_phash = ""
            primary_dhash = ""
            orientation_info: Dict[str, Any] = {}

            for idx, f_path in enumerate(frame_files):
                with Image.open(f_path) as img:
                    if idx == 0:
                        primary_phash = compute_phash(img)
                        primary_dhash = compute_dhash(img)
                        orientation_info = classify_media_orientation(img.width, img.height)

                    sharpness, is_blurry = compute_sharpness_score(img)
                    exposure = compute_exposure_and_color_metrics(img)

                    if sharpness >= best_sharpness:
                        best_sharpness = sharpness
                        best_sharp_blurry = is_blurry
                        best_exposure = exposure

            return {
                "phash": primary_phash,
                "dhash": primary_dhash,
                "sharpness_score": best_sharpness,
                "is_blurry": best_sharp_blurry,
                "video_frames_analyzed": len(frame_files),
                **best_exposure,
                **orientation_info,
            }
    except Exception:
        return None


def analyze_image_heuristics(file_path: Path) -> Optional[Dict[str, Any]]:
    """Analyze image and return complete visual quality and perceptual fingerprint."""
    try:
        with Image.open(file_path) as img:
            phash_val = compute_phash(img)
            dhash_val = compute_dhash(img)
            sharpness, is_blurry = compute_sharpness_score(img)
            exposure = compute_exposure_and_color_metrics(img)
            orientation_info = classify_media_orientation(img.width, img.height)

            return {
                "phash": phash_val,
                "dhash": dhash_val,
                "sharpness_score": sharpness,
                "is_blurry": is_blurry,
                **exposure,
                **orientation_info,
            }
    except Exception:
        return None
