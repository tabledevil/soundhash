# ADV-IMPL: Soundhash Implementation Adversarial Review Summary

Reviewers: codex (gpt-5.4) round 1+2 OK; gemini round 1 OK after retries; gemini round 2 = 429 quota exhausted (CLI error). 3 of 4 reviews complete.

## Top 5 Deal-Breakers (ranked)

1. **`render/audio.py:2009-2018,2030-2037` — LUFS normalization happens BEFORE FX, not after.**
   Quote (codex): "Reverb/delay/chorus/distortion can change integrated loudness, so the final WAV is not actually normalized to TARGET_LUFS; it is only peak-limited afterward."
   Fix: reorder steps in `_postprocess_wav` — apply FX first, then LUFS-normalize, then fades, then peak-limit. Or run LUFS twice (pre/post-FX) and adjust gain post-FX.

2. **`render/midi.py:119` `_GROOVE_CACHE` never cleared between renders → cross-render state leak.**
   Quote (gemini): "module-level cache that is never cleared… persists across multiple calls to render_midi() within the same process, causing state to leak and violating the byte-stable rendering contract."
   Fix: add `_GROOVE_CACHE.clear()` at top of `render_midi()` alongside the existing `_VEL_JITTER_CACHE.clear()`. (Note: data-only cache so leak is benign in current code, but contract-breaking.)

3. **`render/midi.py:827-863, 891-893` — global mutable `_VEL_JITTER_CACHE` is not thread-safe; `_VelJitter._pos` advances during emission, and `render_midi()` clears the shared cache at entry.**
   Quote (codex): "Concurrent renders can interleave or reset each other and change emitted velocities for the same SongSpec."
   Fix: scope the cache to a per-call `dict` (or attach to a `RenderContext` passed through track helpers); remove the global.

4. **`render/audio.py:1874-1889` + `render/fx.py` — host-dependent audio path defeats the bit-identical determinism goal.**
   Quote (codex): "_find_soundfont() picks the first SoundFont present on the machine, and the FX layer explicitly says pedalboard is not bit-identical across builds."
   Fix: ship a single pinned CC0 SF2 in the package (`assets/v1/sf2/`), refuse to render if not present, and gate pedalboard FX behind a flag (or replace with deterministic NumPy chain — see codex round-2 #1).

5. **`decode.py:540-543` — infinite loop if `theory.resolve_progression()` returns `[]`.**
   Quote (codex): "`looped.extend(chord_entries)` never makes progress."
   Fix: add `if not chord_entries: raise RuntimeError(...)` before the while loop, or fall back to a single-tonic chord entry.

## Top 5 Nice-to-haves

1. **`decode.py:640-641` — `counter_program` assigned twice.** First line is dead code; second line couples counter timbre to pad selection (`macro[23] ^ 0x55`). Both reviewers flag. Codex round-2 fix: drive counter from `macro[22]` only — recovers a full byte of entropy and decouples upper-mid layers.

2. **`decode.py` — many `_pick_*` use `eligible[byte % len(eligible)]` without empty-list guards.** Gemini: `_pick_progression` final fallback, `_pick_form`, `_pick_form_unconstrained` can crash with `ZeroDivisionError` / `IndexError` on empty/misconfigured tables. Add explicit empty-check + sentinel default.

3. **`render/midi.py:1702` — `base_octave_midi = 72` hardcoded; `_lead_octave(mood)` exists but is unused.** Soft moods should drop to C4 and M14 chiptune to C6. Codex round-2 #5: 1-line fix, big perceptual gain.

4. **`render/audio.py:2014-2018,2060-2063` — broad `except Exception: pass` swallows pedalboard / pyloudnorm failures silently**, downgrading the render with no signal. Catch specific exceptions; log on failure.

5. **`render/audio.py` — no NaN/inf scrub** between FX and int16 quantization. A misbehaving plugin can poison the output. Add `np.nan_to_num` after `apply_fx`.

Other dead code flagged: `_pick_form()` (unused), `_BEATS_PER_BAR` local (dead), first `chord_tones` placeholder in `_lead_track()` overwritten one line later (`render/midi.py:1737-1740`).

## Round-2 distinguishability/reproducibility diffs (codex)

1. `render/fx.py:84` — replace pedalboard with pure-NumPy deterministic FX chain (biggest determinism win).
2. `decode.py:473` — use unused `macro[8]` to rotate progression: `rot = macro[8] % len(chord_entries); chord_entries = chord_entries[rot:] + chord_entries[:rot]`.
3. `decode.py:596` — filter motif/contour/comp pools by mood AND exclude already-used section IDs for B/C sections.
4. `decode.py:590` — fix double-assigned `counter_program` (see nice-to-have #1).
5. `render/midi.py:905` — use `_lead_octave(mood)` instead of hardcoded 72; fix phrase-end detection to honor `drop_lead`.

## Disagreements / interesting signal

- **Codex elevates LUFS-before-FX as a deal-breaker** (loudness contract violated); gemini missed this entirely. Codex is correct — this is a clear correctness bug given the documented `TARGET_LUFS` contract.
- **Gemini elevates `_GROOVE_CACHE` cross-render leak as a deal-breaker**; codex flagged the analogous `_VEL_JITTER_CACHE` thread-safety issue but didn't catch the missing `.clear()` for `_GROOVE_CACHE`. Both are real, gemini caught one codex missed.
- **Gemini flags empty-list `IndexError` risk broadly**; codex only flags the one infinite-loop case in `looped`. Gemini's wider sweep is the better defensive-programming take.
- **Codex catches** unused `_lead_octave()` and the hardcoded `base_octave_midi = 72` (perceptual + correctness); gemini missed this.
- **Both agree on** the double-assigned `counter_program`, the host-dependent SoundFont path, and pedalboard non-determinism.

## Overall assessment

The implementation is professionally structured and the HKDF-driven decision pipeline is consistently applied — most of the obvious determinism traps (dict ordering, sort-by-id) are correctly mitigated. The serious issues cluster around the **audio post-pipeline**, not the symbolic decode: the LUFS-before-FX ordering is a clear contract bug, the SoundFont/pedalboard chain undermines the bit-identical promise on any non-pinned host, and two module-level caches (one cleared, one not) leak state across renders in inconsistent ways. The decode side is solid except for one infinite-loop edge case, the duplicated `counter_program` assignment (which silently halves entropy on that role), and several small unused-helper / dead-code instances (notably `_lead_octave` ignored by `_lead_track`). Highest ROI fixes per LOC: (a) reorder LUFS/FX, (b) clear `_GROOVE_CACHE`, (c) one-line `base_octave_midi = _lead_octave(mood)`, (d) drop the duplicate `counter_program` line, (e) ship a pinned SF2 + gate pedalboard. Each is ≤5 lines and addresses a deal-breaker.
