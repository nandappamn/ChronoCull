"""Multi-tier metadata extraction engine for images and videos."""

import json
import os
import re
import shutil
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from PIL import ExifTags, Image

from chronocull.config import EXIFTOOL_PATH, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from chronocull.models import MediaItem

# Mac epoch (1904-01-01) to Unix epoch (1970-01-01) delta in seconds
MAC_EPOCH_DELTA = 2082844800

# Regex patterns for filename timestamp extraction
FILENAME_PATTERNS = [
    # YYYYMMDD_HHMMSS or YYYY-MM-DD_HH-MM-SS with optional prefix (IMG_, VID_, PXL_, etc.)
    re.compile(
        r"(?:IMG|VID|PXL|FILE|DSC|MOV|MVI|DJI|GOPR|GP|AUD)?[_-]?([12]\d{3})[-_]?([01]\d)[-_]?([0-3]\d)[-_T ]([0-2]\d)[-_:.]([0-5]\d)[-_:.]([0-5]\d)(?:[_-](\d{2,6}))?",
        re.IGNORECASE,
    ),
    # Compact YYYYMMDD_HHMMSS
    re.compile(
        r"(?:IMG|VID|PXL|FILE|DSC|MOV|MVI|DJI|GOPR|GP)?[_-]?([12]\d{3})([01]\d)([0-3]\d)[_-]?([0-2]\d)([0-5]\d)([0-5]\d)",
        re.IGNORECASE,
    ),
    # WhatsApp export: IMG-YYYYMMDD-WA0001 or VID-YYYYMMDD-WA0001
    re.compile(
        r"(?:IMG|VID)-([12]\d{3})([01]\d)([0-3]\d)-WA\d+",
        re.IGNORECASE,
    ),
    # Date only: YYYY-MM-DD or YYYYMMDD
    re.compile(
        r"([12]\d{3})[-_]([01]\d)[-_]([0-3]\d)",
        re.IGNORECASE,
    ),
]


def find_exiftool() -> Optional[str]:
    """Find exiftool binary on system if available."""
    custom_path = os.environ.get("EXIFTOOL_PATH") or EXIFTOOL_PATH
    if custom_path and os.path.isfile(custom_path) and os.access(custom_path, os.X_OK):
        return custom_path

    tool = shutil.which("exiftool")
    if tool:
        return tool
    common_paths = [
        "/opt/homebrew/bin/exiftool",
        "/usr/local/bin/exiftool",
        "/usr/bin/exiftool",
    ]
    for p in common_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def parse_datetime_str(val: str) -> Optional[datetime]:
    """Parse various datetime string formats into a datetime object."""
    if not val or not isinstance(val, str):
        return None
    val = val.strip()

    # Handle ISO 8601 strings like 2024-08-15T14:30:22+02:00 or 2024-08-15T14:30:22Z
    try:
        dt = datetime.fromisoformat(val)
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        pass

    # Standard EXIF format: "YYYY:MM:DD HH:MM:SS" (possibly with subseconds or timezone)
    formats = [
        "%Y:%m:%d %H:%M:%S",
        "%Y:%m:%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y/%m/%d %H:%M:%S",
        "%Y:%m:%d %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y%m%d_%H%M%S",
        "%Y-%m-%dT%H:%M:%S",
    ]

    # Clean subsecond if present, e.g. "2024:08:15 14:30:22.123"
    clean_val = val
    if "." in clean_val:
        base, sep, rem = clean_val.partition(".")
        # keep up to 6 digits for microseconds
        sub = re.match(r"^(\d+)(.*)$", rem)
        if sub:
            digits, tz = sub.group(1)[:6].ljust(6, "0"), sub.group(2)
            clean_val = f"{base}.{digits}{tz}"
            formats = ["%Y:%m:%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f"] + formats

    for fmt in formats:
        try:
            parsed = datetime.strptime(clean_val, fmt)
            return parsed.replace(tzinfo=None)
        except (ValueError, TypeError):
            continue

    return None


