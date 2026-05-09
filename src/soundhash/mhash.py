"""`mhash` — minimal "hear what this file sounds like" CLI.

Usage:
    mhash <file>              # render and play
    mhash -o <file>           # write <file>.wav next to the file (no playback)
    mhash -o out.wav <file>   # write to a specific path (no playback)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="mhash",
        description="Play a file's deterministic musical hash. "
                    "Use -o to write a .wav instead of playing.")
    p.add_argument("file", help="file to hash")
    p.add_argument("-o", "--output", action="store_true",
                   help="write <file>.soundhash.wav next to the input and exit "
                        "without playing")
    p.add_argument("--out", default=None, metavar="PATH",
                   help="like -o but write to a specific path")
    p.add_argument("--mood", help="override mood (M0..M14)")
    p.add_argument("--mime", default="auto")
    p.add_argument("-q", "--quiet", action="store_true")
    args = p.parse_args(argv)

    if not _ensure_fluidsynth():
        return 2
    if not _ensure_soundfont(quiet=args.quiet):
        return 3

    from .decode import hash_to_spec
    from .mime import detect_mime
    from .render.audio import render_wav
    from .render.midi import render_midi
    from . import SPEC_VERSION

    try:
        with open(args.file, "rb") as f:
            digest = hashlib.sha256(f.read()).digest()
    except OSError as e:
        print(f"mhash: {e}", file=sys.stderr)
        return 1

    mime = detect_mime(args.file) if args.mime == "auto" else args.mime
    spec = hash_to_spec(digest, mime=mime, version=SPEC_VERSION,
                        mood_override=args.mood)
    midi = render_midi(spec)
    prov = {
        "hash_hex": spec.provenance.hash_hex,
        "mood": spec.provenance.mood,
        "mode": spec.mode,
        "key_root": spec.key_root,
        "tempo_bpm": f"{spec.tempo_bpm:.2f}",
        "form_id": spec.form_id,
        "bars": len(spec.bars),
        "groove_template_id": spec.groove_template_id,
        "energy_curve_id": spec.energy_curve_id,
        "fx_wet_scale": spec.fx_wet_scale,
    }
    wav = render_wav(midi, sample_rate=spec.render.sample_rate, provenance=prov)

    if not args.quiet:
        ts = f"{spec.time_sig[0]}/{spec.time_sig[1]}"
        key_pc = "C C# D D# E F F# G G# A A# B".split()[spec.key_root]
        print(f"♪ {args.file} → {spec.provenance.mood} {spec.tempo_bpm:.0f} BPM "
              f"{key_pc} {spec.mode} {ts} ({len(spec.bars)} bars, "
              f"{spec.total_duration_seconds():.1f}s)",
              file=sys.stderr)

    if args.output or args.out:
        out = args.out or (args.file + ".soundhash.wav")
        Path(out).write_bytes(wav)
        if not args.quiet:
            print(f"  wrote {out}", file=sys.stderr)
        return 0

    # Play path: write to a temp file (some players want a real file).
    fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="mhash-")
    os.close(fd)
    try:
        Path(tmp).write_bytes(wav)
        from .play import play_wav
        return play_wav(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _ensure_fluidsynth() -> bool:
    if shutil.which("fluidsynth"):
        return True
    sysname = __import__("platform").system()
    hint = {
        "Darwin": "brew install fluid-synth",
        "Linux":  "sudo apt install fluidsynth   # or: sudo dnf install fluidsynth",
        "Windows": "scoop install fluidsynth   # or download from fluidsynth.org",
    }.get(sysname, "install fluidsynth from your package manager")
    print(f"mhash: fluidsynth not found on PATH. Install it:\n  {hint}",
          file=sys.stderr)
    return False


def _ensure_soundfont(quiet: bool = False) -> bool:
    """Auto-download MS-Basic.sf3 on first run if missing."""
    from .render.audio import _find_soundfont
    try:
        _find_soundfont()
        return True
    except RuntimeError:
        pass
    if not quiet:
        print("mhash: first run — downloading MS-Basic.sf3 (~50 MB) "
              "to assets/v1/sf2/", file=sys.stderr)
    from .setup_assets import main as setup_main
    rc = setup_main([])
    return rc == 0


if __name__ == "__main__":
    raise SystemExit(main())
