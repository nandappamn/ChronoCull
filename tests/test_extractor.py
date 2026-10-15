"""Unit tests for metadata extraction engine."""

import os
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

from chronocull.core.extractor import (
    MAC_EPOCH_DELTA,
    extract_from_filename,
    extract_image_exif,
    extract_media_item,
    parse_datetime_str,
    parse_isobmff_quicktime_atoms,
)


def test_parse_datetime_str():
    """Verify parsing various date strings."""
    assert parse_datetime_str("2024:08:15 14:30:22") == datetime(2024, 8, 15, 14, 30, 22)
    assert parse_datetime_str("2024-08-15 14:30:22") == datetime(2024, 8, 15, 14, 30, 22)
    assert parse_datetime_str("20240815_143022") == datetime(2024, 8, 15, 14, 30, 22)

    # Subsecond test
    dt = parse_datetime_str("2024:08:15 14:30:22.450")
    assert dt == datetime(2024, 8, 15, 14, 30, 22, 450000)

    # Invalid string
    assert parse_datetime_str("invalid-date") is None


def test_filename_regex_extraction(tmp_path: Path):
    """Verify filename patterns extract correct dates."""
    f1 = tmp_path / "IMG_20230815_143022.jpg"
    res1 = extract_from_filename(f1)
    assert res1 is not None
    assert res1[0] == datetime(2023, 8, 15, 14, 30, 22)

    f2 = tmp_path / "VID_20240101_081530.mp4"
    res2 = extract_from_filename(f2)
    assert res2 is not None
    assert res2[0] == datetime(2024, 1, 1, 8, 15, 30)

    f3 = tmp_path / "PXL_20221225_235959.jpg"
    res3 = extract_from_filename(f3)
    assert res3 is not None
    assert res3[0] == datetime(2022, 12, 25, 23, 59, 59)

    # WhatsApp style date
    f4 = tmp_path / "IMG-20230412-WA0005.jpg"
    res4 = extract_from_filename(f4)
    assert res4 is not None
    assert res4[0].year == 2023
    assert res4[0].month == 4
    assert res4[0].day == 12


def test_image_exif_extraction(tmp_path: Path):
    """Verify Pillow EXIF extraction with DateTimeOriginal and subseconds."""
    img_path = tmp_path / "test_photo.jpg"

    # Create dummy image with EXIF
    img = Image.new("RGB", (64, 64), color="red")
    exif = img.getexif()
    exif[306] = "2023:09:10 11:22:33"
    exif[271] = "Canon"
    exif[272] = "EOS R5"

    sub_ifd = exif.get_ifd(0x8769)
    sub_ifd[36867] = "2023:09:10 11:22:33"
    sub_ifd[37521] = "850"

    img.save(img_path, "JPEG", exif=exif)

    item = extract_media_item(img_path)
    assert item.media_type == "image"
    assert item.timestamp == datetime(2023, 9, 10, 11, 22, 33)
    assert item.subsecond == "850"
    assert item.timestamp_source == "exif"
    assert item.metadata.get("make") == "Canon"


def test_isobmff_mp4_mvhd_parsing(tmp_path: Path):
    """Verify binary parsing of ISO-BMFF / MP4 container mvhd atom."""
    mp4_path = tmp_path / "synthetic_test.mp4"

    # Target capture time: 2023-06-15 10:20:30 UTC
    target_dt = datetime(2023, 6, 15, 10, 20, 30, tzinfo=timezone.utc)
    target_unix = int(target_dt.timestamp())
    mac_time = target_unix + MAC_EPOCH_DELTA

    # Construct mvhd atom (version 0, 108 bytes total)
    # size(4), type(4), version/flags(4), creation_time(4), mod_time(4), timescale(4), duration(4), ...
    mvhd_payload = struct.pack(
        ">I4sIIIIII",
        108,  # size
        b"mvhd",
        0,  # version 0 and flags 0
        mac_time,  # creation_time
        mac_time,  # modification_time
        1000,  # timescale
        5000,  # duration
        0x00010000,  # rate
    )
    # pad remaining 76 bytes of mvhd
    mvhd_payload += b"\x00" * (108 - len(mvhd_payload))

    # Construct moov atom wrapping mvhd
    moov_size = 8 + len(mvhd_payload)
    moov_header = struct.pack(">I4s", moov_size, b"moov")
    moov_atom = moov_header + mvhd_payload

    # Minimal ftyp box
    ftyp_box = struct.pack(">I4s4sI", 16, b"ftyp", b"isom", 512)

    with open(mp4_path, "wb") as f:
        f.write(ftyp_box)
        f.write(moov_atom)

    res = parse_isobmff_quicktime_atoms(mp4_path)
    assert res is not None
    extracted_dt, _, meta = res
    assert extracted_dt == datetime(2023, 6, 15, 10, 20, 30)


