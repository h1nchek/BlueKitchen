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


## Expanding sparse images

Use `expand-sparse` to convert an Android sparse image into a raw image:

```bash
bluekitchen expand-sparse system.img system.raw
```

The command validates the complete sparse chunk layout before creating the output. It processes RAW, FILL, DONT_CARE, and CRC32 chunks in a streaming manner. DONT_CARE ranges are represented as zero-filled holes where the filesystem supports sparse files. The source is never modified, and an existing destination is never overwritten. The output can be as large as the expanded image size, so check available disk space first.


## Dynamic partitions and super images

The `inspect-super` command reads Android liblp metadata from a **raw** `super.img` and reports metadata slots, logical partitions, extents, partition groups, and block devices.

```bash
bluekitchen inspect-super super.raw
bluekitchen inspect-super super.raw --slot 1 --json
```

Sparse super images must first be expanded with `expand-sparse`. The parser validates geometry, metadata-header and table SHA-256 checksums, table bounds, extent references, and metadata-area boundaries. It tries the primary metadata copy and then the backup copy for the selected slot. It does not modify the image, reconstruct logical partition images, or prove that a ROM is compatible with a device.

Format references: [AOSP liblp metadata format](https://android.googlesource.com/platform/system/core/+/master/fs_mgr/liblp/include/liblp/metadata_format.h), [AOSP metadata reader](https://chromium.googlesource.com/aosp/platform/system/core/+/087796c31c8726b60c7471eaf0621da6100ef092/fs_mgr/liblp/reader.cpp), and [AOSP metadata offsets](https://android.googlesource.com/platform/system/core/+/f4cd54e51290e011bfbe9786368da42868d30844/fs_mgr/liblp/utility.cpp).
