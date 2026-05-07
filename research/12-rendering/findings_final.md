# Dimension 12 — Final findings (post-adversarial)

## Adopted changes from reviews

| Tag | Decision | Action |
|---|---|---|
| C1 (BUFSIZE quantization) | Accept (no fix) | Document; same across builds = fine. |
| C2 (pedalboard cross-OS) | **Accept** | Reverb only in Docker canonical path. Optional FIR convolution with pinned IR for host-mode reverb. |
| C3 (LAME MP3) | **Accept** | Drop MP3 from canonical-bit-identical contract; mark "perceptually identical." WAV/FLAC are canonical. |
| C4 (FS monoculture) | **Accept** | Require ≥3 engines per role pool; broaden via sfizz + Surge entries. |
| C5 (Salamander size) | **Accept** | Default ship = GeneralUser GS or curated trimmed SF2 (<15 MB). Salamander opt-in. |
| C6 (alts) | Accept partly | Add Nuked-OPL3 for retro mood subset. Skip ZynAddSubFX (state-heavy). |
| C7 (LUFS NaN guard) | **Accept** | Fallback to peak-norm at -3 dBFS if integrated loudness non-finite. |
| C8 (interp order) | Reject (override by G2) | Pin to **4** instead of 7 — speed/quality balance. |
| C9 (NOTICE file) | **Accept** | Add `licenses/` dir with all texts. |
| C10 (numpy sum order) | **Accept** | Explicit Python loop sum; pin numpy + force single-thread BLAS via `OPENBLAS_NUM_THREADS=1` etc. |
| G1 (hash sensitivity) | **Accept** | Add curation step with spectral-centroid distance check before pool freeze. Hand back to dim #14. |
| G2 (interp 4 vs 7) | **Accept** | Pin to 4. |
| G3 (TinySoundFont) | Investigate | Add as future canonical option; needs a Python binding (or run as compiled CLI). Defer to v1.1. |
| G4 (no reverb) | **Accept (default)** | Reverb off by default; opt-in flag for moods that need it. Removes biggest determinism risk. |
| G5 (numpy drums) | **Accept** | Drums primary path = numpy CC0 one-shot mix. FluidSynth ch10 for "GM throwback" mood only. |
| G6 (license fuzz) | **Accept** | Build a pure-CC0 ship-default soundfont from VS Chamber Orchestra + Iowa Piano + CC0 drum kit. GeneralUser GS becomes opt-in. |
| G7 (Surge CLI unverified) | **Accept** | Demote Surge to "v1.1 future work." |
| G8 (CI determinism harness) | **Accept** | Add `tests/render_determinism.py`: N×rerun in container, SHA-256 diff. Cross-platform matrix. |
| G9 (44.1k) | Accept | Stay at 44.1 kHz; document. |
| G10 (size) | Accept | Document. |
| G11 (small pools waste bytes) | **Forward to dim #13** | Use base-N digit packing across decisions, or HKDF expansion. Not solved here. |

## Surfaced sub-dimensions for orchestrator

- **12a — Reverb policy.** Default off; opt-in pedalboard (Docker only) or FIR convolution (cross-platform). Bound to mood from dim #11.
- **12b — Pure-CC0 ship soundfont.** A curated SF2 from VSCO/Iowa/CC0 drums; small (<25 MB), zero attribution friction.
- **12c — Determinism CI matrix.** Required infra. Not music theory but blocks correctness claims.

## Final decisions (locked)

1. Stage 1: mido @ PPQ 480, Type 1, fixed event ordering.
2. Stage 2 primary: FluidSynth fast-render with deterministic flags; **interpolation=4**, single-thread, reverb/chorus OFF.
3. Stage 2 secondary: sfizz_render for piano/strings/specialty.
4. Drums primary: numpy CC0 one-shot mixer. FluidSynth ch10 only for explicit GM mood.
5. Default soundfont: pure-CC0 curated `soundhash_curated_v1.sf2` (~15 MB). GeneralUser GS optional download.
6. Post-FX: pedalboard.Limiter + pyloudnorm to -16 LUFS (with peak-norm fallback). Reverb default OFF.
7. Output: 16-bit/44.1 kHz WAV canonical; FLAC also bit-identical; MP3/OGG perceptually identical only.
8. Reproducibility: Docker image with pinned digest is canonical. Host installs are best-effort; CI golden-file harness mandatory.
9. Synth pool: ≥3 engines per role; spectral distance threshold between adjacent pool entries; fixed JSON pinned by SHA.
10. License: full text shipped in `licenses/`; default ship = pure-CC0 only.
