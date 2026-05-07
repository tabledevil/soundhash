# Dimension 01 — Key & Mode — findings_final

Codex critique was substantial (18 numbered points). Gemini failed with `RESOURCE_EXHAUSTED` 429s and is captured as `[CLI ERROR]` in `gemini_review.md`. Below is an integrated revision.

## Critiques and dispositions

### From codex_review.md

1. **C1 [accept]** Pentatonic & blues are weak as global modes — they lack 4/7 or 2/6 needed by the harmony layer. **Action:** Demote `major_pent`, `minor_pent`, `blues` from byte-4 *modes* to **byte-18 melody-color overlays**. Byte 4 keeps a "host mode" (e.g. ionian/aeolian/mixolydian); the pentatonic/blues subset is layered on top of that mode for the lead.
2. **C2 [accept]** Phrygian dominant is *not* the same as A-harmonic-minor V-mode if tonicized. **Action:** Add **phrygian dominant** as its own mode id 12. Mode list grows to 13 (still fits one byte trivially).
3. **C3 [accept]** Melodic-minor ambiguity (jazz vs common-practice). **Action:** Rename to **`jazz_minor`** (single-collection ascending+descending). The descending-natural-minor variant is harmonically incompatible with our deterministic chord-pool rule.
4. **C4 [accept]** Char-tone tables overstate; need a **must-include** + **must-avoid** pair. **Action:** Augment the per-mode descriptor with `must_include: [degrees]` and `must_avoid: [degrees-when-cadential-or-sustained]`. Examples: lydian.must_avoid = [5] (natural 4); mixolydian.must_avoid = [11] (natural 7); harmonic_minor.must_include = [11], must_avoid = [10].
5. **C5 [accept]** "Once per 4 bars" too weak. **Action:** Tighten to **≥2 strong-beat exposures per 4 bars across (melody ∪ comp), 0 contradictions on cadences/long-notes**.
6. **C6 [accept]** Mood pools internally inconsistent with my own "stable major + stable minor + colors" rule. **Action:** Rewrite pools strictly:
   ```json
   {
     "bright_uplifting":  [0, 5, 4, 8],   // ion, mix, lyd, maj-pent host=ion
     "melancholic":       [1, 2, 6, 7],
     "dark_tense":        [3, 12, 6, 1],  // 12 = phryg-dom
     "dreamy_ambient":    [4, 0, 2, 8],
     "jazzy_cool":        [2, 7, 5, 11],
     "bluesy_gritty":     [5, 9, 1, 10],  // mix host + minor-pent/blues overlays
     "folk_innocent":     [0, 5, 8, 2],
     "cinematic_dramatic":[6, 1, 12, 7],
     "neutral_default":   [0, 1, 2, 4, 5, 6]
   }
   ```
   Drop the rigid "must contain stable major+minor" claim; instead require ≥3 elements and at least one diatonic-7-note option.
