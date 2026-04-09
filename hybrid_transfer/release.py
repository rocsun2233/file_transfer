from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


RELEASE_VERSION = "0.1.0"
SUPPORTED_PLATFORMS = ["windows", "linux", "macos"]


def build_release_manifest(build_date: str) -> dict[str, Any]:
    return {
        "version": RELEASE_VERSION,
        "build_date": build_date,
        "platforms": SUPPORTED_PLATFORMS,
        "android": {
            "mode": "browser-only",
            "note": "Android is currently supported through browser access only and is not packaged natively.",
        },
        "features": [
            "desktop workbench",
            "lan discovery",
            "trusted peer pairing",
            "tcp file transfer",
            "web guest access",
        ],
    }


def ensure_distribution_layout(root: Path) -> None:
    root = Path(root)
    for platform in SUPPORTED_PLATFORMS:
        (root / "dist" / platform / "HybridTransfer").mkdir(parents=True, exist_ok=True)
    (root / "release").mkdir(parents=True, exist_ok=True)


def resolve_pyinstaller_invocation(root: Path) -> tuple[list[str], dict[str, str] | None] | None:
    root = Path(root)
    if importlib.util.find_spec("PyInstaller") is not None:
        return [sys.executable, "-m", "PyInstaller"], None

    site_packages = root / "myenv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if (site_packages / "PyInstaller" / "__main__.py").exists():
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            f"{site_packages}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else str(site_packages)
        )
        return [sys.executable, "-m", "PyInstaller"], env

    pyinstaller = shutil.which("pyinstaller")
    if pyinstaller is not None:
        return [pyinstaller], None

    return None


def validate_build_environment(root: Path, entrypoint: Path) -> list[str]:
    root = Path(root)
    entrypoint = Path(entrypoint)
    errors: list[str] = []
    if resolve_pyinstaller_invocation(root) is None:
        errors.append("PyInstaller is not installed")
    if not entrypoint.exists():
        errors.append(f"Missing entrypoint: {entrypoint}")
    if not root.exists():
        errors.append(f"Missing project root: {root}")
    return errors


def validate_release_outputs(root: Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    release_dir = root / "release"
    for name in ("manifest.json", "README.md", "CHANGELOG.md"):
        if not (release_dir / name).exists():
            errors.append(f"Missing release file: {name}")
    for platform in SUPPORTED_PLATFORMS:
        platform_dir = root / "dist" / platform / "HybridTransfer"
        if not platform_dir.is_dir():
            errors.append(f"Missing platform output: {platform_dir}")
        if not (platform_dir / "README.txt").exists():
            errors.append(f"Missing quick start: {platform_dir / 'README.txt'}")
    return errors


def write_release_files(root: Path, build_date: str) -> None:
    root = Path(root)
    ensure_distribution_layout(root)
    manifest = build_release_manifest(build_date)
    (root / "release" / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
