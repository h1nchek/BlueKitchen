import struct

import pytest

from bluekitchen.boot import BootImageError, inspect_boot_image


def _legacy_boot(version=0, page_size=2048, kernel=b"KERNEL", ramdisk=b"RAMDISK"):
    header = bytearray(1632)
    header[:8] = b"ANDROID!"
    struct.pack_into(
        "<10I", header, 8,
        len(kernel), 0x10008000, len(ramdisk), 0x11000000,
        0, 0, 0x10000100, page_size, version, 0,
    )
    data = bytearray(page_size)
    data[:len(header)] = header
    data.extend(kernel)
    data.extend(bytes((-len(kernel)) % page_size))
    data.extend(ramdisk)
    data.extend(bytes((-len(ramdisk)) % page_size))
    return bytes(data)


def _modern_boot(version=3, kernel=b"KERNEL", ramdisk=b"RAMDISK", signature=b""):
    header = bytearray(4096)
    header[:8] = b"ANDROID!"
    header_size = 1584 if version == 4 else 1580
    struct.pack_into("<4I", header, 8, len(kernel), len(ramdisk), 0, header_size)
    struct.pack_into("<I", header, 40, version)
    if version == 4:
        struct.pack_into("<I", header, 1580, len(signature))
    data = bytearray(header)
    data.extend(kernel)
    data.extend(bytes((-len(kernel)) % 4096))
    data.extend(ramdisk)
    data.extend(signature)
    return bytes(data)


def test_inspect_legacy_boot_image_v0(tmp_path):
    image = tmp_path / "boot.img"
    image.write_bytes(_legacy_boot())

    result = inspect_boot_image(image)

    assert result["format"] == "android_boot_image"
    assert result["header_version"] == 0
    assert result["page_size"] == 2048
    assert result["sections"][0]["name"] == "kernel"
    assert result["sections"][1]["name"] == "ramdisk"
    assert result["inspection_only"] is True


def test_inspect_modern_boot_image_v3(tmp_path):
    image = tmp_path / "boot.img"
    image.write_bytes(_modern_boot())

    result = inspect_boot_image(image)

    assert result["header_version"] == 3
    assert result["page_size"] == 4096
    assert result["sections"][0]["offset"] == 4096


def test_inspect_boot_image_v4_signature(tmp_path):
    image = tmp_path / "boot.img"
    image.write_bytes(_modern_boot(version=4, signature=b"SIGN"))

    result = inspect_boot_image(image)

    assert result["boot_signature_size"] == 4
    assert result["sections"][-1]["name"] == "boot_signature"


def test_reject_invalid_magic(tmp_path):
    image = tmp_path / "bad.img"
    image.write_bytes(b"not-boot")

    with pytest.raises(BootImageError, match="Invalid boot image magic"):
        inspect_boot_image(image)


def test_vendor_boot_image_is_auto_detected(tmp_path):
    image = tmp_path / "vendor_boot.img"
    header = bytearray(4096)
    header[:8] = b"VNDRBOOT"
    struct.pack_into("<5I", header, 8, 3, 4096, 0, 0, 0)
    struct.pack_into("<I", header, 2096, 2112)
    image.write_bytes(header)

    result = inspect_boot_image(image)

    assert result["format"] == "android_vendor_boot_image"
    assert result["header_version"] == 3


def test_reject_truncated_kernel_section(tmp_path):
    image = tmp_path / "bad.img"
    image.write_bytes(_modern_boot(kernel=b"K" * 16)[:4100])

    with pytest.raises(BootImageError, match="kernel section extends"):
        inspect_boot_image(image)