def convert_dms_to_degrees(dms: Any, ref: Optional[str]) -> Optional[float]:
    """Convert EXIF DMS tuple/IFDRational to signed decimal degrees."""
    if not dms or len(dms) < 3:
        return None
    try:
        deg = float(dms[0])
        min_ = float(dms[1])
        sec = float(dms[2])
        decimal = deg + (min_ / 60.0) + (sec / 3600.0)
        if ref and str(ref).strip().upper() in ("S", "W"):
            decimal = -decimal
        if not (-180.0 <= decimal <= 180.0):
            return None
        return round(decimal, 6)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def extract_with_exiftool(file_path: Path) -> Optional[Tuple[datetime, Optional[str], Dict[str, Any]]]:
    """Extract metadata using external exiftool binary if available."""
    tool = find_exiftool()
    if not tool:
        return None

    try:
        cmd = [
            tool,
            "-j",
            "-DateTimeOriginal",
            "-CreateDate",
            "-CreationDate",
            "-SubSecTimeOriginal",
            "-OffsetTimeOriginal",
            "-Make",
            "-Model",
            "-GPSLatitude",
            "-GPSLongitude",
            "-GPSAltitude",
            "-FocalLength",
            "-FocalLengthIn35mmFormat",
            "-FNumber",
            "-ISO",
            "-ExposureTime",
            "-LensModel",
            str(file_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if res.returncode != 0 or not res.stdout:
            return None

        data = json.loads(res.stdout)
        if not data or not isinstance(data, list):
            return None
        info = data[0]

        date_keys = ["CreationDate", "DateTimeOriginal", "CreateDate"]
        dt: Optional[datetime] = None
        for k in date_keys:
            if k in info:
                dt = parse_datetime_str(str(info[k]))
                if dt:
                    break

        if not dt:
            return None

        subsec = str(info.get("SubSecTimeOriginal", "")) if info.get("SubSecTimeOriginal") else None
        meta: Dict[str, Any] = {
            "make": info.get("Make"),
            "model": info.get("Model"),
            "lens_model": info.get("LensModel"),
        }
        if "GPSLatitude" in info and "GPSLongitude" in info:
            try:
                meta["gps_lat"] = round(float(info["GPSLatitude"]), 6)
                meta["gps_lon"] = round(float(info["GPSLongitude"]), 6)
                meta["has_gps"] = True
            except (ValueError, TypeError):
                pass
        if "GPSAltitude" in info:
            try:
                meta["gps_alt"] = round(float(info["GPSAltitude"]), 1)
            except (ValueError, TypeError):
                pass
        if "ISO" in info:
            try:
                meta["iso"] = int(info["ISO"])
            except (ValueError, TypeError):
                pass
        if "FNumber" in info:
            try:
                meta["f_number"] = round(float(info["FNumber"]), 1)
            except (ValueError, TypeError):
                pass
        if "FocalLength" in info:
            try:
                meta["focal_length"] = round(float(str(info["FocalLength"]).replace("mm", "").strip()), 1)
            except (ValueError, TypeError):
                pass
        if "ExposureTime" in info:
            try:
                meta["exposure_time"] = float(info["ExposureTime"])
            except (ValueError, TypeError):
                pass

        return (dt, subsec, {k: v for k, v in meta.items() if v is not None})
    except Exception:
        return None


def extract_image_exif(file_path: Path) -> Optional[Tuple[datetime, Optional[str], Dict[str, Any]]]:
    """Extract EXIF metadata from image using Pillow."""
    try:
        with Image.open(file_path) as img:
            meta: Dict[str, Any] = {
                "width": img.width,
                "height": img.height,
            }
            exif_data = img.getexif()
            if not exif_data:
                return None

            dt_str: Optional[str] = None
            subsec: Optional[str] = None

            # Check primary IFD tags
            # 306 = DateTime, 271 = Make, 272 = Model, 274 = Orientation
            if 306 in exif_data:
                dt_str = str(exif_data[306])
            if 271 in exif_data:
                meta["make"] = str(exif_data[271]).strip()
            if 272 in exif_data:
                meta["model"] = str(exif_data[272]).strip()
            if 274 in exif_data:
                try:
                    meta["orientation"] = int(exif_data[274])
                except (ValueError, TypeError):
                    pass

            # Check Exif SubIFD (0x8769 = 34665)
            sub_ifd = None
            try:
                sub_ifd = exif_data.get_ifd(0x8769)
            except Exception:
                pass

            if sub_ifd:
                # 36867 = DateTimeOriginal, 36868 = DateTimeDigitized, 37521 = SubSecTimeOriginal
                if 36867 in sub_ifd:
                    dt_str = str(sub_ifd[36867])
                elif 36868 in sub_ifd and not dt_str:
                    dt_str = str(sub_ifd[36868])

                if 37521 in sub_ifd:
                    subsec = str(sub_ifd[37521]).strip()

                # Exposure & Optics
                if 33434 in sub_ifd:  # ExposureTime
                    try:
                        exp = sub_ifd[33434]
                        meta["exposure_time"] = float(exp) if exp else None
                    except (ValueError, TypeError):
                        pass
                if 33437 in sub_ifd:  # FNumber
                    try:
                        fn = sub_ifd[33437]
                        meta["f_number"] = round(float(fn), 1) if fn else None
                    except (ValueError, TypeError):
                        pass
                if 34855 in sub_ifd:  # ISOSpeedRatings
                    try:
                        meta["iso"] = int(sub_ifd[34855])
                    except (ValueError, TypeError):
                        pass
                if 37386 in sub_ifd:  # FocalLength
                    try:
                        fl = sub_ifd[37386]
                        meta["focal_length"] = round(float(fl), 1) if fl else None
                    except (ValueError, TypeError):
                        pass
                if 41989 in sub_ifd:  # FocalLengthIn35mmFilm
                    try:
                        meta["focal_length_35mm"] = int(sub_ifd[41989])
                    except (ValueError, TypeError):
                        pass
                if 37385 in sub_ifd:  # Flash
                    try:
                        meta["flash"] = int(sub_ifd[37385])
                    except (ValueError, TypeError):
                        pass
                if 42036 in sub_ifd:  # LensModel
                    meta["lens_model"] = str(sub_ifd[42036]).strip()

            # Check GPS IFD (0x8825 = 34853)
            try:
                gps_ifd = exif_data.get_ifd(0x8825)
                if gps_ifd:
                    lat_ref = gps_ifd.get(1)
                    lat_dms = gps_ifd.get(2)
                    lon_ref = gps_ifd.get(3)
                    lon_dms = gps_ifd.get(4)

                    lat = convert_dms_to_degrees(lat_dms, lat_ref)
                    lon = convert_dms_to_degrees(lon_dms, lon_ref)

                    if lat is not None and lon is not None:
                        meta["gps_lat"] = lat
                        meta["gps_lon"] = lon
                        meta["has_gps"] = True

                        if 6 in gps_ifd:
                            try:
                                alt = float(gps_ifd[6])
                                if gps_ifd.get(5) == 1:
                                    alt = -alt
                                meta["gps_alt"] = round(alt, 1)
                            except (ValueError, TypeError):
                                pass

                        if 17 in gps_ifd:
                            try:
                                meta["gps_direction"] = round(float(gps_ifd[17]), 1)
                            except (ValueError, TypeError):
                                pass
                        if 12 in gps_ifd:
                            try:
                                meta["gps_speed"] = round(float(gps_ifd[12]), 1)
                            except (ValueError, TypeError):
                                pass
                    elif 0 in gps_ifd or gps_ifd:
                        meta["has_gps"] = False
            except Exception:
                pass

            if not dt_str:
                return None

            dt = parse_datetime_str(dt_str)
            if not dt:
                return None

            return (dt, subsec, {k: v for k, v in meta.items() if v is not None})
    except Exception:
        return None


def parse_isobmff_quicktime_atoms(file_path: Path) -> Optional[Tuple[datetime, Optional[str], Dict[str, Any]]]:
    """Pure-Python parser for MP4 / QuickTime MOV atom boxes (moov.mvhd and metadata keys).

    Traverses box headers without loading media payload (mdat) into memory.
    Extracts creation_time (Mac epoch) and Apple creationdate strings.
    """
    try:
        file_size = file_path.stat().st_size
        with open(file_path, "rb") as f:
            moov_data: Optional[bytes] = None

            # Top-level scan for 'moov' atom
            while f.tell() < file_size:
                header = f.read(8)
                if len(header) < 8:
                    break
                box_size, box_type = struct.unpack(">I4s", header)

                if box_size == 1:
                    # 64-bit extended size
                    ext_header = f.read(8)
                    if len(ext_header) < 8:
                        break
                    box_size = struct.unpack(">Q", ext_header)[0]
                    payload_size = box_size - 16
                elif box_size == 0:
                    payload_size = file_size - f.tell()
                else:
                    payload_size = box_size - 8

                if payload_size < 0:
                    break

                if box_type == b"moov":
                    # moov atom contains metadata, load moov payload
                    moov_data = f.read(min(payload_size, 32 * 1024 * 1024))
                    break
                else:
                    # Skip non-moov payloads (e.g. giant mdat payload)
                    f.seek(payload_size, os.SEEK_CUR)

            if not moov_data:
                return None

            # Parse inside moov
            creation_date_str: Optional[str] = None
            mvhd_timestamp: Optional[int] = None
            meta: Dict[str, Any] = {}

            # 1. Search for Apple creationdate string in moov data
            # Apple QuickTime puts "com.apple.quicktime.creationdate" or "©day" in meta/ilst
            apple_date_pattern = re.search(
                rb"([12]\d{3}-[01]\d-[0-3]\dT[0-2]\d:[0-5]\d:[0-5]\d(?:[+-][0-2]\d:?[0-5]\d|Z)?)",
                moov_data,
            )
            if apple_date_pattern:
                try:
                    creation_date_str = apple_date_pattern.group(1).decode("ascii")
                except Exception:
                    pass

            # 2. Parse mvhd atom inside moov (duration, timescale, timestamp)
            mvhd_pos = moov_data.find(b"mvhd")
            if mvhd_pos != -1 and mvhd_pos >= 4:
                # mvhd box header is 4 bytes before 'mvhd'
                box_start = mvhd_pos - 4
                mvhd_payload = moov_data[box_start:]
                if len(mvhd_payload) >= 28:
                    version = mvhd_payload[8]  # 8 is after size (4) + type (4)
                    timescale = 0
                    duration = 0
                    if version == 0 and len(mvhd_payload) >= 28:
                        raw_time = struct.unpack(">I", mvhd_payload[12:16])[0]
                        timescale = struct.unpack(">I", mvhd_payload[20:24])[0]
                        duration = struct.unpack(">I", mvhd_payload[24:28])[0]
                    elif version == 1 and len(mvhd_payload) >= 40:
                        raw_time = struct.unpack(">Q", mvhd_payload[12:20])[0]
                        timescale = struct.unpack(">I", mvhd_payload[28:32])[0]
                        duration = struct.unpack(">Q", mvhd_payload[32:40])[0]
                    else:
                        raw_time = 0

                    if timescale > 0 and duration > 0:
                        meta["duration_seconds"] = round(duration / timescale, 2)

                    if raw_time > MAC_EPOCH_DELTA:
                        unix_time = raw_time - MAC_EPOCH_DELTA
                        # Valid range check (between 1971 and 2100)
                        if 31536000 < unix_time < 4102444800:
                            mvhd_timestamp = unix_time

            # 3. Search for ISO-6709 coordinates in video moov metadata (e.g. iPhone MOV/MP4)
            iso_match = re.search(
                rb"([+-]\d{2,3}(?:\.\d+)?)([+-]\d{2,3}(?:\.\d+)?)(?:([+-]\d+(?:\.\d+)?))?/",
                moov_data,
            )
            if iso_match:
                try:
                    lat_val = float(iso_match.group(1).decode("ascii"))
                    lon_val = float(iso_match.group(2).decode("ascii"))
                    if -90.0 <= lat_val <= 90.0 and -180.0 <= lon_val <= 180.0:
                        meta["gps_lat"] = round(lat_val, 6)
                        meta["gps_lon"] = round(lon_val, 6)
                        meta["has_gps"] = True
                        if iso_match.group(3):
                            meta["gps_alt"] = round(float(iso_match.group(3).decode("ascii")), 1)
                except Exception:
                    pass

            # Decision between Apple creationdate string (contains local timezone) vs mvhd UTC
            if creation_date_str:
                dt = parse_datetime_str(creation_date_str)
                if dt:
                    meta["apple_creationdate"] = creation_date_str
                    return (dt, None, {k: v for k, v in meta.items() if v is not None})

            if mvhd_timestamp is not None:
                dt = datetime.fromtimestamp(mvhd_timestamp, tz=timezone.utc)
                # Keep local/naive representation or UTC
                meta["mvhd_utc"] = dt.isoformat()
                return (dt.replace(tzinfo=None), None, {k: v for k, v in meta.items() if v is not None})

            return None
    except Exception:
        return None


def extract_with_mdls(file_path: Path) -> Optional[Tuple[datetime, Optional[str], Dict[str, Any]]]:
    """Extract creation date via macOS Spotlight mdls command."""
    if sys.platform != "darwin":
        return None

    mdls_bin = shutil.which("mdls") or "/usr/bin/mdls"
    if not os.path.exists(mdls_bin):
        return None

    try:
        res = subprocess.run(
            [mdls_bin, "-name", "kMDItemContentCreationDate", "-raw", str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
        )
        if res.returncode == 0 and res.stdout and res.stdout.strip() != "(null)":
            dt = parse_datetime_str(res.stdout.strip())
            if dt:
                return (dt, None, {"mdls_raw": res.stdout.strip()})
    except Exception:
        pass
    return None


def extract_from_filename(file_path: Path) -> Optional[Tuple[datetime, Optional[str], Dict[str, Any]]]:
    """Extract timestamp from filename regex patterns."""
    stem = file_path.stem
    for pat in FILENAME_PATTERNS:
        match = pat.search(stem)
        if match:
            groups = match.groups()
            try:
                if len(groups) >= 6 and groups[3] is not None:
                    # Full date + time
                    year, month, day, hour, minute, second = map(int, groups[:6])
                    subsec = groups[6] if len(groups) > 6 and groups[6] else None
                    if 1990 <= year <= 2050 and 1 <= month <= 12 and 1 <= day <= 31:
                        dt = datetime(year, month, day, hour, minute, second)
                        return (dt, subsec, {"regex_pattern": pat.pattern})
                elif len(groups) >= 3:
                    # Date only (set time to 12:00:00)
                    year, month, day = map(int, groups[:3])
                    if 1990 <= year <= 2050 and 1 <= month <= 12 and 1 <= day <= 31:
                        dt = datetime(year, month, day, 12, 0, 0)
                        return (dt, None, {"regex_pattern": pat.pattern, "date_only": True})
            except (ValueError, TypeError):
                continue
    return None


def extract_fs_fallback(file_path: Path) -> Tuple[datetime, Optional[str], Dict[str, Any]]:
    """Fallback to filesystem modification timestamp."""
    try:
        stat = file_path.stat()
        # Prefer st_birthtime on macOS if available and reasonable
        ts = getattr(stat, "st_birthtime", stat.st_mtime)
        if ts <= 0:
            ts = stat.st_mtime
        dt = datetime.fromtimestamp(ts)
        return (dt, None, {"fs_mtime": stat.st_mtime})
    except Exception:
        return (datetime.now(), None, {"fs_fallback": True})


def extract_media_item(file_path: Path) -> MediaItem:
    """Multi-tier extractor that determines the original capture date and returns a MediaItem.

    Tier 1: exiftool (if present)
    Tier 2: Pure-Python (Pillow EXIF for images, ISOBMFF atom parser for videos)
    Tier 3: macOS mdls
    Tier 4: Filename regex pattern
    Tier 5: Filesystem timestamp fallback
    """
    path = Path(file_path).resolve()
    ext = path.suffix.lower()
    name = path.name

    if ext in VIDEO_EXTENSIONS:
        media_type = "video"
    elif ext in IMAGE_EXTENSIONS:
        media_type = "image"
    else:
        media_type = "unknown"

    # Tier 1: exiftool (universal, if installed)
    res = extract_with_exiftool(path)
    if res:
        dt, subsec, meta = res
        return MediaItem(
            original_path=path,
            original_name=name,
            extension=ext,
            media_type=media_type,
            timestamp=dt,
            timestamp_source="exif",
            subsecond=subsec,
            metadata=meta,
        )

    # Tier 2: Pure Python / Pillow
    if media_type == "image":
        res = extract_image_exif(path)
        if res:
            dt, subsec, meta = res
            return MediaItem(
                original_path=path,
                original_name=name,
                extension=ext,
                media_type="image",
                timestamp=dt,
                timestamp_source="exif",
                subsecond=subsec,
                metadata=meta,
            )
    elif media_type == "video":
        res = parse_isobmff_quicktime_atoms(path)
        if res:
            dt, subsec, meta = res
            return MediaItem(
                original_path=path,
                original_name=name,
                extension=ext,
                media_type="video",
                timestamp=dt,
                timestamp_source="quicktime_atom",
                subsecond=subsec,
                metadata=meta,
            )

    # Tier 3: Filename regex (when embedded metadata is missing, filename retains camera capture time)
    res = extract_from_filename(path)
    if res:
        dt, subsec, meta = res
        return MediaItem(
            original_path=path,
            original_name=name,
            extension=ext,
            media_type=media_type,
            timestamp=dt,
            timestamp_source="filename_regex",
            subsecond=subsec,
            metadata=meta,
        )

    # Tier 4: macOS mdls
    res = extract_with_mdls(path)
    if res:
        dt, subsec, meta = res
        return MediaItem(
            original_path=path,
            original_name=name,
            extension=ext,
            media_type=media_type,
            timestamp=dt,
            timestamp_source="mdls",
            subsecond=subsec,
            metadata=meta,
        )

    # Tier 5: Filesystem fallback
    dt, subsec, meta = extract_fs_fallback(path)
    return MediaItem(
        original_path=path,
        original_name=name,
        extension=ext,
        media_type=media_type,
        timestamp=dt,
        timestamp_source="fs_fallback",
        subsecond=subsec,
        metadata=meta,
    )
