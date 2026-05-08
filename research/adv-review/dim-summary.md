# soundhash — Adversarial Review of 14 Research Dimensions vs Implementation

Workspace: `research/adv-review/`. Inputs: `DESIGN.md` (351 lines), `src/soundhash/` (~1500 LOC), 14 research summaries, `assets/v1/*.json` (58 tables), `tests/test_label_registry.py`.

## TL;DR

The macro pipeline (mood → tempo → key → mode → form → progression → drums/bass/comp/lead → render → LUFS) is fully wired and within-arch deterministic on the bundled host. Below the macro layer the implementation diverges meaningfully from spec: roughly **11 of 18 declared HKDF labels are unused**, **2 unregistered labels are already live**, the **CI test that would catch both is `@pytest.mark.skip`**, and several signature features the research itself flagged as highest-leverage (accent skeleton, voicing-style byte, true counter-melody modes, clutter budget, drone clash, articulation matrix, humanization profiles, decorrelation IRs, ISP true-peak limiter) are stubbed or absent.

## Per-dimension audit

(Full table in `/tmp/dim-audit.md`. Grades: ✓ wired / ⚠ partial / ✗ stub.)

| # | Dim | Status | One-line gap |
|---|---|---|---|
| 01 | Key & Mode | ⚠ | mode names selected; `must_include` / `must_avoid` enforcement absent; `harmony/modulation` unused |
| 02 | Tempo & Groove | ⚠ | grooves wired but `time_sig="4/4"` and `swing="straight"` are hardcoded constants in `decode.py:598`; byte-5 joint pick missing |
| 03 | Form & Energy | ⚠ | forms+curves OK; `activation_matrix_id="band_basic"` is a hardcoded constant — byte 25 not consumed |
| 04 | Harmony & Voicing | ⚠ | progression OK; **byte 8 (voicing style + sec-dom + mixture) entirely unused**; `harmony/substitutions` declared, never read |
| 05 | Drums & Fills | ⚠ | kits + density-pair OK; **byte 12 (escalation/de-escalation algo) unused** — single fill at section ends only |
| 06 | Bass | ⚠ | patterns+mutations OK; **bass.top ≤ melody.bottom − M3 hard rule not enforced**; `synth_id` declared, GM still wins |
| 07 | Comping | ⚠ | comp role + chord-rhythm OK; **comp.top ≤ melody.median − 5 hard rule not enforced**; strum/arp/chord-rhythm dispatch not role-aware |
| 08 | Melody | ✗ | **accent skeleton (the research's named highest-distinguishability feature) entirely missing**; phrase shapes table not loaded; only 4 of 9 mutation operators |
| 09 | Aux Layers | ⚠ | **5 of 12 layer types implemented**; counter-melody is parallel-3rd ONLY; clutter budget not enforced; drone clash check absent |
| 10 | MIDI Expression | ⚠ | velocity stream + a fixed CC11/bend OK; **articulations (19), humanization profiles (6), `cc_routing.json` all unused**; no synth capability matrix; no RPN fine-tune marcato |
| 11 | MIME → Mood | ⚠ | family detection OK; `magic.mgc` SHA pinning absent; `--mime=strict` is theatre (cli.py:23 still falls back); spec says `M0..M10` but assets+code use `M0..M14` |
| 12 | Rendering | ✗ | pedalboard ≠ pinned-IR convolution; **no ISP true-peak oversampled limiter**; no sfizz path; no curated `soundhash_curated_v1.sf2` (host MS-Basic.sf3 only); `synth_pool.json` declared, code uses `_GM_PALETTE` constant |
| 13 | Hash Architecture | ✗ | `test_all_labels_used_in_code_are_registered` is `@pytest.mark.skip`; no rejection sampling anywhere despite spec promising it for distinguishability-critical picks; `aux/earcandy/main/<i>` and `form/section/<letter>` live but unregistered |
| 14 | Perceptual Determinism | ⚠ | within-arch byte-identity holds on the bundled host only; **no Docker canonical**, no cross-arch ViSQOL run, **no decorrelation IRs**, **no iXML/bext/ID3v2.4 metadata**; FTZ/DAZ/FMA flags not in any visible build script |

## Adversarial-pass synthesis (codex round 1+2; gemini errored 0 bytes)

**Most under-realized:** #08 Melody (accent skeleton), #04 Harmony (byte-8 voicing/sec-dom/mixture), #12 Rendering, #13 Hash-architecture contract. Codex agrees #08 is the single biggest perceptual-bump opportunity — the spec itself names it the highest-distinguishability feature per byte and `melody/accent_skeleton` is even reserved in the HKDF registry.

**Architectural contradiction codex caught beyond the table:** `SongSpec` docstring promises renderers "make no decisions of their own," yet `render/midi.py` derives fresh HKDF velocity-jitter and ear-candy choices at render time (decode is no longer the single decision authority). Spec also says `--mood=<M0..M10>`; code implements `M0..M14`.

**HKDF label registry:** theatre. Runtime never validates; CI test skipped; ~11 of 18 declared labels unused; 2 used labels unregistered.

## Three concrete <100-LOC fixes (codex round 2)

### 1. Accent skeleton (`src/soundhash/render/midi.py`, ~70–90 LOC)

- `def _apply_accent_skeleton(motif_onsets, contour_samples, chord_pcs, hkdf_byte) -> list[int]`
- HKDF: `melody/accent_skeleton` (already registered, never read)
- Tables: `assets/v1/melody/accent_skeleton.json` (to add: 8 micro-shapes), existing `meter_accents.json`
- Loop: 1 byte → row of skeletons → 4 two-bit strong-beat selectors → on each strong cell force `{R,3,5,7}` of current chord; off-cells get micro-shape perturbation then nearest-allowed scale-subset snap. Existing `melody_invert`/`melody_transpose` runs after anchoring.

### 2. Harmony byte 8 (`src/soundhash/decode.py`, ~80–95 LOC)

- `def _apply_harmony_byte8(s, macro8, progression, chord_entries, key_root, mode, mood) -> (chord_entries, voicing_style_id, sec_dom, mixture)`
- HKDF: `harmony/substitutions` (already registered, never read)
- Tables: existing `harmony/progressions.json` + `harmony/voicings.json`; new `harmony/mixture_fallbacks.json`
- Body: bits 0-3 of byte 8 → voicing style index; bit 4 + sub-stream toggle → secondary-dominant slot rewrite (`V7/x` becomes `dom7` rooted at target+P5); bit 5 + sub-stream toggle → mixture-on/off swap from fallback table. Stash result on `comp.extra`.

### 3. Counter-melody modes + clutter budget (`src/soundhash/render/midi.py`, ~85–95 LOC)

- `def _counter_mode_and_cap(spec, bar_idx) -> (mode_str, cap_int)`
- HKDF: existing `macro` (byte 23 high nibble) + `perbar/aux/<i>` (already used)
- Table: existing `aux_layers.json` (already has `counter_melody.modes` + `clutter_budget.tiers`)
- Body: pick mode from `{parallel_3rd, parallel_6th, contrary, call_response}`; per-bar count already-live non-exempt aux layers; skip if cap exhausted; in `contrary` mirror around chord anchor then snap; in `call_response` only fill lead gaps ≥ rest_threshold; clamp to register, vel < lead.

## Recommendations

1. **Un-skip `test_all_labels_used_in_code_are_registered`** and either consume the 11 stale labels or delete them. Add the 2 unregistered live labels to `labels.json` first.
2. **Land the accent-skeleton patch** before any further mood-tuning work — it is the single cheapest distinguishability win, and the research dimension already specified the bytes.
3. **De-hardcode `time_sig`/`swing`** in `decode.py:598` — joint byte-5 pick is a one-line table lookup once `groove_overlays.json` exposes the joint table.
4. **Replace `activation_matrix_id="band_basic"`** with a byte-25 lookup into the (already-built) 16 layer-activation matrices.
5. Treat #12 rendering chain (sfizz, curated SF2, pinned-IR reverb, ISP limiter, Docker canonical) as a single milestone before any v1-freeze claim. Current pedalboard chain is "best-effort, not bit-identical" by its own admission.
