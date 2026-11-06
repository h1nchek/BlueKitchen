"""Safe, bounded extraction of Android ROM ZIP archives."""

from __future__ import annotations

import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from bluekitchen.inspector import _safe_member_name

DEFAULT_MAX_TOTAL_SIZE = 2 * 1024 * 1024 * 1024
DEFAULT_MAX_FILE_SIZE = 512 * 1024 * 1024
DEFAULT_MAX_ENTRIES = 10_000


class ExtractionError(Exception):
    """Raised when a ROM archive cannot be extracted safely."""


def extract_zip(
    archive_path: str | Path,
    destination: str | Path,
    *,
    max_total_size: int = DEFAULT_MAX_TOTAL_SIZE,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> dict[str, Any]:
    """Extract a ZIP to a new directory with path, size and file-count limits.

    The destination must not exist. Unsafe paths, symlinks, encrypted entries,
    duplicate paths and oversized archives are rejected before extraction.
    """
    source = Path(archive_path)
    target = Path(destination)

    if not source.is_file():
        raise ExtractionError(f"Archive does not exist: {source}")
    if target.exists():
        raise ExtractionError(f"Destination already exists: {target}")
    if min(max_total_size, max_file_size, max_entries) <= 0:
        raise ExtractionError("Extraction limits must be positive")

    try:
        if not zipfile.is_zipfile(source):
            raise ExtractionError(f"Not a valid ZIP archive: {source}")
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            if len(members) > max_entries:
                raise ExtractionError(
                    f"Archive has {len(members)} entries; limit is {max_entries}"
                )

            total_size = 0
            seen: set[str] = set()
            for member in members:
                name = member.filename
                normalized = name.replace("\\", "/")
                path = PurePosixPath(normalized)
                if not _safe_member_name(name) or not normalized:
                    raise ExtractionError(f"Unsafe archive path: {name!r}")
                if path.parts and ":" in path.parts[0]:
                    raise ExtractionError(f"Drive-qualified archive path: {name!r}")
                if normalized in seen:
                    raise ExtractionError(f"Duplicate archive path: {name!r}")
                seen.add(normalized)

                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ExtractionError(f"Symbolic links are not allowed: {name!r}")
                if member.flag_bits & 0x1:
                    raise ExtractionError(f"Encrypted ZIP entries are not supported: {name!r}")
                if member.file_size < 0 or member.file_size > max_file_size:
                    raise ExtractionError(f"Entry exceeds size limit: {name!r}")
                total_size += member.file_size
                if total_size > max_total_size:
                    raise ExtractionError("Archive exceeds the total uncompressed size limit")

            target.mkdir(parents=True, exist_ok=False)
            extracted_files = 0
            try:
                root = target.resolve()
                for member in members:
                    relative = PurePosixPath(member.filename.replace("\\", "/"))
                    output = target.joinpath(*relative.parts)
                    resolved_parent = output.parent.resolve()
                    if resolved_parent != root and root not in resolved_parent.parents:
                        raise ExtractionError(f"Archive path escapes destination: {member.filename!r}")
                    if member.is_dir():
                        output.mkdir(parents=True, exist_ok=True)
                        continue
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member, "r") as input_stream, output.open("xb") as output_stream:
                        copied = 0
                        while True:
                            chunk = input_stream.read(1024 * 1024)
                            if not chunk:
                                break
                            copied += len(chunk)
                            if copied > max_file_size:
                                raise ExtractionError(
                                    f"Entry expanded beyond the size limit: {member.filename!r}"
                                )
                            output_stream.write(chunk)
                        if copied != member.file_size:
                            raise ExtractionError(
                                f"Entry size mismatch while extracting: {member.filename!r}"
                            )
                    extracted_files += 1
            except Exception:
                shutil.rmtree(target, ignore_errors=True)
                raise

        return {
            "archive": source.name,
            "destination": str(target),
            "entries": len(members),
            "files_extracted": extracted_files,
            "uncompressed_bytes": total_size,
            "source_preserved": True,
        }
    except ExtractionError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError) as exc:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        raise ExtractionError(f"Could not extract ZIP archive: {exc}") from exc
