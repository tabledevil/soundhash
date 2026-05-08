OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/tabledevil/projects/soundhash
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019e0846-9b9b-78f3-905c-7bf9e679ea9c
--------
user
# SOUND-DESIGN ADVERSARIAL REVIEW: soundhash

## Project context
soundhash deterministically maps a SHA-256 hash to a 30-second piece of generative music. Synthesis: fluidsynth 2.5.4 with MS Basic SF3 (a stock GM soundfont, MuseScore's basic), no internal reverb (disabled to keep determinism). Per-mood pedalboard FX chain applied post-synth. After FX, LUFS normalize to -16, then 8x oversampled true-peak limiter at -1.5 dBFS. There are 15 moods (M0..M14) — palette below only shows M0..M10. Each mood has 5 layers: bass / comp / lead / pad / counter, each picking a GM program from a small tuple of candidates by `byte % len`.

## Tooling
- pedalboard 0.9.22, pyloudnorm 0.2.0, scipy 1.16.2
- soundfont: MS Basic.sf3 51 MB GM-compatible
- output: 48 kHz wav, then mp3/flac via lame/ffmpeg

## Critique brief (please answer these specifically)
1. Which mood FX chains will sound thin / muddy / cliché given the chain ordering and parameters?
2. Bad GM picks in `_GM_PALETTE`? Specifically: is Square Lead 80 vs Calliope 82 vs Saw Lead 81 a defensible spread? Are the pad picks (88/89/90/91/94/95) overused?
3. Is the master EQ over- or under-correcting? Any frequency masking or buildup risks?
4. MS Basic SF3 has well-known timbral ceilings — what should be compensated for in FX?
5. The single FX trick that would most improve the output spectrum?

Be ruthless. Cite specific moods, plugins, parameters, GM program numbers. Output as a markdown critique with sections matching the 5 questions plus a "Top fixes ranked" section.

---

## SOURCE: src/soundhash/render/fx.py and src/soundhash/render/audio.py
"""Per-mood post-render FX chains (reverb / delay / chorus / EQ).

Applied after LUFS normalisation but before the final peak limiter so the
limiter still owns the true-peak ceiling. Determinism is best-effort:
pedalboard's algorithms are not bit-identical across builds, but with
pinned `pedalboard==0.9.x` the output is stable on a given host.

The chains are intentionally subtle. A soundhash is meant to be musical,
not a synthwave demo reel — heavy modulation would obscure distinguishability.
"""
from __future__ import annotations

import io
import wave

import numpy as np


# Per-mood FX recipe. Each entry is a list of (effect_name, kwargs) pairs.
# Effect names map to pedalboard plugin classes.
_MOOD_FX: dict[str, list[tuple[str, dict]]] = {
    # M0 Ambient — long plate reverb + light chorus + low-shelf cut.
    "M0":  [("Reverb",       {"room_size": 0.85, "damping": 0.4, "wet_level": 0.40, "dry_level": 0.70, "width": 1.0}),
            ("Chorus",       {"rate_hz": 0.6, "depth": 0.35, "centre_delay_ms": 12, "feedback": 0.05, "mix": 0.25}),
            ("LowShelfFilter", {"cutoff_frequency_hz": 110, "gain_db": -1.0, "q": 0.7})],
    # M1 Ballad — medium hall, warm low end.
    "M1":  [("Reverb",       {"room_size": 0.70, "damping": 0.5, "wet_level": 0.28, "dry_level": 0.78, "width": 0.9}),
            ("LowShelfFilter", {"cutoff_frequency_hz": 200, "gain_db": +1.5, "q": 0.7}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 8000, "gain_db": +1.0, "q": 0.7})],
    # M2 Hip-hop / Boom-bap — short room + tape-style high cut + light analog warmth.
    "M2":  [("Reverb",       {"room_size": 0.30, "damping": 0.7, "wet_level": 0.18, "dry_level": 0.85, "width": 0.7}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": -2.0, "q": 0.7}),
            ("Distortion",   {"drive_db": 4.0})],
    # M3 Downtempo — wide chorus + slow delay + warm.
    "M3":  [("Chorus",       {"rate_hz": 0.7, "depth": 0.45, "centre_delay_ms": 18, "feedback": 0.10, "mix": 0.30}),
            ("Delay",        {"delay_seconds": 0.375, "feedback": 0.18, "mix": 0.18}),
            ("Reverb",       {"room_size": 0.55, "damping": 0.55, "wet_level": 0.22, "dry_level": 0.80, "width": 0.95})],
    # M4 Latin — light room, slight high-shelf brightness.
    "M4":  [("Reverb",       {"room_size": 0.35, "damping": 0.4, "wet_level": 0.18, "dry_level": 0.85, "width": 0.85}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": +1.5, "q": 0.7})],
    # M5 Synthwave — short plate + ducked dotted-eighth delay + chorus on synths.
    "M5":  [("Chorus",       {"rate_hz": 1.1, "depth": 0.25, "centre_delay_ms": 8, "feedback": 0.05, "mix": 0.20}),
            ("Delay",        {"delay_seconds": 0.214, "feedback": 0.30, "mix": 0.16}),
            ("Reverb",       {"room_size": 0.45, "damping": 0.4, "wet_level": 0.24, "dry_level": 0.82, "width": 1.0})],
    # M6 House — tight ambience + sidechain-feel low pump (use compressor).
    "M6":  [("Reverb",       {"room_size": 0.30, "damping": 0.5, "wet_level": 0.18, "dry_level": 0.85, "width": 0.9}),
            ("Compressor",   {"threshold_db": -16.0, "ratio": 3.0, "attack_ms": 8, "release_ms": 80})],
    # M7 Techno — tight, slightly dark, light delay.
    "M7":  [("Delay",        {"delay_seconds": 0.1875, "feedback": 0.18, "mix": 0.12}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 9000, "gain_db": -1.5, "q": 0.7}),
            ("Reverb",       {"room_size": 0.25, "damping": 0.6, "wet_level": 0.14, "dry_level": 0.88, "width": 0.85})],
    # M8 DnB — tight, snappy, no big space.
    "M8":  [("Compressor",   {"threshold_db": -14.0, "ratio": 2.5, "attack_ms": 5, "release_ms": 60}),
            ("Reverb",       {"room_size": 0.20, "damping": 0.6, "wet_level": 0.10, "dry_level": 0.92, "width": 0.85})],
    # M9 Glitch / IDM — phaser + ping-pong delay + small room.
    "M9":  [("Phaser",       {"rate_hz": 0.4, "depth": 0.40, "centre_frequency_hz": 1300, "feedback": 0.20, "mix": 0.30}),
            ("Delay",        {"delay_seconds": 0.143, "feedback": 0.25, "mix": 0.20}),
            ("Reverb",       {"room_size": 0.30, "damping": 0.4, "wet_level": 0.15, "dry_level": 0.88, "width": 1.0})],
    # M10 Cinematic — large hall, gentle high-shelf air.
    "M10": [("Reverb",       {"room_size": 0.90, "damping": 0.35, "wet_level": 0.45, "dry_level": 0.65, "width": 1.0}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 9000, "gain_db": +2.0, "q": 0.7}),
            ("LowShelfFilter", {"cutoff_frequency_hz": 90, "gain_db": +1.0, "q": 0.7})],
    # M11 Lofi — vinyl warmth: tape saturation, mid-room reverb, top-end roll-off, slow chorus wow-wobble.
    "M11": [("Distortion",   {"drive_db": 6.0}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 5500, "gain_db": -3.0, "q": 0.7}),
            ("Chorus",       {"rate_hz": 0.4, "depth": 0.30, "centre_delay_ms": 22, "feedback": 0.10, "mix": 0.25}),
            ("Reverb",       {"room_size": 0.40, "damping": 0.7, "wet_level": 0.22, "dry_level": 0.82, "width": 0.85})],
    # M12 Chillout — wide chorus, plate reverb, presence boost, dotted-eighth delay.
    "M12": [("Chorus",       {"rate_hz": 0.5, "depth": 0.40, "centre_delay_ms": 18, "feedback": 0.10, "mix": 0.30}),
            ("Delay",        {"delay_seconds": 0.450, "feedback": 0.20, "mix": 0.18}),
            ("Reverb",       {"room_size": 0.65, "damping": 0.5, "wet_level": 0.32, "dry_level": 0.75, "width": 0.95}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": +1.0, "q": 0.7})],
    # M13 Simple — barely-there room reverb. Lets the silence breathe.
    "M13": [("Reverb",       {"room_size": 0.20, "damping": 0.5, "wet_level": 0.10, "dry_level": 0.92, "width": 0.85})],
    # M14 Gameboy — chiptune: light drive, bit-crush-ish high-shelf cut, no reverb (DMG had none).
    "M14": [("HighShelfFilter", {"cutoff_frequency_hz": 8000, "gain_db": -4.0, "q": 0.7}),
            ("Distortion",   {"drive_db": 2.0}),
            ("Reverb",       {"room_size": 0.10, "damping": 0.4, "wet_level": 0.04, "dry_level": 0.96, "width": 0.6})],
}


def apply_fx(samples: np.ndarray, sample_rate: int, mood: str) -> np.ndarray:
    """Apply the mood's FX chain + master bus. samples: (n, 2) float32 in [-1, 1].

    Chain order: mood-specific plugins → master bus (HPF + low-shelf cut +
    presence shelf). The master bus is mood-independent and corrects the
    GM-soundfont's tendency to dominate the low band.
    """
    try:
        from pedalboard import (
            Pedalboard, Reverb, Delay, Chorus, Phaser, Compressor, Distortion,
            LowShelfFilter, HighShelfFilter, HighpassFilter,
        )
    except ImportError:
        return samples

    cls_map = {
        "Reverb": Reverb, "Delay": Delay, "Chorus": Chorus, "Phaser": Phaser,
        "Compressor": Compressor, "Distortion": Distortion,
        "LowShelfFilter": LowShelfFilter, "HighShelfFilter": HighShelfFilter,
        "HighpassFilter": HighpassFilter,
    }
    plugins = []
    for name, kwargs in (_MOOD_FX.get(mood) or []):
        cls = cls_map.get(name)
        if cls is None:
            continue
        plugins.append(cls(**kwargs))

    # Master bus: applied to every mood. Tames sub rumble and lifts presence
    # so spectral balance moves toward the target 25/45/30 distribution.
    plugins.extend([
        HighpassFilter(cutoff_frequency_hz=40),
        LowShelfFilter(cutoff_frequency_hz=110, gain_db=-1.5, q=0.7),
        HighShelfFilter(cutoff_frequency_hz=4500, gain_db=+1.5, q=0.7),
    ])

    board = Pedalboard(plugins)
    return board(samples.astype(np.float32), sample_rate)
"""MIDI → WAV via the fluidsynth CLI, with length cap + cosine fades.

Pinned flags per DESIGN.md §7 determinism contract: cpu-cores=1, no internal
reverb/chorus. Output is normalised to ≤30 s with a 200 ms cosine fade-out
(and a 5 ms fade-in to kill the start-click).

Stage-2 will move to in-process pyfluidsynth + ship a CC0 SoundFont.
"""
from __future__ import annotations

import io
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


# Output length + loudness contract (DESIGN.md §3, dim 14):
MAX_SECONDS = 30.0
FADE_IN_MS = 5
FADE_OUT_MS = 200
TARGET_LUFS = -16.0
PEAK_CEILING_DBFS = -1.5     # peak ceiling (linear-domain limiter, not true-peak)
MAX_GAIN_DB = 24.0           # safety cap on the loudness-correction gain


# Default soundfont — bundled with `brew install fluidsynth` on macOS.
# 307 KB Vintage-Dreams-Waves; sounds appropriate for M5 synthwave-ish output
# but is far from full GM. Override via SOUNDHASH_SOUNDFONT env var.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_SF2 = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "assets", "v1", "sf2"))
_DEFAULT_SF2_CANDIDATES = [
    os.path.join(_REPO_SF2, "MS-Basic.sf3"),
    "/usr/local/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    # last resort: brew's tiny pad-only synth font (no drums)
    "/opt/homebrew/Cellar/fluid-synth/2.5.4/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2",
]


def _find_soundfont() -> str:
    sf = os.environ.get("SOUNDHASH_SOUNDFONT")
    if sf and os.path.isfile(sf):
        return sf
    for p in _DEFAULT_SF2_CANDIDATES:
        if os.path.isfile(p):
            return p
    raise RuntimeError(
        "No SoundFont found. Set SOUNDHASH_SOUNDFONT=/path/to.sf2 "
        "or install fluid-synth via Homebrew."
    )


def render_wav(midi_bytes: bytes, sample_rate: int = 44100,
               provenance: dict | None = None,
               apply_fx: bool = True) -> bytes:
    """Run fluidsynth on the MIDI, return the WAV bytes (with optional metadata)."""
    if shutil.which("fluidsynth") is None:
        raise RuntimeError("fluidsynth CLI not found on PATH")
    sf2 = _find_soundfont()

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        mid_path = td / "in.mid"
        wav_path = td / "out.wav"
        mid_path.write_bytes(midi_bytes)
        cmd = [
            "fluidsynth", "-ni",
            "-F", str(wav_path),
            "-r", str(sample_rate),
            "-o", "synth.cpu-cores=1",
            "-o", "synth.reverb.active=no",
            "-o", "synth.chorus.active=no",
            sf2,
            str(mid_path),
        ]
        # Inherit a controlled locale for cross-platform-stable text parsing.
        env = {**os.environ, "LC_ALL": "C"}
        proc = subprocess.run(cmd, capture_output=True, env=env, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"fluidsynth exited {proc.returncode}: {proc.stderr.decode(errors='replace')[:400]}"
            )
        wav = _postprocess_wav(wav_path.read_bytes(),
                               mood=(provenance or {}).get("mood") if apply_fx else None)
        if provenance:
            wav = _embed_wav_provenance(wav, provenance)
        return wav


def _embed_wav_provenance(wav_bytes: bytes, prov: dict) -> bytes:
    """Insert a RIFF LIST/INFO chunk carrying provenance after `fmt `.

    Sub-chunks (4-byte IDs) used:
        ISFT  software identifier
        ICMT  free-form comment with full provenance
        ICOP  copyright / license
    """
    if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        return wav_bytes  # not a WAV; bail.

    # Build INFO sub-chunks.
    def _info(tag: bytes, text: str) -> bytes:
        data = text.encode("utf-8") + b"\x00"
        if len(data) % 2:
            data += b"\x00"
        return tag + struct.pack("<I", len(data)) + data

    sw = "soundhash/v1"
    comment = (
        f"soundhash/v1 sha={prov.get('hash_hex','?')[:64]} "
        f"mood={prov.get('mood','?')} mode={prov.get('mode','?')} "
        f"key={prov.get('key_root','?')} tempo={prov.get('tempo_bpm','?')} "
        f"form={prov.get('form_id','?')} bars={prov.get('bars','?')} "
        f"groove={prov.get('groove_template_id','?')} "
        f"curve={prov.get('energy_curve_id','?')}"
    )
    info_payload = b"INFO" + _info(b"ISFT", sw) + _info(b"ICMT", comment) \
                            + _info(b"ICOP", "deterministic — see DESIGN.md")
    list_chunk = b"LIST" + struct.pack("<I", len(info_payload)) + info_payload

    # Walk existing chunks and insert LIST right after `fmt `.
    out = bytearray()
    out += wav_bytes[:12]                      # RIFF<size>WAVE; size patched at end
    pos = 12
    inserted = False
    while pos + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[pos:pos + 4]
        chunk_size = struct.unpack("<I", wav_bytes[pos + 4:pos + 8])[0]
        chunk_total = 8 + chunk_size + (chunk_size & 1)
        out += wav_bytes[pos:pos + chunk_total]
        pos += chunk_total
        if not inserted and chunk_id == b"fmt ":
            out += list_chunk
            inserted = True

    if not inserted:
        # No fmt chunk found — append before EOF as safe fallback.
        out += list_chunk

    # Patch RIFF size (= total length of out minus 8 bytes for "RIFF"+size).
    new_size = len(out) - 8
    out[4:8] = struct.pack("<I", new_size)
    return bytes(out)


def _postprocess_wav(wav_bytes: bytes, mood: str | None = None) -> bytes:
    """Cap length, apply fades, LUFS-norm, mood FX chain, peak-limit."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as r:
        n_channels = r.getnchannels()
        sample_width = r.getsampwidth()
        rate = r.getframerate()
        n_frames = r.getnframes()
        raw = r.readframes(n_frames)
    if sample_width != 2:
        return wav_bytes  # only handle 16-bit for now

    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    samples = samples.reshape(-1, n_channels)

    # 1. Length cap.
    max_frames = int(MAX_SECONDS * rate)
    if len(samples) > max_frames:
        samples = samples[:max_frames]
    n = len(samples)

    # 2. Per-mood FX chain FIRST. Reverb/delay/distortion change the
    # integrated loudness, so the LUFS pass must come after the FX
    # otherwise the "-16 LUFS" target is wrong by however much the FX
    # added/removed.
    if mood:
        try:
            from .fx import apply_fx
            samples = apply_fx(samples, rate, mood)
        except Exception:
            pass

    # 3. LUFS normalisation (only if there's enough audio for the gating window).
    samples = _normalise_loudness(samples, rate)

    # 4. Cosine fades.
    fi = max(1, int(FADE_IN_MS * rate / 1000))
    fo = max(1, int(FADE_OUT_MS * rate / 1000))
    if n >= fi:
        ramp = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, fi, dtype=np.float32)))
        samples[:fi] *= ramp[:, None]
    if n >= fo:
        ramp = 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, fo, dtype=np.float32)))
        samples[-fo:] *= ramp[:, None]

    # 5. Peak limiter at PEAK_CEILING_DBFS (linear-domain; deterministic).
    ceiling = 10 ** (PEAK_CEILING_DBFS / 20.0)
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak > ceiling:
        samples *= ceiling / peak

    # Quantise back to int16.
    out_int = np.clip(samples * 32768.0, -32768, 32767).astype("<i2")

    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(n_channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(out_int.tobytes())
    return out.getvalue()


def _normalise_loudness(samples: np.ndarray, rate: int) -> np.ndarray:
    """Apply gain so integrated LUFS approaches TARGET_LUFS. Deterministic.

    pyloudnorm uses ITU-R BS.1770 with a 400 ms window — needs ≥0.4 s of audio.
    """
    try:
        import pyloudnorm
    except ImportError:
        return samples
    if len(samples) < int(0.5 * rate):
        return samples
    meter = pyloudnorm.Meter(rate)        # default block_size=0.4 s
    try:
        loudness = meter.integrated_loudness(samples)
    except Exception:
        return samples
    if not np.isfinite(loudness):
        return samples
    gain_db = TARGET_LUFS - loudness
    gain_db = max(-MAX_GAIN_DB, min(MAX_GAIN_DB, gain_db))
    gain = 10 ** (gain_db / 20.0)
    return samples * gain


## SOURCE: _GM_PALETTE excerpt from src/soundhash/decode.py

# ---------------------------------------------------------------------------
# Mood-keyed GM program palettes (placeholder until synth_pool.json is wired).
# Each tuple gives candidates for that role; byte % len picks one.
# ---------------------------------------------------------------------------

# (gm_program, name) — stick to widely-supported GM patches so MS Basic / GeneralUser cover them.
_GM_PALETTE: dict[str, dict[str, tuple[int, ...]]] = {
    "M0":  {"bass": (32,),               "comp": (88, 89, 91),       "lead": (54, 75, 73),   "pad": (88, 89, 94),    "counter": (52, 73, 91)},   # Ambient
    "M1":  {"bass": (32, 33),            "comp": (0, 4, 24),         "lead": (73, 71, 56),   "pad": (89, 91, 95),    "counter": (40, 41, 73)},
    "M2":  {"bass": (33, 34, 36),        "comp": (4, 5, 11),         "lead": (80, 81, 28),   "pad": (89, 95, 91),    "counter": (4, 5, 11)},
    "M3":  {"bass": (33, 36),            "comp": (4, 5, 88, 89),     "lead": (80, 73, 78),   "pad": (89, 91, 94),    "counter": (52, 91, 73)},
    "M4":  {"bass": (32, 35),            "comp": (24, 25, 32),       "lead": (56, 11, 24),   "pad": (89, 91, 94),    "counter": (60, 56, 73)},
    "M5":  {"bass": (38, 39, 33),        "comp": (81, 89, 80),       "lead": (81, 80, 84),   "pad": (90, 89, 94),    "counter": (82, 81, 84)},
    "M6":  {"bass": (38, 39, 36),        "comp": (16, 17, 81),       "lead": (80, 81, 53),   "pad": (90, 89, 95),    "counter": (54, 80, 81)},
    "M7":  {"bass": (38, 39),            "comp": (81, 89, 90),       "lead": (80, 81, 87),   "pad": (90, 94, 89),    "counter": (87, 80, 81)},
    "M8":  {"bass": (38, 39, 87),        "comp": (89, 88, 91),       "lead": (81, 80, 87),   "pad": (89, 91, 94),    "counter": (54, 81, 91)},
    "M9":  {"bass": (38, 39, 87),        "comp": (90, 91, 102),      "lead": (88, 81, 102),  "pad": (95, 91, 94),    "counter": (102, 88, 91)},
    "M10": {"bass": (32, 43, 44),        "comp": (48, 49, 50, 89),   "lead": (60, 73, 71),   "pad": (49, 51, 94),    "counter": (49, 73, 71)},  # strings/choir
}



codex
Reviewing the FX and palette sources first so the critique is anchored to the actual chain order, gain staging, and GM assignments rather than generic production advice.
exec
/bin/zsh -lc "sed -n '1,260p' src/soundhash/render/fx.py" in /Users/tabledevil/projects/soundhash
exec
/bin/zsh -lc "sed -n '1,260p' src/soundhash/decode.py" in /Users/tabledevil/projects/soundhash
exec
/bin/zsh -lc "sed -n '1,320p' src/soundhash/render/audio.py" in /Users/tabledevil/projects/soundhash
 succeeded in 0ms:
"""Per-mood post-render FX chains (reverb / delay / chorus / EQ).

Applied after LUFS normalisation but before the final peak limiter so the
limiter still owns the true-peak ceiling. Determinism is best-effort:
pedalboard's algorithms are not bit-identical across builds, but with
pinned `pedalboard==0.9.x` the output is stable on a given host.

The chains are intentionally subtle. A soundhash is meant to be musical,
not a synthwave demo reel — heavy modulation would obscure distinguishability.
"""
from __future__ import annotations

import io
import wave

import numpy as np


# Per-mood FX recipe. Each entry is a list of (effect_name, kwargs) pairs.
# Effect names map to pedalboard plugin classes.
_MOOD_FX: dict[str, list[tuple[str, dict]]] = {
    # M0 Ambient — long plate reverb + light chorus + low-shelf cut.
    "M0":  [("Reverb",       {"room_size": 0.85, "damping": 0.4, "wet_level": 0.40, "dry_level": 0.70, "width": 1.0}),
            ("Chorus",       {"rate_hz": 0.6, "depth": 0.35, "centre_delay_ms": 12, "feedback": 0.05, "mix": 0.25}),
            ("LowShelfFilter", {"cutoff_frequency_hz": 110, "gain_db": -1.0, "q": 0.7})],
    # M1 Ballad — medium hall, warm low end.
    "M1":  [("Reverb",       {"room_size": 0.70, "damping": 0.5, "wet_level": 0.28, "dry_level": 0.78, "width": 0.9}),
            ("LowShelfFilter", {"cutoff_frequency_hz": 200, "gain_db": +1.5, "q": 0.7}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 8000, "gain_db": +1.0, "q": 0.7})],
    # M2 Hip-hop / Boom-bap — short room + tape-style high cut + light analog warmth.
    "M2":  [("Reverb",       {"room_size": 0.30, "damping": 0.7, "wet_level": 0.18, "dry_level": 0.85, "width": 0.7}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": -2.0, "q": 0.7}),
            ("Distortion",   {"drive_db": 4.0})],
    # M3 Downtempo — wide chorus + slow delay + warm.
    "M3":  [("Chorus",       {"rate_hz": 0.7, "depth": 0.45, "centre_delay_ms": 18, "feedback": 0.10, "mix": 0.30}),
            ("Delay",        {"delay_seconds": 0.375, "feedback": 0.18, "mix": 0.18}),
            ("Reverb",       {"room_size": 0.55, "damping": 0.55, "wet_level": 0.22, "dry_level": 0.80, "width": 0.95})],
    # M4 Latin — light room, slight high-shelf brightness.
    "M4":  [("Reverb",       {"room_size": 0.35, "damping": 0.4, "wet_level": 0.18, "dry_level": 0.85, "width": 0.85}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": +1.5, "q": 0.7})],
    # M5 Synthwave — short plate + ducked dotted-eighth delay + chorus on synths.
    "M5":  [("Chorus",       {"rate_hz": 1.1, "depth": 0.25, "centre_delay_ms": 8, "feedback": 0.05, "mix": 0.20}),
            ("Delay",        {"delay_seconds": 0.214, "feedback": 0.30, "mix": 0.16}),
            ("Reverb",       {"room_size": 0.45, "damping": 0.4, "wet_level": 0.24, "dry_level": 0.82, "width": 1.0})],
    # M6 House — tight ambience + sidechain-feel low pump (use compressor).
    "M6":  [("Reverb",       {"room_size": 0.30, "damping": 0.5, "wet_level": 0.18, "dry_level": 0.85, "width": 0.9}),
            ("Compressor",   {"threshold_db": -16.0, "ratio": 3.0, "attack_ms": 8, "release_ms": 80})],
    # M7 Techno — tight, slightly dark, light delay.
    "M7":  [("Delay",        {"delay_seconds": 0.1875, "feedback": 0.18, "mix": 0.12}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 9000, "gain_db": -1.5, "q": 0.7}),
            ("Reverb",       {"room_size": 0.25, "damping": 0.6, "wet_level": 0.14, "dry_level": 0.88, "width": 0.85})],
    # M8 DnB — tight, snappy, no big space.
    "M8":  [("Compressor",   {"threshold_db": -14.0, "ratio": 2.5, "attack_ms": 5, "release_ms": 60}),
            ("Reverb",       {"room_size": 0.20, "damping": 0.6, "wet_level": 0.10, "dry_level": 0.92, "width": 0.85})],
    # M9 Glitch / IDM — phaser + ping-pong delay + small room.
    "M9":  [("Phaser",       {"rate_hz": 0.4, "depth": 0.40, "centre_frequency_hz": 1300, "feedback": 0.20, "mix": 0.30}),
            ("Delay",        {"delay_seconds": 0.143, "feedback": 0.25, "mix": 0.20}),
            ("Reverb",       {"room_size": 0.30, "damping": 0.4, "wet_level": 0.15, "dry_level": 0.88, "width": 1.0})],
    # M10 Cinematic — large hall, gentle high-shelf air.
    "M10": [("Reverb",       {"room_size": 0.90, "damping": 0.35, "wet_level": 0.45, "dry_level": 0.65, "width": 1.0}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 9000, "gain_db": +2.0, "q": 0.7}),
            ("LowShelfFilter", {"cutoff_frequency_hz": 90, "gain_db": +1.0, "q": 0.7})],
    # M11 Lofi — vinyl warmth: tape saturation, mid-room reverb, top-end roll-off, slow chorus wow-wobble.
    "M11": [("Distortion",   {"drive_db": 6.0}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 5500, "gain_db": -3.0, "q": 0.7}),
            ("Chorus",       {"rate_hz": 0.4, "depth": 0.30, "centre_delay_ms": 22, "feedback": 0.10, "mix": 0.25}),
            ("Reverb",       {"room_size": 0.40, "damping": 0.7, "wet_level": 0.22, "dry_level": 0.82, "width": 0.85})],
    # M12 Chillout — wide chorus, plate reverb, presence boost, dotted-eighth delay.
    "M12": [("Chorus",       {"rate_hz": 0.5, "depth": 0.40, "centre_delay_ms": 18, "feedback": 0.10, "mix": 0.30}),
            ("Delay",        {"delay_seconds": 0.450, "feedback": 0.20, "mix": 0.18}),
            ("Reverb",       {"room_size": 0.65, "damping": 0.5, "wet_level": 0.32, "dry_level": 0.75, "width": 0.95}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": +1.0, "q": 0.7})],
    # M13 Simple — barely-there room reverb. Lets the silence breathe.
    "M13": [("Reverb",       {"room_size": 0.20, "damping": 0.5, "wet_level": 0.10, "dry_level": 0.92, "width": 0.85})],
    # M14 Gameboy — chiptune: light drive, bit-crush-ish high-shelf cut, no reverb (DMG had none).
    "M14": [("HighShelfFilter", {"cutoff_frequency_hz": 8000, "gain_db": -4.0, "q": 0.7}),
            ("Distortion",   {"drive_db": 2.0}),
            ("Reverb",       {"room_size": 0.10, "damping": 0.4, "wet_level": 0.04, "dry_level": 0.96, "width": 0.6})],
}


def apply_fx(samples: np.ndarray, sample_rate: int, mood: str) -> np.ndarray:
    """Apply the mood's FX chain + master bus. samples: (n, 2) float32 in [-1, 1].

    Chain order: mood-specific plugins → master bus (HPF + low-shelf cut +
    presence shelf). The master bus is mood-independent and corrects the
    GM-soundfont's tendency to dominate the low band.
    """
    try:
        from pedalboard import (
            Pedalboard, Reverb, Delay, Chorus, Phaser, Compressor, Distortion,
            LowShelfFilter, HighShelfFilter, HighpassFilter,
        )
    except ImportError:
        return samples

    cls_map = {
        "Reverb": Reverb, "Delay": Delay, "Chorus": Chorus, "Phaser": Phaser,
        "Compressor": Compressor, "Distortion": Distortion,
        "LowShelfFilter": LowShelfFilter, "HighShelfFilter": HighShelfFilter,
        "HighpassFilter": HighpassFilter,
    }
    plugins = []
    for name, kwargs in (_MOOD_FX.get(mood) or []):
        cls = cls_map.get(name)
        if cls is None:
            continue
        plugins.append(cls(**kwargs))

    # Master bus: applied to every mood. Tames sub rumble and lifts presence
    # so spectral balance moves toward the target 25/45/30 distribution.
    plugins.extend([
        HighpassFilter(cutoff_frequency_hz=40),
        LowShelfFilter(cutoff_frequency_hz=110, gain_db=-1.5, q=0.7),
        HighShelfFilter(cutoff_frequency_hz=4500, gain_db=+1.5, q=0.7),
    ])

    board = Pedalboard(plugins)
    return board(samples.astype(np.float32), sample_rate)

 succeeded in 0ms:
"""Decode a SHA-256 (and optional MIME) into a SongSpec.

Pure function. No I/O after table preload, no system clock, no system random.
All entropy comes from HKDF-Expand of the input hash.

Current scope: produces a fully populated macro SongSpec — mood, tempo, key,
mode, progression resolved to per-bar chord roots and PC sets — for any input.
The melody/bass/drum note generation lives downstream and is not yet wired.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from . import tables, theory
from .spec import (
    Bar,
    LayerSpec,
    Provenance,
    RenderHints,
    SongSpec,
)


# ---------------------------------------------------------------------------
# HKDF (RFC 5869) over SHA-256
# ---------------------------------------------------------------------------

_SALT = b"soundhash-v1"


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    out, t, counter = b"", b"", 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        out += t
        counter += 1
    return out[:length]


class HashStream:
    """Domain-separated entropy stream derived from the input hash."""

    __slots__ = ("_prk", "_version")

    def __init__(self, prk: bytes, version: str = "v1"):
        self._prk = prk
        self._version = version

    def take(self, label: str, n: int) -> bytes:
        info = f"soundhash/{self._version}/{label}".encode("ascii")
        return _hkdf_expand(self._prk, info, n)

    def pick(self, label: str, table):
        b = self.take(label, 1)[0]
        return table[b % len(table)]


# ---------------------------------------------------------------------------
# Selection helpers — each one applies the constraint propagation principle
# ---------------------------------------------------------------------------


def _pick_mood(macro: bytes, mime_family: str | None) -> str:
    """Byte 0 selects mood within a MIME-family-filtered candidate list.

    With mime=None we expose all 11 moods.
    """
    f2m = tables.load("family_to_moods")
    if mime_family and mime_family in f2m["mapping"]:
        candidates = f2m["mapping"][mime_family]["candidates"]
    else:
        candidates = list(f2m["moods"].keys())
    return candidates[macro[0] % len(candidates)]


def _pick_tempo(byte: int, mood: str) -> float:
    pools = tables.load("tempo_pools")["pools"]
    pool = pools[mood]["bpm"]
    base = pool[(byte & 0x07) % len(pool)]
    # 5 high bits drive a ±0.5% nudge to retain entropy without changing perceived BPM.
    nudge = ((byte >> 3) - 16) / 16.0 * 0.005      # in [-0.005, +0.00469]
    return round(base * (1.0 + nudge), 3)


def _pick_mode(byte: int, mood: str) -> str:
    moods = tables.load("moods")["moods"]
    mood_modes = moods[mood]["modes"]
    return mood_modes[byte % len(mood_modes)]


_MOOD_GROOVE_POOL: dict[str, tuple[str, ...]] = {
    "M0":  ("ambient_drift", "neo_soul", "straight_4_4"),
    "M1":  ("straight_4_4", "neo_soul", "gospel_12_8"),
    "M2":  ("boom_bap_60", "dilla_feel", "mpc60_swing"),
    "M3":  ("neo_soul", "mpc60_swing", "dilla_feel", "straight_4_4"),
    "M4":  ("latin_clave_pocket", "dembow_pocket", "mpc60_swing"),
    "M5":  ("synthwave_tight", "straight_4_4"),
    "M6":  ("house_pocket", "amapiano_pocket", "straight_4_4"),
    "M7":  ("techno_push", "straight_4_4"),
    "M8":  ("dnb_amen_lean", "straight_4_4"),
    "M9":  ("trap_triplet_hat", "straight_4_4"),
    "M10": ("straight_4_4", "gospel_12_8", "ambient_drift"),
    "M11": ("dilla_feel", "boom_bap_60", "mpc60_swing", "neo_soul"),    # lofi swing
    "M12": ("ambient_drift", "neo_soul", "straight_4_4"),               # chillout flow
    "M13": ("straight_4_4",),                                            # simple = on the grid
    "M14": ("straight_4_4",),                                            # gameboy = rigid
}


def _pick_groove_template(byte: int, mood: str) -> str:
    pool = _MOOD_GROOVE_POOL.get(mood, ("straight_4_4",))
    try:
        templates = tables.load("groove_templates")["templates"]
    except FileNotFoundError:
        return pool[0]
    available = {t["id"] for t in templates}
    pool = tuple(p for p in pool if p in available) or ("straight_4_4",)
    return pool[byte % len(pool)]


def _expand_form_layout(form: dict, n_bars: int) -> list[str]:
    """Turn `[[letter, bar_count_or_'N'], ...]` into a per-bar section-letter list of length n_bars."""
    layout = form.get("layout") or [["A", "N"]]
    fixed = [(letter, count) for letter, count in layout if count != "N"]
    fixed_total = sum(c for _, c in fixed)
    n_remaining = max(0, n_bars - fixed_total)
    n_natural = sum(1 for _, c in layout if c == "N") or 1
    natural_share, extra = divmod(n_remaining, n_natural)

    out: list[str] = []
    for letter, count in layout:
        if count == "N":
            share = natural_share + (1 if extra > 0 else 0)
            extra = max(0, extra - 1)
            out.extend([letter] * share)
        else:
            out.extend([letter] * count)
    # Truncate / pad to exactly n_bars.
    out = out[:n_bars]
    while len(out) < n_bars:
        out.append(out[-1] if out else "A")
    return out


def _pick_form(byte: int, n_bars: int) -> dict:
    forms = tables.load("forms")["forms"]
    eligible = [f for f in forms if f.get("min_bars", 1) <= n_bars <= f.get("max_bars", 99)]
    if not eligible:
        eligible = forms
    eligible.sort(key=lambda f: f.get("id", 0))
    return eligible[byte % len(eligible)]


# Per-mood form-id preferences. Empty intersection with the 30-s-fit set
# falls back to the unfiltered list. IDs reference forms.json:
#   0 through_composed,  1 A_Aprime,  2 AB_simple,  3 AAB,  4 ABA,
#   5 ABAB,  6 intro_A_fill_A_out,  7 A_build_drop_A,  8 theme_var,
#   9 call_response,  10 intro_A,  11 A_outro,  12 AB_with_fill,
#   13 AABA,  14 ABCA,  15 breakdown_form,  16 riser_drop_loop,
#   17 ostinato_layer,  18 two_arches,  19 late_drop,  20 plateau_fall,
#   21 pyramid,  22 medley,  23 pulse_only.
_MOOD_FORM_PREF: dict[str, tuple[int, ...]] = {
    "M0":  (0, 1, 8, 17, 23),                # ambient: through-composed / ostinato / pulse
    "M1":  (1, 4, 6, 11, 13, 18),            # ballad: A_Aprime, ABA, AABA, two_arches
    "M2":  (2, 5, 8, 13, 14),                # hip-hop: AB / ABAB / theme_var / AABA / ABCA
    "M3":  (0, 1, 8, 17, 18),                # downtempo
    "M4":  (5, 13, 14, 8),                   # latin: ABAB / AABA / ABCA / theme_var
    "M5":  (5, 7, 13, 14, 19),               # synthwave: ABAB / build_drop / late_drop
    "M6":  (5, 14, 15, 19, 16),              # house
    "M7":  (15, 16, 19, 21, 23),             # techno
    "M8":  (5, 7, 16, 19),                   # dnb
    "M9":  (8, 18, 21, 22),                  # glitch
    "M10": (4, 6, 13, 14, 18, 20),           # cinematic
    "M11": (1, 4, 8, 17, 13),                # lofi: A_Aprime / ABA / theme_var / ostinato_layer / AABA
    "M12": (0, 1, 4, 8, 17, 18, 23),         # chillout: through_composed / A_Aprime / ABA / theme_var
    "M13": (1, 4, 13, 23),                   # simple: A_Aprime / ABA / AABA / pulse_only
    "M14": (5, 13, 14, 4, 21),               # gameboy: ABAB / AABA / ABCA / ABA / pyramid
}


def _pick_form_unconstrained(byte: int, max_bars: int, mood: str = "") -> dict:
    """Pick a form whose min_bars fits within max_bars (the 30-second cap),
    biased toward mood-preferred forms when possible."""
    forms = tables.load("forms")["forms"]
    fits = [f for f in forms if f.get("min_bars", 1) <= max_bars]
    if not fits:
        fits = forms
    pref = set(_MOOD_FORM_PREF.get(mood, ()))
    eligible = [f for f in fits if f.get("id") in pref] if pref else []
    if not eligible:
        eligible = fits
    eligible.sort(key=lambda f: f.get("id", 0))
    return eligible[byte % len(eligible)]


def _bars_from_layout(form: dict, default_n: int = 8, cap: int = 99) -> int:
    """Sum fixed counts in form.layout; allocate `default_n` to any 'N' filler.

    Result clamped to [form.min_bars, form.max_bars] then to `cap`.
    """
    layout = form.get("layout") or [["A", "N"]]
    fixed = sum(c for _, c in layout if c != "N")
    n_natural = sum(1 for _, c in layout if c == "N")
    total = fixed + n_natural * max(2, default_n // max(1, len(layout)))
    if not fixed and not n_natural:
        total = default_n
    lo = form.get("min_bars", 1)
    hi = min(cap, form.get("max_bars", cap))
    return max(lo, min(hi, total))


# Per-mood curve-id preferences (intersected with form.allowed_curves).
# IDs: 0 flat_low, 1 flat_mid, 2 flat_high, 3 rise, 4 fall, 5 arc, 6 U,
# 7 two_arches, 8 late_drop, 9 early_drop, 10 plateau_fall,
# 11 slow_build_cliff, 12 sawtooth_2, 13 terraces, 14 breath, 15 reverse_arc.
_MOOD_CURVE_PREF: dict[str, tuple[int, ...]] = {
    "M0":  (0, 1, 6, 14, 15),
    "M1":  (5, 7, 14, 10),
    "M2":  (1, 13, 7),
    "M3":  (5, 14, 13),
    "M4":  (5, 13, 7, 3),
    "M5":  (3, 5, 8, 11),
    "M6":  (3, 13, 8, 11, 5),
    "M7":  (3, 11, 8, 13),
    "M8":  (8, 11, 7),
    "M9":  (12, 7, 13, 4),
    "M10": (5, 11, 7, 14, 15),
    "M11": (1, 14, 5, 13, 6),                # lofi — flat-mid w/ breath, gentle arc, U
    "M12": (1, 14, 6, 5, 15),                # chillout — flat, breath, U
    "M13": (0, 1, 14, 6),                    # simple — flat low/mid, breath
    "M14": (3, 5, 7, 13),                    # gameboy — rise, arc, two_arches, terraces
}


def _pick_energy_curve(byte: int, form: dict, mood: str = "") -> dict:
    curves = tables.load("energy_curves")["curves"]
    allowed_ids = set(form.get("allowed_curves") or [c["id"] for c in curves])
    pref_ids = set(_MOOD_CURVE_PREF.get(mood, ())) & allowed_ids
    chosen_ids = pref_ids if pref_ids else allowed_ids
    eligible = [c for c in curves if c.get("id") in chosen_ids] or curves
    eligible.sort(key=lambda c: c.get("id", 0))
    return eligible[byte % len(eligible)]


def _sample_energy_curve(curve: dict, fraction: float) -> float:
    """Linear interpolation over the curve's `points: [[fraction, energy], ...]`."""
    pts = curve.get("points") or [[0.0, 0.5], [1.0, 0.5]]
    if fraction <= pts[0][0]:
        return float(pts[0][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if fraction <= x1:
            if x1 == x0:
                return float(y1)
            t = (fraction - x0) / (x1 - x0)

 succeeded in 0ms:
"""MIDI → WAV via the fluidsynth CLI, with length cap + cosine fades.

Pinned flags per DESIGN.md §7 determinism contract: cpu-cores=1, no internal
reverb/chorus. Output is normalised to ≤30 s with a 200 ms cosine fade-out
(and a 5 ms fade-in to kill the start-click).

Stage-2 will move to in-process pyfluidsynth + ship a CC0 SoundFont.
"""
from __future__ import annotations

import io
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


# Output length + loudness contract (DESIGN.md §3, dim 14):
MAX_SECONDS = 30.0
FADE_IN_MS = 5
FADE_OUT_MS = 200
TARGET_LUFS = -16.0
PEAK_CEILING_DBFS = -1.5     # peak ceiling (linear-domain limiter, not true-peak)
MAX_GAIN_DB = 24.0           # safety cap on the loudness-correction gain


# Default soundfont — bundled with `brew install fluidsynth` on macOS.
# 307 KB Vintage-Dreams-Waves; sounds appropriate for M5 synthwave-ish output
# but is far from full GM. Override via SOUNDHASH_SOUNDFONT env var.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_SF2 = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "assets", "v1", "sf2"))
_DEFAULT_SF2_CANDIDATES = [
    os.path.join(_REPO_SF2, "MS-Basic.sf3"),
    "/usr/local/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    # last resort: brew's tiny pad-only synth font (no drums)
    "/opt/homebrew/Cellar/fluid-synth/2.5.4/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2",
]


def _find_soundfont() -> str:
    sf = os.environ.get("SOUNDHASH_SOUNDFONT")
    if sf and os.path.isfile(sf):
        return sf
    for p in _DEFAULT_SF2_CANDIDATES:
        if os.path.isfile(p):
            return p
    raise RuntimeError(
        "No SoundFont found. Set SOUNDHASH_SOUNDFONT=/path/to.sf2 "
        "or install fluid-synth via Homebrew."
    )


def render_wav(midi_bytes: bytes, sample_rate: int = 44100,
               provenance: dict | None = None,
               apply_fx: bool = True) -> bytes:
    """Run fluidsynth on the MIDI, return the WAV bytes (with optional metadata)."""
    if shutil.which("fluidsynth") is None:
        raise RuntimeError("fluidsynth CLI not found on PATH")
    sf2 = _find_soundfont()

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        mid_path = td / "in.mid"
        wav_path = td / "out.wav"
        mid_path.write_bytes(midi_bytes)
        cmd = [
            "fluidsynth", "-ni",
            "-F", str(wav_path),
            "-r", str(sample_rate),
            "-o", "synth.cpu-cores=1",
            "-o", "synth.reverb.active=no",
            "-o", "synth.chorus.active=no",
            sf2,
            str(mid_path),
        ]
        # Inherit a controlled locale for cross-platform-stable text parsing.
        env = {**os.environ, "LC_ALL": "C"}
        proc = subprocess.run(cmd, capture_output=True, env=env, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"fluidsynth exited {proc.returncode}: {proc.stderr.decode(errors='replace')[:400]}"
            )
        wav = _postprocess_wav(wav_path.read_bytes(),
                               mood=(provenance or {}).get("mood") if apply_fx else None)
        if provenance:
            wav = _embed_wav_provenance(wav, provenance)
        return wav


def _embed_wav_provenance(wav_bytes: bytes, prov: dict) -> bytes:
    """Insert a RIFF LIST/INFO chunk carrying provenance after `fmt `.

    Sub-chunks (4-byte IDs) used:
        ISFT  software identifier
        ICMT  free-form comment with full provenance
        ICOP  copyright / license
    """
    if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        return wav_bytes  # not a WAV; bail.

    # Build INFO sub-chunks.
    def _info(tag: bytes, text: str) -> bytes:
        data = text.encode("utf-8") + b"\x00"
        if len(data) % 2:
            data += b"\x00"
        return tag + struct.pack("<I", len(data)) + data

    sw = "soundhash/v1"
    comment = (
        f"soundhash/v1 sha={prov.get('hash_hex','?')[:64]} "
        f"mood={prov.get('mood','?')} mode={prov.get('mode','?')} "
        f"key={prov.get('key_root','?')} tempo={prov.get('tempo_bpm','?')} "
        f"form={prov.get('form_id','?')} bars={prov.get('bars','?')} "
        f"groove={prov.get('groove_template_id','?')} "
        f"curve={prov.get('energy_curve_id','?')}"
    )
    info_payload = b"INFO" + _info(b"ISFT", sw) + _info(b"ICMT", comment) \
                            + _info(b"ICOP", "deterministic — see DESIGN.md")
    list_chunk = b"LIST" + struct.pack("<I", len(info_payload)) + info_payload

    # Walk existing chunks and insert LIST right after `fmt `.
    out = bytearray()
    out += wav_bytes[:12]                      # RIFF<size>WAVE; size patched at end
    pos = 12
    inserted = False
    while pos + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[pos:pos + 4]
        chunk_size = struct.unpack("<I", wav_bytes[pos + 4:pos + 8])[0]
        chunk_total = 8 + chunk_size + (chunk_size & 1)
        out += wav_bytes[pos:pos + chunk_total]
        pos += chunk_total
        if not inserted and chunk_id == b"fmt ":
            out += list_chunk
            inserted = True

    if not inserted:
        # No fmt chunk found — append before EOF as safe fallback.
        out += list_chunk

    # Patch RIFF size (= total length of out minus 8 bytes for "RIFF"+size).
    new_size = len(out) - 8
    out[4:8] = struct.pack("<I", new_size)
    return bytes(out)


def _postprocess_wav(wav_bytes: bytes, mood: str | None = None) -> bytes:
    """Cap length, apply fades, LUFS-norm, mood FX chain, peak-limit."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as r:
        n_channels = r.getnchannels()
        sample_width = r.getsampwidth()
        rate = r.getframerate()
        n_frames = r.getnframes()
        raw = r.readframes(n_frames)
    if sample_width != 2:
        return wav_bytes  # only handle 16-bit for now

    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    samples = samples.reshape(-1, n_channels)

    # 1. Length cap.
    max_frames = int(MAX_SECONDS * rate)
    if len(samples) > max_frames:
        samples = samples[:max_frames]
    n = len(samples)

    # 2. Per-mood FX chain FIRST. Reverb/delay/distortion change the
    # integrated loudness, so the LUFS pass must come after the FX
    # otherwise the "-16 LUFS" target is wrong by however much the FX
    # added/removed.
    if mood:
        try:
            from .fx import apply_fx
            samples = apply_fx(samples, rate, mood)
        except Exception:
            pass

    # 3. LUFS normalisation (only if there's enough audio for the gating window).
    samples = _normalise_loudness(samples, rate)

    # 4. Cosine fades.
    fi = max(1, int(FADE_IN_MS * rate / 1000))
    fo = max(1, int(FADE_OUT_MS * rate / 1000))
    if n >= fi:
        ramp = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, fi, dtype=np.float32)))
        samples[:fi] *= ramp[:, None]
    if n >= fo:
        ramp = 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, fo, dtype=np.float32)))
        samples[-fo:] *= ramp[:, None]

    # 5. Peak limiter at PEAK_CEILING_DBFS (linear-domain; deterministic).
    ceiling = 10 ** (PEAK_CEILING_DBFS / 20.0)
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak > ceiling:
        samples *= ceiling / peak

    # Quantise back to int16.
    out_int = np.clip(samples * 32768.0, -32768, 32767).astype("<i2")

    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(n_channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(out_int.tobytes())
    return out.getvalue()


def _normalise_loudness(samples: np.ndarray, rate: int) -> np.ndarray:
    """Apply gain so integrated LUFS approaches TARGET_LUFS. Deterministic.

    pyloudnorm uses ITU-R BS.1770 with a 400 ms window — needs ≥0.4 s of audio.
    """
    try:
        import pyloudnorm
    except ImportError:
        return samples
    if len(samples) < int(0.5 * rate):
        return samples
    meter = pyloudnorm.Meter(rate)        # default block_size=0.4 s
    try:
        loudness = meter.integrated_loudness(samples)
    except Exception:
        return samples
    if not np.isfinite(loudness):
        return samples
    gain_db = TARGET_LUFS - loudness
    gain_db = max(-MAX_GAIN_DB, min(MAX_GAIN_DB, gain_db))
    gain = 10 ** (gain_db / 20.0)
    return samples * gain

codex
I have the chain definitions and the actual render order. One important implementation detail already stands out: the top-level `fx.py` docstring says FX happen after LUFS, but `_postprocess_wav()` actually applies mood FX before loudness normalization, which changes how the chains read in practice.
exec
/bin/zsh -lc "nl -ba src/soundhash/render/fx.py | sed -n '1,220p'" in /Users/tabledevil/projects/soundhash
 succeeded in 0ms:
     1	"""Per-mood post-render FX chains (reverb / delay / chorus / EQ).
     2	
     3	Applied after LUFS normalisation but before the final peak limiter so the
     4	limiter still owns the true-peak ceiling. Determinism is best-effort:
     5	pedalboard's algorithms are not bit-identical across builds, but with
     6	pinned `pedalboard==0.9.x` the output is stable on a given host.
     7	
     8	The chains are intentionally subtle. A soundhash is meant to be musical,
     9	not a synthwave demo reel — heavy modulation would obscure distinguishability.
    10	"""
    11	from __future__ import annotations
    12	
    13	import io
    14	import wave
    15	
    16	import numpy as np
    17	
    18	
    19	# Per-mood FX recipe. Each entry is a list of (effect_name, kwargs) pairs.
    20	# Effect names map to pedalboard plugin classes.
    21	_MOOD_FX: dict[str, list[tuple[str, dict]]] = {
    22	    # M0 Ambient — long plate reverb + light chorus + low-shelf cut.
    23	    "M0":  [("Reverb",       {"room_size": 0.85, "damping": 0.4, "wet_level": 0.40, "dry_level": 0.70, "width": 1.0}),
    24	            ("Chorus",       {"rate_hz": 0.6, "depth": 0.35, "centre_delay_ms": 12, "feedback": 0.05, "mix": 0.25}),
    25	            ("LowShelfFilter", {"cutoff_frequency_hz": 110, "gain_db": -1.0, "q": 0.7})],
    26	    # M1 Ballad — medium hall, warm low end.
    27	    "M1":  [("Reverb",       {"room_size": 0.70, "damping": 0.5, "wet_level": 0.28, "dry_level": 0.78, "width": 0.9}),
    28	            ("LowShelfFilter", {"cutoff_frequency_hz": 200, "gain_db": +1.5, "q": 0.7}),
    29	            ("HighShelfFilter", {"cutoff_frequency_hz": 8000, "gain_db": +1.0, "q": 0.7})],
    30	    # M2 Hip-hop / Boom-bap — short room + tape-style high cut + light analog warmth.
    31	    "M2":  [("Reverb",       {"room_size": 0.30, "damping": 0.7, "wet_level": 0.18, "dry_level": 0.85, "width": 0.7}),
    32	            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": -2.0, "q": 0.7}),
    33	            ("Distortion",   {"drive_db": 4.0})],
    34	    # M3 Downtempo — wide chorus + slow delay + warm.
    35	    "M3":  [("Chorus",       {"rate_hz": 0.7, "depth": 0.45, "centre_delay_ms": 18, "feedback": 0.10, "mix": 0.30}),
    36	            ("Delay",        {"delay_seconds": 0.375, "feedback": 0.18, "mix": 0.18}),
    37	            ("Reverb",       {"room_size": 0.55, "damping": 0.55, "wet_level": 0.22, "dry_level": 0.80, "width": 0.95})],
    38	    # M4 Latin — light room, slight high-shelf brightness.
    39	    "M4":  [("Reverb",       {"room_size": 0.35, "damping": 0.4, "wet_level": 0.18, "dry_level": 0.85, "width": 0.85}),
    40	            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": +1.5, "q": 0.7})],
    41	    # M5 Synthwave — short plate + ducked dotted-eighth delay + chorus on synths.
    42	    "M5":  [("Chorus",       {"rate_hz": 1.1, "depth": 0.25, "centre_delay_ms": 8, "feedback": 0.05, "mix": 0.20}),
    43	            ("Delay",        {"delay_seconds": 0.214, "feedback": 0.30, "mix": 0.16}),
    44	            ("Reverb",       {"room_size": 0.45, "damping": 0.4, "wet_level": 0.24, "dry_level": 0.82, "width": 1.0})],
    45	    # M6 House — tight ambience + sidechain-feel low pump (use compressor).
    46	    "M6":  [("Reverb",       {"room_size": 0.30, "damping": 0.5, "wet_level": 0.18, "dry_level": 0.85, "width": 0.9}),
    47	            ("Compressor",   {"threshold_db": -16.0, "ratio": 3.0, "attack_ms": 8, "release_ms": 80})],
    48	    # M7 Techno — tight, slightly dark, light delay.
    49	    "M7":  [("Delay",        {"delay_seconds": 0.1875, "feedback": 0.18, "mix": 0.12}),
    50	            ("HighShelfFilter", {"cutoff_frequency_hz": 9000, "gain_db": -1.5, "q": 0.7}),
    51	            ("Reverb",       {"room_size": 0.25, "damping": 0.6, "wet_level": 0.14, "dry_level": 0.88, "width": 0.85})],
    52	    # M8 DnB — tight, snappy, no big space.
    53	    "M8":  [("Compressor",   {"threshold_db": -14.0, "ratio": 2.5, "attack_ms": 5, "release_ms": 60}),
    54	            ("Reverb",       {"room_size": 0.20, "damping": 0.6, "wet_level": 0.10, "dry_level": 0.92, "width": 0.85})],
    55	    # M9 Glitch / IDM — phaser + ping-pong delay + small room.
    56	    "M9":  [("Phaser",       {"rate_hz": 0.4, "depth": 0.40, "centre_frequency_hz": 1300, "feedback": 0.20, "mix": 0.30}),
    57	            ("Delay",        {"delay_seconds": 0.143, "feedback": 0.25, "mix": 0.20}),
    58	            ("Reverb",       {"room_size": 0.30, "damping": 0.4, "wet_level": 0.15, "dry_level": 0.88, "width": 1.0})],
    59	    # M10 Cinematic — large hall, gentle high-shelf air.
    60	    "M10": [("Reverb",       {"room_size": 0.90, "damping": 0.35, "wet_level": 0.45, "dry_level": 0.65, "width": 1.0}),
    61	            ("HighShelfFilter", {"cutoff_frequency_hz": 9000, "gain_db": +2.0, "q": 0.7}),
    62	            ("LowShelfFilter", {"cutoff_frequency_hz": 90, "gain_db": +1.0, "q": 0.7})],
    63	    # M11 Lofi — vinyl warmth: tape saturation, mid-room reverb, top-end roll-off, slow chorus wow-wobble.
    64	    "M11": [("Distortion",   {"drive_db": 6.0}),
    65	            ("HighShelfFilter", {"cutoff_frequency_hz": 5500, "gain_db": -3.0, "q": 0.7}),
    66	            ("Chorus",       {"rate_hz": 0.4, "depth": 0.30, "centre_delay_ms": 22, "feedback": 0.10, "mix": 0.25}),
    67	            ("Reverb",       {"room_size": 0.40, "damping": 0.7, "wet_level": 0.22, "dry_level": 0.82, "width": 0.85})],
    68	    # M12 Chillout — wide chorus, plate reverb, presence boost, dotted-eighth delay.
    69	    "M12": [("Chorus",       {"rate_hz": 0.5, "depth": 0.40, "centre_delay_ms": 18, "feedback": 0.10, "mix": 0.30}),
    70	            ("Delay",        {"delay_seconds": 0.450, "feedback": 0.20, "mix": 0.18}),
    71	            ("Reverb",       {"room_size": 0.65, "damping": 0.5, "wet_level": 0.32, "dry_level": 0.75, "width": 0.95}),
    72	            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": +1.0, "q": 0.7})],
    73	    # M13 Simple — barely-there room reverb. Lets the silence breathe.
    74	    "M13": [("Reverb",       {"room_size": 0.20, "damping": 0.5, "wet_level": 0.10, "dry_level": 0.92, "width": 0.85})],
    75	    # M14 Gameboy — chiptune: light drive, bit-crush-ish high-shelf cut, no reverb (DMG had none).
    76	    "M14": [("HighShelfFilter", {"cutoff_frequency_hz": 8000, "gain_db": -4.0, "q": 0.7}),
    77	            ("Distortion",   {"drive_db": 2.0}),
    78	            ("Reverb",       {"room_size": 0.10, "damping": 0.4, "wet_level": 0.04, "dry_level": 0.96, "width": 0.6})],
    79	}
    80	
    81	
    82	def apply_fx(samples: np.ndarray, sample_rate: int, mood: str) -> np.ndarray:
    83	    """Apply the mood's FX chain + master bus. samples: (n, 2) float32 in [-1, 1].
    84	
    85	    Chain order: mood-specific plugins → master bus (HPF + low-shelf cut +
    86	    presence shelf). The master bus is mood-independent and corrects the
    87	    GM-soundfont's tendency to dominate the low band.
    88	    """
    89	    try:
    90	        from pedalboard import (
    91	            Pedalboard, Reverb, Delay, Chorus, Phaser, Compressor, Distortion,
    92	            LowShelfFilter, HighShelfFilter, HighpassFilter,
    93	        )
    94	    except ImportError:
    95	        return samples
    96	
    97	    cls_map = {
    98	        "Reverb": Reverb, "Delay": Delay, "Chorus": Chorus, "Phaser": Phaser,
    99	        "Compressor": Compressor, "Distortion": Distortion,
   100	        "LowShelfFilter": LowShelfFilter, "HighShelfFilter": HighShelfFilter,
   101	        "HighpassFilter": HighpassFilter,
   102	    }
   103	    plugins = []
   104	    for name, kwargs in (_MOOD_FX.get(mood) or []):
   105	        cls = cls_map.get(name)
   106	        if cls is None:
   107	            continue
   108	        plugins.append(cls(**kwargs))
   109	
   110	    # Master bus: applied to every mood. Tames sub rumble and lifts presence
   111	    # so spectral balance moves toward the target 25/45/30 distribution.
   112	    plugins.extend([
   113	        HighpassFilter(cutoff_frequency_hz=40),
   114	        LowShelfFilter(cutoff_frequency_hz=110, gain_db=-1.5, q=0.7),
   115	        HighShelfFilter(cutoff_frequency_hz=4500, gain_db=+1.5, q=0.7),
   116	    ])
   117	
   118	    board = Pedalboard(plugins)
   119	    return board(samples.astype(np.float32), sample_rate)

exec
/bin/zsh -lc "nl -ba src/soundhash/decode.py | sed -n '240,340p'" in /Users/tabledevil/projects/soundhash
exec
/bin/zsh -lc "nl -ba src/soundhash/render/audio.py | sed -n '1,260p'" in /Users/tabledevil/projects/soundhash
 succeeded in 0ms:
   240	
   241	def _pick_energy_curve(byte: int, form: dict, mood: str = "") -> dict:
   242	    curves = tables.load("energy_curves")["curves"]
   243	    allowed_ids = set(form.get("allowed_curves") or [c["id"] for c in curves])
   244	    pref_ids = set(_MOOD_CURVE_PREF.get(mood, ())) & allowed_ids
   245	    chosen_ids = pref_ids if pref_ids else allowed_ids
   246	    eligible = [c for c in curves if c.get("id") in chosen_ids] or curves
   247	    eligible.sort(key=lambda c: c.get("id", 0))
   248	    return eligible[byte % len(eligible)]
   249	
   250	
   251	def _sample_energy_curve(curve: dict, fraction: float) -> float:
   252	    """Linear interpolation over the curve's `points: [[fraction, energy], ...]`."""
   253	    pts = curve.get("points") or [[0.0, 0.5], [1.0, 0.5]]
   254	    if fraction <= pts[0][0]:
   255	        return float(pts[0][1])
   256	    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
   257	        if fraction <= x1:
   258	            if x1 == x0:
   259	                return float(y1)
   260	            t = (fraction - x0) / (x1 - x0)
   261	            return float(y0 + (y1 - y0) * t)
   262	    return float(pts[-1][1])
   263	
   264	
   265	def _pick_progression(byte: int, mood: str, mode: str) -> dict:
   266	    """Filter progression bank by mood-tag ∩ mode, then index."""
   267	    progs = tables.load("harmony/progressions")["progressions"]
   268	    eligible = [p for p in progs if mood in p.get("mood_tags", []) and p["mode"] == mode]
   269	    if not eligible:
   270	        # Fallback: relax mode constraint, keep mood.
   271	        eligible = [p for p in progs if mood in p.get("mood_tags", [])]
   272	    if not eligible:
   273	        # Last-resort fallback: any ionian progression.
   274	        eligible = [p for p in progs if p["mode"] == "ionian"]
   275	    eligible.sort(key=lambda p: p["id"])               # stable order
   276	    return eligible[byte % len(eligible)]
   277	
   278	
   279	def _filter_by_mood(items, mood):
   280	    return [x for x in items if mood in x.get("mood_tags", [])]
   281	
   282	
   283	def _pick_drum_kit(byte: int, mood: str) -> dict:
   284	    kits = tables.load("drums/drumkits")["kits"]
   285	    eligible = _filter_by_mood(kits, mood) or kits
   286	    eligible.sort(key=lambda k: k["id"])
   287	    return eligible[byte % len(eligible)]
   288	
   289	
   290	# ---------------------------------------------------------------------------
   291	# Mood-keyed GM program palettes (placeholder until synth_pool.json is wired).
   292	# Each tuple gives candidates for that role; byte % len picks one.
   293	# ---------------------------------------------------------------------------
   294	
   295	# (gm_program, name) — stick to widely-supported GM patches so MS Basic / GeneralUser cover them.
   296	_GM_PALETTE: dict[str, dict[str, tuple[int, ...]]] = {
   297	    "M0":  {"bass": (32,),               "comp": (88, 89, 91),       "lead": (54, 75, 73),   "pad": (88, 89, 94),    "counter": (52, 73, 91)},   # Ambient
   298	    "M1":  {"bass": (32, 33),            "comp": (0, 4, 24),         "lead": (73, 71, 56),   "pad": (89, 91, 95),    "counter": (40, 41, 73)},
   299	    "M2":  {"bass": (33, 34, 36),        "comp": (4, 5, 11),         "lead": (80, 81, 28),   "pad": (89, 95, 91),    "counter": (4, 5, 11)},
   300	    "M3":  {"bass": (33, 36),            "comp": (4, 5, 88, 89),     "lead": (80, 73, 78),   "pad": (89, 91, 94),    "counter": (52, 91, 73)},
   301	    "M4":  {"bass": (32, 35),            "comp": (24, 25, 32),       "lead": (56, 11, 24),   "pad": (89, 91, 94),    "counter": (60, 56, 73)},
   302	    "M5":  {"bass": (38, 39, 33),        "comp": (81, 89, 80),       "lead": (81, 80, 84),   "pad": (90, 89, 94),    "counter": (82, 81, 84)},
   303	    "M6":  {"bass": (38, 39, 36),        "comp": (16, 17, 81),       "lead": (80, 81, 53),   "pad": (90, 89, 95),    "counter": (54, 80, 81)},
   304	    "M7":  {"bass": (38, 39),            "comp": (81, 89, 90),       "lead": (80, 81, 87),   "pad": (90, 94, 89),    "counter": (87, 80, 81)},
   305	    "M8":  {"bass": (38, 39, 87),        "comp": (89, 88, 91),       "lead": (81, 80, 87),   "pad": (89, 91, 94),    "counter": (54, 81, 91)},
   306	    "M9":  {"bass": (38, 39, 87),        "comp": (90, 91, 102),      "lead": (88, 81, 102),  "pad": (95, 91, 94),    "counter": (102, 88, 91)},
   307	    "M10": {"bass": (32, 43, 44),        "comp": (48, 49, 50, 89),   "lead": (60, 73, 71),   "pad": (49, 51, 94),    "counter": (49, 73, 71)},  # strings/choir
   308	}
   309	
   310	
   311	def _pick_gm_program(byte: int, mood: str, layer: str, default: int) -> int:
   312	    pal = _GM_PALETTE.get(mood, {}).get(layer)
   313	    if not pal:
   314	        return default
   315	    return pal[byte % len(pal)]
   316	
   317	
   318	def _pick_drum_pattern(byte: int, kit_id: str, time_sig: str) -> dict:
   319	    pats = tables.load(f"drums/patterns/{kit_id}")["patterns"]
   320	    eligible = [p for p in pats if time_sig in p.get("valid_time_sigs", [time_sig])]
   321	    if not eligible:
   322	        eligible = pats
   323	    eligible.sort(key=lambda p: p["id"])
   324	    return eligible[byte % len(eligible)]
   325	
   326	
   327	def _pick_drum_fill(byte: int, kit_id: str) -> str:
   328	    try:
   329	        fills = tables.load(f"drums/fills/{kit_id}")["fills"]
   330	    except FileNotFoundError:
   331	        return ""
   332	    if not fills:
   333	        return ""
   334	    # Prefer escalating fills (target_density > current_density) for a build-up feel.
   335	    eligible = [f for f in fills
   336	                if f.get("target_density", 0) >= f.get("current_density", 0)] or fills
   337	    eligible.sort(key=lambda f: f["id"])
   338	    return eligible[byte % len(eligible)]["id"]
   339	
   340	

 succeeded in 0ms:
     1	"""MIDI → WAV via the fluidsynth CLI, with length cap + cosine fades.
     2	
     3	Pinned flags per DESIGN.md §7 determinism contract: cpu-cores=1, no internal
     4	reverb/chorus. Output is normalised to ≤30 s with a 200 ms cosine fade-out
     5	(and a 5 ms fade-in to kill the start-click).
     6	
     7	Stage-2 will move to in-process pyfluidsynth + ship a CC0 SoundFont.
     8	"""
     9	from __future__ import annotations
    10	
    11	import io
    12	import os
    13	import shutil
    14	import struct
    15	import subprocess
    16	import tempfile
    17	import wave
    18	from pathlib import Path
    19	
    20	import numpy as np
    21	
    22	
    23	# Output length + loudness contract (DESIGN.md §3, dim 14):
    24	MAX_SECONDS = 30.0
    25	FADE_IN_MS = 5
    26	FADE_OUT_MS = 200
    27	TARGET_LUFS = -16.0
    28	PEAK_CEILING_DBFS = -1.5     # peak ceiling (linear-domain limiter, not true-peak)
    29	MAX_GAIN_DB = 24.0           # safety cap on the loudness-correction gain
    30	
    31	
    32	# Default soundfont — bundled with `brew install fluidsynth` on macOS.
    33	# 307 KB Vintage-Dreams-Waves; sounds appropriate for M5 synthwave-ish output
    34	# but is far from full GM. Override via SOUNDHASH_SOUNDFONT env var.
    35	_HERE = os.path.dirname(os.path.abspath(__file__))
    36	_REPO_SF2 = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "assets", "v1", "sf2"))
    37	_DEFAULT_SF2_CANDIDATES = [
    38	    os.path.join(_REPO_SF2, "MS-Basic.sf3"),
    39	    "/usr/local/share/sounds/sf2/FluidR3_GM.sf2",
    40	    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    41	    # last resort: brew's tiny pad-only synth font (no drums)
    42	    "/opt/homebrew/Cellar/fluid-synth/2.5.4/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2",
    43	]
    44	
    45	
    46	def _find_soundfont() -> str:
    47	    sf = os.environ.get("SOUNDHASH_SOUNDFONT")
    48	    if sf and os.path.isfile(sf):
    49	        return sf
    50	    for p in _DEFAULT_SF2_CANDIDATES:
    51	        if os.path.isfile(p):
    52	            return p
    53	    raise RuntimeError(
    54	        "No SoundFont found. Set SOUNDHASH_SOUNDFONT=/path/to.sf2 "
    55	        "or install fluid-synth via Homebrew."
    56	    )
    57	
    58	
    59	def render_wav(midi_bytes: bytes, sample_rate: int = 44100,
    60	               provenance: dict | None = None,
    61	               apply_fx: bool = True) -> bytes:
    62	    """Run fluidsynth on the MIDI, return the WAV bytes (with optional metadata)."""
    63	    if shutil.which("fluidsynth") is None:
    64	        raise RuntimeError("fluidsynth CLI not found on PATH")
    65	    sf2 = _find_soundfont()
    66	
    67	    with tempfile.TemporaryDirectory() as td:
    68	        td = Path(td)
    69	        mid_path = td / "in.mid"
    70	        wav_path = td / "out.wav"
    71	        mid_path.write_bytes(midi_bytes)
    72	        cmd = [
    73	            "fluidsynth", "-ni",
    74	            "-F", str(wav_path),
    75	            "-r", str(sample_rate),
    76	            "-o", "synth.cpu-cores=1",
    77	            "-o", "synth.reverb.active=no",
    78	            "-o", "synth.chorus.active=no",
    79	            sf2,
    80	            str(mid_path),
    81	        ]
    82	        # Inherit a controlled locale for cross-platform-stable text parsing.
    83	        env = {**os.environ, "LC_ALL": "C"}
    84	        proc = subprocess.run(cmd, capture_output=True, env=env, check=False)
    85	        if proc.returncode != 0:
    86	            raise RuntimeError(
    87	                f"fluidsynth exited {proc.returncode}: {proc.stderr.decode(errors='replace')[:400]}"
    88	            )
    89	        wav = _postprocess_wav(wav_path.read_bytes(),
    90	                               mood=(provenance or {}).get("mood") if apply_fx else None)
    91	        if provenance:
    92	            wav = _embed_wav_provenance(wav, provenance)
    93	        return wav
    94	
    95	
    96	def _embed_wav_provenance(wav_bytes: bytes, prov: dict) -> bytes:
    97	    """Insert a RIFF LIST/INFO chunk carrying provenance after `fmt `.
    98	
    99	    Sub-chunks (4-byte IDs) used:
   100	        ISFT  software identifier
   101	        ICMT  free-form comment with full provenance
   102	        ICOP  copyright / license
   103	    """
   104	    if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
   105	        return wav_bytes  # not a WAV; bail.
   106	
   107	    # Build INFO sub-chunks.
   108	    def _info(tag: bytes, text: str) -> bytes:
   109	        data = text.encode("utf-8") + b"\x00"
   110	        if len(data) % 2:
   111	            data += b"\x00"
   112	        return tag + struct.pack("<I", len(data)) + data
   113	
   114	    sw = "soundhash/v1"
   115	    comment = (
   116	        f"soundhash/v1 sha={prov.get('hash_hex','?')[:64]} "
   117	        f"mood={prov.get('mood','?')} mode={prov.get('mode','?')} "
   118	        f"key={prov.get('key_root','?')} tempo={prov.get('tempo_bpm','?')} "
   119	        f"form={prov.get('form_id','?')} bars={prov.get('bars','?')} "
   120	        f"groove={prov.get('groove_template_id','?')} "
   121	        f"curve={prov.get('energy_curve_id','?')}"
   122	    )
   123	    info_payload = b"INFO" + _info(b"ISFT", sw) + _info(b"ICMT", comment) \
   124	                            + _info(b"ICOP", "deterministic — see DESIGN.md")
   125	    list_chunk = b"LIST" + struct.pack("<I", len(info_payload)) + info_payload
   126	
   127	    # Walk existing chunks and insert LIST right after `fmt `.
   128	    out = bytearray()
   129	    out += wav_bytes[:12]                      # RIFF<size>WAVE; size patched at end
   130	    pos = 12
   131	    inserted = False
   132	    while pos + 8 <= len(wav_bytes):
   133	        chunk_id = wav_bytes[pos:pos + 4]
   134	        chunk_size = struct.unpack("<I", wav_bytes[pos + 4:pos + 8])[0]
   135	        chunk_total = 8 + chunk_size + (chunk_size & 1)
   136	        out += wav_bytes[pos:pos + chunk_total]
   137	        pos += chunk_total
   138	        if not inserted and chunk_id == b"fmt ":
   139	            out += list_chunk
   140	            inserted = True
   141	
   142	    if not inserted:
   143	        # No fmt chunk found — append before EOF as safe fallback.
   144	        out += list_chunk
   145	
   146	    # Patch RIFF size (= total length of out minus 8 bytes for "RIFF"+size).
   147	    new_size = len(out) - 8
   148	    out[4:8] = struct.pack("<I", new_size)
   149	    return bytes(out)
   150	
   151	
   152	def _postprocess_wav(wav_bytes: bytes, mood: str | None = None) -> bytes:
   153	    """Cap length, apply fades, LUFS-norm, mood FX chain, peak-limit."""
   154	    with wave.open(io.BytesIO(wav_bytes), "rb") as r:
   155	        n_channels = r.getnchannels()
   156	        sample_width = r.getsampwidth()
   157	        rate = r.getframerate()
   158	        n_frames = r.getnframes()
   159	        raw = r.readframes(n_frames)
   160	    if sample_width != 2:
   161	        return wav_bytes  # only handle 16-bit for now
   162	
   163	    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
   164	    samples = samples.reshape(-1, n_channels)
   165	
   166	    # 1. Length cap.
   167	    max_frames = int(MAX_SECONDS * rate)
   168	    if len(samples) > max_frames:
   169	        samples = samples[:max_frames]
   170	    n = len(samples)
   171	
   172	    # 2. Per-mood FX chain FIRST. Reverb/delay/distortion change the
   173	    # integrated loudness, so the LUFS pass must come after the FX
   174	    # otherwise the "-16 LUFS" target is wrong by however much the FX
   175	    # added/removed.
   176	    if mood:
   177	        try:
   178	            from .fx import apply_fx
   179	            samples = apply_fx(samples, rate, mood)
   180	        except Exception:
   181	            pass
   182	
   183	    # 3. LUFS normalisation (only if there's enough audio for the gating window).
   184	    samples = _normalise_loudness(samples, rate)
   185	
   186	    # 4. Cosine fades.
   187	    fi = max(1, int(FADE_IN_MS * rate / 1000))
   188	    fo = max(1, int(FADE_OUT_MS * rate / 1000))
   189	    if n >= fi:
   190	        ramp = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, fi, dtype=np.float32)))
   191	        samples[:fi] *= ramp[:, None]
   192	    if n >= fo:
   193	        ramp = 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, fo, dtype=np.float32)))
   194	        samples[-fo:] *= ramp[:, None]
   195	
   196	    # 5. Peak limiter at PEAK_CEILING_DBFS (linear-domain; deterministic).
   197	    ceiling = 10 ** (PEAK_CEILING_DBFS / 20.0)
   198	    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
   199	    if peak > ceiling:
   200	        samples *= ceiling / peak
   201	
   202	    # Quantise back to int16.
   203	    out_int = np.clip(samples * 32768.0, -32768, 32767).astype("<i2")
   204	
   205	    out = io.BytesIO()
   206	    with wave.open(out, "wb") as w:
   207	        w.setnchannels(n_channels)
   208	        w.setsampwidth(2)
   209	        w.setframerate(rate)
   210	        w.writeframes(out_int.tobytes())
   211	    return out.getvalue()
   212	
   213	
   214	def _normalise_loudness(samples: np.ndarray, rate: int) -> np.ndarray:
   215	    """Apply gain so integrated LUFS approaches TARGET_LUFS. Deterministic.
   216	
   217	    pyloudnorm uses ITU-R BS.1770 with a 400 ms window — needs ≥0.4 s of audio.
   218	    """
   219	    try:
   220	        import pyloudnorm
   221	    except ImportError:
   222	        return samples
   223	    if len(samples) < int(0.5 * rate):
   224	        return samples
   225	    meter = pyloudnorm.Meter(rate)        # default block_size=0.4 s
   226	    try:
   227	        loudness = meter.integrated_loudness(samples)
   228	    except Exception:
   229	        return samples
   230	    if not np.isfinite(loudness):
   231	        return samples
   232	    gain_db = TARGET_LUFS - loudness
   233	    gain_db = max(-MAX_GAIN_DB, min(MAX_GAIN_DB, gain_db))
   234	    gain = 10 ** (gain_db / 20.0)
   235	    return samples * gain

