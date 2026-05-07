# soundhash — Design Document (v1 draft)

> Deterministically convert a file's SHA-256 hash (and optionally its MIME type) into ≤30 s of pleasant, music-theory-correct audio that is easily distinguishable between files. Same hash → bit-identical output.

This document is the synthesis of **14 parallel research dimensions**, each followed by an adversarial pass with `codex` and (where quota allowed) `gemini`. Per-dimension artifacts live under `research/<NN-slug>/`.

---

## 1. Goal & contract

- **Input:** SHA-256 of file bytes (32 bytes). Optionally: MIME type.
- **Output:** ≤30 s audio (canonical: 44.1 kHz / 16-bit stereo WAV; FLAC also bit-identical; MP3/OGG perceptually identical only).
- **Determinism:** identical inputs → identical SongSpec → identical MIDI → identical WAV under a pinned binary contract (Docker image). Cross-arch perceptual identity (ViSQOL > 4.5) is the cross-arch contract.
- **Distinguishability:** hierarchical sensitivity. Byte 0 changes the mood (very audible). Byte 31 changes only mutation salt (subtly audible). MIME-coherent neighbors are a *feature*: similar files sound related.
- **Stability:** v1 will produce identical output forever; bug-fixes go to v2. Spec version embedded in every output.

## 2. Architecture overview

```
file ──┬─ sha256() ─────────────────────┐
       └─ libmagic ─→ MIME family ─→    │
                                        ▼
                       ┌──────── decode.hash_to_spec() ────────┐
                       │  HKDF-SHA256 with domain-separated   │
                       │  labels → 32-byte macro stream +     │
                       │  unbounded sub-streams                │
                       │  ↓ (constraint propagation)           │
                       │  SongSpec  (pure data; every note,    │
                       │  velocity, CC, articulation resolved) │
                       └──────────────────────────────────────┘
                                        │
                       ┌─ render.midi → .mid (pinned mido)
                       └─ render.audio → .wav (pinned FluidSynth + sfizz)
                                        │
                       ─→ loudness norm (-16 LUFS, -1.5 dBTP) → metadata embed
```

The decode is **pure** (no I/O, no clock, no system random). All randomness is HKDF-derived from the hash. The render is **dumb** (no decisions; just plays the spec).

## 3. Mood taxonomy (M0–M10)

| ID | Mood | BPM range | Default time-sigs |
|----|------|-----------|-------------------|
| M0 | Ambient / Drone | 60–80 | 4/4, 6/8, 3/4 |
| M1 | Ballad / Cinematic | 64–80 | 4/4, 6/8, 12/8 |
| M2 | Hip-hop / Boom-bap | 70–94 | 4/4 |
| M3 | Downtempo / Trip-hop | 90–105 | 4/4 |
| M4 | Latin / Afro | 92–112 | 4/4, 6/8 |
| M5 | Synthwave / Pop | 100–120 | 4/4 |
| M6 | House | 120–128 | 4/4 |
| M7 | Techno | 128–138 | 4/4 |
| M8 | DnB / half-time-feel | 85 / 130 / 170–176 | 4/4 |
| M9 | Glitch / IDM | 90–135 | 4/4, 7/8, 5/4 |
| M10 | Cinematic / Trailer | 70–110 | 4/4, 12/8, 3/4 |

Each mood declares: tempo pool, mode whitelist, kit whitelist, synth palette, FX policy, voicing-style whitelist. Mood is selected from `family.candidates[byte0 % len]` where `family` is determined by MIME (or hash byte 0 in `--mime=off` mode). Byte 1 is sub-flavor (brightness).

