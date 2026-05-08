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


def _pick_activation_matrix(byte: int, form_id: int) -> dict:
    """Pick a layer-activation matrix that's compatible with the form.

    Filters out matrices whose A row silences the lead — for a 30-second
    soundhash a lead-silent matrix produces a melody-less output across
    the whole song, which is uniformly drab. Section-specific intro/outro
    matrices (which only fire on those section letters) can still be
    picked because they're whitelisted via compatible_forms.
    """
    try:
        data = tables.load("layer_activation")
    except FileNotFoundError:
        return {}
    matrices = data.get("matrices", [])
    if not matrices:
        return {}
    layers = data.get("layers", []) or [
        "drums", "bass", "comp", "lead", "counter", "drone", "fx_riser", "ad_lib",
    ]
    lead_idx = layers.index("lead") if "lead" in layers else 3

    def _has_lead_in_A(m: dict) -> bool:
        rows = m.get("rows", {})
        a_row = rows.get("A") or (list(rows.values())[0] if rows else [])
        return len(a_row) > lead_idx and a_row[lead_idx] != "-"

    form_eligible = [m for m in matrices if not m.get("compatible_forms")
                     or form_id in m.get("compatible_forms", [])]
    if not form_eligible:
        form_eligible = matrices
    # Prefer matrices that don't silence the lead. Fall back to all if none.
    melody_eligible = [m for m in form_eligible if _has_lead_in_A(m)]
    eligible = melody_eligible or form_eligible
    eligible = sorted(eligible, key=lambda m: m.get("id", 0))
    return eligible[byte % len(eligible)]


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
    # Lead palettes expanded to 5-8 candidates per mood for "main voice variety".
    # Per sound-design adv review: dropped GM 82 Calliope and reduced 87 reliance.
    "M0":  {"bass": (32,),               "comp": (88, 89, 91),       "lead": (54, 75, 73, 91, 11, 70),   "pad": (88, 89, 94),    "counter": (52, 73, 71)},
    "M1":  {"bass": (32, 33),            "comp": (0, 4, 24),         "lead": (73, 71, 56, 68, 41, 11),   "pad": (89, 91, 95),    "counter": (52, 73, 68)},
    "M2":  {"bass": (33, 34, 36),        "comp": (4, 5, 11),         "lead": (80, 81, 28, 4, 5, 6),      "pad": (89, 95, 91),    "counter": (52, 73, 25)},   # counter de-aliased from comp
    "M3":  {"bass": (33, 36),            "comp": (4, 5, 88, 89),     "lead": (80, 73, 78, 4, 5, 11),     "pad": (89, 91, 94),    "counter": (73, 71, 4)},
    "M4":  {"bass": (32, 35),            "comp": (24, 25, 32),       "lead": (56, 11, 24, 73, 12, 25),   "pad": (89, 91, 94),    "counter": (24, 56, 11)},
    "M5":  {"bass": (38, 39, 33),        "comp": (81, 89, 80),       "lead": (81, 80, 84, 87, 88, 89),   "pad": (90, 89, 94),    "counter": (88, 81, 89)},
    "M6":  {"bass": (38, 39, 36),        "comp": (16, 17, 81),       "lead": (80, 81, 53, 87, 89, 84),   "pad": (90, 89, 95),    "counter": (53, 89, 84)},
    "M7":  {"bass": (38, 39),            "comp": (81, 89, 90),       "lead": (80, 81, 87, 88, 89, 90),   "pad": (90, 94, 89),    "counter": (89, 90, 81)},
    "M8":  {"bass": (38, 39, 36),        "comp": (89, 88, 91),       "lead": (81, 80, 88, 84, 90, 87),   "pad": (89, 91, 94),    "counter": (89, 81, 53)},   # bass 87 dropped per adv-review
    "M9":  {"bass": (38, 39, 87),        "comp": (90, 91, 102),      "lead": (88, 81, 102, 87, 100, 99), "pad": (95, 91, 94),    "counter": (102, 88, 91)},
    "M10": {"bass": (32, 43, 44),        "comp": (48, 49, 50, 89),   "lead": (60, 73, 71, 11, 49, 91),   "pad": (49, 51, 94),    "counter": (49, 51, 73)},
    # M11 lofi: warm Rhodes / EP / soft pads.
    "M11": {"bass": (33, 32, 35),        "comp": (4, 5, 0, 24),      "lead": (4, 5, 11, 73, 71, 26),     "pad": (89, 91, 94),    "counter": (4, 5, 73)},
    # M12 chillout: smooth pads + soft reeds + mellow synths.
    "M12": {"bass": (32, 33, 38),        "comp": (88, 89, 91, 4),    "lead": (73, 71, 75, 91, 89, 11),   "pad": (89, 91, 95),    "counter": (52, 91, 73)},
    # M13 simple: piano + acoustic, sparse.
    "M13": {"bass": (32, 33),            "comp": (0, 4, 24),         "lead": (0, 73, 11, 24, 71, 25),    "pad": (89, 88),        "counter": (4, 73, 11)},
    # M14 gameboy: GM approximations of NES/GB chips. Calliope dropped per
    # adv-review; replaced with extra Square + Clarinet (triangle-ish).
    "M14": {"bass": (38, 39, 80),        "comp": (80, 81, 71),       "lead": (80, 81, 88, 84, 99, 38),   "pad": (90, 88, 95),    "counter": (80, 71, 81)},
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