codex
All notes below are based on [fx.py](/Users/tabledevil/projects/soundhash/src/soundhash/render/fx.py:21), [audio.py](/Users/tabledevil/projects/soundhash/src/soundhash/render/audio.py:152), and [_GM_PALETTE](/Users/tabledevil/projects/soundhash/src/soundhash/decode.py:296).

One pipeline mismatch matters up front: [fx.py](/Users/tabledevil/projects/soundhash/src/soundhash/render/fx.py:3) says FX happen after LUFS, but [audio.py](/Users/tabledevil/projects/soundhash/src/soundhash/render/audio.py:172) applies FX before loudness normalization. Also [audio.py](/Users/tabledevil/projects/soundhash/src/soundhash/render/audio.py:196) is a sample-peak scaler, not an oversampled true-peak limiter. That changes how these chains behave.

## 1. Which mood FX chains will sound thin / muddy / cliche given the chain ordering and parameters?

- `M0` will go muddy fast. `Reverb(room_size=0.85, wet=0.40)` into `Chorus(mix=0.25, depth=0.35)` is full-mix wash, not layer-specific ambience. Then only `-1 dB` low shelf at `110 Hz` is nowhere near enough cleanup.
- `M1` is low-mid mud by design. `LowShelf +1.5 dB @ 200 Hz` after a medium hall is exactly where GM warm pads and bass get tubby. The `+1 dB @ 8 kHz` shelf mostly lifts cheap sheen, not real air.
- `M2` is a cliche “lofi button.” Short room, `-2 dB @ 6 kHz`, then `Distortion +4 dB` on the full mix means you are saturating reverb tails and cymbal hash together.
- `M3` is preset-demo downtempo. `Chorus depth 0.45`, `18 ms` center delay, then `375 ms` delay, then reverb, all on the stereo bus, will smear bass definition and collapse role separation.
- `M5` is the most cliche chain in the file. Chorus + `214 ms` delay + plate-ish reverb on a palette already dominated by lead synth patches is straight karaoke synthwave.
- `M6` does not produce “sidechain-feel low pump.” `Reverb -> Compressor(threshold -16, ratio 3:1, attack 8 ms, release 80 ms)` pumps reverb tails and clamps the whole mix. It is bus flattening, not groove enhancement.
- `M7` risks sounding thin because the GM source is already dull and you still apply `HighShelf -1.5 dB @ 9 kHz`. That is “less air, same cardboard.”
- `M8` will sound blunted, not snappy. `Compressor(attack 5 ms)` on the full mix catches too much transient edge before the room reverb even happens.
- `M9` is the cheap-IDM trap. `Phaser centre 1300 Hz, mix 0.30` on the whole mix hollows the intelligibility band, then delay and reverb decorate the hole.
- `M10` is both muddy and trailer-cliche. `Reverb(room_size=0.90, wet=0.45)` plus `+2 dB @ 9 kHz` plus `+1 dB @ 90 Hz` plus the global `+1.5 dB @ 4.5 kHz` shelf is a smile curve on top of a giant hall.
- `M14` is conceptually incoherent. The comment says “no reverb,” but there is still `Reverb(wet=0.04)`. It will not read as Game Boy; it will read as GM-with-EQ.

