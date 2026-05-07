# Metadata Embedding

Goal: every artifact is self-describing. Given just the file, you can recover the input hash, library versions, and the SongSpec digest.

## Common payload (all formats)
```json
{
  "soundhash": "v1",
  "input_sha256": "<64 hex>",
  "spec_sha256": "<64 hex of canonical-JSON SongSpec>",
  "manifest_sha256": "<64 hex of versions manifest>",
  "rendered_at": null,            // null on purpose — determinism, no timestamps
  "ascii_card": "lofi · Cm · 90bpm · I-VI-III-VII · pluck-bass · vibes-lead",
  "tables_version": "v1"
}
```
We deliberately omit timestamps so output is byte-identical across renders.

## WAV
- Use **BWF `bext` chunk** for high-level fields and a custom **`iXML` chunk** for the JSON payload. iXML is widely supported and a free-form XML container; we put the JSON inside `<USER><SOUNDHASH>{json}</SOUNDHASH></USER>`.
- Also write a RIFF `INFO` `ICMT` (comment) field with a one-line summary `soundhash:v1:<input_sha256_first16>:<spec_sha256_first16>`. Tools like Finder/Explorer surface this.
- Avoid `id3 ` chunks in WAV (some players mis-handle them).

## MP3
- ID3v2.4 frames:
  - `TXXX:soundhash` → JSON payload (UTF-8).
  - `TIT2` (title) → ASCII card.
  - `TPE1` (artist) → "soundhash".
  - `TALB` → input_sha256 first 16 hex.
- Use ID3v2.4 with UTF-8 (not v2.3 with UTF-16) to avoid BOM nondeterminism.

## FLAC
- Vorbis comments: `SOUNDHASH=<json>`, `TITLE=<ascii_card>`, `ARTIST=soundhash`, `INPUT_SHA256=<hex>`, `SPEC_SHA256=<hex>`.
- Padding block fixed size 0 (or strip entirely) for byte-determinism.

## MIDI
Self-document every dimension via meta events at tick 0 of track 0:
- Text event (`0xFF 01`): `soundhash v1 input=<hex>`
- Marker events (`0xFF 06`) per dimension:
  - `MOOD=lofi` `KEY=Cm` `TEMPO=90` `FORM=AABA` `PROG=i-VI-III-VII` `KIT=lofi-808` `LEAD=vibes` etc.
- Standard `Set Tempo` and `Time Signature` meta events for canonical playback.
- Track names per layer: `Drums`, `Bass`, `Comp`, `Lead`, `Aux`.
- Copyright meta: `soundhash deterministic v1 — no copyright`.
- Use `ticks_per_beat=480`, format 1, multi-track. Pin mido version.

## Schema collisions to avoid
- BWF `bext` has fixed 256-byte description and 32-byte originator fields — don't overflow.
- iXML must be valid XML; embed JSON inside CDATA.
- ID3 `TXXX` description field must be unique per frame; we use exactly one `soundhash` description.
- FLAC `VENDOR_STRING` is set by encoder — leave alone, do not override (can change with encoder version, but it lives in the streaminfo block which we accept as a versioned artifact).
- MIDI marker events are 7-bit ASCII only; if any field needs UTF-8, base64 it.

## Sidecar (optional)
`<basename>.soundhash.json` — full SongSpec + manifest + ASCII card. Useful for debugging and for clients that strip metadata (some chat apps).

## Verifiability
Given a WAV, we can:
1. Parse iXML → extract JSON.
2. Recompute `spec_sha256` from a renderer round-trip → assert equality.
3. Compare `manifest_sha256` against runtime manifest → flag drift.
