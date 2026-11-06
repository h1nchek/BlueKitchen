# BlueKitchen

**A modular Android ROM kitchen for inspecting, analyzing, and preparing Android firmware.**

BlueKitchen is an open-source toolkit focused on making Android ROM work more understandable and repeatable. It provides a cross-platform Python CLI and a lightweight desktop interface.

> **Project status:** Active development. ZIP inspection and bounded extraction, Android OTA payload metadata inspection, sparse-image inspection and expansion, boot/vendor_boot metadata inspection, and raw super metadata inspection are implemented. The project does not currently patch firmware, apply OTA payload operations, rebuild Android images, or flash devices.

## Goals

- Inspect ROM archives without modifying source files.
- Safely extract ROM ZIP contents with path and size limits.
- Produce clear, machine-readable reports about archive and image metadata.
- Add dedicated backends for Android image formats and boot-related images.
- Validate device configuration files and highlight missing or inconsistent metadata.
- Keep operations explicit, testable, and safe by default.
- Support Windows, Linux, and macOS where the underlying tools allow it.

## Modules

| Module | Purpose | Status |
| --- | --- | --- |
| CLI core | Python package, command entry point, JSON output | Implemented |
| Desktop GUI | Tkinter interface for common inspection and extraction tasks | Implemented (initial) |
| ROM inspector | Read-only ZIP listing and Android marker detection | Implemented |
| ZIP extraction | Bounded extraction into a new directory; rejects unsafe paths and symlinks | Implemented |
| Payload analyzer | CrAU header and protobuf manifest summary; partition operation counts | Implemented (initial) |
| Image tools | Android sparse-image inspection and expansion to raw images | Implemented (initial) |
| Dynamic partitions | Read-only liblp metadata inspection for raw super images | Implemented (initial) |
| Boot image tools | Read-only Android boot and vendor_boot v0-v4 metadata and section inspection | Implemented (initial) |
| Compatibility checks | Validate device configuration and manifests | Planned |
| Image rebuilding | Modify and rebuild supported Android image formats | Planned |
| OTA construction | Build OTA packages from validated inputs | Planned |

## Quick start

BlueKitchen targets Python 3.10 or newer.

Install from source:

    python -m venv .venv

Windows:

    .venv\Scripts\Activate.ps1
    python -m pip install -e ".[dev]"
    bluekitchen --help
    bluekitchen-gui

Linux and macOS:

    source .venv/bin/activate
    python -m pip install -e ".[dev]"
    bluekitchen --help
    bluekitchen-gui

## CLI commands

| Command | Description |
| --- | --- |
| inspect-zip ROM.zip | List ZIP contents and identify Android markers |
| extract-zip ROM.zip output/ | Extract into a new directory with safety limits |
| inspect-payload payload.bin | Parse OTA payload header and manifest |
| inspect-image system.img | Inspect Android sparse image structure or identify a raw image |
| expand-sparse system.img system.raw | Expand a sparse image without overwriting existing files |
| inspect-boot boot.img | Inspect boot or vendor_boot metadata |
| inspect-super super.raw --slot 0 | Inspect liblp metadata in a raw super image |
| extract-super super.raw system_a system.img --slot 0 | Extract a logical partition from raw super.img |

Add --json to supported inspection commands for machine-readable output.

ZIP extraction is limited by default to 10,000 entries, 512 MiB per file, and 2 GiB total uncompressed data. The destination directory must not already exist. Limits can be adjusted with --max-entries, --max-file-size, and --max-total-size.

## Development

Run tests:

    python -m pytest

Run lint checks:

    python -m ruff check .

See CONTRIBUTING.md for development guidelines, docs/ROADMAP.md for planned work, docs/IMAGE_FORMATS.md for image-format support, and docs/DISTRIBUTION.md for standalone builds and installers.

## Design principles

1. **Read-only first:** inspection commands must not alter firmware inputs.
2. **No silent destructive actions:** future write/patch operations must require explicit intent and explain their effects.
3. **Modular backends:** format-specific tools should be isolated behind stable interfaces.
4. **No fake support:** unsupported formats and missing dependencies must be reported honestly.
5. **Test before claiming:** a feature is not considered supported until it has tests and documented limitations.

## Disclaimer

BlueKitchen is an experimental firmware-analysis and development toolkit. Android firmware operations can cause data loss or render a device unusable if performed incorrectly. Always understand an operation and keep independent backups before working with device firmware. The project does not guarantee compatibility with any device or ROM.

## License

BlueKitchen is licensed under the **GNU General Public License v3.0 or later**. See LICENSE.
