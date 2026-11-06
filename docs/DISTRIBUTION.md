# Building standalone binaries

BlueKitchen uses PyInstaller to package the Python CLI as a standalone executable. End users do not need to install Python.

## Supported build targets

The GitHub Actions workflow builds on native hosted runners:

- Windows x86-64: `bluekitchen.exe`
- Linux x86-64: `bluekitchen`
- macOS (Darwin): `bluekitchen`

A binary is specific to its operating system and CPU architecture. Do not rename a Windows build and expect it to run on Linux or macOS.

## Build locally

Use Python 3.10 or newer:

```bash
python -m pip install . "pyinstaller>=6,<7"
pyinstaller --noconfirm --clean --onefile --console --name bluekitchen --paths src src/bluekitchen/__main__.py
```

The standalone executable is written to `dist/`.

## CI artifacts and releases

Run **Build binaries** manually from the GitHub Actions tab to obtain temporary downloadable artifacts. They are retained for 30 days.

Pushing a version tag such as `v0.1.0` builds all platform targets and publishes the executables as GitHub Release assets. The release workflow generates release notes automatically.

## Installer boundary

The workflow intentionally produces portable executables, not installers. A Windows installer can wrap `bluekitchen.exe`; Linux packaging can later provide AppImage, deb, or rpm formats; macOS packaging can provide an app bundle or signed package.

The current binaries are not code-signed or notarized. Windows SmartScreen and macOS Gatekeeper may show warnings. Signing/notarization and installer creation are separate distribution tasks and require the appropriate certificates and accounts.

The Linux binary is built on the current GitHub-hosted Ubuntu image. Compatibility with older distributions and older glibc versions is not guaranteed yet.