**MIME → mood family mapping** (full table in `assets/v1/family_to_moods.json`): text-code → {synthwave, techno, glitch, house}; image → {ambient, downtempo, ballad, synthwave}; audio → {hip-hop, latin, house, ballad}; video → {trailer, dnb, synthwave, techno}; archive → {glitch, boom-bap, techno, downtempo}; document → {ballad, ambient, downtempo, trailer}; spreadsheet → {techno, house, synthwave, glitch}; executable → {techno, glitch, synthwave, dnb}; font → {ambient, ballad, synthwave, downtempo}; 3D-model → {trailer, ambient, synthwave, techno}; web-asset → {house, synthwave, glitch, hip-hop}; database → {techno, glitch, ambient, downtempo}; unknown → {ambient, downtempo, glitch, ballad}.

## 4. Byte budget (master 32-byte map)

Reconciled by dim #13 across all 14 dimensions.

| Byte | Dim | Decision | Table size |
|---|---|---|---|
| 0 | 11 | macro mood (within MIME family) | 4 of 11 |
| 1 | 11 | mood sub-flavor | 8 |
| 2 | 2 | tempo bucket (3 bits index + 5 bits ±0.5% nudge) | 4–8 + nudge |
| 3 | 1 | key root | 12 |
| 4 | 1 | mode | 3–6 (mood-filtered, of 7) |
| 5 | 2 | time-sig + swing combo (joint) | 4–12 per mood |
| 6 | 3 | form template | 16–26 |
| 7 | 4 | progression bank index | 64 (mode-filtered to ≤16) |
| 8 | 4 | voicing style + sec-dom + mixture toggle | 10 styles + bits |
| 9 | 5 | drum kit (mood-filtered) | 12 |
| 10 | 5 | drum pattern A (low nib) + B (high nib) | 8 each |
| 11 | 5 | fill arming + style mods | 16 |
| 12 | 5 | escalation algo (low nib) + de-escalation (high nib) | 8 each |
| 13 | 6 | bass archetype + mutation seed | 36 + seed |
| 14 | 6 | bass synth + octave + articulation + density flag | 8 + bits |
| 15 | 7 | comp role | 12 |
| 16 | 7 | comp synth | 16 |
| 17 | 7 | comp pattern variant (strum/arp/chord-rhythm) | per role |
| 18 | 8 | melody scale subset (bitmask over mode) | 8 |
| 19 | 8 | melody motif rhythm | 32 (per time-sig) |
| 20 | 8 | melody contour | 32 |
| 21 | 8 | melody phrase shape | 16 |
| 22 | 8 | melody tessitura (hi nib) + lead synth (lo nib) | 8 + 16 |
| 23 | 9 | aux-layer mask + counter-melody mode + drone policy | 256-bitfield |
| 24 | 3 | energy curve template (hi nib) + section perturb (lo nib) | 16 + ±1 |
| 25 | 3 | layer activation matrix preset | 16 |
| 26 | 3+8 | per-bar mutation seed + accent skeleton archetype | 256 |
| 27 | 10 | velocity curve + humanization profile + vibrato + portamento | 16+6+bits |
| 28 | 12 | FX preset (reverb size + delay time + saturation) | 16 |
| 29 | 12 | FX send levels preset | 8 |
| 30 | 12 | mix balance preset | 8 |
| 31 | 13 | variation salt (XOR onto per-bar bytes only) | 256 |

**Modulo bias:** zero for table sizes ∈ {2,4,8,16,32,64,128,256}. For odd sizes (12 keys, 7 modes) we accept ≤2.7% bias; rejection sampling with HKDF top-up is used where distinguishability is critical (mood, form). Tables > 256 use two-byte big-endian (`(b0<<8|b1) % len`, bias ≤ 0.4%).

## 5. HKDF expansion (RFC 5869)

```
prk = HMAC-SHA256(salt="soundhash-v1", ikm=sha256_of_file)
expand(label, n) = HKDF-Expand(prk, info=f"soundhash/v1/{label}", L=n)
```

**Reserved labels** (registry in `assets/v1/labels.json`; CI rejects unregistered labels):

