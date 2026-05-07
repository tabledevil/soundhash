# Dimension 11 — MIME-type / file-metadata → mood/palette mapping

## Why MIME at all?

Pure-hash mood selection (byte 0 picks from N moods) gives audio that has **no semantic relationship to file content**. A photo and a tax PDF can collapse to the same archetype.

MIME-aware mapping gives:
- **Recognizability**: a user can hear "image-y" before reading the filename.
- **Free entropy**: byte 0 no longer has to encode "which mood family" — it refines *within* a family.
- **Reduced cross-kind collisions**: MP3 and Word doc never share the same archetype family.

Cost:
- All files of the same MIME share a family (a 5KB JPG and a 5GB MOV both = video-or-image-ish at the family layer; sub-mood and downstream bytes still distinguish).
- MIME detection is **non-deterministic across detectors/platforms** unless we pin one. This is the biggest risk.

## Architecture: MIME → family → byte 0 → sub-mood

```
file → detect(file) → family ∈ FAMILIES (12)
                        → family.mood_pool (4 candidates)
                          → byte0 % 4 picks sub-mood
                            → byte1 picks brightness (existing)
```

Macro mood goes from 1 step (byte 0 mod 32) to 2 steps (family from MIME, then byte 0 mod 4). 12×4 = 48 archetypes — more than the original 32, and now meaningful.

## `mime_families.json` — 12 families

```json
{
  "version": "1",
  "families": [
    {"id":"text_code","label":"Text / Source code",
     "mimes":["text/plain","text/x-python","text/x-c","text/x-java","application/json","application/xml","text/yaml","text/markdown","application/javascript","text/x-shellscript"],
     "exts":[".py",".c",".h",".cpp",".java",".js",".ts",".rs",".go",".rb",".sh",".json",".yaml",".yml",".toml",".md",".txt",".xml"]},
    {"id":"image","label":"Image",
     "mimes":["image/jpeg","image/png","image/gif","image/webp","image/avif","image/heic","image/tiff","image/svg+xml","image/bmp"],
     "exts":[".jpg",".jpeg",".png",".gif",".webp",".avif",".heic",".tif",".tiff",".svg",".bmp"]},
    {"id":"audio","label":"Audio",
     "mimes":["audio/mpeg","audio/wav","audio/x-wav","audio/flac","audio/ogg","audio/aac","audio/x-m4a","audio/midi","audio/opus"],
     "exts":[".mp3",".wav",".flac",".ogg",".aac",".m4a",".mid",".midi",".opus",".aiff"]},
    {"id":"video","label":"Video",
     "mimes":["video/mp4","video/quicktime","video/x-matroska","video/webm","video/x-msvideo","video/mpeg"],
     "exts":[".mp4",".mov",".mkv",".webm",".avi",".mpg",".mpeg",".m4v"]},
    {"id":"archive","label":"Archive / packed binary",
     "mimes":["application/zip","application/x-tar","application/gzip","application/x-7z-compressed","application/x-rar-compressed","application/x-bzip2","application/x-xz"],
     "exts":[".zip",".tar",".gz",".tgz",".7z",".rar",".bz2",".xz",".tar.gz"]},
    {"id":"document","label":"Document (prose)",
     "mimes":["application/pdf","application/msword","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/rtf","application/epub+zip"],
     "exts":[".pdf",".doc",".docx",".rtf",".epub",".odt",".pages"]},
    {"id":"spreadsheet","label":"Spreadsheet / tabular data",
     "mimes":["application/vnd.ms-excel","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","text/csv","text/tab-separated-values","application/vnd.oasis.opendocument.spreadsheet"],
     "exts":[".xls",".xlsx",".csv",".tsv",".ods",".numbers",".parquet",".arrow"]},
    {"id":"executable","label":"Executable / compiled binary",
     "mimes":["application/x-executable","application/x-mach-binary","application/x-msdownload","application/x-elf","application/wasm","application/java-archive"],
     "exts":[".exe",".dll",".so",".dylib",".bin",".o",".class",".jar",".wasm",".app"]},
    {"id":"font","label":"Font",
     "mimes":["font/ttf","font/otf","font/woff","font/woff2","application/font-woff"],
     "exts":[".ttf",".otf",".woff",".woff2",".eot"]},
    {"id":"model3d","label":"3D model / CAD",
     "mimes":["model/gltf-binary","model/gltf+json","model/obj","model/stl","application/x-blender"],
     "exts":[".obj",".stl",".gltf",".glb",".fbx",".blend",".dae",".3ds",".step",".usdz"]},
    {"id":"web_asset","label":"Web asset (markup/style)",
     "mimes":["text/html","text/css","application/xhtml+xml"],
     "exts":[".html",".htm",".css",".scss",".less"]},
    {"id":"unknown","label":"Unknown / opaque",
     "mimes":["application/octet-stream"],"exts":[]}
  ]
}
```

## `family_to_moods.json` — 4 sub-moods per family