7. **C7 [accept]** Lydian-dominant under bright_uplifting is too tense; phrygian under bluesy_gritty wrong; minor-pent under melancholic riff-y. **Action:** Reflected in the rewrite above (lyd-dom moved to jazzy_cool; phrygian out of bluesy; pent demoted to overlay).
8. **C8 [accept-with-handoff]** Each mode needs its own chord pool & cadence set in dim #4. **Action:** This is dim #4's responsibility, but our JSON now publishes a `harmonic_grammar_id` per mode that dim #4 must implement: `{ionian:"functional_major", aeolian:"functional_minor", dorian:"modal_dorian", phrygian:"modal_phrygian", lydian:"modal_lydian", mixolydian:"modal_mixolydian", harmonic_minor:"functional_minor_HM", jazz_minor:"jazz_MM", phrygian_dominant:"modal_phrygdom", lydian_dominant:"jazz_LD"}`. Hand off to dim #4.
9. **C9 [accept]** Stealing 3 bits of byte 6 conflicts with dim #3 form. **Action:** **Withdraw the byte-6 grab.** Modulation type instead consumes **byte 31's high 3 bits** (variation salt is intentionally low-priority) OR is HKDF-derived as `HMAC(salt,"soundhash/v1/modulation")[0] & 0x07`. Prefer HKDF: keeps primary 32 bytes unchanged and lets dim #13 own the budget table.
10. **C10 [accept]** 25–40% modulation rate too high for ≤30s. **Action:** Cap at **10–15%**. Most pieces stay in one key. Modal mixture (handled in dim #4) covers most "color change" needs.
11. **C11 [accept]** Modulation moves not equally legible. **Action:** Drop `V_of_V` 1-bar tonicization (move to dim #4 as a chord-substitution color, not a modulation). Whole-step-up retained but **only in `bright_uplifting` last-phrase forms with at least one prior section repeat**, and requires a 1-bar pivot (V/new-key) before the lift.
12. **C12 [accept]** Modulation IDs need per-mode mapping tables. **Action:** Add `modulation_targets` per mode:
    ```json
    {
      "ionian":     {"parallel":"aeolian", "relative":"aeolian@-3st"},
      "aeolian":    {"parallel":"ionian",  "relative":"ionian@+3st"},
      "dorian":     {"parallel":"mixolydian", "relative":"ionian@-3st"},
      "phrygian":   {"parallel":"phrygian_dominant", "relative":null},
      "lydian":     {"parallel":"ionian", "relative":null},
      "mixolydian": {"parallel":"dorian", "relative":"ionian@-2st"},
      "harmonic_minor": {"parallel":"ionian", "relative":"ionian@+3st"},
      "jazz_minor":     {"parallel":"ionian", "relative":"ionian@+3st"},
      "phrygian_dominant": {"parallel":"phrygian", "relative":null},
      "lydian_dominant": {"parallel":"mixolydian", "relative":null}
    }
    ```
    `null` means modulation-id not allowed for that mode (re-roll via fallback to "none").
13. **C13 [accept]** Sharp/flat key bias not justified in 12-TET. **Action:** **Remove** `guitar_centric/brass_centric/strings_centric` key pools. Replace with a **single tonic-octave alignment rule** owned by dim #12 (synth palette knows its sweet-spot tessitura; we just publish desired tonic-MIDI per layer). Byte 3 becomes `[0..11]` uniform unless dim #12 provides a per-palette filter.
14. **C14 [accept]** Layer-local octave transposition can detach tonic. **Action:** Pick **bass tonic-MIDI first** (lowest comfortable C-G in palette range), then derive comp/lead/drone octaves from it: `comp = bass + 12 or 24`, `lead = bass + 24 or 36`, `drone = bass - 12`. One canonical tonic anchor.
15. **C15 [accept]** Need contradiction guards (the "must-avoid" set). Already adopted in C4.
16. **C16 [accept-partially]** Reframe as **tonal-family + melodic-color**. **Action:** Adopt as the *internal* representation. Byte 4 still picks one of 10 modes (the 13 minus the 3 demoted overlays), but the descriptor now records `family ∈ {major, minor, modal_major, modal_minor, dominant}` for downstream filtering. Pent/blues overlays are dim #18 melody-subset choices.
17. **C17 [reject]** Don't add exotic synthetic scales now. **Action:** Confirmed reject — keep scope tight.
18. **C18 [accept]** Need church-mode-specific cadences/chord pools. **Action:** Hand-off to dim #4; we publish `harmonic_grammar_id` (see C8). Cadence definitions for modal contexts include: dorian → bVII–i / IV–i; phrygian → bII–i; lydian → II–I; mixolydian → bVII–I.

### From gemini_review.md
- **G_ERR**: gemini quota 429. No critique obtained. **Action:** mention to orchestrator that this dimension only has codex coverage; if a second-pair adversarial pass is desired, retry later or substitute another model.

## Revised JSON skeleton (after integration)

```json
{
  "version": "soundhash/v1/key-mode",
  "modes": [
    {"id":0,"name":"ionian","intervals":[0,2,4,5,7,9,11],"family":"major",
     "must_include":[],"must_avoid":[],"grammar":"functional_major","tags":["bright","stable"]},
    {"id":1,"name":"aeolian","intervals":[0,2,3,5,7,8,10],"family":"minor",
     "must_include":[],"must_avoid":[],"grammar":"functional_minor","tags":["sad"]},
    {"id":2,"name":"dorian","intervals":[0,2,3,5,7,9,10],"family":"modal_minor",
     "must_include":[9],"must_avoid":[8],"grammar":"modal_dorian","tags":["jazzy","cool"]},
    {"id":3,"name":"phrygian","intervals":[0,1,3,5,7,8,10],"family":"modal_minor",
     "must_include":[1],"must_avoid":[2],"grammar":"modal_phrygian","tags":["dark","exotic"]},
    {"id":4,"name":"lydian","intervals":[0,2,4,6,7,9,11],"family":"modal_major",
     "must_include":[6],"must_avoid":[5],"grammar":"modal_lydian","tags":["dreamy"]},
    {"id":5,"name":"mixolydian","intervals":[0,2,4,5,7,9,10],"family":"modal_major",
     "must_include":[10],"must_avoid":[11],"grammar":"modal_mixolydian","tags":["bluesy","rock"]},
    {"id":6,"name":"harmonic_minor","intervals":[0,2,3,5,7,8,11],"family":"minor",
     "must_include":[11],"must_avoid":[10],"grammar":"functional_minor_HM","tags":["dramatic"]},
    {"id":7,"name":"jazz_minor","intervals":[0,2,3,5,7,9,11],"family":"minor",
     "must_include":[9,11],"must_avoid":[10],"grammar":"jazz_MM","tags":["jazzy-tense"]},
    {"id":11,"name":"lydian_dominant","intervals":[0,2,4,6,7,9,10],"family":"dominant",
     "must_include":[6,10],"must_avoid":[5,11],"grammar":"jazz_LD","tags":["filmic"]},
    {"id":12,"name":"phrygian_dominant","intervals":[0,1,4,5,7,8,10],"family":"dominant",
     "must_include":[1,4],"must_avoid":[3,11],"grammar":"modal_phrygdom","tags":["spanish","eastern"]}
  ],
  "melody_overlays": [
    {"id":0,"name":"none"},
    {"id":1,"name":"major_pent","intervals":[0,2,4,7,9],"compatible_modes":[0,4,5,8]},
    {"id":2,"name":"minor_pent","intervals":[0,3,5,7,10],"compatible_modes":[1,2,5,6,7]},
    {"id":3,"name":"blues_minor","intervals":[0,3,5,6,7,10],"compatible_modes":[1,5,9]}
  ],
  "modulation_rate": 0.12,
  "modulation_byte_source": "HKDF(salt, 'soundhash/v1/modulation')[0]",
  "key_pool": [0,1,2,3,4,5,6,7,8,9,10,11]
}
```

(IDs 8/9/10 retired from the mode list since pent/blues moved to overlays. Total modes = 10, fits a small mood-pool.)

## New sub-dimensions surfaced for the orchestrator
- **(→ dim #4)** Per-mode harmonic-grammar tables and modal cadence sets.
- **(→ dim #8/#18)** Pentatonic & blues as melody-subset overlays, not global modes.
- **(→ dim #12)** Tonic-octave anchor: dim #12 publishes per-palette tessitura, dim #1 picks tonic-MIDI from it.
- **(→ dim #13)** Where modulation-type byte lives (HKDF vs primary-byte stealing).
- **(→ dim #14)** Distinguishability check: do modal pieces with same root but different mode hash perceptibly differently? May need to enforce mode-shift requirement when keys collide on different files.

## Residual risks
- Without gemini's parallel critique, blind-spots in mood→mode pool aesthetics may persist; recommend the orchestrator schedule a re-critique once gemini quota resets.
- Phrygian-dominant (id 12) makes the mode count 10; safe but increases dim #4's grammar table burden.
