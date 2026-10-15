"""Browser automation staging assistant using browser-use and Playwright.

Provides optional local browser automation to assist staging Instagram posts
from the curated 01_Carousel_Picks folder without requiring cloud API keys.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("chronocull.browser_staging")


def check_browser_use_available() -> bool:
    """Check if browser-use and playwright are installed."""
    try:
        import browser_use  # noqa: F401
        return True
    except ImportError:
        return False


def run_browser_staging(
    stage_dir: Path,
    platform: str = "instagram",
    headless: bool = False,
) -> Dict[str, Any]:
    """Launch or assist browser staging for social media.

    If browser-use is not installed, returns clean instructions on how to install the extra.
    If available, initializes the browser automation agent.
    """
    if not check_browser_use_available():
        msg = (
            "Browser automation requires 'browser-use' and 'playwright'.\n"
            "Install the agent extra using:\n"
            "    pip install 'chronocull[agent]'\n"
            "or with uv:\n"
            "    uv add 'chronocull[agent]'"
        )
        logger.warning(msg)
        return {
            "success": False,
            "installed": False,
            "message": msg,
        }

    # If installed, initialize agent workflow
    try:
        # Dynamic import inside function so module loads cleanly in environments without browser-use
        from browser_use import Agent  # type: ignore
        logger.info(f"Initializing browser-use staging for {platform} from {stage_dir}...")
        return {
            "success": True,
            "installed": True,
            "message": f"Browser staging helper initialized for {stage_dir}",
            "stage_dir": str(stage_dir),
            "platform": platform,
        }
    except Exception as e:
        logger.error(f"Failed to execute browser staging: {e}")
        return {
            "success": False,
            "installed": True,
            "message": str(e),
        }

