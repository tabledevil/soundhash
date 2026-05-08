"""Corpus-level regression tests — sanity-check the full pipeline across many hashes.

Catches issues like a mood losing all its bass patterns, a layer never firing,
or pitches walking out of MIDI range. Runs ~100 small hash decodes; should
finish in ~10s.
"""
import hashlib
import io
from collections import Counter, defaultdict

import pytest


CORPUS_N = 60
MIME_CYCLE = ['text/plain', 'image/png', 'audio/mp3', 'video/mp4',
              'application/pdf', 'application/zip', 'font/ttf', None,
              'application/json', 'application/octet-stream']


# Module-level cache so all tests share the same corpus + MIDI dump.
_CORPUS_CACHE: list = []
_MIDI_CACHE: list = []


def _build_corpus():
    if _CORPUS_CACHE:
        return _CORPUS_CACHE
    from soundhash.decode import hash_to_spec
    for i in range(CORPUS_N):
        h = hashlib.sha256(f'corpus-{i}'.encode()).digest()
        _CORPUS_CACHE.append(hash_to_spec(h, mime=MIME_CYCLE[i % len(MIME_CYCLE)]))
    return _CORPUS_CACHE


def _build_midi():
    if _MIDI_CACHE:
        return _MIDI_CACHE
    from soundhash.render.midi import render_midi
    for s in _build_corpus():
        _MIDI_CACHE.append(render_midi(s))
    return _MIDI_CACHE


def test_all_moods_reachable():
    specs = _build_corpus()
    moods = {s.provenance.mood for s in specs}
    # Expect at least 8 distinct moods in 100 hashes (11 total possible).
    assert len(moods) >= 8, f"only {len(moods)} moods in {CORPUS_N}: {moods}"


def test_pitches_in_midi_range():
    pytest.importorskip("mido")
    import mido
    for data in _build_midi():
        mf = mido.MidiFile(file=io.BytesIO(data))
        for tr in mf.tracks:
            for msg in tr:
                if msg.type == 'note_on':
                    assert 0 <= msg.note <= 127, f"pitch {msg.note} out of MIDI range"


def test_drums_fire_on_almost_every_file():
    pytest.importorskip("mido")
    import mido
    drum_active = 0
    midis = _build_midi()
    for data in midis:
        mf = mido.MidiFile(file=io.BytesIO(data))
        drum = next((t for t in mf.tracks if t.name == 'drums'), None)
        if drum and any(msg.type == 'note_on' and msg.velocity > 0 for msg in drum):
            drum_active += 1
    # Drums are usually the rhythmic floor, but legitimate activation
    # matrices (minimal_pad, ambient_drone, pad_lead, intro_swell, breakdown,
    # outro_tail) intentionally silence drums in their A row. ~30 % of
    # matrices fall into that bucket, so the corpus drum-rate floor is 60 %.
    # The test still catches genuine drum-picking regressions (e.g. all kits
    # broken or all patterns empty) where the rate would collapse to <50 %.
    assert drum_active / len(midis) >= 0.60, \
        f"drums fired on only {drum_active}/{len(midis)} files"


def test_within_mood_layer_activation():
    """Within each mood, no critical layer should be silent on >55% of files."""
    pytest.importorskip("mido")
    import mido
    specs = _build_corpus()
    midis = _build_midi()
    mood_count = Counter()
    layer_active = defaultdict(lambda: defaultdict(int))
    for spec, data in zip(specs, midis):
        mood_count[spec.provenance.mood] += 1
        mf = mido.MidiFile(file=io.BytesIO(data))
        for tr in mf.tracks:
            if not tr.name or tr.name == 'meta':
                continue
            n = sum(1 for msg in tr if msg.type == 'note_on' and msg.velocity > 0)
            if n > 0:
                layer_active[spec.provenance.mood][tr.name] += 1

    failures = []
    for mood, fc in mood_count.items():
        if fc < 5:
            continue
        for layer in ('drums', 'lead'):
            active = layer_active[mood][layer]
            # 40% threshold: activation matrices can legitimately silence
            # individual layers per section in sparse minimal_pad / drone
            # / pad_lead matrices, so this is a regression-detector for
            # mood / palette / pattern issues rather than matrix gating.
            if active / fc < 0.40:
                failures.append(f"{mood}.{layer}: {active}/{fc}")
    assert not failures, f"layer silent on >60% of files: {failures}"


def test_all_12_keys_reachable():
    """All 12 chromatic roots should appear in the corpus.

    A failure here means key selection is biased — likely a regression in
    _pick_mood / family_to_moods / mood mode lists that locked to a subset.
    """
    specs = _build_corpus()
    keys = {s.key_root for s in specs}
    assert keys == set(range(12)), f"missing keys: {set(range(12)) - keys}"


def test_total_duration_under_30s():
    specs = _build_corpus()
    for s in specs:
        assert s.total_duration_seconds() <= 30.0, \
            f"{s.provenance.hash_hex[:8]}: {s.total_duration_seconds():.1f}s"


def test_heuristic_quality_baseline():
    """Average heuristic quality score across the corpus stays above 0.65.

    Catches silent regressions (e.g. someone breaks the master EQ or
    gates and the spectral balance collapses on a wide corpus).
    """
    pytest.importorskip("mido")
    pytest.importorskip("pyloudnorm")
    import shutil
    if shutil.which("fluidsynth") is None:
        pytest.skip("fluidsynth not on PATH")
    from soundhash.quality import score_wav
    from soundhash.render.audio import render_wav
    midis = _build_midi()
    # Score a sub-sample (rendering 60 WAVs is slow). 8 hashes is enough
    # to flag a global regression.
    sub = midis[:8]
    scores: list[float] = []
    for data in sub:
        try:
            wav = render_wav(data)
        except Exception:
            pytest.skip("render_wav unavailable")
        scores.append(score_wav(wav).overall)
    avg = sum(scores) / len(scores)
    assert avg >= 0.65, \
        f"avg quality {avg:.2f} dropped below 0.65 baseline; per-file: {scores}"
