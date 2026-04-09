from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hybrid_transfer.release import ensure_distribution_layout, validate_build_environment, write_release_files
from hybrid_transfer.release import resolve_pyinstaller_invocation

ENTRYPOINT = ROOT / "hybrid_transfer" / "__main__.py"
SPEC = ROOT / "packaging" / "pyinstaller" / "hybrid_transfer.spec"


def write_quick_start(platform: str) -> None:
    target = ROOT / "dist" / platform / "HybridTransfer" / "README.txt"
    target.write_text(
        "\n".join(
            [
                "Hybrid Transfer quick start",
                "",
                "1. Launch the packaged application.",
                "2. Approve firewall or network prompts if shown.",
                "3. Pick a device and start transferring files.",
                "",
                "Android support: browser access only, no native package yet.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build(platform: str, skip_pyinstaller: bool = False) -> int:
    ensure_distribution_layout(ROOT)
    errors = validate_build_environment(ROOT, ENTRYPOINT)
    if errors and not skip_pyinstaller:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    write_release_files(ROOT, build_date=str(date.today()))
    write_quick_start(platform)

    distpath = ROOT / "dist" / platform
    workpath = ROOT / ".build" / platform
    workpath.mkdir(parents=True, exist_ok=True)

    if skip_pyinstaller:
        return 0

    resolved = resolve_pyinstaller_invocation(ROOT)
    if resolved is None:
        print("PyInstaller is not installed", file=sys.stderr)
        return 1
    cmd_prefix, env = resolved
    cmd = cmd_prefix + [
        "--noconfirm",
        "--distpath",
        str(distpath),
        "--workpath",
        str(workpath),
        str(SPEC),
    ]
    return subprocess.call(cmd, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build release artifacts for Hybrid Transfer.")
    parser.add_argument("platform", choices=["windows", "linux", "macos"])
    parser.add_argument("--skip-pyinstaller", action="store_true")
    args = parser.parse_args()
    return build(args.platform, skip_pyinstaller=args.skip_pyinstaller)


if __name__ == "__main__":
    raise SystemExit(main())
