# Summary v2 — 02 Tempo & Groove

> v2 produced concrete JSONs but the agent timed out before writing the narrative. This summary was reconstructed from the on-disk artifacts.

## Files written to `assets/v1/`

| File | Content | Top-level shape |
|---|---|---|
| `tempo_pools.json` | mood → BPM list, half-time/double-time BPM gates | `{pools, half_time_gate_bpm, double_time_gate_bpm, notes}` |
| `groove_templates.json` | 16 groove templates (Dilla-feel, MPC60, neo-soul, house-pocket, techno-push, etc.) with per-instrument-role offset arrays in PPQ-480 ticks | `{ppq, subdivision_cells, humanize_spec, templates[16]}` |
| `groove_overlays.json` | 9 macro-rhythm overlays (clave 3:2, clave 2:3, son clave, dembow, amapiano log-drum, …) applied on top of base patterns | `{format, overlays[9], selection}` |
| `meter_accents.json` | accent strength per beat-cell for 4/4, 3/4, 6/8, 12/8, 7/8 (2+2+3 and 3+2+2) | `{meters, handoff}` |

## Format highlights

- **PPQ 480** is the canonical timing unit. All offsets are signed integer ticks.
- **Per-instrument-role routing**: each groove template has independent offset arrays for `kick / snare / hat_closed / hat_open / ride / perc / bass / comp / lead`. `null` means "inherit straight grid".
- **`humanize_spec`** centralises the deterministic per-note jitter (HKDF label `groove/microtiming`) — collapses with dim #10's velocity humanization.
- **Half-time flag**: BPM ≥ 130 gate, affects only `kick + snare`; hand-off contract documented in `tempo_pools.json` and consumed by dim #05.

## Outstanding (not delivered in v2)

The deepening agent timed out after writing the four JSONs. These items remain open and should be picked up in a v3 iteration:
- Adversarial pass (codex + gemini) on the v2 spec.
- `findings_v2.md` narrative document.
- 30-s tail handling per mood family (currently only briefly mentioned in `tempo_pools.json` notes).

## Validation

All four files parse with `python3 -m json.tool` after a small fix (one `+4` literal → `4`; JSON disallows leading `+`). No structural errors.
