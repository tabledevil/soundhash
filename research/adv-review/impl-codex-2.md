OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/tabledevil/projects/soundhash/research/adv-review
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019e082e-34ea-70d0-bfb6-d1fc65ec2363
--------
user
Soundhash: SHA-256 → 30s deterministic music. HKDF derives all decisions. 9-layer MIDI render (incl. lead/bass/pads/drums/arps/counter), pedalboard FX, LUFS+peak limiter, quality scoring.

TASK: Output ONLY 5 concrete diffs (within 200 LOC total) that maximize DISTINGUISHABILITY (different SHA-256 inputs sound perceptually different) AND REPRODUCIBILITY (same input = same bits). Each diff: file:line, brief before, brief after, 1-line impact rationale. NO exploration, NO preamble, just 5 numbered diffs. Code is below.

## decode.py
"""Decode a SHA-256 (and optional MIME) into a SongSpec.

Pure function. No I/O after table preload, no system clock, no system random.
All entropy comes from HKDF-Expand of the input hash.

Current scope: produces a fully populated macro SongSpec — mood, tempo, key,
mode, progression resolved to per-bar chord roots and PC sets — for any input.
The melody/bass/drum note generation lives downstream and is not yet wired.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from . import tables, theory
from .spec import (
    Bar,
    LayerSpec,
    Provenance,
    RenderHints,
    SongSpec,
)


# ---------------------------------------------------------------------------
# HKDF (RFC 5869) over SHA-256
# ---------------------------------------------------------------------------

_SALT = b"soundhash-v1"


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    out, t, counter = b"", b"", 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        out += t
        counter += 1
    return out[:length]


class HashStream:
    """Domain-separated entropy stream derived from the input hash."""

    __slots__ = ("_prk", "_version")

    def __init__(self, prk: bytes, version: str = "v1"):
        self._prk = prk
        self._version = version

    def take(self, label: str, n: int) -> bytes:
        info = f"soundhash/{self._version}/{label}".encode("ascii")
        return _hkdf_expand(self._prk, info, n)

    def pick(self, label: str, table):
        b = self.take(label, 1)[0]
        return table[b % len(table)]


# ---------------------------------------------------------------------------
# Selection helpers — each one applies the constraint propagation principle
# ---------------------------------------------------------------------------


def _pick_mood(macro: bytes, mime_family: str | None) -> str:
    """Byte 0 selects mood within a MIME-family-filtered candidate list.

    With mime=None we expose all 11 moods.
    """
    f2m = tables.load("family_to_moods")
    if mime_family and mime_family in f2m["mapping"]:
        candidates = f2m["mapping"][mime_family]["candidates"]
    else:
        candidates = list(f2m["moods"].keys())
    return candidates[macro[0] % len(candidates)]


def _pick_tempo(byte: int, mood: str) -> float:
    pools = tables.load("tempo_pools")["pools"]
    pool = pools[mood]["bpm"]
    base = pool[(byte & 0x07) % len(pool)]
    # 5 high bits drive a ±0.5% nudge to retain entropy without changing perceived BPM.
    nudge = ((byte >> 3) - 16) / 16.0 * 0.005      # in [-0.005, +0.00469]
    return round(base * (1.0 + nudge), 3)


def _pick_mode(byte: int, mood: str) -> str:
    moods = tables.load("moods")["moods"]
    mood_modes = moods[mood]["modes"]
    return mood_modes[byte % len(mood_modes)]


_MOOD_GROOVE_POOL: dict[str, tuple[str, ...]] = {
    "M0":  ("ambient_drift", "neo_soul", "straight_4_4"),
    "M1":  ("straight_4_4", "neo_soul", "gospel_12_8"),
    "M2":  ("boom_bap_60", "dilla_feel", "mpc60_swing"),
    "M3":  ("neo_soul", "mpc60_swing", "dilla_feel", "straight_4_4"),
    "M4":  ("latin_clave_pocket", "dembow_pocket", "mpc60_swing"),
    "M5":  ("synthwave_tight", "straight_4_4"),
    "M6":  ("house_pocket", "amapiano_pocket", "straight_4_4"),
    "M7":  ("techno_push", "straight_4_4"),
    "M8":  ("dnb_amen_lean", "straight_4_4"),
    "M9":  ("trap_triplet_hat", "straight_4_4"),
    "M10": ("straight_4_4", "gospel_12_8", "ambient_drift"),
    "M11": ("dilla_feel", "boom_bap_60", "mpc60_swing", "neo_soul"),    # lofi swing
    "M12": ("ambient_drift", "neo_soul", "straight_4_4"),               # chillout flow
    "M13": ("straight_4_4",),                                            # simple = on the grid
    "M14": ("straight_4_4",),                                            # gameboy = rigid
}


def _pick_groove_template(byte: int, mood: str) -> str:
    pool = _MOOD_GROOVE_POOL.get(mood, ("straight_4_4",))
    try:
        templates = tables.load("groove_templates")["templates"]
    except FileNotFoundError:
        return pool[0]
    available = {t["id"] for t in templates}
    pool = tuple(p for p in pool if p in available) or ("straight_4_4",)
    return pool[byte % len(pool)]


def _expand_form_layout(form: dict, n_bars: int) -> list[str]:
    """Turn `[[letter, bar_count_or_'N'], ...]` into a per-bar section-letter list of length n_bars."""
    layout = form.get("layout") or [["A", "N"]]
    fixed = [(letter, count) for letter, count in layout if count != "N"]
    fixed_total = sum(c for _, c in fixed)
    n_remaining = max(0, n_bars - fixed_total)
    n_natural = sum(1 for _, c in layout if c == "N") or 1
    natural_share, extra = divmod(n_remaining, n_natural)

    out: list[str] = []
    for letter, count in layout:
        if count == "N":
            share = natural_share + (1 if extra > 0 else 0)
            extra = max(0, extra - 1)
            out.extend([letter] * share)
        else:
            out.extend([letter] * count)
    # Truncate / pad to exactly n_bars.
    out = out[:n_bars]
    while len(out) < n_bars:
        out.append(out[-1] if out else "A")
    return out


def _pick_form(byte: int, n_bars: int) -> dict:
    forms = tables.load("forms")["forms"]
    eligible = [f for f in forms if f.get("min_bars", 1) <= n_bars <= f.get("max_bars", 99)]
    if not eligible:
        eligible = forms
    eligible.sort(key=lambda f: f.get("id", 0))
    return eligible[byte % len(eligible)]


# Per-mood form-id preferences. Empty intersection with the 30-s-fit set
# falls back to the unfiltered list. IDs reference forms.json:
#   0 through_composed,  1 A_Aprime,  2 AB_simple,  3 AAB,  4 ABA,
#   5 ABAB,  6 intro_A_fill_A_out,  7 A_build_drop_A,  8 theme_var,
#   9 call_response,  10 intro_A,  11 A_outro,  12 AB_with_fill,
#   13 AABA,  14 ABCA,  15 breakdown_form,  16 riser_drop_loop,
#   17 ostinato_layer,  18 two_arches,  19 late_drop,  20 plateau_fall,
#   21 pyramid,  22 medley,  23 pulse_only.
_MOOD_FORM_PREF: dict[str, tuple[int, ...]] = {
    "M0":  (0, 1, 8, 17, 23),                # ambient: through-composed / ostinato / pulse
    "M1":  (1, 4, 6, 11, 13, 18),            # ballad: A_Aprime, ABA, AABA, two_arches
    "M2":  (2, 5, 8, 13, 14),                # hip-hop: AB / ABAB / theme_var / AABA / ABCA
    "M3":  (0, 1, 8, 17, 18),                # downtempo
    "M4":  (5, 13, 14, 8),                   # latin: ABAB / AABA / ABCA / theme_var
    "M5":  (5, 7, 13, 14, 19),               # synthwave: ABAB / build_drop / late_drop
    "M6":  (5, 14, 15, 19, 16),              # house
    "M7":  (15, 16, 19, 21, 23),             # techno
    "M8":  (5, 7, 16, 19),                   # dnb
    "M9":  (8, 18, 21, 22),                  # glitch
    "M10": (4, 6, 13, 14, 18, 20),           # cinematic
    "M11": (1, 4, 8, 17, 13),                # lofi: A_Aprime / ABA / theme_var / ostinato_layer / AABA
    "M12": (0, 1, 4, 8, 17, 18, 23),         # chillout: through_composed / A_Aprime / ABA / theme_var
    "M13": (1, 4, 13, 23),                   # simple: A_Aprime / ABA / AABA / pulse_only
    "M14": (5, 13, 14, 4, 21),               # gameboy: ABAB / AABA / ABCA / ABA / pyramid
}


def _pick_form_unconstrained(byte: int, max_bars: int, mood: str = "") -> dict:
    """Pick a form whose min_bars fits within max_bars (the 30-second cap),
    biased toward mood-preferred forms when possible."""
    forms = tables.load("forms")["forms"]
    fits = [f for f in forms if f.get("min_bars", 1) <= max_bars]
    if not fits:
        fits = forms
    pref = set(_MOOD_FORM_PREF.get(mood, ()))
    eligible = [f for f in fits if f.get("id") in pref] if pref else []
    if not eligible:
        eligible = fits
    eligible.sort(key=lambda f: f.get("id", 0))
    return eligible[byte % len(eligible)]


def _bars_from_layout(form: dict, default_n: int = 8, cap: int = 99) -> int:
    """Sum fixed counts in form.layout; allocate `default_n` to any 'N' filler.

    Result clamped to [form.min_bars, form.max_bars] then to `cap`.
    """
    layout = form.get("layout") or [["A", "N"]]
    fixed = sum(c for _, c in layout if c != "N")
    n_natural = sum(1 for _, c in layout if c == "N")
    total = fixed + n_natural * max(2, default_n // max(1, len(layout)))
    if not fixed and not n_natural:
        total = default_n
    lo = form.get("min_bars", 1)
    hi = min(cap, form.get("max_bars", cap))
    return max(lo, min(hi, total))


# Per-mood curve-id preferences (intersected with form.allowed_curves).
# IDs: 0 flat_low, 1 flat_mid, 2 flat_high, 3 rise, 4 fall, 5 arc, 6 U,
# 7 two_arches, 8 late_drop, 9 early_drop, 10 plateau_fall,
# 11 slow_build_cliff, 12 sawtooth_2, 13 terraces, 14 breath, 15 reverse_arc.
_MOOD_CURVE_PREF: dict[str, tuple[int, ...]] = {
    "M0":  (0, 1, 6, 14, 15),
    "M1":  (5, 7, 14, 10),
    "M2":  (1, 13, 7),
    "M3":  (5, 14, 13),
    "M4":  (5, 13, 7, 3),
    "M5":  (3, 5, 8, 11),
    "M6":  (3, 13, 8, 11, 5),
    "M7":  (3, 11, 8, 13),
    "M8":  (8, 11, 7),
    "M9":  (12, 7, 13, 4),
    "M10": (5, 11, 7, 14, 15),
    "M11": (1, 14, 5, 13, 6),                # lofi — flat-mid w/ breath, gentle arc, U
    "M12": (1, 14, 6, 5, 15),                # chillout — flat, breath, U
    "M13": (0, 1, 14, 6),                    # simple — flat low/mid, breath
    "M14": (3, 5, 7, 13),                    # gameboy — rise, arc, two_arches, terraces
}


def _pick_energy_curve(byte: int, form: dict, mood: str = "") -> dict:
    curves = tables.load("energy_curves")["curves"]
    allowed_ids = set(form.get("allowed_curves") or [c["id"] for c in curves])
    pref_ids = set(_MOOD_CURVE_PREF.get(mood, ())) & allowed_ids
    chosen_ids = pref_ids if pref_ids else allowed_ids
    eligible = [c for c in curves if c.get("id") in chosen_ids] or curves
    eligible.sort(key=lambda c: c.get("id", 0))
    return eligible[byte % len(eligible)]


def _sample_energy_curve(curve: dict, fraction: float) -> float:
    """Linear interpolation over the curve's `points: [[fraction, energy], ...]`."""
    pts = curve.get("points") or [[0.0, 0.5], [1.0, 0.5]]
    if fraction <= pts[0][0]:
        return float(pts[0][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if fraction <= x1:
            if x1 == x0:
                return float(y1)
            t = (fraction - x0) / (x1 - x0)
            return float(y0 + (y1 - y0) * t)
    return float(pts[-1][1])


def _pick_progression(byte: int, mood: str, mode: str) -> dict:
    """Filter progression bank by mood-tag ∩ mode, then index."""
    progs = tables.load("harmony/progressions")["progressions"]
    eligible = [p for p in progs if mood in p.get("mood_tags", []) and p["mode"] == mode]
    if not eligible:
        # Fallback: relax mode constraint, keep mood.
        eligible = [p for p in progs if mood in p.get("mood_tags", [])]
    if not eligible:
        # Last-resort fallback: any ionian progression.
        eligible = [p for p in progs if p["mode"] == "ionian"]
    eligible.sort(key=lambda p: p["id"])               # stable order
    return eligible[byte % len(eligible)]


def _filter_by_mood(items, mood):
    return [x for x in items if mood in x.get("mood_tags", [])]


def _pick_drum_kit(byte: int, mood: str) -> dict:
    kits = tables.load("drums/drumkits")["kits"]
    eligible = _filter_by_mood(kits, mood) or kits
    eligible.sort(key=lambda k: k["id"])
    return eligible[byte % len(eligible)]


# ---------------------------------------------------------------------------
# Mood-keyed GM program palettes (placeholder until synth_pool.json is wired).
# Each tuple gives candidates for that role; byte % len picks one.
# ---------------------------------------------------------------------------

# (gm_program, name) — stick to widely-supported GM patches so MS Basic / GeneralUser cover them.
_GM_PALETTE: dict[str, dict[str, tuple[int, ...]]] = {
    "M0":  {"bass": (32,),               "comp": (88, 89, 91),       "lead": (54, 75, 73),   "pad": (88, 89, 94),    "counter": (52, 73, 91)},   # Ambient
    "M1":  {"bass": (32, 33),            "comp": (0, 4, 24),         "lead": (73, 71, 56),   "pad": (89, 91, 95),    "counter": (40, 41, 73)},
    "M2":  {"bass": (33, 34, 36),        "comp": (4, 5, 11),         "lead": (80, 81, 28),   "pad": (89, 95, 91),    "counter": (4, 5, 11)},
    "M3":  {"bass": (33, 36),            "comp": (4, 5, 88, 89),     "lead": (80, 73, 78),   "pad": (89, 91, 94),    "counter": (52, 91, 73)},
    "M4":  {"bass": (32, 35),            "comp": (24, 25, 32),       "lead": (56, 11, 24),   "pad": (89, 91, 94),    "counter": (60, 56, 73)},
    "M5":  {"bass": (38, 39, 33),        "comp": (81, 89, 80),       "lead": (81, 80, 84),   "pad": (90, 89, 94),    "counter": (82, 81, 84)},
    "M6":  {"bass": (38, 39, 36),        "comp": (16, 17, 81),       "lead": (80, 81, 53),   "pad": (90, 89, 95),    "counter": (54, 80, 81)},
    "M7":  {"bass": (38, 39),            "comp": (81, 89, 90),       "lead": (80, 81, 87),   "pad": (90, 94, 89),    "counter": (87, 80, 81)},
    "M8":  {"bass": (38, 39, 87),        "comp": (89, 88, 91),       "lead": (81, 80, 87),   "pad": (89, 91, 94),    "counter": (54, 81, 91)},
    "M9":  {"bass": (38, 39, 87),        "comp": (90, 91, 102),      "lead": (88, 81, 102),  "pad": (95, 91, 94),    "counter": (102, 88, 91)},
    "M10": {"bass": (32, 43, 44),        "comp": (48, 49, 50, 89),   "lead": (60, 73, 71),   "pad": (49, 51, 94),    "counter": (49, 73, 71)},  # strings/choir
}


def _pick_gm_program(byte: int, mood: str, layer: str, default: int) -> int:
    pal = _GM_PALETTE.get(mood, {}).get(layer)
    if not pal:
        return default
    return pal[byte % len(pal)]


def _pick_drum_pattern(byte: int, kit_id: str, time_sig: str) -> dict:
    pats = tables.load(f"drums/patterns/{kit_id}")["patterns"]
    eligible = [p for p in pats if time_sig in p.get("valid_time_sigs", [time_sig])]
    if not eligible:
        eligible = pats
    eligible.sort(key=lambda p: p["id"])
    return eligible[byte % len(eligible)]


def _pick_drum_fill(byte: int, kit_id: str) -> str:
    try:
        fills = tables.load(f"drums/fills/{kit_id}")["fills"]
    except FileNotFoundError:
        return ""
    if not fills:
        return ""
    # Prefer escalating fills (target_density > current_density) for a build-up feel.
    eligible = [f for f in fills
                if f.get("target_density", 0) >= f.get("current_density", 0)] or fills
    eligible.sort(key=lambda f: f["id"])
    return eligible[byte % len(eligible)]["id"]


def _pick_drum_pattern_pair(byte: int, kit_id: str, time_sig: str) -> tuple[dict, dict]:
    """Pick a (low-density, high-density) pair so render can pick per-bar by energy."""
    try:
        pats = tables.load(f"drums/patterns/{kit_id}")["patterns"]
    except FileNotFoundError:
        return ({}, {})
    eligible = [p for p in pats if time_sig in p.get("valid_time_sigs", [time_sig])] or pats
    eligible.sort(key=lambda p: (p.get("density", 2), p["id"]))
    low = [p for p in eligible if p.get("density", 2) <= 2] or eligible
    high = [p for p in eligible if p.get("density", 2) >= 3] or eligible
    pat_low = low[(byte & 0x0F) % len(low)]
    pat_high = high[(byte >> 4) % len(high)]
    return pat_low, pat_high


def _pick_bass_pattern(byte: int, mood: str, time_sig: str) -> dict:
    pats = tables.load("bass/bass_patterns")["patterns"]
    eligible = [p for p in _filter_by_mood(pats, mood) if time_sig in p.get("time_sigs", [])]
    if not eligible:
        eligible = [p for p in pats if time_sig in p.get("time_sigs", [])] or pats
    eligible.sort(key=lambda p: p["id"])
    return eligible[byte % len(eligible)]


def _pick_bass_synth(byte: int, mood: str, pattern_id: str) -> dict:
    synths = tables.load("bass/bass_synths")["synths"]
    eligible = [s for s in _filter_by_mood(synths, mood)
                if not s.get("pattern_compat") or pattern_id in s["pattern_compat"]]
    if not eligible:
        eligible = _filter_by_mood(synths, mood) or synths
    eligible.sort(key=lambda s: s["id"])
    return eligible[byte % len(eligible)]


def _pick_comp_role(byte: int, mood: str) -> dict:
    roles = tables.load("comp/comp_roles")["roles"]
    eligible = _filter_by_mood(roles, mood) or roles
    eligible.sort(key=lambda r: r["id"])
    return eligible[byte % len(eligible)]


def _pick_comp_synth(byte: int, mood: str, role_id: str) -> dict:
    synths = tables.load("comp/comp_synths")["synths"]
    eligible = [s for s in _filter_by_mood(synths, mood) if role_id in s.get("compatible_roles", [])]
    if not eligible:
        eligible = _filter_by_mood(synths, mood) or synths
    eligible.sort(key=lambda s: s["id"])
    return eligible[byte % len(eligible)]


def _pick_arp_shape(byte: int, mood: str) -> dict:
    data = tables.load("comp/arp_shapes")
    shapes = data.get("shapes", data.get("arp_shapes", data))
    if isinstance(shapes, dict):
        shapes = list(shapes.values())
    eligible = [sh for sh in shapes if mood in sh.get("mood_tags", [])] or shapes
    eligible = sorted(eligible, key=lambda sh: sh.get("id", ""))
    return eligible[byte % len(eligible)]


def _pick_comp_pattern(byte: int, mood: str, time_sig: str) -> dict:
    pats = tables.load("comp/chord_rhythm_patterns")["patterns"]
    eligible = [p for p in _filter_by_mood(pats, mood) if time_sig in p.get("time_sigs", [])]
    if not eligible:
        eligible = [p for p in pats if time_sig in p.get("time_sigs", [])] or pats
    eligible.sort(key=lambda p: p["id"])
    return eligible[byte % len(eligible)]


def _all_comp_patterns(mood: str, time_sig: str) -> list[dict]:
    pats = tables.load("comp/chord_rhythm_patterns")["patterns"]
    eligible = [p for p in pats if mood in p.get("mood_tags", []) and time_sig in p.get("time_sigs", [])]
    if not eligible:
        eligible = [p for p in pats if time_sig in p.get("time_sigs", [])] or pats
    return sorted(eligible, key=lambda p: p["id"])


def _all_motifs_for_time_sig(time_sig: str) -> list[dict]:
    data = tables.load("melody/motif_rhythms")
    pools = data.get("pools", data)
    pool = pools.get(time_sig) or pools.get(time_sig.replace("/", "_")) or next(iter(pools.values()), {})
    if isinstance(pool, dict):
        flat = []
        for v in pool.values():
            if isinstance(v, list):
                flat.extend(v)
        return sorted(flat, key=lambda x: x.get("id", ""))
    return sorted(list(pool), key=lambda x: x.get("id", ""))


def _all_contours() -> list[dict]:
    data = tables.load("melody/contours")
    contours = data.get("contours", data)
    if isinstance(contours, dict):
        contours = list(contours.values())
    return sorted(contours, key=lambda x: x.get("id", ""))


def _pick_melody_motif(byte: int, time_sig: str, mood: str = "") -> dict:
    pool = _all_motifs_for_time_sig(time_sig)
    eligible = [m for m in pool if mood in m.get("mood_tags", [])] if mood else []
    if not eligible:
        eligible = pool
    return eligible[byte % len(eligible)]


def _pick_contour(byte: int, mood: str = "") -> dict:
    pool = _all_contours()
    eligible = [c for c in pool if mood in c.get("mood_tags", [])] if mood else []
    if not eligible:
        eligible = pool
    return eligible[byte % len(eligible)]


def _pick_scale_subset(byte: int, mode: str) -> dict:
    data = tables.load("melody/scale_subsets")
    subsets = data.get("subsets", data.get("scale_subsets", data))
    if isinstance(subsets, dict):
        subsets = list(subsets.values())
    eligible = [s for s in subsets if mode in s.get("applies_to_modes", [mode])] or subsets
    eligible = sorted(eligible, key=lambda x: x.get("id", str(x)))
    return eligible[byte % len(eligible)]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


class UnsupportedVersionError(ValueError):
    pass


def hash_to_spec(
    hash_bytes: bytes,
    mime: Optional[str] = None,
    version: str = "v1",
    mood_override: Optional[str] = None,
) -> SongSpec:
    """Pure: same (hash, mime, version) → same SongSpec.

    Walks the byte budget from CONTEXT/§4 of DESIGN.md top-down, filtering each
    table by all prior choices. See test_decode_invariants.py for invariants.
    """
    if len(hash_bytes) != 32:
        raise ValueError(f"expected 32-byte SHA-256, got {len(hash_bytes)}")
    if version != "v1":
        raise UnsupportedVersionError(version)

    prk = _hkdf_extract(_SALT, hash_bytes)
    s = HashStream(prk, version)
    macro = s.take("macro", 32)

    # MIME → family pre-filter.
    from .mime import family_for_mime
    family = family_for_mime(mime)

    # Macro decisions.
    if mood_override and mood_override.startswith("M") and mood_override[1:].isdigit():
        mood = mood_override
    else:
        mood = _pick_mood(macro, family)
    tempo = _pick_tempo(macro[2], mood)
    key_root = macro[3] % 12
    mode = _pick_mode(macro[4], mood)
    progression = _pick_progression(macro[7], mood, mode)

    # Resolve progression to per-bar chord entries.
    chord_entries = theory.resolve_progression(progression, key_root, mode)

    # Form first — its layout determines bar count, then we cap by what fits
    # in 30 seconds at the chosen tempo (leave 2 s for reverb tail).
    beats_per_bar = 4
    max_bars_for_30s = max(2, int(28.0 * tempo / (60.0 * beats_per_bar)))
    form = _pick_form_unconstrained(macro[6], max_bars_for_30s, mood)
    target_bars = _bars_from_layout(form, default_n=8, cap=max_bars_for_30s)

    # Loop the progression to fill target_bars.
    looped = []
    while len(looped) < target_bars:
        looped.extend(chord_entries)
    looped = looped[:target_bars]
    energy_curve = _pick_energy_curve(macro[24], form, mood)
    groove_id = _pick_groove_template(macro[5], mood)
    section_letters = _expand_form_layout(form, target_bars)
    if target_bars > 1:
        bar_energies = tuple(
            _sample_energy_curve(energy_curve, (i + 0.5) / target_bars)
            for i in range(target_bars)
        )
    else:
        bar_energies = (_sample_energy_curve(energy_curve, 0.5),)

    bars = []
    for i, e in enumerate(looped):
        # Per-bar mutation seeds from HKDF.
        mel_seed = s.take(f"perbar/melody/{i}", 4)
        bass_seed = s.take(f"perbar/bass/{i}", 2)
        mel_op = mel_seed[0] % 8
        bass_op = bass_seed[0] % 8
        # Bar 0 is always identity so the hook + groove land cleanly first.
        if i == 0:
            transpose, invert = 0, False
            octave_shift, skip_last, ghost_first = 0, False, False
        else:
            transpose = {2: +1, 3: -1, 4: +2, 5: -2}.get(mel_op, 0)
            invert = (mel_op == 6)
            octave_shift = {2: +12, 3: -12}.get(bass_op, 0)
            skip_last = (bass_op == 4)
            ghost_first = (bass_op == 5)
        comp_seed = s.take(f"perbar/comp/{i}", 2)
        if i == 0:
            comp_drop_last, comp_vel_pull = False, 0
        else:
            comp_drop_last = (comp_seed[0] % 8 == 0)              # ~12.5% of bars drop last hit
            comp_vel_pull = (comp_seed[1] % 11) - 5                # -5..+5 velocity pull

        # Per-bar layer dropout seed. Soft moods (M0/M11/M12/M13) silence
        # individual layers occasionally so the mix breathes — every 4-8
        # bars some layer rests for a bar.
        drop_seed = s.take(f"perbar/aux/{i}", 4)
        soft_mood = mood in ("M0", "M11", "M12", "M13")
        if i == 0:
            drop_drums = drop_lead = drop_comp = drop_pad = False
        elif soft_mood:
            # Each layer has a 1-in-6 to 1-in-4 chance of resting this bar.
            drop_drums = (drop_seed[0] % 6 == 0)
            drop_lead  = (drop_seed[1] % 5 == 0)
            drop_comp  = (drop_seed[2] % 6 == 0)
            drop_pad   = (drop_seed[3] % 7 == 0)
        else:
            # On other moods only the lead occasionally rests (1-in-12 bars).
            drop_drums = drop_comp = drop_pad = False
            drop_lead = (drop_seed[1] % 12 == 0)
        bars.append(Bar(
            index=i,
            chord=f"{theory.name_for_pc(e['root_pc'])}{e['quality']}",
            chord_root_pc=e["root_pc"],
            chord_root_midi=e["root_midi"],
            chord_pcs=tuple(e["chord_pcs"]),
            chord_quality=e["quality"],
            section_letter=section_letters[i] if i < len(section_letters) else "A",
            melody_transpose=transpose,
            melody_invert=invert,
            bass_octave_shift=octave_shift,
            bass_skip_last=skip_last,
            bass_ghost_first=ghost_first,
            comp_drop_last=comp_drop_last,
            comp_vel_pull=comp_vel_pull,
            drop_drums=drop_drums,
            drop_lead=drop_lead,
            drop_comp=drop_comp,
            drop_pad=drop_pad,
        ))
    bars = tuple(bars)

    # Per-layer picks (constraint propagation continues).
    time_sig_str = "4/4"
    drum_kit = _pick_drum_kit(macro[9], mood)
    drum_pat_low, drum_pat_high = _pick_drum_pattern_pair(macro[10], drum_kit["id"], time_sig_str)
    drum_pat = drum_pat_low or drum_pat_high or {}
    drum_fill_id = _pick_drum_fill(macro[11], drum_kit["id"])
    bass_pat = _pick_bass_pattern(macro[13], mood, time_sig_str)
    bass_synth = _pick_bass_synth(macro[14], mood, bass_pat["id"])
    comp_role = _pick_comp_role(macro[15], mood)
    comp_synth = _pick_comp_synth(macro[16], mood, comp_role["id"])
    comp_pat = _pick_comp_pattern(macro[17], mood, time_sig_str)
    arp_shape = _pick_arp_shape(macro[17], mood)
    melody_motif = _pick_melody_motif(macro[19], time_sig_str, mood)
    melody_contour = _pick_contour(macro[20], mood)
    melody_scale = _pick_scale_subset(macro[18], mode)

    # Prefer the picked synth's gm_program (more specific than the mood palette).
    bass_program = (bass_synth.get("gm_program")
                    or _pick_gm_program(macro[14], mood, "bass", default=33))
    comp_program = _pick_gm_program(macro[16], mood, "comp", default=4)
    lead_program = _pick_gm_program(macro[21], mood, "lead", default=80)
    pad_program  = _pick_gm_program(macro[23], mood, "pad",  default=89)
    counter_program = _pick_gm_program(macro[22], mood, "counter", default=73)
    counter_program = _pick_gm_program(macro[23] ^ 0x55, mood, "counter", default=73)

    # Per-section motif & contour overrides — introduces real variation between
    # form sections (A/B/C). Falls back to the macro melody picks for section A.
    motif_pool = _all_motifs_for_time_sig(time_sig_str)
    contour_pool = _all_contours()
    comp_pattern_pool = _all_comp_patterns(mood, time_sig_str)
    section_motifs: dict[str, str] = {}
    section_contours: dict[str, str] = {}
    section_comp_pats: dict[str, str] = {}
    unique_letters = list(dict.fromkeys(section_letters))
    for li, letter in enumerate(unique_letters):
        if li == 0:
            if motif_pool:
                section_motifs[letter] = melody_motif.get("id", motif_pool[0]["id"])
            if contour_pool:
                section_contours[letter] = melody_contour.get("id", contour_pool[0]["id"])
            section_comp_pats[letter] = comp_pat.get("id", "")
        else:
            seed = s.take(f"form/section/{letter}", 4)
            if motif_pool:
                section_motifs[letter] = motif_pool[seed[0] % len(motif_pool)]["id"]
            if contour_pool:
                section_contours[letter] = contour_pool[seed[1] % len(contour_pool)]["id"]
            if comp_pattern_pool:
                section_comp_pats[letter] = comp_pattern_pool[seed[2] % len(comp_pattern_pool)]["id"]

    layers = (
        LayerSpec(name="drums", midi_channel=9, synth_id=f"drumkit/{drum_kit['id']}",
                  program=0, pattern_id=drum_pat.get("id", ""),
                  extra={
                      "kit": drum_kit["id"],
                      "pattern_low": drum_pat_low.get("id", ""),
                      "pattern_high": drum_pat_high.get("id", ""),
                      "fill_id": drum_fill_id,
                  }),
        LayerSpec(name="bass", midi_channel=0, synth_id=bass_synth["id"],
                  program=bass_program, pattern_id=bass_pat["id"],
                  extra={"octave_window": tuple(bass_synth.get("octave_window_midi", [28, 52]))}),
        LayerSpec(name="comp", midi_channel=1, synth_id=comp_synth["id"],
                  program=comp_program, pattern_id=comp_pat["id"],
                  extra={"role": comp_role["id"], "arp_shape_id": arp_shape["id"]}),
        LayerSpec(name="lead", midi_channel=2, synth_id="lead/placeholder",
                  program=lead_program, pattern_id=melody_motif.get("id", ""),
                  extra={
                      "motif_id": melody_motif.get("id", ""),
                      "contour_id": melody_contour.get("id", ""),
                      "scale_subset_id": melody_scale.get("id", ""),
                  }),
        LayerSpec(name="pad", midi_channel=3, synth_id="pad/aux_wash",
                  program=pad_program, pattern_id="",
                  extra={"role": "pad_wash"}),
        LayerSpec(name="counter", midi_channel=4, synth_id="counter/parallel_third",
                  program=counter_program, pattern_id=melody_motif.get("id", ""),
                  extra={
                      "motif_id": melody_motif.get("id", ""),
                      "contour_id": melody_contour.get("id", ""),
                      "scale_subset_id": melody_scale.get("id", ""),
                      "transpose_degrees": 2,    # parallel third (in scale degrees)
                  }),
        LayerSpec(name="drone", midi_channel=5, synth_id="drone/tonic_fifth",
                  program=89,                      # Pad 2 (warm)
                  pattern_id="",
                  extra={"enabled": mood in ("M0", "M1", "M10", "M12")}),
        LayerSpec(name="riser", midi_channel=6, synth_id="riser/reverse_cymbal",
                  program=119,                     # GM Reverse Cymbal
                  pattern_id="",
                  extra={}),
        LayerSpec(name="ear_candy", midi_channel=7, synth_id="ear_candy/bell",
                  # Mood-keyed bell-ish patch: 9 Glockenspiel, 11 Vibraphone,
                  # 14 Tubular Bells, 98 Crystal, 12 Marimba, 113 Tinkle Bell.
                  program=({"M0": 9, "M1": 11, "M2": 12, "M3": 11,
                            "M4": 12, "M5": 98, "M6": 9, "M7": 98,
                            "M8": 12, "M9": 113, "M10": 14,
                            "M11": 11, "M12": 9, "M13": 9, "M14": 80}
                           .get(mood, 9)),
                  pattern_id="",
                  extra={}),
    )

    provenance = Provenance(
        hash_hex=hash_bytes.hex(),
        mime_detected=mime,
        mime_family=family,
        mood=mood,
        libmagic_version=None,
        magic_mgc_sha=None,
        overrides=(),
    )

    return SongSpec(
        version=version,
        provenance=provenance,
        tempo_bpm=tempo,
        time_sig=(4, 4),
        swing="straight",
        key_root=key_root,
        mode=mode,
        form_id=form.get("name", progression["id"]),
        energy_curve_id=energy_curve.get("name", "arc"),
        activation_matrix_id="band_basic",
        groove_template_id=groove_id,
        bars=bars,
        layers=layers,
        bar_energies=bar_energies,
        section_motif_ids=section_motifs,
        section_contour_ids=section_contours,
        section_comp_pattern_ids=section_comp_pats,
        render=RenderHints(),
    )

## render/midi.py
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

# Per-mood gate overrides. Ambient (M0) uses flat-low curves whose energies
# hover around 0.30 — without lower gates the lead/pad/counter/ear-candy
# would never fire, leaving the soundhash an unmusical thump.
_MOOD_GATE_OVERRIDES = {
    "M0": {"drums": 0.10, "comp": 0.10, "lead": 0.18, "pad": 0.18,
           "counter": 0.30, "ear_candy": 0.22},
    "M10": {"counter": 0.55},
    # Lofi: open mid-range, less peak energy needed.
    "M11": {"counter": 0.45, "ear_candy": 0.40},
    # Chillout: lower thresholds so layers come in slowly.
    "M12": {"drums": 0.20, "lead": 0.30, "pad": 0.30, "counter": 0.45,
            "ear_candy": 0.40},
    # Simple = sparse on purpose. Drums and lead always; comp + pad
    # often silent; counter / ear-candy off entirely.
    "M13": {"drums": 0.15, "comp": 0.55, "lead": 0.15, "pad": 0.55,
            "counter": 0.95, "ear_candy": 0.95},
    # Gameboy: rigid, full-on grid. Layers ride hard once active.
    "M14": {"drums": 0.20, "lead": 0.20, "pad": 0.20, "counter": 0.60,
            "ear_candy": 0.50},
}
_PAD_ENERGY_CEILING = 0.85       # pad drops out at peak energy to keep mix open

# Per-mood lead octave (C5 default = 72; soft moods drop to C4 = 60 so the
# lead doesn't feel shrill and high-pitched).
_MOOD_LEAD_OCTAVE_MIDI = {
    "M0": 60, "M1": 60, "M3": 60, "M10": 60,
    "M11": 60, "M12": 60, "M13": 60,
    "M14": 84,                                   # gameboy: high (chiptune lead sits up there)
}


def _lead_octave(mood: str) -> int:
    return _MOOD_LEAD_OCTAVE_MIDI.get(mood, 72)


def _gate(spec, layer_name: str) -> float:
    overrides = _MOOD_GATE_OVERRIDES.get(spec.provenance.mood, {})
    return overrides.get(layer_name, _ENERGY_GATE.get(layer_name, 0.0))


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
    ec = _ear_candy_track(spec, ticks_per_bar)
    if ec is not None:
        mf.tracks.append(ec)

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
        if e < _gate(spec, "bass"):
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
        if e < _gate(spec, "bass"):
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
        if e < _gate(spec, "comp") or bar.drop_comp:
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
        if e < _gate(spec, "comp") or bar.drop_comp:
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
    base_octave_midi = _lead_octave(spec.provenance.mood)

    events: list[tuple[int, int, int, int]] = []
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        if e < _gate(spec, "counter"):
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


_EAR_CANDY_TABLE: list | None = None


def _ear_candy_table() -> list:
    """Lazily load and cache the ear_candy_table from aux_layers.json."""
    global _EAR_CANDY_TABLE
    if _EAR_CANDY_TABLE is None:
        try:
            data = tables.load("aux_layers")
            _EAR_CANDY_TABLE = data.get("ear_candy_table", {}).get("rows", []) or []
        except FileNotFoundError:
            _EAR_CANDY_TABLE = []
    return _EAR_CANDY_TABLE


def _ear_candy_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack | None:
    """Off-beat percussive stabs at high-energy bars.

    Each bar samples one row from the ear_candy_table via
    HKDF(aux/earcandy/main/<bar_idx>)[0] % len(rows). Positions are 16th-cell
    indices avoiding the downbeats (per the table's contract). Pitches walk
    the chord tones for melodic colour.
    """
    layer = next((l for l in spec.layers if l.name == "ear_candy"), None)
    if layer is None:
        return None
    rows = _ear_candy_table()
    if not rows:
        return None

    track = MidiTrack()
    track.append(MetaMessage("track_name", name="ear_candy", time=0))
    track.append(Message("program_change", channel=7,
                         program=_layer_program(spec, "ear_candy", default=9), time=0))

    import hashlib as _h, hmac as _hm
    prk = _hm.new(b"soundhash-v1",
                  bytes.fromhex(spec.provenance.hash_hex), _h.sha256).digest()

    cells_to_ticks = ticks_per_bar // 16
    events: list[tuple[int, int, int, int]] = []
    for bar in spec.bars:
        e = _bar_energy(spec, bar.index)
        ec_gate = _MOOD_GATE_OVERRIDES.get(spec.provenance.mood, {}).get("ear_candy", 0.50)
        if e < ec_gate:
            continue
        # Drop on fill bars so the fill speaks.
        next_bar = spec.bars[bar.index + 1] if bar.index + 1 < len(spec.bars) else None
        if next_bar is not None and next_bar.section_letter != bar.section_letter:
            continue
        info = f"soundhash/v1/aux/earcandy/main/{bar.index}".encode("ascii")
        out, t, c = b"", b"", 1
        while len(out) < 4:
            t = _hm.new(prk, t + info + bytes([c]), _h.sha256).digest()
            out += t
            c += 1
        row_idx = out[0] % len(rows)
        positions = rows[row_idx] or []
        bar_tick = bar.index * ticks_per_bar
        # Pitches: cycle chord tones in the C5 octave, picking a different
        # tone per stab for melodic interest.
        chord_tones = sorted({72 + ((bar.chord_root_pc + iv) % 12)
                              for iv in (bar.chord_pcs or (0, 4, 7))})
        for j, pos in enumerate(positions):
            if not 1 <= pos <= 15 or pos == 8:
                continue
            on_tick = bar_tick + pos * cells_to_ticks
            pitch = chord_tones[j % len(chord_tones)]
            vel = max(40, min(95, int(45 + 50 * (e - 0.5))))
            vel = max(1, min(127, vel + _vel_jitter(spec, "ear_candy", 4)))
            dur = max(60, cells_to_ticks - 20)
            events.append((on_tick, 0, pitch, vel))
            events.append((on_tick + dur, 1, pitch, 64))

    if not events:
        return None
    events.sort(key=lambda ev: (ev[0], ev[1], ev[2]))
    cursor = 0
    for abs_tick, kind, pitch, vel in events:
        delta = max(0, abs_tick - cursor)
        msg_type = "note_on" if kind == 0 else "note_off"
        track.append(Message(msg_type, channel=7, note=pitch, velocity=vel, time=delta))
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
        if e < _gate(spec, "pad") or e > _PAD_ENERGY_CEILING or bar.drop_pad:
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
        if e < _gate(spec, "drums") or bar.drop_drums:
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
        if e < _gate(spec, "lead") or bar.drop_lead:
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

## render/fx.py
"""Per-mood post-render FX chains (reverb / delay / chorus / EQ).

Applied after LUFS normalisation but before the final peak limiter so the
limiter still owns the true-peak ceiling. Determinism is best-effort:
pedalboard's algorithms are not bit-identical across builds, but with
pinned `pedalboard==0.9.x` the output is stable on a given host.

The chains are intentionally subtle. A soundhash is meant to be musical,
not a synthwave demo reel — heavy modulation would obscure distinguishability.
"""
from __future__ import annotations

import io
import wave

import numpy as np


# Per-mood FX recipe. Each entry is a list of (effect_name, kwargs) pairs.
# Effect names map to pedalboard plugin classes.
_MOOD_FX: dict[str, list[tuple[str, dict]]] = {
    # M0 Ambient — long plate reverb + light chorus + low-shelf cut.
    "M0":  [("Reverb",       {"room_size": 0.85, "damping": 0.4, "wet_level": 0.40, "dry_level": 0.70, "width": 1.0}),
            ("Chorus",       {"rate_hz": 0.6, "depth": 0.35, "centre_delay_ms": 12, "feedback": 0.05, "mix": 0.25}),
            ("LowShelfFilter", {"cutoff_frequency_hz": 110, "gain_db": -1.0, "q": 0.7})],
    # M1 Ballad — medium hall, warm low end.
    "M1":  [("Reverb",       {"room_size": 0.70, "damping": 0.5, "wet_level": 0.28, "dry_level": 0.78, "width": 0.9}),
            ("LowShelfFilter", {"cutoff_frequency_hz": 200, "gain_db": +1.5, "q": 0.7}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 8000, "gain_db": +1.0, "q": 0.7})],
    # M2 Hip-hop / Boom-bap — short room + tape-style high cut + light analog warmth.
    "M2":  [("Reverb",       {"room_size": 0.30, "damping": 0.7, "wet_level": 0.18, "dry_level": 0.85, "width": 0.7}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": -2.0, "q": 0.7}),
            ("Distortion",   {"drive_db": 4.0})],
    # M3 Downtempo — wide chorus + slow delay + warm.
    "M3":  [("Chorus",       {"rate_hz": 0.7, "depth": 0.45, "centre_delay_ms": 18, "feedback": 0.10, "mix": 0.30}),
            ("Delay",        {"delay_seconds": 0.375, "feedback": 0.18, "mix": 0.18}),
            ("Reverb",       {"room_size": 0.55, "damping": 0.55, "wet_level": 0.22, "dry_level": 0.80, "width": 0.95})],
    # M4 Latin — light room, slight high-shelf brightness.
    "M4":  [("Reverb",       {"room_size": 0.35, "damping": 0.4, "wet_level": 0.18, "dry_level": 0.85, "width": 0.85}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": +1.5, "q": 0.7})],
    # M5 Synthwave — short plate + ducked dotted-eighth delay + chorus on synths.
    "M5":  [("Chorus",       {"rate_hz": 1.1, "depth": 0.25, "centre_delay_ms": 8, "feedback": 0.05, "mix": 0.20}),
            ("Delay",        {"delay_seconds": 0.214, "feedback": 0.30, "mix": 0.16}),
            ("Reverb",       {"room_size": 0.45, "damping": 0.4, "wet_level": 0.24, "dry_level": 0.82, "width": 1.0})],
    # M6 House — tight ambience + sidechain-feel low pump (use compressor).
    "M6":  [("Reverb",       {"room_size": 0.30, "damping": 0.5, "wet_level": 0.18, "dry_level": 0.85, "width": 0.9}),
            ("Compressor",   {"threshold_db": -16.0, "ratio": 3.0, "attack_ms": 8, "release_ms": 80})],
    # M7 Techno — tight, slightly dark, light delay.
    "M7":  [("Delay",        {"delay_seconds": 0.1875, "feedback": 0.18, "mix": 0.12}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 9000, "gain_db": -1.5, "q": 0.7}),
            ("Reverb",       {"room_size": 0.25, "damping": 0.6, "wet_level": 0.14, "dry_level": 0.88, "width": 0.85})],
    # M8 DnB — tight, snappy, no big space.
    "M8":  [("Compressor",   {"threshold_db": -14.0, "ratio": 2.5, "attack_ms": 5, "release_ms": 60}),
            ("Reverb",       {"room_size": 0.20, "damping": 0.6, "wet_level": 0.10, "dry_level": 0.92, "width": 0.85})],
    # M9 Glitch / IDM — phaser + ping-pong delay + small room.
    "M9":  [("Phaser",       {"rate_hz": 0.4, "depth": 0.40, "centre_frequency_hz": 1300, "feedback": 0.20, "mix": 0.30}),
            ("Delay",        {"delay_seconds": 0.143, "feedback": 0.25, "mix": 0.20}),
            ("Reverb",       {"room_size": 0.30, "damping": 0.4, "wet_level": 0.15, "dry_level": 0.88, "width": 1.0})],
    # M10 Cinematic — large hall, gentle high-shelf air.
    "M10": [("Reverb",       {"room_size": 0.90, "damping": 0.35, "wet_level": 0.45, "dry_level": 0.65, "width": 1.0}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 9000, "gain_db": +2.0, "q": 0.7}),
            ("LowShelfFilter", {"cutoff_frequency_hz": 90, "gain_db": +1.0, "q": 0.7})],
    # M11 Lofi — vinyl warmth: tape saturation, mid-room reverb, top-end roll-off, slow chorus wow-wobble.
    "M11": [("Distortion",   {"drive_db": 6.0}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 5500, "gain_db": -3.0, "q": 0.7}),
            ("Chorus",       {"rate_hz": 0.4, "depth": 0.30, "centre_delay_ms": 22, "feedback": 0.10, "mix": 0.25}),
            ("Reverb",       {"room_size": 0.40, "damping": 0.7, "wet_level": 0.22, "dry_level": 0.82, "width": 0.85})],
    # M12 Chillout — wide chorus, plate reverb, presence boost, dotted-eighth delay.
    "M12": [("Chorus",       {"rate_hz": 0.5, "depth": 0.40, "centre_delay_ms": 18, "feedback": 0.10, "mix": 0.30}),
            ("Delay",        {"delay_seconds": 0.450, "feedback": 0.20, "mix": 0.18}),
            ("Reverb",       {"room_size": 0.65, "damping": 0.5, "wet_level": 0.32, "dry_level": 0.75, "width": 0.95}),
            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": +1.0, "q": 0.7})],
    # M13 Simple — barely-there room reverb. Lets the silence breathe.
    "M13": [("Reverb",       {"room_size": 0.20, "damping": 0.5, "wet_level": 0.10, "dry_level": 0.92, "width": 0.85})],
    # M14 Gameboy — chiptune: light drive, bit-crush-ish high-shelf cut, no reverb (DMG had none).
    "M14": [("HighShelfFilter", {"cutoff_frequency_hz": 8000, "gain_db": -4.0, "q": 0.7}),
            ("Distortion",   {"drive_db": 2.0}),
            ("Reverb",       {"room_size": 0.10, "damping": 0.4, "wet_level": 0.04, "dry_level": 0.96, "width": 0.6})],
}


def apply_fx(samples: np.ndarray, sample_rate: int, mood: str) -> np.ndarray:
    """Apply the mood's FX chain + master bus. samples: (n, 2) float32 in [-1, 1].

    Chain order: mood-specific plugins → master bus (HPF + low-shelf cut +
    presence shelf). The master bus is mood-independent and corrects the
    GM-soundfont's tendency to dominate the low band.
    """
    try:
        from pedalboard import (
            Pedalboard, Reverb, Delay, Chorus, Phaser, Compressor, Distortion,
            LowShelfFilter, HighShelfFilter, HighpassFilter,
        )
    except ImportError:
        return samples

    cls_map = {
        "Reverb": Reverb, "Delay": Delay, "Chorus": Chorus, "Phaser": Phaser,
        "Compressor": Compressor, "Distortion": Distortion,
        "LowShelfFilter": LowShelfFilter, "HighShelfFilter": HighShelfFilter,
        "HighpassFilter": HighpassFilter,
    }
    plugins = []
    for name, kwargs in (_MOOD_FX.get(mood) or []):
        cls = cls_map.get(name)
        if cls is None:
            continue
        plugins.append(cls(**kwargs))

    # Master bus: applied to every mood. Tames sub rumble and lifts presence
    # so spectral balance moves toward the target 25/45/30 distribution.
    plugins.extend([
        HighpassFilter(cutoff_frequency_hz=40),
        LowShelfFilter(cutoff_frequency_hz=110, gain_db=-1.5, q=0.7),
        HighShelfFilter(cutoff_frequency_hz=4500, gain_db=+1.5, q=0.7),
    ])

    board = Pedalboard(plugins)
    return board(samples.astype(np.float32), sample_rate)

codex
1. `render/fx.py:84`  
Before: `apply_fx()` instantiates `pedalboard` plugins even though the file explicitly notes they are not bit-identical across builds.  
After: replace the pedalboard path with a pure-NumPy deterministic chain (`_delay`, `_tanh_drive`, `_one_pole_hp`, `_shelf`, `_stereo_width`) driven only by `samples`, `sample_rate`, and `mood`.  
Impact: removes the biggest same-input/different-bits risk while preserving mood-specific timbral contrast.

2. `decode.py:473`  
Before: `progression = _pick_progression(macro[7], mood, mode)` then `chord_entries = theory.resolve_progression(...)`; `macro[8]` is unused.  
After: use `macro[8]` to rotate the resolved progression before looping, e.g. `rot = macro[8] % len(chord_entries)` and `chord_entries = chord_entries[rot:] + chord_entries[:rot]`.  
Impact: adds a new audible harmonic axis from currently wasted entropy, so nearby hashes diverge much more even when they land on the same progression ID.

3. `decode.py:596`  
Before: `motif_pool = _all_motifs_for_time_sig(time_sig_str)` and `contour_pool = _all_contours()` ignore `mood_tags`, and B/C section picks can repeat A unchanged.  
After: filter motif/contour/comp-pattern pools by mood first, then for non-A sections choose from candidates excluding A’s ID and any already-used section IDs when alternatives exist.  
Impact: makes section changes hash-sensitive and style-coherent instead of often collapsing to the same melodic/rhythmic material.

4. `decode.py:590`  
Before: `counter_program` is selected from `macro[22]` and immediately overwritten by a second selection from `macro[23] ^ 0x55`, effectively coupling counter timbre to pad selection.  
After: keep `pad_program` on `macro[23]`, and drive `counter_program` from its own independent selector (`macro[22]` or `int.from_bytes(macro[22:24], "big")`) without overwrite.  
Impact: restores lost entropy and decouples two prominent upper-mid layers, increasing timbral distinguishability at zero reproducibility cost.

5. `render/midi.py:905`  
Before: `_lead_track()` hardcodes `base_octave_midi = 72` and computes `is_phrase_end` by looking past `next_bar`, so mood octave mapping is ignored and phrase-end bends often miss real section boundaries.  
After: set `base_octave_midi = _lead_octave(spec.provenance.mood)` and change phrase-end detection to `next_bar is None or next_bar.section_letter != bar.section_letter or next_bar.drop_lead`.  
Impact: makes lead register and phrase cadences audibly reflect the hash-derived structure, improving perceptual separation without introducing any nondeterminism.
2026-05-08T15:24:10.209897Z ERROR codex_core::session: failed to record rollout items: thread 019e082e-34ea-70d0-bfb6-d1fc65ec2363 not found
tokens used
33,290
1. `render/fx.py:84`  
Before: `apply_fx()` instantiates `pedalboard` plugins even though the file explicitly notes they are not bit-identical across builds.  
After: replace the pedalboard path with a pure-NumPy deterministic chain (`_delay`, `_tanh_drive`, `_one_pole_hp`, `_shelf`, `_stereo_width`) driven only by `samples`, `sample_rate`, and `mood`.  
Impact: removes the biggest same-input/different-bits risk while preserving mood-specific timbral contrast.

2. `decode.py:473`  
Before: `progression = _pick_progression(macro[7], mood, mode)` then `chord_entries = theory.resolve_progression(...)`; `macro[8]` is unused.  
After: use `macro[8]` to rotate the resolved progression before looping, e.g. `rot = macro[8] % len(chord_entries)` and `chord_entries = chord_entries[rot:] + chord_entries[:rot]`.  
Impact: adds a new audible harmonic axis from currently wasted entropy, so nearby hashes diverge much more even when they land on the same progression ID.

3. `decode.py:596`  
Before: `motif_pool = _all_motifs_for_time_sig(time_sig_str)` and `contour_pool = _all_contours()` ignore `mood_tags`, and B/C section picks can repeat A unchanged.  
After: filter motif/contour/comp-pattern pools by mood first, then for non-A sections choose from candidates excluding A’s ID and any already-used section IDs when alternatives exist.  
Impact: makes section changes hash-sensitive and style-coherent instead of often collapsing to the same melodic/rhythmic material.

4. `decode.py:590`  
Before: `counter_program` is selected from `macro[22]` and immediately overwritten by a second selection from `macro[23] ^ 0x55`, effectively coupling counter timbre to pad selection.  
After: keep `pad_program` on `macro[23]`, and drive `counter_program` from its own independent selector (`macro[22]` or `int.from_bytes(macro[22:24], "big")`) without overwrite.  
Impact: restores lost entropy and decouples two prominent upper-mid layers, increasing timbral distinguishability at zero reproducibility cost.

5. `render/midi.py:905`  
Before: `_lead_track()` hardcodes `base_octave_midi = 72` and computes `is_phrase_end` by looking past `next_bar`, so mood octave mapping is ignored and phrase-end bends often miss real section boundaries.  
After: set `base_octave_midi = _lead_octave(spec.provenance.mood)` and change phrase-end detection to `next_bar is None or next_bar.section_letter != bar.section_letter or next_bar.drop_lead`.  
Impact: makes lead register and phrase cadences audibly reflect the hash-derived structure, improving perceptual separation without introducing any nondeterminism.
