# Mutation operators (dim #08)

Per-bar operator applied to motif A. Selected by `HKDF(byte26||byte31, "mel/mut", bar_i) % len(allowed)`. Some phrase-shape plan slots **force** a specific operator (e.g. `A_seq+2`).

| Op | Definition | When musical | When NOT |
|---|---|---|---|
| `identity` | unchanged | establishment, refrain, hook bars | overuse → boredom |
| `transpose+N` / `transpose-N` | shift all scale-degrees by N (in scale, not chromatic) | sequences, climbing/falling phrases | when the new pitches blow tessitura |
| `invert` | reflect each delta around motif's first degree | mirror/answer phrases, fugal feel | early in phrase before motif is recognised |
| `retrograde` | reverse onset order, keep durations forward | dramatic end-of-section, B section | when phrase-end anchor must hold (overrides retrograde) |
| `truncate` | drop last note → rest | breath, cadence approach, sentence "fragmentation" | bar 1 (no motif yet) |
| `augment` | ×2 durations (may halve count to fit bar) | climactic last bar, ballad consequent | when neighbouring bars are also slow → drag |
| `diminute` | ×0.5 durations | acceleration, build-up bars per energy curve | when synth has slow attack (resolver should suppress) |
| `ornament` | insert upper- or lower-neighbour 16th before a strong-beat note | embellishment, repeat-of-A second pass | strong-beat constraints already loaded |
| `sequence±N` | transposed retrograde-preserving copy of full motif (1-bar units) | sentence continuation, sequential climbs | more than 3 sequential steps → mechanical |

## Operator filtering rules (tabular pre-filter, not runtime)

- Time-sig 5/4 or 7/8 → `augment` excluded (overflows bar).
- Energy bar < 0.3 → `diminute` excluded.
- Phrase last bar → only `identity`, `truncate`, `augment` (preserve cadence anchor).
- Mood "ambient" → `ornament`, `diminute` excluded (busy ornaments break atmosphere).
- Mood "playful" → `truncate`, `ornament` weighted ×2.

## Sequence direction guard

`transpose+N` and `sequence+N` followed by another `+N` must respect tessitura: if cumulative would exceed range, sign auto-flips (filtered at table-build time).