## 2. Bad GM picks in `_GM_PALETTE`? Is Square Lead 80 vs Calliope 82 vs Saw Lead 81 defensible? Are the pad picks overused?

- `80` Square and `81` Saw are defensible. `82` Calliope is not, at least not as a regular lead option on MS Basic. It usually reads toy-like, nasal, and fake in exactly the wrong way.
- As a spread, `80/81/82` is too narrow anyway. Two are essentially the same lead family, and the third is a novelty patch.
- The pad picks are absolutely overused. `88/89/90/91/94/95` dominate not just `pad`, but also `comp` and `counter` roles across `M0-M10`. That collapses mood identity.
- `89` Warm Pad and `91` Choir Pad are the worst offenders. They are stock-GM shorthand, and on MS Basic they drag everything toward “ROMpler wallpaper.”
- `94` Halo and `95` Sweep are high-risk cliche choices. They sound like preset labels more than musical roles.
- `M8 bass` using `87` Bass+Lead is a bad pick. That patch is mid-forward and compromised as a bass foundation.
- `M9 comp/lead/counter` using `102` FX 7 Echoes is gimmick-on-gimmick. On a stock GM font it reads cheap, not experimental.
- `M6 comp` including `81` Saw Lead is poor orchestration. It fights the lead band instead of functioning as harmonic support.
- `M5` is overcrowded with `80/81/84` across comp, lead, and counter. Too many layers want the same spectral slot.
- `M2 counter` duplicates `comp` exactly with `(4, 5, 11)`. That is not counterpoint; it is role aliasing.

