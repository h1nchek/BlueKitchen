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

The CLI currently exposes two read-only inspectors. `bluekitchen inspect-zip <archive>` reads the ZIP central directory and reports archive sizes, entry counts, selected Android package markers, and suspicious member paths. `bluekitchen inspect-payload <payload.bin>` reads the CrAU header and parses the OTA protobuf manifest to summarize partition names and operation counts. Neither command extracts files or applies update operations.\n\nThe payload parser follows the field layout in the AOSP `update_metadata.proto` schema. It supports the legacy major-version-1 operation lists and the major-version-2 partition list. It does not validate payload signatures, apply data blobs, or establish device compatibility.

The JSON output is intended as an integration point, but is not yet a versioned public schema.

## Extension rules

- Keep format-specific parsing in dedicated modules.
- Do not make external executables mandatory for the core package.
- Return structured data; let the CLI and GUI render it.
- Raise domain-specific errors for expected format and I/O failures.
- Never execute scripts or binaries found inside firmware archives.
