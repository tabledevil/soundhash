# Render Pipeline (concrete CLI/API)

## Stage 1 — SongSpec → MIDI (mido)

```python
import mido
m = mido.MidiFile(type=1, ticks_per_beat=480)
meta = mido.MidiTrack(); m.tracks.append(meta)
meta.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(spec.bpm), time=0))
meta.append(mido.MetaMessage('time_signature', numerator=spec.ts_num, denominator=spec.ts_den, time=0))
for layer in ordered_layers(spec):  # fixed order: drums,bass,comp,lead,aux
    t = mido.MidiTrack(); m.tracks.append(t)
    t.append(mido.Message('program_change', channel=layer.ch, program=layer.program, time=0))
    for ev in sort_events(layer.events):  # fixed (tick, channel, type_priority) sort
        t.append(ev.to_mido(delta=...))
m.save("out.mid")
```

## Stage 2 — MIDI → per-layer WAV

For each layer, render through its chosen engine.

### FluidSynth (most layers)
```
LC_ALL=C fluidsynth -ni -q \
  -r 44100 -R 0 -C 0 -g 0.5 \
  -o synth.cpu-cores=1 \
  -o synth.interpolation=7 \
  -o synth.reverb.active=0 \
  -o synth.chorus.active=0 \
  -o synth.dynamic-sample-loading=0 \
  -o player.timing-source=sample \
  -T wav -F layer_<role>.wav \
  /sf2/GeneralUserGS.sf2 layer_<role>.mid
```

### sfizz (piano/strings where SFZ wins)
```
LC_ALL=C sfizz_render \
  --sfz /sfz/SalamanderGrandPianoV3.sfz \
  --midi layer_comp.mid \
  --wav  layer_comp.wav \
  -s 44100 -b 1024 --use-eot
```

### Surge XT (synth leads)
```
surge-xt-cli --headless --patch <pinned.fxp> \
  --midi layer_lead.mid --out layer_lead.wav --sr 44100
```
(exact flags TBD; v1.3+ exposes CLI; verify in v2)

### Python sample mixer (drums, optional)
Pure numpy mix from CC0 one-shots, deterministic FP order.

## Stage 3 — Mix and master (Python)

```python
import numpy as np, soundfile as sf, pyloudnorm as pyln
from pedalboard import Pedalboard, Reverb, Limiter

mix = np.zeros((N, 2), dtype=np.float32)
for layer in FIXED_ORDER:
    y, sr = sf.read(f"layer_{layer}.wav", dtype='float32', always_2d=True)
    assert sr == 44100
    mix[:len(y)] += y * 10**(spec.gain_db[layer]/20.0)

board = Pedalboard([
    Reverb(room_size=spec.reverb_room, damping=spec.reverb_damp, wet_level=spec.reverb_wet, dry_level=1-spec.reverb_wet, width=1.0),
    Limiter(threshold_db=-1.0, release_ms=100.0),
])
mix = board(mix, 44100)

meter = pyln.Meter(44100)  # BS.1770-4
loud = meter.integrated_loudness(mix)
mix = pyln.normalize.loudness(mix, loud, -16.0)

# fades
fade_in = np.linspace(0,1, int(0.05*44100))**2
fade_out = np.linspace(1,0, int(0.20*44100))**2
mix[:len(fade_in)] *= fade_in[:,None]
mix[-len(fade_out):] *= fade_out[:,None]

sf.write("soundhash.wav", mix, 44100, subtype='PCM_16')
```

Optional encoders: FLAC via `soundfile`, MP3 via `lame --strictly-enforce-ISO -b 192 --cbr -`.

## Caveat
True bit-identical output requires the pinned Docker image. Host-installed renders are best-effort and validated via golden-file diff.
