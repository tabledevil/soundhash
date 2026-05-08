OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/tabledevil/projects/soundhash/research/adv-review
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019e081e-b339-7cb0-83f3-a32eaaa61a89
--------
user
# SOUNDHASH IMPL CRITIQUE

## Project summary
Soundhash deterministically maps a SHA-256 digest to a 30-second piece of music. An HKDF stream over the digest derives every musical decision (key, tempo, structure, instruments, motifs). A 9-layer MIDI rendering pipeline produces parts, which are synthesized to audio (FluidSynth/SoundFont), processed via a pedalboard FX chain, then loudness-normalized to a LUFS target with a peak limiter. A quality scorer evaluates the result. Goals: bit-identical determinism across runs, distinguishability across inputs, robustness.

## Critique brief
Find correctness bugs, determinism leaks (uncontrolled randomness, dict ordering, float nondeterminism, threading), performance issues, dead code, missing edge cases (empty inputs, zero-length notes, clipping, NaN/inf), code smells, and error-handling gaps. Cite file:line. Score deal-breakers vs nice-to-haves. Be terse and concrete.

## === decode.py ===
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

## === render/midi.py ===
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

## === render/audio.py ===
"""MIDI → WAV via the fluidsynth CLI, with length cap + cosine fades.

Pinned flags per DESIGN.md §7 determinism contract: cpu-cores=1, no internal
reverb/chorus. Output is normalised to ≤30 s with a 200 ms cosine fade-out
(and a 5 ms fade-in to kill the start-click).

Stage-2 will move to in-process pyfluidsynth + ship a CC0 SoundFont.
"""
from __future__ import annotations

import io
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


# Output length + loudness contract (DESIGN.md §3, dim 14):
MAX_SECONDS = 30.0
FADE_IN_MS = 5
FADE_OUT_MS = 200
TARGET_LUFS = -16.0
PEAK_CEILING_DBFS = -1.5     # peak ceiling (linear-domain limiter, not true-peak)
MAX_GAIN_DB = 24.0           # safety cap on the loudness-correction gain


# Default soundfont — bundled with `brew install fluidsynth` on macOS.
# 307 KB Vintage-Dreams-Waves; sounds appropriate for M5 synthwave-ish output
# but is far from full GM. Override via SOUNDHASH_SOUNDFONT env var.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_SF2 = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "assets", "v1", "sf2"))
_DEFAULT_SF2_CANDIDATES = [
    os.path.join(_REPO_SF2, "MS-Basic.sf3"),
    "/usr/local/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    # last resort: brew's tiny pad-only synth font (no drums)
    "/opt/homebrew/Cellar/fluid-synth/2.5.4/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2",
]


def _find_soundfont() -> str:
    sf = os.environ.get("SOUNDHASH_SOUNDFONT")
    if sf and os.path.isfile(sf):
        return sf
    for p in _DEFAULT_SF2_CANDIDATES:
        if os.path.isfile(p):
            return p
    raise RuntimeError(
        "No SoundFont found. Set SOUNDHASH_SOUNDFONT=/path/to.sf2 "
        "or install fluid-synth via Homebrew."
    )


def render_wav(midi_bytes: bytes, sample_rate: int = 44100,
               provenance: dict | None = None,
               apply_fx: bool = True) -> bytes:
    """Run fluidsynth on the MIDI, return the WAV bytes (with optional metadata)."""
    if shutil.which("fluidsynth") is None:
        raise RuntimeError("fluidsynth CLI not found on PATH")
    sf2 = _find_soundfont()

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        mid_path = td / "in.mid"
        wav_path = td / "out.wav"
        mid_path.write_bytes(midi_bytes)
        cmd = [
            "fluidsynth", "-ni",
            "-F", str(wav_path),
            "-r", str(sample_rate),
            "-o", "synth.cpu-cores=1",
            "-o", "synth.reverb.active=no",
            "-o", "synth.chorus.active=no",
            sf2,
            str(mid_path),
        ]
        # Inherit a controlled locale for cross-platform-stable text parsing.
        env = {**os.environ, "LC_ALL": "C"}
        proc = subprocess.run(cmd, capture_output=True, env=env, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"fluidsynth exited {proc.returncode}: {proc.stderr.decode(errors='replace')[:400]}"
            )
        wav = _postprocess_wav(wav_path.read_bytes(),
                               mood=(provenance or {}).get("mood") if apply_fx else None)
        if provenance:
            wav = _embed_wav_provenance(wav, provenance)
        return wav


def _embed_wav_provenance(wav_bytes: bytes, prov: dict) -> bytes:
    """Insert a RIFF LIST/INFO chunk carrying provenance after `fmt `.

    Sub-chunks (4-byte IDs) used:
        ISFT  software identifier
        ICMT  free-form comment with full provenance
        ICOP  copyright / license
    """
    if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        return wav_bytes  # not a WAV; bail.

    # Build INFO sub-chunks.
    def _info(tag: bytes, text: str) -> bytes:
        data = text.encode("utf-8") + b"\x00"
        if len(data) % 2:
            data += b"\x00"
        return tag + struct.pack("<I", len(data)) + data

    sw = "soundhash/v1"
    comment = (
        f"soundhash/v1 sha={prov.get('hash_hex','?')[:64]} "
        f"mood={prov.get('mood','?')} mode={prov.get('mode','?')} "
        f"key={prov.get('key_root','?')} tempo={prov.get('tempo_bpm','?')} "
        f"form={prov.get('form_id','?')} bars={prov.get('bars','?')} "
        f"groove={prov.get('groove_template_id','?')} "
        f"curve={prov.get('energy_curve_id','?')}"
    )
    info_payload = b"INFO" + _info(b"ISFT", sw) + _info(b"ICMT", comment) \
                            + _info(b"ICOP", "deterministic — see DESIGN.md")
    list_chunk = b"LIST" + struct.pack("<I", len(info_payload)) + info_payload

    # Walk existing chunks and insert LIST right after `fmt `.
    out = bytearray()
    out += wav_bytes[:12]                      # RIFF<size>WAVE; size patched at end
    pos = 12
    inserted = False
    while pos + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[pos:pos + 4]
        chunk_size = struct.unpack("<I", wav_bytes[pos + 4:pos + 8])[0]
        chunk_total = 8 + chunk_size + (chunk_size & 1)
        out += wav_bytes[pos:pos + chunk_total]
        pos += chunk_total
        if not inserted and chunk_id == b"fmt ":
            out += list_chunk
            inserted = True

    if not inserted:
        # No fmt chunk found — append before EOF as safe fallback.
        out += list_chunk

    # Patch RIFF size (= total length of out minus 8 bytes for "RIFF"+size).
    new_size = len(out) - 8
    out[4:8] = struct.pack("<I", new_size)
    return bytes(out)


