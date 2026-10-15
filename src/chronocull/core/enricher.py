"""Apify data enrichment module for Phase 2 Narrative Storytelling.

This module provides a dependency-free client to execute Apify actors
(like Google Places Scraper or Google Search Scraper) to pull rich
historical, contextual, and review data for trip stops.
"""

import json
import logging
import os
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from chronocull.config import APIFY_ACTOR_PLACES, APIFY_API_BASE
from chronocull.core.clustering import TripClusterResult, TripStop

logger = logging.getLogger("chronocull.enricher")


class ApifyEnricher:
    """Client for Apify API to enrich trip stops with external web context."""

    def __init__(self, token: Optional[str] = None, api_base: Optional[str] = None):
        self.token = token or os.environ.get("APIFY_TOKEN")
        if not self.token:
            raise ValueError("APIFY_TOKEN must be set in environment or passed to ApifyEnricher.")
        self.api_base = (api_base or os.environ.get("APIFY_API_BASE", APIFY_API_BASE)).rstrip("/")

    def _run_actor_sync(self, actor_id: str, input_json: Dict[str, Any], timeout_secs: int = 300) -> List[Dict[str, Any]]:
        """Run an Apify actor synchronously and return its dataset items."""
        actor_path = actor_id.replace("/", "~")
        url = f"{self.api_base}/acts/{actor_path}/runs?token={self.token}"
        req = urllib.request.Request(
            url,
            data=json.dumps(input_json).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        logger.info(f"Starting Apify actor {actor_id}...")
        try:
            with urllib.request.urlopen(req) as response:
                run_data = json.loads(response.read().decode())["data"]
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode()
            logger.error(f"Apify API error: {error_msg}")
            raise RuntimeError(f"Failed to start actor {actor_id}: {e.code} {e.reason}")

        run_id = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]
        
        # Poll for completion
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout_secs:
                raise TimeoutError(f"Actor {actor_id} (run {run_id}) timed out after {timeout_secs}s")

            status_url = f"{self.api_base}/actor-runs/{run_id}?token={self.token}"
            try:
                with urllib.request.urlopen(status_url) as response:
                    status_data = json.loads(response.read().decode())["data"]
                    status = status_data["status"]
            except urllib.error.HTTPError as e:
                logger.warning(f"Error polling run status: {e.code} {e.reason}")
                time.sleep(5)
                continue

            if status in ["SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"]:
                if status != "SUCCEEDED":
                    raise RuntimeError(f"Actor run {run_id} finished with non-success status: {status}")
                break
            
            logger.debug(f"Actor {actor_id} status: {status}. Waiting...")
            time.sleep(3)
            
        # Fetch dataset items
        ds_url = f"{self.api_base}/datasets/{dataset_id}/items?token={self.token}"
        logger.info(f"Actor {actor_id} succeeded. Fetching dataset {dataset_id}...")
        with urllib.request.urlopen(ds_url) as response:
            items = json.loads(response.read().decode())
        
        return items

    def enrich_places(self, stops: List[TripStop]) -> None:
        """Enrich a list of TripStops using the Apify Google Places crawler.
        
        Updates the 'apify_context' attribute of each Stop in-place.
        """
        # Collect stops that have valid titles/locations but are missing context
        search_queries = []
        stop_mapping = []

        for stop in stops:
            if stop.transit_status != "dwell":
                continue
            if stop.apify_context is not None:
                continue
                
            city = stop.location.get("city") or stop.location.get("state")
            if not city and not stop.title:
                continue
                
            # If we have a landmark title, search for that exact landmark in that city.
            # E.g., "Eiffel Tower, Paris"
            query = f"{stop.title}, {city}" if stop.title and city else stop.title or city
            search_queries.append({"searchString": query})
            stop_mapping.append(stop)

        if not search_queries:
            logger.info("No stops require POI enrichment.")
            return

        input_data = {
            "searchStringsArray": [q["searchString"] for q in search_queries],
            "maxCrawledPlacesPerSearch": 1,
            "language": "en",
            "scrapeReviewerName": False,
            "scrapeReviews": True,
            "reviewsSort": "highestRanking",
            "maxReviews": 3,
        }

        actor_id = os.environ.get("APIFY_ACTOR_PLACES", APIFY_ACTOR_PLACES)
        try:
            results = self._run_actor_sync(actor_id, input_data)
        except Exception as e:
            logger.error(f"Apify places enrichment failed: {e}")
            return

        # Map results back to stops
        # The actor results usually contain 'searchString' so we can map them back.
        # If not, we map sequentially (assuming 1 maxCrawledPlacesPerSearch).
        for i, stop in enumerate(stop_mapping):
            if i < len(results):
                place_data = results[i]
                stop.apify_context = {
                    "source": "apify/compass/crawler-google-places",
                    "title": place_data.get("title"),
                    "category": place_data.get("categoryName"),
                    "rating": place_data.get("totalScore"),
                    "reviews_count": place_data.get("reviewsCount"),
                    "description": place_data.get("description"),
                    "website": place_data.get("website"),
                    "address": place_data.get("address"),
                    "top_reviews": [
                        r.get("text") for r in place_data.get("reviews", []) if r.get("text")
                    ]
                }
                logger.info(f"Enriched stop '{stop.title}' -> '{place_data.get('title')}'")


def run_enrichment_pipeline(cluster_result: TripClusterResult) -> None:
    """Master entrypoint to run all Apify enrichments on a TripClusterResult."""
    if not os.environ.get("APIFY_TOKEN"):
        logger.warning("APIFY_TOKEN not found. Skipping Apify enrichment phase.")
        return
        
    enricher = ApifyEnricher()
    all_stops = [stop for day in cluster_result.days for stop in day.stops]
    
    logger.info(f"Starting Apify POI enrichment for {len(all_stops)} stops...")
    enricher.enrich_places(all_stops)

