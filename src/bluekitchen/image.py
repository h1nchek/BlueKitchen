"""Read-only parser for Android sparse image containers."""

from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO


SPARSE_MAGIC = 0xED26FF3A
SPARSE_HEADER = struct.Struct("<I4H4I")
CHUNK_HEADER = struct.Struct("<2H2I")
MAX_CHUNKS = 1_000_000
CHUNK_TYPES = {
    0xCAC1: "RAW",
    0xCAC2: "FILL",
    0xCAC3: "DONT_CARE",
    0xCAC4: "CRC32",
}


class ImageError(Exception):
    """Raised when an image cannot be inspected safely."""


def _read_exact(stream: BinaryIO, size: int, description: str) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise ImageError(f"Truncated {description}")
    return data


def _parse_sparse(stream: BinaryIO, file_size: int, path: Path) -> dict[str, Any]:
    stream.seek(0)
    header_bytes = _read_exact(stream, SPARSE_HEADER.size, "sparse image header")
    (
        magic,
        major,
        minor,
        file_header_size,
        chunk_header_size,
        block_size,
        total_blocks,
        total_chunks,
        checksum,
    ) = SPARSE_HEADER.unpack(header_bytes)

    if magic != SPARSE_MAGIC:
        raise ImageError("Invalid sparse image magic")
    if major != 1:
        raise ImageError(f"Unsupported Android sparse major version: {major}")
    if file_header_size < SPARSE_HEADER.size:
        raise ImageError("Sparse file header size is smaller than the v1 header")
    if chunk_header_size < CHUNK_HEADER.size:
        raise ImageError("Sparse chunk header size is smaller than the v1 header")
    if block_size == 0 or block_size % 4:
        raise ImageError("Invalid sparse block size; expected a non-zero multiple of 4")
    if total_chunks > MAX_CHUNKS:
        raise ImageError(f"Sparse image declares too many chunks ({total_chunks})")

    if file_header_size > file_size:
        raise ImageError("Sparse file header extends beyond the end of the file")
    stream.seek(file_header_size)

    counts: Counter[str] = Counter()
    output_blocks = 0
    chunk_preview: list[dict[str, Any]] = []

    for index in range(total_chunks):
        chunk_start = stream.tell()
        raw_header = _read_exact(stream, chunk_header_size, f"chunk {index} header")
        chunk_type, _reserved, chunk_blocks, total_size = CHUNK_HEADER.unpack(
            raw_header[: CHUNK_HEADER.size]
        )
        name = CHUNK_TYPES.get(chunk_type)
        if name is None:
            raise ImageError(f"Unsupported sparse chunk type 0x{chunk_type:04x} at chunk {index}")

        if total_size < chunk_header_size:
            raise ImageError(f"Invalid total size in sparse chunk {index}")

        if name == "RAW":
            expected_data = chunk_blocks * block_size
            if total_size != chunk_header_size + expected_data:
                raise ImageError(f"Invalid RAW chunk size at chunk {index}")
            output_blocks += chunk_blocks
        elif name == "FILL":
            if total_size != chunk_header_size + 4:
                raise ImageError(f"Invalid FILL chunk size at chunk {index}")
            output_blocks += chunk_blocks
        elif name == "DONT_CARE":
            if total_size != chunk_header_size:
                raise ImageError(f"Invalid DONT_CARE chunk size at chunk {index}")
            output_blocks += chunk_blocks
        else:  # CRC32
            if chunk_blocks != 0 or total_size != chunk_header_size + 4:
                raise ImageError(f"Invalid CRC32 chunk size at chunk {index}")

        data_size = total_size - chunk_header_size
        stream.seek(data_size, 1)
        if stream.tell() > file_size:
            raise ImageError(f"Sparse chunk {index} extends beyond the end of the file")

        counts[name] += 1
        if len(chunk_preview) < 100:
            chunk_preview.append({
                "index": index,
                "type": name,
                "blocks": chunk_blocks,
                "file_offset": chunk_start,
                "total_size": total_size,
            })

    if output_blocks != total_blocks:
        raise ImageError(
            f"Sparse block count mismatch: chunks describe {output_blocks}, "
            f"header declares {total_blocks}"
        )

    parsed_size = stream.tell()
    return {
        "file": path.name,
        "format": "android_sparse_image",
        "is_sparse": True,
        "file_size": file_size,
        "major_version": major,
        "minor_version": minor,
        "file_header_size": file_header_size,
        "chunk_header_size": chunk_header_size,
        "block_size": block_size,
        "total_blocks": total_blocks,
        "expanded_size": total_blocks * block_size,
        "total_chunks": total_chunks,
        "image_checksum": f"0x{checksum:08x}",
        "chunk_counts": dict(sorted(counts.items())),
        "chunks_preview": chunk_preview,
        "preview_truncated": total_chunks > len(chunk_preview),
        "parsed_bytes": parsed_size,
        "trailing_bytes": file_size - parsed_size,
        "inspection_only": True,
    }


