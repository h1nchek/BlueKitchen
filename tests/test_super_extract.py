import pytest

from bluekitchen import super_extract
from bluekitchen.super_extract import SuperExtractError, extract_super_partition


def test_extract_linear_and_zero_extents(tmp_path, monkeypatch):
    source = tmp_path / "super.raw"
    source.write_bytes(b"_" * 1024 + b"A" * 1024 + b"B" * 512)
    output = tmp_path / "system.img"

    monkeypatch.setattr(
        super_extract,
        "inspect_super_image",
        lambda _path, slot=0: {
            "partitions": [{
                "name": "system",
                "size_bytes": 1536,
                "extents": [
                    {
                        "sectors": 2,
                        "target_type": "LINEAR",
                        "physical_sector": 2,
                        "block_device": "super",
                    },
                    {
                        "sectors": 1,
                        "target_type": "ZERO",
                        "physical_sector": None,
                        "block_device": None,
                    },
                ],
            }],
            "block_devices": [{"name": "super", "size": source.stat().st_size}],
        },
    )

    result = extract_super_partition(source, "system", output)

    assert output.read_bytes() == b"A" * 1024 + bytes(512)
    assert result["size_bytes"] == 1536
    assert result["source_preserved"] is True


def test_refuse_existing_output(tmp_path, monkeypatch):
    source = tmp_path / "super.raw"
    source.write_bytes(b"data")
    output = tmp_path / "system.img"
    output.write_bytes(b"keep")

    with pytest.raises(SuperExtractError, match="already exists"):
        extract_super_partition(source, "system", output)

    assert output.read_bytes() == b"keep"


def test_missing_partition_is_reported(tmp_path, monkeypatch):
    source = tmp_path / "super.raw"
    source.write_bytes(b"_" * 4096)
    monkeypatch.setattr(
        super_extract,
        "inspect_super_image",
        lambda _path, slot=0: {"partitions": [], "block_devices": []},
    )

    with pytest.raises(SuperExtractError, match="not found"):
        extract_super_partition(source, "system", tmp_path / "system.img")
