# Building binaries and installers

BlueKitchen uses PyInstaller to package the Python CLI and desktop GUI. End users do not need to install Python.

## Supported build targets

GitHub Actions builds on native hosted runners:

| Platform | Outputs |
| --- | --- |
| Windows x86-64 | CLI and GUI executables, plus a Windows Setup .exe |
| Linux x86-64 | CLI and GUI executables, plus a Debian/Ubuntu .deb package |
| macOS | CLI and GUI executables, plus a macOS .pkg installer |

A binary is specific to its operating system and CPU architecture. Do not rename a Windows build and expect it to run on Linux or macOS.

## Installers

- **Windows:** Inno Setup installs the CLI and GUI executables under Program Files and creates Start Menu shortcuts.
- **Linux:** the .deb package installs bluekitchen and bluekitchen-gui to /usr/bin. It targets Debian-family x86-64 systems, including Ubuntu and Linux Mint.
- **macOS:** the .pkg installs the CLI and GUI executables to /usr/local/bin. The GUI is launched from a terminal with bluekitchen-gui.

The Linux package is .deb only; RPM, AppImage and Flatpak are not provided. The macOS package is a command-line tool plus a Tkinter GUI executable, not a signed application bundle.

## Build locally

Use Python 3.10 or newer:

    python -m pip install . "pyinstaller>=6,<7"
    pyinstaller --noconfirm --clean --onefile --console --name bluekitchen --paths src src/bluekitchen/__main__.py
    pyinstaller --noconfirm --clean --onefile --windowed --name bluekitchen-gui --paths src src/bluekitchen/gui.py

The standalone executables are written to dist/.

## CI artifacts and releases

Run **Build binaries and installers** manually from the GitHub Actions tab, or push to main. The workflow uploads platform binaries and installers as separate artifacts, retained for 30 days.

Pushing a version tag such as v0.1.0 builds all platform targets and publishes executables and installers as GitHub Release assets. The release workflow generates release notes automatically.

## Limitations

The installers and binaries are not code-signed. Windows SmartScreen and macOS Gatekeeper may show warnings. Signing/notarization require appropriate certificates and accounts.

The Linux binary is built on the current GitHub-hosted Ubuntu image. Compatibility with older distributions and older glibc versions is not guaranteed. The GUI requires Tk support, which PyInstaller bundles on supported runners.
