# Determinism Contract

**Invariant:** `sha256(file) == sha256(file') ⇒ sha256(wav) == sha256(wav')` on any machine that satisfies the pinning manifest.

## Pinned components (versions in `versions.lock.json`)

| Layer | Pin | Rationale |
|---|---|---|
| Python | exact minor (e.g. 3.11.9) | hash-randomization seeded; float repr stable across patch but not minor |
| numpy | exact patch | BLAS dispatch differs across versions |
| scipy | exact patch | filter coeff rounding differs |
| mido / pretty_midi | exact | MIDI byte-level output differs across versions |
| FluidSynth | exact (e.g. 2.3.5) | render math changed in 2.x |
| sfizz | exact | SFZ engine drift |
| Surge XT | exact (CLI/headless build) | preset format & DSP changes |
| SoundFonts (.sf2) | content-hashed | even tiny SF2 edits change samples |
| SFZ patches | content-hashed (recursive incl. samples) | sample-level identity required |
| Sample rate | 48000 Hz fixed | resampling is the #1 nondeterminism source |
| Bit depth (intermediate) | float32, final = PCM_16 | float64 differs across BLAS |
| Channels | stereo (2) | |
| Output container | RIFF WAV (PCM) | |
| Tables JSON | content-hashed, schema versioned `tables/v1` | |
| Renderer flags | enumerated below | |

## Disabled non-deterministic features
- FluidSynth: `--disable-chorus --disable-reverb` at the synth level (we add deterministic IR-based reverb in post if any). Set `synth.cpu-cores=1`. Set `synth.audio-channels=1` (stereo via two render passes if needed). `synth.sample-rate=48000`. Disable `synth.dynamic-sample-loading`.
- sfizz: single-threaded mode, no LFO free-running, all LFOs phase-locked to note-on.
- Surge XT: headless render mode with `--non-realtime`; disable "randomize" buttons; pin tuning to 12-TET 440 Hz.
- ffmpeg (if used for mux/normalize): `-vn -af aresample=resampler=soxr:precision=33` (deterministic soxr) `-ar 48000`. Avoid `-af loudnorm` two-pass auto-detect; use measured first pass and pass values explicitly into single-pass.
- pyloudnorm: pin version; the meter is deterministic by construction.
- No system clock, no `random` module, no `secrets`. Single PRNG = `HKDF(sha256(file), info=b"soundhash/v1/<channel>")`.

## Float-determinism rules
- All DSP we author runs in float64 with explicit ordering (no `np.einsum` reductions over parallel threads). Use `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`.
- Resampling: always soxr `precision=33` (VHQ) or built-in scipy `resample_poly` with explicit kaiser window beta — never librosa default (it changes).
- No FFT-based time-stretch (FFTW planning is wisdom-cached, non-deterministic across machines). If needed, use phase-vocoder with fixed window.
- Reverb: pre-rendered IR convolution (deterministic). No algorithmic feedback-network reverbs that depend on sample-rate-dependent buffer init.

## Build / runtime manifest
A `manifest.json` is emitted with each render:
```json
{
  "soundhash_version": "1.0.0",
  "tables_hash": "sha256:…",
  "synths": {"fluidsynth": "2.3.5", "sfizz": "1.2.3"},
  "soundfonts": [{"name": "FluidR3_GM.sf2", "sha256": "…"}],
  "python": "3.11.9",
  "numpy": "1.26.4",
  "scipy": "1.13.0",
  "platform_class": "x86_64-linux-glibc2.35"
}
```
Identity check: `sha256(wav)` is reproducible on any host whose manifest matches.

## Tested invariant
CI job: render N=50 fixed hashes on {linux-x86_64, linux-arm64, macos-arm64}, assert byte-identical WAV. If macOS BLAS drifts, we fall back to a vendored OpenBLAS via wheels.

## Known leaks to monitor
- glibc `expf`/`sinf` differ from musl. Mitigation: vendor a pure-Python or numpy ufunc path for any per-sample transcendentals we author.
- Apple Accelerate vDSP differs from OpenBLAS. Mitigation: force OpenBLAS in our wheel.
- SoundFont sample interpolation in FluidSynth has an `interp` setting (`none|linear|4thorder|7thorder`) — pin `interp=7thorder` (highest quality, deterministic).
- MIDI tick→time conversion: pin `ticks_per_beat=480`; never use floating tempo maps without explicit rounding.
