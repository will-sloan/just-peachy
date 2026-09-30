# Saved sequential ASR controller and GUI candidate

Purpose: extend the actual application Controller command queue and portrait PrototypeUI with a saved-file Sherpa primary and explicit after-stop Nemotron refinement. Primary and refinement text remain separate. The new page provides Transcribe, Refine, Cancel, Save and Reopen. It is an experimental saved-source extension, not a live B02 mode or installed field release. Existing application files and earlier implementations remain unchanged.

Inputs: the admitted original 715127-sample, 16 kHz PCM16 file; installed pinned Sherpa assets; the qualified generic A2 Q8 model, ABI and metadata16/8192-scheduler libraries. The A76 candidate is excluded. The derivative reuses the hash-bound compact-archive application under b01-quiet-artifact-v1/prototype and adds process-local subclasses. It never opens a microphone, plays audio or loads D1, PnC or speaker models. No accuracy scores follow from this protocol.

The Controller owns one model subprocess at a time. Cancel requests a cooperative stop between inference calls; ownership persists until the child exits. A cancelled refinement retains the completed primary artifact and discards the partial refinement from the displayed accepted result. Raw partial events and cancellation evidence remain private. Retry is explicit. Source hashes, successful-result hashes and event hashes are checked on refinement and archive reopening. Save writes a new immutable revision manifest. Mode/start/enrollment changes are rejected while a child is owned. Backend failures remain explicit; abnormal forced termination is not a cancellation pass.

The native protocol invokes real queued commands and actual withdrawn Tk widgets. It completes Sherpa, rejects premature refinement and busy controls, cancels A2 after a publication, explicitly retries A2, and checks separate text, unchanged primary bytes, Save/Open and source-mismatch rejection. Full successful event sequences must equal retained canonical references exactly. Cancelled publications must remain an exact reference prefix. It does not qualify all backend-load failures, arbitrary file selection, visible layout, physical touch, live capture, endurance or general archive import/export. The window remains withdrawn and unmapped throughout.

Resources: CPUs 2/3, shared 200% quota, TasksMax64, one model thread, GPU off, 1 MiB stacks; main/A2 hard address space 1536 MiB, Sherpa child 768 MiB. Initial available RAM 1408 MiB; before Sherpa 850 MiB and before A2 1408 MiB. Sampled aggregate owned RSS above 1152 MiB or available RAM below 192 MiB stops the unit. These are not hard aggregate RAM limits; MEMCG is unavailable. Runtime 300 seconds, main alarm 290, protocol 245, each child alarm 175/coordinator 180, service stop 10. Fixed 32 GB Pi storage retains at least 5 GiB free. The 32 MiB combined output reservation is split 16 MiB target and 16 MiB host; files have an 8 MiB hard limit, individual JSON/event paths have 2 MiB application bounds. Existing output usage is retained under WINDOW_V5. Original app stays active, so timings are conditional.

Outputs are private sequential-gui-v1 receipts: admission, live unit envelope, exact owners, three phase directories (primary, cancelled refinement, successful refinement), publication records, immutable save manifests, GUI text snapshot, results and resource samples. A separate reader must verify events, lifetimes, ownership, archives and bounds, then back up every target file by hash without removing originals. No transcript or audio belongs in Git.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/sequential_gui_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V106.json
```

CMD or Anaconda Prompt (explicit interpreter; no environment activation needed):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\sequential_gui_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V106.json
```

Use an unused run ID and census less than 15 minutes old, generated with host coordinator CPU14. Dispatcher checks exact baseline identities, all prior owners, leases, storage, target-inclusive budgets and source hashes. Gate, worker, child and protocol entry points are internal to the admission. Do not run them directly or rerun a bound run. Once dispatched, preserve these files and use fresh versions for corrections. Runtime imports `controller_class` and `ui_class` from the two extension modules; `sequential_asr_child_v2.py` adds cooperative cancellation to the original phase worker. `sequential_asr_envelope_v1.py` is reused unchanged.
