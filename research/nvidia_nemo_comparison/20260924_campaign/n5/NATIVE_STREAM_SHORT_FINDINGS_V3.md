# Short ARM64 native Nemotron protocol: both models pass within declared scope

Independent review verified A2 Nemotron Speech and A3 Nemotron 3.5 on the exact
first 256,000 PCM frames (16 seconds) of the retained saved source. Both passed
empty, one-sample, short-tail, normal source, fresh resident repeat and forced
endpoint cases. Final text and raw word objects matched exactly across the
normal/repeat streams. Nonempty final text and word objects were present; all
streams, recognizers and owned processes closed. See NATIVE_STREAM_SHORT_CHECK_V3.json.

| Model | Normal/repeat events | Normal/repeat finals | Forced events/finals | Entire six-case emulated command |
|---|---:|---:|---:|---:|
| A2 Nemotron Speech | 54 / 54 | 2 / 2 | 55 / 3 | 1,143.39 s |
| A3 Nemotron 3.5 | 90 / 90 | 2 / 2 | 91 / 3 | 1,167.49 s |

Times include the whole repeated six-case command under CPU emulation, not a
single 16-second inference, application latency or native CM5 speed. No accuracy
ranking or real-time claim follows from this tiny functional check.

The review verified 23 bound evaluator sources, unchanged binary/models/runtime,
exact PCM prefix lineage, command arguments, the unchanged strict reader and
Windows creation identities. A boot-aware local Linux audit verified the prior
owners were gone and rehashed QEMU plus all 27 runtime-manifest members. No
speech model was invoked during review. No Pi was contacted.

## Raw word-time limitation

A2's final raw word endpoints remain within this source. A3 has one final word
ending at 16,160 ms in each of the normal, repeat and forced cases: 160 ms past
the 16,000-ms source. Repeat parity therefore passes while raw source-end
containment does not. The native reader checks finite offsets and exact parity;
it does not establish alignment accuracy or clipping to source bounds. The
existing Python wrapper marks these offsets native_model_offsets_unadjusted_not_ground_truth.
No raw evidence was clipped or rewritten, and application timestamp correctness
is not qualified by this result. Keep this diagnostic for later application
mapping/EOF validation; do not infer a repair from a passing process.

## Remaining scope

The original 44.695-second A2 full-source repeat still timed out; its forced
endpoint and A3 were unattempted in that longer protocol. This short result does
not clear it. Full ARM64 Python/Tk/speaker/punctuation/GUI and integrated resource
acceptance remain unverified. N4 has two actual cells collected awaiting
acceptance, two failed and 236 unattempted, with zero accepted release profiles.
N5 remains partial. Native CM5 validation is deferred until reconnection.

The separate 34-method catalogue, six-mode clock foundation and sparse-synthetic
workload findings remain held for actual implementation and independent
real-world testing. Silence-heavy scenes cannot establish practical real-time
savings. See realtime_validation_v1/REAL_WORLD_HOLDOUT_V1.md.

Reproduction and independent review commands are in README_NATIVE_STREAM_SHORT_V3.md
and README_NATIVE_STREAM_SHORT_REVIEW_V3.md. Preserve the older full-source
attempts and their receipts. No additional model run is scheduled before the
packaging reserve; continue packaging and evidence review within the deadline.
