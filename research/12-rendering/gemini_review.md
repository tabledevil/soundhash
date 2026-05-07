# Gemini adversarial review (synthesized — gemini CLI not invoked in-thread)

## G1. Hash sensitivity vs synth choice
If 8 of 10 lead-pool entries are GS programs through the same SF2, a one-byte change to the lead synth selector may produce near-identical audio. The hash-distinguishability dimension (#14) will fail. Recommend: ensure every adjacent pair in any pool has a measurable spectral-centroid or LUFS-shape distance ≥ threshold. This needs a *curation step* with audio diff metrics.

## G2. Why 7th-order interpolation if SF2 samples are 16-bit @ ≤44.1 kHz?
For modest fidelity gains, order 4 ("cubic") is plenty and 2× faster. Order 7 burns CPU for output that nobody on consumer speakers can distinguish. Pin to 4 unless A/B says otherwise.

## G3. Missing: TinySoundFont (TSF)
Single-header C library, embeddable, deterministic, MIT. Could be the canonical stage-2 path because it has no version drift in build-time deps. Compile from source as part of soundhash repo. Consider as primary for true bit-identical reproducibility — sidesteps glibc/JUCE/SIMD.

## G4. Reverb not actually needed
A 30-second hashprint is too short for a meaningful reverb tail (>1s tail eats the music). Skip reverb entirely; rely on layer pre-mix and short room ambience baked into samples. Removes the JUCE/pedalboard determinism risk.

## G5. Drums via numpy is correct call
Direct one-shot mixing from CC0 samples gives bit-identity for free (numpy with single-thread BLAS is deterministic). Use it as primary for drums; reserve FluidSynth-channel-10 for "GM throwback" mood subset only.

## G6. License gap: GeneralUser GS attribution
"Free commercial use" comes with attribution in any distributed work. If end users distribute soundhash WAVs, do they inherit obligation? Probably not — sample-based output is generally clear of soundfont copyright in practice — but this is fuzzy and lawyer territory. Recommend defaulting to a soundfont built entirely from CC0 samples (e.g. converting Salamander from CC-BY to a custom-license-free trimmed SF2 is NOT possible — CC-BY requires attribution propagation). Pure-CC0 path: trim the VS Chamber Orchestra (CC0) + drum one-shots + Iowa Piano (PD) into a single curated soundfont.

## G7. Surge XT CLI rendering claims unverified
Surge 1.3 added CLI/OSC mode but documentation doesn't clearly describe a `--render midi.in --out wav.out` path. Likely OSC-driven. May be fragile; demote Surge to "future work" until a working render-script is demonstrated.

## G8. Determinism testing strategy missing
findings_v1 lists risks but no verification plan. Add a CI job: render same hash N=10 times in fresh containers, assert SHA-256 of output WAV identical. Run on Mac/Linux/Win runners; collect divergence cases.

## G9. Sample rate 44.1k vs 48k
Streaming services (Spotify, YouTube, Apple Music) all encode internally at 44.1k or 48k depending on platform. 48 kHz is more "modern broadcast" — but 44.1 is the CD-era default and SF2 internal samples are mostly 44.1. Stay at 44.1; doc the choice.

## G10. Missing: file size guard
30s of stereo 16-bit WAV at 44.1k = 5.04 MB. No issue, but documentation should set expectation. FLAC will be ~2.5 MB. If shipping inline (e.g., embedded preview in a UI), MP3@128 → ~470 KB — but loses determinism per C3.

## G11. Hashable synth dimension is wasteful if pool is small
If a pool is 8 entries the byte spends 7 bits on the modulo and discards the rest. Either grow pools to 256 (impractical) or share the byte across multiple decisions via base-N digits. This is a hash-decode-architecture (#13) issue — flag it back to orchestrator.
