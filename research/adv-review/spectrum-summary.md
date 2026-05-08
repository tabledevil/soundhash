# ADV-REVIEW: Musical Spectrum Coverage

Reviewers: codex (gpt-5-codex) + gemini (3.1-pro). Source: 500-hash audit + assets/v1/{moods,tempo_pools,forms,family_to_moods,harmony/progressions}.json + showcase tables.

## Verdict
The system has acceptable **key coverage** but weak **mode coverage**, poor **tempo coverage**, **inflated form count**, and a **mood taxonomy that overstates diversity**. The taxonomy nominally offers 15 moods but, after collapsing perceptually-overlapping clusters, the audible spectrum is closer to **5–6 buckets**. Both reviewers converge on this independently.

## Findings

### 1. Keys (12) — PASS
All 12 roots reached, range 33–55 hits per key over 500 samples. Uniform enough.

### 2. Modes — PARTIAL FAIL
- 6 of 7 diatonic modes used (ionian/aeolian/dorian/lydian/mixolydian/phrygian).
- **Locrian: absent** (no truly unstable harmony surface).
- `jazz_minor` exists inside progressions but is **orphaned** — no mood declares it as a mode, so it never drives output mode.

### 3. Tempo — FAIL
Distribution heavily skewed slow:
- Bulge at 60–100 BPM (354/500 = 71%).
- **Dead zone 140–170 BPM** (only DnB hops over it, landing at 170+).
- **No <60 BPM** (no funeral / sub-doom).
- **No 145–165 BPM** zone where rock / punk / metal / hardcore live.

### 4. Forms (24) — INFLATED
Most outputs are 8 bars; forms with `min_bars >= 12` (intro_A_fill_A_out, A_build_drop_A, AB_with_fill, two_arches, late_drop, riser_drop_loop, plateau_fall, pyramid, medley, AAB, ABA, ABCA) rarely or never realise. Even among realised forms, `through_composed` ≈ `pulse_only` perceptually at 8 bars; `A_Aprime` / `theme_var` / `AABA` collapse to "loop with mild wrinkle." **Effective form vocabulary in the 8-bar regime is ~6–8, not 24.**

### 5. Mood overlap (the central problem)
67% of audited outputs land in M0/M11/M12/M13. The "Soft Slow Blob":
- **M0 Ambient + M1 Ballad + M3 Downtempo + M11 Lofi + M12 Chillout + M13 Simple** all share 70–105 BPM band, ionian/aeolian/dorian modes, and have no enforced timbral / instrumentation differentiator.
- **M6 House vs M7 Techno**: only 10 BPM apart, both 4/4, both share aeolian — relies entirely on groove sample quality.

### 6. Missing genres
Both reviewers agreed on the same structural holes (no cosmetic disagreement):
- **Rock / Alt-Rock / Punk** (fills 145–165 BPM gap).
- **Metal / Hardcore** (locrian/phrygian + 120–160 BPM, double-kick).
- **Funk / Disco** (16th syncopation, slap bass, mixolydian/dorian).
- **Reggae / Ska / Dub** (off-beat skank, dropped downbeat).
- **Soul / R&B / Gospel** (gospel_12_8 groove exists but no mood owns it).
- Secondary: country/folk acoustic, real classical/orchestral (cinematic ≠ contrapuntal), world (afrobeat, k-pop, Indian, gamelan).

### 7. M11/M12/M13/M14 progression coverage
**Zero progressions explicitly tag M11–M14.** They fall back to other-mood progressions, further blurring identity (Lofi has no Lofi-specific harmony grammar).

### 8. 15 moods @ 1000 files?
**No, not as currently distributed.** With 67% concentration in soft slow moods, a 1000-file dump produces ~320+ outputs each of M0/M11/M12/M13. Sameness fatigue within minutes. Either rebalance the family→mood weights or differentiate the soft cluster much harder.

## Round 2 — agreed actions

### A) The 5 redundant moods (consensus across both reviewers)
1. **M0 Ambient**
2. **M11 Lofi**
3. **M12 Chillout**
4. **M13 Simple**
5. **M3 Downtempo** (with M1 Ballad as honourable mention)

Recommended: merge M11+M12 outright; merge M1+M13; force M0 to drone-only, M3 to glitchier syncopation, M11/M12 to enforced lo-fi degradation+sidechain. Without explicit timbre/groove/harmonic-rhythm separators these stay redundant on principle.

### B) The 5 missing genres to add (consensus)
1. **Rock / Punk-Garage** (145–165 BPM, power-chord power voicing, driving 8ths) — plugs tempo gap.
2. **Metal / Hardcore** (120–160 BPM, locrian/phrygian, double-kick, drop-tuned) — adds the only path to true dissonance.
3. **Funk / Disco** (100–120 BPM, 16th syncopation, mixolydian/dorian, slap-bass articulator).
4. **Reggae / Ska / Dub** (70–90 BPM, off-beat skank, dropped downbeat) — zero rhythmic overlap with current moods.
5. **Soul / R&B / Gospel** (60–100 BPM, 12/8 triplet feel, ii-V-I jazz harmony) — distinguishes from ballad via groove and harmonic density.

## Concrete recommended changes (low-risk, high-impact)
- Add a `locrian` mode option to a new `Metal` or `Dissonant` mood.
- Promote `jazz_minor` from progression-only to a declared mood mode (Cinematic or Jazz mood).
- Rebalance `family_to_moods.json` so text/image/audio/video do not all lean on M0/M11/M12/M13. Cap any mood at ≤2 file-family candidate slots.
- Add **150**, **155**, **160**, **165** BPM to a new Rock/Punk mood; add **52**, **56** to Ambient for sub-funeral space.
- Tag at least 6 progressions per mood for M11/M12/M13/M14 (currently 0).
- Cull or gate forms whose `min_bars >= 12` so they only spawn in T3/T4 contexts (already declared but not honoured per audit).
- For 8-bar outputs, collapse the form pool to the audibly distinct subset (~6–8 forms) and use the freed entropy bits for groove/timbre variation.
