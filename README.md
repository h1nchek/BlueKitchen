# BlueKitchen

**A modular Android ROM kitchen for inspecting, analyzing, and preparing Android firmware.**

BlueKitchen is an open-source toolkit focused on making Android ROM work more understandable and repeatable. It starts with a cross-platform Python CLI and is designed to grow into a modular toolkit with optional graphical interfaces.

> **Project status:** Early development. Read-only ZIP inspection, Android OTA payload metadata inspection, and Android sparse-image inspection and expansion, Android boot/vendor_boot metadata inspection, and raw super metadata inspection are implemented. Firmware modification and image-writing features are not yet implemented.

## Goals

- Inspect ROM archives without modifying the source files.
- Produce clear, machine-readable reports about archive contents.
- Add dedicated backends for Android image formats and boot-related images.
- Validate device configuration files and highlight missing or inconsistent metadata.
- Keep operations explicit, testable, and safe by default.
- Support Windows and Linux where the underlying tools allow it.

## Planned modules

| Module | Purpose | Status |
| --- | --- | --- |
| CLI core | Python package, command entry point, JSON output | Implemented (initial) |
| ROM inspector | Read-only ZIP listing and Android marker detection | Implemented (initial) |
| Payload analyzer | CrAU header and protobuf manifest summary; partition operation counts | Implemented (initial) |
| Image tools | Android sparse-image inspection and expansion to raw images | Implemented (initial) |\n| Dynamic partitions | Read-only liblp metadata inspection for raw super images | Implemented (initial) |\n| Boot image tools | Read-only Android boot and vendor_boot v0-v4 metadata, section layout, and vendor ramdisk fragment table inspection | Implemented (initial) |
| Boot image tools | Inspect boot and vendor boot metadata | Planned |
| Compatibility checks | Validate device configuration and manifests | Planned |
| GUI | Optional desktop interface | Planned |

## Quick start

BlueKitchen currently targets Python 3.10 or newer.

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
bluekitchen --help
bluekitchen inspect-payload path\to\payload.bin
bluekitchen inspect-image path\to\system.img
```

Linux:

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
bluekitchen --help
bluekitchen inspect-payload /path/to/payload.bin
bluekitchen inspect-image /path/to/system.img\nbluekitchen expand-sparse /path/to/system.img /path/to/system.raw\nbluekitchen inspect-boot /path/to/boot.img\nbluekitchen inspect-super /path/to/super.raw --slot 0
```

To get machine-readable output, add `--json`:

```bash
bluekitchen inspect-payload payload.bin --json
bluekitchen inspect-image system.img --json\nbluekitchen inspect-boot boot.img --json
```

## Development

Run tests:

```bash
python -m pytest
```

Run lint checks:

```bash
python -m ruff check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines, [docs/ROADMAP.md](docs/ROADMAP.md) for planned work, [docs/IMAGE_FORMATS.md](docs/IMAGE_FORMATS.md) for image-format support, and [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md) for standalone Windows, Linux, and macOS builds.

## Design principles

1. **Read-only first:** inspection commands must not alter firmware inputs.
2. **No silent destructive actions:** future write/patch operations must require explicit intent and explain their effects.
3. **Modular backends:** format-specific tools should be isolated behind stable interfaces.
4. **No fake support:** unsupported formats and missing dependencies must be reported honestly.
5. **Test before claiming:** a feature is not considered supported until it has tests and documented limitations.

## Disclaimer

BlueKitchen is an experimental firmware-analysis and development toolkit. Android firmware operations can cause data loss or render a device unusable if performed incorrectly. Always understand an operation and keep independent backups before working with device firmware. The project does not guarantee compatibility with any device or ROM.

## License

BlueKitchen is licensed under the **GNU General Public License v3.0 or later**. See [LICENSE](LICENSE).
