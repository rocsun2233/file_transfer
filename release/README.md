# Hybrid Transfer Release

Versioned desktop release artifacts live under `dist/`.

Supported packaged targets:

- Windows
- Linux
- macOS

Android support is currently browser-only. No Android native package is produced in this release workflow.

Build flow:

1. Install dependencies from `requirements-packaging.txt`
2. Run the platform build script in `scripts/`
3. Verify outputs with `python3 scripts/verify_release.py`
