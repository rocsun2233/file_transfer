from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hybrid_transfer.release import validate_release_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Hybrid Transfer release layout.")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    errors = validate_release_outputs(Path(args.root).resolve())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("release outputs verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
