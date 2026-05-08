# Byte budget — soundhash v1

How the SHA-256's 32 bytes (after HKDF expansion) map to musical decisions.

## Macro stream (`HKDF-Expand(prk, "soundhash/v1/macro", 32)`)

| Byte | Decision | Filter chain | Table size |
|---|---|---|---|
| 0 | macro mood | family-of-MIME → 4 candidates | 4 of 15 |
| 1 | mood sub-flavor | mood | reserved (currently unused) |
| 2 | tempo | mood's `tempo_pool` | 5–8 BPMs |
| 3 | key root | uniform 0–11 | 12 |
| 4 | mode | mood's `modes` list | 2–5 |
| 5 | groove template | mood's `_MOOD_GROOVE_POOL` | 1–4 |
| 6 | form | tempo-tier × `_MOOD_FORM_PREF` | 4–7 |
| 7 | progression | mood-tag ∩ mode | 2–10 |
| 8 | voicing style | progression's `allowed_voicing_styles` | 1–5 of 10 |
| 9 | drum kit | mood-filtered | 1–6 of 12 |
| 10 | drum pattern (low + high nibbles) | kit + density 1-2 / 3-4 | 8 each |
| 11 | drum fill arming | kit | reserved (currently unused) |
| 12 | drum escalation algo | always | reserved (declared, not consumed) |
| 13 | bass archetype | mood ∩ time-sig | 2–8 |
| 14 | bass synth + octave | mood ∩ pattern_compat | 1–4 |
| 15 | comp role | mood | 1–6 of 12 |
| 16 | comp synth | role-compatible × mood | 1–6 of 16 |
| 17 | comp pattern variant | role × mood | 6–11 |
| 18 | melody scale subset | mode | 1–8 |
| 19 | melody motif rhythm | time-sig × mood | 32 / 4-4 |
| 20 | melody contour | mood | 7–32 of 32 |
| 21 | melody phrase shape | always | reserved (currently unused) |
| 22 | melody tessitura + lead synth | mood | 5–8 leads / mood |
| 23 | aux-layer mask + counter mode | always | counter mode = 4 |
| 24 | energy curve | form × `_MOOD_CURVE_PREF` | 3–7 of 16 |
| 25 | layer activation matrix | form-compatible × lead-audible | 3–10 of 16 |
| 26 | per-bar mutation seed | per-bar HKDF spillover | n/a |
| 27 | velocity curve + humanization | always | reserved (currently unused) |
| 28 | FX preset | mood | inlined in render/fx.py |
| 29 | FX send levels | always | reserved (currently unused) |
| 30 | mix balance preset | always | reserved (currently unused) |
| 31 | counter-mode (low 2 bits) + variation salt | always | counter mode = 4 |

## Per-bar / per-section sub-streams

Spillover over the 32-byte macro budget; consumed via separate HKDF labels.

| Label | Length | Consumer |
|---|---|---|
| `perbar/melody/<i>` | 4 B / bar | melody mutation (transpose / invert) per bar |
| `perbar/bass/<i>` | 2 B / bar | bass octave shift, skip-last, ghost-first |
| `perbar/comp/<i>` | 2 B / bar | comp drop-last, ±5 vel pull |
| `perbar/aux/<i>` | 4 B / bar | layer dropouts (drums/lead/comp/pad) |
| `form/section/<letter>` | 4 B / section | section-specific motif/contour/comp pattern |
| `aux/earcandy/main/<i>` | 4 B / bar | ear-candy stab positions per bar |
| `expression/velocity/L<n>` | 256 B / layer | per-note velocity jitter |
| `melody/accent_skeleton` | 5 B | song-wide accent skeleton + 4 strong-beat targets |

## Dimension → byte mapping

A given musical dimension's primary entropy:

| Dim | Bytes | Helper |
|---|---|---|
| 01 Key & Mode | 3, 4 | `_pick_mode` |
| 02 Tempo & Groove | 2, 5 | `_pick_tempo`, `_pick_groove_template` |
| 03 Form & Energy | 6, 24, 25 | `_pick_form_unconstrained`, `_pick_energy_curve`, `_pick_activation_matrix` |
| 04 Harmony & Voicing | 7, 8 | `_pick_progression`, voicing style |
| 05 Drums & Fills | 9, 10, 11, 12 | `_pick_drum_kit`, `_pick_drum_pattern_pair`, `_pick_drum_fill` |
| 06 Bass | 13, 14 | `_pick_bass_pattern`, `_pick_bass_synth` |
| 07 Comping | 15, 16, 17 | `_pick_comp_role`, `_pick_comp_synth`, `_pick_comp_pattern`, `_pick_arp_shape` |
| 08 Melody | 18, 19, 20, 22, `melody/accent_skeleton` | `_pick_melody_motif`, `_pick_contour`, `_pick_scale_subset`, accent skeleton |
| 09 Aux Layers | 23 | drone enable, counter mode, ear-candy gate |
| 10 MIDI Expression | 27 (reserved) | velocity jitter via per-layer HKDF |
| 11 MIME → Mood | 0 + MIME family | `_pick_mood`, `family_for_mime` |
| 12 Rendering | 28, 29, 30 (reserved) | per-mood FX in `render/fx.py` |
| 13 Hash Architecture | n/a | HKDF labels in `assets/v1/labels.json` |
| 14 Perceptual & Determinism | n/a | LUFS, FX-after-LUFS, peak limit, pyloudnorm |

## Empirical distributions (500-hash audit, mixed MIME)

```
mood:     M0 52, M1 34, M2 21, M3 48, M4 18, M5 11, M6 14, M7 9,
          M8 14, M9 20, M10 39, M11 51, M12 46, M13 78, M14 45
modes:    aeolian 164, ionian 126, dorian 84, lydian 47, phrygian 33,
          jazz_minor 32, locrian 7, mixolydian 7
keys:     33–55 hits per chromatic root (uniform within ~±20%)
voicing:  close_triad 53, open_triad 48, sus_open 37, quartal 27,
          power 17, drop2_7th 8, shell 5, drop3_7th 2, rootless_B 2,
          rootless_A 1
groove:   straight_4_4 30%, neo_soul 16%, ambient_drift 8%, dilla_feel 6%,
          mpc60_swing 5%, gospel_12_8 5%, others <5% each
counter:  parallel_3rd / parallel_6th / contrary / octave_below
          (uniform on byte 31's low 2 bits)
matrix:   arp_lead, 4floor_house, bass_lead_duo, band_basic, band_full,
          bolero_additive, ambient_drone, staccato_stab, pad_lead,
          minimal_pad — 10 of 16 reachable (lead-silent matrices filtered)
```

## Reserved bytes (declared but not yet consumed)

`byte 1` (mood sub-flavor), `byte 11` (drum fill arming), `byte 12` (escalation algo), `byte 21` (melody phrase shape), `byte 27` (velocity / humanization profile), `byte 29` (FX send levels), `byte 30` (mix balance preset). Wiring these is tracked under tasks `P1-#84`, `P2-#93`, etc.
