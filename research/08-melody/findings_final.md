# Dimension #08 — Melody (findings final)

Integrates codex + gemini critiques. Each tag listed; ACCEPT (and integrate) or REJECT (with reasoning).

## Codex critiques

**C1. DEGREE-SPACE MISMATCH** — ACCEPT.
The mix of key-relative subsets and chord-relative anchors must be unified. **Fix:** the canonical degree space for melody is **chord-relative** at all times. Key-relative subsets (`diatonic_full`, `penta_*`, `blues`, `hexatonic_no4`, `mode_character`) are *re-projected at table-build time* onto each chord in the progression, producing a per-chord allowed-degree set. Anchors and contour samples both speak the chord-relative space. The resolver no longer mixes spaces.

**C2. CONTOUR SAMPLE COUNT BREAKS AFTER MUTATION** — ACCEPT.
**Fix:** mutation pipeline is now: (a) pick motif rhythm cell A; (b) apply rhythm-only mutation operators (`truncate`, `augment`, `diminute`) to produce the **post-mutation event list**; (c) sample the contour onto that list. Pitch-only ops (`transpose`, `invert`, `sequence`, `retrograde-pitch`) operate on the post-sampled scale-degree sequence. `ornament` is treated specially: it inserts neighbour 16ths *after* contour sampling and the inserted note inherits its degree from the neighboured note ±1 step in the active subset.

