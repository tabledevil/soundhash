"""Heuristic audio-pleasantness score.

Combines four cheap measurements that correlate with perceived quality of
short musical pieces:

  - LUFS proximity: how close integrated loudness is to the target -16 LUFS.
  - Crest factor: dB ratio of true peak to RMS — too low = squashed/loud,
    too high = quiet/dynamic but soft. Ideal range 9-14 dB.
  - Spectral balance: ratio of low/mid/high band energy. Targets a 25/45/30
    "musical" balance; large deviations (e.g. all-bass or all-treble) score low.
  - Stereo width: |L - R| RMS / |L + R| RMS — 0.10-0.45 sounds full but mono-safe.

The output is a 0..1 score with band sub-scores. Not a substitute for ViSQOL
or PEAQ, but useful for triage / regression on a 1000-hash corpus.
"""
from __future__ import annotations

import io
import wave
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class QualityScore:
    overall: float                # 0..1
    lufs_score: float
    crest_score: float
    spectrum_score: float
    stereo_score: float
    lufs: float                   # actual measured LUFS
    crest_db: float
    band_pct: tuple[float, float, float]  # low, mid, high (sums to 1.0)
    stereo_width: float

    def summary(self) -> str:
        return (f"score={self.overall:.2f}  LUFS={self.lufs:+.1f} "
                f"crest={self.crest_db:.1f}dB  "
                f"bands(L/M/H)={self.band_pct[0]:.0%}/"
                f"{self.band_pct[1]:.0%}/{self.band_pct[2]:.0%}  "
                f"width={self.stereo_width:.2f}")


def score_wav(wav_bytes: bytes, target_lufs: float = -16.0) -> QualityScore:
    """Read a 16-bit stereo PCM WAV and produce a quality score."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as r:
        n_channels = r.getnchannels()
        rate = r.getframerate()
        raw = r.readframes(r.getnframes())
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if n_channels == 2:
        samples = samples.reshape(-1, 2)
    else:
        samples = samples.reshape(-1, 1)
        samples = np.column_stack([samples, samples])

    # ---- LUFS ----------------------------------------------------------
    try:
        import pyloudnorm
        lufs = pyloudnorm.Meter(rate).integrated_loudness(samples)
        if not np.isfinite(lufs):
            lufs = -70.0
    except Exception:
        lufs = -70.0
    # Within 2 dB → 1.0; falls off linearly to 0 at 12 dB away.
    lufs_score = max(0.0, 1.0 - max(0.0, abs(lufs - target_lufs) - 2.0) / 10.0)

    # ---- Crest factor --------------------------------------------------
    mono = samples.mean(axis=1)
    rms = float(np.sqrt(np.mean(mono * mono))) or 1e-9
    peak = float(np.max(np.abs(mono))) or 1e-9
    crest_db = 20.0 * np.log10(peak / rms)
    # Plateau 9-14 dB → 1.0; falls off linearly outside ±5.
    # Crest factor: 9-18 dB is a wide acceptance zone (raw mastered music
    # falls anywhere in that range; broadcast-loud is 8-12, dynamic
    # acoustic is 14-18). Penalize only obvious squashed/peaky cases.
    if 9.0 <= crest_db <= 18.0:
        crest_score = 1.0
    elif crest_db < 9.0:
        crest_score = max(0.0, 1.0 - (9.0 - crest_db) / 5.0)
    else:
        crest_score = max(0.0, 1.0 - (crest_db - 18.0) / 5.0)

    # ---- Spectral balance ----------------------------------------------
    # FFT over a power-of-2 chunk in the middle of the track.
    N = 1 << 15
    if len(mono) < N:
        N = 1 << int(np.floor(np.log2(max(2, len(mono)))))
    mid_start = max(0, (len(mono) - N) // 2)
    chunk = mono[mid_start:mid_start + N] * np.hanning(N).astype(np.float32)
    spec = np.abs(np.fft.rfft(chunk))
    freqs = np.fft.rfftfreq(N, 1.0 / rate)
    low_mask = (freqs >= 20) & (freqs < 250)
    mid_mask = (freqs >= 250) & (freqs < 2500)
    high_mask = (freqs >= 2500) & (freqs < 18000)
    band_pow = np.array([
        float((spec[low_mask] ** 2).sum()),
        float((spec[mid_mask] ** 2).sum()),
        float((spec[high_mask] ** 2).sum()),
    ])
    total = band_pow.sum() or 1e-9
    band_pct = tuple(p / total for p in band_pow)
    # Pleasantness reading of spectral balance is genre-relative (techno needs
    # bass, ambient needs space). Penalize only the obvious failures:
    #   - any band < 8%   → that band is missing → -0.3 per missing
    #   - any band > 70%  → mix is one-band-dominated → -0.3
    spectrum_score = 1.0
    for b in band_pct:
        if b < 0.08:
            spectrum_score -= 0.30
        if b > 0.70:
            spectrum_score -= 0.30
    spectrum_score = max(0.0, spectrum_score)

    # ---- Stereo width --------------------------------------------------
    L, R = samples[:, 0], samples[:, 1]
    mid = (L + R) * 0.5
    side = (L - R) * 0.5
    mid_rms = float(np.sqrt(np.mean(mid * mid))) or 1e-9
    side_rms = float(np.sqrt(np.mean(side * side)))
    width = side_rms / mid_rms
    # Stereo width: 0.08-0.80 is acceptable. Below 0.08 = nearly mono;
    # above 0.80 = phase issues / poor mono-compatibility.
    if 0.08 <= width <= 0.80:
        stereo_score = 1.0
    elif width < 0.08:
        stereo_score = max(0.0, 1.0 - (0.08 - width) / 0.08)
    else:
        stereo_score = max(0.0, 1.0 - (width - 0.80) / 0.5)

    overall = float(np.mean([lufs_score, crest_score, spectrum_score, stereo_score]))

    return QualityScore(
        overall=overall,
        lufs_score=lufs_score,
        crest_score=crest_score,
        spectrum_score=spectrum_score,
        stereo_score=stereo_score,
        lufs=float(lufs),
        crest_db=float(crest_db),
        band_pct=band_pct,
        stereo_width=float(width),
    )
