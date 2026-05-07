# Soundhash — Shared Project Context

> Read this first. Every researcher has the same context. Your dimension-specific brief is in your prompt.

## Goal

Deterministically convert a file's **SHA-256 hash** (32 bytes, optionally extended with HKDF) into **≤30 seconds of pleasant, music-theory-correct audio** that is easily distinguishable between different files. Same hash → bit-identical audio, anywhere.

Inspiration: visual identicons (e.g. GitHub's), but for audio.

## Inputs

- **Primary:** SHA-256 of file bytes (32 bytes = 256 bits = 256 decision tokens of 1 byte each).
- **Secondary (optional):** MIME type and/or file metadata can map to **macro mood/palette** *before* hash bytes are consumed — frees up budget and gives semantic flavor (audio file → different palette than image file).
- **Rule:** hash is consumed as a stream of bytes; never consult bits 1:1.

## Output

- ≤30 seconds.
- Primary artifact: a deterministic **SongSpec** (in-memory structure that fully describes every note, velocity, CC, articulation, layer activation, FX setting).
- Renderer 1: SongSpec → **MIDI** (using mido / pretty_midi / similar).
- Renderer 2: SongSpec + MIDI → **WAV** via existing open-source synths/samplers (FluidSynth + SoundFonts, sfizz, Surge XT, Dexed, Sforzando, etc.). **Do not write our own synths.** Synth choice is itself a hashable dimension.
- Layers: **at least 4, more is fine** (drums, bass, comp/pad, lead, counter-melody, drone, ad-libs, FX risers — all welcome).

## Core principle: hierarchical constraint propagation

Each byte selects from a **lookup table**, but the table is **filtered by all prior choices**, so `byte % len(filtered_table)` is always musically valid. Bad combinations are impossible because they're never in the table.

Decision tree, top-down:

```
mime/macro mood → tempo, key/mode, kits, progression-pool, synth-palette
  key+mode → scale, voicing ranges
    progression → bar count, harmonic rhythm, target chord per bar
      form → section layout, energy curve over bars
        per-bar density → which layers active, which patterns at which intensity
          per-layer pattern → notes/rhythm constrained to current chord & scale
            articulation → CC/velocity/expression
              mix → FX sends, balance
```

## Music theory baked into tables, not runtime

The runtime never enforces theory. The tables are pre-curated so anything you pick is correct:
- Melody works in **scale degrees**, not raw pitches; resolved to pitch using current chord's diatonic context.
- Voice leading is **precomputed** in voicing tables.
- Bass patterns output degrees relative to **current chord root**, not key root.
- Range guards on every layer.
- Strong-beat preference for chord tones, weak-beat for passing tones, encoded in contour tables.

## Determinism contract

- Identical SHA-256 → identical MIDI → identical WAV bytes (assumes pinned synth/soundfont versions, fixed sample rate, fixed renderer flags).
- Tables are static JSON, version-pinned.
- Any randomness must come from the hash, never from the system.

## Initial byte budget sketch (will be refined by dimension #13)

| Bytes | Decision area |
|---|---|
| 0 | macro mood / archetype (or derived from MIME) |
| 1 | mood sub-flavor / brightness |
| 2 | tempo |
| 3 | key root |
| 4 | mode |
| 5 | time sig + swing |
| 6 | form |
| 7-8 | chord progression + voicing style |
| 9-12 | drum kit + patterns A/B + fill bank + escalation algo |
| 13-14 | bass pattern + bass synth/octave |
| 15-17 | comp role + comp synth + arp shape |
| 18-22 | melody scale subset + motif + contour + synth + articulation |
| 23 | counter-melody / extra-layer flags |
| 24-26 | energy curve + layer activation matrix + per-bar mutation seed |
| 27 | humanization |
| 28-29 | FX sends |
| 30 | mix balance preset |
| 31 | variation salt |

If we run out of bytes, we expand via HKDF: `salt = SHA256(file)`, then derive more material with `HMAC(salt, "soundhash/v1/melody")` etc.

## Dimensions being researched in parallel

1. Key & mode (incl. modal mixture, brief modulations)
2. Tempo, time signature, swing/groove
3. Form & energy curves over 30 s
4. Harmony: chord progressions, voicings, voice leading
5. Drums: kits, patterns, fills, escalation/de-escalation algorithms
6. Bass patterns & note selection
7. Comping layer (pad/stab/strum/arp)
8. Melody: motifs, contours, scale subsets, mutation operators
9. Extra/auxiliary layers (drone, ad-libs, risers, ear candy, counter-melody)
10. MIDI expression & humanization (velocity, CC, pitch bend, articulation)
11. MIME-type / file-metadata → mood mapping
12. Rendering stack & synth selection (existing open-source tools only)
13. Hash decode architecture: SHA-256 byte budget, constraint propagation, table format
14. Perceptual distinguishability + determinism + output normalization

## Workspace layout

Each researcher works in `/Users/tabledevil/projects/soundhash/research/<NN-slug>/`:

- `findings_v1.md` — your first-pass research and proposals
- `codex_review.md` — adversarial critique from codex
- `gemini_review.md` — adversarial critique from gemini
- `findings_final.md` — integrated final, addressing or rejecting each critique with reasoning
- `summary.md` — one-page executive summary (≤500 words) for synthesis

## CLI invocation patterns

```bash
# Codex (non-interactive)
codex exec "PROMPT TEXT" 2>&1 | tee codex_review.md
# Or pipe a long prompt via stdin:
cat prompt.txt | codex exec - 2>&1 | tee codex_review.md

# Gemini (non-interactive)
gemini -p "PROMPT TEXT" 2>&1 | tee gemini_review.md
```

When asking for adversarial critique, give the CLI:
1. The shared CONTEXT.md content (so it understands the project).
2. Your `findings_v1.md` content (the thing being critiqued).
3. A specific critique brief: spot weaknesses, missing cases, theory errors, table-size issues, edge cases, novel angles, interactions with other dimensions, anything that would make the output sound bad or non-deterministic.

Concretely, the easiest invocation pattern is:

```bash
codex exec "$(cat <<'EOF'
You are critiquing a design document for ONE dimension of a deterministic audio-hashing tool.

PROJECT CONTEXT:
$(cat /Users/tabledevil/projects/soundhash/research/CONTEXT.md)

DIMENSION UNDER REVIEW:
$(cat findings_v1.md)

YOUR TASK: <specific critique brief>
EOF
)" 2>&1 | tee codex_review.md
```

(Use `bash -c` with proper quoting; the heredoc-inside-command-substitution can be brittle. Prefer building the prompt in a temp file then piping: `cat prompt.txt | codex exec -`.)

## Output rules for researchers

- Be **deep and concrete**. Name specific scales, patterns, tempos, table sizes, algorithms.
- Cite music theory canon where it grounds choices.
- For every "we should pick X" claim, specify: table size, what byte selects it, what pre-filters apply, and what downstream choices it constrains.
- Identify interactions with neighboring dimensions explicitly (e.g. "if dim #2 picks 6/8, my drum patterns must …").
- Web search is permitted via WebFetch/WebSearch when it sharpens specifics (e.g. groove templates from MPC/Logic, GM drum maps).
- Do **not** write code beyond JSON examples or pseudocode in the markdown.
- Do **not** install packages.

## Adversarial-pass output rules

After capturing both reviews, write `findings_final.md` that:
- Lists each critique (codex + gemini) by short tag.
- For each: **accept** (and incorporate) or **reject** (with reasoning).
- Includes any **new dimensions / sub-dimensions** the adversaries surfaced that we should hand back to the orchestrator.

Then write `summary.md` (≤500 words) — the integration-ready exec summary.
