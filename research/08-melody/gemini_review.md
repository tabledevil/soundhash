Ripgrep is not available. Falling back to GrepTool.
Here is the adversarial critique of Dimension #08 (Melody):

**1. Contour-Rhythm Misalignment (The `N=1` Problem)**
Sampling a continuous contour function (like `arch` or `v_shape`) to $N$ points breaks catastrophically for sparse motifs. If a motif has only 1 or 2 onsets (e.g., `long_held` or `half_dot_q`), mapping `t∈[0,1]` is undefined or destroys the contour's identity. 
*Fix:* Contour tables must be pre-filtered by motif density. A contour requiring a peak and a return needs $N \ge 3$. 

**2. Tessitura Clamping Destroys Contour**
The resolver states it "clamps any pitch outside tessitura by octave-shifting toward centre." If a `climbing_seq` contour hits the upper bound, octave-shifting the next note down abruptly turns a rising line into a jagged, confusing leap, breaking the melodic phrase and confusing the listener.
*Fix:* Do not clamp at runtime. Pre-filter the allowed contour/mutation combinations based on the initial tessitura and octave offset so that the natural melodic bounds never exceed the permitted range.

**3. Parallel Fifths Guard is Missing**
The parallel guard explicitly checks `pitch_pc == bass_pc` for two consecutive notes, which only prevents parallel octaves/unisons. It completely fails to catch parallel fifths (`pitch_pc == (bass_pc + 7) % 12`), which are equally destructive to classical/melodic voice independence.
*Fix:* Expand the anti-parallel guard in the resolver to detect when `(pitch_pc - bass_pc) % 12 == 7` across consecutive notes.

**4. Ambiguous Chord-Boundary Onsets**
The phrase shapes define `chord_change_handling: land|approach|common_tone`, but motifs are rhythm cells that may not have an onset exactly on the chord change beat (e.g., syncopated motifs like `charleston` or `off_beat_8ths`). Forcing an anchor on a non-existent `chord_onset_beat` is impossible without mutating the rhythm.
*Fix:* The table-builder must strictly pair motifs with harmonic-rhythms (Dim #04). If the harmonic rhythm changes chords on beat 3, the motif *must* have an onset on beat 3 to use `land`, otherwise fallback to `common_tone` via a tied note.

**5. Non-Deterministic `augment` Operator**
The definition for `augment` says "×2 durations (may halve count to fit bar)". "May halve count" is not an algorithm. If you augment `long_short_long` (1.5, 0.5, 2) in 4/4, you get (3.0, 1.0, 4.0). Simply truncating it to fit the bar discards the phrase ending, leaving unresolved harmonic tension.
*Fix:* `augment` should only be allowed on motifs whose total duration $\le$ 0.5 bars, OR it should strictly mean "spread this motif across two bars" (which requires phrase-plan awareness so it doesn't collide with the next cell).

**6. Retrograde vs. Phrase Anchors Collision**
"Retrograde... when phrase-end anchor must hold (overrides retrograde)". If you reverse the sequence of scale degrees but force the final note to jump to a specific root anchor, you risk introducing an enormous, unmusical leap at the cadence.
*Fix:* Retrograde should only reverse the *rhythm*, leaving the pitch contour forward-moving so the cadence resolves naturally, or retrograde should be disabled on any phrase-ending bar.

**7. Perceptual Waste on Secondary Entropy (Byte 31)**
Byte 31 is allocated to "ornament direction, sequence sign". This consumes an entire byte of hash budget for a micro-detail that is perceptually indistinguishable to most listeners (e.g., an upper vs. lower mordent). In a 30-second identifier, broad strokes matter more.
*Fix:* Roll sequence sign and ornament direction into the mutation seed (Byte 26) via HKDF, and free Byte 31 for something structurally obvious (e.g., a secondary instrument doubling the melody at the octave).

**8. Scale Subset vs. Mode Collision**
If Dim #1 picks Phrygian (which has a b2) and Byte 18 picks `penta_major` (which requires a natural 2), the resolver has contradictory instructions. The document claims "mode" is a pre-filter, but a hardcoded `penta_major` array `[1,2,3,5,6]` cannot adapt to Phrygian.
*Fix:* Scale subsets must be defined entirely as bitmasks over the active mode (e.g., "drop the 2nd and 6th degrees of the current mode"), rather than absolute scale degrees.
