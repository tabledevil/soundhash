# soundhash

> A deterministic **musical fingerprint** for any file. Pipe in some bytes, get back ≤30 seconds of pleasant, music-theory-correct audio. Same hash → identical track.

Like an identicon — but for your ears.

```bash
pip install soundhash
mhash some/file        # plays a unique 30 s song for that file
```

```
╭─[ soundhash ]──────────────────────────────────────────────────────────────────────╮
│  hash    10d59bff…89f1    source LICENSE    mime text/plain                        │
│  mood    M3 sub-flavor 1    tempo 106.6 BPM    key G ionian    meter 4/4           │
│  form    theme_var    groove straight_4_4    voicing close_triad    curve terraces │
│  matrix  4floor_house    humanize machine (jitter ±0)    mix balanced              │
╰────────────────────────────────────────────────────────────────────────────────────╯
  bars    A · A · A · A · Avar · Avar · Avar · Avar
  energy  ▃▃▄▄▅▆▆▇
  chords  Gmaj | Dmaj | Emin | Cmaj | Gmaj | Dmaj | Emin | Cmaj
  roman   I | V | vi | IV | I | V | vi | IV

  arrangement (rows × sections):
            A     B  fill
   drums       ◆     ◆     █
   bass        ◆     ◆     ▪
   comp        ▣     ▣     ·
   lead        ◆     ◆     ·
   riser       ▪     ▪     ·

  L1 drums   ch10 kit=latin-conga  low=lc-d2-tumbao / high=lc-d4-peak-mambo
          ▶ perc_1     X··X ··X· ··X· X···
          ▶ tom_high   ···· ··XX ···· ··XX
          ▶ tom_mid    X··· X··· ···· X···
  L2 bass    ch1  prog 032 Acoustic Bass     pat=bossa_bass
  L3 comp    ch2  prog 004 Electric Piano 1  pat=dotted_8th_pad   role=piano_stab
  L4 lead    ch3  prog 011 Vibraphone        motif=m44_fnk_01
  L5 pad     ch4  prog 089 Warm Pad
  L6 counter ch5  prog 073 Flute             mode=parallel_6th

  fx        Chorus(0.7Hz) → Delay(375ms) → Reverb(0.55)    audio 44100/16-bit @ -16 LUFS

  rendered  notes 359    peak-poly 12    midi 3.1 KB    wav 4.1 MB    dur 18.0s    took 0.82s
```

The dashboard shows everything the renderer is doing: the I-V-vi-IV roman numerals next to chord names, an arrangement matrix for which layers play in which form sections (· silent, ▪ sparse, ▣ normal, █ dense, ◆ energy-scaled), a one-bar drum-pattern grid for L1, and a render-stats footer with note count, peak polyphony, and timings.

## Why

You can show someone an identicon and they'll spot a wrong digit at a glance. soundhash does the same with sound: a deterministic, musical, *memorable* signature of a file's contents. Different files → different songs. Same file → exact same song, every time, on every machine.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install soundhash
brew install fluid-synth      # mac;  apt install fluidsynth  on debian/ubuntu
mhash some/file               # auto-downloads a SoundFont (~50 MB) on first run
```

## What you can do

```bash
mhash path/to/file                  # hash + render + play (default)
mhash -o path/to/file               # write path/to/file.soundhash.wav, no playback
mhash --out my.wav path/to/file     # write to a specific path
mhash --mood M14 path/to/file       # force a mood (M0..M14)
mhash -                             # read stdin
cat foo.bin | mhash                 # ditto, auto-detected
mhash -c 4 some.iso                 # chunk mode: split into 4-MB pieces,
                                    #   play one song per chunk in order
mhash --sf fluidr3 path/to/file     # try the FluidR3 SoundFont (auto-downloads ~141 MB)
mhash --sf ~/my.sf2 path/to/file    # use any .sf2/.sf3 you already have
mhash -q path/to/file               # silence dashboard + progress (just play)

# Power CLI (full flag surface — emit midi/mp3/flac, scores, etc.):
soundhash --audio --mp3 --score path/to/file

