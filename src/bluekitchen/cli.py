"""Command-line interface for BlueKitchen."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bluekitchen import __version__
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
