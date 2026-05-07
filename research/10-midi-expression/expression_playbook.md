# Per-layer expression playbook

| Layer | Humanization | Velocity curve typical | Articulations allowed | Pitch bend | CC routing |
|---|---|---|---|---|---|
| Drums (ch10) | machine (groove-loose if live-drums tag) | drum-table (own dim) | default only | NEVER | CC10 pan static, CC91/93 sends |
| Bass | groove-tight | 3 backbeat-rock / 9 syncopated-funk / 11 arp-pulsing | 0,1,3,4,5,6,15 | mood ∈ {trap,dub,reggaeton}: scoop/slide; else off | CC74 wobble in dub |
| Comp/Pad | groove-loose / acoustic-lively | 7 ballad-swell / 14 sustained-pad | 0,3,7,10,11,15 | off | CC11 phrase-arc REQUIRED, CC91 high, aftertouch->CC11 fallback |
| Lead synth mono | groove-tight | 13 phrase-arc / 12 motif-emphasis | 0,1,2,5,6,7,9,15,16,17,18 | scoop on phrase-start, expressive on long notes | CC1 vibrato (long notes), CC74 sweeps, portamento toggles |
| Lead piano/EP | acoustic-lively | 7 ballad-swell / 13 phrase-arc | 0,1,3,4,5,6,7,8,9,15 | NEVER | CC64 lift-on/press-after, no CC1 |
| Strings orch | acoustic-lively / ballad-rubato | 7 / 13 | 0,3,5,6,7,10,11,12,13,14,15 | small expressive bends only | CC11+CC1 paired, CC2 if breath, key-switches required |
| Brass | acoustic-lively | 5 beat1 / 6 beat14 / 12 motif | 0,1,3,5,6,7,10,11,12,15,16,17,18 | falls/doits/scoops via tail bends | CC1 vibrato on long notes |
| Counter-melody | groove-tight | 10 arp-flowing | 0,1,3,5,15 | off | minimal |
| Drone/FX | machine (frozen) | 14 sustained-pad / 2 flat-piano | 0,15 | off | slow CC11/CC74 LFOs |
