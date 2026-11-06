"""Command-line interface for BlueKitchen."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bluekitchen import __version__
from bluekitchen.boot import BootImageError, inspect_boot_image
from bluekitchen.image import ImageError, expand_sparse_image, inspect_image
from bluekitchen.inspector import InspectionError, inspect_zip
from bluekitchen.payload import PayloadError, inspect_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bluekitchen",
        description="Inspect Android ROM packages safely (read-only).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser(
        "inspect-zip", help="Inspect a ROM ZIP without extracting it"
    )
    inspect_parser.add_argument("archive", type=Path, help="Path to the ROM ZIP")
    inspect_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    image_parser = commands.add_parser(
        "inspect-image", help="Inspect an Android sparse image or identify a raw image"
    )
    image_parser.add_argument("image", type=Path, help="Path to an image file")
    image_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    boot_parser = commands.add_parser(
        "inspect-boot", help="Inspect an Android boot.img header and section layout"
    )
    boot_parser.add_argument("image", type=Path, help="Path to boot.img")
    boot_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    expand_parser = commands.add_parser(
        "expand-sparse", help="Expand a sparse image into a new raw image file"
    )
    expand_parser.add_argument("image", type=Path, help="Sparse image to expand")
    expand_parser.add_argument("output", type=Path, help="New raw image output path")

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
