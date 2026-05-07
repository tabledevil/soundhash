# Summary — 08 Melody

## Goal
Convert SHA-256 → a memorable, theory-correct, distinguishable lead line in ≤30 s.

## Byte allocation (5 primary + 2 shared + HKDF)
- **Byte 18** scale subset (8 entries, bitmask over current mode — see G8 fix).
- **Byte 19** motif rhythm cell (32–64 per time-sig pool, sub-pools by idiom — C3).
- **Byte 20** contour shape (32, filtered by motif onset count — G1).
- **Byte 21** phrase shape (16, packing-function form fit — C8).
- **Byte 22** tessitura offset (hi nibble) + lead-synth pairing (lo nibble).
- **Byte 26 + Byte 31** mutation seed + accent-skeleton archetype (C4 promoted byte 31 to high-leverage).
- HKDF (`soundhash/v1/melody/...`) expands per-bar mutation seeds and the accent skeleton.

## Tables (skeletons in workspace)
- `motif_rhythms.json`: per-time-sig pools, idiom-sub-pool tags, `meter_grouping`, `symmetry_safe` flag, total duration metadata. ~32 entries / 4-4 (split into 5 idiom sub-pools), 32 / 3-4, 32 / 6-8, 16 / 5-4, 12 / 7-8.
- `contours.json`: 32 entries, each a curve definition with `min_onsets`, `anchor_end`, `peak`, `compatible_palettes`.
- `scale_subsets.json`: 8 bitmask templates over the active mode (G8 fix), each with `compatible_palettes` (C11).
- `phrase_shapes.json`: 16 entries including AABA, period, sentence, Q/A, climb_release, hook_first, plus pickup/tag/cad_extension overflow templates (C8).
- `mutation_operators.md`: identity, transpose±N, pitch_invert (symmetry-safe only), retro_rhythm, truncate, augment (now spans 2 bars — G5), diminute, ornament, sequence±N. Selection: `HKDF(byte26||byte31, "mel/mut", bar_i) % len(allowed_after_filter)`.

## Resolver (pseudocode, post-critique)
1. **Single chord-relative degree space** (C1). Key-relative subsets re-project at build time.
2. Mutate rhythm → sample contour onto post-mutation event list (C2).
3. **Accent skeleton** drives strong-beat snap targets (C4) — distinguishability survives snapping.
4. **No runtime tessitura clamp** (C6). Operator chains exceeding span are filtered out at table-build time.
5. **Anti-parallel guard** at strong beats and chord onsets, detects octaves AND fifths, resolves by alternate chord-tone substitution (C7).
6. Phrase-end and chord-change anchors: `land | approach | common_tone | suspension | tension_keep` (C10).
7. Tie-breaks pinned: nearest() → lower; nearest_octave() → previous direction (C12).

## Tessitura by mood
ballad C4–C5, energetic C5–C6, ambient C3–C4, dark A3–A4, playful E4–E5, epic G4–G5. Byte 22 high nibble offsets ±1 octave inside the mood envelope.

## Memorability levers
- **Hook repetition**: every phrase shape repeats motif A ≥ 2 times.
- **Golden-section peak**: bar `round(0.62 × total_bars)` is the climax bar; contour reaches the highest scale-degree available.
- **Accent skeleton** (the most distinguishing single feature): 4 strong-beat scale-degrees + 1 of 8 micro-shape interpolants — drawn from HKDF-expanded byte 31.

## Cross-dimension contracts
- **#01 mode**: feeds bitmask base for scale subsets.
- **#02 time-sig + swing**: gates motif sub-pool, mutation legality (5/4 & 7/8 require `meter_grouping`).
- **#03 form**: declares melodic-section bar count for phrase packing.
- **#04 harmony**: must publish chord-onset beats and palette tag (for blues/locrian compatibility, C11/G4).
- **#06 bass**: melody resolver reads bass pitches at strong beats for the anti-parallel guard.
- **#09 counter-melody**: reuses motif tables with auto-inversion (open question resolved: yes).
- **#11 mood**: gates idiom sub-pools, tessitura, mutation weights.
- **#13 byte budget**: confirms bytes 18–22, 26, 31 + HKDF for per-bar mutation and accent skeleton.

## Open items handed back to orchestrator
1. **Idiom palette** as a cross-layer concept (split-pool driver for drums/bass/comp/melody).
2. **Accent skeleton** as a new named sub-dimension (consumes 1 HKDF byte; high distinguishability ROI).
3. **Harmonic-rhythm interface**: dim #04 must publish chord-onset beat list.
4. **Phrase-level register planning**: co-owned between #03 and #08.

## Risks and open questions
- Chromatic passing tones still excluded — may revisit if blues sub-pool sounds sterile.
- Triplet motifs vs swing: incompatibility, swing flag excludes triplets.
- Total table-build cost: per-mode × per-mood × per-palette projection of subsets is O(modes × moods × palettes × 8) ≈ a few thousand pre-computed degree sets — fits easily in static JSON.
