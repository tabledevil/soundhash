# Version & Manifest — soundhash v1

## Versioning policy

- **Major versions only.** v1, v2, v3. No semver minor/patch that changes output.
- **v1 is frozen forever.** A v1-decoded SongSpec for hash H is bit-identical in 2026, 2030, 2040.
- **All majors coexist** in the codebase. `version="v1"` selects the v1 code path; default version is the **latest stable**, but callers SHOULD pin explicitly.

## What "frozen" means

| Layer | Frozen artifacts |
|---|---|
| Decoder code | `soundhash/v1/decoder.py` — never edited after release |
| Tables | `tables/v1/**` — never edited after release |
| HKDF labels | `tables/v1/labels.json` — never edited |
| Renderer | `soundhash/v1/render_midi.py` (mido pinned to a specific version) |
| Synth | FluidSynth `==X.Y.Z` + soundfont SHA-256 pinned in `tables/v1/render/synthpacks.json` |

## Manifest file (`tables/v1/MANIFEST.json`)

```json
{
  "version": "v1",
  "spec_release_date": "2026-05-07",
  "hkdf_salt": "soundhash-v1",
  "files": {
    "labels.json":           "sha256:...",
    "moods/macro.json":      "sha256:...",
    "harmony/voicings/ionian/0.json": "sha256:...",
    "...": "..."
  },
  "bundle_hash": "sha256:...",
  "render_pins": {
    "fluidsynth": "==2.3.4",
    "soundfont":  "sha256:...",
    "sample_rate": 48000,
    "bit_depth": 16,
    "channels": 2
  }
}
```

## Embedded version markers

- **MIDI:** track 0 tick 0 has a `text` meta event: `soundhash/v1/<hash_prefix_8hex>/<bundle_hash_prefix_8hex>`. Identifiable by tooling, ignored by playback.
- **WAV:** custom RIFF chunk `shsh` placed after `fmt ` and before `data`:
  ```
  'shsh'           | 4 bytes
  chunk_len (LE)   | 4 bytes
  ascii "v1"       | 2 bytes
  hash_bytes       | 32 bytes
  bundle_hash[:8]  | 8 bytes
  pad              | 2 bytes (chunk len even)
  ```

## Migration playbook (when v2 ships)

1. v2 directory `tables/v2/` is created **independent** of v1.
2. v2 labels may reuse v1 names BUT under `soundhash/v2/...` prefix → no collision.
3. Library exposes `version="v1" | "v2"`. Default flips to `"v2"` only after a deprecation period (≥1 year).
4. CLI tool ships with both; users opt-in to v2.
5. Determinism CI: every release runs the v1 golden-vector test on a frozen list of (hash, expected_midi_sha256) pairs. Any drift → fail.

## Forbidden actions

- ❌ Editing any file in `tables/v1/`.
- ❌ Renaming any HKDF label.
- ❌ Reordering `entries` arrays.
- ❌ Changing `hkdf_salt`.
- ❌ Changing rendering pins for v1.

## Bundle hash CI assert

At library import time:

```python
assert _compute_bundle_hash(TABLES_V1_DIR) == MANIFEST_V1["bundle_hash"], \
    "soundhash v1 tables tampered"
```

This makes accidental local edits fail loudly rather than silently produce different output.

## Golden-vector test set

`tests/golden/v1.json`:
```json
[
  {"hash": "00"*32, "midi_sha256": "...", "wav_sha256": "..."},
  {"hash": "ff"*32, "midi_sha256": "...", "wav_sha256": "..."},
  {"hash": "deadbeef..." , "midi_sha256": "...", "wav_sha256": "..."},
  ... 64 vectors
]
```
Run on every commit. A failure here means we accidentally broke v1 determinism.
