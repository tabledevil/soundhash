# Determinism Invariants — soundhash v1

Numbered so tests can reference them.

## Pure-function invariants

- **D1** `hash_to_spec(h, mime, "v1") == hash_to_spec(h, mime, "v1")` for any (h, mime). Idempotent.
- **D2** No reads of clock, env, filesystem (other than initial table load), network, or PRNG inside `hash_to_spec`.
- **D3** No floating-point nondeterminism: tempo and timing computed in **integer micro-BPM and integer ticks**; conversions documented.
- **D4** Every collection ordering used in decisions is a sorted-by-explicit-key list (never `set()` iteration, never `dict` insertion order assumption beyond Python 3.7+).

## HKDF invariants

- **H1** Salt is the literal byte string `b"soundhash-v1"`. Never derived.
- **H2** Every `info` argument starts with `b"soundhash/v1/"`. Enforced by helper.
- **H3** Two distinct labels never produce overlapping byte slices (HKDF guarantees this with overwhelming probability; we additionally never share a `take()` call between dimensions).
- **H4** No label appears twice in `labels.json`. CI assertion.
- **H5** No code path uses raw `hash_bytes` directly except as HKDF IKM. Hash bytes never become decision tokens.

## Modulo-bias invariants

- **M1** For every table `T`, decision is documented as either `b % len(T)` (1 byte) or `(b0<<8|b1) % len(T)` (2 bytes for len>256).
- **M2** No use of rejection sampling (would make consumption hash-dependent).
- **M3** Tables with len ∈ {2,4,8,16,32,64,128,256} use `size_pow2: true`. CI flags any new "high-fanout" table that is not power-of-2.

## Filter invariants

- **F1** Static pre-filtered tables are loaded as-is; decoder never re-filters them.
- **F2** Runtime filter functions are pure and listed in `runtime_filters.md`.
- **F3** Runtime filters output sorted lists by explicit key.
- **F4** Runtime filters never return empty: fallback to unfiltered input.
- **F5** Runtime filter inputs depend only on already-decoded fields, never on yet-to-be-decoded ones.

## Output-shape invariants

- **O1** All MIDI note pitches ∈ [21, 108] (A0..C8).
- **O2** Every layer's notes within its declared register (read from spec).
- **O3** Note duration ≥ 30 ms and ≤ bar length.
- **O4** Total wall time ≤ 30.0 s including 1 s tail.
- **O5** No two notes on the same channel start at exactly the same tick with the same pitch.
- **O6** Bass strong-beat pitches are chord tones (root/3rd/5th/7th).
- **O7** Voicing pitches are always ⊆ chord pitch-class set.
- **O8** Drum hits use only GM percussion notes [27..87].

## Distinguishability invariants

- **K1** For two random hashes h1, h2 in golden test set, MIDI SHA-256 differs in ≥99.9% of pairs.
- **K2** A 1-bit flip in hash changes ≥10 decision points downstream (not just byte 0).
- **K3** `variation_salt` (byte 31) differing alone changes per-bar surface but preserves macro structure (testable by macro fingerprint = first-8-bytes hash of (tempo,key,mode,form,progression)).

## Round-trip invariants

- **R1** `parse_midi(render_midi(spec))` recovers note events bit-equal to `spec.bars`.
- **R2** WAV output byte-identical across runs given pinned synth + sample rate + bit depth + channel count.
- **R3** `extract_shsh_chunk(wav_bytes).hash == sha256(file_bytes)`.

## Forward-compat invariants

- **C1** Calling `hash_to_spec(h, version="v1")` from a vN library (N>1) produces identical output to v1 library.
- **C2** Adding a new HKDF label to v2 cannot change v1 output (proved by code-path isolation: `tables/v1/` and `soundhash/v1/` are sealed).
- **C3** All v1 golden vectors pass on every release.

## Negative tests

- **N1** Truncated hash (<32 B) raises `ValueError`.
- **N2** Unknown version raises `UnsupportedVersionError`.
- **N3** Tampered tables (bundle_hash mismatch) raise on import.
- **N4** Missing label in registry raises at table-build CI time.

## Property-based generators (Hypothesis)

- Generate random 32-byte hashes; assert all O*, R* invariants.
- Generate hash pairs differing in 1 random bit; assert K2.
- Generate identical hash pairs; assert D1.
- Generate hashes restricted to identical bytes 0..30; assert K3.
