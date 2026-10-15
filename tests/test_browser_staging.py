"""Tests for browser staging assistant."""

from pathlib import Path
from chronocull.core.browser_staging import check_browser_use_available, run_browser_staging


def test_browser_staging_fallback(tmp_path: Path):
    """Verify run_browser_staging returns clean message without crashing when browser-use is absent."""
    result = run_browser_staging(tmp_path / "stage_dir")
    assert "installed" in result
    assert "message" in result
    if not result["installed"]:
        assert result["success"] is False
        assert "pip install 'chronocull[agent]'" in result["message"]

