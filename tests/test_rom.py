import struct
from zipfile import ZipFile

from bluekitchen.rom import inspect_rom_archive


def _varint(value):
    encoded = bytearray()
    while value > 0x7F:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def _bytes_field(number, value):
    return _varint((number << 3) | 2) + _varint(len(value)) + value


def _make_payload():
    partition = _bytes_field(1, b"system")
    manifest = _varint(3 << 3) + _varint(4096) + _bytes_field(13, partition)
    header = b"CrAU" + struct.pack(">QQI", 2, len(manifest), 0)
    return header + manifest + b"partition-data"


def test_inspect_rom_zip_with_payload_and_matching_device(tmp_path):
    archive = tmp_path / "BlueOS-mojito.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("payload.bin", _make_payload())
        zip_file.writestr(
            "META-INF/com/android/metadata",
            "pre-device=mojito,sunny\npost-build=example/build\n",
        )

    result = inspect_rom_archive(archive, expected_device="mojito")

    assert result["format"] == "android_rom_zip"
    assert result["device_match"] is True
    assert result["pre_devices"] == ["mojito", "sunny"]
    assert result["payload_partitions"] == ["system"]
    assert result["inspection_only"] is True


def test_report_device_mismatch_without_claiming_incompatibility(tmp_path):
    archive = tmp_path / "rom.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr(
            "META-INF/com/android/metadata",
            "pre-device=another-device\n",
        )

    result = inspect_rom_archive(archive, expected_device="mojito")

    assert result["device_match"] is False
    assert result["payload"] is None


def test_missing_device_metadata_is_unknown(tmp_path):
    archive = tmp_path / "rom.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("META-INF/com/google/android/update-binary", b"stub")

    result = inspect_rom_archive(archive, expected_device="mojito")

    assert result["device_match"] is None
    assert "Recovery installer" in result["markers"]


def test_reject_invalid_embedded_payload(tmp_path):
    archive = tmp_path / "rom.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("payload.bin", b"not a payload")

    import pytest
    from bluekitchen.rom import RomInspectionError

    with pytest.raises(RomInspectionError, match="embedded payload"):
        inspect_rom_archive(archive)

def test_reject_duplicate_payload_entries(tmp_path):
    archive = tmp_path / "duplicate.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("payload.bin", _make_payload())
        zip_file.writestr("payload.bin", _make_payload())

    import pytest
    from bluekitchen.rom import RomInspectionError

    with pytest.raises(RomInspectionError, match="duplicate critical entry"):
        inspect_rom_archive(archive)
