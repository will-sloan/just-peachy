# Retained Windows component timing coverage

Follow-up: the original logs below remain incomplete. A fresh derivative now has independently reviewed full-file cumulative accounting and parity for both compositions; see COMPONENT_COST_FINDINGS_V1.md and COST_CHECK_SUMMARY_V1.json. This later evidence does not fill or relabel the historical missing events.

The two reviewed full-file Windows lifecycle runs cannot supply complete component-cost totals from their remaining event journals. Journal rotation removed the initial events. This audit reads existing evidence only; it does not repeat inference or change earlier correctness acceptance.

| Observation | A0 Sherpa + D1 + E0 | A2 Nemotron ASR + D1 + E0 |
| --- | ---: | ---: |
| Original saved source duration | 44.6954375 s | 44.6954375 s |
| Recorded session elapsed time, including loading/pacing/drain | 92.513439 s | 94.0502975 s |
| Retained publication sequence | 1376–2575 | 789–2071 |
| Retained events | 1,200 | 1,283 |
| Retained E0 cost events / actual lifecycle E0 calls | 8 / 20 | 14 / 20 |
| Retained D1 cost events | 39 | 51 |
| Sum of retained D1 call times only | 69.7809002 s | 82.4198079 s |
| Sum of retained E0 call times only | 0.2399608 s | 0.3949007 s |
| Complete per-component compute RTF | Unavailable | Unavailable |

The retained sequence ranges have no interior gaps or duplicate sequence numbers. Their missing prefixes still prevent whole-run accounting. The partial sums cover different portions of the runs and cannot establish an A0-versus-A2 speed difference. D1's retained calls alone took substantial wall time; neither these partial totals nor session elapsed time quantify complete isolated D1 cost, thread CPU consumption, optimized speed or native Pi performance. Concurrent lane times must not be added and treated as session elapsed time.

The audit recognizes the A0 `research_asr_full_dispatch_cost` field; A2 uses a different dispatch event, so absence of that field for A2 does not mean zero ASR work. This reader deliberately leaves full component RTF unavailable rather than estimating missing calls.

Source inspection also shows that `N2Engine._accept_activity` returns early for a non-final update without output frames. A complete D1 counter must include every native push and finish, including those calls. Increasing retained log volume alone would not fix that accounting gap.

Next implementation should use a fresh derivative with bounded cumulative call counts, accepted sample counts, wall-call time and errors for D1, E0 and backend-specific ASR. Persist totals separately from rotating journals. Separate model load, native processing, orchestration/event work, source pacing and final drain; retain actual availability times and backlog observations. Check counter conservation and unchanged full-file caption/time/activity behavior before using the counters for matched B00/B01/B02 and sustained dense-speech studies. Keep existing inference/drain gates unchanged. This instrumentation is a next action, not yet an implemented feature.

Private receipt: `local/n5/research-extension-20260928/RETAINED_COST_AUDIT_V1.json`, 5,877 bytes, SHA256 `ca3e201feaaec9c7ddd19bacf3b6dccb7c99c54889a449b1256399d44637fafa`. It binds the exact independent reviews, phase results, retained journals and reader source. `README_RETAINED_COSTS_V1.md` documents purpose, inputs, outputs and PowerShell/CMD/Anaconda commands. Raw captions and events remain private. This is a coverage finding, not N4/N5 acceptance or an additional performance benchmark.
