"""Terminal eye-candy: a styled SongSpec dashboard + a tiny progress bar."""
from __future__ import annotations

import os
import re
import sys
import time
from typing import IO, Iterable

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _vlen(s: str) -> int:
    """Visible (printable) length — strips ANSI SGR escapes."""
    return len(_ANSI_RE.sub("", s))

# ANSI palette — disabled when the stream is not a TTY or NO_COLOR is set.
_C = {
    "reset": "\x1b[0m",
    "dim":   "\x1b[2m",
    "bold":  "\x1b[1m",
    "cyan":  "\x1b[36m",
    "mag":   "\x1b[35m",
    "yel":   "\x1b[33m",
    "grn":   "\x1b[32m",
    "red":   "\x1b[31m",
    "blu":   "\x1b[34m",
    "gry":   "\x1b[90m",
}


def _coloriser(stream: IO):
    enabled = stream.isatty() and not os.environ.get("NO_COLOR")
    if not enabled:
        return lambda txt, *_: txt
    def c(txt: str, *codes: str) -> str:
        return "".join(_C[k] for k in codes) + txt + _C["reset"]
    return c


_PC_NAMES = "C C# D D# E F F# G G# A A# B".split()

# Mood → accent colour for the header chip.
_MOOD_TINT = {
    "M0": "cyan", "M1": "yel", "M2": "mag", "M3": "blu",
    "M4": "grn", "M5": "mag", "M6": "yel", "M7": "red",
    "M8": "red", "M9": "mag", "M10": "blu", "M11": "yel",
    "M12": "cyan", "M13": "grn", "M14": "grn",
}

# Diatonic scale-degree → roman numeral (major / minor variants).
_ROMAN_MAJOR = ["I", "ii", "iii", "IV", "V", "vi", "vii°"]
_ROMAN_MINOR = ["i", "ii°", "III", "iv", "v", "VI", "VII"]
_MAJOR_SCALE_PCS = (0, 2, 4, 5, 7, 9, 11)
_MINOR_SCALE_PCS = (0, 2, 3, 5, 7, 8, 10)


def _roman_for(chord_root_pc: int, chord_quality: str,
               key_root: int, mode: str) -> str:
    """Best-effort roman numeral relative to the key. Falls back to ?."""
    interval = (chord_root_pc - key_root) % 12
    is_minor_mode = mode in ("aeolian", "phrygian", "locrian", "jazz_minor")
    scale_pcs = _MINOR_SCALE_PCS if is_minor_mode else _MAJOR_SCALE_PCS
    romans = _ROMAN_MINOR if is_minor_mode else _ROMAN_MAJOR
    if interval in scale_pcs:
        deg = scale_pcs.index(interval)
        rn = romans[deg]
    else:
        # Chromatic — flat or sharp neighbour.
        for d, p in enumerate(scale_pcs):
            if (interval - p) % 12 == 1:
                rn = "♭" + romans[(d + 1) % 7]
                break
        else:
            rn = "?"
    # Quality overlay (uppercase = major, lowercase = minor).
    q = (chord_quality or "").lower()
    if q in ("maj", "maj7", ""):
        rn = rn.upper().replace("♭", "♭").replace("°", "")
    elif q in ("min", "m", "min7", "m7"):
        rn = rn.lower()
    elif q in ("dim", "dim7", "ø", "m7b5"):
        rn = rn.lower() + "°"
    elif q in ("dom7", "7"):
        rn = rn.upper() + "7"
    return rn

# Tiny GM-program label table for the rows we render most often.
_GM_LABELS = {
    0: "Acoustic Piano", 4: "Electric Piano 1", 5: "Electric Piano 2",
    11: "Vibraphone", 12: "Marimba", 16: "Drawbar Organ", 24: "Nylon Guitar",
    25: "Steel Guitar", 26: "Jazz Guitar", 32: "Acoustic Bass",
    33: "Fingered Bass", 34: "Picked Bass", 35: "Fretless Bass",
    36: "Slap Bass 1", 38: "Synth Bass 1", 39: "Synth Bass 2",
    41: "Viola", 43: "Cello", 44: "Tremolo Strings", 48: "String Ensemble 1",
    49: "String Ensemble 2", 50: "Synth Strings 1", 56: "Trumpet",
    60: "French Horn", 68: "Oboe", 71: "Clarinet", 73: "Flute",
    75: "Pan Flute", 78: "Whistle", 80: "Square Lead", 81: "Saw Lead",
    84: "Charang Lead", 87: "Bass+Lead", 88: "New-Age Pad",
    89: "Warm Pad", 90: "Polysynth Pad", 91: "Choir Pad", 94: "Halo Pad",
    95: "Sweep Pad", 98: "Crystal", 99: "Atmosphere", 100: "Brightness",
    102: "Echoes", 113: "Tinkle Bell", 119: "Reverse Cymbal",
}


