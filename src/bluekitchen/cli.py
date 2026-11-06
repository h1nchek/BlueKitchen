"""Command-line interface for BlueKitchen."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bluekitchen import __version__
from bluekitchen.inspector import InspectionError, inspect_zip


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
