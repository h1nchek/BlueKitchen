"""Read-only parser for Android boot image headers (versions 0 through 4)."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, BinaryIO

BOOT_MAGIC = b"ANDROID!"
VENDOR_BOOT_MAGIC = b"VNDRBOOT"
LEGACY_HEADER_SIZE = 1632
V3_HEADER_SIZE = 1580
V4_HEADER_SIZE = 1584
MAX_PAGE_SIZE = 65536


class BootImageError(Exception):
    """Raised when a boot image is malformed or unsupported."""


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def _read_at(stream: BinaryIO, offset: int, size: int, description: str) -> bytes:
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise BootImageError(f"Truncated {description}")
    return data


def _c_string(data: bytes) -> str:
    return data.split(b"\\0", 1)[0].decode("utf-8", errors="replace")


def _check_section(
    name: str, offset: int, size: int, file_size: int
) -> dict[str, int | str]:
    if offset < 0 or size < 0 or offset + size > file_size:
        raise BootImageError(
            f"{name} section extends beyond the end of the file "
            f"(offset={offset}, size={size}, file_size={file_size})"
        )
    return {"name": name, "offset": offset, "size": size}


def _decode_os_version(value: int) -> dict[str, int | str]:
    major = (value >> 25) & 0x7F
    minor = (value >> 18) & 0x7F
    patch = (value >> 11) & 0x7F
    year = ((value >> 4) & 0x7F) + 2000
    month = value & 0xF
    return {
        "raw": value,
        "version": f"{major}.{minor}.{patch}",
        "patch_year": year,
        "patch_month": month,
    }


def inspect_boot_image(path: str | Path) -> dict[str, Any]:
    """Inspect boot.img metadata and section boundaries without extracting data."""
    image_path = Path(path)
    if not image_path.is_file():
        raise BootImageError(f"File does not exist: {image_path}")

    try:
        file_size = image_path.stat().st_size
        with image_path.open("rb") as stream:
            magic = _read_at(stream, 0, 8, "boot image magic")
            if magic != BOOT_MAGIC:
                if magic == VENDOR_BOOT_MAGIC:
                    raise BootImageError(
                        "This is a vendor_boot image; vendor_boot parsing is not "
                        "implemented yet"
                    )
                raise BootImageError("Invalid boot image magic; expected ANDROID!")

            version = struct.unpack("<I", _read_at(stream, 40, 4, "header version"))[0]
            if version > 4:
                raise BootImageError(f"Unsupported boot header version: {version}")

            sections: list[dict[str, int | str]] = []
            if version <= 2:
                values = struct.unpack("<10I", _read_at(stream, 8, 40, "legacy header"))
                (
                    kernel_size,
                    kernel_addr,
                    ramdisk_size,
                    ramdisk_addr,
                    second_size,
                    second_addr,
                    tags_addr,
                    page_size,
                    _header_version,
                    os_version,
                ) = values
                if page_size < LEGACY_HEADER_SIZE or page_size > MAX_PAGE_SIZE:
                    raise BootImageError(
                        f"Invalid legacy page size: {page_size} "
                        f"(expected {LEGACY_HEADER_SIZE}..{MAX_PAGE_SIZE})"
                    )
                if page_size & (page_size - 1):
                    raise BootImageError("Legacy page size must be a power of two")

                name = _c_string(_read_at(stream, 48, 16, "board name"))
                cmdline = _c_string(_read_at(stream, 64, 512, "kernel command line"))
                extra_cmdline = _c_string(_read_at(stream, 608, 1024, "extra command line"))
                header_size = LEGACY_HEADER_SIZE
                if version >= 1:
                    recovery_size, recovery_offset, declared_header_size = struct.unpack(
                        "<IQI", _read_at(stream, 1632, 16, "v1 header extension")
                    )
                    if declared_header_size < 1648 or declared_header_size > page_size:
                        raise BootImageError("Invalid declared boot header size for version 1")
                    header_size = declared_header_size
                else:
                    recovery_size = 0
                    recovery_offset = 0

                dtb_size = 0
                dtb_addr = 0
                if version >= 2:
                    dtb_size, dtb_addr = struct.unpack(
                        "<IQ", _read_at(stream, 1648, 12, "v2 header extension")
                    )
                    declared_header_size = struct.unpack(
                        "<I", _read_at(stream, 1644, 4, "v2 header size")
                    )[0]
                    if declared_header_size < 1660 or declared_header_size > page_size:
                        raise BootImageError("Invalid declared boot header size for version 2")
                    header_size = declared_header_size

                kernel_offset = page_size
                ramdisk_offset = _align(kernel_offset + kernel_size, page_size)
                second_offset = _align(ramdisk_offset + ramdisk_size, page_size)
                sections.append(_check_section("kernel", kernel_offset, kernel_size, file_size))
                sections.append(_check_section("ramdisk", ramdisk_offset, ramdisk_size, file_size))
                if second_size:
                    sections.append(_check_section("second", second_offset, second_size, file_size))

                end_offset = _align(second_offset + second_size, page_size)
                if recovery_size:
                    if recovery_offset < end_offset:
                        raise BootImageError("Recovery DTBO offset overlaps an earlier section")
                    sections.append(
                        _check_section("recovery_dtbo", recovery_offset, recovery_size, file_size)
                    )
                    end_offset = _align(recovery_offset + recovery_size, page_size)
                if dtb_size:
                    sections.append(_check_section("dtb", end_offset, dtb_size, file_size))

                details = {
                    "page_size": page_size,
                    "kernel_address": kernel_addr,
                    "ramdisk_address": ramdisk_addr,
                    "second_address": second_addr,
                    "tags_address": tags_addr,
                    "board_name": name,
                    "kernel_cmdline": " ".join(part for part in (cmdline, extra_cmdline) if part),
                    "os_version": _decode_os_version(os_version),
                    "recovery_dtbo_offset": recovery_offset if recovery_size else None,
                    "dtb_address": dtb_addr if dtb_size else None,
                }
            else:
                kernel_size, ramdisk_size, os_version, header_size = struct.unpack(
                    "<4I", _read_at(stream, 8, 16, "v3/v4 header fields")
                )
                reserved = struct.unpack("<4I", _read_at(stream, 24, 16, "reserved header fields"))
                if any(reserved):
                    raise BootImageError("Reserved boot header fields must be zero")
                if header_size < (V4_HEADER_SIZE if version == 4 else V3_HEADER_SIZE):
                    raise BootImageError("Declared boot header size is too small")
                if header_size > 4096:
                    raise BootImageError("Declared boot header size exceeds the 4096-byte header page")
                cmdline = _c_string(_read_at(stream, 44, 1536, "kernel command line"))
                signature_size = 0
                if version == 4:
                    signature_size = struct.unpack(
                        "<I", _read_at(stream, 1580, 4, "boot signature size")
                    )[0]
                kernel_offset = 4096
                ramdisk_offset = _align(kernel_offset + kernel_size, 4096)
                sections.append(_check_section("kernel", kernel_offset, kernel_size, file_size))
                sections.append(_check_section("ramdisk", ramdisk_offset, ramdisk_size, file_size))
                if signature_size:
                    sections.append(
                        _check_section(
                            "boot_signature", ramdisk_offset + ramdisk_size,
                            signature_size, file_size
                        )
                    )
                details = {
                    "page_size": 4096,
                    "kernel_cmdline": cmdline,
                    "os_version": _decode_os_version(os_version),
                    "boot_signature_size": signature_size,
                }

        return {
            "file": image_path.name,
            "format": "android_boot_image",
            "magic": BOOT_MAGIC.decode("ascii"),
            "header_version": version,
            "header_size": header_size,
            "file_size": file_size,
            "sections": sections,
            "inspection_only": True,
            **details,
        }
    except BootImageError:
        raise
    except OSError as exc:
        raise BootImageError(f"Could not read boot image: {exc}") from exc
    except struct.error as exc:
        raise BootImageError(f"Malformed boot image header: {exc}") from exc
