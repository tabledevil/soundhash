# Layer Activation Matrix Extension (dim #03 → dim #09)

Dim #03 produces an activation matrix `M_primary[layer][bar]` for the four primary layers (drums, bass, comp, lead). Dim #09 extends this with twelve aux layer rows, gated through a deterministic eligibility cascade.

## Cascade per (aux_layer L, bar B)

```
1. mood_eligible       = mood ∈ L.moods
2. section_eligible    = section_label(B) ∈ L.sections_active   (or not in sections_blocked)
3. energy_eligible     = L.energy_range[0] ≤ energy(B) ≤ L.energy_range[1]
4. mask_eligible       = aux_mask[L.id] == 1                     (mask = mood_masks[byte_23[0..3]])
5. mutex_clear         = no higher-priority mutex partner active in this bar
6. clutter_ok          = active_aux_count_so_far(B) < max_aux_active(energy(B))
M_aux[L][B]            = all of above
```

## Resolution order (deterministic)

For each bar B:
1. Compute candidate set C = {L : steps 1–5 pass}.
2. Sort C by `mood_priority[mood]` (stable; layers absent from priority list go last in id-order).
3. Walk C top-down; accept until clutter cap reached. Reject the rest for that bar.

Event layers (riser, downer, fx_oneshot) and always-on (texture) bypass the cap (see aux_layers.json::clutter_budget).

## Edge cases

- **Section transitions**: a riser/downer is anchored to the *target* bar but *fires* in the preceding 1–2 bars; M[riser][B-1] = 1 if target_section(B) has higher energy by ≥0.15.
- **Form section "d" (drop)**: clutter cap is held at 3 (not 4) to keep the drop punchy — encoded as a section override in mood_priority.
- **Modulation bars** (dim #04): drone follows `modulation_policy` bit; harmony_double freezes its interval table to the new key; counter_melody re-resolves scale degrees in new key.
- **Tier T1 (slow tempo, ≤80 BPM)**: counter_rhythm and ad_lib_stab are auto-disabled regardless of mask (too sparse to feel polyrhythmic at <80 BPM).
- **Tier T4 (>150 BPM)**: oohs and pad_wash auto-extend release_ms by +30% to avoid choppy attacks.

## Conflict with primary layers

- `harmony_double` requires lead layer active. If lead is silent in bar B, harmony_double is suppressed.
- `counter_melody` requires lead silent ≥1 beat in `call_response` mode; in parallel modes it requires lead active.
- `drone` requires bass active OR comp active (need at least one harmonic anchor) — otherwise risks feeling like a stuck note.

## Output

The dim #03 matrix is widened from 4 rows to 16 rows (4 primary + 12 aux). Each row is bar-indexed, value ∈ {0, 1} for continuous layers, ∈ {0, position_list} for ear-candy layers (rows are sparse hit lists in those cases).