def inspect_image(path: str | Path) -> dict[str, Any]:
    """Identify a raw file or inspect an Android sparse image without writing data."""
    image_path = Path(path)
    if not image_path.is_file():
        raise ImageError(f"File does not exist: {image_path}")

    try:
        file_size = image_path.stat().st_size
        with image_path.open("rb") as stream:
            magic = stream.read(4)
            if len(magic) < 4:
                return {
                    "file": image_path.name,
                    "format": "raw_or_unknown_image",
                    "is_sparse": False,
                    "file_size": file_size,
                    "inspection_only": True,
                }
            if magic != struct.pack("<I", SPARSE_MAGIC):
                return {
                    "file": image_path.name,
                    "format": "raw_or_unknown_image",
                    "is_sparse": False,
                    "file_size": file_size,
                    "inspection_only": True,
                    "note": "No Android sparse magic detected; filesystem type was not determined.",
                }
            return _parse_sparse(stream, file_size, image_path)
    except ImageError:
        raise
    except OSError as exc:
        raise ImageError(f"Could not read image: {exc}") from exc



def expand_sparse_image(source: str | Path, destination: str | Path) -> dict[str, Any]:
    """Expand a validated Android sparse image into a new raw image file.

    The source is never modified. Existing destination files are never overwritten.
    DONT_CARE ranges are represented as zero-filled sparse-file holes where supported.
    """
    source_path = Path(source)
    destination_path = Path(destination)
    if not source_path.is_file():
        raise ImageError(f"File does not exist: {source_path}")
    if source_path.resolve() == destination_path.resolve():
        raise ImageError("Source and destination must be different files")
    if destination_path.exists():
        raise ImageError(f"Destination already exists: {destination_path}")

    # Validate the complete chunk table and all declared boundaries before creating output.
    summary = inspect_image(source_path)
    if not summary["is_sparse"]:
        raise ImageError("Input is not an Android sparse image")

    created_output = False
    try:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with source_path.open("rb") as input_stream, destination_path.open("xb") as output_stream:
            created_output = True
            input_stream.seek(summary["file_header_size"])
            for index in range(summary["total_chunks"]):
                chunk_header = _read_exact(
                    input_stream, summary["chunk_header_size"], f"chunk {index} header"
                )
                chunk_type, _reserved, chunk_blocks, total_size = CHUNK_HEADER.unpack(
                    chunk_header[: CHUNK_HEADER.size]
                )
                payload_size = total_size - summary["chunk_header_size"]
                output_size = chunk_blocks * summary["block_size"]

                if chunk_type == 0xCAC1:  # RAW
                    remaining = payload_size
                    while remaining:
                        piece = _read_exact(
                            input_stream, min(1024 * 1024, remaining), f"RAW chunk {index}"
                        )
                        output_stream.write(piece)
                        remaining -= len(piece)
                elif chunk_type == 0xCAC2:  # FILL
                    pattern = _read_exact(input_stream, 4, f"FILL chunk {index}")
                    remaining = output_size
                    block = pattern * (min(1024 * 1024, max(4, output_size)) // 4)
                    while remaining:
                        piece = block[: min(len(block), remaining)]
                        output_stream.write(piece)
                        remaining -= len(piece)
                elif chunk_type == 0xCAC3:  # DONT_CARE
                    output_stream.seek(output_size, 1)
                elif chunk_type == 0xCAC4:  # CRC32
                    _read_exact(input_stream, payload_size, f"CRC32 chunk {index}")
                else:
                    raise ImageError(f"Unsupported sparse chunk type 0x{chunk_type:04x}")

            output_stream.truncate(summary["expanded_size"])
            output_stream.flush()
        return {
            "source": source_path.name,
            "output": str(destination_path),
            "expanded_size": summary["expanded_size"],
            "chunks_processed": summary["total_chunks"],
            "source_preserved": True,
        }
    except (OSError, ImageError) as exc:
        if created_output:
            try:
                destination_path.unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(exc, ImageError):
            raise
        raise ImageError(f"Could not expand sparse image: {exc}") from exc
