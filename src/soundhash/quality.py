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


# ---------------------------------------------------------------------------
# Psychoacoustic score (mosqito) — slower, more rigorous
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PsychoScore:
    sones: float                   # Zwicker stationary loudness
    acum: float                    # DIN 45692 stationary sharpness
    loudness_score: float          # 0..1, 1.0 in 18-40 sone "comfortable" range
    sharpness_score: float         # 0..1, 1.0 in 0.8-1.6 acum "smooth" range
    overall: float                 # mean(loudness_score, sharpness_score)

    def summary(self) -> str:
        return (f"psy={self.overall:.2f}  "
                f"loudness={self.sones:.1f} sone (s={self.loudness_score:.2f})  "
                f"sharpness={self.acum:.2f} acum (s={self.sharpness_score:.2f})")


# ---------------------------------------------------------------------------
# Additional triage metrics (per adversarial review)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TriageScore:
    level_range_db: float          # P95 - P10 of 400 ms RMS frames, dB
    loop_repetition: float         # 0..1, max self-similarity at lag 1-4 bars
    low_band_side_width: float     # side/mid RMS in 20-180 Hz band

    def summary(self) -> str:
        return (f"triage  level_range={self.level_range_db:.1f}dB  "
                f"loop_rep={self.loop_repetition:.2f}  "
                f"low_side={self.low_band_side_width:.2f}")


def triage_score(wav_bytes: bytes) -> TriageScore:
    """Three failure-mode metrics per the adversarial review:

    * level_range_db — too low = squashed/loud (no dynamics); too high = patchy.
    * loop_repetition — measures whether the same bar repeats verbatim (boring).
    * low_band_side_width — side/mid balance below 180 Hz; phase / mono issue
      if too high.
    """
    with wave.open(io.BytesIO(wav_bytes), "rb") as r:
        rate = r.getframerate()
        n_channels = r.getnchannels()
        raw = r.readframes(r.getnframes())
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if n_channels == 2:
        stereo = samples.reshape(-1, 2)
    else:
        stereo = np.column_stack([samples.reshape(-1, 1), samples.reshape(-1, 1)])
    mono = stereo.mean(axis=1)

    # 1. Short-term level range (P95 - P10 of 400 ms RMS frames).
    frame = max(1, int(0.4 * rate))
    hop = max(1, int(0.1 * rate))
    if len(mono) >= frame:
        n = 1 + (len(mono) - frame) // hop
        rms = np.empty(n, dtype=np.float32)
        for i in range(n):
            sl = mono[i * hop:i * hop + frame]
            rms[i] = float(np.sqrt(np.mean(sl * sl)))
        rms_db = 20.0 * np.log10(rms + 1e-7)
        active = rms_db > (rms_db.max() - 40.0)
        if active.sum() >= 4:
            db = rms_db[active]
            level_range = float(np.percentile(db, 95) - np.percentile(db, 10))
        else:
            level_range = 0.0
    else:
        level_range = 0.0

    # 2. Loop-repetition index. Simple bar-length self-similarity via lagged
    # STFT-magnitude correlation at 1-4 bars. We don't know the bar in seconds
    # here, so probe lags 0.4 .. 2.0 s in 0.2 s steps.
    N_FFT = 1024
    HOP = N_FFT // 4
    if len(mono) >= N_FFT * 4:
        n_windows = 1 + (len(mono) - N_FFT) // HOP
        win = np.hanning(N_FFT).astype(np.float32)
        spec = np.empty((n_windows, N_FFT // 2 + 1), dtype=np.float32)
        for i in range(n_windows):
            f = mono[i * HOP:i * HOP + N_FFT] * win
            spec[i] = np.abs(np.fft.rfft(f))
        spec /= (np.linalg.norm(spec, axis=1, keepdims=True) + 1e-9)
        # 0.4-2.0 s lags converted to window steps.
        lag_secs = [0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0]
        sims = []
        for lag_s in lag_secs:
            lag_steps = int(lag_s * rate / HOP)
            if 1 <= lag_steps < n_windows - 4:
                # Cosine sim between spec[t] and spec[t+lag], averaged.
                a = spec[:-lag_steps]
                b = spec[lag_steps:]
                sim = float(np.mean(np.sum(a * b, axis=1)))
                sims.append(sim)
        loop_rep = float(max(sims) if sims else 0.0)
    else:
        loop_rep = 0.0

    # 3. Low-band side/mid energy ratio (20-180 Hz).
    if n_channels == 2 and len(mono) >= N_FFT:
        L, R = stereo[:, 0], stereo[:, 1]
        mid = 0.5 * (L + R)
        side = 0.5 * (L - R)
        n_w = 1 + (len(mono) - N_FFT) // HOP
        win = np.hanning(N_FFT).astype(np.float32)
        freqs = np.fft.rfftfreq(N_FFT, 1.0 / rate)
        low = (freqs >= 20) & (freqs < 180)
        m_pow = s_pow = 0.0
        for i in range(n_w):
            mf = np.abs(np.fft.rfft(mid[i * HOP:i * HOP + N_FFT] * win))
            sf = np.abs(np.fft.rfft(side[i * HOP:i * HOP + N_FFT] * win))
            m_pow += float(np.sum(mf[low] ** 2))
            s_pow += float(np.sum(sf[low] ** 2))
        low_side = float(np.sqrt((s_pow + 1e-12) / (m_pow + 1e-12)))
    else:
        low_side = 0.0

    return TriageScore(level_range_db=float(level_range),
                       loop_repetition=loop_rep,
                       low_band_side_width=low_side)


def psychoacoustic_score(wav_bytes: bytes) -> PsychoScore | None:
    """Zwicker loudness + DIN sharpness via mosqito. Returns None if unavailable."""
    try:
        from mosqito.sq_metrics import loudness_zwst, sharpness_din_st
    except ImportError:
        return None

    with wave.open(io.BytesIO(wav_bytes), "rb") as r:
        rate = r.getframerate()
        raw = r.readframes(r.getnframes())
    n_channels = 2 if (len(raw) // 2) % 2 == 0 and rate else 1
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if samples.size > 1 and (samples.size % 2) == 0:
        samples = samples.reshape(-1, 2).mean(axis=1)

    try:
        N, _N_spec, _bark = loudness_zwst(samples, rate, field_type="free")
        sharp = sharpness_din_st(samples, rate, weighting="din")
    except Exception:
        return None

    sones = float(N)
    acum = float(sharp)

    # Score curves chosen against a small mastered-music reference set.
    if 18.0 <= sones <= 40.0:
        loudness_score = 1.0
    elif sones < 18.0:
        loudness_score = max(0.0, sones / 18.0)
    else:
        loudness_score = max(0.0, 1.0 - (sones - 40.0) / 30.0)

    if 0.8 <= acum <= 1.6:
        sharpness_score = 1.0
    elif acum < 0.8:
        sharpness_score = max(0.0, acum / 0.8)
    else:
        sharpness_score = max(0.0, 1.0 - (acum - 1.6) / 1.5)

    return PsychoScore(
        sones=sones,
        acum=acum,
        loudness_score=loudness_score,
        sharpness_score=sharpness_score,
        overall=(loudness_score + sharpness_score) / 2.0,
    )