# 4 mix-balance presets per byte 30. Values are CC7 channel-volume targets
# (0-127). Drums use ch10, others use the per-layer channels we set in spec.
_MIX_PRESETS = [
    # 0 balanced — workmanlike default
    ("balanced",     {"drums": 110, "bass": 100, "comp": 85, "lead": 100,
                      "pad": 70, "counter": 80, "drone": 60,
                      "riser": 95, "ear_candy": 75}),
    # 1 bass-forward — hip-hop / house feel
    ("bass_forward", {"drums": 100, "bass": 118, "comp": 75, "lead": 90,
                      "pad": 60, "counter": 70, "drone": 55,
                      "riser": 90, "ear_candy": 70}),
    # 2 lead-forward — synthwave / cinematic feel
    ("lead_forward", {"drums": 90, "bass": 90, "comp": 75, "lead": 120,
                      "pad": 75, "counter": 95, "drone": 60,
                      "riser": 95, "ear_candy": 80}),
    # 3 minimal — sparse / lofi feel
    ("minimal",      {"drums": 80, "bass": 90, "comp": 65, "lead": 95,
                      "pad": 55, "counter": 65, "drone": 70,
                      "riser": 85, "ear_candy": 65}),
]


def _pick_mix_preset(byte: int) -> tuple[str, dict]:
    name, levels = _MIX_PRESETS[byte % len(_MIX_PRESETS)]
    return name, dict(levels)


def _pick_phrase_shape(byte: int) -> str:
    """Pick a phrase-shape id (e.g. 'ps_AABA', 'ps_period_4_4').

    Currently surfaced on the SongSpec but not yet driving render
    behaviour — the form's section_letters do most of the work.
    Reserved for future per-phrase mutation patterns.
    """
    try:
        data = tables.load("melody/phrase_shapes")
    except FileNotFoundError:
        return "ps_AABA"
    shapes = data.get("shapes", []) or []
    if not shapes:
        return "ps_AABA"
    return shapes[byte % len(shapes)].get("id", "ps_AABA")


def _pick_humanization_profile(byte: int) -> dict:
    try:
        data = tables.load("expression/humanization_profiles")
    except FileNotFoundError:
        return {"name": "groove-tight", "vel_jitter": 4}
    profs = data.get("profiles", [])
    if not profs:
        return {"name": "groove-tight", "vel_jitter": 4}
    return profs[byte % len(profs)]


_ESCALATION_CACHE: dict | None = None


def _escalation_algos() -> tuple[list, list]:
    global _ESCALATION_CACHE
    if _ESCALATION_CACHE is None:
        try:
            data = tables.load("drums/escalation_algorithms")
            _ESCALATION_CACHE = (data.get("escalation", []), data.get("deescalation", []))
        except FileNotFoundError:
            _ESCALATION_CACHE = ([], [])
    return _ESCALATION_CACHE


