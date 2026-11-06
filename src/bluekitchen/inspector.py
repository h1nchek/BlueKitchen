"""Read-only inspection helpers for Android ROM archives."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any
import zipfile


ANDROID_MARKERS = {
    "payload.bin": "A/B OTA payload",
    "META-INF/com/google/android/update-binary": "Recovery installer",
    "META-INF/com/google/android/updater-script": "Edify updater script",
    "boot.img": "Boot image",
    "vendor_boot.img": "Vendor boot image",
    "super.img": "Dynamic partition image",
    "dtbo.img": "Device tree overlay image",
}


class InspectionError(Exception):
    """Raised when an archive cannot be inspected safely."""


def _safe_member_name(name: str) -> bool:
    """Reject absolute and traversal paths in archive member names."""
    path = PurePosixPath(name.replace("\\", "/"))
    return not path.is_absolute() and ".." not in path.parts


def inspect_zip(path: str | Path) -> dict[str, Any]:
    """Return archive metadata without extracting or changing any files."""
    archive_path = Path(path)
    if not archive_path.is_file():
        raise InspectionError(f"File does not exist: {archive_path}")
    if not zipfile.is_zipfile(archive_path):
        raise InspectionError(f"Not a valid ZIP archive: {archive_path}")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            unsafe = [item.filename for item in members if not _safe_member_name(item.filename)]
            markers = sorted({
                ANDROID_MARKERS[item.filename]
                for item in members
                if item.filename in ANDROID_MARKERS
            })
            return {
                "file": archive_path.name,
                "format": "zip",
                "entries": len(members),
                "files": sum(not item.is_dir() for item in members),
                "directories": sum(item.is_dir() for item in members),
                "uncompressed_bytes": sum(item.file_size for item in members),
                "compressed_bytes": sum(item.compress_size for item in members),
                "android_markers": markers,
                "unsafe_paths": unsafe,
                "entries_preview": [
                    {
                        "name": item.filename,
                        "size": item.file_size,
                        "compressed_size": item.compress_size,
                        "is_directory": item.is_dir(),
                    }
                    for item in members[:200]
                ],
                "preview_truncated": len(members) > 200,
            }
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise InspectionError(f"Could not read ZIP archive: {exc}") from exc
