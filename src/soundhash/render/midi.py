"""SongSpec → standard MIDI file (Type 1, PPQ 480).

Dumb consumer. No theory decisions; just plays whatever the SongSpec says.
Looks up the picked drum pattern, motif, contour, and scale subset by ID
in the static tables — but never makes a creative choice.

Output is byte-stable: same SongSpec → same .mid bytes.
"""
from __future__ import annotations

import io

from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo

from .. import tables, theory
from ..spec import SongSpec


PPQ = 480

# Per-layer energy thresholds — below these the layer is silent in that bar.
# Bass is the harmonic floor and plays whenever the song plays.
_ENERGY_GATE = {"drums": 0.30, "comp": 0.20, "lead": 0.40, "bass": 0.0,
                "pad": 0.40, "counter": 0.65}
_PAD_ENERGY_CEILING = 0.85       # pad drops out at peak energy to keep mix open


def _bar_energy(spec, bar_index: int) -> float:
    if spec.bar_energies and bar_index < len(spec.bar_energies):
        return spec.bar_energies[bar_index]
    return 1.0


# Deterministic per-layer velocity-jitter stream (derived from spec.provenance.hash_hex
# via HKDF). Cached on first use. Stream is consumed in event-emit order; render
# is deterministic because event ordering is fixed (sorted by abs_tick).
_VEL_JITTER_CACHE: dict[tuple[str, str], "_VelJitter"] = {}


class _VelJitter:
    __slots__ = ("_stream", "_pos")

    def __init__(self, stream: bytes):
        self._stream = stream
        self._pos = 0

    def next_offset(self, range_pm: int = 5) -> int:
        if not self._stream:
            return 0
        b = self._stream[self._pos % len(self._stream)]
        self._pos += 1
        # Map byte 0..255 → -range..+range, signed.
        return int((b / 255.0) * (2 * range_pm + 1)) - range_pm


def _vel_jitter(spec, layer_name: str, range_pm: int = 5) -> int:
    key = (spec.provenance.hash_hex, layer_name)
    j = _VEL_JITTER_CACHE.get(key)
    if j is None:
        # Derive 256 bytes from HKDF for this layer's jitter stream.
        import hashlib as _h, hmac as _hm
        prk = _hm.new(b"soundhash-v1",
                      bytes.fromhex(spec.provenance.hash_hex),
                      _h.sha256).digest()
        info = f"soundhash/v1/expression/velocity/L{layer_name}".encode("ascii")
        out, t, c = b"", b"", 1
        while len(out) < 256:
            t = _hm.new(prk, t + info + bytes([c]), _h.sha256).digest()
            out += t
            c += 1
        j = _VelJitter(out[:256])
        _VEL_JITTER_CACHE[key] = j
    return j.next_offset(range_pm)


_GROOVE_CACHE: dict[str, dict] = {}


def _groove_template(spec) -> dict:
    """Return the picked groove template, cached. Empty dict means 'no offsets'."""
    gid = getattr(spec, "groove_template_id", "straight_4_4")
    if gid in _GROOVE_CACHE:
        return _GROOVE_CACHE[gid]
    try:
        templates = tables.load("groove_templates")["templates"]
        tpl = next((t for t in templates if t["id"] == gid), {})
    except FileNotFoundError:
        tpl = {}
    _GROOVE_CACHE[gid] = tpl
    return tpl


def _groove_offset(spec, role: str, step: int) -> int:
    """Return PPQ-480 tick offset for role at grid step. 0 if no template / null."""
    offsets = (_groove_template(spec).get("offsets") or {}).get(role)
    if not offsets:
        return 0
    return int(offsets[step % len(offsets)])


