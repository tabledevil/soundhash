# soundhash

Deterministic musical hash. Convert a file's SHA-256 into ≤30 seconds of pleasant, music-theory-correct audio that's easily distinguishable between files. Same hash → identical output, anywhere.

> **Status:** v0.0.1 — design phase. The repo currently contains:
> - the full design document (`DESIGN.md`),
> - per-dimension research artifacts (`research/`),
> - asset stubs (`assets/v1/`) — most carried forward from research,
> - empty Python skeleton (`src/soundhash/`).
>
> No audio rendering yet. See `DESIGN.md` §12 for the vertical-slice roadmap.

## Quickstart (planned)

```bash
soundhash path/to/file               # writes path/to/file.soundhash.wav
soundhash --midi path/to/file        # writes .mid only
soundhash --mood M5 path/to/file     # override MIME-derived mood
soundhash --mime=off path/to/file    # use hash byte 0 for mood instead
```

## Design overview

See `DESIGN.md` for the full spec. Key ideas:
- 14 musical dimensions, each picked from a curated lookup table, hierarchically constrained so bad combinations are impossible.
- 32 bytes of SHA-256 → macro decisions; HKDF-Expand fills per-bar and per-note streams.
- Render via existing tools (FluidSynth + curated SoundFonts, sfizz). No custom synth code.
- Determinism is byte-identical within an arch (Docker canonical), perceptually identical (ViSQOL > 4.5) cross-arch.

## Repo layout

See `DESIGN.md` §11.
