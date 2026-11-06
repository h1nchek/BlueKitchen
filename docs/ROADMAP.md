# Roadmap

BlueKitchen is developed in small, verifiable stages. A roadmap item is not complete merely because an interface or placeholder exists.

## Phase 0 — Project foundation

- [x] Python package and CLI entry point
- [x] Read-only ZIP inspection
- [x] JSON output for scripting
- [x] Initial automated tests and CI
- [ ] Windows and Linux CI verification

## Phase 1 — ROM package analysis

- [x] Parse Android OTA payload headers and manifest metadata (initial)\n- [ ] Identify common ROM package layouts
- [x] Summarize payload partitions and install operation types (initial)\n- [ ] Inspect OTA metadata and updater configuration
- [ ] Detect payload-based and recovery-style packages
- [ ] Add bounded archive inspection and resource limits
- [ ] Generate complete report directories

## Phase 2 — Android image metadata

- [ ] Detect Android sparse images
- [ ] Inspect super image metadata through optional external tools
- [ ] Inspect boot and vendor_boot headers
- [ ] Document tool dependencies and supported image versions

## Phase 3 — Device compatibility

- [ ] Parse device and vendor manifests
- [ ] Check partition and device metadata consistency
- [ ] Report likely compatibility gaps without claiming a ROM will boot

## Phase 4 — Desktop interface

- [ ] Define stable core API
- [ ] Prototype a PySide6 GUI
- [ ] Keep CLI usable without GUI dependencies

## Safety and quality gates

- Inspection remains read-only by default.
- No automatic extraction of untrusted archives.
- No device flashing feature is planned for the initial releases.
- Every format claim must be backed by tests or documented external-tool output.
