# Dim 07 Comping — Concrete Tables v1 Summary

## Files written

All under `/Users/tabledevil/projects/soundhash/assets/v1/comp/`:

| File | Count | Purpose |
|---|---|---|
| `comp_roles.json` | 12 | High-level comping role (pad, stab, arp, strum, skank, etc.) |
| `strum_patterns.json` | 10 | Guitar-style strum grids with D/U direction + velocity |
| `arp_shapes.json` | 12 | Arpeggiator note-order permutations (4-degree indexing) |
| `chord_rhythm_patterns.json` | 11 | Block-chord rhythm hit grids (sustain → ostinato) |
| `comp_synths.json` | 16 | Comp-side synth/instrument selections + GM hints |

## Key design choices

- **Roles** publish `polyphony_mode ∈ {full_voicing, partial_voicing, monophonic_sequence, silent}`, an `attack_class`/`release_class`, and a `pattern_table` pointer. The `no_comp` role is the universal fallback (all moods).
- **Hard guardrail** (DESIGN §6 #07): `must_top_below_melody_median_minus_semitones: 5` is shipped on every audible role. Runtime drops octaves until satisfied.
- **Energy bins**: each role exposes `energy_min/max ∈ [0,1]` so the layer-activation matrix can pre-filter by current bar energy before the byte selects.
- **Mood tags**: drawn strictly from `M0..M10`. Each role has 3–10 tags, weighted toward genre fit (e.g. `muted_skank` ⊂ {M2,M4,M6}; `synth_arp` ⊂ {M5..M9}).
- **Strum patterns** use a 16-step grid (12 for `gospel_triplet` in 12/8). `inter_string_spread_ms` encodes the rake. `palm_mute` is a boolean flag the renderer uses to attenuate sustain + duck CC11.
- **Arp shapes** index *positions in the current voicing's degree list* (0..polyphony−1). `octave_offsets` per step give octave-stack moves. `random_inkey` is HKDF-derived (`hkdf_label: "comp/arp_perm"`) — never `random.*`.
- **Chord-rhythm patterns** use `(step, duration_steps, vel_factor)`. Verified: every `step + duration_steps ≤ grid_steps`. `sustain_whole` fills a bar; `ostinato_8th` is the densest.
- **Synths** map to GM programs for FluidSynth, with `engine_hint` letting dim 12 redirect (sfizz for piano, surge_xt for pads). `compatible_roles` enables pre-filter at byte 16 (comp synth).

## Constraints verified

- All 5 files parse via `python3 -m json.tool`.
- All IDs lowercase_snake_case, unique within file.
- Mood tags ⊂ {M0..M10}.
- `chord_rhythm_patterns`: every hit `step + duration_steps ≤ grid_steps` (programmatically asserted).
- No leading +N numeric literals.

## Open hooks for downstream dims

- Dim 03 (energy curves) drives role activation via `energy_min/max`.
- Dim 04 (voicings) supplies the degree list `arp_shapes.sequence` indexes into; `polyphony` determines max valid index.
- Dim 08 (melody) provides the median pitch for the top-clearance guardrail.
- Dim 12 (rendering) reads `engine_hint` + `gm_program` for synth dispatch.
- Dim 13 (hash architecture) selects role at byte 15, comp synth at byte 16, arp/strum/chord-rhythm pattern at byte 17.

No adversarial pass this iteration.
