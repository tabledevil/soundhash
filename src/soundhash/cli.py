"""soundhash CLI — turn a file into a deterministic 30s audio signature."""
from __future__ import annotations

import argparse
import hashlib
import sys

from . import SPEC_VERSION, __version__
from .decode import hash_to_spec
from .mime import detect_mime


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="soundhash", description=__doc__)
    p.add_argument("file", help="file to hash")
    p.add_argument("--midi", action="store_true", help="emit a .mid file")
    p.add_argument("--audio", action="store_true",
                   help="emit a .wav file (requires fluidsynth on PATH)")
    p.add_argument("--mood", help="override mood (M0..M10)")
    p.add_argument("--mime", default="auto",
                   help="auto | off | strict | <mime/type>")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="dump the full SongSpec breakdown")
    p.add_argument("--version", action="version", version=__version__)
    args = p.parse_args(argv)

    with open(args.file, "rb") as f:
        digest = hashlib.sha256(f.read()).digest()

    if args.mime == "auto":
        mime = detect_mime(args.file)
    elif args.mime == "off":
        mime = None
    elif args.mime == "strict":
        mime = detect_mime(args.file)  # TODO: disable extension fallback
    else:
        mime = args.mime

    spec = hash_to_spec(digest, mime=mime, version=SPEC_VERSION)

    print(f"soundhash {__version__}  spec={spec.version}", file=sys.stderr)
    print(f"  hash    {digest.hex()}", file=sys.stderr)
    print(f"  mime    {mime}", file=sys.stderr)
    print(f"  mood    {spec.provenance.mood}", file=sys.stderr)
    print(f"  tempo   {spec.tempo_bpm:.2f} BPM", file=sys.stderr)
    print(f"  key     {spec.key_root} {spec.mode}", file=sys.stderr)
    print(f"  bars    {len(spec.bars)} ({spec.total_duration_seconds():.1f} s)",
          file=sys.stderr)
    print(f"  prog    {spec.form_id}", file=sys.stderr)

    if args.verbose:
        print("  chords  " + " | ".join(b.chord for b in spec.bars), file=sys.stderr)
        for l in spec.layers:
            extras = " ".join(f"{k}={v}" for k, v in l.extra.items()) if l.extra else ""
            print(f"  layer.{l.name:5s} ch{l.midi_channel:<2d} synth={l.synth_id:30s} "
                  f"pat={l.pattern_id:30s} {extras}", file=sys.stderr)

    if args.midi or args.audio:
        from .render.midi import render_midi
        midi_bytes = render_midi(spec)
        if args.midi:
            out_path = args.file + ".soundhash.mid"
            with open(out_path, "wb") as fh:
                fh.write(midi_bytes)
            print(f"  wrote   {out_path}", file=sys.stderr)
        if args.audio:
            from .render.audio import render_wav
            wav_path = args.file + ".soundhash.wav"
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
            }
            with open(wav_path, "wb") as fh:
                fh.write(render_wav(midi_bytes,
                                    sample_rate=spec.render.sample_rate,
                                    provenance=prov))
            print(f"  wrote   {wav_path}", file=sys.stderr)

    # TODO: render via render.midi / render.audio
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
