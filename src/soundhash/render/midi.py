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
_ENERGY_GATE = {"drums": 0.30, "comp": 0.20, "lead": 0.40, "bass": 0.0}


def _bar_energy(spec, bar_index: int) -> float:
    if spec.bar_energies and bar_index < len(spec.bar_energies):
        return spec.bar_energies[bar_index]
    return 1.0


def render_midi(spec: SongSpec) -> bytes:
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

    layer = next((l for l in spec.layers if l.name == "bass"), None)
    pattern = _find_bass_pattern(layer.pattern_id) if layer else None

    if pattern is None:
        # Fallback: root pulse on each beat.
        return _bass_track_root_pulse(spec, ticks_per_bar, bass)

    grid_cells = pattern.get("grid_cells", 16)
    grid = pattern.get("grid", [])
    cells_to_ticks = ticks_per_bar // grid_cells

    events: list[tuple[int, int, int, int]] = []
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _ENERGY_GATE["bass"]:
            continue
        vel_base = max(50, min(110, int(60 + 50 * e)))
        # Find next bar's root for chromatic-approach handling.
        next_root_midi = (spec.bars[bar.index + 1].chord_root_midi
                          if bar.index + 1 < len(spec.bars) else bar.chord_root_midi)

        cursor_cell = 0
        for cell in grid:
            deg = cell.get("deg", "R")
            length = cell.get("len", 1)
            art = cell.get("art", "tenuto")
            ghost = cell.get("ghost", False)

            if deg in (".", "~"):
                cursor_cell += length
                continue

            pitch = _bass_degree_to_midi(deg, bar, next_root_midi)
            if pitch is None:
                cursor_cell += length
                continue

            on_tick = bar.index * ticks_per_bar + cursor_cell * cells_to_ticks
            # Articulation → fraction of the cell duration.
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
            if ghost or art == "ghost":
                vel = max(20, vel_base - 40)
            events.append((on_tick, 0, pitch, vel))
            events.append((on_tick + dur_ticks, 1, pitch, 64))
            cursor_cell += length

    events.sort(key=lambda ev: (ev[0], ev[1], ev[2]))
    cursor = 0
    for abs_tick, kind, pitch, vel in events:
        delta = max(0, abs_tick - cursor)
        msg_type = "note_on" if kind == 0 else "note_off"
        bass.append(Message(msg_type, channel=0, note=pitch, velocity=vel, time=delta))
        cursor = abs_tick
    return bass


def _bass_track_root_pulse(spec: SongSpec, ticks_per_bar: int, track: MidiTrack) -> MidiTrack:
    cursor = 0
    beats_per_bar = ticks_per_bar // PPQ
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _ENERGY_GATE["bass"]:
            continue
        vel = max(50, min(110, int(60 + 50 * e)))
        for beat in range(beats_per_bar):
            on_tick = bar.index * ticks_per_bar + beat * PPQ
            track.append(Message("note_on", channel=0, note=bar.chord_root_midi,
                                 velocity=vel, time=on_tick - cursor))
            track.append(Message("note_off", channel=0, note=bar.chord_root_midi,
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
    pattern = _find_comp_pattern(layer.pattern_id) if layer else None
    role = _find_comp_role(layer.extra.get("role")) if layer else None

    polyphony = (role or {}).get("polyphony_mode", "full_voicing")
    if polyphony == "silent":
        return comp                          # no_comp role → just program-change track
    if pattern is None:
        return _comp_track_sustain(spec, ticks_per_bar, comp)

    grid_steps = pattern.get("grid_steps", 16)
    cells_to_ticks = ticks_per_bar // grid_steps
    hits = pattern.get("hits", [])

    events: list[tuple[int, int, int, int]] = []
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _ENERGY_GATE["comp"]:
            continue
        vel_base = max(45, min(95, int(45 + 50 * e)))
        voice_base = bar.chord_root_midi + 24
        full_pitches = sorted({voice_base + iv for iv in bar.chord_pcs})
        # Role-aware voicing.
        if polyphony == "monophonic_sequence":
            voice_pitches_per_hit = [[full_pitches[i % len(full_pitches)]] for i in range(len(hits))]
        elif polyphony == "partial_voicing":
            # Drop the 5th if a 7 is present; otherwise root + third.
            if len(full_pitches) >= 4:
                voice_pitches_per_hit = [[full_pitches[0], full_pitches[1], full_pitches[3]]] * len(hits)
            else:
                voice_pitches_per_hit = [full_pitches[:2]] * len(hits)
        else:
            voice_pitches_per_hit = [full_pitches] * len(hits)

        for hit_idx, hit in enumerate(hits):
            step = hit.get("step", 0)
            dur_steps = hit.get("duration_steps", 1)
            vel_factor = hit.get("vel_factor", 1.0)
            on_tick = bar.index * ticks_per_bar + step * cells_to_ticks
            dur_ticks = max(40, dur_steps * cells_to_ticks - 10)
            vel = max(20, min(120, int(vel_base * vel_factor)))
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


def _find_comp_role(role_id: str | None) -> dict | None:
    if not role_id:
        return None
    try:
        roles = tables.load("comp/comp_roles")["roles"]
    except FileNotFoundError:
        return None
    return next((r for r in roles if r.get("id") == role_id), None)


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
        for row_name, hits in pat.get("rows", {}).items():
            gm_key = gm_map.get(row_name)
            if gm_key is None:
                continue
            for ev in hits:
                step = ev["s"]
                if step >= steps:
                    continue
                abs_tick = bar_offset_ticks + step * ticks_per_step
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

    motif = _find_motif(motif_id, f"{spec.time_sig[0]}/{spec.time_sig[1]}")
    contour = next((c for c in tables.load("melody/contours")["contours"]
                    if c["id"] == contour_id), None)
    subsets = tables.load("melody/scale_subsets").get("subsets")
    subset = next((s for s in subsets if s["id"] == subset_id), None) if subsets else None
    if not (motif and contour and subset):
        return None

    track = MidiTrack()
    track.append(MetaMessage("track_name", name="lead", time=0))
    track.append(Message("program_change", channel=2,
                         program=_layer_program(spec, "lead", default=80), time=0))

    mask = subset.get("mask", 127)
    allowed_degs = [d for d in range(7) if mask & (1 << d)] or list(range(7))
    samples = contour["samples"]
    onsets = motif["onsets"]
    base_octave_midi = 72                       # C5

    # Build (abs_tick, kind, pitch, vel) events; deltas computed at the end.
    events = []
    samples_mean = sum(samples) / len(samples) if samples else 0.0
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _ENERGY_GATE["lead"]:
            continue
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
            events.append((on_tick, 0, pitch, vel))
            events.append((on_tick + dur_ticks, 1, pitch, 64))

    events.sort(key=lambda e: (e[0], e[1], e[2]))
    cursor = 0
    for abs_tick, kind, pitch, vel in events:
        delta = max(0, abs_tick - cursor)
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
