# Building binaries and installers

BlueKitchen uses PyInstaller to package the Python CLI as a standalone executable. End users do not need to install Python.

## Supported build targets

GitHub Actions builds on native hosted runners:

| Platform | Output |
| --- | --- |
| Windows x86-64 | `bluekitchen.exe` and a Windows Setup `.exe` |
| Linux x86-64 | `bluekitchen` and a Debian/Ubuntu `.deb` package |
| macOS (Darwin) | `bluekitchen` and a macOS `.pkg` installer |

A binary is specific to its operating system and CPU architecture. Do not rename a Windows build and expect it to run on Linux or macOS.

## Installers

- **Windows:** Inno Setup installs `bluekitchen.exe` under Program Files and creates a Start Menu shortcut. The installer currently does not modify PATH; run the executable from its install directory or add that directory to PATH manually.
- **Linux:** the `.deb` package installs the executable to `/usr/bin/bluekitchen`. It targets Debian-family x86-64 systems (including Ubuntu and Linux Mint), not every Linux distribution.
- **macOS:** the `.pkg` installs the executable to `/usr/local/bin/bluekitchen`. It is currently unsigned and not notarized, so Gatekeeper may warn.

These are command-line packages, not graphical applications. The Linux package is currently `.deb` only; RPM, AppImage and Flatpak are not provided.

## Build locally

Use Python 3.10 or newer:

```bash
python -m pip install . "pyinstaller>=6,<7"
pyinstaller --noconfirm --clean --onefile --console --name bluekitchen --paths src src/bluekitchen/__main__.py
```

The standalone executable is written to `dist/`.

## CI artifacts and releases

Run **Build binaries and installers** manually from the GitHub Actions tab. The workflow uploads separate executable and installer artifacts, retained for 30 days.

Pushing a version tag such as `v0.1.0` builds all platform targets and publishes executables and installers as GitHub Release assets. The release workflow generates release notes automatically.

## Limitations

The installers and binaries are not code-signed. Windows SmartScreen and macOS Gatekeeper may show warnings. Signing/notarization require appropriate certificates and accounts.

The Linux binary is built on the current GitHub-hosted Ubuntu image. Compatibility with older distributions and older glibc versions is not guaranteed.