def test_quicktime_apple_creationdate_parsing(tmp_path: Path):
    """Verify extraction of Apple com.apple.quicktime.creationdate metadata."""
    mov_path = tmp_path / "apple_video.mov"

    # Include Apple ISO creationdate string
    creation_str = b"2024-05-20T17:45:10+0200"
    moov_payload = b"some_keys_metadata_atom_" + creation_str + b"_more_data"
    moov_box = struct.pack(">I4s", len(moov_payload) + 8, b"moov") + moov_payload
    ftyp_box = struct.pack(">I4s4sI", 16, b"ftyp", b"qt  ", 512)

    with open(mov_path, "wb") as f:
        f.write(ftyp_box)
        f.write(moov_box)

    item = extract_media_item(mov_path)
    assert item.media_type == "video"
    assert item.timestamp_source == "quicktime_atom"
    assert item.timestamp.year == 2024
    assert item.timestamp.month == 5
    assert item.timestamp.day == 20
    assert item.timestamp.hour == 17
    assert item.timestamp.minute == 45
    assert item.timestamp.second == 10


def test_gps_conversion_and_optics(tmp_path: Path):
    """Verify conversion of EXIF GPS DMS and optics metadata."""
    from chronocull.core.extractor import convert_dms_to_degrees

    # Test convert_dms_to_degrees
    assert convert_dms_to_degrees((31, 1, 33.691), "N") == 31.026025
    assert convert_dms_to_degrees((77, 6, 58.473), "E") == 77.116242
    assert convert_dms_to_degrees((33, 51, 21.0), "S") == -33.855833
    assert convert_dms_to_degrees((151, 12, 55.0), "W") == -151.215278
    assert convert_dms_to_degrees(None, "N") is None

    # Test image with EXIF GPS and optics
    img_path = tmp_path / "gps_optics_test.jpg"
    img = Image.new("RGB", (100, 80), color="blue")
    exif = img.getexif()
    exif[306] = "2023:07:04 12:00:00"
    exif[271] = "Sony"
    exif[272] = "ILCE-7M4"

    sub_ifd = exif.get_ifd(0x8769)
    sub_ifd[36867] = "2023:07:04 12:00:00"
    sub_ifd[34855] = 200  # ISO
    sub_ifd[33437] = 2.8  # FNumber
    sub_ifd[37386] = 35.0  # FocalLength

    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1] = "N"
    gps_ifd[2] = (48, 51, 24.0)
    gps_ifd[3] = "E"
    gps_ifd[4] = (2, 21, 7.0)
    gps_ifd[6] = 35.5

    img.save(img_path, "JPEG", exif=exif)

    item = extract_media_item(img_path)
    assert item.metadata.get("has_gps") is True
    assert item.metadata.get("gps_lat") == 48.856667
    assert item.metadata.get("gps_lon") == 2.351944
    assert item.metadata.get("gps_alt") == 35.5
    assert item.metadata.get("iso") == 200
    assert item.metadata.get("f_number") == 2.8
    assert item.metadata.get("focal_length") == 35.0
    assert item.metadata.get("width") == 100
    assert item.metadata.get("height") == 80


def test_quicktime_iso6709_and_duration(tmp_path: Path):
    """Verify extraction of ISO-6709 coordinates and duration from MP4."""
    mp4_path = tmp_path / "geo_video.mp4"

    target_dt = datetime(2023, 6, 15, 10, 20, 30, tzinfo=timezone.utc)
    target_unix = int(target_dt.timestamp())
    mac_time = target_unix + MAC_EPOCH_DELTA

    # mvhd with duration 10 seconds (timescale 1000, duration 10000)
    mvhd_payload = struct.pack(
        ">I4sIIIIII",
        108,
        b"mvhd",
        0,
        mac_time,
        mac_time,
        1000,  # timescale
        10000,  # duration = 10s
        0x00010000,
    )
    mvhd_payload += b"\x00" * (108 - len(mvhd_payload))

    # Add ISO-6709 coordinate payload: +48.8566+002.3519+035.0/
    iso_atom = b"xyz_data_+48.8566+002.3519+035.0/_end"
    moov_payload = mvhd_payload + iso_atom
    moov_box = struct.pack(">I4s", len(moov_payload) + 8, b"moov") + moov_payload
    ftyp_box = struct.pack(">I4s4sI", 16, b"ftyp", b"mp42", 512)

    with open(mp4_path, "wb") as f:
        f.write(ftyp_box)
        f.write(moov_box)

    item = extract_media_item(mp4_path)
    assert item.metadata.get("duration_seconds") == 10.0
    assert item.metadata.get("gps_lat") == 48.8566
    assert item.metadata.get("gps_lon") == 2.3519
    assert item.metadata.get("gps_alt") == 35.0

