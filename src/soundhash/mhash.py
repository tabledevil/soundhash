"""`mhash` — quick-play CLI for the deterministic musical hash.

Usage:
    mhash <file>              # render and play
    mhash -                   # read from stdin (also auto-detected via pipe)
    cat foo | mhash           # ditto
    mhash -o <file>           # write <file>.soundhash.wav, no playback
    mhash --out PATH <file>   # write to a specific path, no playback
    mhash -c 4 <file>         # split into 4-MB chunks, play one song per chunk
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
    try:
        return _main(argv)
    except KeyboardInterrupt:
        # Clear any in-progress progress-bar line and print a tidy exit.
        sys.stderr.write("\r" + " " * 80 + "\r")
        sys.stderr.flush()
        print("mhash: interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:
        # `mhash foo | head` and friends: don't whine, just exit.
        try:
            sys.stderr.close()
        except Exception:
            pass
        return 0


def _main(argv: list[str] | None) -> int:
    p = argparse.ArgumentParser(
        prog="mhash",
        description="Play (or save) a file's deterministic musical hash.")
    p.add_argument("file", nargs="?", default=None,
                   help="file to hash (use '-' or pipe via stdin to read stdin)")
    p.add_argument("-o", "--output", action="store_true",
                   help="write <file>.soundhash.wav next to the input and exit "
                        "without playing")
    p.add_argument("--out", default=None, metavar="PATH",
                   help="like -o but write to a specific path")
    p.add_argument("-c", "--chunk", type=float, default=None, metavar="MB",
                   help="split input into MB-sized chunks; play one song per "
                        "chunk in order")
    p.add_argument("--sf", default=None, metavar="SF",
                   help="SoundFont override: a path to a .sf2/.sf3, or "
                        "'fluidr3' to auto-download FluidR3_GM.sf2 "
                        "(~141 MB) and use it for this run")
    p.add_argument("--mood", help="override mood (M0..M14)")
    p.add_argument("--mime", default="auto",
                   help="auto | off | <mime/type> (mime auto-detected from "
                        "filename if not given)")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="suppress dashboard + progress output")
    p.add_argument("--no-show", action="store_true",
                   help="skip the styled dashboard but keep progress bar")
    args = p.parse_args(argv)

    if not _ensure_fluidsynth():
        return 2
    if args.sf:
        sf_path = _resolve_sf_override(args.sf, quiet=args.quiet)
        if sf_path is None:
            return 4
        os.environ["SOUNDHASH_SOUNDFONT"] = str(sf_path)
    if not _ensure_soundfont(quiet=args.quiet):
        return 3

    # Resolve input source ---------------------------------------------------
    stdin_mode = (args.file in (None, "-")
                  and not (sys.stdin.isatty() if args.file is None else False))
    if args.file in (None, "-"):
        # Either explicit '-' or no file given. If stdin is a tty AND no file,
        # that's a usage error.
        if args.file is None and sys.stdin.isatty():
            p.error("no input: pass a file or pipe data into stdin")
        try:
            data = sys.stdin.buffer.read()
        except KeyboardInterrupt:
            return 130
        source_label = "<stdin>"
    else:
        try:
            with open(args.file, "rb") as f:
                data = f.read()
        except OSError as e:
            print(f"mhash: {e}", file=sys.stderr)
            return 1
        source_label = args.file

    if not data:
        print("mhash: empty input", file=sys.stderr)
        return 1

    # Chunk mode: hash + render + play one song per chunk -------------------
    if args.chunk is not None and args.chunk > 0:
        chunk_bytes = max(1, int(args.chunk * 1_000_000))
        n_chunks = (len(data) + chunk_bytes - 1) // chunk_bytes
        if not args.quiet:
            print(f"  chunk mode: {len(data)/1e6:.2f} MB → {n_chunks} chunk(s) "
                  f"of ≤{args.chunk:.2f} MB each", file=sys.stderr)
        rc = 0
        for i in range(n_chunks):
            piece = data[i*chunk_bytes : (i+1)*chunk_bytes]
            label = f"{source_label}#chunk{i+1}/{n_chunks} ({len(piece)/1e6:.2f} MB)"
            rc |= _render_one(piece, label, args, mime_for_naming=args.file)
            if rc:
                break
        return rc

    return _render_one(data, source_label, args, mime_for_naming=args.file)


def _render_one(data: bytes, source_label: str, args, mime_for_naming) -> int:
    from .decode import hash_to_spec
    from .mime import detect_mime
    from .render.audio import render_wav
    from .render.midi import render_midi
    from .dashboard import Progress, print_dashboard, print_render_stats
    import time as _time
    _t0 = _time.monotonic()
    from . import SPEC_VERSION

    show = not (args.quiet or args.no_show)

    progress = Progress(["hash", "decode", "midi", "fluidsynth", "fx+lufs", "ready"]) \
        if not args.quiet else None

    def step(name: str):
        if progress:
            progress.begin(name)
        return name

    step("hash")
    digest = hashlib.sha256(data).digest()
    if progress: progress.end("hash")

    step("decode")
    if args.mime == "auto":
        mime = detect_mime(mime_for_naming) if mime_for_naming and mime_for_naming != "-" else None
    elif args.mime == "off":
        mime = None
    else:
        mime = args.mime
    spec = hash_to_spec(digest, mime=mime, version=SPEC_VERSION,
                        mood_override=args.mood)
    if progress: progress.end("decode")

    if progress:
        progress.finish()

    if show:
        print_dashboard(spec, source_label=source_label, mime=mime)

    step("midi")
    midi = render_midi(spec)
    if progress: progress.end("midi")

    step("fluidsynth")
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
    if progress:
        progress.end("fluidsynth")
        progress.end("fx+lufs")  # render_wav already applies fx+lufs
        progress.end("ready")
        progress.finish()

    if show:
        print_render_stats(spec, midi, wav, _time.monotonic() - _t0)

    if args.output or args.out:
        # Default output path uses source filename if available, else uses
        # the hash hex (stdin / chunk mode).
        if args.out:
            out = args.out
        elif args.file and args.file != "-":
            base = args.file
            if "#chunk" in source_label:
                # In chunk mode write a numbered file per chunk.
                idx = source_label.split("#chunk", 1)[1].split("/", 1)[0]
                base = f"{args.file}.chunk{idx}"
            out = base + ".soundhash.wav"
        else:
            out = f"{spec.provenance.hash_hex[:12]}.soundhash.wav"
        Path(out).write_bytes(wav)
        if not args.quiet:
            print(f"  wrote {out}", file=sys.stderr)
        return 0

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


def _resolve_sf_override(sf: str, quiet: bool = False) -> Path | None:
    """Map --sf <value> → an absolute SoundFont path."""
    if sf.lower() in ("fluidr3", "fluidr3_gm", "fluid"):
        from .setup_assets import _TARGET_DIR, _FLUIDR3_NAME, fetch_fluidr3
        target = _TARGET_DIR / _FLUIDR3_NAME
        if not target.exists():
            if not quiet:
                print(f"mhash: --sf fluidr3 → downloading {_FLUIDR3_NAME} (~141 MB)…",
                      file=sys.stderr)
            try:
                fetch_fluidr3()
            except Exception as e:
                print(f"mhash: FluidR3 download failed: {e}", file=sys.stderr)
                return None
        return target
    p = Path(sf).expanduser()
    if not p.is_file():
        print(f"mhash: --sf {sf} not found", file=sys.stderr)
        return None
    return p.resolve()


def _ensure_soundfont(quiet: bool = False) -> bool:
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
