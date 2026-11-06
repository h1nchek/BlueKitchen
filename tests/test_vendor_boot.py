import struct

import pytest

from bluekitchen.boot import BootImageError, inspect_vendor_boot_image


def _vendor_boot(version=3, ramdisk=b"RAMDISK", dtb=b"DTB", fragment_name=b"platform"):
    page_size = 4096
    header_size = 2128 if version == 4 else 2112
    header = bytearray(page_size)
    header[:8] = b"VNDRBOOT"
    struct.pack_into("<5I", header, 8, version, page_size, 0x10000000, 0x11000000, len(ramdisk))
    struct.pack_into("<I", header, 2076, 0x10000100)
    header[2080:2080 + len(b"test-board")] = b"test-board"
    struct.pack_into("<I", header, 2096, header_size)
    struct.pack_into("<IQ", header, 2100, len(dtb), 0x12000000)

    data = bytearray(header)
    data.extend(ramdisk)
    data.extend(bytes((-len(ramdisk)) % page_size))
    data.extend(dtb)
    data.extend(bytes((-len(dtb)) % page_size))

    if version == 4:
        entry_size = 108
        table = struct.pack("<3I", len(ramdisk), 0, 1)
        table += fragment_name + bytes(32 - len(fragment_name))
        table += struct.pack("<16I", *([0] * 16))
        struct.pack_into("<4I", header, 2112, len(table), 1, entry_size, 4)
        data = bytearray(header)
        data.extend(ramdisk)
        data.extend(bytes((-len(ramdisk)) % page_size))
        data.extend(dtb)
        data.extend(bytes((-len(dtb)) % page_size))
        data.extend(table)
        data.extend(bytes((-len(table)) % page_size))
        data.extend(b"BOOT")
    return bytes(data)


def test_inspect_vendor_boot_v3(tmp_path):
    image = tmp_path / "vendor_boot.img"
    image.write_bytes(_vendor_boot())

    result = inspect_vendor_boot_image(image)

    assert result["header_version"] == 3
    assert result["page_size"] == 4096
    assert result["vendor_ramdisk_size"] == len(b"RAMDISK")
    assert [item["name"] for item in result["sections"]] == ["vendor_ramdisk", "dtb"]


def test_inspect_vendor_boot_v4_fragment_table_and_bootconfig(tmp_path):
    image = tmp_path / "vendor_boot.img"
    image.write_bytes(_vendor_boot(version=4))

    result = inspect_vendor_boot_image(image)

    assert result["header_version"] == 4
    assert result["vendor_ramdisk_fragment_count"] == 1
    assert result["vendor_ramdisk_fragments"][0]["name"] == "platform"
    assert result["vendor_ramdisk_fragments"][0]["type"] == "PLATFORM"
    assert result["bootconfig_size"] == 4
    assert result["sections"][-1]["name"] == "bootconfig"


def test_reject_invalid_vendor_boot_magic(tmp_path):
    image = tmp_path / "bad.img"
    image.write_bytes(bytes(4096))

    with pytest.raises(BootImageError, match="Invalid vendor_boot magic"):
        inspect_vendor_boot_image(image)


def test_reject_vendor_ramdisk_fragment_out_of_bounds(tmp_path):
    image = tmp_path / "bad.img"
    data = bytearray(_vendor_boot(version=4))
    # The first table entry begins after the header, ramdisk and DTB page.
    table_offset = 4096 + 4096 + 4096
    struct.pack_into("<I", data, table_offset + 4, 999999)

    with pytest.raises(BootImageError, match="exceeds ramdisk section"):
        inspect_vendor_boot_image(image)
