import struct

import pytest

from bluekitchen.image import ImageError, inspect_image


def _chunk(kind, blocks, data=b"", header_size=12):
    return struct.pack("<2H2I", kind, 0, blocks, header_size + len(data)) + data


def _sparse(chunks, total_blocks, block_size=4096, file_header_size=28, chunk_header_size=12):
    header = struct.pack(
        "<I4H4I", 0xED26FF3A, 1, 0, file_header_size, chunk_header_size,
        block_size, total_blocks, len(chunks), 0,
    )
    return header + bytes(file_header_size - len(header)) + b"".join(chunks)


def test_inspect_sparse_image_with_raw_fill_and_dont_care(tmp_path):
    chunks = [
        _chunk(0xCAC1, 1, b"A" * 4096),
        _chunk(0xCAC2, 2, b"FILL"),
        _chunk(0xCAC3, 3),
    ]
    image = tmp_path / "system.img"
    image.write_bytes(_sparse(chunks, 6))

    result = inspect_image(image)

    assert result["format"] == "android_sparse_image"
    assert result["expanded_size"] == 6 * 4096
    assert result["chunk_counts"] == {"DONT_CARE": 1, "FILL": 1, "RAW": 1}
    assert result["inspection_only"] is True


def test_inspect_sparse_image_with_extended_headers(tmp_path):
    image = tmp_path / "extended.img"
    image.write_bytes(_sparse(
        [_chunk(0xCAC3, 1, header_size=16)], 1,
        file_header_size=32, chunk_header_size=16,
    ))
    result = inspect_image(image)
    assert result["file_header_size"] == 32
    assert result["chunk_header_size"] == 16


def test_raw_image_is_not_misidentified_as_filesystem(tmp_path):
    image = tmp_path / "boot.img"
    image.write_bytes(b"ANDROID!" + bytes(64))
    result = inspect_image(image)
    assert result["format"] == "raw_or_unknown_image"
    assert "filesystem type was not determined" in result["note"]


def test_reject_invalid_raw_chunk_size(tmp_path):
    image = tmp_path / "broken.img"
    image.write_bytes(_sparse([_chunk(0xCAC1, 1, b"short")], 1))
    with pytest.raises(ImageError, match="RAW chunk size"):
        inspect_image(image)


def test_reject_block_count_mismatch(tmp_path):
    image = tmp_path / "broken.img"
    image.write_bytes(_sparse([_chunk(0xCAC3, 1)], 2))
    with pytest.raises(ImageError, match="block count mismatch"):
        inspect_image(image)


def test_reject_unknown_chunk_type(tmp_path):
    image = tmp_path / "broken.img"
    image.write_bytes(_sparse([_chunk(0xCAFE, 1)], 1))
    with pytest.raises(ImageError, match="Unsupported sparse chunk type"):
        inspect_image(image)


def test_reject_truncated_sparse_header(tmp_path):
    image = tmp_path / "broken.img"
    image.write_bytes(struct.pack("<I", 0xED26FF3A))
    with pytest.raises(ImageError, match="Truncated sparse image header"):
        inspect_image(image)
