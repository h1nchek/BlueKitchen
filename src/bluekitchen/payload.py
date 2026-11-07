"""Read-only parser for Android A/B OTA payload headers and manifests.

The parser intentionally reads only the payload header and protobuf manifest. It
never applies operations, extracts partition data, or modifies the input file.
"""

from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path
from typing import Any


MAGIC = b"CrAU"
MAX_MANIFEST_SIZE = 64 * 1024 * 1024
MAX_PROTO_FIELDS = 1_000_000
OPERATION_NAMES = {
    0: "REPLACE",
    1: "REPLACE_BZ",
    2: "MOVE",
    3: "BSDIFF",
    4: "SOURCE_COPY",
    5: "SOURCE_BSDIFF",
    6: "ZERO",
    7: "DISCARD",
    8: "REPLACE_XZ",
    9: "PUFFDIFF",
    10: "BROTLI_BSDIFF",
}


class PayloadError(Exception):
    """Raised when a payload file is invalid or cannot be parsed."""


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
    raise PayloadError("Malformed protobuf varint")


def _protobuf_fields(data: bytes):
    """Yield (field_number, wire_type, value) from a protobuf message."""
    offset = 0
    count = 0
    while offset < len(data):
        count += 1
        if count > MAX_PROTO_FIELDS:
            raise PayloadError("Protobuf message contains too many fields")
        tag, offset = _read_varint(data, offset)
        field_number, wire_type = tag >> 3, tag & 7
        if field_number == 0:
            raise PayloadError("Invalid protobuf field number 0")

        if wire_type == 0:
            value, offset = _read_varint(data, offset)
        elif wire_type == 1:
            end = offset + 8
            if end > len(data):
                raise PayloadError("Truncated protobuf fixed64 field")
            value = data[offset:end]
            offset = end
        elif wire_type == 2:
            length, offset = _read_varint(data, offset)
            end = offset + length
            if end > len(data):
                raise PayloadError("Truncated protobuf length-delimited field")
            value = data[offset:end]
            offset = end
        elif wire_type == 5:
            end = offset + 4
            if end > len(data):
                raise PayloadError("Truncated protobuf fixed32 field")
            value = data[offset:end]
            offset = end
        else:
            raise PayloadError(f"Unsupported protobuf wire type: {wire_type}")
        yield field_number, wire_type, value


def _first_varint(fields: list[tuple[int, int, Any]], number: int) -> int | None:
    for field_number, wire_type, value in fields:
        if field_number == number and wire_type == 0:
            return value
    return None


def _parse_manifest(manifest: bytes) -> dict[str, Any]:
    fields = list(_protobuf_fields(manifest))
    block_size = _first_varint(fields, 3)
    minor_version = _first_varint(fields, 12) or 0
    partitions = []
    operation_totals: Counter[str] = Counter()
    unknown_operation_types: Counter[int] = Counter()

    def count_operations(operation_blobs: list[bytes]) -> Counter[str]:
        operations: Counter[str] = Counter()
        for operation_blob in operation_blobs:
            operation_fields = list(_protobuf_fields(operation_blob))
            operation_type = _first_varint(operation_fields, 1)
            if operation_type is None:
                label = "UNKNOWN"
                unknown_operation_types[-1] += 1
            elif operation_type in OPERATION_NAMES:
                label = OPERATION_NAMES[operation_type]
            else:
                label = f"UNKNOWN_{operation_type}"
                unknown_operation_types[operation_type] += 1
            operations[label] += 1
            operation_totals[label] += 1
        return operations

    for field_number, wire_type, partition_blob in fields:
        if field_number != 13 or wire_type != 2:
            continue
        partition_fields = list(_protobuf_fields(partition_blob))
        name = next(
            (
                value.decode("utf-8", errors="replace")
                for number, kind, value in partition_fields
                if number == 1 and kind == 2
            ),
            None,
        )
        operation_blobs = [
            value for number, kind, value in partition_fields if number == 8 and kind == 2
        ]
        operations = count_operations(operation_blobs)
        partitions.append({
            "name": name,
            "operation_count": sum(operations.values()),
            "operations": dict(sorted(operations.items())),
        })

    # Major version 1 uses manifest-level operation lists instead of PartitionUpdate.
    if not partitions:
        for field_number, name in ((1, "rootfs"), (2, "kernel")):
            operation_blobs = [
                value for number, kind, value in fields
                if number == field_number and kind == 2
            ]
            if operation_blobs:
                operations = count_operations(operation_blobs)
                partitions.append({
                    "name": name,
                    "operation_count": sum(operations.values()),
                    "operations": dict(sorted(operations.items())),
                })

    return {
        "block_size": block_size if block_size is not None else 4096,
        "minor_version": minor_version,
        "partition_count": len(partitions),
        "partitions": partitions,
        "operation_count": sum(operation_totals.values()),
        "operations": dict(sorted(operation_totals.items())),
        "unknown_operation_types": {str(key): value for key, value in sorted(unknown_operation_types.items())},
    }


def inspect_payload_stream(
    stream: BinaryIO, file_size: int, file_name: str = "payload.bin"
) -> dict[str, Any]:
    """Inspect a payload from an already-open binary stream without reading partition data."""
    try:
        fixed_header = stream.read(20)
        if len(fixed_header) < 20:
            raise PayloadError("File is too small to contain an Android payload header")
        if fixed_header[:4] != MAGIC:
            raise PayloadError("Invalid payload magic; expected CrAU")

        version, manifest_size = struct.unpack(">QQ", fixed_header[4:20])
        if version < 1:
            raise PayloadError(f"Unsupported payload major version: {version}")
        if manifest_size > MAX_MANIFEST_SIZE:
            raise PayloadError(
                f"Manifest is too large ({manifest_size} bytes; limit is {MAX_MANIFEST_SIZE})"
            )

        metadata_signature_size = 0
        if version >= 2:
            signature_size_bytes = stream.read(4)
            if len(signature_size_bytes) != 4:
                raise PayloadError("Truncated payload header (missing metadata signature size)")
            metadata_signature_size = struct.unpack(">I", signature_size_bytes)[0]

        header_size = 24 if version >= 2 else 20
        manifest_offset = header_size
        manifest_end = manifest_offset + manifest_size
        data_offset = manifest_end + metadata_signature_size
        if data_offset > file_size:
            raise PayloadError("Header declares metadata beyond the end of the file")

        manifest = stream.read(manifest_size)
        if len(manifest) != manifest_size:
            raise PayloadError("Truncated payload manifest")

        summary = _parse_manifest(manifest)
        return {
            "file": file_name,
            "format": "android_ota_payload",
            "magic": MAGIC.decode("ascii"),
            "major_version": version,
            "file_size": file_size,
            "header_size": header_size,
            "manifest_offset": manifest_offset,
            "manifest_size": manifest_size,
            "metadata_signature_size": metadata_signature_size,
            "data_offset": data_offset,
            **summary,
            "inspection_only": True,
        }
    except PayloadError:
        raise
    except OSError as exc:
        raise PayloadError(f"Could not read payload: {exc}") from exc


def inspect_payload(path: str | Path) -> dict[str, Any]:
    """Inspect an Android OTA payload file without applying its partition operations."""
    payload_path = Path(path)
    if not payload_path.is_file():
        raise PayloadError(f"File does not exist: {payload_path}")
    try:
        with payload_path.open("rb") as stream:
            return inspect_payload_stream(stream, payload_path.stat().st_size, payload_path.name)
    except PayloadError:
        raise
    except OSError as exc:
        raise PayloadError(f"Could not read payload: {exc}") from exc
