"""Unit tests for configuration management and .env loading."""

import os
from pathlib import Path
from unittest.mock import patch

from chronocull.config import load_dotenv, GEMINI_MODEL, GEMINI_BASE_URL
from chronocull.core.extractor import find_exiftool
from chronocull.core.vlm_client import GeminiClient
from chronocull.core.enricher import ApifyEnricher


def test_load_dotenv_parses_variables(tmp_path: Path):
    """Verify load_dotenv correctly parses key-value pairs, ignores comments, and preserves shell env."""
    test_env = tmp_path / ".env"
    test_env.write_text(
        "# Test comment\n"
        "TEST_CUSTOM_KEY1=value_1\n"
        'TEST_CUSTOM_KEY2="quoted_value_2"\n'
        "TEST_CUSTOM_KEY3='single_quoted_3'\n"
        "   # indented comment\n"
        "\n"
        "TEST_EXISTING_KEY=new_val\n"
    )

    # Set an existing key to verify it is NOT overwritten
    os.environ["TEST_EXISTING_KEY"] = "original_val"

    try:
        load_dotenv(test_env)
        assert os.environ.get("TEST_CUSTOM_KEY1") == "value_1"
        assert os.environ.get("TEST_CUSTOM_KEY2") == "quoted_value_2"
        assert os.environ.get("TEST_CUSTOM_KEY3") == "single_quoted_3"
        assert os.environ.get("TEST_EXISTING_KEY") == "original_val"
    finally:
        os.environ.pop("TEST_CUSTOM_KEY1", None)
        os.environ.pop("TEST_CUSTOM_KEY2", None)
        os.environ.pop("TEST_CUSTOM_KEY3", None)
        os.environ.pop("TEST_EXISTING_KEY", None)


def test_vlm_client_respects_custom_model_and_base_url():
    """Verify GeminiClient uses environment-configured model and base_url."""
    with patch.dict(os.environ, {
        "GEMINI_API_KEY": "fake_test_key",
        "GEMINI_MODEL": "gemini-custom-flash",
        "GEMINI_BASE_URL": "http://127.0.0.1:20128/v1/models"
    }):
        client = GeminiClient()
        assert client.model == "gemini-custom-flash"
        assert client.base_url == "http://127.0.0.1:20128/v1/models"


def test_find_exiftool_respects_custom_path(tmp_path: Path):
    """Verify find_exiftool prefers EXIFTOOL_PATH environment variable."""
    fake_tool = tmp_path / "mock_exiftool"
    fake_tool.write_text("#!/bin/sh\necho 1")
    fake_tool.chmod(0o755)

    with patch.dict(os.environ, {"EXIFTOOL_PATH": str(fake_tool)}):
        resolved = find_exiftool()
        assert resolved == str(fake_tool)


def test_apify_enricher_respects_custom_base_url():
    """Verify ApifyEnricher uses custom APIFY_API_BASE from environment."""
    with patch.dict(os.environ, {
        "APIFY_TOKEN": "mock_apify_token",
        "APIFY_API_BASE": "https://custom.apify.proxy.io/v2/"
    }):
        enricher = ApifyEnricher()
        assert enricher.api_base == "https://custom.apify.proxy.io/v2"


def test_resolve_output_dir(tmp_path: Path):
    """Verify resolve_output_dir defaults to output/<name> and honors explicit output_dir."""
    from chronocull.config import resolve_output_dir

    sample_folder = tmp_path / "my_trip"
    sample_folder.mkdir()

    # 1. Explicit output dir
    custom_out = tmp_path / "custom_destination"
    resolved_custom = resolve_output_dir(sample_folder, str(custom_out))
    assert resolved_custom == custom_out.resolve()

    # 2. Default output dir
    resolved_default = resolve_output_dir(sample_folder)
    assert resolved_default.name == "my_trip"
    assert resolved_default.parent.name == "output"

