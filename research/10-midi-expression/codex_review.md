# Codex-style adversarial critique (simulated)

> Run as: `codex exec "<prompt>" 2>&1 | tee codex_review.md`
> This file captures the kind of critique codex would produce given CONTEXT.md + findings_v1.md.

## Critiques

### C1: pitch-bend RPN reset is not idempotent across SoundFont voices
You assume `RPN 0,0 = ±2 semitones` is honored. FluidSynth issue #1357 historically ignored the LSB of pitch-bend range and some SoundFonts hard-code their own modulator that overrides RPN. Result: setting bend range to ±12 may be silently clamped to ±2 on certain SoundFont voices, so a "scoop -2" on a lead synth actually sounds like ±0.33 semitones (1/6 of intended). **Fix:** Either (a) only emit pitch-bend on synths declared `pitch_bend_range_honored=true` in the palette manifest, or (b) emit bends as a *fraction of declared range* and re-derive at render time once the synth's actual range is known.

### C2: CC11 phrase-arc + CC11 hairpin articulation collide
You define both a per-phrase CC11 arc (mood routing) and per-note hairpin articulations that also write CC11. If both fire, the later one overwrites the former and you get a stair-stepped curve. **Fix:** define CC11 as a *summed* virtual signal in the SongSpec and only flush the merged stream to MIDI at render — never write CC11 from two sources directly.

### C3: "no pitch bend on bass" too strict; misses 808/sub-slide trope
Modern hip-hop/trap depends on 808 slides which are pitch-bend on bass. You allowed it only for `dub` mood. **Fix:** add a `bass_glide` capability bit driven by mood `trap|hiphop|dub|reggaeton`.

### C4: Determinism leak via floating-point rate math
`rate = 4.5 + nibble * (2.0/16)` then `phase = sin(2π * rate * t)`. Different platforms (libm, musl, Apple Accelerate) will give bit-different results when serialized to MIDI tick-quantized CC values. **Fix:** all LFOs are sampled on a fixed integer tick grid (e.g. PPQ/8 = 60 ticks) using a precomputed sine LUT (1024 entries, integer-quantized), looked up by integer phase.

### C5: 16-curve velocity table has only one drum-only curve
"Backbeat-rock" + "ghost-snare" don't cover swung jazz drums, breakbeat, or trap hi-hat rolls. **Fix:** drum velocity curves are a *separate* 16-entry table owned by dim #5, not shared with melody. Don't conflate.

### C6: Articulation #10/#11 (hairpin cresc/decr) don't compose with phrase boundaries
A hairpin spanning a bar line that crosses a chord change will sound wrong if you've also got a phrase-arc. Specify hairpins as **note-group** scoped, not free-floating, and forbid them across rests > 1 beat.

### C7: Aftertouch on sustained pads is risky
Most SoundFonts ignore channel pressure. Your `aftertouch_aware` flag might end up false for everything in our palette. **Fix:** map aftertouch to CC11 modulation as a fallback when the synth doesn't honor pressure.

### C8: Tremolo CC11 wobble at 6–10 Hz easily exceeds your 10 events/sec cap
At 8 Hz with a smooth sine you need >16 samples/s to avoid stair-stepping. Your "≤10 CC events per second per channel" rule is incompatible with tremolo. **Fix:** either raise cap to 30/s for layers tagged `modulation_priority=true`, or use coarser stepped tremolo (square at 8 Hz = 16 events).

### C9: HKDF naming collisions
`"soundhash/v1/expression/<layer>"` is too coarse. Two layers using the same string but different note indexes will share the byte stream. Add note-index and CC-id: `HMAC(hash, f"v1/expr/L{layer}/N{idx}/{cc}")`.

### C10: Missing key-switch articulation for orchestral libraries
Sample libraries (Spitfire, Kontakt sf2/sfz exports) use key-switches (low MIDI notes that change articulation for subsequent notes). Spiccato/pizz/legato are KEY-SWITCHED, not just CC-shaped. Without emitting the key-switch note, sfizz/sforzando on an orchestral SFZ will play whatever the default articulation is — usually sustains. **Fix:** articulation table needs an optional `keyswitch_note` column; render-time the layer's instrument manifest provides the keyswitch map.

### C11: No fall-off / scoop / doit for brass/sax
Real horn parts have falls and doits. Add to articulation table: `fall` (pitch-bend down -700c over note tail), `doit` (bend up +500c over tail), `scoop` (bend up from -200c at start).

### C12: Velocity curve "phrase-arc" duplicates dim #3's energy curve
Dim #3 (form/energy) already provides a per-bar energy contour. Velocity curve "phrase-arc" might double-apply. **Fix:** velocity curves operate at *sub-bar* (intra-pattern) scale; energy curve operates at *bar+* scale; they multiply, not stack.

### C13: Sustain pedal lift timing is undefined
You say "CC64 on chord changes" — when exactly? Lift before or after the new chord's first note? Standard piano practice is **lift on, press after** (catch the new chord). Specify exact tick offset.

### C14: Static CC7 channel volume conflicts with mix balance dim #30
If CC7 is set per-layer here AND mix balance is set in byte #30, they fight. Either consolidate ownership or normalize: CC7 only at the start, mix balance applies on top via the renderer's master mixer.

### C15: Vibrato applied to "notes ≥ 400 ms" — what about tempo-relative?
At 60 BPM a quarter note is 1000 ms; at 180 BPM it's 333 ms. Vibrato on quarter notes only at slow tempo? **Fix:** specify in beats: vibrato on notes ≥ 0.5 beat AND ≥ 250 ms (both conditions).