| Label | Bytes | Purpose |
|---|---|---|
| `macro` | 32 | the main 32-byte map |
| `perbar/drums/<i>` | 4 / bar | drum mutation, ghosts, fill triggers |
| `perbar/bass/<i>` | 2 / bar | bass octave jumps, mutation |
| `perbar/comp/<i>` | 2 / bar | comp inversion, voicing alt |
| `perbar/melody/<i>` | 4 / bar | motif transformation, ornaments |
| `perbar/aux/<i>` | 2 / bar | aux layer gates |
| `earcandy/positions` | 8 | ear-candy event positions |
| `earcandy/types` | 8 | ear-candy event types |
| `expression/velocity/L<n>` | 16 | per-note velocity micro-shape |
| `expression/cc/L<n>` | 16 | per-channel CC stream params |
| `harmony/substitutions` | 8 | per-bar chord-substitution choice |
| `harmony/modulation` | 1 | brief-modulation type |
| `melody/scaleorder` | 8 | scale-subset note-ordering perm |
| `melody/accent_skeleton` | 4 | accent-skeleton archetype shape |
| `groove/microtiming` | 8 | per-instrument-role timing offsets |
| `render/synthparams/L<n>` | 16 | synth dial-tweaks within preset |
| `dither` | 1024 | TPDF dither stream for limiter/quantize |

Worst-case typical song uses ~224 bytes total — HKDF gives this for free.

## 6. Dimension summaries

Full proposals in `research/<NN>/`. One paragraph each:

**#01 Key & Mode** — 7 modes (ionian, aeolian, dorian, phrygian, lydian, mixolydian + jazz_minor), pent/blues demoted to byte-18 melody overlays. Each mode publishes `must_include` and `must_avoid` degrees so the mode is audibly surfaced (≥2 strong-beat exposures of characteristic tones per 4 bars). Brief modulations capped 10–15% rate, 4 types: none / parallel-flip / relative-shift / step-up-whole, gated per mode. Single canonical tonic-MIDI anchor.

**#02 Tempo & Groove** — 9 mood-tempo pools (table above). Time-sig × groove are picked **jointly** via byte 5 to forbid bad combos (16th-swing at 60 BPM, half-time below 130 BPM). 16 named groove templates with PPQ-480 per-instrument-role offsets (Dilla-feel, MPC60, neo-soul, house-pocket, techno-push, trap, dembow, amapiano, gospel-12/8, deterministic-humanize). 12/8 and 6/8 use dotted-quarter as the beat unit. Bar-count-vs-tempo table guarantees every form lands inside [27.5, 30] s including reverb tail.

**#03 Form & Energy** — 24+ forms (ABA, AABA, A-build-drop, intro_A_fill_A_out, late_drop, ostinato, rondo, jazz-head). 16 energy curves (rise, arc, U, two-arches, sawtooth, plateau-fall…). 16 layer-activation matrices. Density bins {sparse, light, normal, dense} drive per-layer parameters. Form ↔ curve compatibility encoded; drops require BPM ≥ 132. Render to 32 s, deterministic 200 ms cosine fade-out, no hard truncation.

**#04 Harmony & Voicing** — 96 progressions in Roman numerals, tagged (mode, mood-tag, length, cadence). Roman numerals carry explicit *quality* (`maj7`, `m7`, `dom7`…) and bass inversion. 10 voicing styles. Voice leading is **precomputed** per (progression × style × mixture-variant); cost function penalizes hidden 5/8, doubled leading tone, voice-out-of-range. Modal mixture is pre-authored per progression slot, not random. Tendency-tone resolutions in `resolution_rules.json`. Empty-bucket fallbacks for every (mode,mood) pair.

