"""Read-only inspection of Android ROM OTA ZIP packages."""

from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from bluekitchen.payload import PayloadError, inspect_payload_stream

METADATA_PATH = "META-INF/com/android/metadata"
PAYLOAD_PATH = "payload.bin"
MAX_METADATA_SIZE = 1024 * 1024


class RomInspectionError(Exception):
    """Raised when a ROM archive cannot be inspected safely."""


def _is_safe_member(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return not path.is_absolute() and ".." not in path.parts


def _read_ota_metadata(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> dict[str, str]:
    if info.file_size > MAX_METADATA_SIZE:
        raise RomInspectionError(
            f"OTA metadata is too large ({info.file_size} bytes; limit is {MAX_METADATA_SIZE})"
        )
    with archive.open(info) as stream:
        raw = stream.read(MAX_METADATA_SIZE + 1)
    if len(raw) > MAX_METADATA_SIZE:
        raise RomInspectionError("OTA metadata exceeds the configured size limit")
    metadata: dict[str, str] = {}
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def inspect_rom_archive(
    path: str | Path, expected_device: str | None = None
) -> dict[str, Any]:
    """Inspect a ROM ZIP and parse an embedded payload manifest without extracting it."""
    archive_path = Path(path)
    if not archive_path.is_file():
        raise RomInspectionError(f"File does not exist: {archive_path}")
    if not zipfile.is_zipfile(archive_path):
        raise RomInspectionError(f"Not a valid ROM ZIP archive: {archive_path}")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            by_name = {member.filename: member for member in members}
            for critical_name in (PAYLOAD_PATH, METADATA_PATH):
                if sum(member.filename == critical_name for member in members) > 1:
                    raise RomInspectionError(
                        f"Archive contains duplicate critical entry: {critical_name}"
                    )
            unsafe_paths = [
                member.filename for member in members if not _is_safe_member(member.filename)
            ]
            metadata: dict[str, str] = {}
            metadata_info = by_name.get(METADATA_PATH)
            if metadata_info is not None:
                metadata = _read_ota_metadata(archive, metadata_info)

            payload: dict[str, Any] | None = None
            payload_info = by_name.get(PAYLOAD_PATH)
            if payload_info is not None:
                try:
                    with archive.open(payload_info) as stream:
                        payload = inspect_payload_stream(
                            stream, payload_info.file_size, PAYLOAD_PATH
                        )
                except (PayloadError, OSError, zipfile.BadZipFile) as exc:
                    raise RomInspectionError(f"Could not inspect embedded payload: {exc}") from exc

            pre_devices = [
                item.strip()
                for item in metadata.get("pre-device", "").split(",")
                if item.strip()
            ]
            expected = expected_device.strip() if expected_device else None
            if expected and pre_devices:
                device_match: bool | None = expected.casefold() in {
                    item.casefold() for item in pre_devices
                }
            else:
                device_match = None

            markers = []
            if payload_info is not None:
                markers.append("A/B OTA payload")
            if "META-INF/com/google/android/update-binary" in by_name:
                markers.append("Recovery installer")
            if "META-INF/com/google/android/updater-script" in by_name:
                markers.append("Edify updater script")
            for image_name, label in (
                ("boot.img", "Boot image"),
                ("vendor_boot.img", "Vendor boot image"),
                ("super.img", "Dynamic partition image"),
                ("dtbo.img", "Device tree overlay image"),
            ):
                if image_name in by_name:
                    markers.append(label)

            return {
                "file": archive_path.name,
                "format": "android_rom_zip",
                "entries": len(members),
                "files": sum(not member.is_dir() for member in members),
                "uncompressed_bytes": sum(member.file_size for member in members),
                "compressed_bytes": sum(member.compress_size for member in members),
                "unsafe_paths": unsafe_paths,
                "markers": markers,
                "ota_metadata": metadata,
                "pre_devices": pre_devices,
                "expected_device": expected,
                "device_match": device_match,
                "payload": payload,
                "payload_partitions": (
                    [item["name"] for item in payload["partitions"]]
                    if payload is not None
                    else []
                ),
                "inspection_only": True,
                "notes": [
                    "Embedded payload metadata was read without extracting partition data.",
                    "ZIP member CRCs and device boot compatibility were not verified.",
                    "A matching pre-device value is metadata evidence, not proof the ROM will boot.",
                ],
            }
    except RomInspectionError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise RomInspectionError(f"Could not read ROM ZIP: {exc}") from exc
