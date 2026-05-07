"""SongSpec — the fully-resolved, deterministic description of a soundhash.

Renderers consume this; they make no decisions of their own.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Note:
    layer: str
    start_tick: int
    duration_ticks: int
    pitch: int             # MIDI 0..127; for ch10 drums, the GM key
    velocity: int          # 1..127
    articulation: str = "tenuto"


@dataclass(frozen=True)
class CCEvent:
    layer: str
    tick: int
    cc: int                # 0..127
    value: int             # 0..127 (or 0..16383 if cc14bit_supported)


@dataclass(frozen=True)
class PitchBend:
    layer: str
    tick: int
    value: int             # -8192..+8191


@dataclass(frozen=True)
class Bar:
    index: int
    chord: str             # e.g. "Cmaj7", resolved (display label)
    chord_root_pc: int = 0          # 0..11 (C..B) of the chord root
    chord_root_midi: int = 36       # MIDI pitch of the bass-octave root
    chord_pcs: tuple[int, ...] = () # semitone offsets-from-root (chord-tone PC set)
    chord_quality: str = "maj"      # quality string from progression
    notes: tuple[Note, ...] = ()
    ccs: tuple[CCEvent, ...] = ()
    bends: tuple[PitchBend, ...] = ()


@dataclass(frozen=True)
class LayerSpec:
    name: str              # "drums", "bass", "comp", "lead", "counter", "drone", ...
    midi_channel: int
    synth_id: str          # references assets/v1/synth_pool.json
    program: int           # GM program or sfz preset index
    pattern_id: str = ""   # references the per-layer pattern table (drum/bass/comp)
    extra: dict = field(default_factory=dict)  # per-layer picks (motif_id, contour_id, ...)


@dataclass(frozen=True)
class RenderHints:
    sample_rate: int = 44100
    bit_depth: int = 16
    target_lufs: float = -16.0
    true_peak_dbtp: float = -1.5


@dataclass(frozen=True)
class Provenance:
    hash_hex: str
    mime_detected: Optional[str]
    mime_family: str
    mood: str
    libmagic_version: Optional[str]
    magic_mgc_sha: Optional[str]
    overrides: tuple[str, ...] = ()


@dataclass(frozen=True)
class SongSpec:
    version: str
    provenance: Provenance
    tempo_bpm: float
    time_sig: tuple[int, int]
    swing: str
    key_root: int          # 0..11 (C..B)
    mode: str
    form_id: str
    energy_curve_id: str
    activation_matrix_id: str
    bars: tuple[Bar, ...] = ()
    layers: tuple[LayerSpec, ...] = ()
    bar_energies: tuple[float, ...] = ()  # one 0..1 per bar from the energy curve
    render: RenderHints = field(default_factory=RenderHints)

    def total_duration_seconds(self) -> float:
        beats_per_bar = self.time_sig[0]
        return len(self.bars) * beats_per_bar * 60.0 / self.tempo_bpm
