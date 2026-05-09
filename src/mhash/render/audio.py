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
_WHEEL_SF2 = os.path.normpath(os.path.join(_HERE, "..", "_assets", "v1", "sf2"))
_DEFAULT_SF2_CANDIDATES = [
    # Prefer the decompressed SF2 — loads ~80 ms vs ~6000 ms for the SF3 (the
    # OGG-Vorbis decode in fluidsynth runs once per invocation otherwise).
    os.path.join(_REPO_SF2, "MS-Basic.sf2"),
    os.path.join(_WHEEL_SF2, "MS-Basic.sf2"),
    os.path.join(_REPO_SF2, "FluidR3_GM.sf2"),
    os.path.join(_WHEEL_SF2, "FluidR3_GM.sf2"),
    os.path.join(_REPO_SF2, "MS-Basic.sf3"),
    os.path.join(_WHEEL_SF2, "MS-Basic.sf3"),
    # Distro-installed FluidR3 (Debian / Ubuntu / Fedora bundle locations).
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/local/share/sounds/sf2/FluidR3_GM.sf2",
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
                               mood=(provenance or {}).get("mood") if apply_fx else None,
                               wet_scale=float((provenance or {}).get("fx_wet_scale", 1.0)))
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

    sw = "mhash/v1"
    comment = (
        f"mhash/v1 sha={prov.get('hash_hex','?')[:64]} "
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


def _postprocess_wav(wav_bytes: bytes, mood: str | None = None,
                     wet_scale: float = 1.0) -> bytes:
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
            samples = apply_fx(samples, rate, mood, wet_scale=wet_scale)
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