# Per-mood demo: one sample per M0..M14, stitched into showcase/showcase.wav:
python3 -m soundhash.showcase --score
```

## A taste of the spectrum

The same file rendered through three very different moods (forced via `--mood`).

#### `--mood M14` — chiptune (LSDj-flavored)
```
╭─[ soundhash ]───────────────────────────────────────────────────────────────────╮
│  hash    7c496489…65e5    source README.md    mime text/plain                   │
│  mood    M14 sub-flavor 1    tempo 153.7 BPM    key C mixolydian    meter 4/4   │
│  form    pyramid    groove straight_4_4    voicing sus_open    curve arc        │
│  matrix  breakdown_pad    humanize groove-loose (jitter ±9)    mix lead_forward │
╰─────────────────────────────────────────────────────────────────────────────────╯
  bars    i · A · A · B · B · B · B · A · A · o
  energy  ▃▄▅▆▆▆▆▅▄▃
  chords  Amin | Fmaj | Cmaj | Gmaj | Amin | Fmaj | Cmaj | Gmaj | Amin | Fmaj
  roman   vi | IV | I | V | vi | IV | I | V | vi | IV

  L1 drums   kit=trap-808   esc=linear_add
          ▶ hat_closed X·X· X·X· X·X· X·X·
          ▶ kick       X··· ···· ··X· ····
          ▶ snare      ···· ···· X··· ····
  L2 bass    prog 039 Synth Bass 2   pat=montuno_bass
  L3 comp    prog 080 Square Lead    pat=jazz_freddie    role=synth_arp
  L4 lead    prog 084 Charang Lead   motif=m44_pop_08
  L5 pad     prog 088 New-Age Pad
  fx         HiShelf(-4dB) → Drive(2dB) → Reverb(0.10)

  rendered   notes 325    peak-poly 10    midi 3.1 KB    wav 4.3 MB    dur 15.6s
```

#### `--mood M0` — ambient
```
╭─[ soundhash ]─────────────────────────────────────────────────────────────────╮
│  hash    10d59bff…89f1    source LICENSE    mime text/plain                   │
│  mood    M0 sub-flavor 1    tempo 65.0 BPM    key G ionian    meter 4/4       │
│  form    pulse_only    groove straight_4_4    voicing power    curve flat_mid │
│  matrix  bass_lead_duo    humanize machine (jitter ±0)    mix balanced        │
╰───────────────────────────────────────────────────────────────────────────────╯
  bars    A · A · A · A · A · A · A
  energy  ▄▄▄▄▄▄▄
  chords  Gmaj | Dmaj | Gmaj | Dmaj | Gmaj | Dmaj | Gmaj
  roman   I | V | I | V | I | V | I

  L1 drums   kit=acoustic-studio   esc=reverse_cymbal_sweep
          ▶ hat_closed XXXX XXXX XXXX XXXX
          ▶ kick       X··· ·X·· ··X· ····
          ▶ snare      ···· X··· ···· X···
  L2 bass    prog 038 Synth Bass 1   pat=halfnote_fifth_walk
  L3 comp    prog 091 Choir Pad      pat=sustain_whole    role=harp_gliss
  L5 pad     prog 088 New-Age Pad
  L7 drone   prog 089 Warm Pad   tonic+5th pedal
  fx         Reverb(0.85) → Chorus(0.6Hz) → LoShelf(-1dB)

  rendered   notes 64    peak-poly 8    midi 0.9 KB    wav 5.3 MB    dur 25.9s