def _postprocess_wav(wav_bytes: bytes, mood: str | None = None) -> bytes:
    """Cap length, apply fades, LUFS-norm, mood FX chain, peak-limit."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as r:
        n_channels = r.getnchannels()
        sample_width = r.getsampwidth()
        rate = r.getframerate()
        n_frames = r.getnframes()
        raw = r.readframes(n_frames)
    if sample_width != 2:
        return wav_bytes  # only handle 16-bit for now

    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    samples = samples.reshape(-1, n_channels)

    # 1. Length cap.
    max_frames = int(MAX_SECONDS * rate)
    if len(samples) > max_frames:
        samples = samples[:max_frames]
    n = len(samples)

    # 2. LUFS normalisation (only if there's enough audio for the gating window).
    samples = _normalise_loudness(samples, rate)

    # 3. Per-mood FX chain (reverb / delay / chorus / EQ via pedalboard).
    if mood:
        try:
            from .fx import apply_fx
            samples = apply_fx(samples, rate, mood)
        except Exception:
            pass

    # 4. Cosine fades.
    fi = max(1, int(FADE_IN_MS * rate / 1000))
    fo = max(1, int(FADE_OUT_MS * rate / 1000))
    if n >= fi:
        ramp = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, fi, dtype=np.float32)))
        samples[:fi] *= ramp[:, None]
    if n >= fo:
        ramp = 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, fo, dtype=np.float32)))
        samples[-fo:] *= ramp[:, None]

    # 5. Peak limiter at PEAK_CEILING_DBFS (linear-domain; deterministic).
    ceiling = 10 ** (PEAK_CEILING_DBFS / 20.0)
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak > ceiling:
        samples *= ceiling / peak

    # Quantise back to int16.
    out_int = np.clip(samples * 32768.0, -32768, 32767).astype("<i2")

    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(n_channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(out_int.tobytes())
    return out.getvalue()


def _normalise_loudness(samples: np.ndarray, rate: int) -> np.ndarray:
    """Apply gain so integrated LUFS approaches TARGET_LUFS. Deterministic.

    pyloudnorm uses ITU-R BS.1770 with a 400 ms window — needs ≥0.4 s of audio.
    """
    try:
        import pyloudnorm
    except ImportError:
        return samples
    if len(samples) < int(0.5 * rate):
        return samples
    meter = pyloudnorm.Meter(rate)        # default block_size=0.4 s
    try:
        loudness = meter.integrated_loudness(samples)
    except Exception:
        return samples
    if not np.isfinite(loudness):
        return samples
    gain_db = TARGET_LUFS - loudness
    gain_db = max(-MAX_GAIN_DB, min(MAX_GAIN_DB, gain_db))
    gain = 10 ** (gain_db / 20.0)
    return samples * gain

## === render/fx.py ===
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
I’m reviewing the implementation as a code review pass focused on determinism, correctness, and edge-case handling. First step is locating the actual files in the repo so I can cite exact `file:line` references instead of estimating from the pasted snippets.
exec
/bin/zsh -lc pwd in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
/Users/tabledevil/projects/soundhash/research/adv-review

exec
/bin/zsh -lc 'rg --files' in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
impl-codex.md
impl-gemini.md

codex
The workspace only has the review docs, not the source tree, so I’m pulling line references from the pasted implementation blocks in those docs. I’m locating the exact sections now and checking for determinism leaks and hard correctness faults before writing findings.
exec
/bin/zsh -lc 'rg -n "''^## === decode'"\\.py ===|"'^## === render/midi'"\\.py ===|"'^## === render/audio'"\\.py ===|"'^## === render/fx'"\\.py ===|"'^def hash_to_spec|''^def render_midi|''^def render_wav|''^def apply_fx|_VEL_JITTER_CACHE|counter_program =|base_octave_midi = 72|_lead_octave'"\\(|groupby|_pick_drum_pattern\\(|_pick_form\\(|_BEATS_PER_BAR|target_bars|pyloudnorm|except Exception|TemporaryDirectory|section_motif_ids|note_on\"" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
impl-codex.md:21:## === decode.py ===
impl-codex.md:172:def _pick_form(byte: int, n_bars: int) -> dict:
impl-codex.md:339:def _pick_drum_pattern(byte: int, kit_id: str, time_sig: str) -> dict:
impl-codex.md:495:def hash_to_spec(
impl-codex.md:537:    target_bars = _bars_from_layout(form, default_n=8, cap=max_bars_for_30s)
impl-codex.md:539:    # Loop the progression to fill target_bars.
impl-codex.md:541:    while len(looped) < target_bars:
impl-codex.md:543:    looped = looped[:target_bars]
impl-codex.md:546:    section_letters = _expand_form_layout(form, target_bars)
impl-codex.md:547:    if target_bars > 1:
impl-codex.md:549:            _sample_energy_curve(energy_curve, (i + 0.5) / target_bars)
impl-codex.md:550:            for i in range(target_bars)
impl-codex.md:640:    counter_program = _pick_gm_program(macro[22], mood, "counter", default=73)
impl-codex.md:641:    counter_program = _pick_gm_program(macro[23] ^ 0x55, mood, "counter", default=73)
impl-codex.md:746:        section_motif_ids=section_motifs,
impl-codex.md:752:## === render/midi.py ===
impl-codex.md:809:def _lead_octave(mood: str) -> int:
impl-codex.md:827:_VEL_JITTER_CACHE: dict[tuple[str, str], "_VelJitter"] = {}
impl-codex.md:848:    j = _VEL_JITTER_CACHE.get(key)
impl-codex.md:862:        _VEL_JITTER_CACHE[key] = j
impl-codex.md:891:def render_midi(spec: SongSpec) -> bytes:
impl-codex.md:893:    _VEL_JITTER_CACHE.clear()
impl-codex.md:899:    _BEATS_PER_BAR = beats_per_bar  # captured by helpers below
impl-codex.md:1048:            msg_type = "note_on" if kind == 0 else "note_off"
impl-codex.md:1072:            track.append(Message("note_on", channel=0, note=root,
impl-codex.md:1194:        msg_type = "note_on" if kind == 0 else "note_off"
impl-codex.md:1212:            comp.append(Message("note_on", channel=1, note=p, velocity=vel, time=delta))
impl-codex.md:1250:    base_octave_midi = _lead_octave(spec.provenance.mood)
impl-codex.md:1261:        motif_id_b = spec.section_motif_ids.get(bar.section_letter, motif_id)
impl-codex.md:1297:        msg_type = "note_on" if kind == 0 else "note_off"
impl-codex.md:1383:        msg_type = "note_on" if kind == 0 else "note_off"
impl-codex.md:1442:            msg_type = "note_on" if kind == 0 else "note_off"
impl-codex.md:1468:    track.append(Message("note_on", channel=5, note=tonic, velocity=vel, time=0))
impl-codex.md:1469:    track.append(Message("note_on", channel=5, note=fifth, velocity=vel, time=0))
impl-codex.md:1513:        msg_type = "note_on" if kind == 0 else "note_off"
impl-codex.md:1659:        msg_type = "note_on" if kind == 0 else "note_off"
impl-codex.md:1702:    base_octave_midi = 72                       # C5
impl-codex.md:1726:        motif_id_b = spec.section_motif_ids.get(bar.section_letter, motif_id)
impl-codex.md:1790:    # 0 note_on, 1 note_off, 2 control_change, 3 pitchwheel.
impl-codex.md:1809:            msg_type = "note_on" if kind == 0 else "note_off"
impl-codex.md:1837:## === render/audio.py ===
impl-codex.md:1896:def render_wav(midi_bytes: bytes, sample_rate: int = 44100,
impl-codex.md:1904:    with tempfile.TemporaryDirectory() as td:
impl-codex.md:2017:        except Exception:
impl-codex.md:2051:    pyloudnorm uses ITU-R BS.1770 with a 400 ms window — needs ≥0.4 s of audio.
impl-codex.md:2054:        import pyloudnorm
impl-codex.md:2059:    meter = pyloudnorm.Meter(rate)        # default block_size=0.4 s
impl-codex.md:2062:    except Exception:
impl-codex.md:2071:## === render/fx.py ===
impl-codex.md:2153:def apply_fx(samples: np.ndarray, sample_rate: int, mood: str) -> np.ndarray:

exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '1,1400p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
     1	OpenAI Codex v0.125.0 (research preview)
     2	--------
     3	workdir: /Users/tabledevil/projects/soundhash/research/adv-review
     4	model: gpt-5.4
     5	provider: openai
     6	approval: never
     7	sandbox: read-only
     8	reasoning effort: high
     9	reasoning summaries: none
    10	session id: 019e081e-b339-7cb0-83f3-a32eaaa61a89
    11	--------
    12	user
    13	# SOUNDHASH IMPL CRITIQUE
    14	
    15	## Project summary
    16	Soundhash deterministically maps a SHA-256 digest to a 30-second piece of music. An HKDF stream over the digest derives every musical decision (key, tempo, structure, instruments, motifs). A 9-layer MIDI rendering pipeline produces parts, which are synthesized to audio (FluidSynth/SoundFont), processed via a pedalboard FX chain, then loudness-normalized to a LUFS target with a peak limiter. A quality scorer evaluates the result. Goals: bit-identical determinism across runs, distinguishability across inputs, robustness.
    17	
    18	## Critique brief
    19	Find correctness bugs, determinism leaks (uncontrolled randomness, dict ordering, float nondeterminism, threading), performance issues, dead code, missing edge cases (empty inputs, zero-length notes, clipping, NaN/inf), code smells, and error-handling gaps. Cite file:line. Score deal-breakers vs nice-to-haves. Be terse and concrete.
    20	
    21	## === decode.py ===
    22	"""Decode a SHA-256 (and optional MIME) into a SongSpec.
    23	
    24	Pure function. No I/O after table preload, no system clock, no system random.
    25	All entropy comes from HKDF-Expand of the input hash.
    26	
    27	Current scope: produces a fully populated macro SongSpec — mood, tempo, key,
    28	mode, progression resolved to per-bar chord roots and PC sets — for any input.
    29	The melody/bass/drum note generation lives downstream and is not yet wired.
    30	"""
    31	from __future__ import annotations
    32	
    33	import hashlib
    34	import hmac
    35	from typing import Optional
    36	
    37	from . import tables, theory
    38	from .spec import (
    39	    Bar,
    40	    LayerSpec,
    41	    Provenance,
    42	    RenderHints,
    43	    SongSpec,
    44	)
    45	
    46	
    47	# ---------------------------------------------------------------------------
    48	# HKDF (RFC 5869) over SHA-256
    49	# ---------------------------------------------------------------------------
    50	
    51	_SALT = b"soundhash-v1"
    52	
    53	
    54	def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    55	    return hmac.new(salt, ikm, hashlib.sha256).digest()
    56	
    57	
    58	def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    59	    out, t, counter = b"", b"", 1
    60	    while len(out) < length:
    61	        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
    62	        out += t
    63	        counter += 1
    64	    return out[:length]
    65	
    66	
    67	class HashStream:
    68	    """Domain-separated entropy stream derived from the input hash."""
    69	
    70	    __slots__ = ("_prk", "_version")
    71	
    72	    def __init__(self, prk: bytes, version: str = "v1"):
    73	        self._prk = prk
    74	        self._version = version
    75	
    76	    def take(self, label: str, n: int) -> bytes:
    77	        info = f"soundhash/{self._version}/{label}".encode("ascii")
    78	        return _hkdf_expand(self._prk, info, n)
    79	
    80	    def pick(self, label: str, table):
    81	        b = self.take(label, 1)[0]
    82	        return table[b % len(table)]
    83	
    84	
    85	# ---------------------------------------------------------------------------
    86	# Selection helpers — each one applies the constraint propagation principle
    87	# ---------------------------------------------------------------------------
    88	
    89	
    90	def _pick_mood(macro: bytes, mime_family: str | None) -> str:
    91	    """Byte 0 selects mood within a MIME-family-filtered candidate list.
    92	
    93	    With mime=None we expose all 11 moods.
    94	    """
    95	    f2m = tables.load("family_to_moods")
    96	    if mime_family and mime_family in f2m["mapping"]:
    97	        candidates = f2m["mapping"][mime_family]["candidates"]
    98	    else:
    99	        candidates = list(f2m["moods"].keys())
   100	    return candidates[macro[0] % len(candidates)]
   101	
   102	
   103	def _pick_tempo(byte: int, mood: str) -> float:
   104	    pools = tables.load("tempo_pools")["pools"]
   105	    pool = pools[mood]["bpm"]
   106	    base = pool[(byte & 0x07) % len(pool)]
   107	    # 5 high bits drive a ±0.5% nudge to retain entropy without changing perceived BPM.
   108	    nudge = ((byte >> 3) - 16) / 16.0 * 0.005      # in [-0.005, +0.00469]
   109	    return round(base * (1.0 + nudge), 3)
   110	
   111	
   112	def _pick_mode(byte: int, mood: str) -> str:
   113	    moods = tables.load("moods")["moods"]
   114	    mood_modes = moods[mood]["modes"]
   115	    return mood_modes[byte % len(mood_modes)]
   116	
   117	
   118	_MOOD_GROOVE_POOL: dict[str, tuple[str, ...]] = {
   119	    "M0":  ("ambient_drift", "neo_soul", "straight_4_4"),
   120	    "M1":  ("straight_4_4", "neo_soul", "gospel_12_8"),
   121	    "M2":  ("boom_bap_60", "dilla_feel", "mpc60_swing"),
   122	    "M3":  ("neo_soul", "mpc60_swing", "dilla_feel", "straight_4_4"),
   123	    "M4":  ("latin_clave_pocket", "dembow_pocket", "mpc60_swing"),
   124	    "M5":  ("synthwave_tight", "straight_4_4"),
   125	    "M6":  ("house_pocket", "amapiano_pocket", "straight_4_4"),
   126	    "M7":  ("techno_push", "straight_4_4"),
   127	    "M8":  ("dnb_amen_lean", "straight_4_4"),
   128	    "M9":  ("trap_triplet_hat", "straight_4_4"),
   129	    "M10": ("straight_4_4", "gospel_12_8", "ambient_drift"),
   130	    "M11": ("dilla_feel", "boom_bap_60", "mpc60_swing", "neo_soul"),    # lofi swing
   131	    "M12": ("ambient_drift", "neo_soul", "straight_4_4"),               # chillout flow
   132	    "M13": ("straight_4_4",),                                            # simple = on the grid
   133	    "M14": ("straight_4_4",),                                            # gameboy = rigid
   134	}
   135	
   136	
   137	def _pick_groove_template(byte: int, mood: str) -> str:
   138	    pool = _MOOD_GROOVE_POOL.get(mood, ("straight_4_4",))
   139	    try:
   140	        templates = tables.load("groove_templates")["templates"]
   141	    except FileNotFoundError:
   142	        return pool[0]
   143	    available = {t["id"] for t in templates}
   144	    pool = tuple(p for p in pool if p in available) or ("straight_4_4",)
   145	    return pool[byte % len(pool)]
   146	
   147	
   148	def _expand_form_layout(form: dict, n_bars: int) -> list[str]:
   149	    """Turn `[[letter, bar_count_or_'N'], ...]` into a per-bar section-letter list of length n_bars."""
   150	    layout = form.get("layout") or [["A", "N"]]
   151	    fixed = [(letter, count) for letter, count in layout if count != "N"]
   152	    fixed_total = sum(c for _, c in fixed)
   153	    n_remaining = max(0, n_bars - fixed_total)
   154	    n_natural = sum(1 for _, c in layout if c == "N") or 1
   155	    natural_share, extra = divmod(n_remaining, n_natural)
   156	
   157	    out: list[str] = []
   158	    for letter, count in layout:
   159	        if count == "N":
   160	            share = natural_share + (1 if extra > 0 else 0)
   161	            extra = max(0, extra - 1)
   162	            out.extend([letter] * share)
   163	        else:
   164	            out.extend([letter] * count)
   165	    # Truncate / pad to exactly n_bars.
   166	    out = out[:n_bars]
   167	    while len(out) < n_bars:
   168	        out.append(out[-1] if out else "A")
   169	    return out
   170	
   171	
   172	def _pick_form(byte: int, n_bars: int) -> dict:
   173	    forms = tables.load("forms")["forms"]
   174	    eligible = [f for f in forms if f.get("min_bars", 1) <= n_bars <= f.get("max_bars", 99)]
   175	    if not eligible:
   176	        eligible = forms
   177	    eligible.sort(key=lambda f: f.get("id", 0))
   178	    return eligible[byte % len(eligible)]
   179	
   180	
   181	# Per-mood form-id preferences. Empty intersection with the 30-s-fit set
   182	# falls back to the unfiltered list. IDs reference forms.json:
   183	#   0 through_composed,  1 A_Aprime,  2 AB_simple,  3 AAB,  4 ABA,
   184	#   5 ABAB,  6 intro_A_fill_A_out,  7 A_build_drop_A,  8 theme_var,
   185	#   9 call_response,  10 intro_A,  11 A_outro,  12 AB_with_fill,
   186	#   13 AABA,  14 ABCA,  15 breakdown_form,  16 riser_drop_loop,
   187	#   17 ostinato_layer,  18 two_arches,  19 late_drop,  20 plateau_fall,
   188	#   21 pyramid,  22 medley,  23 pulse_only.
   189	_MOOD_FORM_PREF: dict[str, tuple[int, ...]] = {
   190	    "M0":  (0, 1, 8, 17, 23),                # ambient: through-composed / ostinato / pulse
   191	    "M1":  (1, 4, 6, 11, 13, 18),            # ballad: A_Aprime, ABA, AABA, two_arches
   192	    "M2":  (2, 5, 8, 13, 14),                # hip-hop: AB / ABAB / theme_var / AABA / ABCA
   193	    "M3":  (0, 1, 8, 17, 18),                # downtempo
   194	    "M4":  (5, 13, 14, 8),                   # latin: ABAB / AABA / ABCA / theme_var
   195	    "M5":  (5, 7, 13, 14, 19),               # synthwave: ABAB / build_drop / late_drop
   196	    "M6":  (5, 14, 15, 19, 16),              # house
   197	    "M7":  (15, 16, 19, 21, 23),             # techno
   198	    "M8":  (5, 7, 16, 19),                   # dnb
   199	    "M9":  (8, 18, 21, 22),                  # glitch
   200	    "M10": (4, 6, 13, 14, 18, 20),           # cinematic
   201	    "M11": (1, 4, 8, 17, 13),                # lofi: A_Aprime / ABA / theme_var / ostinato_layer / AABA
   202	    "M12": (0, 1, 4, 8, 17, 18, 23),         # chillout: through_composed / A_Aprime / ABA / theme_var
   203	    "M13": (1, 4, 13, 23),                   # simple: A_Aprime / ABA / AABA / pulse_only
   204	    "M14": (5, 13, 14, 4, 21),               # gameboy: ABAB / AABA / ABCA / ABA / pyramid
   205	}
   206	
   207	
   208	def _pick_form_unconstrained(byte: int, max_bars: int, mood: str = "") -> dict:
   209	    """Pick a form whose min_bars fits within max_bars (the 30-second cap),
   210	    biased toward mood-preferred forms when possible."""
   211	    forms = tables.load("forms")["forms"]
   212	    fits = [f for f in forms if f.get("min_bars", 1) <= max_bars]
   213	    if not fits:
   214	        fits = forms
   215	    pref = set(_MOOD_FORM_PREF.get(mood, ()))
   216	    eligible = [f for f in fits if f.get("id") in pref] if pref else []
   217	    if not eligible:
   218	        eligible = fits
   219	    eligible.sort(key=lambda f: f.get("id", 0))
   220	    return eligible[byte % len(eligible)]
   221	
   222	
   223	def _bars_from_layout(form: dict, default_n: int = 8, cap: int = 99) -> int:
   224	    """Sum fixed counts in form.layout; allocate `default_n` to any 'N' filler.
   225	
   226	    Result clamped to [form.min_bars, form.max_bars] then to `cap`.
   227	    """
   228	    layout = form.get("layout") or [["A", "N"]]
   229	    fixed = sum(c for _, c in layout if c != "N")
   230	    n_natural = sum(1 for _, c in layout if c == "N")
   231	    total = fixed + n_natural * max(2, default_n // max(1, len(layout)))
   232	    if not fixed and not n_natural:
   233	        total = default_n
   234	    lo = form.get("min_bars", 1)
   235	    hi = min(cap, form.get("max_bars", cap))
   236	    return max(lo, min(hi, total))
   237	
   238	
   239	# Per-mood curve-id preferences (intersected with form.allowed_curves).
   240	# IDs: 0 flat_low, 1 flat_mid, 2 flat_high, 3 rise, 4 fall, 5 arc, 6 U,
   241	# 7 two_arches, 8 late_drop, 9 early_drop, 10 plateau_fall,
   242	# 11 slow_build_cliff, 12 sawtooth_2, 13 terraces, 14 breath, 15 reverse_arc.
   243	_MOOD_CURVE_PREF: dict[str, tuple[int, ...]] = {
   244	    "M0":  (0, 1, 6, 14, 15),
   245	    "M1":  (5, 7, 14, 10),
   246	    "M2":  (1, 13, 7),
   247	    "M3":  (5, 14, 13),
   248	    "M4":  (5, 13, 7, 3),
   249	    "M5":  (3, 5, 8, 11),
   250	    "M6":  (3, 13, 8, 11, 5),
   251	    "M7":  (3, 11, 8, 13),
   252	    "M8":  (8, 11, 7),
   253	    "M9":  (12, 7, 13, 4),
   254	    "M10": (5, 11, 7, 14, 15),
   255	    "M11": (1, 14, 5, 13, 6),                # lofi — flat-mid w/ breath, gentle arc, U
   256	    "M12": (1, 14, 6, 5, 15),                # chillout — flat, breath, U
   257	    "M13": (0, 1, 14, 6),                    # simple — flat low/mid, breath
   258	    "M14": (3, 5, 7, 13),                    # gameboy — rise, arc, two_arches, terraces
   259	}
   260	
   261	
   262	def _pick_energy_curve(byte: int, form: dict, mood: str = "") -> dict:
   263	    curves = tables.load("energy_curves")["curves"]
   264	    allowed_ids = set(form.get("allowed_curves") or [c["id"] for c in curves])
   265	    pref_ids = set(_MOOD_CURVE_PREF.get(mood, ())) & allowed_ids
   266	    chosen_ids = pref_ids if pref_ids else allowed_ids
   267	    eligible = [c for c in curves if c.get("id") in chosen_ids] or curves
   268	    eligible.sort(key=lambda c: c.get("id", 0))
   269	    return eligible[byte % len(eligible)]
   270	
   271	
   272	def _sample_energy_curve(curve: dict, fraction: float) -> float:
   273	    """Linear interpolation over the curve's `points: [[fraction, energy], ...]`."""
   274	    pts = curve.get("points") or [[0.0, 0.5], [1.0, 0.5]]
   275	    if fraction <= pts[0][0]:
   276	        return float(pts[0][1])
   277	    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
   278	        if fraction <= x1:
   279	            if x1 == x0:
   280	                return float(y1)
   281	            t = (fraction - x0) / (x1 - x0)
   282	            return float(y0 + (y1 - y0) * t)
   283	    return float(pts[-1][1])
   284	
   285	
   286	def _pick_progression(byte: int, mood: str, mode: str) -> dict:
   287	    """Filter progression bank by mood-tag ∩ mode, then index."""
   288	    progs = tables.load("harmony/progressions")["progressions"]
   289	    eligible = [p for p in progs if mood in p.get("mood_tags", []) and p["mode"] == mode]
   290	    if not eligible:
   291	        # Fallback: relax mode constraint, keep mood.
   292	        eligible = [p for p in progs if mood in p.get("mood_tags", [])]
   293	    if not eligible:
   294	        # Last-resort fallback: any ionian progression.
   295	        eligible = [p for p in progs if p["mode"] == "ionian"]
   296	    eligible.sort(key=lambda p: p["id"])               # stable order
   297	    return eligible[byte % len(eligible)]
   298	
   299	
   300	def _filter_by_mood(items, mood):
   301	    return [x for x in items if mood in x.get("mood_tags", [])]
   302	
   303	
   304	def _pick_drum_kit(byte: int, mood: str) -> dict:
   305	    kits = tables.load("drums/drumkits")["kits"]
   306	    eligible = _filter_by_mood(kits, mood) or kits
   307	    eligible.sort(key=lambda k: k["id"])
   308	    return eligible[byte % len(eligible)]
   309	
   310	
   311	# ---------------------------------------------------------------------------
   312	# Mood-keyed GM program palettes (placeholder until synth_pool.json is wired).
   313	# Each tuple gives candidates for that role; byte % len picks one.
   314	# ---------------------------------------------------------------------------
   315	
   316	# (gm_program, name) — stick to widely-supported GM patches so MS Basic / GeneralUser cover them.
   317	_GM_PALETTE: dict[str, dict[str, tuple[int, ...]]] = {
   318	    "M0":  {"bass": (32,),               "comp": (88, 89, 91),       "lead": (54, 75, 73),   "pad": (88, 89, 94),    "counter": (52, 73, 91)},   # Ambient
   319	    "M1":  {"bass": (32, 33),            "comp": (0, 4, 24),         "lead": (73, 71, 56),   "pad": (89, 91, 95),    "counter": (40, 41, 73)},
   320	    "M2":  {"bass": (33, 34, 36),        "comp": (4, 5, 11),         "lead": (80, 81, 28),   "pad": (89, 95, 91),    "counter": (4, 5, 11)},
   321	    "M3":  {"bass": (33, 36),            "comp": (4, 5, 88, 89),     "lead": (80, 73, 78),   "pad": (89, 91, 94),    "counter": (52, 91, 73)},
   322	    "M4":  {"bass": (32, 35),            "comp": (24, 25, 32),       "lead": (56, 11, 24),   "pad": (89, 91, 94),    "counter": (60, 56, 73)},
   323	    "M5":  {"bass": (38, 39, 33),        "comp": (81, 89, 80),       "lead": (81, 80, 84),   "pad": (90, 89, 94),    "counter": (82, 81, 84)},
   324	    "M6":  {"bass": (38, 39, 36),        "comp": (16, 17, 81),       "lead": (80, 81, 53),   "pad": (90, 89, 95),    "counter": (54, 80, 81)},
   325	    "M7":  {"bass": (38, 39),            "comp": (81, 89, 90),       "lead": (80, 81, 87),   "pad": (90, 94, 89),    "counter": (87, 80, 81)},
   326	    "M8":  {"bass": (38, 39, 87),        "comp": (89, 88, 91),       "lead": (81, 80, 87),   "pad": (89, 91, 94),    "counter": (54, 81, 91)},
   327	    "M9":  {"bass": (38, 39, 87),        "comp": (90, 91, 102),      "lead": (88, 81, 102),  "pad": (95, 91, 94),    "counter": (102, 88, 91)},
   328	    "M10": {"bass": (32, 43, 44),        "comp": (48, 49, 50, 89),   "lead": (60, 73, 71),   "pad": (49, 51, 94),    "counter": (49, 73, 71)},  # strings/choir
   329	}
   330	
   331	
   332	def _pick_gm_program(byte: int, mood: str, layer: str, default: int) -> int:
   333	    pal = _GM_PALETTE.get(mood, {}).get(layer)
   334	    if not pal:
   335	        return default
   336	    return pal[byte % len(pal)]
   337	
   338	
   339	def _pick_drum_pattern(byte: int, kit_id: str, time_sig: str) -> dict:
   340	    pats = tables.load(f"drums/patterns/{kit_id}")["patterns"]
   341	    eligible = [p for p in pats if time_sig in p.get("valid_time_sigs", [time_sig])]
   342	    if not eligible:
   343	        eligible = pats
   344	    eligible.sort(key=lambda p: p["id"])
   345	    return eligible[byte % len(eligible)]
   346	
   347	
   348	def _pick_drum_fill(byte: int, kit_id: str) -> str:
   349	    try:
   350	        fills = tables.load(f"drums/fills/{kit_id}")["fills"]
   351	    except FileNotFoundError:
   352	        return ""
   353	    if not fills:
   354	        return ""
   355	    # Prefer escalating fills (target_density > current_density) for a build-up feel.
   356	    eligible = [f for f in fills
   357	                if f.get("target_density", 0) >= f.get("current_density", 0)] or fills
   358	    eligible.sort(key=lambda f: f["id"])
   359	    return eligible[byte % len(eligible)]["id"]
   360	
   361	
   362	def _pick_drum_pattern_pair(byte: int, kit_id: str, time_sig: str) -> tuple[dict, dict]:
   363	    """Pick a (low-density, high-density) pair so render can pick per-bar by energy."""
   364	    try:
   365	        pats = tables.load(f"drums/patterns/{kit_id}")["patterns"]
   366	    except FileNotFoundError:
   367	        return ({}, {})
   368	    eligible = [p for p in pats if time_sig in p.get("valid_time_sigs", [time_sig])] or pats
   369	    eligible.sort(key=lambda p: (p.get("density", 2), p["id"]))
   370	    low = [p for p in eligible if p.get("density", 2) <= 2] or eligible
   371	    high = [p for p in eligible if p.get("density", 2) >= 3] or eligible
   372	    pat_low = low[(byte & 0x0F) % len(low)]
   373	    pat_high = high[(byte >> 4) % len(high)]
   374	    return pat_low, pat_high
   375	
   376	
   377	def _pick_bass_pattern(byte: int, mood: str, time_sig: str) -> dict:
   378	    pats = tables.load("bass/bass_patterns")["patterns"]
   379	    eligible = [p for p in _filter_by_mood(pats, mood) if time_sig in p.get("time_sigs", [])]
   380	    if not eligible:
   381	        eligible = [p for p in pats if time_sig in p.get("time_sigs", [])] or pats
   382	    eligible.sort(key=lambda p: p["id"])
   383	    return eligible[byte % len(eligible)]
   384	
   385	
   386	def _pick_bass_synth(byte: int, mood: str, pattern_id: str) -> dict:
   387	    synths = tables.load("bass/bass_synths")["synths"]
   388	    eligible = [s for s in _filter_by_mood(synths, mood)
   389	                if not s.get("pattern_compat") or pattern_id in s["pattern_compat"]]
   390	    if not eligible:
   391	        eligible = _filter_by_mood(synths, mood) or synths
   392	    eligible.sort(key=lambda s: s["id"])
   393	    return eligible[byte % len(eligible)]
   394	
   395	
   396	def _pick_comp_role(byte: int, mood: str) -> dict:
   397	    roles = tables.load("comp/comp_roles")["roles"]
   398	    eligible = _filter_by_mood(roles, mood) or roles
   399	    eligible.sort(key=lambda r: r["id"])
   400	    return eligible[byte % len(eligible)]
   401	
   402	
   403	def _pick_comp_synth(byte: int, mood: str, role_id: str) -> dict:
   404	    synths = tables.load("comp/comp_synths")["synths"]
   405	    eligible = [s for s in _filter_by_mood(synths, mood) if role_id in s.get("compatible_roles", [])]
   406	    if not eligible:
   407	        eligible = _filter_by_mood(synths, mood) or synths
   408	    eligible.sort(key=lambda s: s["id"])
   409	    return eligible[byte % len(eligible)]
   410	
   411	
   412	def _pick_arp_shape(byte: int, mood: str) -> dict:
   413	    data = tables.load("comp/arp_shapes")
   414	    shapes = data.get("shapes", data.get("arp_shapes", data))
   415	    if isinstance(shapes, dict):
   416	        shapes = list(shapes.values())
   417	    eligible = [sh for sh in shapes if mood in sh.get("mood_tags", [])] or shapes
   418	    eligible = sorted(eligible, key=lambda sh: sh.get("id", ""))
   419	    return eligible[byte % len(eligible)]
   420	
   421	
   422	def _pick_comp_pattern(byte: int, mood: str, time_sig: str) -> dict:
   423	    pats = tables.load("comp/chord_rhythm_patterns")["patterns"]
   424	    eligible = [p for p in _filter_by_mood(pats, mood) if time_sig in p.get("time_sigs", [])]
   425	    if not eligible:
   426	        eligible = [p for p in pats if time_sig in p.get("time_sigs", [])] or pats
   427	    eligible.sort(key=lambda p: p["id"])
   428	    return eligible[byte % len(eligible)]
   429	
   430	
   431	def _all_comp_patterns(mood: str, time_sig: str) -> list[dict]:
   432	    pats = tables.load("comp/chord_rhythm_patterns")["patterns"]
   433	    eligible = [p for p in pats if mood in p.get("mood_tags", []) and time_sig in p.get("time_sigs", [])]
   434	    if not eligible:
   435	        eligible = [p for p in pats if time_sig in p.get("time_sigs", [])] or pats
   436	    return sorted(eligible, key=lambda p: p["id"])
   437	
   438	
   439	def _all_motifs_for_time_sig(time_sig: str) -> list[dict]:
   440	    data = tables.load("melody/motif_rhythms")
   441	    pools = data.get("pools", data)
   442	    pool = pools.get(time_sig) or pools.get(time_sig.replace("/", "_")) or next(iter(pools.values()), {})
   443	    if isinstance(pool, dict):
   444	        flat = []
   445	        for v in pool.values():
   446	            if isinstance(v, list):
   447	                flat.extend(v)
   448	        return sorted(flat, key=lambda x: x.get("id", ""))
   449	    return sorted(list(pool), key=lambda x: x.get("id", ""))
   450	
   451	
   452	def _all_contours() -> list[dict]:
   453	    data = tables.load("melody/contours")
   454	    contours = data.get("contours", data)
   455	    if isinstance(contours, dict):
   456	        contours = list(contours.values())
   457	    return sorted(contours, key=lambda x: x.get("id", ""))
   458	
   459	
   460	def _pick_melody_motif(byte: int, time_sig: str, mood: str = "") -> dict:
   461	    pool = _all_motifs_for_time_sig(time_sig)
   462	    eligible = [m for m in pool if mood in m.get("mood_tags", [])] if mood else []
   463	    if not eligible:
   464	        eligible = pool
   465	    return eligible[byte % len(eligible)]
   466	
   467	
   468	def _pick_contour(byte: int, mood: str = "") -> dict:
   469	    pool = _all_contours()
   470	    eligible = [c for c in pool if mood in c.get("mood_tags", [])] if mood else []
   471	    if not eligible:
   472	        eligible = pool
   473	    return eligible[byte % len(eligible)]
   474	
   475	
   476	def _pick_scale_subset(byte: int, mode: str) -> dict:
   477	    data = tables.load("melody/scale_subsets")
   478	    subsets = data.get("subsets", data.get("scale_subsets", data))
   479	    if isinstance(subsets, dict):
   480	        subsets = list(subsets.values())
   481	    eligible = [s for s in subsets if mode in s.get("applies_to_modes", [mode])] or subsets
   482	    eligible = sorted(eligible, key=lambda x: x.get("id", str(x)))
   483	    return eligible[byte % len(eligible)]
   484	
   485	
   486	# ---------------------------------------------------------------------------
   487	# Public entry point
   488	# ---------------------------------------------------------------------------
   489	
   490	
   491	class UnsupportedVersionError(ValueError):
   492	    pass
   493	
   494	
   495	def hash_to_spec(
   496	    hash_bytes: bytes,
   497	    mime: Optional[str] = None,
   498	    version: str = "v1",
   499	    mood_override: Optional[str] = None,
   500	) -> SongSpec:
   501	    """Pure: same (hash, mime, version) → same SongSpec.
   502	
   503	    Walks the byte budget from CONTEXT/§4 of DESIGN.md top-down, filtering each
   504	    table by all prior choices. See test_decode_invariants.py for invariants.
   505	    """
   506	    if len(hash_bytes) != 32:
   507	        raise ValueError(f"expected 32-byte SHA-256, got {len(hash_bytes)}")
   508	    if version != "v1":
   509	        raise UnsupportedVersionError(version)
   510	
   511	    prk = _hkdf_extract(_SALT, hash_bytes)
   512	    s = HashStream(prk, version)
   513	    macro = s.take("macro", 32)
   514	
   515	    # MIME → family pre-filter.
   516	    from .mime import family_for_mime
   517	    family = family_for_mime(mime)
   518	
   519	    # Macro decisions.
   520	    if mood_override and mood_override.startswith("M") and mood_override[1:].isdigit():
   521	        mood = mood_override
   522	    else:
   523	        mood = _pick_mood(macro, family)
   524	    tempo = _pick_tempo(macro[2], mood)
   525	    key_root = macro[3] % 12
   526	    mode = _pick_mode(macro[4], mood)
   527	    progression = _pick_progression(macro[7], mood, mode)
   528	
   529	    # Resolve progression to per-bar chord entries.
   530	    chord_entries = theory.resolve_progression(progression, key_root, mode)
   531	
   532	    # Form first — its layout determines bar count, then we cap by what fits
   533	    # in 30 seconds at the chosen tempo (leave 2 s for reverb tail).
   534	    beats_per_bar = 4
   535	    max_bars_for_30s = max(2, int(28.0 * tempo / (60.0 * beats_per_bar)))
   536	    form = _pick_form_unconstrained(macro[6], max_bars_for_30s, mood)
   537	    target_bars = _bars_from_layout(form, default_n=8, cap=max_bars_for_30s)
   538	
   539	    # Loop the progression to fill target_bars.
   540	    looped = []
   541	    while len(looped) < target_bars:
   542	        looped.extend(chord_entries)
   543	    looped = looped[:target_bars]
   544	    energy_curve = _pick_energy_curve(macro[24], form, mood)
   545	    groove_id = _pick_groove_template(macro[5], mood)
   546	    section_letters = _expand_form_layout(form, target_bars)
   547	    if target_bars > 1:
   548	        bar_energies = tuple(
   549	            _sample_energy_curve(energy_curve, (i + 0.5) / target_bars)
   550	            for i in range(target_bars)
   551	        )
   552	    else:
   553	        bar_energies = (_sample_energy_curve(energy_curve, 0.5),)
   554	
   555	    bars = []
   556	    for i, e in enumerate(looped):
   557	        # Per-bar mutation seeds from HKDF.
   558	        mel_seed = s.take(f"perbar/melody/{i}", 4)
   559	        bass_seed = s.take(f"perbar/bass/{i}", 2)
   560	        mel_op = mel_seed[0] % 8
   561	        bass_op = bass_seed[0] % 8
   562	        # Bar 0 is always identity so the hook + groove land cleanly first.
   563	        if i == 0:
   564	            transpose, invert = 0, False
   565	            octave_shift, skip_last, ghost_first = 0, False, False
   566	        else:
   567	            transpose = {2: +1, 3: -1, 4: +2, 5: -2}.get(mel_op, 0)
   568	            invert = (mel_op == 6)
   569	            octave_shift = {2: +12, 3: -12}.get(bass_op, 0)
   570	            skip_last = (bass_op == 4)
   571	            ghost_first = (bass_op == 5)
   572	        comp_seed = s.take(f"perbar/comp/{i}", 2)
   573	        if i == 0:
   574	            comp_drop_last, comp_vel_pull = False, 0
   575	        else:
   576	            comp_drop_last = (comp_seed[0] % 8 == 0)              # ~12.5% of bars drop last hit
   577	            comp_vel_pull = (comp_seed[1] % 11) - 5                # -5..+5 velocity pull
   578	
   579	        # Per-bar layer dropout seed. Soft moods (M0/M11/M12/M13) silence
   580	        # individual layers occasionally so the mix breathes — every 4-8
   581	        # bars some layer rests for a bar.
   582	        drop_seed = s.take(f"perbar/aux/{i}", 4)
   583	        soft_mood = mood in ("M0", "M11", "M12", "M13")
   584	        if i == 0:
   585	            drop_drums = drop_lead = drop_comp = drop_pad = False
   586	        elif soft_mood:
   587	            # Each layer has a 1-in-6 to 1-in-4 chance of resting this bar.
   588	            drop_drums = (drop_seed[0] % 6 == 0)
   589	            drop_lead  = (drop_seed[1] % 5 == 0)
   590	            drop_comp  = (drop_seed[2] % 6 == 0)
   591	            drop_pad   = (drop_seed[3] % 7 == 0)
   592	        else:
   593	            # On other moods only the lead occasionally rests (1-in-12 bars).
   594	            drop_drums = drop_comp = drop_pad = False
   595	            drop_lead = (drop_seed[1] % 12 == 0)
   596	        bars.append(Bar(
   597	            index=i,
   598	            chord=f"{theory.name_for_pc(e['root_pc'])}{e['quality']}",
   599	            chord_root_pc=e["root_pc"],
   600	            chord_root_midi=e["root_midi"],
   601	            chord_pcs=tuple(e["chord_pcs"]),
   602	            chord_quality=e["quality"],
   603	            section_letter=section_letters[i] if i < len(section_letters) else "A",
   604	            melody_transpose=transpose,
   605	            melody_invert=invert,
   606	            bass_octave_shift=octave_shift,
   607	            bass_skip_last=skip_last,
   608	            bass_ghost_first=ghost_first,
   609	            comp_drop_last=comp_drop_last,
   610	            comp_vel_pull=comp_vel_pull,
   611	            drop_drums=drop_drums,
   612	            drop_lead=drop_lead,
   613	            drop_comp=drop_comp,
   614	            drop_pad=drop_pad,
   615	        ))
   616	    bars = tuple(bars)
   617	
   618	    # Per-layer picks (constraint propagation continues).
   619	    time_sig_str = "4/4"
   620	    drum_kit = _pick_drum_kit(macro[9], mood)
   621	    drum_pat_low, drum_pat_high = _pick_drum_pattern_pair(macro[10], drum_kit["id"], time_sig_str)
   622	    drum_pat = drum_pat_low or drum_pat_high or {}
   623	    drum_fill_id = _pick_drum_fill(macro[11], drum_kit["id"])
   624	    bass_pat = _pick_bass_pattern(macro[13], mood, time_sig_str)
   625	    bass_synth = _pick_bass_synth(macro[14], mood, bass_pat["id"])
   626	    comp_role = _pick_comp_role(macro[15], mood)
   627	    comp_synth = _pick_comp_synth(macro[16], mood, comp_role["id"])
   628	    comp_pat = _pick_comp_pattern(macro[17], mood, time_sig_str)
   629	    arp_shape = _pick_arp_shape(macro[17], mood)
   630	    melody_motif = _pick_melody_motif(macro[19], time_sig_str, mood)
   631	    melody_contour = _pick_contour(macro[20], mood)
   632	    melody_scale = _pick_scale_subset(macro[18], mode)
   633	
   634	    # Prefer the picked synth's gm_program (more specific than the mood palette).
   635	    bass_program = (bass_synth.get("gm_program")
   636	                    or _pick_gm_program(macro[14], mood, "bass", default=33))
   637	    comp_program = _pick_gm_program(macro[16], mood, "comp", default=4)
   638	    lead_program = _pick_gm_program(macro[21], mood, "lead", default=80)
   639	    pad_program  = _pick_gm_program(macro[23], mood, "pad",  default=89)
   640	    counter_program = _pick_gm_program(macro[22], mood, "counter", default=73)
   641	    counter_program = _pick_gm_program(macro[23] ^ 0x55, mood, "counter", default=73)
   642	
   643	    # Per-section motif & contour overrides — introduces real variation between
   644	    # form sections (A/B/C). Falls back to the macro melody picks for section A.
   645	    motif_pool = _all_motifs_for_time_sig(time_sig_str)
   646	    contour_pool = _all_contours()
   647	    comp_pattern_pool = _all_comp_patterns(mood, time_sig_str)
   648	    section_motifs: dict[str, str] = {}
   649	    section_contours: dict[str, str] = {}
   650	    section_comp_pats: dict[str, str] = {}
   651	    unique_letters = list(dict.fromkeys(section_letters))
   652	    for li, letter in enumerate(unique_letters):
   653	        if li == 0:
   654	            if motif_pool:
   655	                section_motifs[letter] = melody_motif.get("id", motif_pool[0]["id"])
   656	            if contour_pool:
   657	                section_contours[letter] = melody_contour.get("id", contour_pool[0]["id"])
   658	            section_comp_pats[letter] = comp_pat.get("id", "")
   659	        else:
   660	            seed = s.take(f"form/section/{letter}", 4)
   661	            if motif_pool:
   662	                section_motifs[letter] = motif_pool[seed[0] % len(motif_pool)]["id"]
   663	            if contour_pool:
   664	                section_contours[letter] = contour_pool[seed[1] % len(contour_pool)]["id"]
   665	            if comp_pattern_pool:
   666	                section_comp_pats[letter] = comp_pattern_pool[seed[2] % len(comp_pattern_pool)]["id"]
   667	
   668	    layers = (
   669	        LayerSpec(name="drums", midi_channel=9, synth_id=f"drumkit/{drum_kit['id']}",
   670	                  program=0, pattern_id=drum_pat.get("id", ""),
   671	                  extra={
   672	                      "kit": drum_kit["id"],
   673	                      "pattern_low": drum_pat_low.get("id", ""),
   674	                      "pattern_high": drum_pat_high.get("id", ""),
   675	                      "fill_id": drum_fill_id,
   676	                  }),
   677	        LayerSpec(name="bass", midi_channel=0, synth_id=bass_synth["id"],
   678	                  program=bass_program, pattern_id=bass_pat["id"],
   679	                  extra={"octave_window": tuple(bass_synth.get("octave_window_midi", [28, 52]))}),
   680	        LayerSpec(name="comp", midi_channel=1, synth_id=comp_synth["id"],
   681	                  program=comp_program, pattern_id=comp_pat["id"],
   682	                  extra={"role": comp_role["id"], "arp_shape_id": arp_shape["id"]}),
   683	        LayerSpec(name="lead", midi_channel=2, synth_id="lead/placeholder",
   684	                  program=lead_program, pattern_id=melody_motif.get("id", ""),
   685	                  extra={
   686	                      "motif_id": melody_motif.get("id", ""),
   687	                      "contour_id": melody_contour.get("id", ""),
   688	                      "scale_subset_id": melody_scale.get("id", ""),
   689	                  }),
   690	        LayerSpec(name="pad", midi_channel=3, synth_id="pad/aux_wash",
   691	                  program=pad_program, pattern_id="",
   692	                  extra={"role": "pad_wash"}),
   693	        LayerSpec(name="counter", midi_channel=4, synth_id="counter/parallel_third",
   694	                  program=counter_program, pattern_id=melody_motif.get("id", ""),
   695	                  extra={
   696	                      "motif_id": melody_motif.get("id", ""),
   697	                      "contour_id": melody_contour.get("id", ""),
   698	                      "scale_subset_id": melody_scale.get("id", ""),
   699	                      "transpose_degrees": 2,    # parallel third (in scale degrees)
   700	                  }),
   701	        LayerSpec(name="drone", midi_channel=5, synth_id="drone/tonic_fifth",
   702	                  program=89,                      # Pad 2 (warm)
   703	                  pattern_id="",
   704	                  extra={"enabled": mood in ("M0", "M1", "M10", "M12")}),
   705	        LayerSpec(name="riser", midi_channel=6, synth_id="riser/reverse_cymbal",
   706	                  program=119,                     # GM Reverse Cymbal
   707	                  pattern_id="",
   708	                  extra={}),
   709	        LayerSpec(name="ear_candy", midi_channel=7, synth_id="ear_candy/bell",
   710	                  # Mood-keyed bell-ish patch: 9 Glockenspiel, 11 Vibraphone,
   711	                  # 14 Tubular Bells, 98 Crystal, 12 Marimba, 113 Tinkle Bell.
   712	                  program=({"M0": 9, "M1": 11, "M2": 12, "M3": 11,
   713	                            "M4": 12, "M5": 98, "M6": 9, "M7": 98,
   714	                            "M8": 12, "M9": 113, "M10": 14,
   715	                            "M11": 11, "M12": 9, "M13": 9, "M14": 80}
   716	                           .get(mood, 9)),
   717	                  pattern_id="",
   718	                  extra={}),
   719	    )
   720	
   721	    provenance = Provenance(
   722	        hash_hex=hash_bytes.hex(),
   723	        mime_detected=mime,
   724	        mime_family=family,
   725	        mood=mood,
   726	        libmagic_version=None,
   727	        magic_mgc_sha=None,
   728	        overrides=(),
   729	    )
   730	
   731	    return SongSpec(
   732	        version=version,
   733	        provenance=provenance,
   734	        tempo_bpm=tempo,
   735	        time_sig=(4, 4),
   736	        swing="straight",
   737	        key_root=key_root,
   738	        mode=mode,
   739	        form_id=form.get("name", progression["id"]),
   740	        energy_curve_id=energy_curve.get("name", "arc"),
   741	        activation_matrix_id="band_basic",
   742	        groove_template_id=groove_id,
   743	        bars=bars,
   744	        layers=layers,
   745	        bar_energies=bar_energies,
   746	        section_motif_ids=section_motifs,
   747	        section_contour_ids=section_contours,
   748	        section_comp_pattern_ids=section_comp_pats,
   749	        render=RenderHints(),
   750	    )
   751	
   752	## === render/midi.py ===
   753	"""SongSpec → standard MIDI file (Type 1, PPQ 480).
   754	
   755	Dumb consumer. No theory decisions; just plays whatever the SongSpec says.
   756	Looks up the picked drum pattern, motif, contour, and scale subset by ID
   757	in the static tables — but never makes a creative choice.
   758	
   759	Output is byte-stable: same SongSpec → same .mid bytes.
   760	"""
   761	from __future__ import annotations
   762	
   763	import io
   764	
   765	from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo
   766	
   767	from .. import tables, theory
   768	from ..spec import SongSpec
   769	
   770	
   771	PPQ = 480
   772	
   773	# Per-layer energy thresholds — below these the layer is silent in that bar.
   774	# Bass is the harmonic floor and plays whenever the song plays.
   775	_ENERGY_GATE = {"drums": 0.30, "comp": 0.20, "lead": 0.40, "bass": 0.0,
   776	                "pad": 0.40, "counter": 0.65}
   777	
   778	# Per-mood gate overrides. Ambient (M0) uses flat-low curves whose energies
   779	# hover around 0.30 — without lower gates the lead/pad/counter/ear-candy
   780	# would never fire, leaving the soundhash an unmusical thump.
   781	_MOOD_GATE_OVERRIDES = {
   782	    "M0": {"drums": 0.10, "comp": 0.10, "lead": 0.18, "pad": 0.18,
   783	           "counter": 0.30, "ear_candy": 0.22},
   784	    "M10": {"counter": 0.55},
   785	    # Lofi: open mid-range, less peak energy needed.
   786	    "M11": {"counter": 0.45, "ear_candy": 0.40},
   787	    # Chillout: lower thresholds so layers come in slowly.
   788	    "M12": {"drums": 0.20, "lead": 0.30, "pad": 0.30, "counter": 0.45,
   789	            "ear_candy": 0.40},
   790	    # Simple = sparse on purpose. Drums and lead always; comp + pad
   791	    # often silent; counter / ear-candy off entirely.
   792	    "M13": {"drums": 0.15, "comp": 0.55, "lead": 0.15, "pad": 0.55,
   793	            "counter": 0.95, "ear_candy": 0.95},
   794	    # Gameboy: rigid, full-on grid. Layers ride hard once active.
   795	    "M14": {"drums": 0.20, "lead": 0.20, "pad": 0.20, "counter": 0.60,
   796	            "ear_candy": 0.50},
   797	}
   798	_PAD_ENERGY_CEILING = 0.85       # pad drops out at peak energy to keep mix open
   799	
   800	# Per-mood lead octave (C5 default = 72; soft moods drop to C4 = 60 so the
   801	# lead doesn't feel shrill and high-pitched).
   802	_MOOD_LEAD_OCTAVE_MIDI = {
   803	    "M0": 60, "M1": 60, "M3": 60, "M10": 60,
   804	    "M11": 60, "M12": 60, "M13": 60,
   805	    "M14": 84,                                   # gameboy: high (chiptune lead sits up there)
   806	}
   807	
   808	
   809	def _lead_octave(mood: str) -> int:
   810	    return _MOOD_LEAD_OCTAVE_MIDI.get(mood, 72)
   811	
   812	
   813	def _gate(spec, layer_name: str) -> float:
   814	    overrides = _MOOD_GATE_OVERRIDES.get(spec.provenance.mood, {})
   815	    return overrides.get(layer_name, _ENERGY_GATE.get(layer_name, 0.0))
   816	
   817	
   818	def _bar_energy(spec, bar_index: int) -> float:
   819	    if spec.bar_energies and bar_index < len(spec.bar_energies):
   820	        return spec.bar_energies[bar_index]
   821	    return 1.0
   822	
   823	
   824	# Deterministic per-layer velocity-jitter stream (derived from spec.provenance.hash_hex
   825	# via HKDF). Cached on first use. Stream is consumed in event-emit order; render
   826	# is deterministic because event ordering is fixed (sorted by abs_tick).
   827	_VEL_JITTER_CACHE: dict[tuple[str, str], "_VelJitter"] = {}
   828	
   829	
   830	class _VelJitter:
   831	    __slots__ = ("_stream", "_pos")
   832	
   833	    def __init__(self, stream: bytes):
   834	        self._stream = stream
   835	        self._pos = 0
   836	
   837	    def next_offset(self, range_pm: int = 5) -> int:
   838	        if not self._stream:
   839	            return 0
   840	        b = self._stream[self._pos % len(self._stream)]
   841	        self._pos += 1
   842	        # Map byte 0..255 → -range..+range, signed.
   843	        return int((b / 255.0) * (2 * range_pm + 1)) - range_pm
   844	
   845	
   846	def _vel_jitter(spec, layer_name: str, range_pm: int = 5) -> int:
   847	    key = (spec.provenance.hash_hex, layer_name)
   848	    j = _VEL_JITTER_CACHE.get(key)
   849	    if j is None:
   850	        # Derive 256 bytes from HKDF for this layer's jitter stream.
   851	        import hashlib as _h, hmac as _hm
   852	        prk = _hm.new(b"soundhash-v1",
   853	                      bytes.fromhex(spec.provenance.hash_hex),
   854	                      _h.sha256).digest()
   855	        info = f"soundhash/v1/expression/velocity/L{layer_name}".encode("ascii")
   856	        out, t, c = b"", b"", 1
   857	        while len(out) < 256:
   858	            t = _hm.new(prk, t + info + bytes([c]), _h.sha256).digest()
   859	            out += t
   860	            c += 1
   861	        j = _VelJitter(out[:256])
   862	        _VEL_JITTER_CACHE[key] = j
   863	    return j.next_offset(range_pm)
   864	
   865	
   866	_GROOVE_CACHE: dict[str, dict] = {}
   867	
   868	
   869	def _groove_template(spec) -> dict:
   870	    """Return the picked groove template, cached. Empty dict means 'no offsets'."""
   871	    gid = getattr(spec, "groove_template_id", "straight_4_4")
   872	    if gid in _GROOVE_CACHE:
   873	        return _GROOVE_CACHE[gid]
   874	    try:
   875	        templates = tables.load("groove_templates")["templates"]
   876	        tpl = next((t for t in templates if t["id"] == gid), {})
   877	    except FileNotFoundError:
   878	        tpl = {}
   879	    _GROOVE_CACHE[gid] = tpl
   880	    return tpl
   881	
   882	
   883	def _groove_offset(spec, role: str, step: int) -> int:
   884	    """Return PPQ-480 tick offset for role at grid step. 0 if no template / null."""
   885	    offsets = (_groove_template(spec).get("offsets") or {}).get(role)
   886	    if not offsets:
   887	        return 0
   888	    return int(offsets[step % len(offsets)])
   889	
   890	
   891	def render_midi(spec: SongSpec) -> bytes:
   892	    # Reset stateful caches so render is idempotent within a process.
   893	    _VEL_JITTER_CACHE.clear()
   894	    mf = MidiFile(ticks_per_beat=PPQ, type=1)
   895	
   896	    num, den_pow2 = spec.time_sig
   897	    beats_per_bar = num
   898	    ticks_per_bar = PPQ * beats_per_bar
   899	    _BEATS_PER_BAR = beats_per_bar  # captured by helpers below
   900	
   901	    # ---- meta ------------------------------------------------------------
   902	    meta = MidiTrack()
   903	    meta.append(MetaMessage("track_name", name="meta", time=0))
   904	    meta.append(MetaMessage("set_tempo", tempo=bpm2tempo(spec.tempo_bpm), time=0))
   905	    meta.append(MetaMessage("time_signature", numerator=num,
   906	                            denominator=den_pow2, time=0))
   907	    meta.append(MetaMessage("marker",
   908	                            text=f"soundhash/v1 {spec.provenance.hash_hex[:16]} "
   909	                                 f"{spec.provenance.mood} {spec.mode}",
   910	                            time=0))
   911	    mf.tracks.append(meta)
   912	
   913	    mf.tracks.append(_bass_track(spec, ticks_per_bar))
   914	    mf.tracks.append(_comp_track(spec, ticks_per_bar))
   915	    drum = _drum_track(spec, ticks_per_bar)
   916	    if drum is not None:
   917	        mf.tracks.append(drum)
   918	    lead = _lead_track(spec, ticks_per_bar)
   919	    if lead is not None:
   920	        mf.tracks.append(lead)
   921	    pad = _pad_track(spec, ticks_per_bar)
   922	    if pad is not None:
   923	        mf.tracks.append(pad)
   924	    counter = _counter_track(spec, ticks_per_bar)
   925	    if counter is not None:
   926	        mf.tracks.append(counter)
   927	    drone = _drone_track(spec, ticks_per_bar)
   928	    if drone is not None:
   929	        mf.tracks.append(drone)
   930	    riser = _riser_track(spec, ticks_per_bar)
   931	    if riser is not None:
   932	        mf.tracks.append(riser)
   933	    ec = _ear_candy_track(spec, ticks_per_bar)
   934	    if ec is not None:
   935	        mf.tracks.append(ec)
   936	
   937	    buf = io.BytesIO()
   938	    mf.save(file=buf)
   939	    return buf.getvalue()
   940	
   941	
   942	# ---------------------------------------------------------------------------
   943	# Per-track builders
   944	# ---------------------------------------------------------------------------
   945	
   946	
   947	def _bass_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack:
   948	    bass = MidiTrack()
   949	    bass.append(MetaMessage("track_name", name="bass", time=0))
   950	    bass.append(Message("program_change", channel=0,
   951	                        program=_layer_program(spec, "bass", default=33), time=0))
   952	    # Initial portamento defaults: off, mid time. We turn it on/off per-bar
   953	    # below when bass_octave_shift fires.
   954	    bass.append(Message("control_change", channel=0, control=5, value=64, time=0))   # CC5 portamento time
   955	    bass.append(Message("control_change", channel=0, control=65, value=0, time=0))   # CC65 portamento off
   956	
   957	    layer = next((l for l in spec.layers if l.name == "bass"), None)
   958	    pattern = _find_bass_pattern(layer.pattern_id) if layer else None
   959	    oct_window = (layer.extra.get("octave_window") if layer else None) or (24, 60)
   960	
   961	    if pattern is None:
   962	        # Fallback: root pulse on each beat.
   963	        return _bass_track_root_pulse(spec, ticks_per_bar, bass)
   964	
   965	    grid_cells = pattern.get("grid_cells", 16)
   966	    grid = pattern.get("grid", [])
   967	    cells_to_ticks = ticks_per_bar // grid_cells
   968	
   969	    events: list[tuple[int, int, int, int]] = []
   970	    cc_events: list[tuple[int, int, int]] = []   # (abs_tick, cc, value)
   971	    for bar in spec.bars:
   972	        e = _bar_energy(spec, bar.index)
   973	        if e < _gate(spec, "bass"):
   974	            continue
   975	        vel_base = max(50, min(110, int(60 + 50 * e)))
   976	        # Find next bar's root for chromatic-approach handling.
   977	        next_root_midi = (spec.bars[bar.index + 1].chord_root_midi
   978	                          if bar.index + 1 < len(spec.bars) else bar.chord_root_midi)
   979	        # Portamento on for bars where bass_octave_shift is non-zero (synth
   980	        # bass voices glide between octaves instead of cutting).
   981	        if bar.bass_octave_shift != 0:
   982	            cc_events.append((bar.index * ticks_per_bar, 65, 127))   # on
   983	            cc_events.append(((bar.index + 1) * ticks_per_bar - 5, 65, 0))  # off at end
   984	
   985	        cursor_cell = 0
   986	        last_idx = len(grid) - 1
   987	        for ci, cell in enumerate(grid):
   988	            deg = cell.get("deg", "R")
   989	            length = cell.get("len", 1)
   990	            art = cell.get("art", "tenuto")
   991	            ghost = cell.get("ghost", False)
   992	
   993	            # Per-bar mutation: skip the last cell (breath / fill).
   994	            if bar.bass_skip_last and ci == last_idx:
   995	                cursor_cell += length
   996	                continue
   997	
   998	            if deg in (".", "~"):
   999	                cursor_cell += length
  1000	                continue
  1001	
  1002	            pitch = _bass_degree_to_midi(deg, bar, next_root_midi)
  1003	            if pitch is None:
  1004	                cursor_cell += length
  1005	                continue
  1006	
  1007	            # Per-bar octave shift, clamped to the picked synth's window.
  1008	            pitch = pitch + bar.bass_octave_shift
  1009	            lo, hi = oct_window
  1010	            while pitch < lo:
  1011	                pitch += 12
  1012	            while pitch > hi:
  1013	                pitch -= 12
  1014	            pitch = max(lo, min(hi, pitch))
  1015	
  1016	            on_tick = bar.index * ticks_per_bar + cursor_cell * cells_to_ticks
  1017	            on_tick = max(bar.index * ticks_per_bar,
  1018	                          on_tick + _groove_offset(spec, "bass", cursor_cell))
  1019	            length_ticks = length * cells_to_ticks
  1020	            if art == "staccato":
  1021	                dur_ticks = max(60, length_ticks // 3)
  1022	            elif art == "legato":
  1023	                dur_ticks = max(60, length_ticks - 8)
  1024	            elif art == "ghost":
  1025	                dur_ticks = max(60, length_ticks // 4)
  1026	            else:                     # tenuto / slide / others
  1027	                dur_ticks = max(60, length_ticks - 20)
  1028	
  1029	            vel = vel_base
  1030	            if ghost or art == "ghost" or (bar.bass_ghost_first and ci == 0):
  1031	                vel = max(20, vel_base - 40)
  1032	            vel = max(1, min(127, vel + _vel_jitter(spec, "bass", 4)))
  1033	            events.append((on_tick, 0, pitch, vel))
  1034	            events.append((on_tick + dur_ticks, 1, pitch, 64))
  1035	            cursor_cell += length
  1036	
  1037	    merged = list(events) + [(t, 2, cc, val) for t, cc, val in cc_events]
  1038	    merged.sort(key=lambda ev: (ev[0], ev[1], ev[2]))
  1039	    cursor = 0
  1040	    for abs_tick, kind, *rest in merged:
  1041	        delta = max(0, abs_tick - cursor)
  1042	        if kind == 2:
  1043	            cc, val = rest
  1044	            bass.append(Message("control_change", channel=0,
  1045	                                control=cc, value=val, time=delta))
  1046	        else:
  1047	            pitch, vel = rest
  1048	            msg_type = "note_on" if kind == 0 else "note_off"
  1049	            bass.append(Message(msg_type, channel=0, note=pitch, velocity=vel, time=delta))
  1050	        cursor = abs_tick
  1051	    return bass
  1052	
  1053	
  1054	def _bass_track_root_pulse(spec: SongSpec, ticks_per_bar: int, track: MidiTrack) -> MidiTrack:
  1055	    layer = next((l for l in spec.layers if l.name == "bass"), None)
  1056	    oct_window = (layer.extra.get("octave_window") if layer else None) or (24, 60)
  1057	    cursor = 0
  1058	    beats_per_bar = ticks_per_bar // PPQ
  1059	    for bar in spec.bars:
  1060	        e = _bar_energy(spec, bar.index)
  1061	        if e < _gate(spec, "bass"):
  1062	            continue
  1063	        vel = max(50, min(110, int(60 + 50 * e)))
  1064	        root = bar.chord_root_midi
  1065	        lo, hi = oct_window
  1066	        while root < lo:
  1067	            root += 12
  1068	        while root > hi:
  1069	            root -= 12
  1070	        for beat in range(beats_per_bar):
  1071	            on_tick = bar.index * ticks_per_bar + beat * PPQ
  1072	            track.append(Message("note_on", channel=0, note=root,
  1073	                                 velocity=vel, time=on_tick - cursor))
  1074	            track.append(Message("note_off", channel=0, note=root,
  1075	                                 velocity=64, time=PPQ - 10))
  1076	            cursor = on_tick + PPQ - 10
  1077	    return track
  1078	
  1079	
  1080	def _find_bass_pattern(pattern_id: str) -> dict | None:
  1081	    if not pattern_id:
  1082	        return None
  1083	    try:
  1084	        pats = tables.load("bass/bass_patterns")["patterns"]
  1085	    except FileNotFoundError:
  1086	        return None
  1087	    return next((p for p in pats if p.get("id") == pattern_id), None)
  1088	
  1089	
  1090	# Degree language from `assets/v1/bass/bass_patterns.json` legend.
  1091	_BASS_DEG_OFFSETS = {
  1092	    "R": 0, "b3": 3, "3": 4, "b5": 6, "5": 7, "6": 9, "b6": 8,
  1093	    "b7": 10, "7": 11, "8": 12, "9": 14,
  1094	}
  1095	
  1096	
  1097	def _bass_degree_to_midi(deg: str, bar, next_root_midi: int) -> int | None:
  1098	    """Resolve a bass degree symbol against the current chord."""
  1099	    if deg == "CH":
  1100	        # Chromatic approach: a half-step below the next chord root.
  1101	        return max(24, min(60, next_root_midi - 1))
  1102	    if deg in ("3", "b3"):
  1103	        # Use the chord's actual third (chord_pcs[1] for triads/sevenths).
  1104	        if len(bar.chord_pcs) >= 2:
  1105	            return bar.chord_root_midi + bar.chord_pcs[1]
  1106	    if deg in ("5", "b5"):
  1107	        if len(bar.chord_pcs) >= 3:
  1108	            return bar.chord_root_midi + bar.chord_pcs[2]
  1109	    off = _BASS_DEG_OFFSETS.get(deg)
  1110	    if off is None:
  1111	        return None
  1112	    return bar.chord_root_midi + off
  1113	
  1114	
  1115	def _comp_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack:
  1116	    comp = MidiTrack()
  1117	    comp.append(MetaMessage("track_name", name="comp", time=0))
  1118	    comp.append(Message("program_change", channel=1,
  1119	                        program=_layer_program(spec, "comp", default=4), time=0))
  1120	
  1121	    layer = next((l for l in spec.layers if l.name == "comp"), None)
  1122	    role = _find_comp_role(layer.extra.get("role")) if layer else None
  1123	
  1124	    polyphony = (role or {}).get("polyphony_mode", "full_voicing")
  1125	    if polyphony == "silent":
  1126	        return comp                          # no_comp role → just program-change track
  1127	
  1128	    default_pattern = _find_comp_pattern(layer.pattern_id) if layer else None
  1129	    if default_pattern is None and not spec.section_comp_pattern_ids:
  1130	        return _comp_track_sustain(spec, ticks_per_bar, comp)
  1131	
  1132	    events: list[tuple[int, int, int, int]] = []
  1133	    for bar in spec.bars:
  1134	        e = _bar_energy(spec, bar.index)
  1135	        if e < _gate(spec, "comp") or bar.drop_comp:
  1136	            continue
  1137	        # Per-section comp pattern, falling back to the macro pick.
  1138	        pat_id = spec.section_comp_pattern_ids.get(bar.section_letter, layer.pattern_id if layer else "")
  1139	        pattern = _find_comp_pattern(pat_id) or default_pattern
  1140	        if pattern is None:
  1141	            continue
  1142	        grid_steps = pattern.get("grid_steps", 16)
  1143	        cells_to_ticks = ticks_per_bar // grid_steps
  1144	        hits = pattern.get("hits", [])
  1145	        vel_base = max(45, min(95, int(45 + 50 * e)))
  1146	        voice_base = bar.chord_root_midi + 24
  1147	        full_pitches = sorted({voice_base + iv for iv in bar.chord_pcs})
  1148	        # Role-aware voicing.
  1149	        if polyphony == "monophonic_sequence":
  1150	            shape = _find_arp_shape((layer.extra or {}).get("arp_shape_id", ""))
  1151	            seq = (shape or {}).get("sequence", [0, 1, 2, 3])
  1152	            oct_off = (shape or {}).get("octave_offsets", [0] * len(seq))
  1153	            voice_pitches_per_hit = []
  1154	            for hi in range(len(hits)):
  1155	                step_idx = hi % len(seq)
  1156	                deg_idx = seq[step_idx]
  1157	                octs = oct_off[step_idx] if step_idx < len(oct_off) else 0
  1158	                if 0 <= deg_idx < len(full_pitches):
  1159	                    p = full_pitches[deg_idx] + 12 * octs
  1160	                else:
  1161	                    p = full_pitches[deg_idx % len(full_pitches)] + 12 * octs
  1162	                voice_pitches_per_hit.append([max(36, min(96, p))])
  1163	        elif polyphony == "partial_voicing":
  1164	            # Drop the 5th if a 7 is present; otherwise root + third.
  1165	            if len(full_pitches) >= 4:
  1166	                voice_pitches_per_hit = [[full_pitches[0], full_pitches[1], full_pitches[3]]] * len(hits)
  1167	            else:
  1168	                voice_pitches_per_hit = [full_pitches[:2]] * len(hits)
  1169	        else:
  1170	            voice_pitches_per_hit = [full_pitches] * len(hits)
  1171	
  1172	        last_hit_idx = len(hits) - 1
  1173	        for hit_idx, hit in enumerate(hits):
  1174	            if bar.comp_drop_last and hit_idx == last_hit_idx:
  1175	                continue
  1176	            step = hit.get("step", 0)
  1177	            dur_steps = hit.get("duration_steps", 1)
  1178	            vel_factor = hit.get("vel_factor", 1.0)
  1179	            on_tick = bar.index * ticks_per_bar + step * cells_to_ticks
  1180	            on_tick = max(bar.index * ticks_per_bar,
  1181	                          on_tick + _groove_offset(spec, "comp", step))
  1182	            dur_ticks = max(40, dur_steps * cells_to_ticks - 10)
  1183	            vel = max(20, min(120, int(vel_base * vel_factor) + bar.comp_vel_pull))
  1184	            vel = max(1, min(127, vel + _vel_jitter(spec, "comp", 4)))
  1185	            pitches = voice_pitches_per_hit[hit_idx]
  1186	            for p in pitches:
  1187	                events.append((on_tick, 0, p, vel))
  1188	                events.append((on_tick + dur_ticks, 1, p, 64))
  1189	
  1190	    events.sort(key=lambda ev: (ev[0], ev[1], ev[2]))
  1191	    cursor = 0
  1192	    for abs_tick, kind, pitch, vel in events:
  1193	        delta = max(0, abs_tick - cursor)
  1194	        msg_type = "note_on" if kind == 0 else "note_off"
  1195	        comp.append(Message(msg_type, channel=1, note=pitch, velocity=vel, time=delta))
  1196	        cursor = abs_tick
  1197	    return comp
  1198	
  1199	
  1200	def _comp_track_sustain(spec: SongSpec, ticks_per_bar: int, comp: MidiTrack) -> MidiTrack:
  1201	    cursor = 0
  1202	    for bar in spec.bars:
  1203	        e = _bar_energy(spec, bar.index)
  1204	        if e < _gate(spec, "comp") or bar.drop_comp:
  1205	            continue
  1206	        vel = max(45, min(95, int(45 + 50 * e)))
  1207	        voice_base = bar.chord_root_midi + 24
  1208	        pitches = sorted({voice_base + iv for iv in bar.chord_pcs})
  1209	        on_tick = bar.index * ticks_per_bar
  1210	        for i, p in enumerate(pitches):
  1211	            delta = (on_tick - cursor) if i == 0 else 0
  1212	            comp.append(Message("note_on", channel=1, note=p, velocity=vel, time=delta))
  1213	            cursor = on_tick if i == 0 else cursor
  1214	        off_tick = on_tick + ticks_per_bar - 20
  1215	        for i, p in enumerate(pitches):
  1216	            delta = (off_tick - cursor) if i == 0 else 0
  1217	            comp.append(Message("note_off", channel=1, note=p, velocity=64, time=delta))
  1218	            cursor = off_tick if i == 0 else cursor
  1219	    return comp
  1220	
  1221	
  1222	def _counter_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack | None:
  1223	    """Parallel-3rd harmony of the lead motif, only on high-energy bars."""
  1224	    layer = next((l for l in spec.layers if l.name == "counter"), None)
  1225	    if layer is None:
  1226	        return None
  1227	    motif_id = layer.extra.get("motif_id")
  1228	    contour_id = layer.extra.get("contour_id")
  1229	    subset_id = layer.extra.get("scale_subset_id")
  1230	    if not (motif_id and contour_id and subset_id):
  1231	        return None
  1232	    transpose = int(layer.extra.get("transpose_degrees", 2))
  1233	
  1234	    ts_str = f"{spec.time_sig[0]}/{spec.time_sig[1]}"
  1235	    contours_list = tables.load("melody/contours")["contours"]
  1236	    subsets = tables.load("melody/scale_subsets").get("subsets")
  1237	    subset = next((s for s in subsets if s["id"] == subset_id), None) if subsets else None
  1238	    default_motif = _find_motif(motif_id, ts_str)
  1239	    default_contour = next((c for c in contours_list if c["id"] == contour_id), None)
  1240	    if not (default_motif and default_contour and subset):
  1241	        return None
  1242	
  1243	    track = MidiTrack()
  1244	    track.append(MetaMessage("track_name", name="counter", time=0))
  1245	    track.append(Message("program_change", channel=4,
  1246	                         program=_layer_program(spec, "counter", default=73), time=0))
  1247	
  1248	    mask = subset.get("mask", 127)
  1249	    allowed_degs = [d for d in range(7) if mask & (1 << d)] or list(range(7))
  1250	    base_octave_midi = _lead_octave(spec.provenance.mood)
  1251	
  1252	    events: list[tuple[int, int, int, int]] = []
  1253	    for bar in spec.bars:
  1254	        e = _bar_energy(spec, bar.index)
  1255	        if e < _gate(spec, "counter"):
  1256	            continue
  1257	        # Drop on fill bars too, so the fill speaks.
  1258	        next_bar = spec.bars[bar.index + 1] if bar.index + 1 < len(spec.bars) else None
  1259	        if next_bar is not None and next_bar.section_letter != bar.section_letter:
  1260	            continue
  1261	        motif_id_b = spec.section_motif_ids.get(bar.section_letter, motif_id)
  1262	        contour_id_b = spec.section_contour_ids.get(bar.section_letter, contour_id)
  1263	        motif = _find_motif(motif_id_b, ts_str) or default_motif
  1264	        contour = next((c for c in contours_list if c["id"] == contour_id_b),
  1265	                       default_contour)
  1266	        samples = contour["samples"]
  1267	        onsets = motif["onsets"]
  1268	        bar_tick = bar.index * ticks_per_bar
  1269	        n_onsets = len(onsets)
  1270	        for i, (start_beat, dur_beat) in enumerate(onsets):
  1271	            t = i / max(1, n_onsets - 1) if n_onsets > 1 else 0.0
  1272	            sample_idx = min(len(samples) - 1, int(round(t * (len(samples) - 1))))
  1273	            scale_degree_1 = samples[sample_idx]
  1274	            # Apply per-bar lead mutation, then add the harmony transpose.
  1275	            scale_degree_1 = max(1, scale_degree_1 + bar.melody_transpose + transpose)
  1276	            deg_idx = (scale_degree_1 - 1) % 7
  1277	            octave_shift = (scale_degree_1 - 1) // 7
  1278	            if deg_idx not in allowed_degs:
  1279	                deg_idx = min(allowed_degs, key=lambda d: abs(d - deg_idx))
  1280	            interval = theory.MODES[spec.mode][deg_idx]
  1281	            pitch = base_octave_midi + spec.key_root + interval + 12 * octave_shift
  1282	            pitch = max(48, min(96, pitch))
  1283	
  1284	            on_tick = bar_tick + int(round(start_beat * PPQ))
  1285	            dur_ticks = max(60, int(round(dur_beat * PPQ)) - 20)
  1286	            vel = max(40, min(95, int(50 + 40 * e) - 15))    # always behind the lead
  1287	            vel = max(1, min(127, vel + _vel_jitter(spec, "counter", 4)))
  1288	            events.append((on_tick, 0, pitch, vel))
  1289	            events.append((on_tick + dur_ticks, 1, pitch, 64))
  1290	
  1291	    if not events:
  1292	        return None
  1293	    events.sort(key=lambda ev: (ev[0], ev[1], ev[2]))
  1294	    cursor = 0
  1295	    for abs_tick, kind, pitch, vel in events:
  1296	        delta = max(0, abs_tick - cursor)
  1297	        msg_type = "note_on" if kind == 0 else "note_off"
  1298	        track.append(Message(msg_type, channel=4, note=pitch, velocity=vel, time=delta))
  1299	        cursor = abs_tick
  1300	    return track
  1301	
  1302	
  1303	_EAR_CANDY_TABLE: list | None = None
  1304	
  1305	
  1306	def _ear_candy_table() -> list:
  1307	    """Lazily load and cache the ear_candy_table from aux_layers.json."""
  1308	    global _EAR_CANDY_TABLE
  1309	    if _EAR_CANDY_TABLE is None:
  1310	        try:
  1311	            data = tables.load("aux_layers")
  1312	            _EAR_CANDY_TABLE = data.get("ear_candy_table", {}).get("rows", []) or []
  1313	        except FileNotFoundError:
  1314	            _EAR_CANDY_TABLE = []
  1315	    return _EAR_CANDY_TABLE
  1316	
  1317	
  1318	def _ear_candy_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack | None:
  1319	    """Off-beat percussive stabs at high-energy bars.
  1320	
  1321	    Each bar samples one row from the ear_candy_table via
  1322	    HKDF(aux/earcandy/main/<bar_idx>)[0] % len(rows). Positions are 16th-cell
  1323	    indices avoiding the downbeats (per the table's contract). Pitches walk
  1324	    the chord tones for melodic colour.
  1325	    """
  1326	    layer = next((l for l in spec.layers if l.name == "ear_candy"), None)
  1327	    if layer is None:
  1328	        return None
  1329	    rows = _ear_candy_table()
  1330	    if not rows:
  1331	        return None
  1332	
  1333	    track = MidiTrack()
  1334	    track.append(MetaMessage("track_name", name="ear_candy", time=0))
  1335	    track.append(Message("program_change", channel=7,
  1336	                         program=_layer_program(spec, "ear_candy", default=9), time=0))
  1337	
  1338	    import hashlib as _h, hmac as _hm
  1339	    prk = _hm.new(b"soundhash-v1",
  1340	                  bytes.fromhex(spec.provenance.hash_hex), _h.sha256).digest()
  1341	
  1342	    cells_to_ticks = ticks_per_bar // 16
  1343	    events: list[tuple[int, int, int, int]] = []
  1344	    for bar in spec.bars:
  1345	        e = _bar_energy(spec, bar.index)
  1346	        ec_gate = _MOOD_GATE_OVERRIDES.get(spec.provenance.mood, {}).get("ear_candy", 0.50)
  1347	        if e < ec_gate:
  1348	            continue
  1349	        # Drop on fill bars so the fill speaks.
  1350	        next_bar = spec.bars[bar.index + 1] if bar.index + 1 < len(spec.bars) else None
  1351	        if next_bar is not None and next_bar.section_letter != bar.section_letter:
  1352	            continue
  1353	        info = f"soundhash/v1/aux/earcandy/main/{bar.index}".encode("ascii")
  1354	        out, t, c = b"", b"", 1
  1355	        while len(out) < 4:
  1356	            t = _hm.new(prk, t + info + bytes([c]), _h.sha256).digest()
  1357	            out += t
  1358	            c += 1
  1359	        row_idx = out[0] % len(rows)
  1360	        positions = rows[row_idx] or []
  1361	        bar_tick = bar.index * ticks_per_bar
  1362	        # Pitches: cycle chord tones in the C5 octave, picking a different
  1363	        # tone per stab for melodic interest.
  1364	        chord_tones = sorted({72 + ((bar.chord_root_pc + iv) % 12)
  1365	                              for iv in (bar.chord_pcs or (0, 4, 7))})
  1366	        for j, pos in enumerate(positions):
  1367	            if not 1 <= pos <= 15 or pos == 8:
  1368	                continue
  1369	            on_tick = bar_tick + pos * cells_to_ticks
  1370	            pitch = chord_tones[j % len(chord_tones)]
  1371	            vel = max(40, min(95, int(45 + 50 * (e - 0.5))))
  1372	            vel = max(1, min(127, vel + _vel_jitter(spec, "ear_candy", 4)))
  1373	            dur = max(60, cells_to_ticks - 20)
  1374	            events.append((on_tick, 0, pitch, vel))
  1375	            events.append((on_tick + dur, 1, pitch, 64))
  1376	
  1377	    if not events:
  1378	        return None
  1379	    events.sort(key=lambda ev: (ev[0], ev[1], ev[2]))
  1380	    cursor = 0
  1381	    for abs_tick, kind, pitch, vel in events:
  1382	        delta = max(0, abs_tick - cursor)
  1383	        msg_type = "note_on" if kind == 0 else "note_off"
  1384	        track.append(Message(msg_type, channel=7, note=pitch, velocity=vel, time=delta))
  1385	        cursor = abs_tick
  1386	    return track
  1387	
  1388	
  1389	def _riser_track(spec: SongSpec, ticks_per_bar: int) -> MidiTrack | None:
  1390	    """One-bar reverse-cymbal sweep before any large energy jump.
  1391	
  1392	    Triggered on bar i when bar_energies[i+1] - bar_energies[i] >= 0.25.
  1393	    Uses GM program 119 (Reverse Cymbal); pitch 60 is irrelevant — the
  1394	    sample is the timbre. CC11 ramp lets the swell crescendo in.
  1395	    """
  1396	    layer = next((l for l in spec.layers if l.name == "riser"), None)
  1397	    if layer is None or len(spec.bar_energies) < 2:
  1398	        return None
  1399	
  1400	    # Trigger threshold: delta ≥ 0.22. We picked 0.22 over 0.25 after observing

codex
I have a first pass of concrete bugs. The highest-risk ones are in MIDI rendering: one thread-safety/determinism leak from global jitter state, and one plainly incorrect lead-register implementation where the helper exists but is ignored.
exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '620,680p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
   620	    drum_kit = _pick_drum_kit(macro[9], mood)
   621	    drum_pat_low, drum_pat_high = _pick_drum_pattern_pair(macro[10], drum_kit["id"], time_sig_str)
   622	    drum_pat = drum_pat_low or drum_pat_high or {}
   623	    drum_fill_id = _pick_drum_fill(macro[11], drum_kit["id"])
   624	    bass_pat = _pick_bass_pattern(macro[13], mood, time_sig_str)
   625	    bass_synth = _pick_bass_synth(macro[14], mood, bass_pat["id"])
   626	    comp_role = _pick_comp_role(macro[15], mood)
   627	    comp_synth = _pick_comp_synth(macro[16], mood, comp_role["id"])
   628	    comp_pat = _pick_comp_pattern(macro[17], mood, time_sig_str)
   629	    arp_shape = _pick_arp_shape(macro[17], mood)
   630	    melody_motif = _pick_melody_motif(macro[19], time_sig_str, mood)
   631	    melody_contour = _pick_contour(macro[20], mood)
   632	    melody_scale = _pick_scale_subset(macro[18], mode)
   633	
   634	    # Prefer the picked synth's gm_program (more specific than the mood palette).
   635	    bass_program = (bass_synth.get("gm_program")
   636	                    or _pick_gm_program(macro[14], mood, "bass", default=33))
   637	    comp_program = _pick_gm_program(macro[16], mood, "comp", default=4)
   638	    lead_program = _pick_gm_program(macro[21], mood, "lead", default=80)
   639	    pad_program  = _pick_gm_program(macro[23], mood, "pad",  default=89)
   640	    counter_program = _pick_gm_program(macro[22], mood, "counter", default=73)
   641	    counter_program = _pick_gm_program(macro[23] ^ 0x55, mood, "counter", default=73)
   642	
   643	    # Per-section motif & contour overrides — introduces real variation between
   644	    # form sections (A/B/C). Falls back to the macro melody picks for section A.
   645	    motif_pool = _all_motifs_for_time_sig(time_sig_str)
   646	    contour_pool = _all_contours()
   647	    comp_pattern_pool = _all_comp_patterns(mood, time_sig_str)
   648	    section_motifs: dict[str, str] = {}
   649	    section_contours: dict[str, str] = {}
   650	    section_comp_pats: dict[str, str] = {}
   651	    unique_letters = list(dict.fromkeys(section_letters))
   652	    for li, letter in enumerate(unique_letters):
   653	        if li == 0:
   654	            if motif_pool:
   655	                section_motifs[letter] = melody_motif.get("id", motif_pool[0]["id"])
   656	            if contour_pool:
   657	                section_contours[letter] = melody_contour.get("id", contour_pool[0]["id"])
   658	            section_comp_pats[letter] = comp_pat.get("id", "")
   659	        else:
   660	            seed = s.take(f"form/section/{letter}", 4)
   661	            if motif_pool:
   662	                section_motifs[letter] = motif_pool[seed[0] % len(motif_pool)]["id"]
   663	            if contour_pool:
   664	                section_contours[letter] = contour_pool[seed[1] % len(contour_pool)]["id"]
   665	            if comp_pattern_pool:
   666	                section_comp_pats[letter] = comp_pattern_pool[seed[2] % len(comp_pattern_pool)]["id"]
   667	
   668	    layers = (
   669	        LayerSpec(name="drums", midi_channel=9, synth_id=f"drumkit/{drum_kit['id']}",
   670	                  program=0, pattern_id=drum_pat.get("id", ""),
   671	                  extra={
   672	                      "kit": drum_kit["id"],
   673	                      "pattern_low": drum_pat_low.get("id", ""),
   674	                      "pattern_high": drum_pat_high.get("id", ""),
   675	                      "fill_id": drum_fill_id,
   676	                  }),
   677	        LayerSpec(name="bass", midi_channel=0, synth_id=bass_synth["id"],
   678	                  program=bass_program, pattern_id=bass_pat["id"],
   679	                  extra={"octave_window": tuple(bass_synth.get("octave_window_midi", [28, 52]))}),
   680	        LayerSpec(name="comp", midi_channel=1, synth_id=comp_synth["id"],

exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '820,930p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
   820	        return spec.bar_energies[bar_index]
   821	    return 1.0
   822	
   823	
   824	# Deterministic per-layer velocity-jitter stream (derived from spec.provenance.hash_hex
   825	# via HKDF). Cached on first use. Stream is consumed in event-emit order; render
   826	# is deterministic because event ordering is fixed (sorted by abs_tick).
   827	_VEL_JITTER_CACHE: dict[tuple[str, str], "_VelJitter"] = {}
   828	
   829	
   830	class _VelJitter:
   831	    __slots__ = ("_stream", "_pos")
   832	
   833	    def __init__(self, stream: bytes):
   834	        self._stream = stream
   835	        self._pos = 0
   836	
   837	    def next_offset(self, range_pm: int = 5) -> int:
   838	        if not self._stream:
   839	            return 0
   840	        b = self._stream[self._pos % len(self._stream)]
   841	        self._pos += 1
   842	        # Map byte 0..255 → -range..+range, signed.
   843	        return int((b / 255.0) * (2 * range_pm + 1)) - range_pm
   844	
   845	
   846	def _vel_jitter(spec, layer_name: str, range_pm: int = 5) -> int:
   847	    key = (spec.provenance.hash_hex, layer_name)
   848	    j = _VEL_JITTER_CACHE.get(key)
   849	    if j is None:
   850	        # Derive 256 bytes from HKDF for this layer's jitter stream.
   851	        import hashlib as _h, hmac as _hm
   852	        prk = _hm.new(b"soundhash-v1",
   853	                      bytes.fromhex(spec.provenance.hash_hex),
   854	                      _h.sha256).digest()
   855	        info = f"soundhash/v1/expression/velocity/L{layer_name}".encode("ascii")
   856	        out, t, c = b"", b"", 1
   857	        while len(out) < 256:
   858	            t = _hm.new(prk, t + info + bytes([c]), _h.sha256).digest()
   859	            out += t
   860	            c += 1
   861	        j = _VelJitter(out[:256])
   862	        _VEL_JITTER_CACHE[key] = j
   863	    return j.next_offset(range_pm)
   864	
   865	
   866	_GROOVE_CACHE: dict[str, dict] = {}
   867	
   868	
   869	def _groove_template(spec) -> dict:
   870	    """Return the picked groove template, cached. Empty dict means 'no offsets'."""
   871	    gid = getattr(spec, "groove_template_id", "straight_4_4")
   872	    if gid in _GROOVE_CACHE:
   873	        return _GROOVE_CACHE[gid]
   874	    try:
   875	        templates = tables.load("groove_templates")["templates"]
   876	        tpl = next((t for t in templates if t["id"] == gid), {})
   877	    except FileNotFoundError:
   878	        tpl = {}
   879	    _GROOVE_CACHE[gid] = tpl
   880	    return tpl
   881	
   882	
   883	def _groove_offset(spec, role: str, step: int) -> int:
   884	    """Return PPQ-480 tick offset for role at grid step. 0 if no template / null."""
   885	    offsets = (_groove_template(spec).get("offsets") or {}).get(role)
   886	    if not offsets:
   887	        return 0
   888	    return int(offsets[step % len(offsets)])
   889	
   890	
   891	def render_midi(spec: SongSpec) -> bytes:
   892	    # Reset stateful caches so render is idempotent within a process.
   893	    _VEL_JITTER_CACHE.clear()
   894	    mf = MidiFile(ticks_per_beat=PPQ, type=1)
   895	
   896	    num, den_pow2 = spec.time_sig
   897	    beats_per_bar = num
   898	    ticks_per_bar = PPQ * beats_per_bar
   899	    _BEATS_PER_BAR = beats_per_bar  # captured by helpers below
   900	
   901	    # ---- meta ------------------------------------------------------------
   902	    meta = MidiTrack()
   903	    meta.append(MetaMessage("track_name", name="meta", time=0))
   904	    meta.append(MetaMessage("set_tempo", tempo=bpm2tempo(spec.tempo_bpm), time=0))
   905	    meta.append(MetaMessage("time_signature", numerator=num,
   906	                            denominator=den_pow2, time=0))
   907	    meta.append(MetaMessage("marker",
   908	                            text=f"soundhash/v1 {spec.provenance.hash_hex[:16]} "
   909	                                 f"{spec.provenance.mood} {spec.mode}",
   910	                            time=0))
   911	    mf.tracks.append(meta)
   912	
   913	    mf.tracks.append(_bass_track(spec, ticks_per_bar))
   914	    mf.tracks.append(_comp_track(spec, ticks_per_bar))
   915	    drum = _drum_track(spec, ticks_per_bar)
   916	    if drum is not None:
   917	        mf.tracks.append(drum)
   918	    lead = _lead_track(spec, ticks_per_bar)
   919	    if lead is not None:
   920	        mf.tracks.append(lead)
   921	    pad = _pad_track(spec, ticks_per_bar)
   922	    if pad is not None:
   923	        mf.tracks.append(pad)
   924	    counter = _counter_track(spec, ticks_per_bar)
   925	    if counter is not None:
   926	        mf.tracks.append(counter)
   927	    drone = _drone_track(spec, ticks_per_bar)
   928	    if drone is not None:
   929	        mf.tracks.append(drone)
   930	    riser = _riser_track(spec, ticks_per_bar)

exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '1688,1818p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
  1688	                         program=_layer_program(spec, "lead", default=80), time=0))
  1689	    # CC11 expression curve: slow swell across the song to keep sustained
  1690	    # notes from sounding static. Cosine envelope, sampled per bar.
  1691	    cc_events: list[tuple[int, int, int]] = []  # (abs_tick, cc, value)
  1692	    n_bars = len(spec.bars)
  1693	    if n_bars:
  1694	        for i in range(n_bars):
  1695	            # Per-bar swell: 95 at bar start, 122 at midpoint, 105 at end.
  1696	            for frac, val in ((0.0, 95), (0.5, 122), (1.0, 105)):
  1697	                t_in_bar = int(round(frac * ticks_per_bar))
  1698	                cc_events.append((i * ticks_per_bar + t_in_bar, 11, val))
  1699	
  1700	    mask = subset.get("mask", 127)
  1701	    allowed_degs = [d for d in range(7) if mask & (1 << d)] or list(range(7))
  1702	    base_octave_midi = 72                       # C5
  1703	
  1704	    # Build (abs_tick, kind, pitch, vel) events; deltas computed at the end.
  1705	    # Pitch-bend events are stored separately and merged at the end.
  1706	    events = []
  1707	    bend_events: list[tuple[int, int]] = []
  1708	    for bar in spec.bars:
  1709	        e = _bar_energy(spec, bar.index)
  1710	        if e < _gate(spec, "lead") or bar.drop_lead:
  1711	            continue
  1712	        # Lead drops out on fill bars (next section is different) so the drum
  1713	        # fill speaks. Standard production convention.
  1714	        next_bar = spec.bars[bar.index + 1] if bar.index + 1 < len(spec.bars) else None
  1715	        if next_bar is not None and next_bar.section_letter != bar.section_letter:
  1716	            continue
  1717	        # Phrase end: this bar is the last lead-active bar before either the
  1718	        # song ends OR the lead drops for a fill. We apply a downward bend
  1719	        # ("fall") to its last note.
  1720	        is_phrase_end = (
  1721	            next_bar is None
  1722	            or (next_bar.index + 1 < len(spec.bars)
  1723	                and spec.bars[next_bar.index + 1].section_letter != next_bar.section_letter)
  1724	        )
  1725	        # Per-section motif/contour — falls back to the macro pick for unknown letters.
  1726	        motif_id_b = spec.section_motif_ids.get(bar.section_letter, motif_id)
  1727	        contour_id_b = spec.section_contour_ids.get(bar.section_letter, contour_id)
  1728	        motif = _find_motif(motif_id_b, ts_str) or default_motif
  1729	        contour = next((c for c in contours_list if c["id"] == contour_id_b),
  1730	                       default_contour)
  1731	        samples = contour["samples"]
  1732	        onsets = motif["onsets"]
  1733	        samples_mean = sum(samples) / len(samples) if samples else 0.0
  1734	        bar_tick = bar.index * ticks_per_bar
  1735	        n_onsets = len(onsets)
  1736	        # Strong-beat snap targets: chord tones in the lead octave.
  1737	        chord_tones = sorted(
  1738	            base_octave_midi + ((spec.key_root + iv) % 12 + (bar.chord_root_pc + iv) // 12 * 0)
  1739	            for iv in ()  # placeholder; we recompute below for clarity
  1740	        )
  1741	        chord_tones = sorted({base_octave_midi + ((bar.chord_root_pc + iv) % 12) + 12 * 0
  1742	                              for iv in bar.chord_pcs})
  1743	        for i, (start_beat, dur_beat) in enumerate(onsets):
  1744	            t = i / max(1, n_onsets - 1) if n_onsets > 1 else 0.0
  1745	            sample_idx = min(len(samples) - 1, int(round(t * (len(samples) - 1))))
  1746	            scale_degree_1 = samples[sample_idx]
  1747	            # Per-bar mutation: invert (mirror about mean) then transpose.
  1748	            if bar.melody_invert and samples_mean:
  1749	                scale_degree_1 = int(round(2 * samples_mean - scale_degree_1))
  1750	            scale_degree_1 = max(1, scale_degree_1 + bar.melody_transpose)
  1751	            deg_idx = (scale_degree_1 - 1) % 7
  1752	            octave_shift = (scale_degree_1 - 1) // 7
  1753	            if deg_idx not in allowed_degs:
  1754	                deg_idx = min(allowed_degs, key=lambda d: abs(d - deg_idx))
  1755	            interval = theory.MODES[spec.mode][deg_idx]
  1756	            pitch = base_octave_midi + spec.key_root + interval + 12 * octave_shift
  1757	            pitch = max(48, min(96, pitch))
  1758	
  1759	            # Strong-beat chord-tone snap: on beats 0 and 2 (in 4/4), pull the
  1760	            # picked pitch to the nearest chord tone of the current bar.
  1761	            beat_in_bar = start_beat % beats_per_bar
  1762	            is_strong = abs(beat_in_bar - 0.0) < 0.01 or abs(beat_in_bar - 2.0) < 0.01
  1763	            if is_strong and chord_tones:
  1764	                pitch = min(chord_tones, key=lambda c: abs(c - pitch))
  1765	
  1766	            on_tick = bar_tick + int(round(start_beat * PPQ))
  1767	            dur_ticks = max(60, int(round(dur_beat * PPQ)) - 20)
  1768	            vel = max(50, min(115, int(60 + 60 * e)))
  1769	            # Section-start accent on the first lead onset of any bar that
  1770	            # begins a new section. Boost +15 velocity so the section change
  1771	            # is audible on the lead.
  1772	            prev_bar = spec.bars[bar.index - 1] if bar.index > 0 else None
  1773	            is_section_start = (prev_bar is not None
  1774	                                and prev_bar.section_letter != bar.section_letter)
  1775	            if is_section_start and i == 0:
  1776	                vel = min(127, vel + 15)
  1777	            events.append((on_tick, 0, pitch, vel))
  1778	            events.append((on_tick + dur_ticks, 1, pitch, 64))
  1779	
  1780	            # Phrase-end bend: schedule a downward fall on the last onset.
  1781	            is_last_onset = (i == n_onsets - 1)
  1782	            if is_phrase_end and is_last_onset:
  1783	                bend_start = on_tick + max(20, dur_ticks // 2)
  1784	                bend_end = on_tick + dur_ticks - 5
  1785	                bend_events.append((bend_start, 0))           # neutral at start
  1786	                bend_events.append((bend_end, -8192))         # full -2 semitones
  1787	                bend_events.append((on_tick + dur_ticks + 20, 0))  # reset after note-off
  1788	
  1789	    # Merge note + CC + pitch-bend events. Kind ordering at same tick:
  1790	    # 0 note_on, 1 note_off, 2 control_change, 3 pitchwheel.
  1791	    merged = (
  1792	        list(events)
  1793	        + [(t, 2, cc, val) for t, cc, val in cc_events]
  1794	        + [(t, 3, val, 0) for t, val in bend_events]
  1795	    )
  1796	    merged.sort(key=lambda e: (e[0], e[1], e[2]))
  1797	    cursor = 0
  1798	    for abs_tick, kind, *rest in merged:
  1799	        delta = max(0, abs_tick - cursor)
  1800	        if kind == 2:
  1801	            cc, val = rest
  1802	            track.append(Message("control_change", channel=2,
  1803	                                 control=cc, value=val, time=delta))
  1804	        elif kind == 3:
  1805	            bend_val, _ = rest
  1806	            track.append(Message("pitchwheel", channel=2, pitch=bend_val, time=delta))
  1807	        else:
  1808	            pitch, vel = rest
  1809	            msg_type = "note_on" if kind == 0 else "note_off"
  1810	            track.append(Message(msg_type, channel=2, note=pitch, velocity=vel, time=delta))
  1811	        cursor = abs_tick
  1812	    return track
  1813	
  1814	
  1815	# ---------------------------------------------------------------------------
  1816	# Helpers
  1817	# ---------------------------------------------------------------------------
  1818	

exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '1888,2075p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
  1888	        if os.path.isfile(p):
  1889	            return p
  1890	    raise RuntimeError(
  1891	        "No SoundFont found. Set SOUNDHASH_SOUNDFONT=/path/to.sf2 "
  1892	        "or install fluid-synth via Homebrew."
  1893	    )
  1894	
  1895	
  1896	def render_wav(midi_bytes: bytes, sample_rate: int = 44100,
  1897	               provenance: dict | None = None,
  1898	               apply_fx: bool = True) -> bytes:
  1899	    """Run fluidsynth on the MIDI, return the WAV bytes (with optional metadata)."""
  1900	    if shutil.which("fluidsynth") is None:
  1901	        raise RuntimeError("fluidsynth CLI not found on PATH")
  1902	    sf2 = _find_soundfont()
  1903	
  1904	    with tempfile.TemporaryDirectory() as td:
  1905	        td = Path(td)
  1906	        mid_path = td / "in.mid"
  1907	        wav_path = td / "out.wav"
  1908	        mid_path.write_bytes(midi_bytes)
  1909	        cmd = [
  1910	            "fluidsynth", "-ni",
  1911	            "-F", str(wav_path),
  1912	            "-r", str(sample_rate),
  1913	            "-o", "synth.cpu-cores=1",
  1914	            "-o", "synth.reverb.active=no",
  1915	            "-o", "synth.chorus.active=no",
  1916	            sf2,
  1917	            str(mid_path),
  1918	        ]
  1919	        # Inherit a controlled locale for cross-platform-stable text parsing.
  1920	        env = {**os.environ, "LC_ALL": "C"}
  1921	        proc = subprocess.run(cmd, capture_output=True, env=env, check=False)
  1922	        if proc.returncode != 0:
  1923	            raise RuntimeError(
  1924	                f"fluidsynth exited {proc.returncode}: {proc.stderr.decode(errors='replace')[:400]}"
  1925	            )
  1926	        wav = _postprocess_wav(wav_path.read_bytes(),
  1927	                               mood=(provenance or {}).get("mood") if apply_fx else None)
  1928	        if provenance:
  1929	            wav = _embed_wav_provenance(wav, provenance)
  1930	        return wav
  1931	
  1932	
  1933	def _embed_wav_provenance(wav_bytes: bytes, prov: dict) -> bytes:
  1934	    """Insert a RIFF LIST/INFO chunk carrying provenance after `fmt `.
  1935	
  1936	    Sub-chunks (4-byte IDs) used:
  1937	        ISFT  software identifier
  1938	        ICMT  free-form comment with full provenance
  1939	        ICOP  copyright / license
  1940	    """
  1941	    if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
  1942	        return wav_bytes  # not a WAV; bail.
  1943	
  1944	    # Build INFO sub-chunks.
  1945	    def _info(tag: bytes, text: str) -> bytes:
  1946	        data = text.encode("utf-8") + b"\x00"
  1947	        if len(data) % 2:
  1948	            data += b"\x00"
  1949	        return tag + struct.pack("<I", len(data)) + data
  1950	
  1951	    sw = "soundhash/v1"
  1952	    comment = (
  1953	        f"soundhash/v1 sha={prov.get('hash_hex','?')[:64]} "
  1954	        f"mood={prov.get('mood','?')} mode={prov.get('mode','?')} "
  1955	        f"key={prov.get('key_root','?')} tempo={prov.get('tempo_bpm','?')} "
  1956	        f"form={prov.get('form_id','?')} bars={prov.get('bars','?')} "
  1957	        f"groove={prov.get('groove_template_id','?')} "
  1958	        f"curve={prov.get('energy_curve_id','?')}"
  1959	    )
  1960	    info_payload = b"INFO" + _info(b"ISFT", sw) + _info(b"ICMT", comment) \
  1961	                            + _info(b"ICOP", "deterministic — see DESIGN.md")
  1962	    list_chunk = b"LIST" + struct.pack("<I", len(info_payload)) + info_payload
  1963	
  1964	    # Walk existing chunks and insert LIST right after `fmt `.
  1965	    out = bytearray()
  1966	    out += wav_bytes[:12]                      # RIFF<size>WAVE; size patched at end
  1967	    pos = 12
  1968	    inserted = False
  1969	    while pos + 8 <= len(wav_bytes):
  1970	        chunk_id = wav_bytes[pos:pos + 4]
  1971	        chunk_size = struct.unpack("<I", wav_bytes[pos + 4:pos + 8])[0]
  1972	        chunk_total = 8 + chunk_size + (chunk_size & 1)
  1973	        out += wav_bytes[pos:pos + chunk_total]
  1974	        pos += chunk_total
  1975	        if not inserted and chunk_id == b"fmt ":
  1976	            out += list_chunk
  1977	            inserted = True
  1978	
  1979	    if not inserted:
  1980	        # No fmt chunk found — append before EOF as safe fallback.
  1981	        out += list_chunk
  1982	
  1983	    # Patch RIFF size (= total length of out minus 8 bytes for "RIFF"+size).
  1984	    new_size = len(out) - 8
  1985	    out[4:8] = struct.pack("<I", new_size)
  1986	    return bytes(out)
  1987	
  1988	
  1989	def _postprocess_wav(wav_bytes: bytes, mood: str | None = None) -> bytes:
  1990	    """Cap length, apply fades, LUFS-norm, mood FX chain, peak-limit."""
  1991	    with wave.open(io.BytesIO(wav_bytes), "rb") as r:
  1992	        n_channels = r.getnchannels()
  1993	        sample_width = r.getsampwidth()
  1994	        rate = r.getframerate()
  1995	        n_frames = r.getnframes()
  1996	        raw = r.readframes(n_frames)
  1997	    if sample_width != 2:
  1998	        return wav_bytes  # only handle 16-bit for now
  1999	
  2000	    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
  2001	    samples = samples.reshape(-1, n_channels)
  2002	
  2003	    # 1. Length cap.
  2004	    max_frames = int(MAX_SECONDS * rate)
  2005	    if len(samples) > max_frames:
  2006	        samples = samples[:max_frames]
  2007	    n = len(samples)
  2008	
  2009	    # 2. LUFS normalisation (only if there's enough audio for the gating window).
  2010	    samples = _normalise_loudness(samples, rate)
  2011	
  2012	    # 3. Per-mood FX chain (reverb / delay / chorus / EQ via pedalboard).
  2013	    if mood:
  2014	        try:
  2015	            from .fx import apply_fx
  2016	            samples = apply_fx(samples, rate, mood)
  2017	        except Exception:
  2018	            pass
  2019	
  2020	    # 4. Cosine fades.
  2021	    fi = max(1, int(FADE_IN_MS * rate / 1000))
  2022	    fo = max(1, int(FADE_OUT_MS * rate / 1000))
  2023	    if n >= fi:
  2024	        ramp = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, fi, dtype=np.float32)))
  2025	        samples[:fi] *= ramp[:, None]
  2026	    if n >= fo:
  2027	        ramp = 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, fo, dtype=np.float32)))
  2028	        samples[-fo:] *= ramp[:, None]
  2029	
  2030	    # 5. Peak limiter at PEAK_CEILING_DBFS (linear-domain; deterministic).
  2031	    ceiling = 10 ** (PEAK_CEILING_DBFS / 20.0)
  2032	    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
  2033	    if peak > ceiling:
  2034	        samples *= ceiling / peak
  2035	
  2036	    # Quantise back to int16.
  2037	    out_int = np.clip(samples * 32768.0, -32768, 32767).astype("<i2")
  2038	
  2039	    out = io.BytesIO()
  2040	    with wave.open(out, "wb") as w:
  2041	        w.setnchannels(n_channels)
  2042	        w.setsampwidth(2)
  2043	        w.setframerate(rate)
  2044	        w.writeframes(out_int.tobytes())
  2045	    return out.getvalue()
  2046	
  2047	
  2048	def _normalise_loudness(samples: np.ndarray, rate: int) -> np.ndarray:
  2049	    """Apply gain so integrated LUFS approaches TARGET_LUFS. Deterministic.
  2050	
  2051	    pyloudnorm uses ITU-R BS.1770 with a 400 ms window — needs ≥0.4 s of audio.
  2052	    """
  2053	    try:
  2054	        import pyloudnorm
  2055	    except ImportError:
  2056	        return samples
  2057	    if len(samples) < int(0.5 * rate):
  2058	        return samples
  2059	    meter = pyloudnorm.Meter(rate)        # default block_size=0.4 s
  2060	    try:
  2061	        loudness = meter.integrated_loudness(samples)
  2062	    except Exception:
  2063	        return samples
  2064	    if not np.isfinite(loudness):
  2065	        return samples
  2066	    gain_db = TARGET_LUFS - loudness
  2067	    gain_db = max(-MAX_GAIN_DB, min(MAX_GAIN_DB, gain_db))
  2068	    gain = 10 ** (gain_db / 20.0)
  2069	    return samples * gain
  2070	
  2071	## === render/fx.py ===
  2072	"""Per-mood post-render FX chains (reverb / delay / chorus / EQ).
  2073	
  2074	Applied after LUFS normalisation but before the final peak limiter so the
  2075	limiter still owns the true-peak ceiling. Determinism is best-effort:

codex
I’m checking a few more spots for hidden edge cases now: lookup helpers that can misresolve IDs, bar-count logic against the 30 s cap, and places where failures get silently swallowed instead of producing a stable contract.
exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '495,565p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
   495	def hash_to_spec(
   496	    hash_bytes: bytes,
   497	    mime: Optional[str] = None,
   498	    version: str = "v1",
   499	    mood_override: Optional[str] = None,
   500	) -> SongSpec:
   501	    """Pure: same (hash, mime, version) → same SongSpec.
   502	
   503	    Walks the byte budget from CONTEXT/§4 of DESIGN.md top-down, filtering each
   504	    table by all prior choices. See test_decode_invariants.py for invariants.
   505	    """
   506	    if len(hash_bytes) != 32:
   507	        raise ValueError(f"expected 32-byte SHA-256, got {len(hash_bytes)}")
   508	    if version != "v1":
   509	        raise UnsupportedVersionError(version)
   510	
   511	    prk = _hkdf_extract(_SALT, hash_bytes)
   512	    s = HashStream(prk, version)
   513	    macro = s.take("macro", 32)
   514	
   515	    # MIME → family pre-filter.
   516	    from .mime import family_for_mime
   517	    family = family_for_mime(mime)
   518	
   519	    # Macro decisions.
   520	    if mood_override and mood_override.startswith("M") and mood_override[1:].isdigit():
   521	        mood = mood_override
   522	    else:
   523	        mood = _pick_mood(macro, family)
   524	    tempo = _pick_tempo(macro[2], mood)
   525	    key_root = macro[3] % 12
   526	    mode = _pick_mode(macro[4], mood)
   527	    progression = _pick_progression(macro[7], mood, mode)
   528	
   529	    # Resolve progression to per-bar chord entries.
   530	    chord_entries = theory.resolve_progression(progression, key_root, mode)
   531	
   532	    # Form first — its layout determines bar count, then we cap by what fits
   533	    # in 30 seconds at the chosen tempo (leave 2 s for reverb tail).
   534	    beats_per_bar = 4
   535	    max_bars_for_30s = max(2, int(28.0 * tempo / (60.0 * beats_per_bar)))
   536	    form = _pick_form_unconstrained(macro[6], max_bars_for_30s, mood)
   537	    target_bars = _bars_from_layout(form, default_n=8, cap=max_bars_for_30s)
   538	
   539	    # Loop the progression to fill target_bars.
   540	    looped = []
   541	    while len(looped) < target_bars:
   542	        looped.extend(chord_entries)
   543	    looped = looped[:target_bars]
   544	    energy_curve = _pick_energy_curve(macro[24], form, mood)
   545	    groove_id = _pick_groove_template(macro[5], mood)
   546	    section_letters = _expand_form_layout(form, target_bars)
   547	    if target_bars > 1:
   548	        bar_energies = tuple(
   549	            _sample_energy_curve(energy_curve, (i + 0.5) / target_bars)
   550	            for i in range(target_bars)
   551	        )
   552	    else:
   553	        bar_energies = (_sample_energy_curve(energy_curve, 0.5),)
   554	
   555	    bars = []
   556	    for i, e in enumerate(looped):
   557	        # Per-bar mutation seeds from HKDF.
   558	        mel_seed = s.take(f"perbar/melody/{i}", 4)
   559	        bass_seed = s.take(f"perbar/bass/{i}", 2)
   560	        mel_op = mel_seed[0] % 8
   561	        bass_op = bass_seed[0] % 8
   562	        # Bar 0 is always identity so the hook + groove land cleanly first.
   563	        if i == 0:
   564	            transpose, invert = 0, False
   565	            octave_shift, skip_last, ghost_first = 0, False, False

exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '1818,1848p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
  1818	
  1819	
  1820	def _find_motif(motif_id: str, time_sig: str) -> dict | None:
  1821	    pools = tables.load("melody/motif_rhythms")["pools"]
  1822	    for ts, pool in pools.items():
  1823	        items = pool if isinstance(pool, list) else [v for sub in pool.values()
  1824	                                                     for v in (sub if isinstance(sub, list) else [sub])]
  1825	        for m in items:
  1826	            if m.get("id") == motif_id:
  1827	                return m
  1828	    return None
  1829	
  1830	
  1831	def _layer_program(spec: SongSpec, name: str, default: int) -> int:
  1832	    for l in spec.layers:
  1833	        if l.name == name:
  1834	            return max(0, min(127, l.program))
  1835	    return default
  1836	
  1837	## === render/audio.py ===
  1838	"""MIDI → WAV via the fluidsynth CLI, with length cap + cosine fades.
  1839	
  1840	Pinned flags per DESIGN.md §7 determinism contract: cpu-cores=1, no internal
  1841	reverb/chorus. Output is normalised to ≤30 s with a 200 ms cosine fade-out
  1842	(and a 5 ms fade-in to kill the start-click).
  1843	
  1844	Stage-2 will move to in-process pyfluidsynth + ship a CC0 SoundFont.
  1845	"""
  1846	from __future__ import annotations
  1847	
  1848	import io

exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '223,240p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
   223	def _bars_from_layout(form: dict, default_n: int = 8, cap: int = 99) -> int:
   224	    """Sum fixed counts in form.layout; allocate `default_n` to any 'N' filler.
   225	
   226	    Result clamped to [form.min_bars, form.max_bars] then to `cap`.
   227	    """
   228	    layout = form.get("layout") or [["A", "N"]]
   229	    fixed = sum(c for _, c in layout if c != "N")
   230	    n_natural = sum(1 for _, c in layout if c == "N")
   231	    total = fixed + n_natural * max(2, default_n // max(1, len(layout)))
   232	    if not fixed and not n_natural:
   233	        total = default_n
   234	    lo = form.get("min_bars", 1)
   235	    hi = min(cap, form.get("max_bars", cap))
   236	    return max(lo, min(hi, total))
   237	
   238	
   239	# Per-mood curve-id preferences (intersected with form.allowed_curves).
   240	# IDs: 0 flat_low, 1 flat_mid, 2 flat_high, 3 rise, 4 fall, 5 arc, 6 U,

exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '148,180p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
   148	def _expand_form_layout(form: dict, n_bars: int) -> list[str]:
   149	    """Turn `[[letter, bar_count_or_'N'], ...]` into a per-bar section-letter list of length n_bars."""
   150	    layout = form.get("layout") or [["A", "N"]]
   151	    fixed = [(letter, count) for letter, count in layout if count != "N"]
   152	    fixed_total = sum(c for _, c in fixed)
   153	    n_remaining = max(0, n_bars - fixed_total)
   154	    n_natural = sum(1 for _, c in layout if c == "N") or 1
   155	    natural_share, extra = divmod(n_remaining, n_natural)
   156	
   157	    out: list[str] = []
   158	    for letter, count in layout:
   159	        if count == "N":
   160	            share = natural_share + (1 if extra > 0 else 0)
   161	            extra = max(0, extra - 1)
   162	            out.extend([letter] * share)
   163	        else:
   164	            out.extend([letter] * count)
   165	    # Truncate / pad to exactly n_bars.
   166	    out = out[:n_bars]
   167	    while len(out) < n_bars:
   168	        out.append(out[-1] if out else "A")
   169	    return out
   170	
   171	
   172	def _pick_form(byte: int, n_bars: int) -> dict:
   173	    forms = tables.load("forms")["forms"]
   174	    eligible = [f for f in forms if f.get("min_bars", 1) <= n_bars <= f.get("max_bars", 99)]
   175	    if not eligible:
   176	        eligible = forms
   177	    eligible.sort(key=lambda f: f.get("id", 0))
   178	    return eligible[byte % len(eligible)]
   179	
   180	

codex
There’s also a cross-host determinism problem in audio rendering: the renderer picks the first SoundFont it happens to find on the machine, so identical MIDI can synthesize differently on different boxes even with the same code. I’m pulling the exact lines for that and a couple of API/edge-case issues.
exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '1860,1894p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
  1860	# Output length + loudness contract (DESIGN.md §3, dim 14):
  1861	MAX_SECONDS = 30.0
  1862	FADE_IN_MS = 5
  1863	FADE_OUT_MS = 200
  1864	TARGET_LUFS = -16.0
  1865	PEAK_CEILING_DBFS = -1.5     # peak ceiling (linear-domain limiter, not true-peak)
  1866	MAX_GAIN_DB = 24.0           # safety cap on the loudness-correction gain
  1867	
  1868	
  1869	# Default soundfont — bundled with `brew install fluidsynth` on macOS.
  1870	# 307 KB Vintage-Dreams-Waves; sounds appropriate for M5 synthwave-ish output
  1871	# but is far from full GM. Override via SOUNDHASH_SOUNDFONT env var.
  1872	_HERE = os.path.dirname(os.path.abspath(__file__))
  1873	_REPO_SF2 = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "assets", "v1", "sf2"))
  1874	_DEFAULT_SF2_CANDIDATES = [
  1875	    os.path.join(_REPO_SF2, "MS-Basic.sf3"),
  1876	    "/usr/local/share/sounds/sf2/FluidR3_GM.sf2",
  1877	    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
  1878	    # last resort: brew's tiny pad-only synth font (no drums)
  1879	    "/opt/homebrew/Cellar/fluid-synth/2.5.4/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2",
  1880	]
  1881	
  1882	
  1883	def _find_soundfont() -> str:
  1884	    sf = os.environ.get("SOUNDHASH_SOUNDFONT")
  1885	    if sf and os.path.isfile(sf):
  1886	        return sf
  1887	    for p in _DEFAULT_SF2_CANDIDATES:
  1888	        if os.path.isfile(p):
  1889	            return p
  1890	    raise RuntimeError(
  1891	        "No SoundFont found. Set SOUNDHASH_SOUNDFONT=/path/to.sf2 "
  1892	        "or install fluid-synth via Homebrew."
  1893	    )
  1894	

exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '90,116p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
    90	def _pick_mood(macro: bytes, mime_family: str | None) -> str:
    91	    """Byte 0 selects mood within a MIME-family-filtered candidate list.
    92	
    93	    With mime=None we expose all 11 moods.
    94	    """
    95	    f2m = tables.load("family_to_moods")
    96	    if mime_family and mime_family in f2m["mapping"]:
    97	        candidates = f2m["mapping"][mime_family]["candidates"]
    98	    else:
    99	        candidates = list(f2m["moods"].keys())
   100	    return candidates[macro[0] % len(candidates)]
   101	
   102	
   103	def _pick_tempo(byte: int, mood: str) -> float:
   104	    pools = tables.load("tempo_pools")["pools"]
   105	    pool = pools[mood]["bpm"]
   106	    base = pool[(byte & 0x07) % len(pool)]
   107	    # 5 high bits drive a ±0.5% nudge to retain entropy without changing perceived BPM.
   108	    nudge = ((byte >> 3) - 16) / 16.0 * 0.005      # in [-0.005, +0.00469]
   109	    return round(base * (1.0 + nudge), 3)
   110	
   111	
   112	def _pick_mode(byte: int, mood: str) -> str:
   113	    moods = tables.load("moods")["moods"]
   114	    mood_modes = moods[mood]["modes"]
   115	    return mood_modes[byte % len(mood_modes)]
   116	

exec
/bin/zsh -lc "nl -ba impl-codex.md | sed -n '2071,2185p'" in /Users/tabledevil/projects/soundhash/research/adv-review
 succeeded in 0ms:
  2071	## === render/fx.py ===
  2072	"""Per-mood post-render FX chains (reverb / delay / chorus / EQ).
  2073	
  2074	Applied after LUFS normalisation but before the final peak limiter so the
  2075	limiter still owns the true-peak ceiling. Determinism is best-effort:
  2076	pedalboard's algorithms are not bit-identical across builds, but with
  2077	pinned `pedalboard==0.9.x` the output is stable on a given host.
  2078	
  2079	The chains are intentionally subtle. A soundhash is meant to be musical,
  2080	not a synthwave demo reel — heavy modulation would obscure distinguishability.
  2081	"""
  2082	from __future__ import annotations
  2083	
  2084	import io
  2085	import wave
  2086	
  2087	import numpy as np
  2088	
  2089	
  2090	# Per-mood FX recipe. Each entry is a list of (effect_name, kwargs) pairs.
  2091	# Effect names map to pedalboard plugin classes.
  2092	_MOOD_FX: dict[str, list[tuple[str, dict]]] = {
  2093	    # M0 Ambient — long plate reverb + light chorus + low-shelf cut.
  2094	    "M0":  [("Reverb",       {"room_size": 0.85, "damping": 0.4, "wet_level": 0.40, "dry_level": 0.70, "width": 1.0}),
  2095	            ("Chorus",       {"rate_hz": 0.6, "depth": 0.35, "centre_delay_ms": 12, "feedback": 0.05, "mix": 0.25}),
  2096	            ("LowShelfFilter", {"cutoff_frequency_hz": 110, "gain_db": -1.0, "q": 0.7})],
  2097	    # M1 Ballad — medium hall, warm low end.
  2098	    "M1":  [("Reverb",       {"room_size": 0.70, "damping": 0.5, "wet_level": 0.28, "dry_level": 0.78, "width": 0.9}),
  2099	            ("LowShelfFilter", {"cutoff_frequency_hz": 200, "gain_db": +1.5, "q": 0.7}),
  2100	            ("HighShelfFilter", {"cutoff_frequency_hz": 8000, "gain_db": +1.0, "q": 0.7})],
  2101	    # M2 Hip-hop / Boom-bap — short room + tape-style high cut + light analog warmth.
  2102	    "M2":  [("Reverb",       {"room_size": 0.30, "damping": 0.7, "wet_level": 0.18, "dry_level": 0.85, "width": 0.7}),
  2103	            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": -2.0, "q": 0.7}),
  2104	            ("Distortion",   {"drive_db": 4.0})],
  2105	    # M3 Downtempo — wide chorus + slow delay + warm.
  2106	    "M3":  [("Chorus",       {"rate_hz": 0.7, "depth": 0.45, "centre_delay_ms": 18, "feedback": 0.10, "mix": 0.30}),
  2107	            ("Delay",        {"delay_seconds": 0.375, "feedback": 0.18, "mix": 0.18}),
  2108	            ("Reverb",       {"room_size": 0.55, "damping": 0.55, "wet_level": 0.22, "dry_level": 0.80, "width": 0.95})],
  2109	    # M4 Latin — light room, slight high-shelf brightness.
  2110	    "M4":  [("Reverb",       {"room_size": 0.35, "damping": 0.4, "wet_level": 0.18, "dry_level": 0.85, "width": 0.85}),
  2111	            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": +1.5, "q": 0.7})],
  2112	    # M5 Synthwave — short plate + ducked dotted-eighth delay + chorus on synths.
  2113	    "M5":  [("Chorus",       {"rate_hz": 1.1, "depth": 0.25, "centre_delay_ms": 8, "feedback": 0.05, "mix": 0.20}),
  2114	            ("Delay",        {"delay_seconds": 0.214, "feedback": 0.30, "mix": 0.16}),
  2115	            ("Reverb",       {"room_size": 0.45, "damping": 0.4, "wet_level": 0.24, "dry_level": 0.82, "width": 1.0})],
  2116	    # M6 House — tight ambience + sidechain-feel low pump (use compressor).
  2117	    "M6":  [("Reverb",       {"room_size": 0.30, "damping": 0.5, "wet_level": 0.18, "dry_level": 0.85, "width": 0.9}),
  2118	            ("Compressor",   {"threshold_db": -16.0, "ratio": 3.0, "attack_ms": 8, "release_ms": 80})],
  2119	    # M7 Techno — tight, slightly dark, light delay.
  2120	    "M7":  [("Delay",        {"delay_seconds": 0.1875, "feedback": 0.18, "mix": 0.12}),
  2121	            ("HighShelfFilter", {"cutoff_frequency_hz": 9000, "gain_db": -1.5, "q": 0.7}),
  2122	            ("Reverb",       {"room_size": 0.25, "damping": 0.6, "wet_level": 0.14, "dry_level": 0.88, "width": 0.85})],
  2123	    # M8 DnB — tight, snappy, no big space.
  2124	    "M8":  [("Compressor",   {"threshold_db": -14.0, "ratio": 2.5, "attack_ms": 5, "release_ms": 60}),
  2125	            ("Reverb",       {"room_size": 0.20, "damping": 0.6, "wet_level": 0.10, "dry_level": 0.92, "width": 0.85})],
  2126	    # M9 Glitch / IDM — phaser + ping-pong delay + small room.
  2127	    "M9":  [("Phaser",       {"rate_hz": 0.4, "depth": 0.40, "centre_frequency_hz": 1300, "feedback": 0.20, "mix": 0.30}),
  2128	            ("Delay",        {"delay_seconds": 0.143, "feedback": 0.25, "mix": 0.20}),
  2129	            ("Reverb",       {"room_size": 0.30, "damping": 0.4, "wet_level": 0.15, "dry_level": 0.88, "width": 1.0})],
  2130	    # M10 Cinematic — large hall, gentle high-shelf air.
  2131	    "M10": [("Reverb",       {"room_size": 0.90, "damping": 0.35, "wet_level": 0.45, "dry_level": 0.65, "width": 1.0}),
  2132	            ("HighShelfFilter", {"cutoff_frequency_hz": 9000, "gain_db": +2.0, "q": 0.7}),
  2133	            ("LowShelfFilter", {"cutoff_frequency_hz": 90, "gain_db": +1.0, "q": 0.7})],
  2134	    # M11 Lofi — vinyl warmth: tape saturation, mid-room reverb, top-end roll-off, slow chorus wow-wobble.
  2135	    "M11": [("Distortion",   {"drive_db": 6.0}),
  2136	            ("HighShelfFilter", {"cutoff_frequency_hz": 5500, "gain_db": -3.0, "q": 0.7}),
  2137	            ("Chorus",       {"rate_hz": 0.4, "depth": 0.30, "centre_delay_ms": 22, "feedback": 0.10, "mix": 0.25}),
  2138	            ("Reverb",       {"room_size": 0.40, "damping": 0.7, "wet_level": 0.22, "dry_level": 0.82, "width": 0.85})],
  2139	    # M12 Chillout — wide chorus, plate reverb, presence boost, dotted-eighth delay.
  2140	    "M12": [("Chorus",       {"rate_hz": 0.5, "depth": 0.40, "centre_delay_ms": 18, "feedback": 0.10, "mix": 0.30}),
  2141	            ("Delay",        {"delay_seconds": 0.450, "feedback": 0.20, "mix": 0.18}),
  2142	            ("Reverb",       {"room_size": 0.65, "damping": 0.5, "wet_level": 0.32, "dry_level": 0.75, "width": 0.95}),
  2143	            ("HighShelfFilter", {"cutoff_frequency_hz": 6000, "gain_db": +1.0, "q": 0.7})],
  2144	    # M13 Simple — barely-there room reverb. Lets the silence breathe.
  2145	    "M13": [("Reverb",       {"room_size": 0.20, "damping": 0.5, "wet_level": 0.10, "dry_level": 0.92, "width": 0.85})],
  2146	    # M14 Gameboy — chiptune: light drive, bit-crush-ish high-shelf cut, no reverb (DMG had none).
  2147	    "M14": [("HighShelfFilter", {"cutoff_frequency_hz": 8000, "gain_db": -4.0, "q": 0.7}),
  2148	            ("Distortion",   {"drive_db": 2.0}),
  2149	            ("Reverb",       {"room_size": 0.10, "damping": 0.4, "wet_level": 0.04, "dry_level": 0.96, "width": 0.6})],
  2150	}
  2151	
  2152	
  2153	def apply_fx(samples: np.ndarray, sample_rate: int, mood: str) -> np.ndarray:
  2154	    """Apply the mood's FX chain + master bus. samples: (n, 2) float32 in [-1, 1].
  2155	
  2156	    Chain order: mood-specific plugins → master bus (HPF + low-shelf cut +
  2157	    presence shelf). The master bus is mood-independent and corrects the
  2158	    GM-soundfont's tendency to dominate the low band.
  2159	    """
  2160	    try:
  2161	        from pedalboard import (
  2162	            Pedalboard, Reverb, Delay, Chorus, Phaser, Compressor, Distortion,
  2163	            LowShelfFilter, HighShelfFilter, HighpassFilter,
  2164	        )
  2165	    except ImportError:
  2166	        return samples
  2167	
  2168	    cls_map = {
  2169	        "Reverb": Reverb, "Delay": Delay, "Chorus": Chorus, "Phaser": Phaser,
  2170	        "Compressor": Compressor, "Distortion": Distortion,
  2171	        "LowShelfFilter": LowShelfFilter, "HighShelfFilter": HighShelfFilter,
  2172	        "HighpassFilter": HighpassFilter,
  2173	    }
  2174	    plugins = []
  2175	    for name, kwargs in (_MOOD_FX.get(mood) or []):
  2176	        cls = cls_map.get(name)
  2177	        if cls is None:
  2178	            continue
  2179	        plugins.append(cls(**kwargs))
  2180	
  2181	    # Master bus: applied to every mood. Tames sub rumble and lifts presence
  2182	    # so spectral balance moves toward the target 25/45/30 distribution.
  2183	    plugins.extend([
  2184	        HighpassFilter(cutoff_frequency_hz=40),
  2185	        LowShelfFilter(cutoff_frequency_hz=110, gain_db=-1.5, q=0.7),

codex
Line refs below are against the pasted source blocks.

- `[Deal-breaker]` `render/midi.py:827-863,891-893` Global mutable `_VEL_JITTER_CACHE` breaks thread safety and determinism. `_VelJitter._pos` is consumed during event emission, and `render_midi()` clears the shared cache at entry. Concurrent renders can interleave or reset each other and change emitted velocities for the same `SongSpec`.
- `[Deal-breaker]` `render/audio.py:1874-1889` and `render/fx.py:2074-2077,2153-2180` The default audio path is host-dependent. `_find_soundfont()` picks the first SoundFont present on the machine, and the FX layer explicitly says pedalboard is not bit-identical across builds. If “bit-identical determinism” is meant beyond one pinned host image, this misses the goal by design.
- `[Deal-breaker]` `render/audio.py:2009-2018,2030-2037` LUFS normalization happens before FX, not after. Reverb/delay/chorus/distortion can change integrated loudness, so the final WAV is not actually normalized to `TARGET_LUFS`; it is only peak-limited afterward.

- `[Serious]` `decode.py:540-543` Infinite loop if `theory.resolve_progression()` ever returns `[]`. `looped.extend(chord_entries)` never makes progress.
- `[Serious]` `render/midi.py:809-810,1702` Lead octave policy is not implemented. `_lead_octave()` exists and mood comments say soft moods should drop to C4 / M14 to C6, but `_lead_track()` hard-codes `base_octave_midi = 72`.
- `[Serious]` `render/midi.py:1820-1827` `_find_motif()` ignores its `time_sig` argument and searches every pool in insertion order. If motif IDs ever collide across time signatures, you get wrong rhythms; even without collisions, it is a hidden data-order dependency.
- `[Serious]` `render/audio.py:2014-2018,2060-2063` Broad exception swallowing silently changes output. FX or loudness-meter failures downgrade the render with no signal, which is a determinism and observability leak.

- `[Nice-to-have]` `render/audio.py:2013-2037` No `NaN`/`inf` scrub after FX / loudness gain. If a plugin returns non-finite samples, limiter and int16 quantization proceed on bad data.
- `[Nice-to-have]` `decode.py:520-526` `mood_override` accepts any `M<digits>` token, then crashes later with `KeyError` for unknown moods. Validate up front and raise `ValueError`.
- `[Nice-to-have]` `decode.py:640-641,172-178`; `render/midi.py:899,1737-1740` Dead code: `counter_program` is assigned twice, `_pick_form()` appears unused, `_BEATS_PER_BAR` is unused, and the first `chord_tones` expression in `_lead_track()` is overwritten immediately.

Highest-priority fixes: make render-local jitter state, pin a single shipped synth/FX stack or disable non-bit-stable FX by default, and move LUFS normalization after FX.
2026-05-08T15:07:37.837292Z ERROR codex_core::session: failed to record rollout items: thread 019e081e-b339-7cb0-83f3-a32eaaa61a89 not found
tokens used
78,958
Line refs below are against the pasted source blocks.

- `[Deal-breaker]` `render/midi.py:827-863,891-893` Global mutable `_VEL_JITTER_CACHE` breaks thread safety and determinism. `_VelJitter._pos` is consumed during event emission, and `render_midi()` clears the shared cache at entry. Concurrent renders can interleave or reset each other and change emitted velocities for the same `SongSpec`.
- `[Deal-breaker]` `render/audio.py:1874-1889` and `render/fx.py:2074-2077,2153-2180` The default audio path is host-dependent. `_find_soundfont()` picks the first SoundFont present on the machine, and the FX layer explicitly says pedalboard is not bit-identical across builds. If “bit-identical determinism” is meant beyond one pinned host image, this misses the goal by design.
- `[Deal-breaker]` `render/audio.py:2009-2018,2030-2037` LUFS normalization happens before FX, not after. Reverb/delay/chorus/distortion can change integrated loudness, so the final WAV is not actually normalized to `TARGET_LUFS`; it is only peak-limited afterward.

- `[Serious]` `decode.py:540-543` Infinite loop if `theory.resolve_progression()` ever returns `[]`. `looped.extend(chord_entries)` never makes progress.
- `[Serious]` `render/midi.py:809-810,1702` Lead octave policy is not implemented. `_lead_octave()` exists and mood comments say soft moods should drop to C4 / M14 to C6, but `_lead_track()` hard-codes `base_octave_midi = 72`.
- `[Serious]` `render/midi.py:1820-1827` `_find_motif()` ignores its `time_sig` argument and searches every pool in insertion order. If motif IDs ever collide across time signatures, you get wrong rhythms; even without collisions, it is a hidden data-order dependency.
- `[Serious]` `render/audio.py:2014-2018,2060-2063` Broad exception swallowing silently changes output. FX or loudness-meter failures downgrade the render with no signal, which is a determinism and observability leak.

- `[Nice-to-have]` `render/audio.py:2013-2037` No `NaN`/`inf` scrub after FX / loudness gain. If a plugin returns non-finite samples, limiter and int16 quantization proceed on bad data.
- `[Nice-to-have]` `decode.py:520-526` `mood_override` accepts any `M<digits>` token, then crashes later with `KeyError` for unknown moods. Validate up front and raise `ValueError`.
- `[Nice-to-have]` `decode.py:640-641,172-178`; `render/midi.py:899,1737-1740` Dead code: `counter_program` is assigned twice, `_pick_form()` appears unused, `_BEATS_PER_BAR` is unused, and the first `chord_tones` expression in `_lead_track()` is overwritten immediately.

Highest-priority fixes: make render-local jitter state, pin a single shipped synth/FX stack or disable non-bit-stable FX by default, and move LUFS normalization after FX.
