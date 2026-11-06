import struct

import pytest

from bluekitchen.payload import PayloadError, inspect_payload


def _varint(value):
    encoded = bytearray()
    while value > 0x7F:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def _varint_field(number, value):
    return _varint(number << 3) + _varint(value)


def _bytes_field(number, value):
    return _varint((number << 3) | 2) + _varint(len(value)) + value


def _make_payload(manifest, version=2, signature=b"sig"):
    header = b"CrAU" + struct.pack(">QQ", version, len(manifest))
    if version >= 2:
        header += struct.pack(">I", len(signature))
    return header + manifest + (signature if version >= 2 else b"") + b"partition-data"


def test_inspect_payload_v2_with_partition_operations(tmp_path):
    replace_operation = _varint_field(1, 0)
    zero_operation = _varint_field(1, 6)
    partition = (
        _bytes_field(1, b"system")
        + _bytes_field(8, replace_operation)
        + _bytes_field(8, zero_operation)
    )
    manifest = _varint_field(3, 4096) + _bytes_field(13, partition)
    payload_file = tmp_path / "payload.bin"
    payload_file.write_bytes(_make_payload(manifest))

    result = inspect_payload(payload_file)

    assert result["magic"] == "CrAU"
    assert result["major_version"] == 2
    assert result["block_size"] == 4096
    assert result["partition_count"] == 1
    assert result["partitions"][0]["name"] == "system"
    assert result["partitions"][0]["operations"] == {"REPLACE": 1, "ZERO": 1}
    assert result["metadata_signature_size"] == 3
    assert result["inspection_only"] is True


def test_inspect_payload_v1_without_signature_size(tmp_path):
    manifest = _varint_field(3, 4096)
    payload_file = tmp_path / "payload.bin"
    payload_file.write_bytes(_make_payload(manifest, version=1))

    result = inspect_payload(payload_file)

    assert result["major_version"] == 1
    assert result["metadata_signature_size"] == 0
    assert result["partition_count"] == 0


def test_reject_invalid_magic(tmp_path):
    payload_file = tmp_path / "payload.bin"
    payload_file.write_bytes(b"NOPE" + bytes(32))

    with pytest.raises(PayloadError, match="Invalid payload magic"):
        inspect_payload(payload_file)


def test_reject_manifest_beyond_file_end(tmp_path):
    payload_file = tmp_path / "payload.bin"
    payload_file.write_bytes(b"CrAU" + struct.pack(">QQI", 2, 100, 0))

    with pytest.raises(PayloadError, match="beyond the end"):
        inspect_payload(payload_file)
