# Perceptual Distinguishability Metric (PHD — Perceptual Hash Distance)

## Goal
A pseudometric `d(s_a, s_b) ∈ [0, 1]` over two soundhash outputs (or their underlying SongSpecs / rendered audio) such that:
- `d ≈ 0` ⇒ a listener cannot tell them apart.
- `d > 0.25` ⇒ a casual listener distinguishes them in a 2-second A/B test.
- `d > 0.5` ⇒ obviously different "song".

## Two-track measurement

Compute PHD at two layers; both must clear thresholds before we trust a corpus.

### Track A — SongSpec semantic distance (cheap, deterministic, no rendering required)

| Component | Weight | Computation |
|---|---|---|
| Macro mood (byte 0) | 0.30 | 0 if same archetype, 1 if different palette family, 0.5 if adjacent (e.g. "lofi"↔"chill") |
| Key root | 0.05 | min(|Δsemitones|, 12-|Δsemitones|) / 6 |
| Mode | 0.05 | 0 same; 0.5 parallel (Cmaj↔Cmin); 1 unrelated |
| Tempo | 0.10 | min(|Δbpm|/60, 1) |
| Time sig + swing | 0.05 | indicator + swing-delta/0.5 |
| Progression | 0.10 | 1 - (longest common chord-function subseq / max len) |
| Form/energy curve | 0.05 | 1 - cosine(energy_curve_a, energy_curve_b) |
| Drum kit + pattern bank | 0.08 | kit-id mismatch + pattern-bank Jaccard |
| Bass + comp synth palette | 0.07 | synth-id Jaccard over active layers |
| Melody contour | 0.10 | 1 - cosine(contour_vec_a, contour_vec_b) where vec = quantized scale-degree deltas |
| Aux layer set | 0.05 | Jaccard over active aux layers |

Sum is in [0,1]. This metric is a **pseudometric** (symmetric, identity-of-indiscernibles-up-to-equivalence, triangle inequality holds because each component is itself a metric on a discrete or normalized continuous space).

### Track B — Audio-feature distance (ground truth, rendered)

Extract from the 30 s WAV using `librosa`/`essentia` (pin versions):
- 13-dim MFCC means + stds (timbre)
- 12-dim chroma mean (harmonic content)
- Onset-density / beat-density (rhythm)
- Spectral centroid + rolloff means (brightness)
- Loudness envelope (RMS over 100 ms frames, downsampled to 30 dims)

Concatenate → ~75-dim feature vector, z-score-normalized over the corpus. Distance = cosine distance.

## Calibration
- Render 100 hand-picked *intentionally similar* pairs (same mood, key, tempo, slight melody shift) → measure feature distance distribution → defines `d_similar`.
- Render 100 *intentionally different* pairs (different moods entirely) → defines `d_different`.
- Scale Track-B distances so `mean(d_similar) ≈ 0.15` and `mean(d_different) ≈ 0.7`.

## Acceptance criteria for the corpus
On a corpus of N=1000 random hashes:
- Track A: 5th percentile pairwise distance ≥ 0.20.
- Track B: cosine distance distribution: ≥99% of pairs have d ≥ 0.15; no two pairs collide within `d < 0.05` (collision = effectively same audio).
- Track A and Track B should correlate: Spearman ρ ≥ 0.6.

## Earworm heuristics (qualitative, audited on a 30-clip sample)
1. Distinctive opening 2 bars: lead enters within first 4 beats with a contour change ≥ 4 scale degrees.
2. Hook: melody contains a 3-5 note motif that recurs ≥ 2× verbatim or transposed.
3. B-section contrast: ≥1 of {tempo halftime feel, key/mode shift, drop, register jump ≥ octave}.
4. Rhythmic identity: drum pattern's onset hash is unique vs other clips at >0.3 hamming.
5. Memorable cadence: final 2 bars resolve to tonic or a recognizable plagal/half cadence.

These are scored 0/1 each by automated analysis (or human spot-check). Target ≥4/5 for ≥90% of corpus.
