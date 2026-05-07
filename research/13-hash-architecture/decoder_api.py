"""
soundhash v1 decoder API — pseudocode signature + invariants.
This is documentation, not runnable. Real implementation lives elsewhere.
"""

from dataclasses import dataclass
from typing import Optional
import hashlib
import hmac

# ---------------------------------------------------------------------------
# HKDF (RFC 5869) over SHA-256
# ---------------------------------------------------------------------------

def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt, ikm, hashlib.sha256).digest()

def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    out, t, counter = b"", b"", 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        out += t
        counter += 1
    return out[:length]

# ---------------------------------------------------------------------------
# Stream API — never advance a "global tape"; always derive per-label
# ---------------------------------------------------------------------------

class HashStream:
    def __init__(self, prk: bytes, version: str = "v1"):
        self._prk = prk
        self._version = version

    def take(self, label: str, n: int) -> bytes:
        info = f"soundhash/{self._version}/{label}".encode("ascii")
        return hkdf_expand(self._prk, info, n)

    def pick(self, label: str, table: list) -> object:
        b = self.take(label, 1)[0]
        return table[b % len(table)]

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SongSpec:
    version: str
    hash_prefix: str
    tempo_bpm: float
    time_sig: tuple
    key_root: int
    mode: str
    form: list
    bars: list
    layers: list
    render: dict

def hash_to_spec(
    hash_bytes: bytes,
    mime: Optional[str] = None,
    version: str = "v1",
    *,
    file_bytes: Optional[bytes] = None,
) -> SongSpec:
    """Pure function. Same inputs → same SongSpec.

    Invariants (asserted in tests):
      I1  hash_to_spec(h) == hash_to_spec(h)                 # idempotent
      I2  no I/O, no time, no system randomness
      I3  bundle_hash(tables/v1) == MANIFEST.bundle_hash     # tamper check
      I4  every label used appears in labels.json
      I5  all pitches ∈ [21,108]; per-layer registers honored
      I6  total wall time of rendered output ≤ 30.0 s
      I7  bit-flip in hash → spec changes (≥99.9% of flips)
      I8  spec.version == version (caller's choice)
      I9  variation_salt only XORs into per-bar streams; never macro
      I10 runtime filters never return empty (fallback to input)
    """
    assert len(hash_bytes) == 32
    if version != "v1":
        raise UnsupportedVersionError(version)

    prk = hkdf_extract(salt=b"soundhash-v1", ikm=hash_bytes)
    s = HashStream(prk, version)

    macro = s.take("macro", 32)
    salt = macro[31]

    # Walk the constraint tree top-down.
    mood = pick_mood(macro[0], macro[1], mime)
    tempo = pick_tempo(macro[2], mood)
    key_root = macro[3] % 12
    mode = MODES[macro[4] % len(MODES)]
    ts, swing = TIMESIG_SWING[macro[5] % 8]
    form_tpl = FORMS[macro[6] % 16]
    progression = pick_progression(macro[7], mood, mode)
    voicings = load_voicings(mode, key_root)         # static pre-filtered
    voicing_style = voicings[macro[8] % len(voicings)]
    # ... and so on, every dim consumes from `s.take(label,n)` ...

    bars = []
    for i, target_chord in enumerate(progression):
        bar_seed = s.take(f"perbar/melody/{i}", 4)
        # XOR variation salt into per-bar bytes for surface variation
        bar_seed = bytes(b ^ salt for b in bar_seed)
        bars.append(build_bar(i, target_chord, voicing_style, bar_seed, s))

    return SongSpec(
        version=version,
        hash_prefix=hash_bytes[:4].hex(),
        tempo_bpm=tempo, time_sig=ts, key_root=key_root, mode=mode,
        form=form_tpl, bars=bars, layers=[], render={},
    )

# ---------------------------------------------------------------------------
# Renderers (dumb consumers)
# ---------------------------------------------------------------------------

def render_midi(spec: SongSpec) -> bytes:
    """No decisions. Iterate spec.bars and emit MIDI. Byte-stable."""

def render_wav(spec: SongSpec, midi: bytes) -> bytes:
    """Drive pinned synth (FluidSynth+SF or sfizz). Byte-stable given pinned versions."""
