"""Music-theory helpers — pure functions, no I/O.

Just enough to resolve a Roman-numeral progression into per-bar (root MIDI,
chord quality, chord-tone PC set) tuples.
"""
from __future__ import annotations

from typing import Iterable

# ---------------------------------------------------------------------------
# Pitch classes
# ---------------------------------------------------------------------------

PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


# Mode intervals from tonic (semitones), 7 degrees each.
MODES: dict[str, tuple[int, ...]] = {
    "ionian":      (0, 2, 4, 5, 7, 9, 11),
    "aeolian":     (0, 2, 3, 5, 7, 8, 10),
    "dorian":      (0, 2, 3, 5, 7, 9, 10),
    "phrygian":    (0, 1, 3, 5, 7, 8, 10),
    "lydian":      (0, 2, 4, 6, 7, 9, 11),
    "mixolydian":  (0, 2, 4, 5, 7, 9, 10),
    "jazz_minor":  (0, 2, 3, 5, 7, 9, 11),
    "locrian":     (0, 1, 3, 5, 6, 8, 10),
}


# Chord quality → semitone offsets from root.
QUALITY_PCS: dict[str, tuple[int, ...]] = {
    "maj":      (0, 4, 7),
    "min":      (0, 3, 7),
    "dim":      (0, 3, 6),
    "aug":      (0, 4, 8),
    "sus":      (0, 5, 7),
    "sus2":     (0, 2, 7),
    "sus4":     (0, 5, 7),
    "maj7":     (0, 4, 7, 11),
    "m7":       (0, 3, 7, 10),
    "min7":     (0, 3, 7, 10),
    "dom7":     (0, 4, 7, 10),
    "min7b5":   (0, 3, 6, 10),
    "m7b5":     (0, 3, 6, 10),
    "dim7":     (0, 3, 6, 9),
    "mMaj7":    (0, 3, 7, 11),
}


# Roman numeral (case-insensitive base) → diatonic scale degree (1-indexed).
_ROMAN_DEGREE = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
}


# ---------------------------------------------------------------------------
# Roman-numeral parsing
# ---------------------------------------------------------------------------


def parse_roman_root(rn: str) -> tuple[int, int]:
    """Parse a Roman numeral string and return (degree_1to7, semitone_alteration).

    `semitone_alteration` is -1 for flat-prefixed (bVII), +1 for sharp (#iv),
    0 otherwise. Extensions (7, maj7, etc.) and secondary-dominant suffixes
    (V7/V) are ignored — quality lives in the progression's `qualities` array.

    Examples:
      "I"        → (1, 0)
      "vi"       → (6, 0)
      "bVII"     → (7, -1)
      "V7/V"     → (5, 0)        # we treat the *applied* chord as living on V
                                 #   (the secondary-dom target is downstream)
      "iim7b5"   → (2, 0)
    """
    s = rn.strip()
    alt = 0
    if s.startswith("b"):
        alt = -1
        s = s[1:]
    elif s.startswith("#"):
        alt = +1
        s = s[1:]

    # Strip secondary-dominant target after slash; ignore extensions after numeral.
    if "/" in s:
        s = s.split("/", 1)[0]

    # Pull the numeral prefix off the front (longest first).
    s_lower = s.lower()
    for numeral in ("vii", "iii", "iv", "vi", "ii", "v", "i"):
        if s_lower.startswith(numeral):
            return _ROMAN_DEGREE[numeral], alt
    raise ValueError(f"unparseable Roman numeral: {rn!r}")


# ---------------------------------------------------------------------------
# Progression → chord-pitch resolution
# ---------------------------------------------------------------------------


def chord_pcs(quality: str) -> tuple[int, ...]:
    """Return the semitone-from-root pitch classes for a chord quality."""
    return QUALITY_PCS.get(quality, QUALITY_PCS["maj"])


def degree_to_pc(degree: int, alteration: int, key_root_pc: int, mode: str) -> int:
    """Return the pitch class (0..11) of a Roman numeral's root."""
    intervals = MODES[mode]
    base = intervals[degree - 1]
    return (key_root_pc + base + alteration) % 12


def resolve_progression(
    progression: dict,
    key_root_pc: int,
    mode: str | None = None,
    bass_octave: int = 2,
) -> list[dict]:
    """Resolve a progression dict into per-chord (bar) entries.

    Returns a list of dicts of length `progression["length_bars"]`. Each entry:
        {
          "rn": "I",
          "quality": "maj",
          "root_pc": 0,
          "root_midi": 36,            # bass octave
          "chord_pcs": [0, 4, 7],
          "bass_inversion": 0,
        }
    """
    rn_list = progression["rn"]
    qualities = progression["qualities"]
    inversions = progression.get("bass_inversions", [0] * len(rn_list))
    prog_mode = mode or progression["mode"]
    out = []
    for i, rn in enumerate(rn_list):
        deg, alt = parse_roman_root(rn)
        root_pc = degree_to_pc(deg, alt, key_root_pc, prog_mode)
        q = qualities[i]
        pcs = chord_pcs(q)
        root_midi = bass_octave * 12 + root_pc  # MIDI 0 = C-1 → octave 0 = C-1, octave 2 = C1; bass C = 24+root_pc … in our convention bass_octave=2 → MIDI 24+pc; for "C2" we want MIDI 36 actually
        # Match the "MIDI octave" convention where C4 = 60. So MIDI = (octave+1)*12 + pc.
        root_midi = (bass_octave + 1) * 12 + root_pc
        out.append({
            "rn": rn,
            "quality": q,
            "root_pc": root_pc,
            "root_midi": root_midi,
            "chord_pcs": list(pcs),
            "bass_inversion": inversions[i] if i < len(inversions) else 0,
        })
    return out


def chord_tones_midi(entry: dict, octave: int = 4) -> list[int]:
    """Return MIDI pitches of the chord tones in a target octave (C4 = 60)."""
    base = (octave + 1) * 12 + entry["root_pc"]
    return [base + iv for iv in entry["chord_pcs"]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def diatonic_pcs(key_root_pc: int, mode: str) -> list[int]:
    """The 7 diatonic pitch classes of a key+mode."""
    return [(key_root_pc + iv) % 12 for iv in MODES[mode]]


def name_for_pc(pc: int) -> str:
    return PITCH_NAMES[pc % 12]