```

#### `--mood M11` — lofi (jazzy)
```
╭─[ soundhash ]────────────────────────────────────────────────────────────────╮
│  hash    c32a49aa…2e01    source BYTES.md    mime text/plain                 │
│  mood    M11 sub-flavor 0    tempo 70.1 BPM    key A# dorian    meter 4/4    │
│  form    AABA    groove dilla_feel    voicing open_triad    curve arc        │
│  matrix  band_basic    humanize groove-loose (jitter ±9)    mix lead_forward │
╰──────────────────────────────────────────────────────────────────────────────╯
  bars    A · A · A · A · B · B · A · A
  energy  ▃▄▅▆▆▅▄▃
  chords  A#maj | Gmin | Cmin | Fmaj | A#maj | Gmin | Cmin | Fmaj
  roman   I | vi | ii | V | I | vi | ii | V

  L1 drums   kit=jazz-kit   esc=reverse_cymbal_sweep
          ▶ ride       X··X X··· X··X X···
          ▶ kick       X··· ···· X··· ····
          ▶ snare      ···· X··· ···· X···
          ▶ hat_closed ···· X··· ···· X···
  L2 bass    prog 038 Synth Bass 1   pat=root_fifth_alt
  L3 comp    prog 024 Nylon Guitar   pat=montuno_2_3    role=piano_arp
  L4 lead    prog 071 Clarinet       motif=m44_pop_04
  L6 counter prog 005 Electric Piano 2   mode=parallel_3rd
  fx         Drive(6dB) → HiShelf(-3dB) → Chorus(0.4Hz) → Reverb(0.40)

  rendered   notes 193    peak-poly 9    midi 1.9 KB    wav 5.3 MB    dur 27.4s
```

## How it works

1. **Hash.** SHA-256 of the input bytes.
2. **Decode.** Walk a deterministic HKDF-SHA256 byte stream over 32 macro decisions: mood, tempo, key, mode, time-signature, form, energy curve, chord progression, voicing, drum kit / pattern, bass pattern, comp role, melody motif, contour, FX, mix… A lookup table is pre-filtered by all prior decisions, so every combination produces music-theory-correct output.
3. **MIDI.** Render 9 simultaneous layers — drums (ch10), bass, comp, lead, pad, counter-melody, drone, riser, ear-candy stabs.
4. **Audio.** `fluidsynth` synthesizes the MIDI through a General-MIDI SoundFont; `pedalboard` applies a per-mood FX chain (reverb / delay / chorus / saturation / EQ); `pyloudnorm` normalises to -16 LUFS.
5. **Play.** macOS `afplay`, Linux `paplay`/`aplay`, Windows PowerShell SoundPlayer.

15 moods (`M0` ambient → `M14` gameboy/chiptune), 16 forms, 16 energy curves, 16 grooves, 12 drum kits, 39 chord progressions, 10 voicing styles, 8 escalation algorithms, ~2200 GM samples — all selected deterministically from the hash.

The MIME type of the input file biases the mood selection, so `.json` and `.wav` and `.mkv` *tend* to sound recognizably different even before content kicks in. (Override with `--mime off` for pure content-driven output.)

## Setup notes

- `pip install soundhash` pulls every Python dep (`mido`, `numpy`, `python-magic`, `pyloudnorm`, `pedalboard`, `soundfile`).
- Optional extras: `pip install soundhash[quality]` for `mosqito` psychoacoustic scoring; `pip install soundhash[dev]` for the test suite + `build`/`twine`.
- The `fluidsynth` system binary is required for audio render. macOS: `brew install fluid-synth`. Debian/Ubuntu: `apt install fluidsynth`. Windows: `scoop install fluidsynth`.
- The default GM SoundFont (`MS-Basic.sf3`, ~50 MB) is auto-downloaded on first `mhash` run into `assets/v1/sf2/`. To skip the per-render OGG-decode tax, the installer also produces an uncompressed `MS-Basic.sf2` (~440 MB additional disk, ~12× faster renders). Override via `SOUNDHASH_SOUNDFONT=/path/to/your.sf2`.

## Dev

```bash
git clone https://github.com/tabledevil/soundhash
cd soundhash
pip install -e ".[dev]"
pytest -q                      # 23 fast tests
soundhash --self-test          # baseline MIDI SHA check
python -m build                # builds dist/*.whl + .tar.gz
```

See `DESIGN.md` for the full spec, `BYTES.md` for the byte-by-byte map of how each SHA-256 byte drives a musical decision, `AESTHETICS.md` for per-mood design intent, and `CHANGELOG.md` for the journey.

## License

MIT. © 2026 tabledevil.
