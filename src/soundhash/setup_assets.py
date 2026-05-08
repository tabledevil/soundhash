"""One-shot asset bootstrapper.

Downloads the default GM SoundFont (MuseScore MS Basic SF3, ~50 MB) into
`assets/v1/sf2/` if it isn't already there. Idempotent.

Run:
    python -m soundhash.setup_assets
"""
from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path


_SF3_URL = "https://raw.githubusercontent.com/musescore/MuseScore/master/share/sound/MS%20Basic.sf3"
_SF3_NAME = "MS-Basic.sf3"
_HERE = Path(__file__).resolve().parent
_TARGET_DIR = _HERE.parent.parent / "assets" / "v1" / "sf2"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  → downloading {dest.name} from {url}", file=sys.stderr)
    with urllib.request.urlopen(url) as r, open(dest, "wb") as out:
        size = int(r.headers.get("Content-Length", "0"))
        chunk = 1 << 16
        read = 0
        while True:
            buf = r.read(chunk)
            if not buf:
                break
            out.write(buf)
            read += len(buf)
            if size:
                pct = 100 * read / size
                print(f"\r    {read/1e6:.1f} / {size/1e6:.1f} MB  {pct:5.1f}%",
                      end="", file=sys.stderr, flush=True)
        if size:
            print("", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    target = _TARGET_DIR / _SF3_NAME
    if target.exists():
        sha = hashlib.sha256(target.read_bytes()).hexdigest()
        size_mb = target.stat().st_size / 1e6
        print(f"  ✓ {target} already present ({size_mb:.1f} MB, sha256={sha[:12]}…)",
              file=sys.stderr)
        return 0
    _download(_SF3_URL, target)
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    size_mb = target.stat().st_size / 1e6
    print(f"  ✓ wrote {target} ({size_mb:.1f} MB, sha256={sha[:12]}…)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
