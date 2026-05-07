# Dimension 01 — Key & Mode — findings_v1

## Scope recap
Byte 3 picks the **key root** (12 chromatic). Byte 4 picks the **mode**. Mood (byte 0/1) and MIME pre-filter the mode pool. This document defines the modes we support, mood→mode pools, modulation rules, characteristic-tone enforcement, register-coupling, and JSON skeletons.

## 1. Mode list — included / excluded

**Included (12 modes total):**

| ID | Mode | Intervals (semitones from root) | Mood tags |
|----|------|-----|------|
| 0 | Ionian (major) | 0,2,4,5,7,9,11 | bright, stable, hopeful |
| 1 | Aeolian (nat. minor) | 0,2,3,5,7,8,10 | sad, pensive, cinematic |
| 2 | Dorian | 0,2,3,5,7,9,10 | jazzy, cool, hopeful-minor |
| 3 | Phrygian | 0,1,3,5,7,8,10 | exotic, dark, flamenco, tense |
| 4 | Lydian | 0,2,4,6,7,9,11 | dreamy, bright, ethereal |
| 5 | Mixolydian | 0,2,4,5,7,9,10 | bluesy, rock, folk, swaggering |
| 6 | Harmonic minor | 0,2,3,5,7,8,11 | dramatic, classical-minor |
| 7 | Melodic minor (asc) | 0,2,3,5,7,9,11 | jazzy-tense, sophisticated |
| 8 | Major pentatonic | 0,2,4,7,9 | innocent, folk, simple |
| 9 | Minor pentatonic | 0,3,5,7,10 | bluesy, rock, raw |
| 10 | Blues (minor pent +b5) | 0,3,5,6,7,10 | gritty, bar-room |
| 11 | Lydian dominant (#4 b7) | 0,2,4,6,7,9,10 | film-score, bright-funky |

**Excluded:**
- **Locrian**: diminished tonic; tonality dissolves.
- **Whole-tone, octatonic, chromatic**: ambiguous tonal center; chord progressions in dim #4 assume stable tonic. Allow as colors inside motifs (dim #8).
- **Phrygian dominant**: covered functionally by Harmonic minor's V-mode.
- **Double harmonic / Hungarian**: novelty risk; defer.
- **Microtonal**: out of scope (see §5).

`mode_id = filtered_pool[byte4 % len(pool)]`.

## 2. Mood → mode pool (byte 4 pre-filter)

```json
{
  "mood_pools": {
    "bright_uplifting":  [0, 4, 8, 11, 5],
    "melancholic":       [1, 2, 6, 9],
    "dark_tense":        [3, 6, 1, 10],
    "dreamy_ambient":    [4, 0, 8, 2],
    "jazzy_cool":        [2, 7, 11, 5],
    "bluesy_gritty":     [9, 10, 5, 3],
    "folk_innocent":     [8, 0, 5, 2],
    "cinematic_dramatic":[6, 1, 7, 4],
    "neutral_default":   [0, 1, 2, 4, 5, 8, 9]
  }
}
```

Every mood has a stable major option, a stable minor option, and 1–3 colors.

## 3. Key root (byte 3) and key→register

12-TET → all 12 enharmonics functionally identical; byte 3 = `[0..11]` semitone offset from C.

```json
{
  "key_pools": {
    "guitar_centric":  [4, 9, 2, 7, 11, 0],
    "brass_centric":   [10, 3, 8, 5, 0, 7],
    "strings_centric": [7, 2, 9, 4, 0, 5],
    "synth_neutral":   [0,1,2,3,4,5,6,7,8,9,10,11]
  }
}
```

For pure synths the pool is `synth_neutral`. For sampled palettes the pool biases to keys whose tonics fall in pleasant register.

## 4. Modal characteristic-tone enforcement

Mode descriptor publishes mandatory tones; melody/comp MUST emphasize them on strong beats at least once per 4 bars.

```json
{
  "characteristic_tones": {
    "lydian":          [6],
    "phrygian":        [1],
    "mixolydian":      [10],
    "dorian":          [9],
    "harmonic_minor":  [8,11],
    "melodic_minor":   [9,11],
    "lydian_dominant": [6,10],
    "blues":           [6]
  }
}
```

Dim #8 motif table is filtered to motifs whose strong-beat hits include at least one characteristic tone in the first 4 bars; dim #4 chord voicings biased to include them (e.g. lydian → IImaj7 with #4 voicing).

## 5. Tuning

**12-TET, A=440, fixed.** Reasons: determinism, universal synth/SF support, listener calibration. Alt-tunings can be a future hash dimension via Surge XT (SCL).

## 6. Key↔register

```json
{
  "layer_registers": {
    "bass":  {"low": 28, "high": 52},
    "comp":  {"low": 48, "high": 72},
    "lead":  {"low": 60, "high": 84},
    "drone": {"low": 24, "high": 48}
  }
}
```

After key root chosen, layer transposes by octave so median note lands in window.

## 7. Brief modulations within 30 s

Modulation rare: ~25–40% of pieces. When it happens, one canonical move:

| ID | Move | When |
|----|------|------|
| 0 | none | most pieces |
| 1 | parallel mode flip | dark_tense, cinematic, B-section |
| 2 | relative shift | melancholic, jazzy, last 8 bars |
| 3 | up a whole step | bright_uplifting, final phrase |
| 4 | V/V tonicization (1 bar) | jazzy, cinematic |

Triggered by `(byte_6 >> 5) & 0x07` mapped through mood's allowed-modulation list. Length 1–8 bars then return.

**Modal interchange** (borrowing chords) lives in dim #4, not a modulation.

## 8. Byte budget

- Byte 3: key root, table 6–12 (mood-filtered).
- Byte 4: mode, table 3–7 (mood-filtered).
- 3 bits from byte 6: modulation type (table 5).

## 9. JSON skeleton

```json
{
  "version": "soundhash/v1/key-mode",
  "modes": [
    {"id":0,"name":"ionian","intervals":[0,2,4,5,7,9,11],"chars":[],"tags":["bright","stable"]},
    {"id":1,"name":"aeolian","intervals":[0,2,3,5,7,8,10],"chars":[],"tags":["sad"]},
    {"id":2,"name":"dorian","intervals":[0,2,3,5,7,9,10],"chars":[9],"tags":["jazzy"]},
    {"id":3,"name":"phrygian","intervals":[0,1,3,5,7,8,10],"chars":[1],"tags":["dark","exotic"]},
    {"id":4,"name":"lydian","intervals":[0,2,4,6,7,9,11],"chars":[6],"tags":["dreamy"]},
    {"id":5,"name":"mixolydian","intervals":[0,2,4,5,7,9,10],"chars":[10],"tags":["bluesy"]},
    {"id":6,"name":"harmonic_minor","intervals":[0,2,3,5,7,8,11],"chars":[8,11],"tags":["dramatic"]},
    {"id":7,"name":"melodic_minor","intervals":[0,2,3,5,7,9,11],"chars":[9,11],"tags":["jazzy-tense"]},
    {"id":8,"name":"major_pent","intervals":[0,2,4,7,9],"chars":[],"tags":["folk"]},
    {"id":9,"name":"minor_pent","intervals":[0,3,5,7,10],"chars":[],"tags":["bluesy","raw"]},
    {"id":10,"name":"blues","intervals":[0,3,5,6,7,10],"chars":[6],"tags":["gritty"]},
    {"id":11,"name":"lydian_dominant","intervals":[0,2,4,6,7,9,10],"chars":[6,10],"tags":["filmic"]}
  ],
  "modulations": [
    {"id":0,"name":"none"},
    {"id":1,"name":"parallel_flip","section":"B","bars":8},
    {"id":2,"name":"relative_shift","section":"outro","bars":8},
    {"id":3,"name":"step_up","section":"final","bars":4},
    {"id":4,"name":"V_of_V","section":"any","bars":1}
  ]
}
```

## 10. Examples
- byte0 → `bright_uplifting`; byte3=0x4A → root index 4 (E); byte4=0x07 → mode 11 (lydian dom). Result: E lydian dominant, must hit A#/D on strong beats. No modulation.
- byte0 → `melancholic`; A harmonic minor; byte6 high bits → modulation 2 (relative shift to C major last 8 bars).

## 11. Interactions
- #4 Harmony reads mode + chars; voicings filtered.
- #8 Melody enforces char-tone hits.
- #11 MIME→mood drives mode pool.
- #12 Synth palette drives key pool.
- #3 Form shares 3 bits for modulation type.
