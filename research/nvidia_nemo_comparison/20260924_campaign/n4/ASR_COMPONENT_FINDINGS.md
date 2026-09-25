# ASR full-bank component findings

On 2026-09-25 the strict review passed all **1,920 component cells**: A0, A1, A2
and A3 each processed the same 240 accepted scenes and both O0/O1 captures.
Each variant processed 21,787.81 seconds of saved audio. The exact numerical
coordinator and model exited before review and before the subsequent D1 launch.

The review verified source/profile/cache/index bindings, all compressed event
streams through EOF/CRC and their expanded hashes, source dispatch/tail/drain
censuses, native/raw final outputs and formatting parent/FIFO integrity. Across
the four variants it accounted for 871,600 dispatches and 1,394,419,840 source
samples. `ASR_FULL_BANK_REVIEW_V1.json` binds the full private review; it awards
zero integrated N4 cells and no Controller/widget or live-latency qualification.

| Variant | Reviewed cells | Recorded compute seconds / audio second | Maximum cell-end sampled process RSS (GiB) | First model-constructor observation (s) |
|---|---:|---:|---:|---:|
| A0 / current Sherpa baseline | 480 | 0.055 | 0.553 | 1.310 |
| A1 / realtime EOU 120M | 480 | 0.580 | 0.738 | 2.012 |
| A2 / Nemotron English 600M | 480 | 0.575 | 1.037 | 0.492 |
| A3 / Nemotron 3.5 English | 480 | 0.568 | 1.027 | 0.534 |

These are accelerated stateful ASR component observations on the admitted CPU4
placement with one model-library thread and GPU disabled. They do not compare
recognition quality or complete applications. Cell-end RSS can miss transient
peaks and includes process/runtime/cache state; it is not whole-stack physical
RAM. Constructor duration is not a cold disk/cache measurement. None of these
values qualifies a 2-GB CM5 configuration, source-paced latency or total system
throughput. All deployment tiers remain UNKNOWN at this component-report level.

`ASR_COMPONENT_REPORT_V1.json` contains unrounded values, scope and evidence
bindings. The reproducible summarizer's purpose, inputs/outputs and PowerShell,
CMD and Anaconda commands are in `README_ASR_COMPONENT_REPORT.md`. Aggregate
values were checked against all reviewed cell results. The helper exited.
Private utterance text, recordings, embeddings and model files remain outside Git.

D1/E0 followed by D1/E1 has now started under the existing supervisor, using this
accepted ASR review as its bound predecessor. `D1_FULL_BANK_STARTED_V1.json` records
the exact launch identities and first actual completed component cell; it is a
start receipt, not a terminal result. D1's full 960-cell review, modeled joint
comparison and scoring, shortlisted application/continuity runs, resource tiers
and N5 software/releases remain outstanding. See `REMAINING_EXECUTION.md` for the
dependency order and unchanged packaging/deadline limits.
