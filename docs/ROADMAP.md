# Roadmap

BlueKitchen is developed in small, verifiable stages. A roadmap item is not complete merely because an interface or placeholder exists.

## Phase 0 — Project foundation

- [x] Python package and CLI entry point
- [x] JSON output for scripting
- [x] Automated tests and CI
- [x] Cross-platform executable build workflow
- [x] Initial Windows, Linux and macOS installer workflows

## Phase 1 — ROM package analysis

- [x] Read-only ZIP inspection and Android marker detection
- [x] Inspect OTA ZIP metadata and embedded payload manifest without extracting partition data
- [x] Bounded ZIP extraction with traversal, symlink and size-limit checks
- [x] Create a ZIP package from a prepared directory with symlink and overwrite protection
- [x] Parse Android OTA payload headers and manifest metadata (initial)
- [x] Summarize payload partitions and install operation types (initial)
- [ ] Inspect OTA metadata and updater configuration
- [ ] Detect and report common ROM package layouts
- [ ] Generate complete report directories

## Phase 2 — Android image metadata

- [x] Detect and validate Android sparse image headers and chunk layout (initial)
- [x] Expand sparse images to new raw files without overwriting inputs (initial)
- [x] Parse liblp geometry, metadata slots, partitions, extents, groups and block devices in raw super images (initial)
- [x] Extract linear and zero extents for a selected logical partition from raw super images (initial)
- [ ] Support liblp metadata parsing directly from sparse super images
- [x] Inspect Android boot image headers v0-v4 and section boundaries (initial)
- [x] Inspect vendor_boot v3/v4 headers and ramdisk fragment tables (initial)
- [ ] Extract boot and vendor_boot sections with verified boundaries
- [ ] Inspect common filesystem metadata in raw partition images

## Phase 3 — Device compatibility

- [ ] Parse device and vendor manifests
- [ ] Check partition and device metadata consistency
- [ ] Report likely compatibility gaps without claiming a ROM will boot

## Phase 4 — Desktop interface

- [x] Initial cross-platform Tkinter GUI
- [x] Run common inspection and extraction operations from the GUI
- [x] Save JSON reports
- [ ] Add richer project/workspace management

## Phase 5 — Image preparation

- [ ] Define format-specific write APIs and validation contracts
- [ ] Add controlled image modification workflows
- [x] Add bounded ZIP package construction from prepared directory trees
- [ ] Add reproducible OTA package construction
- [ ] Add checksums and post-build verification

## Safety and quality gates

- Inspection is read-only.
- Archive extraction is bounded and rejects unsafe paths.
- Image expansion writes only to a new output path and preserves the source.
- No device flashing feature is included.
- Every format claim must be backed by tests or documented external-tool output.
