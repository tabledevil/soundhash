# Mood aesthetics

Per-mood design intent. Useful for understanding what a mhash is *trying* to do, separate from any one render's particular output.

| Mood | Intent | Tempo | Modes | Groove pool | Form pool | FX chain |
|---|---|---|---|---|---|---|
| **M0 Ambient** | floating, no goal, pad-led | 54-80 | ionian / aeolian / dorian / lydian / phrygian | ambient_drift / neo_soul / straight_4_4 | through_composed / A_Aprime / theme_var / ostinato_layer / pulse_only | big plate reverb + chorus + low-shelf cut |
| **M1 Ballad** | warm, hopeful, song-form | 64-80 | ionian / aeolian / dorian | straight_4_4 / neo_soul / gospel_12_8 | A_Aprime / ABA / intro_A_fill_A_out / A_outro / AABA / two_arches | medium hall + low-shelf boost + air shelf |
| **M2 Hip-hop** | boom-bap, head-nod, dusty | 70-94 | aeolian / dorian / phrygian / jazz_minor | boom_bap_60 / dilla_feel / mpc60_swing | AB_simple / ABAB / theme_var / AABA / ABCA | short room + tape high-cut + light drive |
| **M3 Downtempo** | meditative groove, off-beat-comfortable | 90-105 | ionian / aeolian / dorian / lydian / jazz_minor | neo_soul / mpc60_swing / dilla_feel / straight_4_4 | through_composed / A_Aprime / theme_var / ostinato_layer / two_arches | wide chorus + dotted-eighth delay + warm room |
| **M4 Latin** | percussive, dance-leaning, modal | 92-112 | ionian / phrygian / mixolydian / aeolian | latin_clave_pocket / dembow_pocket / mpc60_swing | ABAB / AABA / ABCA / theme_var | dry room + presence shelf |
| **M5 Synthwave** | nostalgic glow, neon dusk | 100-120 | ionian / aeolian / lydian | synthwave_tight / straight_4_4 | ABAB / A_build_drop_A / AABA / ABCA / late_drop | chorus + dotted-eighth delay + plate |
| **M6 House** | groove pump, club-shaped | 120-128 | ionian / aeolian / mixolydian | house_pocket / amapiano_pocket / straight_4_4 | ABAB / ABCA / breakdown_form / late_drop / riser_drop_loop | glue compressor → tight room |
| **M7 Techno** | hypnotic loop, dark drive | 128-138 | aeolian / phrygian / dorian | techno_push / straight_4_4 | breakdown_form / riser_drop_loop / late_drop / pyramid / pulse_only | short room + light delay + dark high-shelf |
| **M8 DnB** | snappy break, half-time-feel possible | 85 / 130 / 170-176 | aeolian / dorian / phrygian | dnb_amen_lean / straight_4_4 | ABAB / A_build_drop_A / riser_drop_loop / late_drop | snappy comp + tight room |
| **M9 Glitch / IDM** | broken grid, dissonance-friendly | 90-135 | dorian / phrygian / aeolian / locrian | trap_triplet_hat / straight_4_4 | theme_var / two_arches / pyramid / medley | phaser + ping-pong delay + small room |
| **M10 Cinematic** | breath, build, score-like | 54-110 | aeolian / dorian / lydian / phrygian | straight_4_4 / gospel_12_8 / ambient_drift | ABA / intro_A_fill_A_out / AABA / ABCA / two_arches / plateau_fall | large hall + sub shelf + air shelf |
| **M11 Lofi** | vinyl warmth, jazzy | 70-92 | ionian / aeolian / dorian / jazz_minor / lydian | dilla_feel / boom_bap_60 / mpc60_swing / neo_soul | A_Aprime / ABA / theme_var / ostinato_layer / AABA | tape sat + high-cut + slow chorus + small room |
| **M12 Chillout** | smooth, ambient-leaning, minor-key-comfort | 80-100 | ionian / lydian / aeolian / dorian | ambient_drift / neo_soul / straight_4_4 | through_composed / A_Aprime / ABA / theme_var | wide chorus + 0.45 s delay + plate + air shelf |
| **M13 Simple** | stripped, song-shape, kid-piano | 70-110 | ionian / aeolian | straight_4_4 | A_Aprime / ABA / AABA / pulse_only | barely-there room |
| **M14 Gameboy** | chiptune approximation (LSDj-flavor) | 110-150 | ionian / aeolian / dorian / mixolydian | straight_4_4 | ABAB / AABA / ABCA / ABA / pyramid | dark high-shelf cut + light drive + tiny room |

## Per-mood layer programs (from `_GM_PALETTE`)

