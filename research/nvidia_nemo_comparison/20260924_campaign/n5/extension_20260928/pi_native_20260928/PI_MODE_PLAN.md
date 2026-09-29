# Pi-first modes and actual validation

The September 28 user instructions now prioritize ready-to-run modes on the connected CM5. Original N5 same-frontend, explicit-backend, data-preservation, install/rollback and backup requirements still apply. The user specifically excludes saved-file ASR/WER accuracy scoring: saved inputs establish execution, source coverage, text passage and resource/timing behavior only. The quiet microphone is permitted for a route check, not a speech-quality test. No new live capture has been initiated in this Pi session.

## Mode delivery order

| Mode | Intended operation | Current native evidence / gate |
|---|---|---|
| Existing Sherpa application | Preserve current rc5 install and personal data as rollback | Installed/running; separate original-paced ASR component passed saved-file passage. Existing complete GUI/live route is not requalified by this check. |
| Sherpa + Nemotron diarizer + ReDimNet | Captions immediately; labels Pending/Unknown until one ordered speaker lane supplies evidence | ASR and short D1 components run natively. Integrated new application mode, E0 combination, UI controls and sustained drain remain to qualify. First new-mode priority. |
| Delayed speaker labels | Same ASR/UI, explicitly delayed D1 using supported larger whole chunk/cache recipes | Candidate only. Must measure source mapping, cache history, EOF and actual compute savings; larger Python pushes alone are not a new native recipe. |
| On-demand identity | Compute ReDimNet only for sufficient clean/new/uncertain speech | Candidate only; retain returning-speaker/overlap checks. Anonymous bypass is a separately labelled control with no persistent personal-name claim. |
| Nemotron ASR + Nemotron diarizer + ReDimNet | All-Nemotron ASR/activity with existing identity model | Not installed/qualified on this Pi. Measure ASR load/working-set first; 2 GB is a concrete constraint. Never silently replace a selected backend or turn off speakers to make it load. |
| Two-pass session | Sherpa captions live; Nemotron ASR refinement when idle/after recording | Candidate only; load sequentially where needed, expose revisions, preserve timestamps/history and measure completion/drain. |

Use one source tree/shared front end and explicit backend manifests, separate app data for engineering checks, no research identities in personal storage. New launchers should open idle when the user invokes them and state their actual qualification level. Keep the current install pointer unchanged until a verified replacement and rollback path exist. Do not treat standalone component scripts as delivered application modes.

## Native investigation order

1. Resolve the preserved full-source D1 repeat timeout and optimized-kernel numerical differences. A 12-second pass cannot qualify history growth, steady state, full files or 30/60-minute conversations.
2. Continue from the two completed Cortex-A76 CPU builds and their preserved failed generic-probability checks; see STATUS.md. Inspect actual emitted dot-product instructions, then compare saved-input probabilities, state/timestamps and speed against the generic-kernel candidate under identical resources. Read README_A76.md. A kernel parity check is software reproducibility, not a new speech-accuracy score.
3. Package a native B01 engineering manifest on the preserved current application derivative, bind Linux library/model paths and checksums, test startup failure with no fallback, input drain/shutdown/restart, caption-first behavior, pending labels and save/reopen/delete. Independently check E0/punctuation/Tk availability and compatibility first. Preserve fixed-roster/identity provenance; do not create people or enroll voices.
4. Add only controlled supported chunk/cache, on-demand identity and caption-worker changes. Keep one ordered D1 state. Measure actual inference, gate/IPC/context overhead, source backlog slope/max/drain and explicit degraded intervals. Extra workers share the same total resource admission.
5. Compare a qualified ONNX Runtime CPU/INT8 route if a graph plus frontend/cache driver can be obtained within admitted acquisition/output limits. ORT 1.29 is installed; D1 ONNX is not. The native model is already mixed Q8 GGUF, so exporting alone is not an optimization. XNNPACK/operator coverage, ARM kernels, threading and memory must be measured. Community offline exports are not automatically streaming replacements. Current acquisition restriction remains; present a concrete asset/size/purpose if it becomes necessary.
6. Run native original-pacing, dense speech, quiet/short turns, returning speakers, overlap, jitter/bursts and 30/60-minute endurance after shorter gates. Record actual CPU/RSS, thermals/clocks/throttle, swap, caption/label latency, corrections and lost/degraded coverage. Short runs with the existing app active are diagnostics, not controlled capacity guarantees.
7. During a user-ready spoken/noisy session, freeze modes/settings and compare real XVF reference/ASR/postprocessed routes with matched gains and chronology. Separate restaurant babble, steady noise and impacts. Do not deliberately collect unrelated private conversation. Only independently labelled real speech supports new quality/accuracy claims.

The generic native source currently reserves an unnecessarily large scheduler capacity for this tested D1 graph. The bounded capacity repair is separate from CPU-kernel acceleration and model/chunk changes. Its original native run aborted under the cap; there is no measured before/after RSS or speed improvement to claim. See STATUS.md for exact observed results and preserved failures.

## Documentation and execution

This file is a plan, not executable code. Use README.md for inventory/staging, README_V2–V5.md for versioned D1 protocols, README_SCHEDULER.md for the native partial scheduler build, README_SHERPA.md for original-paced transcription passage and README_A76.md for the next CPU candidate. Each contains PowerShell/CMD/Anaconda commands, inputs and outputs. No automatic accuracy sweep, model download, training, enrollment, live capture or OS reconfiguration is authorized by these scripts.
