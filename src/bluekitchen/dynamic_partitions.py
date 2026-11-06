"""Read-only parser for Android liblp dynamic-partition metadata in raw super images."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any, BinaryIO

GEOMETRY_MAGIC = 0x616C4467
METADATA_MAGIC = 0x414C5030
GEOMETRY_OFFSET = 4096
GEOMETRY_BACKUP_OFFSET = 8192
GEOMETRY_SIZE = 4096
PARTITION_RESERVED_BYTES = 4096
SECTOR_SIZE = 512
GEOMETRY_STRUCT = struct.Struct("<II32sIII")
HEADER_V1_0_SIZE = 128
HEADER_V1_2_SIZE = 256
PARTITION_STRUCT = struct.Struct("<36s4I")
EXTENT_STRUCT = struct.Struct("<QIQI")
GROUP_STRUCT = struct.Struct("<36sIQ")
BLOCK_DEVICE_STRUCT = struct.Struct("<QIIQ36sI")
MAX_METADATA_SIZE = 64 * 1024 * 1024
MAX_TABLE_ENTRIES = 1_000_000
PARTITION_ATTRS = 0xF
EXTENT_LINEAR = 0
EXTENT_ZERO = 1


class SuperImageError(Exception):
    """Raised when liblp metadata is invalid or unsupported."""


def _read_exact(stream: BinaryIO, size: int, description: str) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise SuperImageError(f"Truncated {description}")
    return data


def _name(value: bytes) -> str:
    return value.split(bytes((0,)), 1)[0].decode("ascii", errors="replace")


def _read_geometry(stream: BinaryIO, offset: int) -> dict[str, int]:
    stream.seek(offset)
    raw = _read_exact(stream, GEOMETRY_STRUCT.size, "liblp geometry")
    magic, struct_size, checksum, metadata_max_size, slot_count, logical_block_size = (
        GEOMETRY_STRUCT.unpack(raw)
    )
    if magic != GEOMETRY_MAGIC:
        raise SuperImageError("Invalid liblp geometry magic")
    if struct_size != GEOMETRY_STRUCT.size:
        raise SuperImageError(f"Unsupported liblp geometry struct size: {struct_size}")
    if metadata_max_size == 0 or metadata_max_size > MAX_METADATA_SIZE:
        raise SuperImageError("Invalid or excessive liblp metadata_max_size")
    if metadata_max_size % SECTOR_SIZE:
        raise SuperImageError("liblp metadata_max_size is not sector-aligned")
    if slot_count == 0 or slot_count > 32:
        raise SuperImageError("Invalid liblp metadata slot count")
    if logical_block_size < SECTOR_SIZE or logical_block_size % SECTOR_SIZE:
        raise SuperImageError("Invalid liblp logical block size")

    normalized = bytearray(raw)
    normalized[8:40] = bytes(32)
    if hashlib.sha256(normalized).digest() != checksum:
        raise SuperImageError("Invalid liblp geometry SHA-256 checksum")
    return {
        "metadata_max_size": metadata_max_size,
        "metadata_slot_count": slot_count,
        "logical_block_size": logical_block_size,
        "geometry_offset": offset,
    }


def _read_metadata(
    stream: BinaryIO, metadata_offset: int, geometry: dict[str, int], file_size: int
) -> dict[str, Any]:
    if metadata_offset + geometry["metadata_max_size"] > file_size:
        raise SuperImageError("liblp metadata slot extends beyond the end of the image")

    stream.seek(metadata_offset)
    fixed = _read_exact(stream, HEADER_V1_0_SIZE, "liblp metadata header")
    (
        magic,
        major,
        minor,
        header_size,
        header_checksum,
        tables_size,
        tables_checksum,
    ) = struct.unpack("<IHHI32sI32s", fixed[:80])
    if magic != METADATA_MAGIC:
        raise SuperImageError("Invalid liblp metadata magic")
    if major != 10 or minor > 2:
        raise SuperImageError(f"Unsupported liblp metadata version {major}.{minor}")

    expected_header_size = HEADER_V1_2_SIZE if minor >= 2 else HEADER_V1_0_SIZE
    if header_size != expected_header_size:
        raise SuperImageError("Invalid liblp metadata header size")
    if tables_size > geometry["metadata_max_size"] or tables_size > MAX_METADATA_SIZE:
        raise SuperImageError("Invalid or excessive liblp tables_size")

    descriptors = [
        struct.unpack_from("<III", fixed, offset)
        for offset in (80, 92, 104, 116)
    ]
    if header_size > HEADER_V1_0_SIZE:
        extra = _read_exact(stream, header_size - HEADER_V1_0_SIZE, "expanded liblp header")
        header = fixed + extra
    else:
        header = fixed

    normalized_header = bytearray(header)
    normalized_header[12:44] = bytes(32)
    if hashlib.sha256(normalized_header).digest() != header_checksum:
        raise SuperImageError("Invalid liblp metadata header SHA-256 checksum")

    table_names = ("partitions", "extents", "groups", "block_devices")
    expected_sizes = (
        PARTITION_STRUCT.size,
        EXTENT_STRUCT.size,
        GROUP_STRUCT.size,
        BLOCK_DEVICE_STRUCT.size,
    )
    for name, (offset, count, entry_size), expected_size in zip(
        table_names, descriptors, expected_sizes, strict=True
    ):
        if count > MAX_TABLE_ENTRIES:
            raise SuperImageError(f"Too many liblp {name} entries")
        if count and entry_size != expected_size:
            raise SuperImageError(f"Unexpected liblp {name} entry size: {entry_size}")
        if offset > tables_size or count * entry_size > tables_size - offset:
            raise SuperImageError(f"liblp {name} table exceeds table data bounds")

    tables = _read_exact(stream, tables_size, "liblp tables")
    if hashlib.sha256(tables).digest() != tables_checksum:
        raise SuperImageError("Invalid liblp tables SHA-256 checksum")

    parsed_tables: dict[str, list[Any]] = {}
    for name, (offset, count, entry_size), entry_struct in zip(
        table_names,
        descriptors,
        (PARTITION_STRUCT, EXTENT_STRUCT, GROUP_STRUCT, BLOCK_DEVICE_STRUCT),
        strict=True,
    ):
        parsed_tables[name] = [
            entry_struct.unpack_from(tables, offset + index * entry_size)
            for index in range(count)
        ]

    groups = [
        {
            "name": _name(name),
            "flags": flags,
            "maximum_size": maximum_size,
        }
        for name, flags, maximum_size in parsed_tables["groups"]
    ]
    devices = [
        {
            "first_logical_sector": first_sector,
            "alignment": alignment,
            "alignment_offset": alignment_offset,
            "size": size,
            "name": _name(name),
            "flags": flags,
        }
        for (
            first_sector,
            alignment,
            alignment_offset,
            size,
            name,
            flags,
        ) in parsed_tables["block_devices"]
    ]
    if not devices:
        raise SuperImageError("liblp metadata does not contain a block device")

    extents = []
    for num_sectors, target_type, target_data, target_source in parsed_tables["extents"]:
        if num_sectors == 0:
            raise SuperImageError("liblp extent has zero sectors")
        if target_type == EXTENT_LINEAR:
            if target_source >= len(devices):
                raise SuperImageError("liblp extent references an unknown block device")
            device = devices[target_source]
            if target_data + num_sectors > device["size"] // SECTOR_SIZE:
                raise SuperImageError("liblp linear extent exceeds its block device")
        elif target_type == EXTENT_ZERO:
            if target_data != 0 or target_source != 0:
                raise SuperImageError("Invalid liblp zero extent fields")
        else:
            raise SuperImageError(f"Unsupported liblp extent target type: {target_type}")
        extents.append({
            "sectors": num_sectors,
            "target_type": "LINEAR" if target_type == EXTENT_LINEAR else "ZERO",
            "physical_sector": target_data if target_type == EXTENT_LINEAR else None,
            "block_device": devices[target_source]["name"] if target_type == EXTENT_LINEAR else None,
        })

    partitions = []
    for name, attributes, first_extent, extent_count, group_index in parsed_tables["partitions"]:
        partition_name = _name(name)
        if not partition_name:
            raise SuperImageError("liblp partition has an empty name")
        if attributes & ~PARTITION_ATTRS:
            raise SuperImageError(f"Partition {partition_name} has unknown attributes")
        if extent_count == 0 or first_extent + extent_count > len(extents):
            raise SuperImageError(f"Partition {partition_name} has an invalid extent range")
        if group_index >= len(groups):
            raise SuperImageError(f"Partition {partition_name} references an unknown group")
        partition_extents = extents[first_extent:first_extent + extent_count]
        partitions.append({
            "name": partition_name,
            "attributes": attributes,
            "readonly": bool(attributes & 1),
            "group": groups[group_index]["name"],
            "extent_count": extent_count,
            "size_bytes": sum(item["sectors"] for item in partition_extents) * SECTOR_SIZE,
            "extents": partition_extents,
        })

    metadata_region = PARTITION_RESERVED_BYTES + (
        GEOMETRY_SIZE + geometry["metadata_max_size"] * geometry["metadata_slot_count"]
    ) * 2
    if metadata_region > devices[0]["first_logical_sector"] * SECTOR_SIZE:
        raise SuperImageError("liblp metadata overlaps logical partition contents")

    return {
        "metadata_version": f"{major}.{minor}",
        "header_size": header_size,
        "tables_size": tables_size,
        "flags": struct.unpack_from("<I", header, 128)[0] if header_size >= 256 else 0,
        "partitions": partitions,
        "partition_count": len(partitions),
        "extents": extents,
        "extent_count": len(extents),
        "groups": groups,
        "block_devices": devices,
        "block_device_count": len(devices),
    }


def inspect_super_image(path: str | Path, slot: int = 0) -> dict[str, Any]:
    """Inspect liblp metadata in a raw super image, trying primary then backup metadata."""
    image_path = Path(path)
    if not image_path.is_file():
        raise SuperImageError(f"File does not exist: {image_path}")

    try:
        file_size = image_path.stat().st_size
        with image_path.open("rb") as stream:
            stream.seek(0)
            if stream.read(4) == struct.pack("<I", 0xED26FF3A):
                raise SuperImageError(
                    "Sparse super images are not parsed directly yet; expand the image first"
                )

            geometry_error = None
            geometry = None
            for offset in (GEOMETRY_OFFSET, GEOMETRY_BACKUP_OFFSET):
                try:
                    geometry = _read_geometry(stream, offset)
                    break
                except SuperImageError as exc:
                    geometry_error = exc
            if geometry is None:
                raise SuperImageError(f"Could not read valid liblp geometry: {geometry_error}")
            if slot < 0 or slot >= geometry["metadata_slot_count"]:
                raise SuperImageError(
                    f"Metadata slot {slot} is out of range "
                    f"(available slots: 0..{geometry['metadata_slot_count'] - 1})"
                )

            primary = PARTITION_RESERVED_BYTES + GEOMETRY_SIZE * 2 + (
                geometry["metadata_max_size"] * slot
            )
            backup = PARTITION_RESERVED_BYTES + GEOMETRY_SIZE * 2 + (
                geometry["metadata_max_size"] * geometry["metadata_slot_count"]
            ) + geometry["metadata_max_size"] * slot

            metadata = None
            metadata_source = None
            metadata_error = None
            for offset, source in ((primary, "primary"), (backup, "backup")):
                try:
                    metadata = _read_metadata(stream, offset, geometry, file_size)
                    metadata_source = source
                    break
                except SuperImageError as exc:
                    metadata_error = exc
            if metadata is None:
                raise SuperImageError(f"Could not read valid metadata: {metadata_error}")

        return {
            "file": image_path.name,
            "format": "android_super_image",
            "file_size": file_size,
            "metadata_slot": slot,
            "metadata_source": metadata_source,
            "geometry": geometry,
            "inspection_only": True,
            **metadata,
        }
    except SuperImageError:
        raise
    except OSError as exc:
        raise SuperImageError(f"Could not read super image: {exc}") from exc