| Mood | bass | comp | lead candidates | pad |
|---|---|---|---|---|
| M0 Ambient | 32 (Acoustic Bass) | 88 / 89 / 91 (pads) | 54 / 75 / 73 / 91 / 11 / 70 | 88 / 89 / 94 |
| M1 Ballad | 32 / 33 | 0 (Piano) / 4 (EP1) / 24 (Nylon) | 73 (Flute) / 71 (Clarinet) / 56 (Trumpet) / 68 (Oboe) / 41 (Viola) / 11 (Vibes) | 89 / 91 / 95 |
| M2 Hip-hop | 33 / 34 / 36 | 4 / 5 / 11 | 80 / 81 / 28 / 4 / 5 / 6 | 89 / 95 / 91 |
| M3 Downtempo | 33 / 36 | 4 / 5 / 88 / 89 | 80 / 73 / 78 / 4 / 5 / 11 | 89 / 91 / 94 |
| M4 Latin | 32 / 35 | 24 / 25 / 32 (steel-string family) | 56 / 11 / 24 / 73 / 12 / 25 | 89 / 91 / 94 |
| M5 Synthwave | 38 / 39 / 33 | 81 / 89 / 80 | 81 / 80 / 84 / 87 / 88 / 89 | 90 / 89 / 94 |
| M6 House | 38 / 39 / 36 | 16 / 17 / 81 (organ + lead) | 80 / 81 / 53 / 87 / 89 / 84 | 90 / 89 / 95 |
| M7 Techno | 38 / 39 | 81 / 89 / 90 | 80 / 81 / 87 / 88 / 89 / 90 | 90 / 94 / 89 |
| M8 DnB | 38 / 39 / 36 | 89 / 88 / 91 | 81 / 80 / 88 / 84 / 90 / 87 | 89 / 91 / 94 |
| M9 Glitch | 38 / 39 / 87 | 90 / 91 / 102 | 88 / 81 / 102 / 87 / 100 / 99 | 95 / 91 / 94 |
| M10 Cinematic | 32 / 43 (cello) / 44 (tremolo strings) | 48 / 49 / 50 / 89 (string ensembles) | 60 (French Horn) / 73 / 71 / 11 / 49 / 91 | 49 / 51 / 94 |
| M11 Lofi | 33 / 32 / 35 | 4 / 5 / 0 / 24 (Rhodes / EP / Piano / Nylon) | 4 / 5 / 11 / 73 / 71 / 26 (Jazz Guitar) | 89 / 91 / 94 |
| M12 Chillout | 32 / 33 / 38 | 88 / 89 / 91 / 4 | 73 / 71 / 75 / 91 / 89 / 11 | 89 / 91 / 95 |
| M13 Simple | 32 / 33 | 0 (Piano) / 4 / 24 | 0 / 73 / 11 / 24 / 71 / 25 | 89 / 88 |
| M14 Gameboy | 38 / 39 / 80 | 80 / 81 / 71 (Square / Saw / Clarinet-triangle) | 80 / 81 / 88 / 84 / 99 / 38 | 90 / 88 / 95 |

GM program references: 0 piano, 4 EP1, 11 vibes, 24 nylon, 32 acoustic bass, 33 fingered bass, 38 synth bass 1, 39 synth bass 2, 49/50 strings, 80 square lead, 81 saw lead, 88-95 pads.

## Drum kits per mood

| Mood | Eligible kits |
|---|---|
| M0 Ambient | acoustic-studio / brushes / lo-fi-tape / hand-perc / mallets / music-box-tick / kalimba-tick |
| M1 Ballad | acoustic-studio / brushes / jazz-kit / mallets / music-box-tick |
| M2 Hip-hop | trap-808 / lo-fi-tape |
| M3 Downtempo | jazz-kit / lo-fi-tape / hand-perc / latin-conga / kalimba-tick |
| M4 Latin | hand-perc / latin-conga |
| M5 Synthwave | acoustic-studio / house-909 |
| M6 House | house-909 |
| M7 Techno | house-909 |
| M8 DnB | trap-808 / dnb-breakbeat |
| M9 Glitch | dnb-breakbeat |
| M10 Cinematic | acoustic-studio / brushes / jazz-kit / hand-perc / mallets / latin-conga / music-box-tick / kalimba-tick |
| M11 Lofi | (inherits from M0/M2 fallbacks — no exclusive kit yet) |
| M12 Chillout | (inherits from M0 fallbacks) |
| M13 Simple | (inherits — minimal_pad activation matrix often silences drums) |
| M14 Gameboy | (inherits — GM doesn't have a true chip drum kit; uses house-909 as closest) |

## Listening notes

- **M5 Synthwave** scores lower than its "feel" suggests because the GM saw lead at low velocity in MS-Basic SF3 sounds thin. The arrangement is correct — the soundfont ceiling shows up here.
- **M9 Glitch** is intentionally sharp (DIN sharpness ~1.9 acum across the corpus) — that's the genre.
- **M0 Ambient** outputs land 90% mid-band (4% low / 1% high) on the heuristic. Genre-correct: ambient is mid-range pad music. The heuristic doesn't penalize this any more (relaxed `<8% in any band` rule).
- **M14 Gameboy** is the closest GM patches can get to chiptune. The square+saw+clarinet trio is a deliberate approximation; a true chiptune pass would need a custom synth or a chip-specific soundfont.
- **M2 Hip-hop + jazz_minor** is musically valid (jazz hip-hop crossover) but scores lower because trap-808 + jazz-minor melody is a less-conventional combo than M2 + dorian.

The mood ↔ score correlation isn't strong: a mood's *intent* is more about timbre and arrangement than any single quality number.
