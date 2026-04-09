# Release Build Guide

## Packaging Dependency

Install packaging requirements:

```bash
python3 -m pip install -r requirements-packaging.txt
```

## Platform Builds

Build on the matching platform host.

### Linux

```bash
bash scripts/build_linux.sh
```

### macOS

```bash
bash scripts/build_macos.sh
```

### Windows

```bat
scripts\build_windows.bat
```

## Dry Run Without PyInstaller

Use this only to generate release metadata and quick-start files when PyInstaller is unavailable:

```bash
python3 scripts/build_release.py linux --skip-pyinstaller
```

## Validation

Run automated checks before packaging:

```bash
python3 -m unittest tests/test_hybrid_transfer.py tests/test_transfer_runtime.py tests/test_desktop_ui.py tests/test_packaging_release.py
python3 -m py_compile hybrid_transfer/*.py tests/test_*.py
```

Verify the release layout after a build:

```bash
python3 scripts/verify_release.py --root .
```

## Android Boundary

Android is not packaged as a native client in this workflow. Current Android access is browser-only and will be handled in a later change.