**C3. STYLE-COLLISION RHYTHM POOL** — ACCEPT.
**Fix:** split 4/4 motif pool into **idiom-tagged sub-pools**: `pop_basic` (16), `latin_clave` (12), `swing_jazz` (10), `funk_syncop` (10), `lyrical_ballad` (10). The macro mood (dim #11) selects which sub-pools are unlocked; byte 19 then picks within the union of unlocked pools. No more cross-idiom contamination.

**C4. STRONG-BEAT SNAP ERASES DISTINCTIVENESS** — ACCEPT (high priority for the project's distinguishability goal).
**Fix:** add a **hash-selected accent skeleton** — 2 bytes from HKDF (`"soundhash/v1/melody/skeleton"`) define (i) which 4 strong-beat scale-degrees the phrase lands on (out of the chord-tone set, weighted by harmonic function), and (ii) which contour micro-shape (out of 8) interpolates between them. The skeleton survives strong-beat snap because it *is* the snap target. Distinguishability is now a function of the skeleton, not just the contour.

**C5. RETROGRADE/INVERT DESTROY PHRASE GRAMMAR** — ACCEPT.
**Fix:** `retrograde` is removed as a generic op. Replaced with `retro_rhythm` (reverses durations only, pitches forward) and `pitch_invert` is restricted to motifs flagged `symmetry_safe: true` (≤4 notes, no anacrusis, no cadential bar). Both ops are excluded from antecedent/consequent boundary bars and from any bar tagged `cadence` in the phrase plan.

**C6. TESSITURA CLAMP CAUSES OCTAVE FLICKER** — ACCEPT.
**Fix:** clamp is removed from the runtime resolver. Replaced with **phrase-level register planning at table-build time**: the resolver pre-computes the total interval span produced by (motif × contour × all sequence/transpose ops in the phrase plan); if span exceeds tessitura, the operator chain is rejected at filter time so byte 21/26 never selects it. The whole phrase lives in one register unless `is_peak_bar` authorises a one-octave jump.

**C7. BASS GUARD IS TOO WEAK AND TOO LATE** — ACCEPT.
**Fix:** the anti-parallel guard now compares melody and bass on **successive strong beats and on every chord onset**, not just consecutive notes. It detects parallel octaves AND parallel fifths (`(mel_pc - bass_pc) % 12 ∈ {0, 7}` between successive accented notes when motion direction matches). Resolution: instead of octave-shifting (which can blow tessitura — also gemini's G3), substitute the alternate chord-tone closest to the contour sample.

**C8. PHRASE FILTER TOO RIGID FOR 30S** — ACCEPT.
**Fix:** add phrase templates `pickup_then_8`, `7_plus_tag`, `cad_extension`, `1_bar_tail`, `half_cadence_antecedent` to the 16-shape pool, and replace the strict-divisibility filter with a packing function: shapes are valid if `bars + pickup + tag` fits the form's melodic section ±1 bar.

**C9. 5/4 AND 7/8 UNDER-SPECIFIED** — ACCEPT.
**Fix:** every motif cell carries a `meter_grouping` field (e.g. `"3+2"`, `"2+3"`, `"2+2+3"`). Each contour and mutation table also carries compatible-grouping tags. Sub-pool filtering excludes incompatible groupings before byte 19 picks.

**C10. CHORD-CHANGE RULES TOO COARSE** — PARTIAL ACCEPT.
The `land|approach|common_tone` taxonomy is kept (it's enough for 90% of cases), but extended with two event-level tags: `suspension` (hold previous-chord tension over the new chord, resolve down by step on next weak beat) and `tension_keep` (if the current note is a 9/11/13 of the new chord, do nothing). Encoded as a per-bar `chord_change_handling` field with 5 values. Reject the full harmonic-function tagging — overkill for 30-second pieces.

**C11. BLUES/LOCRIAN THEORY-SHALLOW** — ACCEPT.
**Fix:** scale subsets gain a `compatible_palettes` array; harmony palette (dim #04) must be in the array for byte 18 to surface that subset. `blues` requires `palette ∈ {blues, dominant_workout, modal_jazz}`. `locrian` requires explicit locrian-safe harmony pool.

**C12. DETERMINISM ORDERING UNSTATED** — ACCEPT.
**Fix:** the spec now mandates: (a) all JSON tables sort lexicographically by `id` at load; (b) `nearest()` ties → prefer lower scale-degree; (c) `nearest_octave()` ties → prefer same direction as previous melodic motion; (d) HKDF labels are versioned (`soundhash/v1/...`); (e) pre-filters apply in fixed order: mode → time-sig → mood → swing → palette.

## Gemini critiques

**G1. CONTOUR-RHYTHM MISALIGNMENT (N=1 problem)** — ACCEPT.
**Fix:** add `min_onsets` to each contour entry (e.g. `arch.min_onsets=3`, `chant.min_onsets=1`). Filter excludes incompatible (motif, contour) pairs before byte 20 picks.

**G2. TESSITURA CLAMP** — DUPLICATE of C6. Already accepted; same fix applies.

**G3. PARALLEL FIFTHS GUARD MISSING** — ACCEPT.
Folded into C7 fix.

**G4. AMBIGUOUS CHORD-BOUNDARY ONSETS** — ACCEPT.
**Fix:** harmonic-rhythm boundaries are pre-checked: if motif lacks an onset on the chord-change beat, that motif is restricted to `common_tone` handling (held/tied note) and the `land`/`approach` options are excluded for that bar.

**G5. NON-DETERMINISTIC `augment`** — ACCEPT.
**Fix:** `augment` is redefined as: "double durations, span the motif over **two bars** of the phrase plan." It is only legal when a phrase plan has two consecutive identical slots (e.g. `["A","A"]` becomes `["A_aug"]` consuming both). Total duration is preserved; truncation never happens.

**G6. RETROGRADE VS PHRASE ANCHORS** — DUPLICATE of C5. Same fix.

**G7. PERCEPTUAL WASTE ON BYTE 31** — REJECT (with note).
Byte 31 is shared with dim #14 (variation salt) and serves multiple dimensions; reallocating is not within #08's authority. However, point taken that ornament-direction is low-information; we route ornament-direction selection through `byte26 ⊕ bar_index` instead, freeing byte 31 entropy for more structural choices (specifically, choice of accent skeleton from C4). Net: byte 31 stays, but now selects among **8 accent-skeleton archetypes** which is much higher-leverage than ornament direction.

**G8. SCALE SUBSET vs MODE COLLISION** — ACCEPT.
**Fix:** scale subsets are now bitmask templates over the active mode's degree set, not absolute degrees. `penta_major` becomes "drop 4 and 7 from the mode". Applied to phrygian, this drops scale degrees 4 and b7, yielding a phrygian-pentatonic that's modally consistent. Definition tables in `scale_subsets.json` switch from `"degrees":[1,2,3,5,6]` to `"keep_indices":[0,1,2,4,5]` (positions in the 7-degree mode array).

## New sub-dimensions surfaced (hand back to orchestrator)

1. **Idiom palette** (cross-cutting): drums, bass, comp, melody all need to agree on idiom (pop/latin/swing/funk/ballad). Could be its own byte controlled by mood, OR a derived value. Recommend a dedicated flag controlled jointly by dims #5/#6/#7/#8.
2. **Accent skeleton** (new for melody): introduced by C4. Owns 1 byte from HKDF expansion. Most discriminative single feature in the melody pipeline.
3. **Harmonic-rhythm awareness contract**: dim #04 must publish chord-onset beats so #08 can pre-filter motifs. Currently implicit; should be an explicit interface.
4. **Per-phrase register planning**: a precomputation step that lives between #03 (form) and #08 (melody). Could be co-owned.
5. **Symmetry-safe motif tag**: required for invert/retrograde ops (C5). Add as a flag on every motif entry.
