# Dimension #08 — Melody (findings v1)

## 1. Design philosophy

Melody is the most perceptually-discriminating layer in a 30-second piece — listeners remember tunes more than chords or grooves. So the pipeline must:

1. Be **maximally distinguishable** between hashes (small byte-changes → audibly different tune).
2. Be **theory-correct by construction** (no avoid-notes on strong beats, no awkward leaps that don't recover).
3. Be **memorable** (clear motif, repetition, mutation, phrase-end resolution).

Encoded in **scale degrees + rhythm cells**, not raw MIDI. A deterministic resolver consumes (current_chord, scale_subset, mode, tessitura, beat_strength) → MIDI pitch.

## 2. Byte allocation (bytes 18–22 + reused 26 & 31)

| Byte | Use | Table size | Pre-filter |
|---|---|---|---|
| 18 | Scale subset | 8 | mode (dim #1) |
| 19 | Motif rhythm cell | 32–64 per time-sig pool | dim #2 (time-sig + swing), mood density |
| 20 | Contour shape | 32 | mood (rise vs fall affinity) |
| 21 | Phrase shape | 16 | dim #3 form (must divide melodic-bar count) |
| 22 | Tessitura offset (hi nibble) + lead-synth pairing (lo nibble) | 4×4 | mood sets base tessitura |
| 26 | Per-bar mutation seed (shared) | 256 | XOR'd with bar idx → operator pick |
| 31 | Variation salt (shared) | 256 | secondary entropy: ornament direction, sequence sign |

If form has more bars than seed nibbles, expand via HKDF: `HMAC(SHA256(file), "soundhash/v1/melody-mut")`.

## 3. Motif rhythm cells — `motif_rhythms.json` skeleton

Per time-sig pools. Cell = 1–2 bars of normalized onsets (in beats) + durations. Velocity hints advisory.

```json
{
  "version": 1,
  "4/4": [
    {"id":"qq_h",         "bars":1,"name":"q-q-h",         "onsets":[0,1,2],            "durs":[1,1,2]},
    {"id":"anac_qqh",     "bars":2,"name":"anacrusis-q-q-h","onsets":[-0.5,1,2,3],      "durs":[0.5,1,1,1]},
    {"id":"long_short_long","bars":1,                       "onsets":[0,1.5,2],         "durs":[1.5,0.5,2]},
    {"id":"dotted_e_16",  "bars":1,                         "onsets":[0,0.75,1,1.75,2,2.75,3,3.75],"durs":[0.75,0.25,0.75,0.25,0.75,0.25,0.75,0.25]},
    {"id":"charleston",   "bars":1,                         "onsets":[0,1.5],           "durs":[1.5,2.5]},
    {"id":"16_pickup_dotted_e","bars":1,                    "onsets":[-0.25,0,1,2],     "durs":[0.25,1,1,2]},
    {"id":"tresillo",     "bars":1,                         "onsets":[0,1.5,3],         "durs":[1.5,1.5,1]},
    {"id":"cinquillo",    "bars":1,                         "onsets":[0,0.5,1.5,2,3],   "durs":[0.5,1,0.5,1,1]},
    {"id":"son_clave_2_3","bars":2,                         "onsets":[0,1.5,3,5,6],     "durs":[1.5,1.5,2,1,2]},
    {"id":"rumba_clave",  "bars":2,                         "onsets":[0,1.5,3.25,5,6],  "durs":[1.5,1.75,1.75,1,2]},
    {"id":"habanera",     "bars":1,                         "onsets":[0,1.5,2,3],       "durs":[1.5,0.5,1,1]},
    {"id":"all_quarters", "bars":1,                         "onsets":[0,1,2,3],         "durs":[1,1,1,1]},
    {"id":"all_eighths",  "bars":1,                         "onsets":[0,0.5,1,1.5,2,2.5,3,3.5],"durs":[0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5]},
    {"id":"scotch_snap",  "bars":1,                         "onsets":[0,0.25,1,2,3],    "durs":[0.25,0.75,1,1,1]},
    {"id":"long_held",    "bars":2,                         "onsets":[0],               "durs":[8]},
    {"id":"call_response_q","bars":2,                       "onsets":[0,1,2,4,5,6],     "durs":[1,1,1,1,1,1]},
    {"id":"lullaby_3+3+2","bars":1,                         "onsets":[0,1.5,3],         "durs":[1.5,1.5,1]},
    {"id":"pickup_8th_long","bars":1,                       "onsets":[-0.5,0,2],        "durs":[0.5,2,2]},
    {"id":"samba_cell",   "bars":1,                         "onsets":[0,0.75,1.5,2.5,3],"durs":[0.75,0.75,1,0.5,1]},
    {"id":"bossa_phrase", "bars":2,                         "onsets":[0,1.5,3,4,5.5,7], "durs":[1.5,1.5,1,1.5,1.5,1]},
    {"id":"dotted_q_e",   "bars":1,                         "onsets":[0,1.5,2,3],       "durs":[1.5,0.5,1,1]},
    {"id":"swing_8ths",   "bars":1,                         "onsets":[0,0.66,1,1.66,2,2.66,3,3.66],"durs":[0.66,0.34,0.66,0.34,0.66,0.34,0.66,0.34]},
    {"id":"rest_dense",   "bars":2,                         "onsets":[2,2.5,3,4,4.5],   "durs":[0.5,0.5,1,0.5,3.5]},
    {"id":"anacrusis_3_8th","bars":2,                       "onsets":[-1.5,-1,-0.5,0,2,4,6],"durs":[0.5,0.5,0.5,2,2,2,2]},
    {"id":"long_pickup",  "bars":2,                         "onsets":[-1,4],            "durs":[1,4]},
    {"id":"q_triplet",    "bars":1,                         "onsets":[0,0.667,1.333,2,3],"durs":[0.667,0.667,0.667,1,1]},
    {"id":"half_dot_q",   "bars":1,                         "onsets":[0,3],             "durs":[3,1]},
    {"id":"off_beat_8ths","bars":1,                         "onsets":[0.5,1.5,2.5,3.5], "durs":[0.5,0.5,0.5,0.5]},
    {"id":"two_plus_three","bars":2,                        "onsets":[0,2.5,5],         "durs":[2.5,2.5,3]},
    {"id":"fanfare",      "bars":1,                         "onsets":[0,0.25,0.5,1,2],  "durs":[0.25,0.25,0.5,1,2]},
    {"id":"lament_descend","bars":2,                        "onsets":[0,2,3,4,6],       "durs":[2,1,1,2,2]},
    {"id":"perky_skip",   "bars":1,                         "onsets":[0,0.5,1,1.5,2.5,3],"durs":[0.5,0.5,0.5,1,0.5,1]}
  ],
  "3/4": [
    {"id":"waltz_qqq","bars":1,"onsets":[0,1,2],"durs":[1,1,1]},
    {"id":"waltz_dotted","bars":1,"onsets":[0,1.5],"durs":[1.5,1.5]},
    {"id":"waltz_3+3","bars":2,"onsets":[0,3],"durs":[3,3]},
    {"id":"waltz_pickup","bars":1,"onsets":[-0.5,0,1,2],"durs":[0.5,1,1,1]},
    "...32 entries total..."
  ],
  "6/8": [
    {"id":"compound_qqq","bars":1,"onsets":[0,1,2,3,4,5],"durs":[1,1,1,1,1,1]},
    {"id":"compound_dot","bars":1,"onsets":[0,3],"durs":[3,3]},
    {"id":"tarantella","bars":1,"onsets":[0,1,2,3,4,5],"durs":[1,1,1,1,1,1]},
    "...32 entries total..."
  ],
  "5/4": [
    {"id":"take5_3+2","bars":1,"onsets":[0,1,2,3,4],"durs":[1,1,1,1,1]},
    "...16 entries..."
  ],
  "7/8": [ "...12 entries..." ]
}
```

Pool sizes: 32 (4/4), 32 (3/4), 32 (6/8), 16 (5/4), 12 (7/8). `byte19 % len(filtered_pool)` picks.

Pre-filters: mood density (ballad ≤ 0.6 notes/beat, energetic ≥ 1.0); swing flag (swing-friendly cells only).

## 4. Contour shapes — `contours.json` skeleton (32 entries)

A contour is a function on `t∈[0,1]` returning a fractional **scale-degree** offset relative to the current chord-root. Sampled to N=motif.onset_count points; the last point carries an `anchor_end` forcing phrase-end resolution.

```json
{
  "version": 1,
  "shapes": [
    {"id":"rise",            "curve":"t",                       "anchor_end":"chord_tone"},
    {"id":"arch",            "curve":"sin(pi*t)",                "anchor_end":"chord_tone","peak":0.5},
    {"id":"golden_arch",     "curve":"piecewise_peak(0.62)",     "anchor_end":"root","peak":0.62},
    {"id":"fall",            "curve":"1-t",                      "anchor_end":"root"},
    {"id":"valley",          "curve":"-sin(pi*t)",               "anchor_end":"chord_tone"},
    {"id":"zigzag",          "curve":"saw(t,4)",                 "anchor_end":"chord_tone"},
    {"id":"plateau_then_fall","curve":"plateau60_then_fall",     "anchor_end":"root"},
    {"id":"sigh",            "curve":"step_down_2",               "anchor_end":"3rd"},
    {"id":"call_response",   "curve":"phrase_AB(rise,fall)",      "anchor_end":"chord_tone"},
    {"id":"leap_recover",    "curve":"leap5_then_step",           "anchor_end":"3rd"},
    {"id":"appoggiatura",    "curve":"non_chord_then_resolve",    "anchor_end":"chord_tone"},
    {"id":"escape_tone",     "curve":"step_then_leap_back",       "anchor_end":"chord_tone"},
    {"id":"pendulum",        "curve":"oscillate(3rd,±2)",         "anchor_end":"3rd"},
    {"id":"stair_up",        "curve":"step_up_per_note",          "anchor_end":"5th"},
    {"id":"stair_down",      "curve":"step_down_per_note",        "anchor_end":"root"},
    {"id":"pivot_high",      "curve":"top_pivot_5th_neighbours",  "anchor_end":"5th"},
    {"id":"pivot_low",       "curve":"low_pivot_root_neighbours", "anchor_end":"root"},
    {"id":"two_plateaus",    "curve":"low_then_high",             "anchor_end":"chord_tone"},
    {"id":"falling_3rds",    "curve":"chord_arp_descending",      "anchor_end":"root"},
    {"id":"rising_3rds",     "curve":"chord_arp_ascending",       "anchor_end":"5th"},
    {"id":"neighbor_loop",   "curve":"r,r+1,r,r-1,r",             "anchor_end":"root"},
    {"id":"upper_nbr_motif", "curve":"3,4,3 pattern",             "anchor_end":"3rd"},
    {"id":"question",        "curve":"rise_unresolved",           "anchor_end":"2nd_or_7th"},
    {"id":"answer",          "curve":"fall_to_tonic",             "anchor_end":"root"},
    {"id":"mirror",          "curve":"sym_around_center",         "anchor_end":"chord_tone"},
    {"id":"chant",           "curve":"flat",                       "anchor_end":"root"},
    {"id":"bell",            "curve":"impulse_arpeggio",          "anchor_end":"5th"},
    {"id":"wave",            "curve":"sin(2pi*t)",                 "anchor_end":"chord_tone"},
    {"id":"double_wave",     "curve":"sin(4pi*t)",                 "anchor_end":"chord_tone"},
    {"id":"climbing_seq",    "curve":"step_up_then_repeat",       "anchor_end":"5th"},
    {"id":"falling_seq",     "curve":"step_down_then_repeat",     "anchor_end":"root"},
    {"id":"v_shape",         "curve":"down_then_up",               "anchor_end":"3rd"}
  ]
}
```

## 5. Scale subsets — `scale_subsets.json` skeleton

```json
{
  "version":1,
  "subsets":[
    {"id":"diatonic_full",  "kind":"key_relative","degrees":[1,2,3,4,5,6,7]},
    {"id":"penta_major",    "kind":"key_relative","degrees":[1,2,3,5,6]},
    {"id":"penta_minor",    "kind":"key_relative","degrees":[1,3,4,5,7]},
    {"id":"blues",          "kind":"key_relative","degrees":[1,"b3",4,"#4",5,"b7"]},
    {"id":"hexatonic_no4",  "kind":"key_relative","degrees":[1,2,3,5,6,7]},
    {"id":"mode_character", "kind":"key_relative","degrees_map":{
       "lydian":[1,2,3,"#4",5,6,7],"dorian":[1,2,"b3",4,5,6,"b7"],
       "mixolydian":[1,2,3,4,5,6,"b7"],"phrygian":[1,"b2","b3",4,5,"b6","b7"],
       "locrian":[1,"b2","b3",4,"b5","b6","b7"]}},
    {"id":"chord_tone_only","kind":"chord_relative","degrees":[1,3,5,7]},
    {"id":"arp_from_chord", "kind":"chord_relative","degrees":[1,3,5,7,9]}
  ]
}
```

## 6. Phrase shapes — `phrase_shapes.json` skeleton (16)

```json
{
  "version":1,
  "shapes":[
    {"id":"AABA_2bar",   "bars":8,"plan":["A","A","B","A"],          "B_mutation":"transpose+2"},
    {"id":"AAB_sentence","bars":4,"plan":["A","A","B"],               "B_mutation":"continuation_rise"},
    {"id":"period",      "bars":8,"plan":["antecedent","consequent"], "consequent_anchor":"root"},
    {"id":"Q_A",         "bars":4,"plan":["Q","A"],                   "Q_anchor":"2nd_or_7th","A_anchor":"root"},
    {"id":"AB",          "bars":4,"plan":["A","B"]},
    {"id":"AAA_var",     "bars":6,"plan":["A","A_orn","A_aug"]},
    {"id":"ABAC",        "bars":8,"plan":["A","B","A","C"]},
    {"id":"climb_release","bars":8,"plan":["A","A_seq+2","A_seq+4","release"],"release_anchor":"root"},
    {"id":"call_resp_4", "bars":4,"plan":["call","response"]},
    {"id":"chant_repeat","bars":4,"plan":["A","A","A","A"]},
    {"id":"AABB",        "bars":4,"plan":["A","A","B","B"]},
    {"id":"long_short_short","bars":4,"plan":["A_aug","B","B"]},
    {"id":"continuous",  "bars":8,"plan":["thru-composed"]},
    {"id":"arch_phrase", "bars":8,"plan":["A","A_seq+2","A_seq+4","A_seq+2","A"]},
    {"id":"sentence_8",  "bars":8,"plan":["A","A","B","B","cont","cont","cad","cad"]},
    {"id":"hook_first",  "bars":8,"plan":["HOOK","A","HOOK","A","HOOK","B","HOOK","cad"]}
  ]
}
```

Form filter: byte 21 only sees shapes whose `bars` divide melody-section length given by dim #3.

## 7. Mutation operators (see `mutation_operators.md`)

Identity / transpose ±N (in scale) / invert (around motif's first scale-degree) / retrograde / truncate / augment (×2 durs) / diminute (×0.5 durs) / ornament (insert upper or lower neighbour before strong-beat note) / sequence (translate motif by ±N steps preserving rhythm).

Selection per bar `i`:
```
allowed = phrase_shape.allowed_ops(bar_i)        # plan slot can FORCE an op (e.g. A_seq+2)
seed_byte = HKDF(byte26 || byte31, "mel/mut", i)  # 1 byte
op = allowed[ seed_byte % len(allowed) ]
param = HKDF(byte26 || byte31, "mel/param", i)    # ornament dir / sequence sign
```

## 8. Tessitura per mood

| Mood | Base tessitura | Octave offsets allowed |
|---|---|---|
| ballad | C4–C5 | -1, 0 |
| energetic | C5–C6 | 0, +1 |
| ambient | C3–C4 | -1, 0 |
| dark | A3–A4 | -1, 0 |
| playful | E4–E5 | 0, +1 |
| epic | G4–G5 | 0, +1 |

Resolver clamps any pitch outside tessitura by octave-shifting toward centre.

## 9. Resolver pseudocode

```
def resolve_pitch(contour_sample, scale_subset, current_chord, key, mode,
                   tessitura, beat_strength, prev_pitch, is_phrase_end):
    raw_deg = contour_sample.degree            # fractional, e.g. 2.7
    if scale_subset.kind == "chord_relative":
        candidates = scale_subset.degrees
        ref_root_pc = current_chord.root_pc
    else:
        candidates = degrees_for_mode(scale_subset, mode)
        ref_root_pc = key.root_pc
    deg = nearest(raw_deg, candidates)
    # strong-beat snap
    if beat_strength == "strong" and not is_chord_tone(deg, current_chord, scale_subset):
        deg = nearest_chord_tone(deg, current_chord, scale_subset)
    # phrase-end / chord-change anchor
    if is_phrase_end or contour_sample.is_chord_boundary:
        deg = current_chord.tone(contour_sample.anchor_end)   # root|3rd|5th|7th
    pc = (ref_root_pc + DEGREE_TO_SEMITONES[mode][deg]) % 12
    pitch = nearest_octave(pc, prev_pitch, tessitura)
    # leap-recover guard
    if abs(pitch - prev_pitch) > 12 and not contour_sample.deliberate_big_leap:
        # mark next sample for stepwise return (resolver cooperates with contour iterator)
        next_hint = step_toward(prev_pitch, pitch)
    return pitch
```

## 10. Chord changes (interaction with dim #04)

Phrase shapes carry `chord_change_handling: land|approach|common_tone`.
- `land`: the note at the chord-onset beat is forced to a chord-tone of the new chord.
- `approach`: the immediately preceding weak-beat note is the new chord-tone ±1 step.
- `common_tone`: hold a pitch shared by old & new chords across the change.

## 11. Memorability + parallel-melody-bass guard

- **Hook repetition**: every phrase shape repeats motif A ≥ 2 times.
- **Anti-parallel**: at resolver step 6, if `pitch_pc == bass_pc` for two consecutive notes AND the interval pattern matches a parallel 5th/8ve, octave-shift the melody up.
- **Golden-section peak**: resolver flags `is_peak_bar = round(0.62 * total_bars)`; on that bar the contour is overridden to reach the highest available scale-degree within tessitura.

## 12. Open questions

1. Allow chromatic passing tones? (Currently no; risk for table-built guarantee.)
2. Triplet motifs vs swing — outright incompatibility, or quantize?
3. Counter-melody (dim #9) — re-use motif tables with auto-inversion?
