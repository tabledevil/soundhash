# Findings final v2 — 02 Tempo & Groove

> Codex returned 27 critiques (all accepted, C9 partial). Gemini 429'd MODEL_CAPACITY_EXHAUSTED on all retries; only `gemini-3.1-pro-preview` was attempted. Re-run gemini once quota resets.

## Critique disposition

### Schema / format
- **C1** `subdivision_cells` violated by gospel_12_8 (12-cell array). **Accept.**
- **C12** `compound_68_bell` 12 cells vs `meter_accents` 6/8 = 6 cells. **Accept.**
- **C13** `subdivision_cells` should be meter-keyed not role-keyed. **Accept.**
- **C20** Overlay role symbols (clave_wood, log_drum, snare_ghost, shaker) need a kit-fallback contract. **Accept.**

### Archetype gaps
- **C2** No 3/4, 6/8, or odd-meter dedicated grooves. **Accept.**
- **C3** No jazz/triplet-swing ride pocket distinct from gospel. **Accept.**

### Per-role offset feel
- **C4** `dilla_feel.kick` non-zero but labeled "on grid". **Accept.**
- **C5** `mpc60_swing` swing_pct=0.58 → +19 ticks but file uses +24 (≈60%). **Accept.**
- **C6** `neo_soul` swing_pct=0.54 → +10 but file uses +16. **Accept.**
- **C7** `trap_triplet_hat` cannot be expressed as 16th-grid offsets `[0,-40,+40,0]`; needs separate 12-pulse subgrid. **Accept.**

### Overlay theory (correctness, NOT taste)
- **C8** Clave is 2-bar (32 cells), encoded as 1-bar 16. **Accept (must-fix).**
- **C9** son_clave_3_2 cells `[0,3,6,10,12]` non-canonical. **Partial accept** — depends on doubling convention.
- **C10** tresillo should be `[0,6,12]`; file has `[0,6,10]`. **Accept (must-fix).**
- **C11** dembow_classic mislabels primary backbeats (cells 4/8/12) as `snare_ghost`; they are `snare_main`. **Accept (must-fix).**

### Meter accents
- **C14** 3/4 `natural_snare_cells=[4,8]` — 8 is country-specific, over-specifies. **Accept.**
- **C15** 7/8_3+2+2 internal inconsistency `backbeats=[3,5]` vs `natural_snare_cells=[5]`. **Accept.**
- **C16** 6/8 / 12/8 internal weights (0.50/0.40) too high — compound feels will sound square. **Accept.**

### BPM gates
- **C17** Gates global, fires double-time in Ambient/Ballad/Cinematic. **Accept.**
- **C18** 130 boundary collides M7 Techno + M8 DnB. **Accept.**
- **C19** `double_time_gate_bpm` lacks a flag schema/handoff parallel to half-time. **Accept.**

### Determinism
- **C21** "2 bytes per note" contradicts two-draw triangular (needs 4 bytes). **Accept (must-fix).**
- **C22** `(a+b-65535)/2` unnormalized and unrounded. **Accept (must-fix).**
- **C23** Overlay selection shares `groove/microtiming` HKDF label with jitter — coupling. **Accept.**
- **C24** PRNG order tuple ambiguous when multiple events share cell/role. **Accept.**

### Cross-dim
- **C25** Half-time snare-cell override conflicts with `meter_accents.4/4.natural_snare_cells=[4,12]`. **Accept.**
- **C26** Bass-pattern remap (dim #06) vs authored bass offsets — ordering undefined. **Accept.**
- **C27** Overlay accents don't propagate to dim #03 (form) or #08 (melody). **Accept.**

## Concrete diffs to apply (queued for v3)

### `tempo_pools.json`
- Change to strict `>130` for half_time (or shift M7 floor to 132).
- Add `half_time_eligible_moods: ["M2","M7","M8"]`.
- Add `double_time_eligible_moods: ["M2","M9"]`.
- Add `double_time_flag` block parallel to `half_time_flag`.

### `groove_templates.json`
- Refactor `subdivision_cells` to meter-keyed (not role-keyed).
- Zero `dilla_feel.kick` (or rename feel).
- Recalibrate `mpc60_swing` ticks +24 → +19.
- Recalibrate `neo_soul` hats +16 → +10.
- Add `hat_triplet` 12-cell role for trap.
- Add new templates: `jazz_swing_ride`, `waltz_3_4`, `folk_6_8`, `odd_7_8_223`.
- `humanize_spec`: 4 bytes/note; formula `tick = round(((a+b-65535)/65536) * J)`.
- Consumption order `(bar, cell, layer, role, event_idx)`.
- Add `half_time_flag.override` for natural_snare_cells.

### `groove_overlays.json`
- Add `pattern_bars: 2`, `bar_cells: 32` for clave overlays.
- Re-encode son_clave_3_2 / 2_3 / rumba on 32-cell grid.
- tresillo `[0,6,10]` → `[0,6,12]`.
- dembow_classic cells 4,8,12 role `snare_ghost` → `snare_main`.
- Add `role_kit_fallback` GM map.
- Split HKDF: `groove/overlay_select` distinct from `groove/microtiming`.
- Add `accent_export` per overlay (consumed by dim #03 / #08).

### `meter_accents.json`
- 3/4 `natural_snare_cells: [4]`.
- 7/8_3+2+2 align backbeats and snare cells.
- Lower 6/8 internal cells to `[1.00,0.10,0.30,0.75,0.10,0.30]`.
- Lower 12/8 internal 0.40 → 0.25, 0.50 → 0.30.

## New sub-dimensions surfaced (hand back to orchestrator)

- **02b**: role → kit GM-percussion fallback map (consumed by dims #05, #12).
- **02c**: N-bar pattern timelines for 2-bar clave / Brazilian / Cuban patterns.
- **02d**: dim #02 ↔ #06 ordering contract (bass-rewrite before micro-timing offset).
- **02e**: 12-pulse triplet subgrid role channel orthogonal to the 16th grid.
- **02f**: overlay accent export channel to dims #03 (form) and #08 (melody).

## Recommendation

Apply diffs; spawn 02b–02f as follow-ups. Do NOT freeze v1 until C8/C10/C11 (clave/tresillo/dembow theory) and C21/C22 (humanize formula) are corrected — those are correctness, not taste. Re-run gemini critique when capacity returns; codex coverage alone is sufficient for v2 → v3 transition but a second voice is desirable.