def _gm(p: int) -> str:
    return _GM_LABELS.get(p, f"GM#{p}")


def _spark(values: Iterable[float]) -> str:
    bars = "▁▂▃▄▅▆▇█"
    out = []
    for v in values:
        v = max(0.0, min(1.0, float(v)))
        out.append(bars[int(v * (len(bars) - 1))])
    return "".join(out)


def _drum_pattern_grid(pattern_id: str, kit_id: str) -> list[str]:
    """One bar of the picked drum pattern as a list of `voice X·X···` lines."""
    if not pattern_id or not kit_id:
        return []
    try:
        from . import tables
        pats = tables.load(f"drums/patterns/{kit_id}").get("patterns", [])
    except Exception:
        return []
    pat = next((p for p in pats if p.get("id") == pattern_id), None)
    if not pat:
        return []
    steps = pat.get("steps", pat.get("grid_steps", 16))
    rows = pat.get("rows", {})
    out = []
    # Show up to 4 most-active voices so the grid stays compact.
    voices = sorted(rows.items(), key=lambda kv: -len(kv[1]))[:4]
    for name, cells in voices:
        marks = ["·"] * steps
        for hit in cells:
            s = hit.get("s", -1) if isinstance(hit, dict) else hit
            if 0 <= s < steps:
                marks[s] = "X"
        body = "".join(m if (i % 4) else (" " + m)
                       for i, m in enumerate(marks)).strip()
        out.append(f"{name:<11}{body}")
    return out


def _fx_summary(mood: str, wet_scale: float) -> str:
    try:
        from .render.fx import _MOOD_FX
    except Exception:
        return ""
    chain = _MOOD_FX.get(mood) or []
    parts = []
    for name, kw in chain:
        if name == "Reverb":
            parts.append(f"Reverb({kw.get('room_size', 0.5):.2f})")
        elif name == "Chorus":
            parts.append(f"Chorus({kw.get('rate_hz', 0.5):.1f}Hz)")
        elif name == "Delay":
            parts.append(f"Delay({kw.get('delay_seconds', 0.25):.0f}s)" if kw.get("delay_seconds", 0) >= 1 else f"Delay({int(kw.get('delay_seconds', 0)*1000)}ms)")
        elif name == "Phaser":
            parts.append("Phaser")
        elif name == "Compressor":
            parts.append(f"Comp({kw.get('ratio', 1):.0f}:1)")
        elif name == "Distortion":
            parts.append(f"Drive({kw.get('drive_db', 0):.0f}dB)")
        elif name == "LowShelfFilter":
            parts.append(f"LoShelf({kw.get('gain_db', 0):+.0f}dB)")
        elif name == "HighShelfFilter":
            parts.append(f"HiShelf({kw.get('gain_db', 0):+.0f}dB)")
        else:
            parts.append(name)
    chain_s = " → ".join(parts) if parts else "—"
    return f"{chain_s}    wet ×{wet_scale:.2f}"


