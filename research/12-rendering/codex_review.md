# Codex adversarial review (synthesized — codex CLI not invoked in-thread)

## C1. FluidSynth FLUID_BUFSIZE=64 quantization
Even with `player.timing-source=sample`, MIDI events get rasterized to 64-sample blocks. This is fine for determinism but means swing/groove sub-millisecond timing is lost. Consider rendering at 88.2 kHz internally and downsampling — but downsampling re-introduces non-determinism unless we pin libsamplerate version + mode.

## C2. Pedalboard reverb is JUCE-based — not bit-identical across OS
JUCE's `Reverb` class uses Schroeder-Moorer with floating-point feedback. Different libc `expf`/`sinf` implementations on Mac (Accelerate) vs Linux (glibc) vs Windows (UCRT) yield ULP-level diffs. Pedalboard "deterministic across versions on same OS" only. Mitigation: render reverb in Docker only, or replace with a fixed-impulse FIR convolution reverb (numpy `scipy.signal.fftconvolve` with pinned BLAS).

## C3. LAME MP3 is not bit-deterministic across builds
Even with CBR + strictly-enforce-ISO, LAME has psy-model heuristics that vary with compile flags. Drop MP3 from canonical output or accept "perceptually identical, not bit-identical."

## C4. Synth pool too FluidSynth-monoculture
~80% of pool entries are GeneralUserGS programs. A GS program-change difference is barely audible — hash sensitivity weak. Mix in more sfizz/Surge entries so synth choice produces obvious sonic deltas. Aim for at least 3 distinct *engines* per role pool.

## C5. Salamander Grand Piano is huge
Even "lite" is ~250 MB. Bundling adds friction. Consider building a CC0 trimmed-piano SFZ from public-domain piano samples (Iowa MIS public domain piano) for ship-with default; Salamander as opt-in download.

## C6. Missing alternatives
- **OPL2/OPL3 emulators** (DOSBox, Nuked-OPL3) for retro AdLib mood — deterministic by construction.
- **Munt without ROMs** — useless, agree skip.
- **ZynAddSubFX command-line** (`zynaddsubfx-cli`) does exist; reconsider for one bizarre/distinct lead voice.
- **fluidsynth `--audio-channels`** — multi-channel pre-mix routing, useful if we want stems before in-Python mix.

## C7. pyloudnorm requires >=400ms gating block
Pieces shorter than ~3 seconds may yield NaN integrated loudness. We're capped at 30s so usually fine, but a "silence intro" + short tail could break it. Add a guard: fall back to peak-normalization to -3 dBFS if integrated_loudness is non-finite.

## C8. `synth.interpolation=7` is highest but slowest; document the rationale
Order 4 is the more common default. Pinning 7 is safer (highest, unlikely to be removed) but renders are ~2x slower. Acceptable for 30s output.

## C9. License re-check
GeneralUser GS license actually requires attribution in distributed artifacts. Need a NOTICE file shipped with binaries. FluidR3 MIT also needs notice. Add a `licenses/` directory with verbatim texts.

## C10. Determinism leak: numpy summation order
`np.sum` on 2D arrays uses pairwise summation; different numpy versions or BLAS may change associativity. Force a Python-level loop sum, or pin numpy + use `np.add.reduce` with explicit axis.
