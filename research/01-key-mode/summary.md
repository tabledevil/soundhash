# Dimension 01 — Key & Mode — Summary

## Decisions

**Mode set (10, byte 4):** ionian, aeolian, dorian, phrygian, lydian, mixolydian, harmonic_minor, jazz_minor, lydian_dominant, phrygian_dominant. Excluded: locrian (no stable tonic), whole-tone/octatonic/chromatic (ambiguous), double-harmonic/Hungarian (defer). Pentatonic-major/minor and blues are **demoted** from modes to **byte-18 melody-color overlays** — they cannot support full chordal harmony.

**Key root (byte 3):** uniform `[0..11]` semitone offset from C. The instrument-family key-pool bias (guitar/brass/strings) is dropped — notation-era thinking, inaudible in 12-TET. Tonic tessitura is owned by dim #12 (synth palette).

**Tuning:** 12-TET, A=440, fixed. Alt-tunings deferred.

**Tonic anchor:** bass picks the palette-friendly tonic-MIDI first; comp = bass+12/+24, lead = bass+24/+36, drone = bass-12. Single canonical anchor instead of per-layer drift.

**Mood → mode pool:** 9 mood classes, each ≥3 modes including ≥1 diatonic-7-note option. Lydian-dominant lives in `jazzy_cool`/`cinematic_dramatic`, not `bright_uplifting`. Phrygian-dominant slots into `dark_tense`. Pent/blues no longer appear here.

**Characteristic-tone enforcement:** each mode publishes `must_include` and `must_avoid` (the contradicting degree). Rule: ≥2 strong-beat exposures of must-include per 4 bars across melody ∪ comp; zero must-avoid hits on cadences or long notes. Stops modes from collapsing into "secretly major/minor."

**Modal interchange:** owned by dim #4 (uses must-include as borrowable-tone palette); not a modulation.

**Brief modulations:** capped at 10–15% of pieces. Types: `none`, `parallel_flip` (explicit pivot), `relative_shift` (last 8 bars, tonal-family modes only), `step_up_whole` (bright_uplifting only, requires prior section repeat + V-of-new-key pivot). `V/V tonicization` removed and reassigned to dim #4 as a chord-substitution color. Per-mode `modulation_targets` table makes every modulation deterministic. Modulation-type bits come via HKDF (`HMAC(salt, "soundhash/v1/modulation")[0]`) — no theft from byte 6 / dim #3.

**Harmonic-grammar handoff:** each mode publishes a `grammar` id (functional_major, modal_dorian, jazz_LD, modal_phrygdom, …). Dim #4 implements one chord-pool + cadence-set per grammar. Modal cadences: dorian bVII–i & IV–i; phrygian bII–i; lydian II–I; mixolydian bVII–I.

## Byte budget
- Byte 3: key root, table 12.
- Byte 4: mode, table 3–6 (mood-filtered).
- Byte 18 (melody): overlay choice, mode-compatibility-filtered.
- Modulation type: HKDF, 3 bits, 5-entry table.

## Handoffs
- **#4 Harmony** owns chord pools + cadences per `grammar`, modal mixture, V/V color.
- **#8/#18 Melody** owns char-tone enforcement and pent/blues overlay choice.
- **#11 MIME→mood** drives mode-pool prefilter.
- **#12 Synth palette** owns per-layer tessitura.
- **#13 Decode architecture** confirms HKDF for modulation bits.
- **#14 Distinguishability** verifies same-root different-mode collisions are audibly distinct.

## Residual risks
- Gemini adversarial critique unavailable (HTTP 429 across all attempted models); only codex provided pressure. Recommend re-critique once quota resets.
- Phrygian-dominant addition expands dim #4's grammar burden.
- 10–15% modulation cap and step-up-requires-repeat rule should be validated against rendered samples in dim #14.