def print_dashboard(spec, source_label: str, mime: str | None,
                    stream: IO = sys.stderr) -> None:
    c = _coloriser(stream)
    pr = lambda *a, **k: print(*a, **k, file=stream)

    key = _PC_NAMES[spec.key_root]
    ts = f"{spec.time_sig[0]}/{spec.time_sig[1]}"
    hash_short = f"{spec.provenance.hash_hex[:8]}…{spec.provenance.hash_hex[-4:]}"
    mood_tint = _MOOD_TINT.get(spec.provenance.mood, "yel")

    side = c("│", "cyan")
    rows = [
        f" hash    {c(hash_short, 'mag')}    "
        f"{c('source', 'gry')} {source_label}    "
        f"{c('mime', 'gry')} {mime or '—'}",
        f" mood    {c(spec.provenance.mood, mood_tint, 'bold')}"
        f" sub-flavor {spec.sub_flavor}    "
        f"{c('tempo', 'gry')} {c(f'{spec.tempo_bpm:.1f} BPM', 'grn')}    "
        f"{c('key', 'gry')} {c(key + ' ' + spec.mode, 'grn')}    "
        f"{c('meter', 'gry')} {c(ts, 'grn')}",
        f" form    {c(spec.form_id, 'grn')}    "
        f"{c('groove', 'gry')} {spec.groove_template_id}    "
        f"{c('voicing', 'gry')} {spec.voicing_style}    "
        f"{c('curve', 'gry')} {spec.energy_curve_id}",
        f" matrix  {spec.activation_matrix_id}    "
        f"{c('humanize', 'gry')} {spec.humanization_profile} "
        f"(jitter ±{spec.humanization_vel_jitter})    "
        f"{c('mix', 'gry')} {spec.mix_preset_id}",
    ]
    inner = max(_vlen(r) for r in rows) + 2          # 1 space pad each side
    inner = max(inner, len("─[ mhash ]") + 2)
    bar = "─" * inner

    def boxed(body: str) -> str:
        pad = max(0, inner - 2 - _vlen(body))
        return f"{side} {body}{' ' * pad} {side}"

    pr(c(f"╭─[ mhash ]{bar[14:]}╮", "cyan"))
    for r in rows:
        pr(boxed(r))
    pr(c(f"╰{bar}╯", "cyan"))

    # ─── form / energy / chord run ──────────────────────────────────
    bars_str = " · ".join(b.section_letter for b in spec.bars)
    pr(f"  {c('bars   ', 'gry')} {bars_str}")
    if spec.bar_energies:
        pr(f"  {c('energy ', 'gry')} {c(_spark(spec.bar_energies), 'mag')}")
    chord_line = " | ".join(b.chord for b in spec.bars)
    pr(f"  {c('chords ', 'gry')} {chord_line}")
    roman_line = " | ".join(_roman_for(b.chord_root_pc, b.chord_quality,
                                       spec.key_root, spec.mode)
                            for b in spec.bars)
    pr(f"  {c('roman  ', 'gry')} {c(roman_line, 'yel')}")
    pr("")

    # ─── per-section activation grid ────────────────────────────────
    if spec.activation_rows:
        layer_names = ("drums", "bass", "comp", "lead", "counter",
                       "drone", "riser", "ad_lib")
        sections = list(spec.activation_rows.keys())
        cell_glyph = {"-": "·", "s": "▪", "n": "▣", "d": "█", "*": "◆"}
        pr(f"  {c('arrangement (rows × sections):', 'gry')}")
        header = "         " + "  ".join(f"{s:>4}" for s in sections)
        pr(c(header, "gry"))
        for li, lname in enumerate(layer_names):
            cells = []
            for sec in sections:
                row = spec.activation_rows.get(sec, [])
                glyph = cell_glyph.get(row[li] if li < len(row) else "-", "·")
                col = "grn" if glyph in ("▣", "█") else \
                      "yel" if glyph in ("▪", "◆") else "gry"
                cells.append(c(f"{glyph:>4}", col))
            pr(f"   {lname:<8} " + "  ".join(cells))
        pr("")

    layers_by_name = {l.name: l for l in spec.layers}

    def row(prefix: str, layer_name: str, body: str):
        layer = layers_by_name.get(layer_name)
        if not layer:
            return
        pr(f"  {c(prefix, 'cyan', 'bold')} {c(layer_name.ljust(7), 'bold')}"
           f" ch{layer.midi_channel + 1:<2} {body}")

    drum_layer = layers_by_name.get("drums")
    if drum_layer:
        kit = drum_layer.extra.get("kit", "")
        pat_low = drum_layer.extra.get("pattern_low", "")
        pat_high = drum_layer.extra.get("pattern_high", "")
        fill = drum_layer.extra.get("fill_id", "")
        esc = drum_layer.extra.get("esc_algo", "")
        row("L1", "drums", f"kit={c(kit, 'yel')}  low={pat_low} / high={pat_high}  fill={fill}  esc={esc}")
        for line in _drum_pattern_grid(pat_low or pat_high, kit):
            pr(f"          {c('▶', 'mag')} {c(line, 'gry')}")

    bass = layers_by_name.get("bass")
    if bass:
        row("L2", "bass", f"prog {bass.program:03d} {c(_gm(bass.program), 'yel')}   "
                          f"pat={bass.pattern_id}   synth={bass.synth_id}")

    comp = layers_by_name.get("comp")
    if comp:
        role = comp.extra.get("role", "")
        arp = comp.extra.get("arp_shape_id", "")
        row("L3", "comp", f"prog {comp.program:03d} {c(_gm(comp.program), 'yel')}   "
                          f"pat={comp.pattern_id}   role={role}   arp={arp}")

    lead = layers_by_name.get("lead")
    if lead:
        row("L4", "lead", f"prog {lead.program:03d} {c(_gm(lead.program), 'yel')}   "
                          f"motif={lead.extra.get('motif_id', '')}   "
                          f"contour={lead.extra.get('contour_id', '')}   "
                          f"scale={lead.extra.get('scale_subset_id', '')}")

    pad = layers_by_name.get("pad")
    if pad:
        row("L5", "pad", f"prog {pad.program:03d} {c(_gm(pad.program), 'yel')}")

    counter = layers_by_name.get("counter")
    if counter:
        row("L6", "counter", f"prog {counter.program:03d} {c(_gm(counter.program), 'yel')}   "
                             f"mode={counter.extra.get('counter_mode', '')}")

    drone = layers_by_name.get("drone")
    if drone and drone.extra.get("enabled"):
        row("L7", "drone", f"prog {drone.program:03d} {c(_gm(drone.program), 'yel')}   tonic+5th pedal")

    pr("")
    pr(f"  {c('fx     ', 'gry')} {_fx_summary(spec.provenance.mood, spec.fx_wet_scale)}    "
       f"{c('audio', 'gry')} {spec.render.sample_rate}/{spec.render.bit_depth}-bit @ "
       f"{spec.render.target_lufs:.0f} LUFS")
    pr("")


