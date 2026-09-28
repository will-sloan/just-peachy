# Campaign deadline outcome — partial

The authorized offline campaign ended at **2026-09-28 14:48:19 UTC**.
The hourly follow-up is paused. N1–N3 retain their separately scoped offline
acceptance; **N4 and N5 are incomplete**. This is deadline closure, not campaign
acceptance. No further experiment or hardware access is authorized by this
closure. Recording and backing up this outcome does not extend the experiment
window.

| Stage | Verified outcome |
|---|---|
| N1 | Complete within the agreed offline scope. |
| N2 | 422/422 evaluations; accepted offline with declared limitations. |
| N3 | Accepted offline component evidence. |
| N4 | 7,680 main and 1,536 mode modeled scores reviewed. Actual application panel: 2 collected pending acceptance, 2 failed, 236 unattempted out of 240; zero accepted cells or new release profiles. |
| N5 | Working Windows saved-file engineering previews and scoped emulated ARM64 component passes; full application and release acceptance incomplete. |

## What works and what it establishes

Windows A2 Nemotron English ASR + D1 Nemotron 3 diarization has paired
saved-file preview evidence with retained E0 ReDimNet and with anonymous
external-encoder bypass. Stable ASR input chunking and render/save/reopen/delete
checks are preserved. This is one saved-file lifecycle, not full-bank acceptance,
realtime throughput, endurance or calibrated personal naming. See
[backend guide](BACKEND_GUIDE.md) and
[preview instructions](README_D1_ANONYMOUS_PREVIEW_V1.md).

Sherpa ARM64 C-API parity passed the original four-case/repeat protocol and
eight malformed-WAV checks under explicit emulated Cortex-A76. A2/A3 passed
the six-case repeat/forced-endpoint protocol on the exact first 16 seconds of
saved PCM. The full-source A2 repeat still timed out; long A3 was not attempted.
A3 short-clip raw word timing extends 160ms beyond EOF. Short component passes
cannot clear the long-source failure, qualify source-aligned timing or establish
full ARM64 application behavior. No Pi runtime or memory tier is measured.

The reviewed engineering-bank main nonoverlap WER is 14.92% for A0 Sherpa and
13.34% for A2, a 1.58 percentage-point improvement on that population. See
[the N4 report](../n4/N4_PARTIAL_REPORT_20260927.md) for the exact scope and
[component performance report](COMPONENT_PERFORMANCE_REPORT_20260927.md) for
component and combination metrics. These results do not establish performance
on independent real conversations or the physical Pi.

## Remaining blockers and later work

1. Repair and qualify application speaker-lane drain and Controller closure.
   Both failed D1 cells exceeded the unchanged 60-second finalization drain;
   one also recorded unsuccessful Controller closure. The precise rejecting
   exception was not captured. Later process exit does not turn these into
   successful application shutdowns.
2. Complete the actual 240-cell panel, continuity and restart checks, integrated
   resource measurements, and per-build controls/import/export/failure/rollback
   qualification before accepting new release profiles.
3. Complete long-source native ASR repetition/forced endpoints and timing
   validation; execute the full ARM64 Python/Tk/speaker/punctuation/GUI stack.
4. Integrate and measure candidate pacing, workers and shadow gates. There are
   34 specified methods, six implemented source-clock modes and eight passing
   deterministic clock tests. The clock is a model-free foundation: no
   application adapter, measured optimized throughput or production skip gate
   is qualified.
5. After reconnection and later authorization, check actual CM5 storage,
   installation, GUI, CPU/RAM, thermals, clocks, long-run backlog and hardware.
   Follow [Pi reconnection quickstart](PI_RECONNECT_QUICKSTART_V1.md).

Retain A0/D1/E0 and A2/D1/E0 as priorities, with optional anonymous encoder
bypass. TitaNet work is retired and its evidence preserved. Fine-tuning remains
assessment only. Silence-heavy synthetic scenes can overstate skipping savings:
freeze configurations and use matched ungated, source-paced controls on held-out
dense, natural-pause, quiet/short, overlap and noisy speech. No tokens is not
proof of silence. Read the mandatory
[real-world holdout requirements](realtime_validation_v1/REAL_WORLD_HOLDOUT_V1.md).

## Preserved deliverables and verification

The immutable V7 analysis handoff remains:
`NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign_20260928_v7.zip`,
179,217 bytes, 59 members, SHA-256
`43887860a863a87f56da18d2b413efc891470f754fb5339fc6ee8b9e8a029a5c`.
It is an analysis package, not a complete installer. The baseline core archive
and small Pi reconnection companion remain separately scoped; see
[artifact index](ARTIFACT_INDEX.json) and
[V7 checkpoint instructions](README_CHECKPOINT_V7.md).
This deadline addendum is separate from the frozen ZIP; earlier evidence and
source commits are preserved.

Final checks rehashed N2/N3 acceptance, current status and V7 ZIP, and confirmed
the exact three campaign PID creation identities absent. The unrelated Windows
WSL service was left untouched. Free space was 111.64 GiB on C and 92.34 GiB on
G. Before this addendum, local and GitHub branch
`codex/n1-foundation-20260924` matched commit
`cbf0135c0b59e2ecd1e59e806564aba12fb50307` with a clean worktree.
The closure commit and remote verification are recorded privately under
`local/n5/deadline-close-20260928-v1/` after publication.

[Machine-readable closure](CAMPAIGN_DEADLINE_20260928.json) records the
nonacceptance state. No private audio, profiles, weights or raw transcripts are
included in this documentation commit. There was no Pi contact, new capture,
playback, training, enrollment or desktop input takeover.
