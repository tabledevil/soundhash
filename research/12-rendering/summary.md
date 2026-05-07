## Summary — 12 Rendering

**Stack.** Stage 1: `mido` (PPQ 480, Type 1, fixed event sort). Stage 2: `fluidsynth --fast-render` as primary; `sfizz_render` for piano/strings; pure-Python numpy mixer for drums (CC0 one-shots). Surge XT CLI deferred until v1.1.

**Determinism contract.** Canonical output is bit-identical only inside a pinned Docker image (linux/amd64). Host-installed renders are best-effort and validated by a golden-file CI harness across Mac/Linux/Windows. Render flags: 44.1 kHz, `synth.interpolation=4`, `synth.cpu-cores=1`, `synth.dynamic-sample-loading=0`, `player.timing-source=sample`, `-R 0 -C 0`, `LC_ALL=C`, single-threaded BLAS for numpy. PPQ 480 + banker's rounding once.

**FX.** No reverb/chorus inside FluidSynth (algorithms drift across versions). Reverb off by default; opt-in path uses `pedalboard.Reverb` (Docker only) or a FIR convolution with a pinned IR (cross-platform). Loudness normalized to -16 LUFS via `pyloudnorm` (BS.1770-4) with peak-norm fallback at -3 dBFS for short/silent edge cases. `pedalboard.Limiter` at -1 dBTP. Cosine fades 50 ms in / 200 ms out. Output: 16-bit PCM WAV (canonical) + FLAC (also bit-identical); MP3/OGG flagged "perceptually identical only" because LAME and libvorbis are not bit-deterministic across builds.

**Synth pool (hashable dimension).** Per role (drums/bass/comp/lead/aux), 8–16 entries each. Each entry = `{engine, asset, asset_sha256, bank, program, mood_tags, key_tags, range, post}`. Selection: `byte % len(filter_by_mood(pool))`. Curation rule: ≥3 distinct engines per role pool, plus a spectral-centroid distance check between adjacent entries to guarantee audible difference per byte change (hands a curation requirement to dim #14).

**Default soundfont (license-clean).** Build `soundhash_curated_v1.sf2` from CC0/PD assets (VS Chamber Orchestra CC0 + Iowa MIS piano PD + CC0 drum one-shots). Target <25 MB. Optional opt-in downloads: GeneralUser GS (permissive + attribution), FluidR3_GM (MIT), Salamander Grand Piano (CC-BY). Reject: Arachno (license unclear), SCC1t2 / Roland MT-32 ROMs (proprietary). All text licenses ship in `licenses/`.

**Byte allocation.** No new bytes requested. Per-layer synth selection bytes (13/16/19/23) suffice if pools ≤16. Sub-preset variation drawn from HKDF stream. Flag forwarded: small pools waste bits — dim #13 should consider base-N digit packing across decisions.

**Determinism risk register (top items).** FluidSynth reverb/chorus drift → off. Multi-thread voice add reorder → cpu-cores=1. SIMD/libc math drift → Docker is canonical. JUCE/pedalboard cross-OS drift → reverb off by default. LAME variability → MP3 not in canonical contract. Locale float parsing in SFZ → `LC_ALL=C`. numpy summation/BLAS thread variance → fixed Python-loop sum + threads=1. Missing soundfont preset → preflight refuse.

**Surfaced sub-dimensions.** 12a Reverb policy. 12b Pure-CC0 ship soundfont. 12c Determinism CI matrix.

**Deliverables in this directory.** `findings_v1.md`, `codex_review.md`, `gemini_review.md`, `findings_final.md`, `synth_pool.json`, `render_pipeline.md`, `versions.lock.json`, `summary.md`.
