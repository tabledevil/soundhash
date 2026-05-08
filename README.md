# soundhash

Deterministic musical hash. Convert a file's SHA-256 into ≤30 seconds of pleasant, music-theory-correct audio that is easily distinguishable between files. Same hash → identical MIDI, identical WAV.

## Quick demo

```bash
# Render an audio fingerprint of a file (writes path/to/file.soundhash.{wav,mid,mp3}).
PYTHONPATH=src python3 -m soundhash.cli --audio --mp3 path/to/file

# Force a specific mood regardless of MIME.
PYTHONPATH=src python3 -m soundhash.cli --audio --mood M0 path/to/file

# Print quality scores after render.
PYTHONPATH=src python3 -m soundhash.cli --audio --score --psy path/to/file

# Build a per-mood demo: one sample per M0..M10, stitched into showcase/showcase.wav.
PYTHONPATH=src python3 -m soundhash.showcase --score
```

## What's wired

- **Decode** (`src/soundhash/decode.py`) — pure HKDF-driven walker over a 32-byte macro budget plus per-bar / per-section sub-streams.
- **9 musical layers** rendered from the SongSpec:
  drums (channel 10, kit-mapped GM percussion), bass (degree-rhythm grid + per-synth octave window + portamento on octave shifts), comp (chord-rhythm pattern, voicing follows polyphony mode + arp shape), lead (motif × contour × scale subset, strong-beat chord-tone snap, per-bar mutation, CC11 swell, phrase-end pitch-bend fall, section-start velocity accent), pad (mid-energy chord wash), counter-melody (parallel-3rd shadow at high energy), drone (M0/M1/M10 tonic+5th pedal), riser (reverse cymbal on energy jumps), ear-candy (off-beat bell stabs).
- **Per-mood biases**: 11 moods (M0 ambient → M10 cinematic), each with its own GM-program palette, groove template pool, energy-curve preferences, form preferences, layer-activation gates.
- **Per-mood FX chain** (pedalboard): genre-appropriate reverb / delay / chorus / phaser / EQ.
- **Master bus**: HighpassFilter@40Hz, low-shelf -1.5 dB, high-shelf +1.5 dB.
- **LUFS normalisation** to -16 LUFS via pyloudnorm; peak ceiling -1.5 dBFS.
- **Quality scoring**: heuristic (LUFS / crest / spectral balance / stereo width) + optional psychoacoustic (Zwicker loudness, DIN sharpness via mosqito).
- **Provenance**: WAV LIST/INFO chunk with hash, mood, mode, key, tempo, form, bars, groove, curve.
- **Form-driven structure**: 24+ forms drive bar count and section letters; per-section motifs / contours / chord-rhythm patterns; drum fills on section transitions; crash on new-section downbeats.

## CLI flags

```
soundhash <file>
  --midi             write .mid
  --audio            render .wav (requires fluidsynth on PATH)
  --mp3              also write .mp3 (requires lame)
  --flac             also write .flac (requires flac CLI)
  --mood Mxx         override mood (M0..M10)
  --mime auto|off|strict|<type>
  --score            heuristic 0..1 quality summary after render
  --psy              mosqito loudness + sharpness summary
  -v, --verbose      dump SongSpec breakdown
```

## Status

| | |
|---|---|
| Tests | 20 passing (decode invariants + render + corpus regression) |
| Layers | 9 musical (drums, bass, comp, lead, pad, counter, drone, riser, ear-candy) + meta |
| Moods | 11 (M0–M10) |
| Forms | 24 |
| Energy curves | 16 |
| Groove templates | 16 |
| Drum kits | 12 |
| Bass patterns | 36 |
| Chord progressions | 90 |
| Showcase score | heuristic 0.85 avg, psychoacoustic 0.98 avg |
| Audio determinism | bit-identical within arch (Docker canonical pending) |

See `DESIGN.md` for the full spec; per-dimension research lives in `research/`.

## Setup

```bash
brew install fluid-synth lame flac           # mac; renderer + encoders
pip install -e ".[dev,render]"               # python deps + tests
pip install pyloudnorm pedalboard mosqito    # quality scoring (optional)
```

A CC0/permissive GM SoundFont must be at `assets/v1/sf2/MS-Basic.sf3`. The repo's `.gitignore` excludes the `sf2/` directory; download MuseScore's MS Basic SF3 (~50 MB) from the MuseScore source repo, or set `SOUNDHASH_SOUNDFONT=/path/to/your.sf2`.

## Repo layout

```
DESIGN.md                  ← full spec
research/                  ← 14 research dimensions (one folder each)
src/soundhash/
  decode.py                ← hash → SongSpec
  spec.py                  ← SongSpec dataclasses
  theory.py                ← Roman numeral resolution
  mime.py                  ← MIME → mood family
  quality.py               ← heuristic + psychoacoustic scoring
  showcase.py              ← per-mood demo generator
  cli.py                   ← entry point
  render/
    midi.py                ← SongSpec → .mid (9 layers)
    audio.py               ← .mid → .wav (fluidsynth + LUFS + provenance)
    fx.py                  ← per-mood FX chains + master EQ
  tables/                  ← static-table loader
assets/v1/                 ← 58 JSON tables (forms, drums, comp, melody, …)
tests/                     ← decode invariants, render smoke, corpus regression
showcase/                  ← demo output (gitignored)
```
