# Changelog

All notable changes to the soundhash project. Format: reverse chronological, grouped by milestone.

## v0.0.1 — initial scaffold + research

- Repo scaffold: pyproject, src/soundhash skeleton, asset stubs.
- 14 dimensions of research under `research/<NN-slug>/`.
- 58 curated JSON tables under `assets/v1/`.
- Decoder skeleton consumes 32-byte HKDF macro stream.
- DESIGN.md, README.md, MIME family resolver, soundfont bootstrap.

## v0.1.0 — first PyPI release

- Bumped version to 0.1.0; added MIT LICENSE.
- Filled in PyPI metadata: authors, license, classifiers, project URLs,
  keywords, full README rendering.
- Wheel build: pure-Python `py3-none-any` (~144 KB). Asset bundle ships
  inside the wheel as `soundhash/_assets/v1/...`; SoundFonts are
  excluded and downloaded on first run.
- All asset-loading modules (`tables`, `mime`, `render.audio`,
  `setup_assets`) check the dev path first and fall back to the wheel
  layout, so `pip install soundhash` works the same as `-e .`.
- `dev` extra now pulls `build` + `twine` for release tooling.
- Self-test SHA unchanged; 23/23 fast tests green on the wheel.

## Meter flexibility (post-M2)

- New HKDF label `meter/timesig` drives `time_sig` from a dedicated 1-byte
  spillover. ~94% of hashes still land on 4/4; ~6% of opt-in moods land on
  3/4, 6/8, or 12/8 (drawn from each mood's `time_sigs` list).
- Self-test seed unchanged (byte = 147, below the 240 threshold).
- 7/8 and 5/4 declared by some moods but held back until drum/comp/motif
  banks have coverage; falls back to 4/4 transparently.

## Milestone 2 — vertical slice

- 9-layer MIDI render: drums, bass, comp, lead, pad, counter, drone, riser, ear-candy.
- WAV render via `fluidsynth -ni` shell-out + MS-Basic.sf3 SoundFont.
- LUFS norm to -16 / true-peak limit / cosine fades.
- Per-mood pedalboard FX chains (reverb / delay / chorus / phaser / EQ).
- 11-mood showcase generator (`python -m soundhash.showcase`) + browser HTML.
- MP3 + FLAC export.
- Heuristic (LUFS / crest / spectrum / width) + mosqito psychoacoustic scoring.
- 4 new moods added per user feedback: M11 lofi, M12 chillout, M13 simple, M14 gameboy.

## Adversarial-review batch

5 parallel reviewers (codex + gemini × 5 areas: implementation, sound design, musical spectrum, quality measurement, dimensions audit) flagged 18 P0/P1/P2 items.

### P0 — correctness bugs
- Reorder `_postprocess_wav`: FX → LUFS → fades → peak limit (was LUFS-before-FX, so the -16 LUFS contract was a lie).
- Clear `_GROOVE_CACHE` per-render (asymmetric leak vs. `_VEL_JITTER_CACHE`).
- `_lead_octave(spec)` actually used by `_counter_track` (was hardcoding 72).
- Dropped duplicate `counter_program` assignment.
- Empty-progression infinite-loop guard.

### P1 — spec gaps
- **Accent skeleton wired** (highest-distinguishability-per-byte feature). HKDF byte from `melody/accent_skeleton` picks 4 strong-beat chord-tone targets weighted [R 35%, 3 30%, 5 25%, 7 10%] + a 3-value micro_shape applied to weak slots.
- **Layer activation matrix** (byte 25) consumed; 16 matrices on disk filtered to 10 lead-audible ones.
- **Voicing style** (byte 8) with 10 implementations: close_triad / open_triad / sus_open / quartal / power / shell / drop2_7th / drop3_7th / rootless_A / rootless_B.
- Mood family rebalance (no mood in >5 family slots; M4/M8 raised from 1 → 3 each).
- M11–M14 progressions explicitly tagged (39 progressions tagged, was 0).
- Triage metrics added: `level_range_db`, `loop_repetition`, `low_band_side_width`.

### P2 — polish
- Counter-melody now has 4 modes (parallel_3rd / parallel_6th / contrary / octave_below).
- Bass + comp register guards (comp.top ≤ lead.median - 5).
- Drum escalation algos picked from byte 12 (2 of 8 implemented in render: `linear_add`, `ghost_note_stack`).
- Locrian + jazz_minor reachable; sub-60 BPM for M0/M10.
- Label registry test un-skipped; 2 live unregistered labels added.

### Sound-design adversarial pass
- MIME resolver promoted from top-level stub to exact → prefix → fallback against `mime_families.json`.
- Master EQ retargeted at MS-Basic SF3's actual problem bands (200-400 Hz mud, 2.5-4.5 kHz plastic).
- Dropped GM 82 Calliope + GM 87 from inappropriate slots; M2 counter de-aliased from comp.
- M6 chain reordered so reverb tails don't pump.
- Lead palettes expanded 3 → 5-8 candidates per mood for "main voice variety".

## Reserved-byte wiring (post-review)

After P-stack closed, all remaining "reserved/unused" macro bytes were wired:

- **byte 1** — 4 mood sub-flavors (stock / brighter / darker / tighter), each tweaks tempo and lead octave.
- **byte 27** — 6 humanization profiles scaling vel-jitter (machine / groove-tight / groove-loose / acoustic-lively / ballad-rubato / swing-jazz).
- **byte 29** — 4 FX wet scales (0.6 / 0.9 / 1.0 / 1.15) multiplying any plugin `wet_level` / `mix` kwargs.
- **byte 30** — 4 mix-balance presets (balanced / bass_forward / lead_forward / minimal) emitting per-layer CC7 channel volume.

## Documentation

- BYTES.md — full byte-by-byte map with filter chain, table size, empirical distributions.
- DESIGN.md §13 — implementation status with 31/32 bytes wired, only #84 invasive deferred.
- showcase/showcase.html — browser preview of 15-mood demo.

## Late additions

- **All 8 drum escalation algos** now render-active (linear_add, ghost_note_stack, subdivision_double, snare_roll_crescendo, tom_rollup, hat_density_ramp, polyrhythm_overlay, reverse_cymbal_sweep). Each picks deterministically from byte 12; render applies on rising-energy bars (Δ ≥ 0.08).
- **`--self-test` CLI** subcommand: renders a fixed seed and verifies its MIDI SHA against a baseline. Catches accidental output drift from refactors / dep upgrades.

## Known deferred work

- **#84 time_sig + swing de-hardcode** — render currently assumes 4/4 in dozens of places (drum patterns 16-cell grid, comp chord_rhythm grid, melody motif `total_beats`). Multi-day rework.
- **Phrase shape (byte 21)** — phrase_shapes.json on disk; phrase shape is implicit in motif `total_beats` for now.
- **Cross-arch determinism** — host-bound to Apple Silicon + fluidsynth 2.5.4 + MS-Basic SF3. Docker canonical or per-arch wheel matrix is the next step.