```json
{
  "text_code":  ["minimal_clicky","8bit_chiptune","lo-fi_study","modular_blip"],
  "image":      ["bright_lyrical","dreamy_pad","playful_kalimba","sun_arp"],
  "audio":      ["meta_atmospheric","tape_warble","spectral_drone","vinyl_dub"],
  "video":      ["cinematic_orchestral","trailer_riser","synthwave_score","noir_jazz"],
  "archive":    ["industrial_dark","bitcrushed_pulse","vault_lowend","concrete_clang"],
  "document":   ["library_calm","felt_piano","string_quartet","music_box"],
  "spreadsheet":["clockwork_grid","steve_reich_min","bossa_clave","poly_marimba"],
  "executable": ["stark_electronic","machine_techno","circuit_bent","cli_bleeps"],
  "font":       ["typographic_pizz","glyph_celesta","serif_choral","mono_sequencer"],
  "model3d":    ["lush_scifi","voxel_arp","prog_synth","ambient_geometry"],
  "web_asset":  ["web2_jingle","ambient_browser","css_wave","html5_chime"],
  "unknown":    ["mystery_drone","gritty_lofi","static_field","empty_room"]
}
```

Each label is a key into pool tables defined by dims 1/2/3/5/12 (e.g. `cinematic_orchestral` → tempo 70-95, modes [aeolian, dorian], kit [orch_perc], synths [strings, brass, cinematic_pad]).

## MIME detection — deterministic spec

**Spec v1:**
1. Use `python-magic` against a **bundled, version-pinned `magic.mgc`** (libmagic 5.46) checked into the repo. No system fallback.
2. If pinned-libmagic returns `application/octet-stream` or `inode/x-empty`, fall back to **extension lookup** (last suffix, lowercased) against `mime_families.json`.
3. If extension also unknown → family `unknown`.
4. We do **not** use OS UTI, HTTP `Content-Type`, or stdlib `mimetypes` (varies by Python version).

The bundled `magic.mgc` hash is part of the spec version. Bumping it bumps soundhash version (v1 → v2) because output WAV bytes can change.

## Byte allocation impact

Original sketch: byte 0 = macro-mood (32-archetype mod-table).
New: family is **free** (derived from file). Byte 0 mod 4 = sub-mood within family. Byte 1 unchanged.

Byte 0 effective entropy at the macro stage rises from log2(32)=5 bits to log2(48)≈5.58 bits, *and* it is semantically meaningful.

## File-size, mod-date, filename — fold in?

- **File size**: Reject. Redundant with hash for content-uniqueness; bracket boundaries create arbitrary "why is 1.01 MB different" cliffs; weakens determinism if user appends a newline.
- **Mod-date / ctime**: Reject hard. Filesystem-dependent; copies break it; violates "same bytes → same audio".
- **Filename**: Reject by default; expose `--include-filename` opt-in. Filename is metadata, not content. Default contract: identical bytes → identical audio.

MIME is the only metadata signal used by default. Everything else is opt-in.

## Edge cases

- **`application/octet-stream`**: extension fallback; else `unknown`. The `unknown` family's moods are textural/uncommitted (drones, lofi).
- **`text/plain`** is heterogeneous (license / TSV / poem / log). Mapped to `text_code`; downstream hash entropy distinguishes.
- **`application/zip`** could be docx/jar/epub/ODF. libmagic strict mode usually disambiguates; if not, family = `archive`. No recursive peek (would break determinism on tiny content changes).
- **Polyglot files**: libmagic returns first match; deterministic given pinned DB.
- **Empty files**: SHA-256 fixed; MIME = `inode/x-empty` → `unknown`. Output: fixed boring drone.
- **Symlinks / device files**: resolve symlinks; refuse devices.

## Provenance

MIDI track 0 embeds a `text` meta-event:
```
{"v":"soundhash/1","sha256":"…","mime":"image/png","family":"image","sub":"dreamy_pad","override":null}
```
Auditable. Output still depends only on hash + family deterministically.

## User override

- `--family <id>` forces a family.
- `--include-filename` mixes SHA256(basename) into salt.
- `--mime-detect [libmagic|extension|none]` forces detection method.

All overrides are recorded in provenance, so override-derived audio is distinguishable from default-pipeline audio. Determinism preserved: same hash + same flags → same output.

## Adversarial-anticipation

- *JSON config vs Python file?* Same family (`text_code`); byte 0 differentiates. Could split into `text_data` vs `source_code` if we want; flagged as a knob.
- *libmagic non-determinism* → addressed by pinning + bundling magic.mgc.
- *No libmagic on system* → extension fallback; document that bundled libmagic is canonical (mode `soundhash/1-libmagic` vs `soundhash/1-ext`).
- *Cliché labels* (font → typographic_pizz, etc.) — yes, some are precious. Pool is swappable.
- *web_asset = text_code with extra steps?* Defensible split given visual nature; mergeable to 11 families.

## Open questions for orchestrator

1. Split `text_code` into source vs data? (toggle, not a blocker)
2. Add `notebook` family (.ipynb, .rmd)? Currently in `text_code`/`document`.
3. Add `database` family (`application/x-sqlite3`, `.db`, `.parquet`)? Currently `unknown`/`spreadsheet`.
