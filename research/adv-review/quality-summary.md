# ADV-QUALITY — Adversarial review of soundhash quality measurement

Reviewed: `src/soundhash/quality.py` (heuristic + mosqito stationary
psychoacoustic score), against the 11-mood showcase corpus.

## Per-mood numbers (showcase)

```
mood  heur  psy   LUFS    crest  L%   M%   H%   width  sone   acum
M0    0.76  1.00  -13.3   15.1   4%   94%   1%  0.66   29.1  1.33
M1    0.98  0.99  -16.3   18.4  31%   40%  29%  0.35   28.5  1.63
M2    0.99  0.97  -13.7   16.0  29%   62%   9%  0.19   34.9  1.70
M3    0.77  1.00  -15.8   18.1   4%   95%   1%  0.23   25.3  1.47
M4    0.88  1.00  -16.7   18.9  32%   65%   2%  0.22   24.4  1.56
M5    0.67  0.95  -18.4   21.4  71%   22%   7%  0.25   23.5  1.75
M6    0.93  0.98  -16.6   16.7  61%   37%   3%  0.15   27.5  1.66
M7    0.71  0.96  -19.2   21.6  49%   46%   5%  0.21   22.5  1.71
M8    0.93  1.00  -15.3   17.7  32%   64%   4%  0.09   30.3  1.61
M9    0.81  0.90  -18.5   21.6  39%   27%  34%  0.11   23.4  1.89
M10   0.91  1.00  -17.1   18.3  43%   56%   1%  0.73   22.9  1.42
```

## Headline verdict (consensus across codex + gemini)

This is **not a "pleasantness" model**; it is a weak failure detector for
level / dynamics / coarse timbre / stereo spread. The current docstring
oversells. Several showcase scores are demonstrably wrong:

- **M2 = 0.99** with only 9% high-band, M0/M3/M10 with 1% high-band still
  scoring 0.76-0.91 — these are dull / muffled / "telephone-bandwidth"
  mixes that the current spectral term cannot punish hard enough (single
  -0.30 hit per offending band).
- **M8 = 0.93** at width 0.09 — sitting on the near-mono boundary, should
  not look excellent.
- **M9** width 0.11 + acum 1.89 — psy still 0.90; the stationary metrics
  smear over real content.

## Issues with the existing metrics

| Metric | Issue |
|---|---|
| LUFS prox (-16, ±2 dB plateau) | Streaming-centric optimum is too tight for a 30-s cue; -20..-12 is more realistic. Integrated LUFS over a clip with quiet intro is misleading. |
| Crest factor 9-18 dB on full mono | Single global peak/RMS is gameable by 2 outlier transients. Use **short-frame (50-200 ms) crest, score median + 95th percentile.** |
| Spectral bands (8% / 70% only) | 20-250 Hz "low" includes mud; 2.5 kHz crossover groups vocal presence with air; one mid-of-track FFT chunk is gameable; -0.30 penalty is too soft for 1% high. |
| Stereo width 0.08-0.80 plateau | 0.08 is mono, 0.80 already phase-risky. **No phase / correlation check at all** → polarity-flipped channel scores high width but disappears on mono. |
| Mosqito stationary | Wrong object for music. `loudness_zwst`/`sharpness_din_st` average over content with drops/builds. **Replace with `loudness_zwtv` / `sharpness_din_tv` and report N5 / S5 (95th percentile of active frames).** |

## What's missing (concrete)

Both reviewers converge on:

- **True-peak (ITU-R BS.1770)** ≤ -1 dBTP; clipped-sample rate < 0.1 %
- **Inter-channel correlation** median 0.1..0.95, min > -0.2; **bass
  correlation < 150 Hz > 0.8** (mono-compatibility of low end)
- **DC offset** < -60 dBFS
- **Time-varying loudness** (LRA / short-term level range) — see metric 1 below
- **Spectral flatness/tonalness** median 0.05..0.5 (catches noise-shaped
  output gaming the band metric)
- **Spectral centroid** median 500-4000 Hz; **high-band occupancy** > 10% of frames
- **Onset density** 0.5..6 onsets/sec (catches static drones)
- **Loop / self-similarity index** — detects "same 1-2 bar loop for 30 s"
- **CLAP / audio embeddings** for outlier and "is this music?" detection
  (PEAQ/ViSQOL are reference-based and useless without ground truth here)

