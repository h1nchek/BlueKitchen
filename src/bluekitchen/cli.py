"""Command-line interface for BlueKitchen."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bluekitchen import __version__
from bluekitchen.boot import BootImageError, inspect_boot_image
from bluekitchen.dynamic_partitions import SuperImageError, inspect_super_image
from bluekitchen.image import ImageError, expand_sparse_image, inspect_image
from bluekitchen.extractor import ExtractionError, extract_zip
from bluekitchen.super_extract import SuperExtractError, extract_super_partition
from bluekitchen.inspector import InspectionError, inspect_zip
from bluekitchen.payload import PayloadError, inspect_payload
from bluekitchen.packer import PackingError, pack_zip


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bluekitchen",
        description="Analyze Android ROM packages and prepare image files without modifying source inputs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser(
        "inspect-zip", help="Inspect a ROM ZIP without extracting it"
    )
    inspect_parser.add_argument("archive", type=Path, help="Path to the ROM ZIP")
    inspect_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    extract_parser = commands.add_parser(
        "extract-zip", help="Safely extract a ROM ZIP into a new directory"
    )
    extract_parser.add_argument("archive", type=Path, help="Path to the ROM ZIP")
    extract_parser.add_argument("output", type=Path, help="New output directory (must not exist)")
    extract_parser.add_argument("--max-total-size", type=int, default=2 * 1024 * 1024 * 1024,
                                help="Maximum total uncompressed size in bytes")
    extract_parser.add_argument("--max-file-size", type=int, default=512 * 1024 * 1024,
                                help="Maximum size of one extracted file in bytes")
    extract_parser.add_argument("--max-entries", type=int, default=10000,
                                help="Maximum number of archive entries")

    image_parser = commands.add_parser(
        "inspect-image", help="Inspect an Android sparse image or identify a raw image"
    )
    image_parser.add_argument("image", type=Path, help="Path to an image file")
    image_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    boot_parser = commands.add_parser(
        "inspect-boot", help="Inspect an Android boot or vendor_boot image header and section layout"
    )
    boot_parser.add_argument("image", type=Path, help="Path to boot.img")
    boot_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    super_parser = commands.add_parser(
        "inspect-super", help="Inspect Android dynamic partition metadata in a raw super image"
    )
    super_parser.add_argument("image", type=Path, help="Path to a raw super.img")
    super_parser.add_argument("--slot", type=int, default=0, help="Metadata slot number (default: 0)")
    super_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    super_extract_parser = commands.add_parser(
        "extract-super",
        help="Extract one logical partition from a raw super image into a new image file",
    )
    super_extract_parser.add_argument("image", type=Path, help="Path to a raw super.img")
    super_extract_parser.add_argument("partition", help="Logical partition name, e.g. system_a")
    super_extract_parser.add_argument("output", type=Path, help="New output image path")
    super_extract_parser.add_argument("--slot", type=int, default=0, help="Metadata slot number")

    expand_parser = commands.add_parser(
        "expand-sparse", help="Expand a sparse image into a new raw image file"
    )
    expand_parser.add_argument("image", type=Path, help="Sparse image to expand")
    expand_parser.add_argument("output", type=Path, help="New raw image output path")

    pack_parser = commands.add_parser(
        "pack-zip", help="Create a ROM ZIP from a prepared directory"
    )
    pack_parser.add_argument("directory", type=Path, help="Prepared ROM directory")
    pack_parser.add_argument("output", type=Path, help="New output ZIP path")

    payload_parser = commands.add_parser(
        "inspect-payload", help="Inspect an Android OTA payload.bin header and manifest"
    )
    payload_parser.add_argument("payload", type=Path, help="Path to payload.bin")
    payload_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "inspect-zip":
        try:
            result = inspect_zip(args.archive)
        except InspectionError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Archive: {result['file']}")
            print(f"Entries: {result['entries']} ({result['files']} files, {result['directories']} dirs)")
            print(f"Uncompressed: {result['uncompressed_bytes']} bytes")
            print(f"Compressed: {result['compressed_bytes']} bytes")
            print("Android markers:")
            if result["android_markers"]:
                for marker in result["android_markers"]:
                    print(f"  - {marker}")
            else:
                print("  - No known Android markers found")
            if result["unsafe_paths"]:
                print("WARNING: unsafe archive paths detected:")
                for name in result["unsafe_paths"]:
                    print(f"  - {name}")
        return 0
    if args.command == "extract-zip":
        try:
            result = extract_zip(
                args.archive,
                args.output,
                max_total_size=args.max_total_size,
                max_file_size=args.max_file_size,
                max_entries=args.max_entries,
            )
        except ExtractionError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"Archive: {result['archive']}")
        print(f"Output: {result['destination']}")
        print(f"Files extracted: {result['files_extracted']}")
        print(f"Uncompressed: {result['uncompressed_bytes']} bytes")
        print("Source archive was not modified; existing output directories are never overwritten.")
        return 0
    if args.command == "pack-zip":
        try:
            result = pack_zip(args.directory, args.output)
        except PackingError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"Source directory: {result['source_directory']}")
        print(f"Archive: {result['archive']}")
        print(f"Files packed: {result['files_packed']}")
        print(f"Uncompressed: {result['uncompressed_bytes']} bytes")
        print("Source directory was not modified; existing output files are never overwritten.")
        return 0
    if args.command == "inspect-image":
        try:
            result = inspect_image(args.image)
        except ImageError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif result["is_sparse"]:
            print(f"Image: {result['file']}")
            print(f"Format: Android sparse v{result['major_version']}.{result['minor_version']}")
            print(f"File size: {result['file_size']} bytes")
            print(f"Expanded size: {result['expanded_size']} bytes")
            print(f"Block size: {result['block_size']} bytes")
            print(f"Chunks: {result['total_chunks']}")
            for name, count in result["chunk_counts"].items():
                print(f"  {name}: {count}")
            if result["trailing_bytes"]:
                print(f"Trailing bytes: {result['trailing_bytes']}")
            print("Inspection only: image data was not expanded or modified.")
        else:
            print(f"Image: {result['file']}")
            print("Format: raw or unknown (not an Android sparse image)")
            print(f"File size: {result['file_size']} bytes")
            print("Filesystem type was not determined.")
        return 0
    if args.command == "inspect-super":
        try:
            result = inspect_super_image(args.image, slot=args.slot)
        except SuperImageError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            geometry = result["geometry"]
            print(f"Super image: {result['file']}")
            print(f"Metadata version: {result['metadata_version']}")
            print(f"Metadata slot: {result['metadata_slot']} ({result['metadata_source']})")
            print(f"Metadata slots available: {geometry['metadata_slot_count']}")
            print(f"Partitions: {result['partition_count']}")
            for partition in result["partitions"]:
                print(
                    f"  - {partition['name']}: {partition['size_bytes']} bytes, "
                    f"group={partition['group']}, extents={partition['extent_count']}"
                )
            print("Inspection only: super image was not modified.")
        return 0
    if args.command == "expand-sparse":
        try:
            result = expand_sparse_image(args.image, args.output)
        except ImageError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"Expanded: {result['source']}")
        print(f"Output: {result['output']}")
        print(f"Size: {result['expanded_size']} bytes")
        print(f"Chunks processed: {result['chunks_processed']}")
        print("Source image was not modified; existing output files are never overwritten.")
        return 0
    if args.command == "extract-super":
        try:
            result = extract_super_partition(
                args.image, args.partition, args.output, slot=args.slot
            )
        except SuperExtractError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"Super image: {result['source']}")
        print(f"Partition: {result['partition']}")
        print(f"Output: {result['output']}")
        print(f"Size: {result['size_bytes']} bytes")
        print(f"Extents: {result['extent_count']}")
        print("Source image was not modified; existing output files are never overwritten.")
        return 0
    if args.command == "inspect-boot":
        try:
            result = inspect_boot_image(args.image)
        except BootImageError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Boot image: {result['file']}")
            print(f"Header version: {result['header_version']}")
            print(f"Header size: {result['header_size']} bytes")
            print(f"Page size: {result['page_size']} bytes")
            print(f"File size: {result['file_size']} bytes")
            if result.get("board_name"):
                print(f"Board: {result['board_name']}")
            if result.get("kernel_cmdline"):
                print(f"Kernel cmdline: {result['kernel_cmdline']}")
            print("Sections:")
            for section in result["sections"]:
                print(f"  - {section['name']}: offset {section['offset']}, {section['size']} bytes")
            print("Inspection only: image data was not extracted or modified.")
        return 0
    if args.command == "inspect-payload":
        try:
            result = inspect_payload(args.payload)
        except PayloadError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Payload: {result['file']}")
            print(f"Format: {result['format']} (CrAU v{result['major_version']})")
            print(f"File size: {result['file_size']} bytes")
            print(f"Manifest: {result['manifest_size']} bytes at offset {result['manifest_offset']}")
            print(f"Metadata signature: {result['metadata_signature_size']} bytes")
            print(f"Payload data starts at: {result['data_offset']}")
            if result["block_size"] is not None:
                print(f"Block size: {result['block_size']} bytes")
            print(f"Partitions: {result['partition_count']}")
            for partition in result["partitions"]:
                print(f"  - {partition['name'] or '<unnamed>'}: {partition['operation_count']} operations")
                for operation, count in partition["operations"].items():
                    print(f"      {operation}: {count}")
            print("Inspection only: partition operations were not applied.")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
