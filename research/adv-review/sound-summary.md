# SOUND-DESIGN Adversarial Review — Summary

**Reviewers:** codex (gpt-5.4) — completed. gemini — HTTP 429 quota exhausted, no usable output.
**Single-reviewer caveat:** disagreements section below is empty; this summary reflects codex only.
**Sources:** `src/soundhash/render/fx.py`, `src/soundhash/render/audio.py`, `src/soundhash/decode.py::_GM_PALETTE`.
**Note:** showcase/showcase.md does not exist on disk (only sample wav/mid files in showcase/).

---

## Top 5 sound-design changes (ranked)

1. **Band-limit every wet path.** Insert HPF 180–250 Hz and LPF 6–8 kHz inside reverb/delay sends (or filter the wet output) on all moods. Time-based FX are currently full-range full-mix inserts — they amplify exactly the worst parts of MS Basic SF3 (low-mid pad fog and brittle fake top). Codex calls this the single highest-leverage change.
2. **Re-tune the master EQ to fight the real problem bands.** Replace `LowShelf -1.5 dB @ 110 Hz` + `HighShelf +1.5 dB @ 4.5 kHz` with cuts at 200–400 Hz (bass+pad mud) and 2.5–4.5 kHz (plasticky GM upper-mid). Current 40 Hz HPF and 110 Hz shelf address a band MS Basic doesn't actually misbehave in. The +4.5 kHz shelf also partially undoes deliberate darkening in M2/M7/M11/M14.
3. **Clean `_GM_PALETTE`.** Specifically: drop GM 82 (Calliope) as a regular lead — toy/nasal on MS Basic; drop GM 87 (Bass+Lead) as M8 bass — mid-forward, weak foundation; use GM 102 (FX7 Echoes) in M9 sparingly; reduce reliance on pads 89/91/94/95 across `comp`/`counter`/`pad` (they collapse mood identity into "ROMpler wallpaper").
4. **Rebuild M6, M8, M10 chains** — descriptor/chain mismatches.
   - M6 "sidechain pump" is actually `Reverb -> Compressor(-16 dB, 3:1, 8/80 ms)` flattening the bus and pumping reverb tails. Needs gain-keyed ducking on a 1/4-note LFO on pads only.
   - M8 "snappy DnB" with `Compressor(attack 5 ms)` clips transients before the room reverb — invert order or remove.
   - M10 "cinematic" stacks `Reverb 0.90/0.45 wet` + `+2 dB @ 9 kHz` + `+1 dB @ 90 Hz` + global `+1.5 dB @ 4.5 kHz` smile = trailer cliché on top of giant hall.
5. **Reconcile pipeline reality with comments.** `fx.py` docstring claims FX are post-LUFS, but `audio.py:_postprocess_wav` applies FX **before** `_normalise_loudness` (good thing — but fix the docstring). Also: the limiter is a sample-peak scaler, not the "8x oversampled true-peak limiter" the brief described. Either implement true-peak (e.g. `pedalboard.Limiter` with oversampling, or scipy resample-then-clip) or stop calling it one. Loudness norm happening after FX means muddy ambience gets boosted to consistent audibility rather than self-masking.

## Worst-offender mood FX chains

- **M0 (Ambient):** big plate (room 0.85, wet 0.40) + chorus (mix 0.25, depth 0.35) on full mix → wash, with only -1 dB @ 110 Hz cleanup. Will turn to mush.
- **M1 (Ballad):** `LowShelf +1.5 dB @ 200 Hz` after a medium hall — the exact frequency where GM warm pads + bass go tubby.
- **M3 (Downtempo):** Chorus(depth 0.45, 18 ms) → Delay(375 ms) → Reverb on stereo bus = preset-demo smear; bass definition collapses.
- **M5 (Synthwave):** Chorus + 214 ms delay + plate, applied to a palette already dominated by GM 80/81/84 = karaoke-synthwave cliché.
- **M9 (Glitch/IDM):** Phaser centred at 1300 Hz, mix 0.30 on the whole mix scoops the intelligibility band; delay/reverb decorate the resulting hole.
- **M10 (Cinematic):** smile EQ on top of room 0.90 / wet 0.45 hall; muddy + cliché simultaneously.
- **M14 (Gameboy):** comment says "no reverb (DMG had none)" but chain still has `Reverb(wet=0.04)`. Reads as GM-with-EQ, not chiptune. Either set wet=0 or drop the plugin.
- **M2 counter** duplicates `comp` exactly `(4, 5, 11)` — not counterpoint, role aliasing.

## GM palette specific calls

- **80/81 (Square/Saw lead):** defensible.
- **82 (Calliope):** not defensible as a regular lead on MS Basic — toy/nasal.
- **80/81/82 spread:** too narrow — two are the same lead family + one novelty.
- **Pads 88/89/90/91/94/95:** overused, and they leak into `comp` and `counter` roles across M0–M10, collapsing mood identity. 89 (Warm Pad) and 91 (Choir Pad) are the worst stock-GM shorthand offenders; 94 (Halo) and 95 (Sweep) are preset-label cliché.
- **M6 comp including 81 (Saw Lead):** fights the lead band instead of supporting harmony.
- **M5 (80/81/84 across comp/lead/counter):** spectrally overcrowded.
- **M9 102 (FX7 Echoes) across comp/lead/counter:** gimmick-on-gimmick on a stock GM font.

## Single highest-leverage trick

Band-limit reverb/delay returns to roughly **200 Hz – 7 kHz** (HPF 180–250 Hz, LPF 6–8 kHz, optional dip around 300 Hz). Higher impact than any further master EQ tweak.

## Disagreements between reviewers

None to report — gemini returned HTTP 429 (quota exhausted) and produced no usable critique. Codex stands alone. **Recommend re-running gemini once quota resets to obtain a second opinion, particularly on the M14 chiptune chain and the master EQ band-targeting (where a second perspective is most valuable).**

## Overall paragraph

The pipeline's biggest sound-design problem is treating per-mood FX as full-range full-mix bus inserts on top of a stock GM soundfont — every reverb/delay/chorus/phaser carries MS Basic's two ugliest regions (200–400 Hz pad fog, 2.5–4.5 kHz plasticky upper-mid) into a louder, wider, more decorated version of itself. The master EQ "smile" (HPF 40, LowShelf 110, HighShelf 4.5k) is targeted at frequencies that aren't the actual failure mode and partially fights the mood-specific darkening in M2/M7/M11/M14. The `_GM_PALETTE` compounds this by leaning on a small set of ROMpler-cliché pads (89/91/94/95) across multiple roles per mood, plus a few outright bad picks (Calliope 82 lead, Bass+Lead 87 as M8 bass, FX7 102 stacked in M9). The single most cost-effective fix is to band-limit every wet path aggressively before adjusting anything else. Pipeline-claim hygiene is a secondary issue: docstrings and the brief describe a post-LUFS / true-peak setup that the code does not actually implement.
