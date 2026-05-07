# Gemini-style adversarial critique (simulated)

## Critiques

### G1: "Audio palette" of synths is undefined here, but expression cannot be portable
Different render targets (FluidSynth + GM SoundFont, sfizz + custom SFZ, Surge XT, Dexed) interpret the same CC differently. CC74 means "filter cutoff" on Surge but on a GM SoundFont it's "Brightness" with a different scaling. Your "canonical CC set" claim is false unless you pin the exact SoundFont/preset. Recommend: a *capability matrix* per synth in dim #12, and expression code emits an **abstract** intent (`{kind:"brighten", amount:0.4}`) that's lowered to CC events at render time, per-target.

### G2: Pitch-bend "always emit pitch_bend(0) before next note" is wrong for legato slides
On a true legato/portamento, you DO NOT want to reset the bend — the bend IS the slide. Your rule conflicts with portamento articulation. Distinguish: reset-on-next-note unless `articulation in {legato, slur, portamento}`.

### G3: Channel allocation is missing
You assume one MIDI channel per layer but never say so. Standard MIDI = 16 channels, channel 10 reserved for drums. With 4–6 layers + multi-articulation + key-switching, you can run out. Specify: channel allocation policy (1 layer = 1 channel; layered/divisi instruments may take 2; channel 10 always drums).

### G4: Tempo-relative humanization missing
"timing_ms_max:25" is absolute. At 60 BPM that's 6% of a beat (acceptable for a ballad). At 180 BPM that's 18% — feels sloppy. **Fix:** humanization expressed as max % of tick, with a floor and ceiling in absolute ms.

### G5: Velocity curves expressed as 16-step arrays are time-signature blind
A 4/4 backbeat curve indexed by 16 sixteenth-steps doesn't fit 6/8 or 7/8. Define curves over **beat fractions** (length 1, indexed by `(beat_position % 1)`) or supply per-time-sig curve variants.

### G6: Determinism: integer math everywhere, but you didn't say
Ms-to-ticks conversion `ticks = ms * PPQ * BPM / 60000` involves floats. Different orderings round differently. Make it explicit: `ticks = (ms * PPQ * BPM + 30000) // 60000` integer division, fixed PPQ=480.

### G7: Missing "release velocity"
Many sample libraries respond to release velocity (note-off velocity) for release samples (key-noise on piano, breath releases on flute). You mentioned only note-on velocity. Add: release_vel = note_on_vel scaled by articulation factor (staccato → high release vel, legato → low).

### G8: No mention of MPE
Modern soft-synths (Surge XT) support MPE (per-note pitch-bend on separate channels). For polyphonic synths you can get per-note vibrato/bend. Either declare MPE explicitly out-of-scope, or allocate a mode flag.

### G9: Crash risk: byte #27 has only 8 bits but you packed 4+2+1+1
Re-checking your bit table: `[0:4]=4, [4:6]=2, [6:7]=1, [7:8]=1` — that's 8 bits total. OK. But it's tight; any future addition (MPE flag, release-vel curve) needs HKDF expansion. Acknowledge.

### G10: "drums always machine" is too rigid
Live drummers humanize. Your "live-drums" tag override exists but isn't byte-mapped. Where does the byte come from to flag it?

### G11: CC events at startup vs. mid-song
You don't say whether per-layer static CCs (CC7, CC10, CC91, CC93) are emitted at tick 0 or per-section. If a section change wants new reverb send, you need ramping or you'll hear a click. **Fix:** all static CC changes ramp over 64 ticks.

### G12: 7-bit CC resolution may quantize visibly slow LFOs
A slow CC11 sweep from 60→90 over 8 seconds = 30 distinct values over 8 s = 3.75 events/s. That's fine, but if you want smoother, you must use 14-bit CC (CC11 MSB + CC43 LSB). Most SoundFonts ignore LSB. **Fix:** declare 7-bit-only and accept the staircase, OR use abstract intent + render-time interpolation if the renderer supports it.

### G13: Marcato "+30 vel + slight detune" — detune via pitch bend conflicts with pitch-bend articulations
If a marcato note is also part of a pitch-bend phrase, the +10c detune will compose unpredictably. Spec the composition order: articulation detune is applied as note-on cents-shift via tuning event (RPN fine-tune), not via pitch bend.

### G14: Aftertouch and channel pressure confusion
"Aftertouch (channel pressure)" — there are TWO kinds: channel pressure (1 value/channel) and polyphonic aftertouch (per-note). You're using channel pressure but say "aftertouch crescendo if sustained > 2s" on a pad — multi-note pad chords share one pressure value, fine, but say so.

### G15: "Don't overdo it" cap of 10 events/s/channel is a soft target only
SMF (Standard MIDI File) and SoundFont rendering can handle hundreds of CC/s. The cap is for taste, not technical limits. Reframe: "≤ ~30/s for legibility in an SMF viewer; humans don't perceive >30 Hz CC modulation as separate events." Tremolo at 8 Hz = 16/s is fine.

### G16: No fallback when synth ignores CC
If `breath_aware=false` we said use CC1 instead. But CC1 may already be vibrato. Conflict. Fallback should be CC11 (expression) for breath-like swells.

### G17: Time-quantization of articulation note-length scaling
`length=0.5x` of a 16th note at 480 PPQ = 60 ticks. At what PPQ floor? If `0.3x` of a 32nd note rounds to 0 ticks, the note-off precedes note-on. **Fix:** floor articulation duration at MIN(20 ticks, 5 ms).