def render_midi(spec: SongSpec) -> bytes:
    # Reset stateful caches so render is idempotent within a process.
    _VEL_JITTER_CACHE.clear()
    mf = MidiFile(ticks_per_beat=PPQ, type=1)

    num, den_pow2 = spec.time_sig
    beats_per_bar = num
    ticks_per_bar = PPQ * beats_per_bar
    _BEATS_PER_BAR = beats_per_bar  # captured by helpers below

    # ---- meta ------------------------------------------------------------
    meta = MidiTrack()
    meta.append(MetaMessage("track_name", name="meta", time=0))
    meta.append(MetaMessage("set_tempo", tempo=bpm2tempo(spec.tempo_bpm), time=0))
    meta.append(MetaMessage("time_signature", numerator=num,
                            denominator=den_pow2, time=0))
    meta.append(MetaMessage("marker",
                            text=f"soundhash/v1 {spec.provenance.hash_hex[:16]} "
                                 f"{spec.provenance.mood} {spec.mode}",
                            time=0))
    mf.tracks.append(meta)

    mf.tracks.append(_bass_track(spec, ticks_per_bar))
    mf.tracks.append(_comp_track(spec, ticks_per_bar))
    drum = _drum_track(spec, ticks_per_bar)
    if drum is not None:
        mf.tracks.append(drum)
    lead = _lead_track(spec, ticks_per_bar)
    if lead is not None:
        mf.tracks.append(lead)
    pad = _pad_track(spec, ticks_per_bar)
    if pad is not None:
        mf.tracks.append(pad)
    counter = _counter_track(spec, ticks_per_bar)
    if counter is not None:
        mf.tracks.append(counter)
    drone = _drone_track(spec, ticks_per_bar)
    if drone is not None:
        mf.tracks.append(drone)
    riser = _riser_track(spec, ticks_per_bar)
    if riser is not None:
        mf.tracks.append(riser)

    buf = io.BytesIO()
    mf.save(file=buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Per-track builders
# ---------------------------------------------------------------------------


def _bass_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack:
    bass = MidiTrack()
    bass.append(MetaMessage("track_name", name="bass", time=0))
    bass.append(Message("program_change", channel=0,
                        program=_layer_program(spec, "bass", default=33), time=0))
    # Initial portamento defaults: off, mid time. We turn it on/off per-bar
    # below when bass_octave_shift fires.
    bass.append(Message("control_change", channel=0, control=5, value=64, time=0))   # CC5 portamento time
    bass.append(Message("control_change", channel=0, control=65, value=0, time=0))   # CC65 portamento off

    layer = next((l for l in spec.layers if l.name == "bass"), None)
    pattern = _find_bass_pattern(layer.pattern_id) if layer else None
    oct_window = (layer.extra.get("octave_window") if layer else None) or (24, 60)

    if pattern is None:
        # Fallback: root pulse on each beat.
        return _bass_track_root_pulse(spec, ticks_per_bar, bass)

    grid_cells = pattern.get("grid_cells", 16)
    grid = pattern.get("grid", [])
    cells_to_ticks = ticks_per_bar // grid_cells

    events: list[tuple[int, int, int, int]] = []
    cc_events: list[tuple[int, int, int]] = []   # (abs_tick, cc, value)
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _ENERGY_GATE["bass"]:
            continue
        vel_base = max(50, min(110, int(60 + 50 * e)))
        # Find next bar's root for chromatic-approach handling.
        next_root_midi = (spec.bars[bar.index + 1].chord_root_midi
                          if bar.index + 1 < len(spec.bars) else bar.chord_root_midi)
        # Portamento on for bars where bass_octave_shift is non-zero (synth
        # bass voices glide between octaves instead of cutting).
        if bar.bass_octave_shift != 0:
            cc_events.append((bar.index * ticks_per_bar, 65, 127))   # on
            cc_events.append(((bar.index + 1) * ticks_per_bar - 5, 65, 0))  # off at end

        cursor_cell = 0
        last_idx = len(grid) - 1
        for ci, cell in enumerate(grid):
            deg = cell.get("deg", "R")
            length = cell.get("len", 1)
            art = cell.get("art", "tenuto")
            ghost = cell.get("ghost", False)

            # Per-bar mutation: skip the last cell (breath / fill).
            if bar.bass_skip_last and ci == last_idx:
                cursor_cell += length
                continue

            if deg in (".", "~"):
                cursor_cell += length
                continue

            pitch = _bass_degree_to_midi(deg, bar, next_root_midi)
            if pitch is None:
                cursor_cell += length
                continue

            # Per-bar octave shift, clamped to the picked synth's window.
            pitch = pitch + bar.bass_octave_shift
            lo, hi = oct_window
            while pitch < lo:
                pitch += 12
            while pitch > hi:
                pitch -= 12
            pitch = max(lo, min(hi, pitch))

            on_tick = bar.index * ticks_per_bar + cursor_cell * cells_to_ticks
            on_tick = max(bar.index * ticks_per_bar,
                          on_tick + _groove_offset(spec, "bass", cursor_cell))
            length_ticks = length * cells_to_ticks
            if art == "staccato":
                dur_ticks = max(60, length_ticks // 3)
            elif art == "legato":
                dur_ticks = max(60, length_ticks - 8)
            elif art == "ghost":
                dur_ticks = max(60, length_ticks // 4)
            else:                     # tenuto / slide / others
                dur_ticks = max(60, length_ticks - 20)

            vel = vel_base
            if ghost or art == "ghost" or (bar.bass_ghost_first and ci == 0):
                vel = max(20, vel_base - 40)
            vel = max(1, min(127, vel + _vel_jitter(spec, "bass", 4)))
            events.append((on_tick, 0, pitch, vel))
            events.append((on_tick + dur_ticks, 1, pitch, 64))
            cursor_cell += length

    merged = list(events) + [(t, 2, cc, val) for t, cc, val in cc_events]
    merged.sort(key=lambda ev: (ev[0], ev[1], ev[2]))
    cursor = 0
    for abs_tick, kind, *rest in merged:
        delta = max(0, abs_tick - cursor)
        if kind == 2:
            cc, val = rest
            bass.append(Message("control_change", channel=0,
                                control=cc, value=val, time=delta))
        else:
            pitch, vel = rest
            msg_type = "note_on" if kind == 0 else "note_off"
            bass.append(Message(msg_type, channel=0, note=pitch, velocity=vel, time=delta))
        cursor = abs_tick
    return bass


def _bass_track_root_pulse(spec: SongSpec, ticks_per_bar: int, track: MidiTrack) -> MidiTrack:
    layer = next((l for l in spec.layers if l.name == "bass"), None)
    oct_window = (layer.extra.get("octave_window") if layer else None) or (24, 60)
    cursor = 0
    beats_per_bar = ticks_per_bar // PPQ
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _ENERGY_GATE["bass"]:
            continue
        vel = max(50, min(110, int(60 + 50 * e)))
        root = bar.chord_root_midi
        lo, hi = oct_window
        while root < lo:
            root += 12
        while root > hi:
            root -= 12
        for beat in range(beats_per_bar):
            on_tick = bar.index * ticks_per_bar + beat * PPQ
            track.append(Message("note_on", channel=0, note=root,
                                 velocity=vel, time=on_tick - cursor))
            track.append(Message("note_off", channel=0, note=root,
                                 velocity=64, time=PPQ - 10))
            cursor = on_tick + PPQ - 10
    return track


def _find_bass_pattern(pattern_id: str) -> dict | None:
    if not pattern_id:
        return None
    try:
        pats = tables.load("bass/bass_patterns")["patterns"]
    except FileNotFoundError:
        return None
    return next((p for p in pats if p.get("id") == pattern_id), None)


# Degree language from `assets/v1/bass/bass_patterns.json` legend.
_BASS_DEG_OFFSETS = {
    "R": 0, "b3": 3, "3": 4, "b5": 6, "5": 7, "6": 9, "b6": 8,
    "b7": 10, "7": 11, "8": 12, "9": 14,
}


def _bass_degree_to_midi(deg: str, bar, next_root_midi: int) -> int | None:
    """Resolve a bass degree symbol against the current chord."""
    if deg == "CH":
        # Chromatic approach: a half-step below the next chord root.
        return max(24, min(60, next_root_midi - 1))
    if deg in ("3", "b3"):
        # Use the chord's actual third (chord_pcs[1] for triads/sevenths).
        if len(bar.chord_pcs) >= 2:
            return bar.chord_root_midi + bar.chord_pcs[1]
    if deg in ("5", "b5"):
        if len(bar.chord_pcs) >= 3:
            return bar.chord_root_midi + bar.chord_pcs[2]
    off = _BASS_DEG_OFFSETS.get(deg)
    if off is None:
        return None
    return bar.chord_root_midi + off


def _comp_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack:
    comp = MidiTrack()
    comp.append(MetaMessage("track_name", name="comp", time=0))
    comp.append(Message("program_change", channel=1,
                        program=_layer_program(spec, "comp", default=4), time=0))

    layer = next((l for l in spec.layers if l.name == "comp"), None)
    role = _find_comp_role(layer.extra.get("role")) if layer else None

    polyphony = (role or {}).get("polyphony_mode", "full_voicing")
    if polyphony == "silent":
        return comp                          # no_comp role → just program-change track

    default_pattern = _find_comp_pattern(layer.pattern_id) if layer else None
    if default_pattern is None and not spec.section_comp_pattern_ids:
        return _comp_track_sustain(spec, ticks_per_bar, comp)

    events: list[tuple[int, int, int, int]] = []
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _ENERGY_GATE["comp"]:
            continue
        # Per-section comp pattern, falling back to the macro pick.
        pat_id = spec.section_comp_pattern_ids.get(bar.section_letter, layer.pattern_id if layer else "")
        pattern = _find_comp_pattern(pat_id) or default_pattern
        if pattern is None:
            continue
        grid_steps = pattern.get("grid_steps", 16)
        cells_to_ticks = ticks_per_bar // grid_steps
        hits = pattern.get("hits", [])
        vel_base = max(45, min(95, int(45 + 50 * e)))
        voice_base = bar.chord_root_midi + 24
        full_pitches = sorted({voice_base + iv for iv in bar.chord_pcs})
        # Role-aware voicing.
        if polyphony == "monophonic_sequence":
            shape = _find_arp_shape((layer.extra or {}).get("arp_shape_id", ""))
            seq = (shape or {}).get("sequence", [0, 1, 2, 3])
            oct_off = (shape or {}).get("octave_offsets", [0] * len(seq))
            voice_pitches_per_hit = []
            for hi in range(len(hits)):
                step_idx = hi % len(seq)
                deg_idx = seq[step_idx]
                octs = oct_off[step_idx] if step_idx < len(oct_off) else 0
                if 0 <= deg_idx < len(full_pitches):
                    p = full_pitches[deg_idx] + 12 * octs
                else:
                    p = full_pitches[deg_idx % len(full_pitches)] + 12 * octs
                voice_pitches_per_hit.append([max(36, min(96, p))])
        elif polyphony == "partial_voicing":
            # Drop the 5th if a 7 is present; otherwise root + third.
            if len(full_pitches) >= 4:
                voice_pitches_per_hit = [[full_pitches[0], full_pitches[1], full_pitches[3]]] * len(hits)
            else:
                voice_pitches_per_hit = [full_pitches[:2]] * len(hits)
        else:
            voice_pitches_per_hit = [full_pitches] * len(hits)

        last_hit_idx = len(hits) - 1
        for hit_idx, hit in enumerate(hits):
            if bar.comp_drop_last and hit_idx == last_hit_idx:
                continue
            step = hit.get("step", 0)
            dur_steps = hit.get("duration_steps", 1)
            vel_factor = hit.get("vel_factor", 1.0)
            on_tick = bar.index * ticks_per_bar + step * cells_to_ticks
            on_tick = max(bar.index * ticks_per_bar,
                          on_tick + _groove_offset(spec, "comp", step))
            dur_ticks = max(40, dur_steps * cells_to_ticks - 10)
            vel = max(20, min(120, int(vel_base * vel_factor) + bar.comp_vel_pull))
            vel = max(1, min(127, vel + _vel_jitter(spec, "comp", 4)))
            pitches = voice_pitches_per_hit[hit_idx]
            for p in pitches:
                events.append((on_tick, 0, p, vel))
                events.append((on_tick + dur_ticks, 1, p, 64))

    events.sort(key=lambda ev: (ev[0], ev[1], ev[2]))
    cursor = 0
    for abs_tick, kind, pitch, vel in events:
        delta = max(0, abs_tick - cursor)
        msg_type = "note_on" if kind == 0 else "note_off"
        comp.append(Message(msg_type, channel=1, note=pitch, velocity=vel, time=delta))
        cursor = abs_tick
    return comp


def _comp_track_sustain(spec: SongSpec, ticks_per_bar: int, comp: MidiTrack) -> MidiTrack:
    cursor = 0
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _ENERGY_GATE["comp"]:
            continue
        vel = max(45, min(95, int(45 + 50 * e)))
        voice_base = bar.chord_root_midi + 24
        pitches = sorted({voice_base + iv for iv in bar.chord_pcs})
        on_tick = bar.index * ticks_per_bar
        for i, p in enumerate(pitches):
            delta = (on_tick - cursor) if i == 0 else 0
            comp.append(Message("note_on", channel=1, note=p, velocity=vel, time=delta))
            cursor = on_tick if i == 0 else cursor
        off_tick = on_tick + ticks_per_bar - 20
        for i, p in enumerate(pitches):
            delta = (off_tick - cursor) if i == 0 else 0
            comp.append(Message("note_off", channel=1, note=p, velocity=64, time=delta))
            cursor = off_tick if i == 0 else cursor
    return comp


def _counter_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack | None:
    """Parallel-3rd harmony of the lead motif, only on high-energy bars."""
    layer = next((l for l in spec.layers if l.name == "counter"), None)
    if layer is None:
        return None
    motif_id = layer.extra.get("motif_id")
    contour_id = layer.extra.get("contour_id")
    subset_id = layer.extra.get("scale_subset_id")
    if not (motif_id and contour_id and subset_id):
        return None
    transpose = int(layer.extra.get("transpose_degrees", 2))

    ts_str = f"{spec.time_sig[0]}/{spec.time_sig[1]}"
    contours_list = tables.load("melody/contours")["contours"]
    subsets = tables.load("melody/scale_subsets").get("subsets")
    subset = next((s for s in subsets if s["id"] == subset_id), None) if subsets else None
    default_motif = _find_motif(motif_id, ts_str)
    default_contour = next((c for c in contours_list if c["id"] == contour_id), None)
    if not (default_motif and default_contour and subset):
        return None

    track = MidiTrack()
    track.append(MetaMessage("track_name", name="counter", time=0))
    track.append(Message("program_change", channel=4,
                         program=_layer_program(spec, "counter", default=73), time=0))

    mask = subset.get("mask", 127)
    allowed_degs = [d for d in range(7) if mask & (1 << d)] or list(range(7))
    base_octave_midi = 72                       # C5

    events: list[tuple[int, int, int, int]] = []
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _ENERGY_GATE["counter"]:
            continue
        # Drop on fill bars too, so the fill speaks.
        next_bar = spec.bars[bar.index + 1] if bar.index + 1 < len(spec.bars) else None
        if next_bar is not None and next_bar.section_letter != bar.section_letter:
            continue
        motif_id_b = spec.section_motif_ids.get(bar.section_letter, motif_id)
        contour_id_b = spec.section_contour_ids.get(bar.section_letter, contour_id)
        motif = _find_motif(motif_id_b, ts_str) or default_motif
        contour = next((c for c in contours_list if c["id"] == contour_id_b),
                       default_contour)
        samples = contour["samples"]
        onsets = motif["onsets"]
        bar_tick = bar.index * ticks_per_bar
        n_onsets = len(onsets)
        for i, (start_beat, dur_beat) in enumerate(onsets):
            t = i / max(1, n_onsets - 1) if n_onsets > 1 else 0.0
            sample_idx = min(len(samples) - 1, int(round(t * (len(samples) - 1))))
            scale_degree_1 = samples[sample_idx]
            # Apply per-bar lead mutation, then add the harmony transpose.
            scale_degree_1 = max(1, scale_degree_1 + bar.melody_transpose + transpose)
            deg_idx = (scale_degree_1 - 1) % 7
            octave_shift = (scale_degree_1 - 1) // 7
            if deg_idx not in allowed_degs:
                deg_idx = min(allowed_degs, key=lambda d: abs(d - deg_idx))
            interval = theory.MODES[spec.mode][deg_idx]
            pitch = base_octave_midi + spec.key_root + interval + 12 * octave_shift
            pitch = max(48, min(96, pitch))

            on_tick = bar_tick + int(round(start_beat * PPQ))
            dur_ticks = max(60, int(round(dur_beat * PPQ)) - 20)
            vel = max(40, min(95, int(50 + 40 * e) - 15))    # always behind the lead
            vel = max(1, min(127, vel + _vel_jitter(spec, "counter", 4)))
            events.append((on_tick, 0, pitch, vel))
            events.append((on_tick + dur_ticks, 1, pitch, 64))

    if not events:
        return None
    events.sort(key=lambda ev: (ev[0], ev[1], ev[2]))
    cursor = 0
    for abs_tick, kind, pitch, vel in events:
        delta = max(0, abs_tick - cursor)
        msg_type = "note_on" if kind == 0 else "note_off"
        track.append(Message(msg_type, channel=4, note=pitch, velocity=vel, time=delta))
        cursor = abs_tick
    return track


def _riser_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack | None:
    """One-bar reverse-cymbal sweep before any large energy jump.

    Triggered on bar i when bar_energies[i+1] - bar_energies[i] >= 0.25.
    Uses GM program 119 (Reverse Cymbal); pitch 60 is irrelevant — the
    sample is the timbre. CC11 ramp lets the swell crescendo in.
    """
    layer = next((l for l in spec.layers if l.name == "riser"), None)
    if layer is None or len(spec.bar_energies) < 2:
        return None

    # Trigger threshold: delta ≥ 0.22. We picked 0.22 over 0.25 after observing
    # that build-ups in late_drop / slow_build_cliff curves often peak at
    # ~0.225 — the riser was inaudible because every late-drop track skipped
    # exactly when the build hits.
    rises: list[int] = []
    for i in range(len(spec.bar_energies) - 1):
        if spec.bar_energies[i + 1] - spec.bar_energies[i] >= 0.22:
            rises.append(i)
    if not rises:
        return None

    track = MidiTrack()
    track.append(MetaMessage("track_name", name="riser", time=0))
    track.append(Message("program_change", channel=6,
                         program=_layer_program(spec, "riser", default=119), time=0))

    events: list[tuple[int, int, int, int]] = []   # (abs_tick, kind, *rest)
    PITCH = 60
    for bar_idx in rises:
        bar_tick = bar_idx * ticks_per_bar
        # CC11 swell across the bar: 20 → 127 in 8 steps.
        for k in range(8):
            t_in_bar = int(round((k / 8) * ticks_per_bar))
            val = max(1, min(127, int(20 + 107 * k / 7)))
            events.append((bar_tick + t_in_bar, 2, 11, val))
        # One held note across the bar.
        events.append((bar_tick, 0, PITCH, 80))
        events.append((bar_tick + ticks_per_bar - 40, 1, PITCH, 64))
        # Reset CC11 to a neutral value just after note-off so subsequent rises
        # start from a known baseline.
        events.append((bar_tick + ticks_per_bar - 20, 2, 11, 100))

    events.sort(key=lambda e: (e[0], e[1], e[2]))
    cursor = 0
    for abs_tick, kind, *rest in events:
        delta = max(0, abs_tick - cursor)
        if kind == 2:
            cc, val = rest
            track.append(Message("control_change", channel=6,
                                 control=cc, value=val, time=delta))
        else:
            pitch, vel = rest
            msg_type = "note_on" if kind == 0 else "note_off"
            track.append(Message(msg_type, channel=6, note=pitch, velocity=vel, time=delta))
        cursor = abs_tick
    return track


def _drone_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack | None:
    """Sustained tonic+fifth pedal on the song key; only M0/M1/M10 by default."""
    layer = next((l for l in spec.layers if l.name == "drone"), None)
    if layer is None or not layer.extra.get("enabled"):
        return None
    track = MidiTrack()
    track.append(MetaMessage("track_name", name="drone", time=0))
    track.append(Message("program_change", channel=5,
                         program=_layer_program(spec, "drone", default=89), time=0))
    # One held tonic + fifth across the whole song. Two-octave register
    # below the comp so the drone doesn't muddy the bass.
    tonic = 36 + spec.key_root           # C2..B2 region
    fifth = tonic + 7
    if not spec.bars:
        return None
    on_tick = 0
    off_tick = len(spec.bars) * ticks_per_bar - 60
    if off_tick <= on_tick:
        return None
    vel = 48
    track.append(Message("note_on", channel=5, note=tonic, velocity=vel, time=0))
    track.append(Message("note_on", channel=5, note=fifth, velocity=vel, time=0))
    track.append(Message("note_off", channel=5, note=tonic, velocity=64, time=off_tick))
    track.append(Message("note_off", channel=5, note=fifth, velocity=64, time=0))
    return track


def _pad_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack | None:
    layer = next((l for l in spec.layers if l.name == "pad"), None)
    if layer is None:
        return None
    pad = MidiTrack()
    pad.append(MetaMessage("track_name", name="pad", time=0))
    pad.append(Message("program_change", channel=3,
                       program=_layer_program(spec, "pad", default=89), time=0))

    events: list[tuple[int, int, int, int]] = []
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        # Pad fills the mid-energy zone; drops out at peak so the lead/drums
        # are not crowded.
        if e < _ENERGY_GATE["pad"] or e > _PAD_ENERGY_CEILING:
            continue
        # Voice one octave above the comp (= chord_root_midi + 36) and only
        # use the bottom 3 chord tones — pads sit better when they are dense
        # but quiet rather than wide and prominent.
        voice_base = bar.chord_root_midi + 36
        chord_pcs = bar.chord_pcs[:3] if bar.chord_pcs else (0, 4, 7)
        pitches = sorted({voice_base + iv for iv in chord_pcs})
        pitches = [p for p in pitches if 48 <= p <= 96]
        if not pitches:
            continue
        on_tick = bar.index * ticks_per_bar
        off_tick = on_tick + ticks_per_bar - 80     # leave a small gap to breathe
        # Velocity below comp's, so it sits behind in the mix.
        vel_base = max(30, min(70, int(40 + 25 * (e - 0.4))))
        for p in pitches:
            v = max(1, min(120, vel_base + _vel_jitter(spec, "pad", 3)))
            events.append((on_tick, 0, p, v))
            events.append((off_tick, 1, p, 64))

    events.sort(key=lambda ev: (ev[0], ev[1], ev[2]))
    cursor = 0
    for abs_tick, kind, pitch, vel in events:
        delta = max(0, abs_tick - cursor)
        msg_type = "note_on" if kind == 0 else "note_off"
        pad.append(Message(msg_type, channel=3, note=pitch, velocity=vel, time=delta))
        cursor = abs_tick
    return pad


def _find_comp_role(role_id: str | None) -> dict | None:
    if not role_id:
        return None
    try:
        roles = tables.load("comp/comp_roles")["roles"]
    except FileNotFoundError:
        return None
    return next((r for r in roles if r.get("id") == role_id), None)


def _find_arp_shape(shape_id: str) -> dict | None:
    if not shape_id:
        return None
    try:
        data = tables.load("comp/arp_shapes")
    except FileNotFoundError:
        return None
    shapes = data.get("shapes", data.get("arp_shapes", data))
    if isinstance(shapes, dict):
        shapes = list(shapes.values())
    return next((s for s in shapes if s.get("id") == shape_id), None)


def _find_comp_pattern(pattern_id: str) -> dict | None:
    if not pattern_id:
        return None
    try:
        pats = tables.load("comp/chord_rhythm_patterns")["patterns"]
    except FileNotFoundError:
        return None
    return next((p for p in pats if p.get("id") == pattern_id), None)


def _drum_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack | None:
    layer = next((l for l in spec.layers if l.name == "drums"), None)
    if layer is None or "kit" not in layer.extra:
        return None
    try:
        kit = next(k for k in tables.load("drums/drumkits")["kits"]
                   if k["id"] == layer.extra["kit"])
        all_pats = tables.load(f"drums/patterns/{kit['id']}")["patterns"]
    except (FileNotFoundError, StopIteration):
        return None

    pat_by_id = {p["id"]: p for p in all_pats}
    pat_low_id = layer.extra.get("pattern_low") or layer.pattern_id
    pat_high_id = layer.extra.get("pattern_high") or layer.pattern_id
    pat_low = pat_by_id.get(pat_low_id) or pat_by_id.get(layer.pattern_id)
    pat_high = pat_by_id.get(pat_high_id) or pat_low
    if pat_low is None:
        return None

    # Fill (used at section transitions).
    fill = None
    fill_id = layer.extra.get("fill_id")
    if fill_id:
        try:
            fills = tables.load(f"drums/fills/{kit['id']}")["fills"]
            fill = next((f for f in fills if f["id"] == fill_id), None)
        except FileNotFoundError:
            fill = None

    track = MidiTrack()
    track.append(MetaMessage("track_name", name="drums", time=0))

    gm_map = kit["gm_map"]
    DRUM_LEN = 80
    events: list[tuple[int, int, int, int]] = []  # (abs_tick, kind, pitch, vel)
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _ENERGY_GATE["drums"]:
            continue
        # Density-aware: high-density pattern when energy ≥ 0.55, else low.
        pat = pat_high if e >= 0.55 else pat_low
        steps = pat.get("steps", 16)
        bars_in_pat = pat.get("bars", 1)
        ticks_per_step = (ticks_per_bar * bars_in_pat) // steps
        vel_scale = max(0.4, min(1.1, 0.55 + 0.55 * e))
        bar_offset_ticks = bar.index * ticks_per_bar

        # Detect section transition: this is a fill bar if the next bar starts
        # a new section letter.
        next_bar = spec.bars[bar.index + 1] if bar.index + 1 < len(spec.bars) else None
        prev_bar = spec.bars[bar.index - 1] if bar.index > 0 else None
        is_fill_bar = (
            fill is not None and next_bar is not None
            and next_bar.section_letter != bar.section_letter
        )
        is_section_start = (prev_bar is not None
                            and prev_bar.section_letter != bar.section_letter)
        fill_span = fill.get("span_steps", 8) if is_fill_bar else 0
        fill_start_step = max(0, steps - fill_span) if is_fill_bar else steps

        # Crash cymbal on the downbeat of a new section.
        if is_section_start:
            crash_key = gm_map.get("crash") or gm_map.get("crash_1") or 49
            on_tick = bar_offset_ticks
            on_tick = max(bar_offset_ticks,
                          on_tick + _groove_offset(spec, "crash", 0))
            v = max(60, min(120, int(round(110 * vel_scale))))
            events.append((on_tick, 0, crash_key, v))
            events.append((on_tick + DRUM_LEN * 4, 1, crash_key, 64))

        # Regular pattern hits (skip the fill region if this bar carries a fill).
        for row_name, hits in pat.get("rows", {}).items():
            gm_key = gm_map.get(row_name)
            if gm_key is None:
                continue
            for ev in hits:
                step = ev["s"]
                if step >= steps or step >= fill_start_step:
                    continue
                abs_tick = bar_offset_ticks + step * ticks_per_step
                abs_tick = max(bar_offset_ticks,
                               abs_tick + _groove_offset(spec, row_name, step))
                v = max(1, min(127, int(round(ev["v"] * vel_scale)) + _vel_jitter(spec, "drums", 5)))
                events.append((abs_tick, 0, gm_key, v))
                events.append((abs_tick + DRUM_LEN, 1, gm_key, 64))

        # Overlay the fill in the last fill_span cells.
        if is_fill_bar:
            for row_name, hits in fill.get("rows", {}).items():
                gm_key = gm_map.get(row_name)
                if gm_key is None:
                    continue
                for ev in hits:
                    step_in_fill = ev["s"]
                    if step_in_fill >= fill_span:
                        continue
                    abs_step = fill_start_step + step_in_fill
                    abs_tick = bar_offset_ticks + abs_step * ticks_per_step
                    abs_tick = max(bar_offset_ticks,
                                   abs_tick + _groove_offset(spec, row_name, abs_step))
                    v = max(1, min(127, int(round(ev["v"] * vel_scale))))
                    events.append((abs_tick, 0, gm_key, v))
                    events.append((abs_tick + DRUM_LEN, 1, gm_key, 64))
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    cursor = 0
    for abs_tick, kind, pitch, vel in events:
        delta = max(0, abs_tick - cursor)
        msg_type = "note_on" if kind == 0 else "note_off"
        track.append(Message(msg_type, channel=9, note=pitch, velocity=vel, time=delta))
        cursor = abs_tick
    return track


def _lead_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack | None:
    beats_per_bar = ticks_per_bar // PPQ
    layer = next((l for l in spec.layers if l.name == "lead"), None)
    if layer is None:
        return None
    motif_id = layer.extra.get("motif_id")
    contour_id = layer.extra.get("contour_id")
    subset_id = layer.extra.get("scale_subset_id")
    if not (motif_id and contour_id and subset_id):
        return None

    ts_str = f"{spec.time_sig[0]}/{spec.time_sig[1]}"
    contours_list = tables.load("melody/contours")["contours"]
    subsets = tables.load("melody/scale_subsets").get("subsets")
    subset = next((s for s in subsets if s["id"] == subset_id), None) if subsets else None
    default_motif = _find_motif(motif_id, ts_str)
    default_contour = next((c for c in contours_list if c["id"] == contour_id), None)
    if not (default_motif and default_contour and subset):
        return None

    track = MidiTrack()
    track.append(MetaMessage("track_name", name="lead", time=0))
    track.append(Message("program_change", channel=2,
                         program=_layer_program(spec, "lead", default=80), time=0))
    # CC11 expression curve: slow swell across the song to keep sustained
    # notes from sounding static. Cosine envelope, sampled per bar.
    cc_events: list[tuple[int, int, int]] = []  # (abs_tick, cc, value)
    n_bars = len(spec.bars)
    if n_bars:
        for i in range(n_bars):
            # Per-bar swell: 95 at bar start, 122 at midpoint, 105 at end.
            for frac, val in ((0.0, 95), (0.5, 122), (1.0, 105)):
                t_in_bar = int(round(frac * ticks_per_bar))
                cc_events.append((i * ticks_per_bar + t_in_bar, 11, val))

    mask = subset.get("mask", 127)
    allowed_degs = [d for d in range(7) if mask & (1 << d)] or list(range(7))
    base_octave_midi = 72                       # C5

    # Build (abs_tick, kind, pitch, vel) events; deltas computed at the end.
    # Pitch-bend events are stored separately and merged at the end.
    events = []
    bend_events: list[tuple[int, int]] = []
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _ENERGY_GATE["lead"]:
            continue
        # Lead drops out on fill bars (next section is different) so the drum
        # fill speaks. Standard production convention.
        next_bar = spec.bars[bar.index + 1] if bar.index + 1 < len(spec.bars) else None
        if next_bar is not None and next_bar.section_letter != bar.section_letter:
            continue
        # Phrase end: this bar is the last lead-active bar before either the
        # song ends OR the lead drops for a fill. We apply a downward bend
        # ("fall") to its last note.
        is_phrase_end = (
            next_bar is None
            or (next_bar.index + 1 < len(spec.bars)
                and spec.bars[next_bar.index + 1].section_letter != next_bar.section_letter)
        )
        # Per-section motif/contour — falls back to the macro pick for unknown letters.
        motif_id_b = spec.section_motif_ids.get(bar.section_letter, motif_id)
        contour_id_b = spec.section_contour_ids.get(bar.section_letter, contour_id)
        motif = _find_motif(motif_id_b, ts_str) or default_motif
        contour = next((c for c in contours_list if c["id"] == contour_id_b),
                       default_contour)
        samples = contour["samples"]
        onsets = motif["onsets"]
        samples_mean = sum(samples) / len(samples) if samples else 0.0
        bar_tick = bar.index * ticks_per_bar
        n_onsets = len(onsets)
        # Strong-beat snap targets: chord tones in the lead octave.
        chord_tones = sorted(
            base_octave_midi + ((spec.key_root + iv) % 12 + (bar.chord_root_pc + iv) // 12 * 0)
            for iv in ()  # placeholder; we recompute below for clarity
        )
        chord_tones = sorted({base_octave_midi + ((bar.chord_root_pc + iv) % 12) + 12 * 0
                              for iv in bar.chord_pcs})
        for i, (start_beat, dur_beat) in enumerate(onsets):
            t = i / max(1, n_onsets - 1) if n_onsets > 1 else 0.0
            sample_idx = min(len(samples) - 1, int(round(t * (len(samples) - 1))))
            scale_degree_1 = samples[sample_idx]
            # Per-bar mutation: invert (mirror about mean) then transpose.
            if bar.melody_invert and samples_mean:
                scale_degree_1 = int(round(2 * samples_mean - scale_degree_1))
            scale_degree_1 = max(1, scale_degree_1 + bar.melody_transpose)
            deg_idx = (scale_degree_1 - 1) % 7
            octave_shift = (scale_degree_1 - 1) // 7
            if deg_idx not in allowed_degs:
                deg_idx = min(allowed_degs, key=lambda d: abs(d - deg_idx))
            interval = theory.MODES[spec.mode][deg_idx]
            pitch = base_octave_midi + spec.key_root + interval + 12 * octave_shift
            pitch = max(48, min(96, pitch))

            # Strong-beat chord-tone snap: on beats 0 and 2 (in 4/4), pull the
            # picked pitch to the nearest chord tone of the current bar.
            beat_in_bar = start_beat % beats_per_bar
            is_strong = abs(beat_in_bar - 0.0) < 0.01 or abs(beat_in_bar - 2.0) < 0.01
            if is_strong and chord_tones:
                pitch = min(chord_tones, key=lambda c: abs(c - pitch))

            on_tick = bar_tick + int(round(start_beat * PPQ))
            dur_ticks = max(60, int(round(dur_beat * PPQ)) - 20)
            vel = max(50, min(115, int(60 + 60 * e)))
            # Section-start accent on the first lead onset of any bar that
            # begins a new section. Boost +15 velocity so the section change
            # is audible on the lead.
            prev_bar = spec.bars[bar.index - 1] if bar.index > 0 else None
            is_section_start = (prev_bar is not None
                                and prev_bar.section_letter != bar.section_letter)
            if is_section_start and i == 0:
                vel = min(127, vel + 15)
            events.append((on_tick, 0, pitch, vel))
            events.append((on_tick + dur_ticks, 1, pitch, 64))

            # Phrase-end bend: schedule a downward fall on the last onset.
            is_last_onset = (i == n_onsets - 1)
            if is_phrase_end and is_last_onset:
                bend_start = on_tick + max(20, dur_ticks // 2)
                bend_end = on_tick + dur_ticks - 5
                bend_events.append((bend_start, 0))           # neutral at start
                bend_events.append((bend_end, -8192))         # full -2 semitones
                bend_events.append((on_tick + dur_ticks + 20, 0))  # reset after note-off

    # Merge note + CC + pitch-bend events. Kind ordering at same tick:
    # 0 note_on, 1 note_off, 2 control_change, 3 pitchwheel.
    merged = (
        list(events)
        + [(t, 2, cc, val) for t, cc, val in cc_events]
        + [(t, 3, val, 0) for t, val in bend_events]
    )
    merged.sort(key=lambda e: (e[0], e[1], e[2]))
    cursor = 0
    for abs_tick, kind, *rest in merged:
        delta = max(0, abs_tick - cursor)
        if kind == 2:
            cc, val = rest
            track.append(Message("control_change", channel=2,
                                 control=cc, value=val, time=delta))
        elif kind == 3:
            bend_val, _ = rest
            track.append(Message("pitchwheel", channel=2, pitch=bend_val, time=delta))
        else:
            pitch, vel = rest
            msg_type = "note_on" if kind == 0 else "note_off"
            track.append(Message(msg_type, channel=2, note=pitch, velocity=vel, time=delta))
        cursor = abs_tick
    return track


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_motif(motif_id: str, time_sig: str) -> dict | None:
    pools = tables.load("melody/motif_rhythms")["pools"]
    for ts, pool in pools.items():
        items = pool if isinstance(pool, list) else [v for sub in pool.values()
                                                     for v in (sub if isinstance(sub, list) else [sub])]
        for m in items:
            if m.get("id") == motif_id:
                return m
    return None


def _layer_program(spec: SongSpec, name: str, default: int) -> int:
    for l in spec.layers:
        if l.name == name:
            return max(0, min(127, l.program))
    return default
