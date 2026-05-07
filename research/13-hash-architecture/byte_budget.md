# Byte Budget — soundhash v1

## Macro stream (HKDF label `soundhash/v1/macro`, 32 bytes)

The first 32 bytes of macro decisions follow CONTEXT.md's sketch closely:

| Byte | Dim | Decision | Table size | Bias |
|---|---|---|---|---|
| 0 | 11 | macro mood / archetype | 16 | none |
| 1 | 11 | mood sub-flavor | 8 | none |
| 2 | 2 | tempo bucket | 64 | none |
| 3 | 1 | key root | 12 | 1.6% |
| 4 | 1 | mode | 7 | 2.7% (accept) |
| 5 | 2 | time-sig + swing combo | 8 | none |
| 6 | 3 | form template | 16 | none |
| 7 | 4 | progression bank index | 64 | none |
| 8 | 4 | voicing style | 16 | none |
| 9 | 5 | drum kit | 16 | none |
| 10 | 5 | drum pattern A | 32 | none |
| 11 | 5 | drum pattern B | 32 | none |
| 12 | 5 | fill bank + escalation algo | 16 | none |
| 13 | 6 | bass pattern | 32 | none |
| 14 | 6 | bass synth + octave | 16 | none |
| 15 | 7 | comp role | 8 | none |
| 16 | 7 | comp synth | 16 | none |
| 17 | 7 | arp shape | 16 | none |
| 18 | 8 | melody scale subset | 8 | none |
| 19 | 8 | motif | 32 | none |
| 20 | 8 | contour | 16 | none |
| 21 | 8 | melody synth | 16 | none |
| 22 | 8 | melody articulation | 8 | none |
| 23 | 9 | counter-melody / extra-layer flags | 256 (bitfield) | n/a |
| 24 | 3 | energy curve template | 16 | none |
| 25 | 3 | layer activation matrix preset | 32 | none |
| 26 | 3 | section length tweak | 4 | none |
| 27 | 10 | humanization profile | 16 | none |
| 28 | 12 | FX preset (reverb/delay/saturation) | 16 | none |
| 29 | 12 | FX send levels preset | 8 | none |
| 30 | 12 | mix balance preset | 8 | none |
| 31 | 13 | variation salt (XOR onto per-bar bytes) | 256 | n/a |

## Spillover streams (HKDF expansions)

| Label | Length | Purpose | Consumed by |
|---|---|---|---|
| `soundhash/v1/perbar/drums/<i>` | 4 B per bar | drum mutation/intensity, ghost notes, fill triggers | dim 5 |
| `soundhash/v1/perbar/bass/<i>` | 2 B per bar | bass mutation, octave jumps, ghost notes | dim 6 |
| `soundhash/v1/perbar/comp/<i>` | 2 B per bar | comp mutation, voicing inversion choice | dim 7 |
| `soundhash/v1/perbar/melody/<i>` | 4 B per bar | motif transformation, ornament selection | dim 8 |
| `soundhash/v1/perbar/aux/<i>` | 2 B per bar | aux/ear-candy gate + selection | dim 9 |
| `soundhash/v1/earcandy/positions` | 8 B | ear-candy event positions on song timeline | dim 9 |
| `soundhash/v1/earcandy/types` | 8 B | which type of ear-candy event | dim 9 |
| `soundhash/v1/expression/velocity` | 16 B | per-note velocity micro-shaping seeds | dim 10 |
| `soundhash/v1/expression/cc` | 16 B | CC curve params per layer | dim 10 |
| `soundhash/v1/harmony/substitutions` | 8 B | per-bar chord-substitution choice | dim 4 |
| `soundhash/v1/melody/scaleorder` | 8 B | scale-subset note-ordering perm | dim 8 |
| `soundhash/v1/render/synthparams` | 16 B | synth parameter dial-tweaks (within preset) | dim 12 |

### Per-bar budget worst case

8 bars × (4+2+2+4+2 = 14 bytes) = **112 bytes** per song just for per-bar mutation. HKDF gives this for free.

### Total byte consumption (typical 8-bar song)

- Macro: 32 B
- Per-bar streams: 112 B
- Ear-candy: 16 B
- Expression: 32 B
- Harmony substitutions: 8 B
- Render synthparams: 16 B
- Misc: 8 B
- **Total: ~224 bytes** all derived deterministically from the 32-byte SHA-256 via HKDF.

## Modulo-bias rule per cell

For any table with len ∈ {2,4,8,16,32,64,128,256}, single-byte selection has **zero bias**. We pad less convenient sizes (e.g. 12 → keep at 12, accept 1.6%; 7 → keep at 7, accept 2.7%) **except** when distinguishability matters (mood/macro), where we round table size to a power of 2 by careful curation.

For tables with len > 256, use two bytes big-endian: `(b0<<8 | b1) % len`. Bias ≤ 0.4%.

## Reserved labels (do not reuse)

A label registry file (`tables/v1/labels.json`) lists every label string. CI rejects PRs that add a label not in the registry, and rejects renaming/removal of any v1 label.
