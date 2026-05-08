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
    section_letter: str = "A"       # form-section label (A/B/C/Ap/...)
    melody_transpose: int = 0       # per-bar scale-degree shift from HKDF mutation seed
    melody_invert: bool = False     # mirror the contour around its mean
    bass_octave_shift: int = 0      # +12/-12 transpose for bass this bar
    bass_skip_last: bool = False    # rest the last bass cell (fill-style breath)
    bass_ghost_first: bool = False  # play first cell at ghost velocity
    comp_drop_last: bool = False    # rest the last comp hit (per-bar ear-candy)
    comp_vel_pull: int = 0          # ±5 velocity pull on comp this bar
    # Layer dropouts (silence drives interest in soft moods). Each flag
    # silences that layer for this bar even if the energy gate would pass.
    drop_drums: bool = False
    drop_lead: bool = False
    drop_comp: bool = False
    drop_pad: bool = False
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
    groove_template_id: str = "straight_4_4"
    bars: tuple[Bar, ...] = ()
    layers: tuple[LayerSpec, ...] = ()
    bar_energies: tuple[float, ...] = ()  # one 0..1 per bar from the energy curve
    section_motif_ids: dict[str, str] = field(default_factory=dict)
    section_contour_ids: dict[str, str] = field(default_factory=dict)
    section_comp_pattern_ids: dict[str, str] = field(default_factory=dict)
    # Per-section layer activity from layer_activation matrix:
    # {section_letter: [drums, bass, comp, lead, counter, drone, fx_riser, ad_lib]}
    # cell values: '-' silent, 's' sparse, 'n' normal, 'd' dense, '*' energy-scaled.
    activation_rows: dict[str, list[str]] = field(default_factory=dict)
    render: RenderHints = field(default_factory=RenderHints)

    def total_duration_seconds(self) -> float:
        beats_per_bar = self.time_sig[0]
        return len(self.bars) * beats_per_bar * 60.0 / self.tempo_bpm
