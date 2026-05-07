# Dimension #08 — Melody — Summary v2 (≤500 words)

## What v2 adds

The v1 final integrated all codex+gemini critiques but stopped at narrative. v2 turns the spec into the JSON the decoder will actually consume. Six files now live under `assets/v1/melody/`:

1. **`motif_rhythms.json`** — 76 rhythm cells partitioned by time-signature and idiom sub-pool. 4/4 holds 32 cells across five idioms (`pop_basic` 8, `latin_clave` 6, `swing_jazz` 6, `funk_syncop` 5, `lyrical_ballad` 7). 6/8 holds 16, 3/4 holds 12, 12/8 holds 8, 7/8 holds 8 split between `2+2+3` and `3+2+2` groupings. Every cell carries `total_beats`, `meter_grouping`, `symmetry_safe`, and `mood_tags` so byte 19 can be filtered before consumption.
2. **`contours.json`** — 32 contours sampled in a single chord-relative degree space (`1=root`, `8=octave`). Each carries `min_onsets` (the v1 G1 fix), `anchor_end`, `peak_position_frac`, `compatible_palettes`, `compatible_phrase_shapes`, `mood_tags`. Coverage spans arches, terraces, blue-bends, lydian lifts, phrygian darks, pendulums, minimal hooks.
3. **`scale_subsets.json`** — 8 bitmask templates over the active mode's 7-degree array (`bit 0 = degree 1`). `full_diatonic` (127), `pent_major` (55), `pent_minor` (109), `blues` (125), `hexatonic_no_4` (119), `chord_tone_only` (21), `arpeggio` (85), `mode_characteristic` (91). Pent-minor/blues are marked as overlay subsets that add chromatic notes at build time per dim #01. `applies_to_modes` and `mood_bias` plumbed throughout.
4. **`phrase_shapes.json`** — 16 templates: AABA, period_4_4, sentence_2_2_4, q_a, climb_release, hook_first, call_response_2_2, pickup_then_8, 7_plus_tag, cad_extension, 1_bar_tail, half_cadence_antecedent, ostinato_loop, ABAC, ABCD_through, rondo_ABACA. Each carries an explicit `packing_function` describing how it expands to the actual melodic-section bar count returned by dim #03.
5. **`accent_skeleton.json`** — the HKDF-driven sub-dimension. 8 micro_shape archetypes give 3 weak-beat interpolation offsets between adjacent strong beats. Spec section formalises the 1-byte HKDF consumption (`soundhash/v1/melody/accent_skeleton`), the chord-tone weighting `[0.35, 0.30, 0.25, 0.10]` (R / 3 / 5 / extension), the truncation rule for meters with <4 strong beats, and the bass-collision substitution that replaces the v1 octave-shift hack.
6. **`mutation_operators.json`** — the v1 markdown table converted to structured form: 12 operator entries, each with `applicable_time_sigs`, `preserves_phrase_coherence`, and a 4-element `weight_by_phrase_position` array (bar1, bar2, bar3, cadence). `filter_rules` enumerates time-sig / mood / cadence / symmetry-safe gates.

## Self-consistency

All six files pass `python3 -m json.tool`. Every cross-reference (`compatible_palettes`, `compatible_phrase_shapes`, `applies_to_modes`, `mood_tags`) targets either a sibling melody file, the v1 mode list, or `M0..M10` IDs from `assets/v1/moods.json`.

## What changes for downstream dims

- Dim #04 must publish chord-onset beats so motif filtering can detect chord-change events (G4 contract).
- Dim #03 owns the phrase packing length; `phrase_shapes.json` `packing_function` strings document the contract; the decoder's resolver implements them.
- Dim #13 should reserve the `melody/accent_skeleton` HKDF label (already present in `assets/v1/labels.json` per v1).

No files outside `assets/v1/melody/` and `research/08-melody/` were modified. DESIGN.md untouched.
