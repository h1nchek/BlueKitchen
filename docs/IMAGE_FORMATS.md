# Android image format support

BlueKitchen's image inspection is deliberately metadata-only.

## Android sparse images

Command:

```powershell
bluekitchen inspect-image path\to\system.img
bluekitchen inspect-image path\to\system.img --json
```

The parser recognizes the Android sparse magic value and reads the version, header sizes, block size, output block count, checksum field, and chunk table. It counts the supported chunk types:

- `RAW` — literal block data
- `FILL` — repeated four-byte fill value
- `DONT_CARE` — output blocks without stored input data
- `CRC32` — checksum chunk

It validates chunk lengths, file boundaries, and the total number of output blocks. The chunk preview is capped at 100 entries and the parser refuses files declaring more than one million chunks.

## Raw or unknown images

Files without the sparse magic are reported as `raw_or_unknown_image`. This is not a filesystem identification result. The file may be an Android boot image, a raw partition image, or another binary format.

## Current limitations

- Sparse data is not expanded or written to disk.
- Filesystem types and filesystem contents are not inspected.
- The checksum field is reported but not recalculated or verified.
- Dynamic-partition metadata inside `super.img` is not parsed yet.
- No image is sent to a connected device.

The sparse header and chunk definitions are based on the Android Open Source Project's `libsparse/sparse_format.h`: https://android.googlesource.com/platform/system/core/+/HEAD/libsparse/sparse_format.h


## Android boot images

The `inspect-boot` command reads Android boot image headers v0-v4 and reports header metadata and the byte ranges of kernel, ramdisk, optional second-stage, recovery DTBO, DTB, and v4 boot-signature sections where present.

```bash
bluekitchen inspect-boot boot.img
bluekitchen inspect-boot boot.img --json
```

The parser validates declared header sizes, page sizes, section bounds, and supported header versions. It does not extract, decompress, modify, repack, verify AVB, or establish device compatibility. Vendor boot images (`VNDRBOOT`) are identified but not parsed yet.

Format references: [AOSP boot image header documentation](https://source.android.com/docs/core/architecture/bootloader/boot-image-header) and [AOSP bootimg.h](https://android.googlesource.com/platform/system/tools/mkbootimg/+/refs/heads/android17-release/include/bootimg/bootimg.h).
