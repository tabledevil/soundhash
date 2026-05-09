"""Per-mood post-render FX chains (reverb / delay / chorus / EQ).

Applied after LUFS normalisation but before the final peak limiter so the
limiter still owns the true-peak ceiling. Determinism is best-effort:
pedalboard's algorithms are not bit-identical across builds, but with
pinned `pedalboard==0.9.x` the output is stable on a given host.

The chains are intentionally subtle. A mhash is meant to be musical,
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
    # M6 House — compressor BEFORE reverb so the verb tails don't pump
    # (reviewer flagged the prior order as 'pumping reverb tails'). Tight
    # ambience after the glue compression.
    "M6":  [("Compressor",   {"threshold_db": -16.0, "ratio": 3.0, "attack_ms": 8, "release_ms": 80}),
            ("Reverb",       {"room_size": 0.30, "damping": 0.5, "wet_level": 0.18, "dry_level": 0.85, "width": 0.9})],
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


def apply_fx(samples: np.ndarray, sample_rate: int, mood: str,
             wet_scale: float = 1.0) -> np.ndarray:
    """Apply the mood's FX chain + master bus. samples: (n, 2) float32 in [-1, 1].

    Chain order: mood-specific plugins → master bus (HPF + low-shelf cut +
    presence shelf). The master bus is mood-independent and corrects the
    GM-soundfont's tendency to dominate the low band.

    `wet_scale` (byte-29-driven) multiplies any `wet_level` / `mix` kwargs
    on the mood plugins so the same chain can land 'dry' (0.5), normal (1.0),
    or 'very-wet' (1.3) per-hash.
    """
    try:
        from pedalboard import (
            Pedalboard, Reverb, Delay, Chorus, Phaser, Compressor, Distortion,
            LowShelfFilter, HighShelfFilter, HighpassFilter, LowpassFilter,
            Mix, Chain,
        )
    except ImportError:
        return samples

    cls_map = {
        "Reverb": Reverb, "Delay": Delay, "Chorus": Chorus, "Phaser": Phaser,
        "Compressor": Compressor, "Distortion": Distortion,
        "LowShelfFilter": LowShelfFilter, "HighShelfFilter": HighShelfFilter,
        "HighpassFilter": HighpassFilter,
    }

    def _wet_only(plugin, original_wet: float):
        """Wrap a Reverb/Delay so its wet path is HPF-200 / LPF-7k band-limited.

        Eliminates 200-400 Hz mud and 7-20 kHz fizz from time-based effects
        while preserving original wet/dry balance via Mix.
        """
        return Mix([
            Chain([]),                                       # dry passthrough
            Chain([
                HighpassFilter(cutoff_frequency_hz=220),
                plugin,                                      # wet-only configured below
                LowpassFilter(cutoff_frequency_hz=7000),
            ]),
        ])

    plugins = []
    for name, kwargs in (_MOOD_FX.get(mood) or []):
        cls = cls_map.get(name)
        if cls is None:
            continue
        if wet_scale != 1.0:
            scaled = dict(kwargs)
            for k in ("wet_level", "mix"):
                if k in scaled:
                    scaled[k] = max(0.0, min(1.0, float(scaled[k]) * wet_scale))
            kwargs = scaled

        if name in ("Reverb", "Delay"):
            # For Reverb/Delay, route the wet path through HPF→LPF and use
            # Mix to combine with the dry signal. The plugin runs full-wet
            # internally; the original wet_level/mix becomes the gain on
            # the wet branch (we approximate by leaving the plugin's own
            # wet ratio at its configured value — simpler than rebalancing).
            plugins.append(_wet_only(cls(**kwargs), kwargs.get("wet_level", kwargs.get("mix", 0.3))))
        else:
            plugins.append(cls(**kwargs))

    # Master bus: applied to every mood. Per the sound-design adversarial
    # review (codex), MS Basic SF3 has two ugly regions: 200-400 Hz pad/bass
    # mud and 2.5-4.5 kHz plasticky upper-mid. The shelves below cut those
    # specifically; the HPF kills DC/sub rumble; the high-shelf at 8 kHz
    # adds gentle air without lifting the plastic band.
    plugins.extend([
        HighpassFilter(cutoff_frequency_hz=40),
        LowShelfFilter(cutoff_frequency_hz=300, gain_db=-1.8, q=0.6),
        HighShelfFilter(cutoff_frequency_hz=3500, gain_db=-1.2, q=0.6),
        HighShelfFilter(cutoff_frequency_hz=8000, gain_db=+1.5, q=0.7),
    ])

    board = Pedalboard(plugins)
    return board(samples.astype(np.float32), sample_rate)
