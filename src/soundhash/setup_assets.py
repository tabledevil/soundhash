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
# Prefer the editable-tree path; fall back to the wheel-bundled `_assets` dir.
_DEV_DIR = _HERE.parent.parent / "assets" / "v1" / "sf2"
_WHEEL_DIR = _HERE / "_assets" / "v1" / "sf2"
_TARGET_DIR = _DEV_DIR if _DEV_DIR.parent.parent.exists() else _WHEEL_DIR


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
    sf3 = _TARGET_DIR / _SF3_NAME
    sf2 = _TARGET_DIR / _SF3_NAME.replace(".sf3", ".sf2")

    if not sf3.exists():
        _download(_SF3_URL, sf3)
        sha = hashlib.sha256(sf3.read_bytes()).hexdigest()
        size_mb = sf3.stat().st_size / 1e6
        print(f"  ✓ wrote {sf3} ({size_mb:.1f} MB, sha256={sha[:12]}…)", file=sys.stderr)
    else:
        sha = hashlib.sha256(sf3.read_bytes()).hexdigest()
        size_mb = sf3.stat().st_size / 1e6
        print(f"  ✓ {sf3} already present ({size_mb:.1f} MB, sha256={sha[:12]}…)",
              file=sys.stderr)

    # Decompress SF3 → SF2 once. fluidsynth's per-invocation OGG decode adds
    # ~6 s of startup tax on every render; the uncompressed SF2 loads in
    # ~80 ms. Trades ~440 MB of disk for an 80× speedup.
    if not sf2.exists():
        print("  → converting SF3 → SF2 (one-time, decompresses OGG samples)…",
              file=sys.stderr)
        try:
            from .sf3_to_sf2 import convert
            n, sz = convert(sf3, sf2)
            print(f"  ✓ wrote {sf2} ({sz/1e6:.0f} MB, {n} samples)",
                  file=sys.stderr)
        except Exception as e:
            print(f"  ⚠ SF2 conversion failed ({e}); falling back to SF3 (slow load)",
                  file=sys.stderr)
            return 0
    else:
        print(f"  ✓ {sf2} already present ({sf2.stat().st_size/1e6:.0f} MB)",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