# ─── progress bar ──────────────────────────────────────────────────────

def print_render_stats(spec, midi_bytes: bytes, wav_bytes: bytes | None,
                       elapsed_s: float, stream: IO = sys.stderr) -> None:
    """One-line footer summarising what the renderer produced."""
    c = _coloriser(stream)
    pr = lambda *a, **k: print(*a, **k, file=stream)
    n_notes, peak_poly = _midi_stats(midi_bytes)
    parts = [
        c("rendered", "grn", "bold"),
        f"{c('notes', 'gry')} {n_notes}",
        f"{c('peak-poly', 'gry')} {peak_poly}",
        f"{c('midi', 'gry')} {len(midi_bytes)/1024:.1f} KB",
    ]
    if wav_bytes:
        parts += [
            f"{c('wav', 'gry')} {len(wav_bytes)/1e6:.1f} MB",
            f"{c('dur', 'gry')} {spec.total_duration_seconds():.1f}s",
        ]
    parts.append(f"{c('took', 'gry')} {elapsed_s:.2f}s")
    pr("  " + "    ".join(parts))


def _midi_stats(midi_bytes: bytes) -> tuple[int, int]:
    """Return (total_note_on_count, peak_simultaneous_polyphony) for a MIDI blob."""
    try:
        import io
        import mido
        mf = mido.MidiFile(file=io.BytesIO(midi_bytes))
    except Exception:
        return (0, 0)
    n_notes = 0
    peak_poly = cur_poly = 0
    # Walk the merged event stream so polyphony reflects across-track concurrency.
    for msg in mf:
        if msg.type == "note_on" and msg.velocity > 0:
            n_notes += 1
            cur_poly += 1
            peak_poly = max(peak_poly, cur_poly)
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            cur_poly = max(0, cur_poly - 1)
    return n_notes, peak_poly


class Progress:
    """Phase-labelled progress bar that overwrites a single stderr line."""
    def __init__(self, phases: list[str], stream: IO = sys.stderr):
        self.phases = phases
        self.stream = stream
        self.tty = stream.isatty() and not os.environ.get("NO_COLOR")
        self.start = time.monotonic()
        self.phase_start = self.start
        self.idx = 0
        self.done_idx = 0

    def begin(self, name: str) -> None:
        if name in self.phases:
            self.idx = self.phases.index(name)
        self.phase_start = time.monotonic()
        self._draw(name)

    def end(self, name: str) -> None:
        if name in self.phases:
            self.done_idx = self.phases.index(name) + 1

    def _draw(self, name: str) -> None:
        if not self.tty:
            return
        width = 24
        filled = int(width * self.done_idx / max(1, len(self.phases)))
        bar = "▓" * filled + "░" * (width - filled)
        elapsed = time.monotonic() - self.start
        line = (f"\r  \x1b[36m[{bar}]\x1b[0m "
                f"{self.done_idx}/{len(self.phases)}  "
                f"\x1b[33m{name:<22}\x1b[0m  ⏱ {elapsed:4.1f}s")
        self.stream.write(line)
        self.stream.flush()

    def finish(self) -> None:
        if self.tty:
            self.stream.write("\r" + " " * 80 + "\r")
            self.stream.flush()
