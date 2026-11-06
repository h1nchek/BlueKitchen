import struct

import pytest

from bluekitchen.image import ImageError, expand_sparse_image


def _chunk(kind, blocks, data=b"", header_size=12):
    return struct.pack("<2H2I", kind, 0, blocks, header_size + len(data)) + bytes(header_size - 12) + data


def _sparse(chunks, total_blocks, block_size=4096):
    header = struct.pack(
        "<I4H4I", 0xED26FF3A, 1, 0, 28, 12, block_size, total_blocks, len(chunks), 0
    )
    return header + bytes(28 - len(header)) + b"".join(chunks)


def test_expand_sparse_image_raw_fill_and_dont_care(tmp_path):
    source = tmp_path / "system.img"
    output = tmp_path / "system.raw"
    source.write_bytes(_sparse([
        _chunk(0xCAC1, 1, b"A" * 4096),
        _chunk(0xCAC2, 1, b"FILL"),
        _chunk(0xCAC3, 1),
    ], 3))

    result = expand_sparse_image(source, output)

    raw = output.read_bytes()
    assert raw[:4096] == b"A" * 4096
    assert raw[4096:8192] == b"FILL" * 1024
    assert raw[8192:] == bytes(4096)
    assert result["expanded_size"] == 3 * 4096
    assert source.exists()


def test_expand_sparse_refuses_to_overwrite(tmp_path):
    source = tmp_path / "source.img"
    output = tmp_path / "existing.raw"
    source.write_bytes(_sparse([_chunk(0xCAC3, 1)], 1))
    output.write_bytes(b"keep")

    with pytest.raises(ImageError, match="already exists"):
        expand_sparse_image(source, output)

    assert output.read_bytes() == b"keep"


def test_expand_sparse_rejects_raw_input(tmp_path):
    source = tmp_path / "raw.img"
    source.write_bytes(b"not sparse")

    with pytest.raises(ImageError, match="not an Android sparse image"):
        expand_sparse_image(source, tmp_path / "out.img")
