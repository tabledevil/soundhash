"""Build a per-mood showcase: one sample per mood, stitched into one WAV + index.

Usage:
    python -m mhash.showcase            # writes showcase/{showcase.wav,
                                            # showcase.md, M0_<seed>.wav, …}
    python -m mhash.showcase --moods M0 M5 M9   # subset

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
    "M3":  "font/ttf",
    "M4":  "audio/wav",
    "M5":  "application/json",
    "M6":  "text/html",
    "M7":  "application/x-executable",
    "M8":  "video/mp4",
    "M9":  "application/zip",
    "M10": "video/quicktime",
    "M11": "text/x-python",
    "M12": "image/jpeg",
    "M13": "application/x-pdf",
    "M14": "model/gltf+json",
}

ALL_MOODS = [f"M{i}" for i in range(15)]


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


def _spec_from_file_for_mood(file_path: str, mood: str):
    from .decode import hash_to_spec
    h = hashlib.sha256(open(file_path, "rb").read()).digest()
    return f"{Path(file_path).name}-{mood}", h, hash_to_spec(h, mood_override=mood)


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
    ap = argparse.ArgumentParser(prog="mhash.showcase")
    ap.add_argument("--moods", nargs="*", default=ALL_MOODS,
                    help="moods to include (default: all 11)")
    ap.add_argument("--out", default="showcase",
                    help="output directory")
    ap.add_argument("--gap", type=float, default=1.0,
                    help="silence between samples in stitched WAV")
    ap.add_argument("--score", action="store_true",
                    help="print quality score per sample")
    ap.add_argument("--file", metavar="PATH",
                    help="render this file in every requested mood (cross-mood demo)")
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
        if args.file:
            result = _spec_from_file_for_mood(args.file, mood)
        else:
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

    # Browser-friendly index: HTML with one <audio> per mood.
    html = _build_html(rendered)
    (out_dir / "showcase.html").write_text(html)
    print(f"index:    {out_dir / 'showcase.html'}", file=sys.stderr)

    return 0


def _build_html(rendered: list) -> str:
    rows = []
    for mood, _, info in rendered:
        rows.append(f"""<tr>
  <td><span class="mood">{mood}</span></td>
  <td>{info['form']}</td>
  <td>{info['tempo']:.0f} BPM</td>
  <td>{info['key']} {info['mode']}</td>
  <td>{info['groove']}</td>
  <td>{info['curve']}</td>
  <td>{info['bars']}</td>
  <td>{info['duration']:.1f}s</td>
  <td>{info['score']}</td>
  <td><audio controls preload="none" src="{info['name']}.wav"></audio></td>
</tr>""")
    table = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>mhash showcase</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #1d1f22; background: #f7f7f9; }}
  h1 {{ font-weight: 600; }}
  .stitched {{ margin: 1em 0 2em; padding: 1em; background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
  th, td {{ padding: 0.55em 0.75em; text-align: left; border-bottom: 1px solid #eee; font-size: 0.92em; }}
  th {{ background: #1d1f22; color: white; font-weight: 500; }}
  tr:last-child td {{ border-bottom: none; }}
  .mood {{ display: inline-block; padding: 0.18em 0.5em; background: #1d1f22; color: white; border-radius: 4px; font-family: ui-monospace, monospace; font-size: 0.86em; }}
  audio {{ width: 240px; height: 32px; }}
  footer {{ margin-top: 2em; color: #888; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>mhash showcase</h1>
<p>One representative sample per mood. Each row was generated from a different SHA-256, then forced into that mood by hash search. All renders go through the same 9-layer pipeline + per-mood FX chain + master EQ + LUFS normalisation.</p>

<div class="stitched">
  <strong>All-moods stitched</strong> (1 s gaps)
  <br>
  <audio controls preload="none" src="showcase.wav" style="width:100%; margin-top:0.5em;"></audio>
</div>

<table>
<thead>
<tr><th>mood</th><th>form</th><th>tempo</th><th>key</th><th>groove</th><th>curve</th><th>bars</th><th>duration</th><th>score</th><th>audio</th></tr>
</thead>
<tbody>
{table}
</tbody>
</table>

<footer>Generated by <code>python -m mhash.showcase</code>. See <code>showcase.md</code> for the same data in markdown.</footer>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
