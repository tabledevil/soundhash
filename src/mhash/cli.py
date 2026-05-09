"""mhash CLI — turn a file into a deterministic 30s audio signature."""
from __future__ import annotations

import argparse
import hashlib
import sys

from . import SPEC_VERSION, __version__
from .decode import hash_to_spec
from .mime import detect_mime


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mhash", description=__doc__)
    p.add_argument("file", nargs="?", help="file to hash (omit for --self-test)")
    p.add_argument("--midi", action="store_true", help="emit a .mid file")
    p.add_argument("--audio", action="store_true",
                   help="emit a .wav file (requires fluidsynth on PATH)")
    p.add_argument("--mp3", action="store_true",
                   help="also emit a .mp3 (requires lame on PATH)")
    p.add_argument("--flac", action="store_true",
                   help="also emit a .flac (requires flac on PATH)")
    p.add_argument("--sf", default=None, metavar="SF",
                   help="SoundFont override: a path to a .sf2/.sf3, or "
                        "'fluidr3' to auto-download FluidR3_GM.sf2 (~141 MB)")
    p.add_argument("--mood", help="override mood (M0..M10)")
    p.add_argument("--mime", default="auto",
                   help="auto | off | strict | <mime/type>")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="dump the full SongSpec breakdown")
    p.add_argument("--score", action="store_true",
                   help="after audio render, print a heuristic quality score")
    p.add_argument("--psy", action="store_true",
                   help="also print psychoacoustic score (Zwicker loudness, DIN sharpness; needs mosqito)")
    p.add_argument("--self-test", action="store_true",
                   help="render a fixed seed and compare its MIDI hash against a baseline; exits 0 on match, 1 on drift")
    p.add_argument("--version", action="version", version=__version__)
    args = p.parse_args(argv)

    if args.self_test:
        return _self_test()

    if args.sf:
        from .mhash import _resolve_sf_override
        sf_path = _resolve_sf_override(args.sf)
        if sf_path is None:
            return 4
        import os as _os
        _os.environ["SOUNDHASH_SOUNDFONT"] = str(sf_path)

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

    spec = hash_to_spec(digest, mime=mime, version=SPEC_VERSION,
                        mood_override=args.mood)

    print(f"mhash {__version__}  spec={spec.version}", file=sys.stderr)
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
            out_path = args.file + ".mhash.mid"
            with open(out_path, "wb") as fh:
                fh.write(midi_bytes)
            print(f"  wrote   {out_path}", file=sys.stderr)
        if args.audio:
            from .render.audio import render_wav
            wav_path = args.file + ".mhash.wav"
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
            wav_bytes = render_wav(midi_bytes,
                                   sample_rate=spec.render.sample_rate,
                                   provenance=prov)
            with open(wav_path, "wb") as fh:
                fh.write(wav_bytes)
            print(f"  wrote   {wav_path}", file=sys.stderr)
            if args.score:
                from .quality import score_wav
                print(f"  quality {score_wav(wav_bytes).summary()}", file=sys.stderr)
            if args.psy:
                from .quality import psychoacoustic_score, triage_score
                psy = psychoacoustic_score(wav_bytes)
                if psy is None:
                    print("  psy     unavailable (install mosqito)", file=sys.stderr)
                else:
                    print(f"  psy     {psy.summary()}", file=sys.stderr)
                tri = triage_score(wav_bytes)
                print(f"  {tri.summary()}", file=sys.stderr)
            if args.mp3:
                import shutil, subprocess
                if shutil.which("lame"):
                    mp3_path = args.file + ".mhash.mp3"
                    subprocess.run(["lame", "-q", "2", "-b", "192",
                                    "--silent", wav_path, mp3_path], check=True)
                    print(f"  wrote   {mp3_path}", file=sys.stderr)
                else:
                    print("  mp3     skipped (lame not on PATH)", file=sys.stderr)
            if args.flac:
                import shutil, subprocess
                if shutil.which("flac"):
                    flac_path = args.file + ".mhash.flac"
                    subprocess.run(["flac", "-f", "-s", "-o", flac_path, wav_path],
                                   check=True)
                    print(f"  wrote   {flac_path}", file=sys.stderr)
                else:
                    print("  flac    skipped (flac CLI not on PATH)", file=sys.stderr)

    # TODO: render via render.midi / render.audio
    return 0


_SELF_TEST_SEED = "soundhash-self-test-v1"
_SELF_TEST_MIME = "application/json"
_SELF_TEST_MIDI_SHA = "29a5a37f798d47fd6bdda78c3182a00efd94c13bee35dc270bd0c141c7eda563"


def _self_test() -> int:
    """Render a fixed seed and compare its MIDI hash to a baseline.

    Catches accidental output drift from refactors / dependency upgrades.
    Reports diff on mismatch but does not gate WAV output on platform-bound
    fluidsynth/SF2 paths.
    """
    import hashlib
    from .decode import hash_to_spec
    from .render.midi import render_midi
    h = hashlib.sha256(_SELF_TEST_SEED.encode()).digest()
    spec = hash_to_spec(h, mime=_SELF_TEST_MIME)
    midi = render_midi(spec)
    sha = hashlib.sha256(midi).hexdigest()
    ok = sha == _SELF_TEST_MIDI_SHA
    print(f"  seed     {_SELF_TEST_SEED}", file=sys.stderr)
    print(f"  spec     mood={spec.provenance.mood} tempo={spec.tempo_bpm:.2f} "
          f"key={spec.key_root} {spec.mode} form={spec.form_id}",
          file=sys.stderr)
    print(f"  midi_sha {sha}", file=sys.stderr)
    if ok:
        print("  PASS — output matches baseline", file=sys.stderr)
        return 0
    print(f"  expected {_SELF_TEST_MIDI_SHA}", file=sys.stderr)
    print("  FAIL — output drifted from the v0.0.1 baseline", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
