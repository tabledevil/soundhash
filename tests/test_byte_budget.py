"""Byte-budget assertions tracking DESIGN.md §4.

Each entry: (byte_index, dimension_number, what_it_decides). When a future
change shifts a byte's owner, this test is the single point of update.
"""

# (byte, dim, decision)
BYTE_BUDGET = [
    (0,  11, "macro mood"),
    (1,  11, "mood sub-flavor"),
    (2,   2, "tempo bucket + nudge"),
    (3,   1, "key root"),
    (4,   1, "mode"),
    (5,   2, "time-sig + swing combo"),
    (6,   3, "form template"),
    (7,   4, "progression bank index"),
    (8,   4, "voicing style + sec-dom + mixture"),
    (9,   5, "drum kit"),
    (10,  5, "drum patterns A,B"),
    (11,  5, "fill arming + style mods"),
    (12,  5, "escalation + de-escalation algo"),
    (13,  6, "bass archetype + mutation seed"),
    (14,  6, "bass synth + octave + articulation"),
    (15,  7, "comp role"),
    (16,  7, "comp synth"),
    (17,  7, "comp pattern variant"),
    (18,  8, "melody scale subset"),
    (19,  8, "melody motif"),
    (20,  8, "melody contour"),
    (21,  8, "melody phrase"),
    (22,  8, "melody tessitura + lead synth"),
    (23,  9, "aux mask + counter-melody mode"),
    (24,  3, "energy curve + section perturb"),
    (25,  3, "layer activation matrix"),
    (26,  3, "per-bar mutation seed + accent skeleton"),
    (27, 10, "velocity + humanization + vibrato + portamento"),
    (28, 12, "FX preset"),
    (29, 12, "FX send levels"),
    (30, 12, "mix balance preset"),
    (31, 13, "variation salt"),
]


def test_budget_covers_32_bytes():
    indices = [b[0] for b in BYTE_BUDGET]
    assert indices == list(range(32))


def test_no_gaps_no_dupes():
    assert len(set(b[0] for b in BYTE_BUDGET)) == 32


def test_every_dim_present():
    dims_used = {b[1] for b in BYTE_BUDGET}
    # Dim 14 (perceptual/determinism) doesn't claim a byte; it operates on the rendered output.
    assert dims_used == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}
