"""Render-side smoke + determinism tests."""
import hashlib

import pytest

from soundhash.decode import hash_to_spec


def _h(s: bytes) -> bytes:
    return hashlib.sha256(s).digest()


def test_midi_render_is_deterministic():
    mido = pytest.importorskip("mido")
    from soundhash.render.midi import render_midi

    spec = hash_to_spec(_h(b"determinism-1"))
    a = render_midi(spec)
    b = render_midi(spec)
    assert a == b, "MIDI rendering must be byte-identical for same SongSpec"


def test_midi_render_varies_per_hash():
    mido = pytest.importorskip("mido")
    from soundhash.render.midi import render_midi

    a = render_midi(hash_to_spec(_h(b"file-a")))
    b = render_midi(hash_to_spec(_h(b"file-b")))
    assert a != b, "different hashes must produce different MIDI"


def test_midi_has_expected_track_count():
    mido = pytest.importorskip("mido")
    import io
    from soundhash.render.midi import render_midi

    spec = hash_to_spec(_h(b"x"))
    data = render_midi(spec)
    mf = mido.MidiFile(file=io.BytesIO(data))
    assert mf.type == 1
    assert mf.ticks_per_beat == 480
    assert len(mf.tracks) >= 2  # meta + at least one music track


def test_audio_render_deterministic_when_fluidsynth_available():
    import shutil
    if shutil.which("fluidsynth") is None:
        pytest.skip("fluidsynth not on PATH")
    from soundhash.render.audio import render_wav
    from soundhash.render.midi import render_midi

    spec = hash_to_spec(_h(b"audio-test"))
    midi = render_midi(spec)
    try:
        a = render_wav(midi)
        b = render_wav(midi)
    except RuntimeError as e:
        pytest.skip(f"render_wav unavailable: {e}")
    assert a == b
    assert len(a) > 1000  # not empty
    # Quick sanity: WAV length ≤ 32 s of stereo 16-bit @44.1k = 32*44100*4 + header.
    assert len(a) < 32 * 44100 * 4 + 1024


def test_midi_total_length_within_30s():
    mido = pytest.importorskip("mido")
    import io
    from soundhash.render.midi import render_midi

    for seed in (b"a", b"b", b"c", b"d"):
        spec = hash_to_spec(_h(seed))
        mf = mido.MidiFile(file=io.BytesIO(render_midi(spec)))
        assert mf.length <= 30.0, f"{seed!r}: {mf.length:.2f}s exceeds 30s"
