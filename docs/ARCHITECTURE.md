# Architecture

BlueKitchen separates the user interface from format-specific inspection logic.

    CLI / future GUI
          |
          v
    Core API (errors, reports, configuration)
          |
          +-- ROM package inspectors
          +-- Android image backends
          +-- device metadata validators
          |
          v
    Read-only filesystem access / optional external tools

## Current implementation

The CLI currently exposes three read-only inspectors:

- `bluekitchen inspect-zip <archive>` reads the ZIP central directory and reports archive sizes, entry counts, selected Android package markers, and suspicious member paths.
- `bluekitchen inspect-payload <payload.bin>` reads the CrAU header and parses the OTA protobuf manifest to summarize partition names and operation counts.
- `bluekitchen inspect-image <image>` validates Android sparse-image headers and chunk layout, or labels non-sparse input as raw/unknown without guessing its filesystem.

None of these commands extracts, expands, modifies, or flashes firmware.

The sparse-image parser follows the AOSP `libsparse` format header and validates declared chunk sizes and output block totals. It does not expand sparse data, inspect filesystem contents, parse `super.img` logical-partition metadata, or verify the image checksum.

The payload parser follows the field layout in the AOSP `update_metadata.proto` schema. It supports the legacy major-version-1 operation lists and the major-version-2 partition list. It does not validate payload signatures, apply data blobs, or establish device compatibility.

The JSON output is intended as an integration point, but is not yet a versioned public schema.

## Extension rules

- Keep format-specific parsing in dedicated modules.
- Do not make external executables mandatory for the core package.
- Return structured data; let the CLI and GUI render it.
- Raise domain-specific errors for expected format and I/O failures.
- Never execute scripts or binaries found inside firmware archives.
