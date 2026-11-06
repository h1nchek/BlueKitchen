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

The first release exposes the command: bluekitchen inspect-zip <archive>. It reads the ZIP central directory and reports archive sizes, entry counts, selected Android package markers, and suspicious member paths. It does not extract files.

The JSON output is intended as an integration point, but is not yet a versioned public schema.

## Extension rules

- Keep format-specific parsing in dedicated modules.
- Do not make external executables mandatory for the core package.
- Return structured data; let the CLI and GUI render it.
- Raise domain-specific errors for expected format and I/O failures.
- Never execute scripts or binaries found inside firmware archives.