**#05 Drums & Fills** — 12 kits (acoustic, brushes, jazz, trap-808, house-909, lo-fi, hand-perc, mallets, latin, dnb-breakbeat, music-box, kalimba). 480 patterns (5 density × 8 patterns × 12 kits). 96 fills indexed by (Δ-density). 8 escalation algorithms + 8 de-escalation (linear-add, subdivision-double, tom-rollup, snare-roll-crescendo, hat-density-ramp, reverse-cymbal-sweep, ghost-note-stack, polyrhythm-overlay). Style coverage includes funk, trap-rolls, footwork, garage 2-step, breakbeat, Amen, bossa, son-clave, tresillo, bembé.

**#06 Bass** — 36 archetype patterns expressed as degree-rhythm grids relative to current chord root (R, 3, b3, 5, 6, b6, b7, 7, 8, 9, CH, rest, tie). 8 bass synths with mood-filtered octave windows. Chromatic passing tones are flag-gated. Hard rule: bass top ≤ melody bottom − M3, fall back to octave-down + root if violated. Coverage includes Motown walks, ska upstroke, country alternating, gospel walk-up, latin tumbao, acid 303, trap 808 glide, Reese, dub.

**#07 Comping** — 12 roles (pad_sustain, piano_stab, piano_arp, guitar_strum, muted_skank, ep_comp, rhodes, organ_pad, synth_arp, brass_stabs, harp_gliss, no_comp). 10 strum patterns, 12 arp shapes, 11 chord-rhythm patterns, 16 comp synths. Hard guardrail: `comp.top ≤ melody.median − 5 semitones`. Density couples to energy bins. Polyphony budgets per role.

**#08 Melody** — Single chord-relative degree space. 32-64 motif rhythm cells per time-sig (idiom-tagged sub-pools). 32 contour shapes (`min_onsets`, `anchor_end`, `peak`). 8 scale subsets as bitmasks over current mode. 16 phrase shapes (AABA, period, sentence, Q/A, climb-release, hook-first). 9 mutation operators (transpose ±N, invert, retrograde, truncate, augment, diminute, ornament, sequence ±N). Accent skeleton (4 strong-beat chord tones + 1 of 8 micro-shapes) is the highest-distinguishability single feature. Anti-parallel guard at strong beats, golden-section peak, hook repetition.

**#09 Aux Layers** — 12 layer types (counter-melody, harmony-double, drone, pad-wash, oohs, ad-lib stab, riser, downer, texture, fx-oneshot, bell-sparkle, counter-rhythm). Clutter budget: max-aux scales 0/1/2/3/4 across energy thresholds 0.20/0.45/0.70/0.90. Texture is exempt (always-on bus). Counter-melody modes: parallel-3rd / parallel-6th / contrary / call-response with phrase-end lookahead. Drone clash check is interval-content vs current chord tones (mute on m9/tritone friction). Ear-candy is 2/4-bar motif templates per section, ≥80% on off-beats.

**#10 MIDI Expression** — Abstract intent layer (e.g. `cc_intent="brighten", amount=0.4`) lowered by renderer using a synth capability matrix (`pitch_bend_range_honored`, `breath_aware`, `aftertouch_aware`, `cc14bit_supported`, `keyswitch_map`). 16 velocity curves, 19 articulations (incl. fall/doit/scoop/keyswitch), 6 humanization profiles, per-mood per-layer CC routing. Pitch bend as fraction of declared RPN range; never on ch10 drums. CC merge rule prevents collisions. Marcato detune via RPN fine-tune cents (NOT pitch-bend).

**#11 MIME → Mood** — 13 family taxonomy (text-code, image, audio, video, archive, document-pdf, spreadsheet, executable, font, model-3d, web-asset, database, unknown). MIME detected via pinned `python-magic 0.4.27` + frozen `magic.mgc`. Family pre-filters mood pool before byte 0 is consumed. CLI overrides: `--mime=auto|off|strict|<slug>`, `--mime-family=<id>`, `--mood=<M0..M10>`. Provenance: detected MIME, libmagic version, magic.mgc SHA, family, override — embedded in MIDI track-0 and WAV INFO chunks. No file-size or filename influence.

