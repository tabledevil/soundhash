# dim 05 — Drums & Fills, tables v1

This document summarises the four concrete JSON artifacts produced for dim 05
under `assets/v1/drums/`. All files validate as JSON (`python3 -m json.tool`).
IDs are `lower-snake-or-hyphen`, unique within file. Mood tags are drawn only
from `M0..M10`. There are no leading-`+` numeric literals.

## drumkits.json

Twelve kits, each carrying a GM-style key map (channel-10 note numbers for
`kick`, `snare`, `snare_rim`, `hat_closed`, `hat_open`, `ride`, `crash`,
`tom_low`, `tom_mid`, `tom_high`, `perc_1`, `perc_2`), a `mood_tags` whitelist,
a `humanize` baseline (`timing_ms`, `velocity`), a `valid_time_sigs` list and a
`sample_pack_hint` slug to be resolved by dim 12 to a concrete CC0 pack or SF2
program. Kits without a real bass-drum voice (`hand-perc`, `mallets`,
`latin-conga`, `music-box-tick`, `kalimba-tick`) declare `has_kick: false` so
the form scheduler can substitute a bass-layer pulse where the kick would
otherwise have anchored downbeats. Mood-tag distribution: M0×6, M1×5, M2×3,
M3×5, M4×2, M5×3, M6×1, M7×1, M8×3, M9×2, M10×7 — every mood is covered.

## patterns/<kit>.json — 73 patterns total

Each kit ships at least 6 density-tagged patterns (target was 5+), giving a
distribution of `density 0`×12, `density 1`×11, `density 2`×24, `density 3`×14,
`density 4`×12 (73 total, ≥60 required). Patterns are 16-step bars by default;
`12/8`, `6/8` and `3/4` patterns set `steps:12` and `valid_time_sigs`
accordingly; one trap pattern uses `steps:24` to encode triplet-grid hat rolls.
Every pattern declares `assumes_swing` (default `false`), an optional
`ghost_snare` array, and a `style_tag`. Style coverage achieved:
`4-on-the-floor`, `boom-bap`, `amen-style`, `bossa`, `son-clave`, `tresillo`,
`bembe-12-8`, `shuffle`, `brushed-ballad`, `trap-rolls`, `trap-triplets`,
`footwork-160`, `garage-2step`, `breakbeat-classic`, `funk-1`, `tumbao`,
`cascara`, `mambo-peak`, `waltz`, `tick-tock`, plus per-kit `texture` and
`peak` variants.

## fills/<kit>.json — 56 fills total

Every kit has between 4 and 5 fills indexed by `(current_density,
target_density)` with a `span_steps` field (4 or 8) and a `crash_at_next_down`
boolean that lets the renderer drop a crash on the downbeat of the bar after
the fill resolves. Fills cover both escalation transitions
(d1→d2, d2→d3, d2→d4, d3→d4) and de-escalation (d3→d1, d4→d2), so the
bar-level density planner always has a usable transition fill in either
direction without needing to synthesise one.

## escalation_algorithms.json

Eight escalation algorithms (`linear_add`, `subdivision_double`, `tom_rollup`,
`snare_roll_crescendo`, `hat_density_ramp`, `reverse_cymbal_sweep`,
`ghost_note_stack`, `polyrhythm_overlay`) and eight de-escalation algorithms
(`linear_strip`, `subdivision_halve`, `drop_layer`, `kick_only_breakdown`,
`snare_silence_skel`, `hat_thinning`, `ghost_decay`, `swap_to_ride`). Each
entry declares `preserves_rows`, `mutates_rows`, a `param_schema` (type-tagged
parameter slots filled at decode-time from `perbar/drums/<i>` HKDF bytes), and
a `bpm_clamp_max_subdiv` table that prevents 32nd-note ramps at fast tempos
(`>140 BPM ⇒ max subdiv 8`).

## File counts

- drumkits: 12
- patterns: 73 across 12 files (≥60 required)
- fills: 56 across 12 files (≥48 required)
- algorithms: 16 (8 escalation + 8 de-escalation)
