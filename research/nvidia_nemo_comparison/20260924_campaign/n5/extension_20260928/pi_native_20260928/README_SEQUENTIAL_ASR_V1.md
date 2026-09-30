# Native sequential Sherpa and Nemotron refinement candidate

Purpose: implement an explicit two-stage saved-source workflow. Sherpa publishes initial text at original1x input pacing. After its process has exited and exact owner is absent, generic A2 Nemotron processes the same complete file without pacing and publishes a separate refinement. The primary transcript remains immutable and available. This is a reusable coordinator/state contract with event callbacks, not yet the production GUI, live microphone route, diarization/B02 mode, endurance or quality acceptance.

Inputs: pinned original715127sample/16k PCM16 WAV; unchanged installed Sherpa encoder/decoder/joiner/tokens; already qualified generic A2 metadata16/8192scheduler/95%guard/originalcache libraries, Q8 weights and ABI adapter. Assets are reused by exact absolute path and SHA256, with no copies/downloads or original installation changes. The A76 candidate is excluded. Fresh WINDOW_V5 census and target admission bind all code/assets/reference events.

States: IDLE, TRANSCRIBING, PRIMARY_READY, REFINING, COMPLETE; explicit PRIMARY_FAILED/REFINEMENT_FAILED. A2 cannot begin while Sherpa is alive or without a completed primary revision. Five invalid-transition checks include alive-owner, changed-source, premature refinement and implicit retry rejection. A failed refinement keeps the primary result; there is no silent backend substitution. Each publication carries backend/source timing; coordinator receipts add delivery time. The two event/revision files stay distinct and retain original chronology. No ASR accuracy scoring, merged transcript quality claim, PnC, E0 or D1 runs.

One actual model process at a time under the same CPU2/3,total200%,Tasks64 unit. Main hardAS1536MiB; Sherpa child768MiB; A2 child1536MiB;1MiB stacks/one model thread/GPUoff. These are per-process virtual caps, not aggregate memory enforcement. Initial1408MiB available; repeated before A2,850MiB before Sherpa. Sampled owned main+child RSS1152MiB or availableRAM below192MiB stops the service; kernel lacks MEMCG. Shared baseline remains active. Runtime300s/main alarm290s, each child175s alarm/180s coordinator bound,10s service stop. Abnormal forced child closure is a failure. Save actual unit properties and exact owner lifetimes. Disk5GiB reserve on the fixed32GB device,32MiB combined output reservation split16MiB target/host,8MiB per-file hard bound,2MiB per event stream/JSON helper,4MiB service log. Existing evidence/usage is retained.

Protocol: one complete Sherpa phase then one complete A2 phase, with exact equality to their retained canonical reference events (only availability clocks excluded). This new handoff/lifetime check is not a repeat benchmark. Sherpa's original0.66s EOF padding is recorded as padding, not source audio. A2 uses1280sample feeds, native EOF and idempotent finish. Require all715127source samples in each phase, nonempty text, distinct artifacts, natural process exits, exact source hash unchanged and nonoverlapping process lifetimes. The standard-library independent reader must compare the events itself and verify live envelope, state transitions, publication delivery, quotas and baseline/lease closure.

Outputs: private sequential-asr-v1 admission, live envelope, source-bound phase logs/events/results, coordinator state/publication events, exact owners, output/resource receipts. Public reports contain metrics only. Both primary/refinement transcripts remain private. No microphone, playback or standalone new audio file. New source and README become immutable when dispatched; use a new version for corrections.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/sequential_asr_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V82.json
```
CMD / Anaconda Prompt (explicit interpreter, no activation required):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\sequential_asr_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V82.json
```
Use a fresh unused census less than15minutes old and unused fixed run ID. Gate/worker/child flags are internal admitted entry points. Host census/coordinator usesCPU14. Review before acceptance; a launcher or exit0 alone is not qualification. Private evidence backup must verify file hashes and preserve target originals.