**#12 Rendering** — Stage 1: `mido` (PPQ 480, Type 1, fixed event sort). Stage 2: FluidSynth `--fast-render` for general MIDI; sfizz for piano/strings; pure-Python numpy mixer for drum one-shots. Render flags: 44.1 kHz, `synth.interpolation=4`, `cpu-cores=1`, no internal reverb/chorus. Reverb via FIR convolution with pinned IRs (or `pedalboard.Reverb` Docker-only). Loudness: `pyloudnorm` to -16 LUFS, 8×-oversampled limiter at -1.5 dBTP. Default soundfont: build CC0 `soundhash_curated_v1.sf2` < 25 MB. Synth pool is mood-filtered per role; selection uses existing layer bytes.

**#13 Hash Architecture** — HKDF-Expand(SHA-256) with 17 reserved domain-separated labels. 32-byte macro stream + per-bar / per-layer sub-streams. Static pre-filter strategy (build-time per (mood,mode) tables). Rejection sampling with 64-pull cap and HKDF top-up for non-power-of-2 tables when distinguishability matters. Decoder is pure: `hash_to_spec(hash, mime, version) -> SongSpec`. Pinned invariants I1–I10 (idempotence, no I/O, manifest integrity, label-registry membership, range guards, length ≤30 s, bit-flip sensitivity, no-empty-filter, salt scope).

**#14 Perceptual & Determinism** — Determinism is byte-identical *within an arch* (Docker canonical) + cross-arch *perceptually* (ViSQOL > 4.5, Track-B feature distance < 0.005). FTZ/DAZ on, FMA off, single-thread BLAS, soxr precision=33, FluidSynth native stereo render, locale `LC_ALL=C`. Loudness: -16 LUFS integrated, ≤-14 LUFS-S, intro 3 s LUFS-S ≥ -20 (audibility). Length: song-end marker ≤ `32 - RT60 - 0.2` s so reverb tail never gets sheared. Stereo: drop Haas; mood-keyed precomputed decorrelation IRs. Metadata: parallel iXML + bext RIFF chunks, canonical chunk ordering, ID3v2.4 alphabetical frames, FLAC vendor block override. Distinguishability score is heuristic (PHD), with ViSQOLAudio + 75-dim feature cosine + CLAP embedding as gold standards.

## 7. Determinism contract

1. **Within-arch byte-identity** under pinned Docker image (`linux/amd64`).
2. **Cross-arch perceptual identity:** ViSQOL > 4.5, feature cosine distance < 0.005.
3. Pinned: Python, numpy, scipy, soxr, mido, FluidSynth, sfizz, pyloudnorm, pedalboard. SHA-pinned soundfonts/sfz/IR-files.
4. Render flags: 44.1 kHz, 16-bit stereo, `synth.cpu-cores=1`, no internal reverb/chorus, deterministic interpolation, integer-tick math, fixed PPQ=480.
5. CFLAGS for any C extensions: `-ffp-contract=off`, FTZ=DAZ=on, no FMA contraction.
6. Locale `LC_ALL=C`, BLAS thread-count=1.
7. No system clock, no system random — all entropy from HKDF.
8. Canonical chunk ordering for WAV/FLAC/MP3 metadata.
9. CI golden-corpus regression: 1024 hashes × per-arch wheels.

## 8. Distinguishability test plan

- **Phase 0:** within-arch byte-identity (CI golden files).
- **Phase 0.5:** cross-arch perceptual identity (ViSQOL).
- **Phase 1:** LUFS envelope + intro-audibility checks.
- **Phase 2:** N=1000 random hashes; ViSQOL pairwise primary metric; PHD as cheap monitor; CLAP embedding tertiary.
- **Phase 2.5:** within-MIME-family minimum-distance acceptance (avoid mood-coherence collapsing distinctiveness).
- **Phase 3:** byte-flip adversarial neighbor sweep.
- **Phase 4:** ABX human study (≥30 listeners, ≥95% across-mood, ≥70% within-mood).
- **Phase 5:** earworm heuristics (distinctive opening 2 bars, recurring 3-5 note hook, B-section contrast, unique drum onset hash, recognizable cadence).

