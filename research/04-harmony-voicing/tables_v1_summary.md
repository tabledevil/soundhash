# Dim 04 — Harmony & Voicing Tables v1

Three JSON tables built under `/Users/tabledevil/projects/soundhash/assets/v1/harmony/` for the soundhash deterministic-audio pipeline. All three validate via `python3 -m json.tool`. IDs are stable lowercase_snake_case and unique within each file. Mood IDs are drawn from `moods.json` (M0..M10). Modes use the canonical 7-list: `ionian, aeolian, dorian, phrygian, lydian, mixolydian, jazz_minor` (the latter standing in for harmonic-/melodic-minor color).

## progressions.json — 90 entries

Each entry is a Roman-numeral chord sequence with explicit chord qualities, bass inversions, mode, mood tags, length in bars, harmonic rhythm, cadence type, tonic-strength score, optional modal-mixture slot, optional secondary-dominant slot indices, allowed and default voicing styles. Cadence vocabulary covers `authentic, plagal, deceptive, half, phrygian, modal_VII_i, picardy, none`. Roman-numeral case follows quality (uppercase = major-quality, lowercase = minor); flat-prefixed `bII, bIII, bVI, bVII` mark borrowed/modal chords. Every (mode, mood) pair that is allowed by `moods.json` has at least one progression entry — no empty buckets.

Distribution:

| Mode | Count |
|---|---|
| ionian | 24 |
| aeolian | 24 |
| dorian | 10 |
| mixolydian | 8 |
| lydian | 6 |
| phrygian | 6 |
| jazz_minor | 8 |
| modal-mixture variants (carry `mixture_slot`/`mixture_chord`) | 6 |
| **total** | **90** |

Includes idiomatic staples: pop axis (I-V-vi-IV, vi-IV-I-V), doo-wop, Pachelbel canon, ii-V-I (major and minor), rhythm changes A, Andalusian cadence, So What quartal, Mixolydian I-bVII vamps, Lydian I-II "dreamy", Phrygian flamenco i-bII-bIII, jazz-minor i(maj7) modal vamps, Neapolitan, tritone-sub turnaround, picardy-third closes, and short 2-bar ostinatos for techno/glitch use.

## voicings.json — 10 styles

Defines each voicing style with: polyphony, MIDI register window, compatible chord qualities, mood compatibility list, whether a separate bass layer is required, doubling rules, and spacing rule. Styles: `close_triad, open_triad, shell, rootless_A, rootless_B, drop2_7th, drop3_7th, sus_open, quartal, power`. Register windows are conservative (low 36 for power, high 84 for sus_open/quartal) to leave melody headroom and keep bass-comp separation. Doubling rules forbid doubled 3rds in major/minor triads and doubled 3rd/7th in 7th-chord forms; rootless A/B require a bass layer.

## resolution_rules.json — 15 entries

Tendency-tone resolution rules indexed by `(from_quality, to_quality, context)`. Each rule lists per-voice resolutions with symbolic `direction` codes (`up_h, down_h, up_w, down_w, down_p4, down_p5, common_tone, down_d3`, etc.). Coverage:

- `V7 -> I` (major) and `V7 -> i` (minor)
- `V7 -> vi` deceptive
- `V7/x -> x` generic secondary dominant
- `bII7 -> I` tritone substitution
- `IV -> I` plagal and `iv -> I` minor-plagal mixture
- `bVI -> V`
- `ii7 -> V7 -> I` (the inner ii→V link)
- `vii°7 -> i` and half-diminished `vii-ø7 -> i`
- Neapolitan `bII6 -> V7`
- Phrygian `bII -> i` half-step cadence
- Modal `bVII -> i`
- `V7alt -> Imaj7` (with b9/#9/b13 voice handling)

These are intended for build-time precomputation of voice-leading paths per (progression × voicing × mixture) combo, per the dim-04 brief in DESIGN.md §6.
