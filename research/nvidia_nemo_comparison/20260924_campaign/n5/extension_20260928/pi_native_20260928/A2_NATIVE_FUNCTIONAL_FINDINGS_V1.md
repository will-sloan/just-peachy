# Native Nemotron ASR functional passage

September29,20:14UTC: the original44.6954375-second saved file now completes on CM5 twice in one resident ASR process, with nonempty text, exact repeated canonical events and natural destruction/shutdown. This is component functionality and resource evidence; not speech accuracy, real-time capacity, full conformance or B02/N5 acceptance. The original rc5 app remained active and unchanged.

| Check | Result and boundary |
|---|---|
| Fresh metadata candidate build | 5.60s native compilation; source/patch/hash/ELF/envelope reviewed, no models |
| V3,1280MiB virtual | Loaded887.51MiB encoder, reached193-node initialization graph;157.81MiB scheduler allocation aborted. OS owners closed; no RESULT or clean app finalization |
| V4,1536MiB virtual | First2s twice, same single empty-text final event, EOF/post-finish/closure; not speech passage |
| Full original source/repeat | 715127samples and87events per session;86nonempty text publications, exact event equality; no accuracy score |
| First/repeat duration | 78.542/77.096s for44.695s audio; workloadRTF1.757/1.725, slower than real time |
| Full memory | Kernel peak966.047MiBRSS; sampled virtual1388.156MiB, kernel sampledVmPeak1418.891MiB; different sampling scopes |
| Lifecycle | Reset source origins, idempotent EOF, rejected post-finish feed, recognizer destruction and natural exit0; exact owners closed |

The new A2-specific build changes metadata reservations64MiB to16MiB and adds arena measurements. It retains8192-node scheduler/95% guard, original graph cache, generic CPU, weights and model mathematics. Allocation assertions remain. Library SHA6415fb2a77aa5483bbb91e5ecaf5d58c6c3f9edbfe92575f1ab2389d6064bc1b. The short test observed at most2727graph nodes and1,005,008bytes metadata; this does not qualify every recipe/long workload. It does not reuse D1's2048/2MiB/LRU1 bounds.

The isolated1536MiB virtual admission used the user's resource-adjustment authority after a measured additional157.81MiB scheduler request. AvailableRAM1408MiB required before launch; sampled stop below192MiB availableRAM or above1152MiB processRSS. CPU2/3, total200%, one native graph thread, Tasks64,1MiB stack; full protocol600s with590s alarm. Hard virtual limits are enforced; no hard RSS/MEMCG or swap-free claim. Old failures and admissions remain unchanged. The original app has not been stopped or replaced.

The full independent reader verifies source/model/runtime hashes, actual live unit settings, source sample/time arithmetic, terminal final, event equality/nonempty passage and closure. It does not compare modified versus original runtime logits, validate forced endpoints, or establish phonetic word alignment. Saved audio is not an ASR/WER test corpus. First-load0.585s excludes lazy encoder creation; do not call that complete model-load latency. Session durations include stream creation/push/EOF and are not original1x producer tests.

## Next usable mode

Complete forced-endpoint/tail/malformed/full conformance, then compare a qualified Cortex-A76 implementation under matched resources. A sequential Sherpa-first/Nemotron refinement mode is the initial practical use of this slower-than-real-time ASR candidate. Integrated B02 adds D1/E0/GUI memory and cannot inherit isolated fit. Keep B01/B05 saved previews, quiet-source repairs, D1 ONNX frontend/cache driver and bounded recording/logging moving alongside it.

Reproduction: [build](README_A2_MEMORY_BUILD_V1.md), [V3](README_A2_NATIVE_PROBE_V3.md), [V4](README_A2_NATIVE_PROBE_V4.md), [prefix/failure review](README_REVIEW_A2_NATIVE_PROBE_V2.md), [full run](README_A2_NATIVE_FULL_V1.md), [full review](README_REVIEW_A2_NATIVE_FULL_V1.md). All include purpose/inputs/outputs/PowerShell/CMD/Anaconda steps. Private build review retains exact source diff/ELF, command exits and hash; do not overwrite bound code. Private transcript/event evidence stays out of Git.

ClosureV37:135recorded research identities closed, no active research units, microphoneclosed, both leasesfree, baselineunchanged;1,790,749,048/3,221,225,472combined output bytes. The user requested faster visibility: follow-ups changed from hourly to every10minutes, same October1 17:47:34UTC checkpoint. Distinguish actual compute, source inspection and idle time; never keep redundant jobs running just to look busy.
