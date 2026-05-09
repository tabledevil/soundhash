"""Terminal eye-candy: a styled SongSpec dashboard + a tiny progress bar."""
from __future__ import annotations

import os
import sys
import time
from typing import IO, Iterable

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


def _drum_pattern_grid(pattern_id: str, kit_id: str, width: int = 32) -> str:
    """One bar of the picked drum pattern as X / · cells."""
    if not pattern_id or not kit_id:
        return ""
    try:
        from . import tables
        pats = tables.load(f"drums/patterns/{kit_id}").get("patterns", [])
    except Exception:
        return ""
    pat = next((p for p in pats if p.get("id") == pattern_id), None)
    if not pat:
        return ""
    grid = pat.get("grid_steps", 16)
    hits = pat.get("hits", [])
    cells = ["·"] * grid
    for h in hits:
        step = h.get("step", -1)
        if 0 <= step < grid:
            cells[step] = "X"
    # Render with light dividers every 4 cells, padded out to `width`.
    body = "".join(c if (i % 4) else (" " + c) for i, c in enumerate(cells)).strip()
    return f"{body}   ({grid}-step)"


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

    bar = "─" * 70
    pr(c(f"╭─[ soundhash ]{bar[14:]}╮", "cyan"))
    pr(f"{c('│', 'cyan')}  hash    {c(hash_short, 'mag')}")
    pr(f"{c('│', 'cyan')}  source  {source_label}")
    pr(f"{c('│', 'cyan')}  mime    {mime or '—'}")
    pr(f"{c('│', 'cyan')}  mood    {c(spec.provenance.mood, 'yel', 'bold')}    "
       f"sub-flavor {spec.sub_flavor}")
    pr(f"{c('│', 'cyan')}  tempo   {c(f'{spec.tempo_bpm:.1f} BPM', 'grn')}   "
       f"key {c(key + ' ' + spec.mode, 'grn')}   "
       f"meter {c(ts, 'grn')}   form {c(spec.form_id, 'grn')}")
    pr(f"{c('│', 'cyan')}  groove  {spec.groove_template_id}    "
       f"voicing {spec.voicing_style}    curve {spec.energy_curve_id}    "
       f"matrix {spec.activation_matrix_id}")
    pr(c(f"╰{bar}╯", "cyan"))

    bars = " · ".join(b.section_letter for b in spec.bars)
    pr(f"  {c('bars  ', 'gry')}  {bars}")
    if spec.bar_energies:
        pr(f"  {c('energy', 'gry')}  {c(_spark(spec.bar_energies), 'mag')}")
    chord_line = " | ".join(b.chord for b in spec.bars)
    pr(f"  {c('chords', 'gry')}  {chord_line}")
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
        grid = _drum_pattern_grid(pat_low or pat_high, kit)
        if grid:
            pr(f"          {c('▶', 'mag')} {c(grid, 'gry')}")

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
    pr(f"  {c('fx     ', 'gry')} {_fx_summary(spec.provenance.mood, spec.fx_wet_scale)}")
    pr(f"  {c('mix    ', 'gry')} {spec.mix_preset_id}    "
       f"humanize {spec.humanization_profile} (jitter ±{spec.humanization_vel_jitter})    "
       f"sr {spec.render.sample_rate}/{spec.render.bit_depth}-bit    "
       f"target {spec.render.target_lufs:.0f} LUFS")
    pr("")


# ─── progress bar ──────────────────────────────────────────────────────

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