## 3. Is the master EQ over- or under-correcting? Any frequency masking or buildup risks?

- It is under-correcting the real problem and over-correcting the wrong bands.
- `HPF @ 40 Hz` is fine but mostly irrelevant. MS Basic is not failing because of sub-40 rumble.
- `LowShelf -1.5 dB @ 110 Hz` is too gentle and too low. Your buildup risk is more `180-350 Hz` and `400-900 Hz` than true sub.
- `HighShelf +1.5 dB @ 4.5 kHz` is too blunt. On bright or noisy GM patches it boosts plastic attack, hiss, and reverb fizz. On dull patches it still does not create real openness.
- The master shelf partially undoes the deliberate darkening in `M2`, `M7`, `M11`, and `M14`.
- Biggest masking zone: `200-350 Hz` from bass plus warm/new-age/choir pads plus full-range reverb.
- Second masking zone: `500-900 Hz` from choir pad `91`, synth voice `54`, string ensembles `48/49`, and organ/EP comps.
- Third masking zone: `2-4 kHz` from square/saw/charang/brassy leads piling up under the global presence shelf.
- Because loudness normalization happens after FX, any muddy ambience is normalized up and made consistently audible rather than self-hiding.

## 4. MS Basic SF3 has well-known timbral ceilings — what should be compensated for in FX?

