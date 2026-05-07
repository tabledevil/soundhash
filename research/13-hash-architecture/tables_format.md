# Table Format — soundhash v1

## Top-level layout

```
tables/v1/
  MANIFEST.json              # bundle hash + per-file hashes
  labels.json                # HKDF label registry
  moods/macro.json           # 16 macro mood archetypes
  moods/sub.json             # 8 sub-flavors per macro (nested)
  tempo/buckets.json         # 64 tempo entries
  keys/roots.json            # 12 chromatic roots
  modes/list.json            # 7 modes (+ optional modal mixture sets)
  timesig/swing.json         # 8 (ts × swing) combos
  form/templates.json        # 16 form templates
  harmony/progressions.json  # 64 progressions, per (mode) pre-filtered
  harmony/voicings/<mode>/<root>.json   # pre-filtered voicing tables
  drums/kits.json            # 16 GM-ish kits
  drums/patterns/A.json      # 32 patterns, tagged per mood/tempo
  drums/patterns/B.json
  drums/fills.json           # 16 fill banks
  bass/patterns.json         # 32 patterns, scale-degree relative
  comp/roles.json            # 8 roles
  comp/arps.json             # 16 arpeggio shapes
  melody/subsets.json        # 8 scale-subsets per mode
  melody/motifs.json         # 32 motifs in scale-degree form
  melody/contours.json       # 16 contour templates
  aux/earcandy.json          # event-type bank
  expression/velprofiles.json
  expression/cccurves.json
  render/synthpacks.json
  render/fx.json
  render/mix.json
```

## Schema convention (JSON, every file)

Every table file is an object:

```json
{
  "label": "soundhash/v1/<dimension>/<table>",
  "version": "v1",
  "size_pow2": false,
  "entries": [
    { "id": 0, "name": "...", "data": { ... }, "tags": ["...", "..."] },
    ...
  ]
}
```

Rules:
- `entries[i].id` MUST equal index `i`. Lookup is `entries[byte % len(entries)]`.
- `entries` is **append-only** within a major version. To deprecate, mark `"deprecated": true` but leave the slot occupied (or the % math shifts).
- `size_pow2: true` documents that we hand-curated to a power of 2 for zero bias.
- `tags` are used at table-build time for static pre-filtering.

## Static pre-filter generation

A build script (`build_tables.py`) materializes filtered tables:

```
for mode in modes:
  for root in roots:
    voicings_full = load("harmony/voicings/master.json")
    voicings_mode = [v for v in voicings_full if mode in v.tags]
    voicings_root = [transpose(v, root) for v in voicings_mode]
    write(f"harmony/voicings/{mode}/{root}.json", voicings_root)
```

The decoder **never** reads `master.json`; it reads the already-filtered mode/root file. This means:
- Lookup is O(1).
- The hash byte's % length is always against the **filtered** length, so distinguishability of files within (mode, root) is preserved.
- Build determinism: filter is a pure function of the master file + mode/root keys → CI-reproducible.

## Runtime filter (Tier 2) — narrow use only

Used only for "register × current-chord-voicing" trimming on melody and bass:

```python
def filter_pitches(candidates: list[int], chord: Chord, register: tuple[int,int]) -> list[int]:
    out = [p for p in candidates if register[0] <= p <= register[1]]
    if not out:
        out = list(candidates)        # fallback: unfiltered, never empty
    return sorted(out)                # canonical order for determinism
```

Determinism rules for runtime filters:
1. Pure function (no globals, no time).
2. Inputs: only previously-decided spec fields.
3. Output: **always sorted** by a documented key.
4. Never empty (fallback to input).
5. Listed in `runtime_filters.md` (≤6 functions; we cap this).

## Adding a new entry without breaking determinism

Within v1, no edits to existing slots. To add a new pattern, we **cannot** append to v1 (would change `len(entries)` and shift modulo). We ship v2.

To make tables **expansion-friendly without bumping major version**, slots may be marked `"reserved": true` in v1 and replaced by real entries in v1.0.x **only if** v1.0.x explicitly says so AND the manifest hash changes AND the spec version string in MIDI/WAV becomes `v1.0.x`. Default policy: **don't do this**; just bump to v2.

## Bundle hash

```
bundle_hash = SHA256( sorted(file_path + ":" + sha256(file_contents) for file in tables/v1/) )
```

Pinned in `pyproject.toml` as a runtime assertion at decoder import time.
