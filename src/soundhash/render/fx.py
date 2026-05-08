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
}


def apply_fx(samples: np.ndarray, sample_rate: int, mood: str) -> np.ndarray:
    """Apply the mood's FX chain. samples: (n, 2) float32 in [-1, 1]."""
    chain = _MOOD_FX.get(mood)
    if not chain:
        return samples
    try:
        from pedalboard import (
            Pedalboard, Reverb, Delay, Chorus, Phaser, Compressor, Distortion,
            LowShelfFilter, HighShelfFilter,
        )
    except ImportError:
        return samples

    cls_map = {
        "Reverb": Reverb, "Delay": Delay, "Chorus": Chorus, "Phaser": Phaser,
        "Compressor": Compressor, "Distortion": Distortion,
        "LowShelfFilter": LowShelfFilter, "HighShelfFilter": HighShelfFilter,
    }
    plugins = []
    for name, kwargs in chain:
        cls = cls_map.get(name)
        if cls is None:
            continue
        plugins.append(cls(**kwargs))
    board = Pedalboard(plugins)
    # pedalboard expects (channels, samples) for multi-channel float32 in [-1,1].
    return board(samples.astype(np.float32), sample_rate)
