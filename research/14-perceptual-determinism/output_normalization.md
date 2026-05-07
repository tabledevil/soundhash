# Output Normalization

## Loudness
- **Target: -16 LUFS integrated**, true-peak ceiling **-1.0 dBTP**.
- Rationale: -16 LUFS is the streaming-safe floor (Spotify -14, YouTube -14, Apple Music -16, broadcast EBU R128 -23). Going to -14 risks turn-down on platforms and is too hot for embedded UI playback (icon-style use case = often previewed in browser tabs). -16 keeps headroom for the inevitable transient drum hits without limiter pumping.
- Tool: `pyloudnorm` (ITU-R BS.1770-4) for measurement; gain applied as a single static scalar (no compression). Then a deterministic true-peak limiter (4× oversampling, fixed lookahead 1.5 ms) clamps to -1 dBTP.
- **No** ffmpeg `loudnorm` two-pass — the `linear=true` single-pass mode is acceptable only if measured values are passed explicitly; we prefer pyloudnorm + custom limiter for full control.

## Peak vs loudness
Loudness normalization preferred. Peak normalization makes a sparse arpeggio sound quiet next to a dense drum loop. We commit to perceptual loudness consistency across the corpus.

## Stereo image
- Default: stereo, but **mono-compatible**: mid/side ratio target ≥ 0.7 mid energy. Verify by summing L+R and checking energy loss < 3 dB.
- Mood-driven width:
  - "ambient", "lofi", "dream" → wide (Haas <20 ms or true stereo synth output).
  - "techno", "punchy", "marimba-percussion" → narrow/centered (mid-heavy).
- Width selection is a **table choice keyed by mood**, not a runtime free parameter. So determinism holds.
- Hard rule: drums and bass always centered (mono). Stereo info goes to pads, leads, aux.

## Fades and clicks
- Fade-in: 5 ms linear ramp from -inf to 0 dB. Eliminates DC click and synth attack pop. (1 ms is too short for some sample-based attacks; 50 ms loses transient information.)
- Fade-out: scaled to reverb tail. If reverb RT60 ≈ 1.2 s, fade = min(1.5 s, remaining_audio). For dry mood patches, fade = 200 ms.
- Detection: measure RMS-tail decay; fade starts when RMS first drops 20 dB below peak after natural song-end marker.

## Length policy
- **Natural end ≤ 30 s + reverb tail**, capped hard at 32.0 s.
- Form module emits an explicit "song-end" sample index. Renderer continues to capture reverb tail until RMS < -60 dBFS or 2 s after end-marker, whichever is sooner.
- Hard 30 s cuts feel unmusical — we end on a cadence beat, even if that means 24 s for half-time tunes or 29 s for fast ones.
- Minimum length: 12 s (anything shorter feels like a stinger). Form table is filtered to ensure ≥12 s.

## Final container
- WAV: PCM 16-bit, 48 kHz, stereo. No compression. Size ≈ 5.5 MB for 30 s.
- Optional MP3 sidecar at 192 kbps CBR (LAME pinned version) for distribution. CBR (not VBR) for byte-determinism.
- Optional FLAC: deterministic if `--no-padding --no-seektable` and pinned encoder.

## Dithering
Float32 → PCM16 conversion uses **TPDF dither at -90 dBFS, deterministic noise from HKDF stream** (not system random). Without dither, quiet tails truncate audibly. Dither is reproducible because its noise bytes are hash-derived.
