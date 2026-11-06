import hashlib
import struct

import pytest

from bluekitchen.dynamic_partitions import SuperImageError, inspect_super_image


def _make_super():
    metadata_max_size = 4096
    slot_count = 1
    logical_block_size = 4096

    partition = struct.pack("<36s4I", b"system", 1, 0, 1, 0)
    extent = struct.pack("<QIQI", 16, 0, 64, 0)
    group = struct.pack("<36sIQ", b"default", 0, 0)
    device = struct.pack("<QIIQ36sI", 64, 4096, 0, 1024 * 1024, b"super", 0)
    tables = partition + extent + group + device

    descriptors = (
        struct.pack("<III", 0, 1, 52)
        + struct.pack("<III", 52, 1, 24)
        + struct.pack("<III", 76, 1, 48)
        + struct.pack("<III", 124, 1, 64)
    )
    header = bytearray(256)
    struct.pack_into("<IHHI", header, 0, 0x414C5030, 10, 2, 256)
    header[48:80] = hashlib.sha256(tables).digest()
    struct.pack_into("<I", header, 44, len(tables))
    header[80:128] = descriptors
    struct.pack_into("<I", header, 128, 0)
    header[12:44] = hashlib.sha256(header).digest()

    geometry = bytearray(struct.pack(
        "<II32sIII", 0x616C4467, 52, bytes(32),
        metadata_max_size, slot_count, logical_block_size,
    ))
    geometry[8:40] = hashlib.sha256(geometry).digest()

    image = bytearray(1024 * 1024)
    image[4096:4096 + 52] = geometry
    image[8192:8192 + 52] = geometry
    metadata_offset = 4096 + 8192
    image[metadata_offset:metadata_offset + 256] = header
    image[metadata_offset + 256:metadata_offset + 256 + len(tables)] = tables
    return image


def test_inspect_super_image_partition_metadata(tmp_path):
    image = tmp_path / "super.img"
    image.write_bytes(_make_super())

    result = inspect_super_image(image)

    assert result["format"] == "android_super_image"
    assert result["metadata_version"] == "10.2"
    assert result["partition_count"] == 1
    assert result["partitions"][0]["name"] == "system"
    assert result["partitions"][0]["size_bytes"] == 16 * 512
    assert result["partitions"][0]["readonly"] is True
    assert result["metadata_source"] == "primary"


def test_reject_sparse_super_image(tmp_path):
    image = tmp_path / "super.img"
    image.write_bytes(struct.pack("<I", 0xED26FF3A) + bytes(100))

    with pytest.raises(SuperImageError, match="expand the image first"):
        inspect_super_image(image)


def test_reject_corrupt_geometry_checksum(tmp_path):
    image = tmp_path / "super.img"
    data = _make_super()
    data[4096 + 8] ^= 0xFF
    data[8192 + 8] ^= 0xFF
    image.write_bytes(data)

    with pytest.raises(SuperImageError, match="valid liblp geometry"):
        inspect_super_image(image)


def test_reject_invalid_slot(tmp_path):
    image = tmp_path / "super.img"
    image.write_bytes(_make_super())

    with pytest.raises(SuperImageError, match="out of range"):
        inspect_super_image(image, slot=1)