- Compensate for shallow depth. Use short, filtered ambience or predelayed reverb; do not use giant full-band halls on the full mix.
- Compensate for plasticky upper mids. The ugly part of cheap GM is usually `2.5-4.5 kHz`, not lack of top-end shelf.
- Compensate for static sustain loops. Very subtle movement helps, but only on selected sustained layers, not on bass and not on the full mix.
- Compensate for weak bass translation with harmonics, not low shelving. These fonts often need density in `80-160 Hz`, not more blanket energy below `100 Hz`.
- Compensate for narrow, flat imaging with selective width on pads and counters only. Your current chorus/phaser choices hit the entire stereo mix and destabilize the wrong content.
- Compensate for fake transients and abrupt releases by shaping wet returns, not by global compression.

## 5. The single FX trick that would most improve the output spectrum?

Band-limit every wet path aggressively.

If you change one thing, make all reverb and delay returns effectively live inside roughly `200 Hz - 7 kHz`. In practice: `HPF 180-250 Hz`, `LPF 6-8 kHz`, optionally a gentle extra dip around `300 Hz`. Right now your time-based FX are carrying the worst parts of MS Basic: low-mid pad fog and brittle fake air. Filtering the wet signal fixes more than another master shelf ever will.

## Top fixes ranked

1. Stop treating time/modulation FX as full-range full-mix inserts. Filter the wet path hard, or the whole project keeps sounding like a soundfont with effects sprayed on top.
2. Clean `_GM_PALETTE`: drop `82` as a default lead, drop `87` as bass, use `102` sparingly if at all, and cut pad reliance on `89/91/94/95`.
3. Replace the static master smile with actual low-mid control. The real problem band is not `40-110 Hz`; it is `200-400 Hz` and, secondarily, harsh `2.5-4.5 kHz`.
4. Rebuild `M6`, `M8`, and `M10`. Those are the clearest cases of “descriptor says one thing, chain does another.”
5. Align the code comments and pipeline claims with reality: FX are pre-LUFS in code, and the limiter shown here is not a true-peak limiter. That matters because your spectral and loudness choices are being judged through that mismatch.
2026-05-08T15:51:16.437961Z ERROR codex_core::session: failed to record rollout items: thread 019e0846-9b9b-78f3-905c-7bf9e679ea9c not found
tokens used
68,188
All notes below are based on [fx.py](/Users/tabledevil/projects/soundhash/src/soundhash/render/fx.py:21), [audio.py](/Users/tabledevil/projects/soundhash/src/soundhash/render/audio.py:152), and [_GM_PALETTE](/Users/tabledevil/projects/soundhash/src/soundhash/decode.py:296).

