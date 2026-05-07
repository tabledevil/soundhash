# Dimension 12 — Rendering Stack & Synth Selection (v1)

## 1. Stage 1: SongSpec → MIDI
Primary `mido` (MIT, pure Python). PPQ=480. Fixed event sort key (tick, channel, type_priority). pretty_midi only as dev-time read helper. python-rtmidi skipped.

## 2. Stage 2: MIDI → WAV
Primary: **FluidSynth** in fast-render mode with deterministic flags:
`fluidsynth -ni -q -r 44100 -R 0 -C 0 -g 0.5 -o synth.cpu-cores=1 -o synth.interpolation=7 -o synth.reverb.active=0 -o synth.chorus.active=0 -o synth.dynamic-sample-loading=0 -o player.timing-source=sample -T wav -F out.wav <sf2> in.mid`

Secondary: **sfizz_render** for piano/strings (Salamander, Sonatina). Surge XT CLI (v1.3+) optional for synth leads.
Rejected: TiMidity++ (lossy SF2), Munt (Roland ROMs not redistributable), Csound/SC (overkill), ZynAddSubFX/Yoshimi (state-heavy), Carla/Ardour (heavy host).

## 3. Synth pool (hashable)
Per-role pools (drums/bass/comp/lead/aux) of 8–16 entries. Entry: {engine, asset, asset_sha256, bank, program, mood_tags, key_tags, range, post}. Selection by `byte % len(filter_by_mood(pool))`.

## 4. Post-processing (deterministic order)
Per-layer render → numpy mix in fixed layer order → pedalboard.Reverb (pinned) → pyloudnorm to -16 LUFS → pedalboard.Limiter at -1 dBTP → 50ms/200ms fades → 16-bit/44.1k WAV via soundfile. Optional FLAC/OGG/MP3 (LAME `--strictly-enforce-ISO --cbr`).

## 5. Pinning manifest
Docker digest, fluidsynth/sfizz/surge versions, libsndfile/lame/flac/vorbis, mido/numpy/pedalboard/pyloudnorm pins, soundfont SHA-256s, render flags. See versions.lock.json.

## 6. License audit
- **Bundle:** GeneralUser GS (permissive, ~30 MB) — preferred default. Optional curated trimmed SF2 (<15 MB).
- **Optional download:** FluidR3_GM (MIT), Salamander Grand Piano (CC-BY 3.0), Sonatina Symphonic (CC Sampling Plus), VS Chamber Orchestra (CC0), Salamander Drumkit (CC-BY 3.0).
- **Reject:** Arachno (license unclear), SCC1t2 (Roland-derived), Roland MT-32/CM ROMs (proprietary).

## 7. Byte allocation
Existing per-layer synth bytes (13/16/19/23) suffice if pools ≤16. Sub-preset variation drawn from HKDF stream, not new bytes.

## 8. Determinism risk register
Reverb/chorus algo drift → off in synth, applied post in pinned pedalboard. Multi-thread voice-add reorder → cpu-cores=1. Interpolation default change → pin to 7. SR mismatch → enforce 44100. SIMD float drift across hosts → Docker is canonical. LAME variability → CBR + strict ISO. Locale-float SFZ parsing → LC_ALL=C. Missing soundfont preset → preflight refuse. JUCE/pedalboard updates → pin exact, golden-file CI.

## 9. Cross-platform
Docker (linux/amd64) is canonical. ARM Mac and Windows hosts run "best-effort" with golden-file verifier; `--canonical` invokes Docker for bit-exact output.

## 10. Drum path
GM channel-10 via FluidSynth is fine baseline. Optional sample-based drums via sfizz SFZ kit, or pure-Python numpy mix from CC0 one-shots — preferred for sharpest hash sensitivity. Decision shared with dim #5.

## 11. Open questions for adversaries
- FluidSynth interpolation determinism across SIMD paths?
- Pedalboard reverb cross-OS bit identity?
- Should drums always go through Python sample mixer for tighter determinism?
