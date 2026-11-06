"""Create reproducible ROM ZIP packages from a prepared directory."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

DEFAULT_MAX_FILES = 10_000
DEFAULT_MAX_TOTAL_SIZE = 4 * 1024 * 1024 * 1024


class PackingError(Exception):
    """Raised when a directory cannot be packed safely."""


def pack_zip(
    source_directory: str | Path,
    destination: str | Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_total_size: int = DEFAULT_MAX_TOTAL_SIZE,
) -> dict[str, int | str | bool]:
    """Pack a directory into a new ZIP archive without following symlinks."""
    source = Path(source_directory)
    target = Path(destination)

    if not source.is_dir() or source.is_symlink():
        raise PackingError(f"Source must be an existing, non-symlink directory: {source}")
    if min(max_files, max_total_size) <= 0:
        raise PackingError("Packing limits must be positive")

    source_root = source.resolve()
    target_resolved = target.resolve()
    if target_resolved == source_root or source_root in target_resolved.parents:
        raise PackingError("Output archive must be outside the source directory")
    if target.exists():
        raise PackingError(f"Destination already exists: {target}")

    try:
        files: list[Path] = []
        total_size = 0
        names: set[str] = set()
        for current, directories, filenames in os.walk(source_root, followlinks=False):
            current_path = Path(current)
            for directory in list(directories):
                child = current_path / directory
                if child.is_symlink():
                    raise PackingError(f"Symbolic links are not allowed: {child}")
            for filename in filenames:
                file_path = current_path / filename
                if file_path.is_symlink():
                    raise PackingError(f"Symbolic links are not allowed: {file_path}")
                if not file_path.is_file():
                    continue
                relative = file_path.relative_to(source_root).as_posix()
                if relative.startswith("/") or ".." in Path(relative).parts:
                    raise PackingError(f"Unsafe relative path: {relative!r}")
                normalized = relative.casefold()
                if normalized in names:
                    raise PackingError(f"Duplicate archive path: {relative!r}")
                names.add(normalized)
                total_size += file_path.stat().st_size
                if len(files) >= max_files:
                    raise PackingError(f"Directory contains more than {max_files} files")
                if total_size > max_total_size:
                    raise PackingError("Directory exceeds the total uncompressed size limit")
                files.append(file_path)

        target.parent.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            with target.open("xb") as output_stream:
                created = True
                with zipfile.ZipFile(
                    output_stream, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
                ) as archive:
                    for file_path in sorted(files):
                        archive.write(file_path, file_path.relative_to(source_root).as_posix())
        except Exception:
            if created or target.exists():
                target.unlink(missing_ok=True)
            raise

        return {
            "source_directory": str(source_root),
            "archive": str(target),
            "files_packed": len(files),
            "uncompressed_bytes": total_size,
            "source_preserved": True,
        }
    except PackingError:
        raise
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise PackingError(f"Could not create ROM ZIP: {exc}") from exc