One pipeline mismatch matters up front: [fx.py](/Users/tabledevil/projects/soundhash/src/soundhash/render/fx.py:3) says FX happen after LUFS, but [audio.py](/Users/tabledevil/projects/soundhash/src/soundhash/render/audio.py:172) applies FX before loudness normalization. Also [audio.py](/Users/tabledevil/projects/soundhash/src/soundhash/render/audio.py:196) is a sample-peak scaler, not an oversampled true-peak limiter. That changes how these chains behave.

## 1. Which mood FX chains will sound thin / muddy / cliche given the chain ordering and parameters?

- `M0` will go muddy fast. `Reverb(room_size=0.85, wet=0.40)` into `Chorus(mix=0.25, depth=0.35)` is full-mix wash, not layer-specific ambience. Then only `-1 dB` low shelf at `110 Hz` is nowhere near enough cleanup.
- `M1` is low-mid mud by design. `LowShelf +1.5 dB @ 200 Hz` after a medium hall is exactly where GM warm pads and bass get tubby. The `+1 dB @ 8 kHz` shelf mostly lifts cheap sheen, not real air.
- `M2` is a cliche “lofi button.” Short room, `-2 dB @ 6 kHz`, then `Distortion +4 dB` on the full mix means you are saturating reverb tails and cymbal hash together.
- `M3` is preset-demo downtempo. `Chorus depth 0.45`, `18 ms` center delay, then `375 ms` delay, then reverb, all on the stereo bus, will smear bass definition and collapse role separation.
- `M5` is the most cliche chain in the file. Chorus + `214 ms` delay + plate-ish reverb on a palette already dominated by lead synth patches is straight karaoke synthwave.
- `M6` does not produce “sidechain-feel low pump.” `Reverb -> Compressor(threshold -16, ratio 3:1, attack 8 ms, release 80 ms)` pumps reverb tails and clamps the whole mix. It is bus flattening, not groove enhancement.
- `M7` risks sounding thin because the GM source is already dull and you still apply `HighShelf -1.5 dB @ 9 kHz`. That is “less air, same cardboard.”
- `M8` will sound blunted, not snappy. `Compressor(attack 5 ms)` on the full mix catches too much transient edge before the room reverb even happens.
- `M9` is the cheap-IDM trap. `Phaser centre 1300 Hz, mix 0.30` on the whole mix hollows the intelligibility band, then delay and reverb decorate the hole.
- `M10` is both muddy and trailer-cliche. `Reverb(room_size=0.90, wet=0.45)` plus `+2 dB @ 9 kHz` plus `+1 dB @ 90 Hz` plus the global `+1.5 dB @ 4.5 kHz` shelf is a smile curve on top of a giant hall.
- `M14` is conceptually incoherent. The comment says “no reverb,” but there is still `Reverb(wet=0.04)`. It will not read as Game Boy; it will read as GM-with-EQ.