## Gaming the score

The current 4-metric mean is trivially gameable: low-level wide-panned
**pink noise** fills all bands above 8% and pushes width into the
plateau; a brickwall limiter on a sine + noise mix dials in -16 LUFS and
~12 dB crest; **HF dither** lifts `acum` above 0.8; only the middle FFT
chunk needs to look right because the spectrum is sampled once.

## Round 2 — three concrete additional metrics (codex)

Highest signal-to-effort ratio additions (each <30 LOC):

### 1. `short_term_level_range_db` — catches flat / dropout-prone dynamics
400 ms RMS frames, dB-domain, active-only (> -40 dBFS), `P95 - P10`.
Good 3-12 dB; flag <3 dB (flat/limiter-mashed) or >14 dB (unstable).

```python
def short_term_level_range_db(samples, sr):
    import numpy as np, librosa
    mono = samples.mean(axis=1) if samples.ndim == 2 else samples
    rms = librosa.feature.rms(y=mono,
                              frame_length=int(0.4*sr),
                              hop_length=int(0.1*sr),
                              center=False)[0]
    db = librosa.amplitude_to_db(rms + 1e-7, ref=np.max)
    active = db > -40.0
    if active.sum() < 8:
        return 0.0
    return float(np.percentile(db[active], 95) -
                 np.percentile(db[active], 10))
```

### 2. `loop_repetition_index` — catches "1-2 bar loop for 30 s"
Lagged self-similarity on chroma CENS over 2-8 s lags, max mean cosine.
Flag > 0.96.

```python
def loop_repetition_index(samples, sr):
    import numpy as np, librosa
    mono = samples.mean(axis=1) if samples.ndim == 2 else samples
    hop = int(0.5 * sr)
    C = librosa.feature.chroma_cens(y=mono, sr=sr, hop_length=hop)
    C /= np.linalg.norm(C, axis=0, keepdims=True) + 1e-9
    sims = []
    for lag in range(4, 17):  # 2-8 s
        if C.shape[1] <= lag:
            continue
        sims.append(np.mean(np.sum(C[:, :-lag] * C[:, lag:], axis=0)))
    return float(max(sims) if sims else 0.0)
```

### 3. `low_band_side_width` — catches phasey / mono-incompatible bass
Mid/side STFT energy in 20-180 Hz only; `sqrt(E_side / E_mid)`.
Good < 0.18; flag > 0.25.

```python
def low_band_side_width(samples, sr):
    import numpy as np, librosa
    if samples.ndim != 2:
        return 0.0
    L, R = samples[:, 0], samples[:, 1]
    mid, side = 0.5 * (L + R), 0.5 * (L - R)
    M = np.abs(librosa.stft(mid,  n_fft=4096, hop_length=1024)) ** 2
    S = np.abs(librosa.stft(side, n_fft=4096, hop_length=1024)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)
    low = (freqs >= 20) & (freqs < 180)
    return float(np.sqrt((S[low].mean() + 1e-9) / (M[low].mean() + 1e-9)))
```

(Gemini round-2 was rate-limited by upstream capacity; round-1 critique is folded into the issues table above.)

## Recommended action items (priority order)

1. **Re-label** the score: it is a "failure-triage score", not a
   pleasantness model. Update docstring and DESIGN.md §13.
2. **Swap mosqito stationary → time-varying** (`loudness_zwtv`,
   `sharpness_din_tv`), report N5/S5. Single biggest accuracy win for
   music with drops/builds.
3. **Add true-peak + clipped-sample-rate + DC-offset + L/R correlation**
   as hard gates (pass/fail), not soft scores — these are objective
   defects.
4. **Stiffen the spectrum term**: split high-band into presence
   (2.5-6 kHz) and air (6-18 kHz); penalize 1-2 % bands proportionally
   (current -0.30 floor is too gentle), add **spectral flatness** to
   detect noise-filling.
5. Add the 3 metrics above (short-term level range, loop repetition,
   low-band side width).
6. **Anti-gaming**: average spectrum over multiple FFT chunks across
   the clip, not one centred chunk.
7. For genuine "pleasantness" / outlier detection, add **CLAP embedding
   distance to a small reference set** — captures semantic music-ness
   that DSP heuristics fundamentally cannot.