## 9. Adversarial-pass coverage

| Dim | Codex | Gemini | Notes |
|---|---|---|---|
| 01 | ✅ | ❌ 429 | recommend gemini re-pass once quota resets |
| 02 | ✅ | ✅ | full coverage |
| 03 | ❌ | ✅ | codex was busy |
| 04 | ✅ | ✅ | full coverage |
| 05 | self-only | self-only | adversarial inline |
| 06 | self-only | self-only | adversarial inline |
| 07 | self-only | self-only | adversarial inline |
| 08 | ✅ | ✅ | full coverage |
| 09 | ✅ | ✅ | full coverage |
| 10 | ✅ | ✅ | full coverage |
| 11 | ✅ | ❌ 429 | re-pass on quota reset |
| 12 | self-only | self-only | inline; web research substituted |
| 13 | ✅ | ✅ | from prior run on disk |
| 14 | ✅ | ✅ | full coverage |

8/14 fully covered, 2/14 partial, 4/14 self-only. Recommended follow-up: re-run codex+gemini on dims 5, 6, 7, 12, and gemini on 1/3/11 once quota resets.

## 10. Open sub-dimensions surfaced

Items the research surfaced that may justify their own design pass:

- **Idiom palette** as a cross-layer concept (drives drums + bass + comp + melody sub-pool selection coherently).
- **Accent skeleton** as a named sub-dimension under #08 (highest distinguishability per byte).
- **Pattern-overlay grooves** (clave, dembow, amapiano) — owned jointly by #05 + #06.
- **Half-time as macro-rhythm flag** owned by #03 + #05.
- **Per-instrument-role timing routing** as a renderer requirement.
- **Decorrelation IR set** for stereo (post-Haas-removal) — new asset class.
- **Inversion / bass-figure** as a dim co-owned by #04 + #06.
- **12-bar blues macro form** belongs in #03 not #04.
- **Compressor stage** (deterministic) added before the limiter — currently underspecified.
- **Sidechain ducking** deserves its own sub-dim.
- **Vocal-chop licensing** — v1 uses synth-stab approximation only.

## 11. Repo layout

```
soundhash/
  DESIGN.md                  ← this document
  README.md
  pyproject.toml
  src/soundhash/
    __init__.py
    cli.py                   ← `soundhash <file>` entry point
    decode.py                ← hash_to_spec + HashStream + HKDF
    spec.py                  ← SongSpec dataclasses
    mime.py                  ← MIME → family resolver
    theory.py                ← scale/chord helpers (placeholder)
    tables/__init__.py       ← static-table loader + manifest validator
    render/midi.py           ← SongSpec → .mid
    render/audio.py          ← .mid → .wav (FluidSynth/sfizz)
  assets/v1/
    manifest.json            ← bundle hash + version pins
    labels.json              ← HKDF label registry
    moods.json               ← M0–M10 + sub-flavor
    mime_families.json       ← (from research/11)
    family_to_moods.json     ← (from research/11)
    forms.json               ← (from research/03)
    energy_curves.json       ← (from research/03)
    layer_activation.json    ← (from research/03)
    aux_layers.json          ← (from research/09)
    expression/velocity_curves.json   ← (from research/10)
    expression/articulation.json      ← (from research/10)
    expression/cc_routing.json        ← (from research/10)
    expression/humanization_profiles.json ← (from research/10)
    synth_pool.json          ← (from research/12)
    versions.lock.json       ← (from research/12)
    progressions.json        ← TODO: build from research/04 spec
    voicings.json            ← TODO
    drumkits.json            ← TODO
    drum_patterns/<kit>.json ← TODO
    bass_patterns.json       ← TODO
    comp_*.json              ← TODO
    motif_rhythms.json       ← TODO
    contours.json            ← TODO
    scale_subsets.json       ← TODO
    phrase_shapes.json       ← TODO
  tests/
    test_decode_invariants.py  ← I1–I10 from decoder_api.py
    test_byte_budget.py        ← every byte's ownership assertion
    test_label_registry.py     ← reject unregistered HKDF labels
  research/                  ← per-dimension findings (already populated)
```

