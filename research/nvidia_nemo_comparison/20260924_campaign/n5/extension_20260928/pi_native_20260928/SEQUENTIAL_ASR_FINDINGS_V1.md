# Native sequential Sherpa and Nemotron ASR: saved-source handoff passes

September30 01:19UTC. Independent status: `PASS_NATIVE_SEQUENTIAL_SHERPA_A2_SAVED_SOURCE_ONLY`. This new coordinator first publishes Sherpa text at original1x saved-input pacing, waits for that exact process to close, then starts generic A2 Nemotron on the same full source. Primary and refined transcripts remain separate immutable private revisions. No microphone, playback, D1, E0, PnC or GUI ran.

Both stages accepted all715127samples from the original44.6954375s file. The independent reader compared all51Sherpa and87A2 canonical events with their retained references exactly, excluding only availability clocks; source hashes and final outputs match. This checks functional correspondence, not ASR accuracy or better transcript quality. The previously failed A76 candidate was not used. Existing installed/staged assets were reused without copies.

| Stage | Source-processing wall time | CPU time including phase work | Peak process RSS |
|---|---:|---:|---:|
| Sherpa, original1x pacing | 44.789s | 8.079s | 276.703MiB |
| Generic Nemotron A2, unpaced refinement | 79.049s | 78.989s | 966.297MiB |

Whole coordinator128.553s includes model setup/process transitions; the phase times exclude some setup. Maximum coordinator publication delivery20.284ms is measured after model publication, not acoustic caption latency. A2 remains slower than real time. No improvement over a matched benchmark is claimed; original rc5 remains active. Model process lifetimes are demonstrably disjoint, avoiding simultaneous Sherpa/A2 residency. Sampled main+child RSS peaked972.812MiB; this is not hard RSS enforcement or combined A2/D1 fit.

The coordinator exposes TRANSCRIBING, PRIMARY_READY, REFINING and COMPLETE plus explicit failure states. Five negative state checks reject premature refinement, unsafe/alive-owner completion, changed source and silent retry; failed refinement retains the primary. Actual GUI controls/cancellation and application archives are not integrated. Sherpa EOF adds its unchanged0.66s padding; it is not counted among source samples. A2 uses the qualified1280sample push/native EOF path. All four exact research owners close naturally; actual CPU2/3/200%,Tasks64,1MiB stacks, per-process AS caps and300s unit were verified. No capture/route/baseline changes occurred.

Private22file/226,949byte backup verified; target originals preserved. ClosureV83: all195Pi/44isolated host owners closed, capture closed, leases free; combined4,341,407,476/5GiB. Fixed32GBPi free17,893,818,368bytes, available RAM1,582,514,176bytes, closure temperature55.1C andthrottled=0x0. Global swap3049in/35519out is contextual only; these are closure observations, not peak thermal or swap-free evidence.

Next: bind the explicit revisions/state events to the actual controller and GUI, including cancellation/failure and archive controls, under a fresh admission. Separately finish actual source startup/controller isolation before changed quiet B01 and diagnose alternate D1 state mismatch without relaxing its1e-5 gates. Full live, physical GUI, endurance, integrated B02 and field/N4/N5 release acceptance remain open.

Execution: [sequential README](README_SEQUENTIAL_ASR_V1.md). Independent reader: [review README](README_REVIEW_SEQUENTIAL_ASR_V1.md). Private sequential-asr-v1-evidence/REVIEW.json/BACKUP.json and NATIVE_CLOSURE_V83/NATIVE_RESOURCES_V83 retain source, ownership and resource evidence.
