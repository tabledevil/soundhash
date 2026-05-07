# Corpus Test Plan

## Phase 0 — golden-file determinism
- 50 fixed hashes (covering all macro moods + edge bytes 0x00, 0xFF).
- Render on linux-x86_64, linux-arm64, macos-arm64.
- Assert: `sha256(wav)` identical across hosts.
- Also render twice on same host, assert identical.

## Phase 1 — distribution sanity (N=1000 random hashes)
- Generate hashes from `HKDF(b"corpus-seed-v1", info=i)` for `i in 0..999`. Reproducible corpus.
- For each, capture: SongSpec, MIDI, WAV, audio features (75-dim vector from `distinguishability_metric.md` Track B).
- Stats to compute:
  - Histogram of macro-mood byte 0 buckets — should match table-row distribution within χ² test.
  - Histogram of tempo, key, mode — uniform per their table.
  - Length distribution (target 12–32 s).
  - LUFS distribution (target -16 ± 0.5).
  - True-peak distribution (≤ -1 dBTP, no exceptions).

## Phase 2 — pairwise distinguishability
- All `1000 × 999 / 2 ≈ 500k` pairs.
- Track A (SongSpec PHD): mean, p5, p1.
- Track B (audio cosine distance): mean, p5, p1.
- Acceptance:
  - p5 (Track A) ≥ 0.20.
  - p1 (Track B) ≥ 0.10.
  - 0 pairs with Track B < 0.05 (effective audio collision).
  - Spearman ρ(A, B) ≥ 0.6.
- For every pair below the p5 threshold: log to `near_collisions.jsonl` for human review.

## Phase 3 — adversarial neighbors
- For 100 random base hashes, flip each of 256 bits one at a time → 25,600 mutated hashes.
- Compute Track-B distance to base.
- Expected curve: byte-0 flips → mean d ≈ 0.6 (mood change). Byte-31 flips → mean d ≈ 0.05 (variation salt only).
- This validates the hierarchical sensitivity claim: high bytes are load-bearing, low bytes are texture.
- Acceptance: byte 0..7 flips produce d > 0.3 in ≥80% of cases.

## Phase 4 — earworm spot-check (human-in-the-loop, optional)
- Sample 50 clips uniformly from corpus.
- 5 listeners rate each on 5 earworm heuristics (1/0 each).
- Acceptance: ≥4/5 heuristics passed for ≥90% of clips.
- A/B test: 20 random pairs, listener guesses "same or different file?" — accuracy should be ≥95% for non-same-mood pairs.

## Phase 5 — feature-space embedding
- 75-dim feature vectors → UMAP to 2D.
- Visual inspection: clusters should align with macro-mood byte 0.
- Quantitative: silhouette score on byte-0 labels ≥ 0.3.

## Phase 6 — collision attack model (documentation only)
- Soundhash is **not** a cryptographic hash. SHA-256 of input is preimage-resistant; soundhash output collapses 256 bits → ~30 s of audio whose perceptual content is described by ~10–20 bits of entropy in Track-A space (mood × key × mode × tempo-bucket × prog-id × ...).
- Birthday bound: ~`sqrt(2 ** effective_bits)` random hashes before perceptual collision.
- We document an estimate (target effective ≥ 24 bits = ~4k hashes before collision is likely) and verify empirically in Phase 2.

## Outputs
- `corpus_v1/wavs/*.wav` (1000 files, ~5.5 GB)
- `corpus_v1/specs/*.json`
- `corpus_v1/features.parquet`
- `corpus_v1/report.html` with all stats and UMAP plot.
- CI: re-run Phase 0 every commit; Phase 1–2 nightly; Phases 3–5 weekly.
