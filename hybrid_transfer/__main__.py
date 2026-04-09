from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from hybrid_transfer.desktop import DesktopShell
else:
    from .desktop import DesktopShell


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid LAN file transfer prototype")
    parser.add_argument("--state-path", default=str(Path(".hybrid_transfer/state.json")))
    args = parser.parse_args()

    shell = DesktopShell(state_path=args.state_path)
    shell.run()


if __name__ == "__main__":
    main()
