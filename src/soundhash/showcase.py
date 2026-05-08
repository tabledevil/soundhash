"""Build a per-mood showcase: one sample per mood, stitched into one WAV + index.

Usage:
    python -m soundhash.showcase            # writes showcase/{showcase.wav,
                                            # showcase.md, M0_<seed>.wav, …}
    python -m soundhash.showcase --moods M0 M5 M9   # subset

The showcase searches a deterministic seed pool until it finds a hash that
lands on each requested mood, then renders MIDI + WAV for each via the
normal render pipeline.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import sys
import wave
from pathlib import Path

import numpy as np


# Map mood → MIME family that biases toward it (not strictly required —
# the seed search will eventually hit any mood — but speeds up discovery).
_MIME_HINT = {
    "M0":  "image/png",
    "M1":  "application/pdf",
    "M2":  "audio/mp3",
    "M3":  "image/jpeg",
    "M4":  "audio/wav",
    "M5":  "text/plain",
    "M6":  "text/html",
    "M7":  "text/css",
    "M8":  "video/mp4",
    "M9":  "application/zip",
    "M10": "video/quicktime",       # video → trailer/cinematic candidate set
}

ALL_MOODS = [f"M{i}" for i in range(11)]


def _find_seed_for_mood(mood: str, max_tries: int = 5000):
    from .decode import hash_to_spec
    mime = _MIME_HINT.get(mood)
    for i in range(max_tries):
        seed = f"showcase-{mood}-{i}"
        h = hashlib.sha256(seed.encode()).digest()
        spec = hash_to_spec(h, mime=mime)
        if spec.provenance.mood == mood:
            return seed, h, spec
    return None


def _render_one(seed: str, h: bytes, spec, out_dir: Path):
    from .render.midi import render_midi
    from .render.audio import render_wav
    midi = render_midi(spec)
    prov = {
        "hash_hex": spec.provenance.hash_hex, "mood": spec.provenance.mood,
        "mode": spec.mode, "key_root": spec.key_root,
        "tempo_bpm": f"{spec.tempo_bpm:.2f}", "form_id": spec.form_id,
        "bars": len(spec.bars),
        "groove_template_id": spec.groove_template_id,
        "energy_curve_id": spec.energy_curve_id,
    }
    wav = render_wav(midi, sample_rate=spec.render.sample_rate, provenance=prov)
    name = f"{spec.provenance.mood}_{seed}".replace("/", "_")
    (out_dir / f"{name}.mid").write_bytes(midi)
    (out_dir / f"{name}.wav").write_bytes(wav)
    return name, wav


def _stitch(wavs: list[bytes], gap_seconds: float = 1.0) -> bytes:
    """Concatenate 16-bit stereo WAVs with `gap_seconds` of silence between."""
    out_segments: list[np.ndarray] = []
    rate = 44100
    n_channels = 2
    for i, b in enumerate(wavs):
        with wave.open(io.BytesIO(b), "rb") as r:
            rate = r.getframerate()
            n_channels = r.getnchannels()
            raw = r.readframes(r.getnframes())
        seg = np.frombuffer(raw, dtype="<i2").reshape(-1, n_channels)
        out_segments.append(seg)
        if i != len(wavs) - 1:
            gap = np.zeros((int(rate * gap_seconds), n_channels), dtype="<i2")
            out_segments.append(gap)
    full = np.concatenate(out_segments, axis=0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(n_channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(full.tobytes())
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="soundhash.showcase")
    ap.add_argument("--moods", nargs="*", default=ALL_MOODS,
                    help="moods to include (default: all 11)")
    ap.add_argument("--out", default="showcase",
                    help="output directory")
    ap.add_argument("--gap", type=float, default=1.0,
                    help="silence between samples in stitched WAV")
    ap.add_argument("--score", action="store_true",
                    help="print quality score per sample")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rendered: list[tuple[str, bytes, dict]] = []
    md_lines = ["# Soundhash showcase", ""]
    md_lines.append("| Mood | Form | Tempo | Key | Groove | Curve | Bars | Sec | Score |")
    md_lines.append("|------|------|-------|-----|--------|-------|------|-----|-------|")

    if args.score:
        from .quality import score_wav

    for mood in args.moods:
        result = _find_seed_for_mood(mood)
        if result is None:
            print(f"  {mood}: no hash found in 1000 tries", file=sys.stderr)
            continue
        seed, h, spec = result
        name, wav = _render_one(seed, h, spec, out_dir)
        score_str = ""
        if args.score:
            sc = score_wav(wav)
            score_str = f"{sc.overall:.2f}"
        rendered.append((mood, wav, {
            "name": name, "form": spec.form_id, "tempo": spec.tempo_bpm,
            "key": spec.key_root, "mode": spec.mode,
            "groove": spec.groove_template_id, "curve": spec.energy_curve_id,
            "bars": len(spec.bars), "duration": spec.total_duration_seconds(),
            "score": score_str,
        }))
        print(f"  {mood}: {name}.wav  form={spec.form_id} tempo={spec.tempo_bpm:.0f} "
              f"key={spec.key_root} {spec.mode}  bars={len(spec.bars)} {score_str}",
              file=sys.stderr)

    # Markdown index.
    for mood, _, info in rendered:
        md_lines.append(f"| {mood} | {info['form']} | {info['tempo']:.1f} | "
                        f"{info['key']} {info['mode']} | {info['groove']} | "
                        f"{info['curve']} | {info['bars']} | "
                        f"{info['duration']:.1f}s | {info['score']} |")
        md_lines.append("")
    md_lines.append("")
    md_lines.append("## Files")
    for mood, _, info in rendered:
        md_lines.append(f"- `{info['name']}.wav` — {mood}")
    (out_dir / "showcase.md").write_text("\n".join(md_lines) + "\n")

    if len(rendered) >= 2:
        stitched = _stitch([r[1] for r in rendered], gap_seconds=args.gap)
        (out_dir / "showcase.wav").write_bytes(stitched)
        print(f"\nstitched: {out_dir / 'showcase.wav'}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