## 12. Roadmap — vertical slice plan

1. **Repo skeleton** ✅
2. **HKDF + decoder skeleton** ✅
3. **All-mood end-to-end vertical slice** ✅ (Apr 2026): every mood, real MIDI + WAV.
4. **Listen test:** generate ~50 hashes per mood; manual audit; prune bad table entries — TODO.
5. **Distinguishability harness**: implement Phase 0–2 of the test plan — TODO.
6. **LUFS normalization** + ITU-R BS.1770 loudness target -16 LUFS — TODO.
7. **Cross-arch wheels + Docker canonical** — TODO.

## 13. Implementation status (current)

End-to-end pipeline working: SHA-256 → SongSpec → MIDI (5 tracks) → WAV.

### Wired in `src/soundhash/`

- **`decode.hash_to_spec(hash, mime)`** — pure HKDF-driven walker over the 32-byte budget. Picks: mood (MIME-family-filtered), tempo (with ±0.5% nudge), key root, mode, progression (mood ∩ mode), drum kit + drum pattern, bass pattern + synth, comp role + synth + chord-rhythm pattern, melody motif + contour + scale-subset.
- **`theory.resolve_progression`** — Roman numeral → (root_pc, root_midi, chord_pcs, quality) per bar.
- **`render.midi`** — emits Type-1 PPQ-480 MIDI with 5 tracks (meta + bass + comp + drums on ch10 + lead). All events sorted by absolute tick before delta computation. Strong-beat (beats 0 and 2 in 4/4) chord-tone snap on the lead.
- **`render.audio`** — shells out to `fluidsynth -ni`, reads back the WAV, then trims to ≤30 s and applies a 5 ms fade-in + 200 ms cosine fade-out. Output is 16-bit/44.1 kHz stereo, deterministic across runs of the same hash.
- **`mime.detect_mime` / `family_for_mime`** — pinned to `python-magic` with extension fallback for `octet-stream`. (Not yet enforcing the strict SHA-pinning of `magic.mgc`; that lands with the determinism-contract iteration.)

### Verified contract (within-arch byte-identity)

- Same hash → same SongSpec.
- Same SongSpec → same MIDI bytes.
- Same MIDI → same WAV bytes (under bundled VintageDreamsWaves-v2.sf2 + fluidsynth 2.5.4 + Apple Silicon).
- 16 tests pass (10 decoder invariants + 5 MIDI render + 1 audio render).

### Known gaps before v1 freeze

- Audio render pinning is host-bound (Mac Apple Silicon / fluidsynth 2.5.4 / brew-bundled SoundFont). Cross-arch will require either Docker canonical or per-arch wheel testing. Currently the contract is "byte-identical *for me right now*", not "byte-identical universally".
- LUFS normalization not yet applied; the WAV is whatever FluidSynth produces minus reverb/chorus.
- Drum/bass/comp patterns play their *own* rhythms on top of each other without an energy curve filtering them — every section is "full density".
- Form selection is a constant (8 bars, loop progression). Form-table (`forms.json`) is on disk but not consumed.
- Mood-keyed synth selection (`synth_pool.json`) not consumed; layer programs are fixed (33/4/80) regardless of pick.
- HKDF labels beyond `macro` are reserved but not yet consumed (per-bar mutation, ear-candy, expression, dither).

### Repo footprint

- 58 JSON tables under `assets/v1/` (all valid).
- ~700 LOC of Python in `src/soundhash/`.
- 14 dimensions of research findings in `research/`.
