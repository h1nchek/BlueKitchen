"""Extract a logical partition from a validated raw Android super image."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from bluekitchen.dynamic_partitions import SuperImageError, inspect_super_image

SECTOR_SIZE = 512
COPY_CHUNK_SIZE = 1024 * 1024


class SuperExtractError(Exception):
    """Raised when a logical partition cannot be extracted safely."""


def extract_super_partition(
    image_path: str | Path,
    partition_name: str,
    destination: str | Path,
    *,
    slot: int = 0,
) -> dict[str, Any]:
    """Write one logical partition to a new raw image file.

    The input must be a raw super image. Linear extents are copied from their
    physical sectors; zero extents are emitted as zero-filled data.
    """
    source = Path(image_path)
    target = Path(destination)
    if not source.is_file():
        raise SuperExtractError(f"Super image does not exist: {source}")
    if source.resolve() == target.resolve():
        raise SuperExtractError("Source and destination must be different files")
    if target.exists():
        raise SuperExtractError(f"Destination already exists: {target}")
    if not partition_name:
        raise SuperExtractError("Partition name must not be empty")

    try:
        metadata = inspect_super_image(source, slot=slot)
    except SuperImageError as exc:
        raise SuperExtractError(str(exc)) from exc

    partition = next(
        (item for item in metadata["partitions"] if item["name"] == partition_name),
        None,
    )
    if partition is None:
        available = ", ".join(item["name"] for item in metadata["partitions"])
        raise SuperExtractError(
            f"Partition {partition_name!r} was not found. Available: {available or 'none'}"
        )

    devices = {item["name"]: item for item in metadata["block_devices"]}
    extents = partition["extents"]
    expected_size = partition["size_bytes"]
    actual_size = sum(item["sectors"] * SECTOR_SIZE for item in extents)
    if actual_size != expected_size:
        raise SuperExtractError("Partition extent size does not match metadata size")

    file_size = source.stat().st_size
    for extent in extents:
        if extent["target_type"] == "LINEAR":
            device_name = extent["block_device"]
            if device_name not in devices:
                raise SuperExtractError(f"Unknown block device in extent: {device_name!r}")
            device = devices[device_name]
            offset = extent["physical_sector"] * SECTOR_SIZE
            size = extent["sectors"] * SECTOR_SIZE
            if offset + size > min(file_size, device["size"]):
                raise SuperExtractError("Partition extent exceeds the available super image")
        elif extent["target_type"] != "ZERO":
            raise SuperExtractError(
                f"Unsupported extent type: {extent['target_type']!r}"
            )

    created = False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as input_stream, target.open("xb") as output_stream:
            created = True
            for extent in extents:
                remaining = extent["sectors"] * SECTOR_SIZE
                if extent["target_type"] == "ZERO":
                    zeroes = bytes(min(COPY_CHUNK_SIZE, remaining))
                    while remaining:
                        piece = zeroes[: min(len(zeroes), remaining)]
                        output_stream.write(piece)
                        remaining -= len(piece)
                    continue

                input_stream.seek(extent["physical_sector"] * SECTOR_SIZE)
                while remaining:
                    piece = input_stream.read(min(COPY_CHUNK_SIZE, remaining))
                    if not piece:
                        raise SuperExtractError("Unexpected end of super image during extraction")
                    output_stream.write(piece)
                    remaining -= len(piece)

            output_stream.flush()
            if output_stream.tell() != expected_size:
                raise SuperExtractError("Extracted partition size does not match metadata")

        return {
            "source": source.name,
            "partition": partition_name,
            "output": str(target),
            "size_bytes": expected_size,
            "extent_count": len(extents),
            "slot": slot,
            "source_preserved": True,
        }
    except Exception as exc:
        if created or target.exists():
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(exc, SuperExtractError):
            raise
        raise SuperExtractError(f"Could not extract super partition: {exc}") from exc
