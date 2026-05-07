OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/tabledevil/projects/soundhash/research/01-key-mode
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019e032e-7a08-79f3-acf2-6c23c9d4e280
--------
user
You are critiquing a design document for ONE dimension of a deterministic audio-hashing tool called soundhash.

PROJECT CONTEXT:
# Soundhash — Shared Project Context

> Read this first. Every researcher has the same context. Your dimension-specific brief is in your prompt.

## Goal

Deterministically convert a file's **SHA-256 hash** (32 bytes, optionally extended with HKDF) into **≤30 seconds of pleasant, music-theory-correct audio** that is easily distinguishable between different files. Same hash → bit-identical audio, anywhere.

Inspiration: visual identicons (e.g. GitHub's), but for audio.

## Inputs

- **Primary:** SHA-256 of file bytes (32 bytes = 256 bits = 256 decision tokens of 1 byte each).
- **Secondary (optional):** MIME type and/or file metadata can map to **macro mood/palette** *before* hash bytes are consumed — frees up budget and gives semantic flavor (audio file → different palette than image file).
- **Rule:** hash is consumed as a stream of bytes; never consult bits 1:1.

## Output

- ≤30 seconds.
- Primary artifact: a deterministic **SongSpec** (in-memory structure that fully describes every note, velocity, CC, articulation, layer activation, FX setting).
- Renderer 1: SongSpec → **MIDI** (using mido / pretty_midi / similar).
- Renderer 2: SongSpec + MIDI → **WAV** via existing open-source synths/samplers (FluidSynth + SoundFonts, sfizz, Surge XT, Dexed, Sforzando, etc.). **Do not write our own synths.** Synth choice is itself a hashable dimension.
- Layers: **at least 4, more is fine** (drums, bass, comp/pad, lead, counter-melody, drone, ad-libs, FX risers — all welcome).

## Core principle: hierarchical constraint propagation

Each byte selects from a **lookup table**, but the table is **filtered by all prior choices**, so `byte % len(filtered_table)` is always musically valid. Bad combinations are impossible because they're never in the table.

Decision tree, top-down:

```
mime/macro mood → tempo, key/mode, kits, progression-pool, synth-palette
  key+mode → scale, voicing ranges
    progression → bar count, harmonic rhythm, target chord per bar
      form → section layout, energy curve over bars
        per-bar density → which layers active, which patterns at which intensity
          per-layer pattern → notes/rhythm constrained to current chord & scale
            articulation → CC/velocity/expression
              mix → FX sends, balance
```

## Music theory baked into tables, not runtime

The runtime never enforces theory. The tables are pre-curated so anything you pick is correct:
- Melody works in **scale degrees**, not raw pitches; resolved to pitch using current chord's diatonic context.
- Voice leading is **precomputed** in voicing tables.
- Bass patterns output degrees relative to **current chord root**, not key root.
- Range guards on every layer.
- Strong-beat preference for chord tones, weak-beat for passing tones, encoded in contour tables.

## Determinism contract

- Identical SHA-256 → identical MIDI → identical WAV bytes (assumes pinned synth/soundfont versions, fixed sample rate, fixed renderer flags).
- Tables are static JSON, version-pinned.
- Any randomness must come from the hash, never from the system.

## Initial byte budget sketch (will be refined by dimension #13)

| Bytes | Decision area |
|---|---|
| 0 | macro mood / archetype (or derived from MIME) |
| 1 | mood sub-flavor / brightness |
| 2 | tempo |
| 3 | key root |
| 4 | mode |
| 5 | time sig + swing |
| 6 | form |
| 7-8 | chord progression + voicing style |
| 9-12 | drum kit + patterns A/B + fill bank + escalation algo |
| 13-14 | bass pattern + bass synth/octave |
| 15-17 | comp role + comp synth + arp shape |
| 18-22 | melody scale subset + motif + contour + synth + articulation |
| 23 | counter-melody / extra-layer flags |
| 24-26 | energy curve + layer activation matrix + per-bar mutation seed |
| 27 | humanization |
| 28-29 | FX sends |
| 30 | mix balance preset |
| 31 | variation salt |

If we run out of bytes, we expand via HKDF: `salt = SHA256(file)`, then derive more material with `HMAC(salt, "soundhash/v1/melody")` etc.

## Dimensions being researched in parallel

1. Key & mode (incl. modal mixture, brief modulations)
2. Tempo, time signature, swing/groove
3. Form & energy curves over 30 s
4. Harmony: chord progressions, voicings, voice leading
5. Drums: kits, patterns, fills, escalation/de-escalation algorithms
6. Bass patterns & note selection
7. Comping layer (pad/stab/strum/arp)
8. Melody: motifs, contours, scale subsets, mutation operators
9. Extra/auxiliary layers (drone, ad-libs, risers, ear candy, counter-melody)
10. MIDI expression & humanization (velocity, CC, pitch bend, articulation)
11. MIME-type / file-metadata → mood mapping
12. Rendering stack & synth selection (existing open-source tools only)
13. Hash decode architecture: SHA-256 byte budget, constraint propagation, table format
14. Perceptual distinguishability + determinism + output normalization

## Workspace layout

Each researcher works in `/Users/tabledevil/projects/soundhash/research/<NN-slug>/`:

- `findings_v1.md` — your first-pass research and proposals
- `codex_review.md` — adversarial critique from codex
- `gemini_review.md` — adversarial critique from gemini
- `findings_final.md` — integrated final, addressing or rejecting each critique with reasoning
- `summary.md` — one-page executive summary (≤500 words) for synthesis

## CLI invocation patterns

```bash
# Codex (non-interactive)
codex exec "PROMPT TEXT" 2>&1 | tee codex_review.md
# Or pipe a long prompt via stdin:
cat prompt.txt | codex exec - 2>&1 | tee codex_review.md

# Gemini (non-interactive)
gemini -p "PROMPT TEXT" 2>&1 | tee gemini_review.md
```

When asking for adversarial critique, give the CLI:
1. The shared CONTEXT.md content (so it understands the project).
2. Your `findings_v1.md` content (the thing being critiqued).
3. A specific critique brief: spot weaknesses, missing cases, theory errors, table-size issues, edge cases, novel angles, interactions with other dimensions, anything that would make the output sound bad or non-deterministic.

Concretely, the easiest invocation pattern is:

```bash
codex exec "$(cat <<'EOF'
You are critiquing a design document for ONE dimension of a deterministic audio-hashing tool.

PROJECT CONTEXT:
$(cat /Users/tabledevil/projects/soundhash/research/CONTEXT.md)

DIMENSION UNDER REVIEW:
$(cat findings_v1.md)

YOUR TASK: <specific critique brief>
EOF
)" 2>&1 | tee codex_review.md
```

(Use `bash -c` with proper quoting; the heredoc-inside-command-substitution can be brittle. Prefer building the prompt in a temp file then piping: `cat prompt.txt | codex exec -`.)

## Output rules for researchers

- Be **deep and concrete**. Name specific scales, patterns, tempos, table sizes, algorithms.
- Cite music theory canon where it grounds choices.
- For every "we should pick X" claim, specify: table size, what byte selects it, what pre-filters apply, and what downstream choices it constrains.
- Identify interactions with neighboring dimensions explicitly (e.g. "if dim #2 picks 6/8, my drum patterns must …").
- Web search is permitted via WebFetch/WebSearch when it sharpens specifics (e.g. groove templates from MPC/Logic, GM drum maps).
- Do **not** write code beyond JSON examples or pseudocode in the markdown.
- Do **not** install packages.

## Adversarial-pass output rules

After capturing both reviews, write `findings_final.md` that:
- Lists each critique (codex + gemini) by short tag.
- For each: **accept** (and incorporate) or **reject** (with reasoning).
- Includes any **new dimensions / sub-dimensions** the adversaries surfaced that we should hand back to the orchestrator.

Then write `summary.md` (≤500 words) — the integration-ready exec summary.


DIMENSION UNDER REVIEW (findings_v1 for Key & Mode):

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

YOUR TASK: Critique the above design adversarially. Identify:
- Music theory errors (interval lists, characteristic tones, mood mappings).
- Missing modes/scales we should reconsider including or excluding.
- Mood→mode-pool mismatches (e.g. is dorian really "hopeful-minor"? Is blues fitting "dark_tense"?).
- Modulation pitfalls in 30s pieces (whole-step-up clichés, V/V in only 1 bar may not register, parallel-flip needing strong setup).
- Table-size / determinism / byte-budget issues (stealing 3 bits from byte 6 — does that conflict with dim #3 Form?).
- Characteristic-tone enforcement: is "once per 4 bars on strong beat" enough? Counter-examples?
- Key→register: is the sharp/flat key bias justified given 12-TET? Sampled libraries — does it actually matter?
- Determinism / interaction risks with dim #4 (harmony), #8 (melody), #11 (MIME-mood), #12 (synth).
- Novel angles missed (e.g. quartal/synthetic scales? mode mixture timeline? church-mode chord pools?).

Be specific, terse, and concrete. Output as a numbered list of critiques, each tagged [accept-likely] or [reject-likely] from your view.

codex
Reviewing the key/mode design against the shared constraints and the neighboring dimensions it touches. I’m checking for theory mistakes, pool mismatches, and places where the byte-budget or cross-dimension contract will break down.
codex
1. `[accept-likely]` **Pentatonic and blues do not fit the same contract as “global mode.”** `major_pent`, `minor_pent`, and `blues` are strong melodic vocabularies but weak harmonic systems for dim #4’s progression/voicing layer. A 30 s piece with full chordal accompaniment will either backfill missing 4/7 or 2/6 degrees from outside the collection, or collapse into vamp-only harmony. Treat these as melody/ornament subsets in dim #8, not byte-4 global modes.

2. `[accept-likely]` **The “Phrygian dominant is covered by harmonic minor V-mode” claim is theory-wrong for tonic identity.** `E phrygian dominant` and `A harmonic minor` share pitch content but not tonal center, cadence behavior, or bass gravity. If tonicized modal centers are allowed elsewhere, this exclusion is inconsistent.

3. `[accept-likely]` **`melodic_minor (asc)` is underspecified and stylistically mixed.** In common-practice usage it is not a symmetric up/down collection; in jazz usage it is a stable 7-note “jazz minor.” You need to pick one. For this system, it should explicitly be “jazz melodic minor” or it will create dim #4/#8 ambiguity.

4. `[accept-likely]` **Characteristic-tone tables overstate some tones.** For harmonic minor, `11` (raised 7) is the real identifier; `8` (b6) is shared with aeolian and is not characteristic by itself. For melodic minor, `9` and `11` together distinguish it from aeolian, but if harmony keeps using minor iv/bVI idioms it will still read as plain minor. Characteristic-tone logic needs “must include” and “must avoid contradicting” tables.

5. `[accept-likely]` **“Hit characteristic tone once per 4 bars on a strong beat” is too weak and easy to game.** One accented `#4` does not make lydian if the rest of the piece keeps asserting natural 4 via voicings or passing tones. Better rule: at least 2 exposures per 4 bars across melody+comp, and zero contradiction by the competing degree in cadential or long-note positions.

6. `[accept-likely]` **Mood pools are internally inconsistent with your own stated rule.** `dark_tense: [3,6,1,10]` has no stable major option. `jazzy_cool: [2,7,11,5]` has no plain stable tonic major/minor at all. `folk_innocent: [8,0,5,2]` has no true minor unless you count dorian, which changes the claim. Either remove the rule or fix the pools.

7. `[accept-likely]` **Several mood→mode mappings are likely to sound wrong in practice.** `lydian_dominant` inside `bright_uplifting` is quite tense because of the `b7`; it reads “showy dominant color,” not stable uplift. `phrygian` inside `bluesy_gritty` is a poor fit outside niche fusion/flamenco gestures. `minor_pent` inside `melancholic` biases toward riff/blues language, not “pensive/cinematic.”

8. `[accept-likely]` **Mode selection cannot be independent of harmonic grammar.** Ionian/aeolian/dorian/phrygian/lydian/mixolydian each need distinct chord pools, cadence types, and allowable borrowed functions. If dim #4 reuses one generic progression bank, byte 4 becomes cosmetic. This is most severe for phrygian, lydian dominant, and melodic minor.

9. `[accept-likely]` **Stealing 3 bits from byte 6 is a contract problem, not a detail.** Dim #3 already owns form. Modulation type is tightly coupled to section layout, cadence location, and bar count. Either byte 6 is centrally decomposed by dim #13, or this dimension should not unilaterally consume its high bits.

10. `[accept-likely]` **Your modulation rate is too high for ≤30 s pieces.** `25–40%` is aggressive when many outputs will only have 8–16 bars. A short identicon track needs fast center recognition; frequent modulation reduces memorability and makes distinctness worse. I would cap true modulation closer to `10–20%`, with the rest using modal mixture or secondary-function color only.

11. `[accept-likely]` **The listed modulation types are not equally legible in short forms.** `up a whole step` is a cliché and will read as a gimmick unless the form already repeats material. `V/V tonicization (1 bar)` often will not register at all, especially under fast harmonic rhythm or non-functional modal harmony. `parallel_flip` needs explicit pivot handling; otherwise it sounds like an abrupt palette swap, not modulation.

12. `[accept-likely]` **Modulation mappings are undefined for non-tonal-family modes.** What is the “relative shift” of dorian, blues, or lydian dominant? What is the “parallel flip” target of phrygian? Without per-mode mapping tables, these IDs are not deterministic musical operations.

13. `[accept-likely]` **Key-pool bias by instrument family is weakly justified in 12-TET rendered audio.** For MIDI+synth playback, “good brass keys” or “guitar keys” matter far less than absolute tessitura and idiomatic voicing. Unless a specific sampled library has root-sample artifacts tied to transposition distance, tonic letter name does not buy much. This looks like notation-era bias, not audio-rendering value.

14. `[accept-likely]` **The register rule is too layer-local and can break tonal anchoring.** “Transpose each layer by octave so median note lands in window” can detach the perceived tonic if bass, drone, and comp optimize independently. Bass/drone should anchor the tonic register first; upper layers can adapt around that shared floor.

15. `[accept-likely]` **You need explicit contradiction guards, not just characteristic-tone encouragement.** Examples: lydian should strongly suppress natural 4 in sustained melodic accents; dorian should suppress b6 in cadential spots; mixolydian should suppress leading-tone `7` behavior; phrygian should control natural 2 unless used as chromatic exception. Otherwise the listener hears plain major/minor with occasional color notes.

16. `[accept-likely]` **A better abstraction may be “tonal family” + “melodic color collection,” not one byte = one mode.** Family could be `major / minor / modal-major / modal-minor / dominant / blues`. Then dim #8 can choose pent/blues/jazz-minor subsets as melodic color while dim #4 gets a stable harmonic grammar. That is more deterministic and avoids fake-mode outputs.

17. `[reject-likely]` **Adding more exotic synthetic scales now is probably a mistake.** Quartal language, double harmonic, Hungarian minor, whole-tone, octatonic, etc. would increase distinctness, but they explode the harmony tables and raise “novelty risk” fast. The current omission is defensible if you fix the existing mode contract first.

18. `[accept-likely]` **You are missing church-mode-specific cadence and chord-pool definitions, which matter more than adding new modes.** If dorian, phrygian, lydian, and mixolydian stay, each needs curated cadential moves and tonic-supporting sonorities; otherwise they collapse into aeolian/ionian with costume notes. This is the main missed angle.
2026-05-07T16:05:02.323260Z ERROR codex_core::session: failed to record rollout items: thread 019e032e-7a08-79f3-acf2-6c23c9d4e280 not found
tokens used
17,473
1. `[accept-likely]` **Pentatonic and blues do not fit the same contract as “global mode.”** `major_pent`, `minor_pent`, and `blues` are strong melodic vocabularies but weak harmonic systems for dim #4’s progression/voicing layer. A 30 s piece with full chordal accompaniment will either backfill missing 4/7 or 2/6 degrees from outside the collection, or collapse into vamp-only harmony. Treat these as melody/ornament subsets in dim #8, not byte-4 global modes.

2. `[accept-likely]` **The “Phrygian dominant is covered by harmonic minor V-mode” claim is theory-wrong for tonic identity.** `E phrygian dominant` and `A harmonic minor` share pitch content but not tonal center, cadence behavior, or bass gravity. If tonicized modal centers are allowed elsewhere, this exclusion is inconsistent.

3. `[accept-likely]` **`melodic_minor (asc)` is underspecified and stylistically mixed.** In common-practice usage it is not a symmetric up/down collection; in jazz usage it is a stable 7-note “jazz minor.” You need to pick one. For this system, it should explicitly be “jazz melodic minor” or it will create dim #4/#8 ambiguity.

4. `[accept-likely]` **Characteristic-tone tables overstate some tones.** For harmonic minor, `11` (raised 7) is the real identifier; `8` (b6) is shared with aeolian and is not characteristic by itself. For melodic minor, `9` and `11` together distinguish it from aeolian, but if harmony keeps using minor iv/bVI idioms it will still read as plain minor. Characteristic-tone logic needs “must include” and “must avoid contradicting” tables.

5. `[accept-likely]` **“Hit characteristic tone once per 4 bars on a strong beat” is too weak and easy to game.** One accented `#4` does not make lydian if the rest of the piece keeps asserting natural 4 via voicings or passing tones. Better rule: at least 2 exposures per 4 bars across melody+comp, and zero contradiction by the competing degree in cadential or long-note positions.

6. `[accept-likely]` **Mood pools are internally inconsistent with your own stated rule.** `dark_tense: [3,6,1,10]` has no stable major option. `jazzy_cool: [2,7,11,5]` has no plain stable tonic major/minor at all. `folk_innocent: [8,0,5,2]` has no true minor unless you count dorian, which changes the claim. Either remove the rule or fix the pools.

7. `[accept-likely]` **Several mood→mode mappings are likely to sound wrong in practice.** `lydian_dominant` inside `bright_uplifting` is quite tense because of the `b7`; it reads “showy dominant color,” not stable uplift. `phrygian` inside `bluesy_gritty` is a poor fit outside niche fusion/flamenco gestures. `minor_pent` inside `melancholic` biases toward riff/blues language, not “pensive/cinematic.”

8. `[accept-likely]` **Mode selection cannot be independent of harmonic grammar.** Ionian/aeolian/dorian/phrygian/lydian/mixolydian each need distinct chord pools, cadence types, and allowable borrowed functions. If dim #4 reuses one generic progression bank, byte 4 becomes cosmetic. This is most severe for phrygian, lydian dominant, and melodic minor.

9. `[accept-likely]` **Stealing 3 bits from byte 6 is a contract problem, not a detail.** Dim #3 already owns form. Modulation type is tightly coupled to section layout, cadence location, and bar count. Either byte 6 is centrally decomposed by dim #13, or this dimension should not unilaterally consume its high bits.

10. `[accept-likely]` **Your modulation rate is too high for ≤30 s pieces.** `25–40%` is aggressive when many outputs will only have 8–16 bars. A short identicon track needs fast center recognition; frequent modulation reduces memorability and makes distinctness worse. I would cap true modulation closer to `10–20%`, with the rest using modal mixture or secondary-function color only.

11. `[accept-likely]` **The listed modulation types are not equally legible in short forms.** `up a whole step` is a cliché and will read as a gimmick unless the form already repeats material. `V/V tonicization (1 bar)` often will not register at all, especially under fast harmonic rhythm or non-functional modal harmony. `parallel_flip` needs explicit pivot handling; otherwise it sounds like an abrupt palette swap, not modulation.

12. `[accept-likely]` **Modulation mappings are undefined for non-tonal-family modes.** What is the “relative shift” of dorian, blues, or lydian dominant? What is the “parallel flip” target of phrygian? Without per-mode mapping tables, these IDs are not deterministic musical operations.

13. `[accept-likely]` **Key-pool bias by instrument family is weakly justified in 12-TET rendered audio.** For MIDI+synth playback, “good brass keys” or “guitar keys” matter far less than absolute tessitura and idiomatic voicing. Unless a specific sampled library has root-sample artifacts tied to transposition distance, tonic letter name does not buy much. This looks like notation-era bias, not audio-rendering value.

14. `[accept-likely]` **The register rule is too layer-local and can break tonal anchoring.** “Transpose each layer by octave so median note lands in window” can detach the perceived tonic if bass, drone, and comp optimize independently. Bass/drone should anchor the tonic register first; upper layers can adapt around that shared floor.

15. `[accept-likely]` **You need explicit contradiction guards, not just characteristic-tone encouragement.** Examples: lydian should strongly suppress natural 4 in sustained melodic accents; dorian should suppress b6 in cadential spots; mixolydian should suppress leading-tone `7` behavior; phrygian should control natural 2 unless used as chromatic exception. Otherwise the listener hears plain major/minor with occasional color notes.

16. `[accept-likely]` **A better abstraction may be “tonal family” + “melodic color collection,” not one byte = one mode.** Family could be `major / minor / modal-major / modal-minor / dominant / blues`. Then dim #8 can choose pent/blues/jazz-minor subsets as melodic color while dim #4 gets a stable harmonic grammar. That is more deterministic and avoids fake-mode outputs.

17. `[reject-likely]` **Adding more exotic synthetic scales now is probably a mistake.** Quartal language, double harmonic, Hungarian minor, whole-tone, octatonic, etc. would increase distinctness, but they explode the harmony tables and raise “novelty risk” fast. The current omission is defensible if you fix the existing mode contract first.

18. `[accept-likely]` **You are missing church-mode-specific cadence and chord-pool definitions, which matter more than adding new modes.** If dorian, phrygian, lydian, and mixolydian stay, each needs curated cadential moves and tonic-supporting sonorities; otherwise they collapse into aeolian/ionian with costume notes. This is the main missed angle.