def _pick_escalation_algos(byte: int) -> tuple[str, str]:
    """Byte 12 split: high nibble = escalation algo, low nibble = de-escalation."""
    esc, deesc = _escalation_algos()
    e_id = esc[(byte >> 4) % len(esc)]["id"] if esc else ""
    d_id = deesc[(byte & 0x0F) % len(deesc)]["id"] if deesc else ""
    return e_id, d_id


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

    # Byte 1: 4 sub-flavors per mood — subtle modulations layered on top of the
    # mood's macro character. Same mood, different "shade".
    #   sub 0: stock        (no nudge)
    #   sub 1: brighter     (+2% tempo, smaller reverb)
    #   sub 2: darker       (-3% tempo, lead -12, larger reverb)
    #   sub 3: tighter      (+1% tempo, smaller reverb)
    sub_flavor = macro[1] & 0x03
    tempo = _pick_tempo(macro[2], mood)
    tempo_nudge = {0: 1.0, 1: 1.02, 2: 0.97, 3: 1.01}[sub_flavor]
    tempo = round(tempo * tempo_nudge, 2)
    key_root = macro[3] % 12
    mode = _pick_mode(macro[4], mood)
    progression = _pick_progression(macro[7], mood, mode)
    # Byte 8: pick voicing style from progression's allowed list. Was unused.
    allowed_voicings = progression.get("allowed_voicing_styles") \
        or [progression.get("default_voicing_style", "close_triad")]
    voicing_style = allowed_voicings[macro[8] % len(allowed_voicings)]

    # Resolve progression to per-bar chord entries.
    chord_entries = theory.resolve_progression(progression, key_root, mode)

    # Form first — its layout determines bar count, then we cap by what fits
    # in 30 seconds at the chosen tempo (leave 2 s for reverb tail).
    beats_per_bar = 4
    max_bars_for_30s = max(2, int(28.0 * tempo / (60.0 * beats_per_bar)))
    form = _pick_form_unconstrained(macro[6], max_bars_for_30s, mood)
    target_bars = _bars_from_layout(form, default_n=8, cap=max_bars_for_30s)

    # Loop the progression to fill target_bars.
    if not chord_entries:
        # Fallback: a single bar of the tonic. Should not happen with the
        # curated table but guards against a runtime infinite-loop.
        chord_entries = [{"rn": "I", "quality": "maj", "root_pc": key_root,
                          "root_midi": (3 + 1) * 12 + key_root,
                          "chord_pcs": [0, 4, 7], "bass_inversion": 0}]
    looped = []
    while len(looped) < target_bars:
        looped.extend(chord_entries)
    looped = looped[:target_bars]
    energy_curve = _pick_energy_curve(macro[24], form, mood)
    groove_id = _pick_groove_template(macro[5], mood)
    section_letters = _expand_form_layout(form, target_bars)
    activation_matrix = _pick_activation_matrix(macro[25], form.get("id", 0))
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
    esc_algo, deesc_algo = _pick_escalation_algos(macro[12])
    humanization = _pick_humanization_profile(macro[27])
    mix_preset_id, mix_preset = _pick_mix_preset(macro[30])
    # Wet-level scales clamped to 1.15 max — 1.3 was over-saturating reverb
    # tails on already-wet moods (cinematic, ambient) and pulling LUFS down.
    fx_wet_scale = (0.6, 0.9, 1.0, 1.15)[macro[29] & 0x03]
    phrase_shape_id = _pick_phrase_shape(macro[21])
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
                      "esc_algo": esc_algo,
                      "deesc_algo": deesc_algo,
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
        LayerSpec(name="counter", midi_channel=4,
                  synth_id=("counter/" + ["parallel_3rd","parallel_6th","contrary","octave_below"][macro[31] & 0x03]),
                  program=counter_program, pattern_id=melody_motif.get("id", ""),
                  extra={
                      "motif_id": melody_motif.get("id", ""),
                      "contour_id": melody_contour.get("id", ""),
                      "scale_subset_id": melody_scale.get("id", ""),
                      # 4 counter-melody modes selected by 2 bits of byte 31:
                      #   0=parallel_3rd, 1=parallel_6th, 2=contrary, 3=octave_below.
                      "counter_mode": ["parallel_3rd","parallel_6th","contrary","octave_below"][macro[31] & 0x03],
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
        activation_matrix_id=activation_matrix.get("name", "band_basic"),
        groove_template_id=groove_id,
        voicing_style=voicing_style,
        sub_flavor=sub_flavor,
        humanization_profile=humanization.get("name", "groove-tight"),
        humanization_vel_jitter=int(humanization.get("vel_jitter", 4)),
        mix_preset_id=mix_preset_id,
        mix_levels=mix_preset,
        fx_wet_scale=fx_wet_scale,
        phrase_shape_id=phrase_shape_id,
        bars=bars,
        layers=layers,
        bar_energies=bar_energies,
        section_motif_ids=section_motifs,
        section_contour_ids=section_contours,
        section_comp_pattern_ids=section_comp_pats,
        activation_rows=dict(activation_matrix.get("rows", {})),
        render=RenderHints(),
    )
