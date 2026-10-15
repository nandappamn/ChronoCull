"""Unit tests for heuristics module (pHash, dHash, sharpness, and exposure metrics)."""

from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from chronocull.utils.heuristics import (
    analyze_image_heuristics,
    analyze_video_heuristics,
    classify_media_orientation,
    compute_dhash,
    compute_exposure_and_color_metrics,
    compute_phash,
    compute_sharpness_score,
    hamming_distance,
)


def test_perceptual_hashes(tmp_path: Path):
    """Verify pHash and dHash calculation and Hamming distance behavior."""
    # Create base image with geometric shapes (strong features)
    img1 = Image.new("RGB", (200, 200), color="white")
    draw = ImageDraw.Draw(img1)
    draw.ellipse([30, 30, 90, 90], fill="red", outline="black")
    draw.rectangle([110, 110, 180, 180], fill="blue", outline="black")

    # Identical image
    img2 = img1.copy()

    # Near-duplicate: slight crop/resize (simulating camera burst hand tremor)
    img_near = img1.crop((2, 2, 198, 198)).resize((200, 200))

    # Completely different image (black)
    img_diff = Image.new("RGB", (200, 200), color="black")

    h1_phash = compute_phash(img1)
    h2_phash = compute_phash(img2)
    h_near_phash = compute_phash(img_near)
    h_diff_phash = compute_phash(img_diff)

    h1_dhash = compute_dhash(img1)
    h2_dhash = compute_dhash(img2)
    h_near_dhash = compute_dhash(img_near)
    h_diff_dhash = compute_dhash(img_diff)

    # Identical images must have distance 0
    assert hamming_distance(h1_phash, h2_phash) == 0
    assert hamming_distance(h1_dhash, h2_dhash) == 0

    # Near duplicates must have low distance (<= 6)
    assert hamming_distance(h1_phash, h_near_phash) <= 6
    assert hamming_distance(h1_dhash, h_near_dhash) <= 6

    # Distinct images must have high distance (>= 15)
    assert hamming_distance(h1_phash, h_diff_phash) >= 15
    assert hamming_distance(h1_dhash, h_diff_dhash) >= 15


def test_sharpness_and_blur_detection(tmp_path: Path):
    """Verify Laplacian variance correctly distinguishes sharp vs blurred images."""
    # Sharp image with high-contrast edges
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    arr[50:150, 50:150] = [255, 255, 255]
    sharp_img = Image.fromarray(arr)

    # Blurred version of the same image
    blurred_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=8))

    sharp_score, sharp_blurry = compute_sharpness_score(sharp_img)
    blur_score, blur_blurry = compute_sharpness_score(blurred_img)

    assert sharp_score > blur_score
    assert sharp_score > 200.0
    assert sharp_blurry is False
    assert blur_score < 100.0
    assert blur_blurry is True


def test_exposure_and_colorfulness():
    """Verify exposure metrics and colorfulness scoring."""
    # Monochrome dark image
    dark_arr = np.full((100, 100, 3), 10, dtype=np.uint8)
    dark_img = Image.fromarray(dark_arr)
    m_dark = compute_exposure_and_color_metrics(dark_img)
    assert m_dark["mean_brightness"] < 20.0
    assert m_dark["colorfulness"] < 5.0

    # High saturation colorful image
    color_arr = np.zeros((100, 100, 3), dtype=np.uint8)
    color_arr[:, :50] = [255, 0, 0]
    color_arr[:, 50:] = [0, 255, 0]
    color_img = Image.fromarray(color_arr)
    m_color = compute_exposure_and_color_metrics(color_img)
    assert m_color["colorfulness"] > 50.0


def test_analyze_image_heuristics(tmp_path: Path):
    """Verify end-to-end file heuristic analysis."""
    test_file = tmp_path / "test.jpg"
    img = Image.new("RGB", (64, 64), color="orange")
    img.save(test_file)

    res = analyze_image_heuristics(test_file)
    assert res is not None
    assert "phash" in res
    assert "dhash" in res
    assert "sharpness_score" in res
    assert "is_blurry" in res
    assert "mean_brightness" in res
    assert "colorfulness" in res
    assert res["social_format"] == "square_1_1"
    assert res["orientation"] == "square"


def test_classify_media_orientation():
    """Verify aspect ratio classification for 9:16 stories, 4:5 carousels, 1:1 square, and 16:9 landscape."""
    # 9:16 Vertical Story (e.g., 1080x1920)
    story = classify_media_orientation(1080, 1920)
    assert story["social_format"] == "story_9_16"
    assert story["orientation"] == "vertical"

    # 4:5 Carousel Pick (e.g., 1080x1350)
    carousel = classify_media_orientation(1080, 1350)
    assert carousel["social_format"] == "carousel_4_5"
    assert carousel["orientation"] == "vertical"

    # 1:1 Square (e.g., 1000x1000)
    sq = classify_media_orientation(1000, 1000)
    assert sq["social_format"] == "square_1_1"
    assert sq["orientation"] == "square"

    # 16:9 Landscape (e.g., 1920x1080)
    land = classify_media_orientation(1920, 1080)
    assert land["social_format"] == "landscape_16_9"
    assert land["orientation"] == "horizontal"


def test_analyze_video_heuristics_missing_ffmpeg(tmp_path: Path):
    """Verify analyze_video_heuristics returns None gracefully when ffmpeg is not available."""
    dummy_video = tmp_path / "clip.mp4"
    dummy_video.write_text("dummy")

    res = analyze_video_heuristics(dummy_video, ffmpeg_path="/nonexistent/binary/ffmpeg")
    assert res is None


def test_analyze_video_heuristics_mocked(tmp_path: Path, monkeypatch):
    """Verify analyze_video_heuristics extracts metrics when ffmpeg produces frame images."""
    import subprocess

    dummy_video = tmp_path / "clip.mp4"
    dummy_video.write_text("dummy")

    def mock_subprocess_run(cmd, *args, **kwargs):
        # Find output pattern in command
        out_pattern = cmd[-1]
        out_dir = Path(out_pattern).parent
        # Create 2 synthesized frames
        f1 = out_dir / "frame_01.jpg"
        f2 = out_dir / "frame_02.jpg"
        Image.new("RGB", (1080, 1920), color="blue").save(f1)
        Image.new("RGB", (1080, 1920), color="red").save(f2)
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    res = analyze_video_heuristics(dummy_video, ffmpeg_path="fake_ffmpeg")
    assert res is not None
    assert res["video_frames_analyzed"] == 2
    assert res["social_format"] == "story_9_16"
    assert res["orientation"] == "vertical"
    assert "phash" in res
    assert "sharpness_score" in res