## 2. Bad GM picks in `_GM_PALETTE`? Is Square Lead 80 vs Calliope 82 vs Saw Lead 81 defensible? Are the pad picks overused?

- `80` Square and `81` Saw are defensible. `82` Calliope is not, at least not as a regular lead option on MS Basic. It usually reads toy-like, nasal, and fake in exactly the wrong way.
- As a spread, `80/81/82` is too narrow anyway. Two are essentially the same lead family, and the third is a novelty patch.
- The pad picks are absolutely overused. `88/89/90/91/94/95` dominate not just `pad`, but also `comp` and `counter` roles across `M0-M10`. That collapses mood identity.
- `89` Warm Pad and `91` Choir Pad are the worst offenders. They are stock-GM shorthand, and on MS Basic they drag everything toward “ROMpler wallpaper.”
- `94` Halo and `95` Sweep are high-risk cliche choices. They sound like preset labels more than musical roles.
- `M8 bass` using `87` Bass+Lead is a bad pick. That patch is mid-forward and compromised as a bass foundation.
- `M9 comp/lead/counter` using `102` FX 7 Echoes is gimmick-on-gimmick. On a stock GM font it reads cheap, not experimental.
- `M6 comp` including `81` Saw Lead is poor orchestration. It fights the lead band instead of functioning as harmonic support.
- `M5` is overcrowded with `80/81/84` across comp, lead, and counter. Too many layers want the same spectral slot.
- `M2 counter` duplicates `comp` exactly with `(4, 5, 11)`. That is not counterpoint; it is role aliasing.

## 3. Is the master EQ over- or under-correcting? Any frequency masking or buildup risks?

- It is under-correcting the real problem and over-correcting the wrong bands.
- `HPF @ 40 Hz` is fine but mostly irrelevant. MS Basic is not failing because of sub-40 rumble.
- `LowShelf -1.5 dB @ 110 Hz` is too gentle and too low. Your buildup risk is more `180-350 Hz` and `400-900 Hz` than true sub.
- `HighShelf +1.5 dB @ 4.5 kHz` is too blunt. On bright or noisy GM patches it boosts plastic attack, hiss, and reverb fizz. On dull patches it still does not create real openness.
- The master shelf partially undoes the deliberate darkening in `M2`, `M7`, `M11`, and `M14`.
- Biggest masking zone: `200-350 Hz` from bass plus warm/new-age/choir pads plus full-range reverb.
- Second masking zone: `500-900 Hz` from choir pad `91`, synth voice `54`, string ensembles `48/49`, and organ/EP comps.
- Third masking zone: `2-4 kHz` from square/saw/charang/brassy leads piling up under the global presence shelf.
- Because loudness normalization happens after FX, any muddy ambience is normalized up and made consistently audible rather than self-hiding.

## 4. MS Basic SF3 has well-known timbral ceilings — what should be compensated for in FX?

- Compensate for shallow depth. Use short, filtered ambience or predelayed reverb; do not use giant full-band halls on the full mix.
- Compensate for plasticky upper mids. The ugly part of cheap GM is usually `2.5-4.5 kHz`, not lack of top-end shelf.
- Compensate for static sustain loops. Very subtle movement helps, but only on selected sustained layers, not on bass and not on the full mix.
- Compensate for weak bass translation with harmonics, not low shelving. These fonts often need density in `80-160 Hz`, not more blanket energy below `100 Hz`.
- Compensate for narrow, flat imaging with selective width on pads and counters only. Your current chorus/phaser choices hit the entire stereo mix and destabilize the wrong content.
- Compensate for fake transients and abrupt releases by shaping wet returns, not by global compression.

## 5. The single FX trick that would most improve the output spectrum?

Band-limit every wet path aggressively.

If you change one thing, make all reverb and delay returns effectively live inside roughly `200 Hz - 7 kHz`. In practice: `HPF 180-250 Hz`, `LPF 6-8 kHz`, optionally a gentle extra dip around `300 Hz`. Right now your time-based FX are carrying the worst parts of MS Basic: low-mid pad fog and brittle fake air. Filtering the wet signal fixes more than another master shelf ever will.

## Top fixes ranked

1. Stop treating time/modulation FX as full-range full-mix inserts. Filter the wet path hard, or the whole project keeps sounding like a soundfont with effects sprayed on top.
2. Clean `_GM_PALETTE`: drop `82` as a default lead, drop `87` as bass, use `102` sparingly if at all, and cut pad reliance on `89/91/94/95`.
3. Replace the static master smile with actual low-mid control. The real problem band is not `40-110 Hz`; it is `200-400 Hz` and, secondarily, harsh `2.5-4.5 kHz`.
4. Rebuild `M6`, `M8`, and `M10`. Those are the clearest cases of “descriptor says one thing, chain does another.”
5. Align the code comments and pipeline claims with reality: FX are pre-LUFS in code, and the limiter shown here is not a true-peak limiter. That matters because your spectral and loudness choices are being judged through that mismatch.
