# Copied-recording post-run controller and UI check

Purpose: close the unexecuted Save/Open and stopped-rendering boundary from field-live-gui-v2 without another capture or model inference. Preserve that run's reporting failure. Build offline B01 v7 from its exact v5 release; only the empty-caption UI code/cache, one helper, and this documentation change. The v5 entrypoint and model/source configuration remain byte-identical. No original install or candidate pointer is activated.

`field_caption_state_v1.py` supplies state-aware empty-caption wording. `field_run_reporting_v1.py` reports absent optional counters as unavailable/null and accepts a native session path only from a completed durable epoch with matching parent and sample count. It never turns an early None into a path or invents a zero counter. The old failed harness is not modified; these corrected report paths are exercised in the new protocol. `field_postrun_protocol_v1.py` stages v6 and privately copies the completed 448320-sample recording, then uses actual installed GUI Open, Save/pin, and reopen commands. Only copied conversation metadata may change. Original epochs, events and audio must retain exact hashes. Empty rows are expected for this particular recording; the test does not supply speech labels or establish silence.

STARTING/RUNNING/STOPPING views are explicit no-capture UI snapshots. Actual controller, model loads and microphone stay idle. The real stopped view is restored before natural closure. The screenshots are visible Pi rendering, not physical touch or new hardware evidence. The test checks actual optional model counters, five rejected premature/mismatched session reports, current capture closure, and no new source receipts/session directories. No playback, enrollment, import negatives, model rerun, asset copy or download occurs. Saved audio is copied once and counted in output.

Inputs: a fresh WINDOW_V5 CPU14 census; exact source-bound field-live-gui-v2 release, private conversation, config and prior failure-aware independent review/backup; current authority and baseline identities. Output: a fresh `field-postrun-v2` Pi folder with admission/live limits, source/v6 code archive and installed candidate, copied private data, action/reporting records, snapshots, five PNGs, result and supervised resource samples. The independent reader creates `field-postrun-v2-evidence/target`, REVIEW and BACKUP privately. All prior inputs and all failed outputs are retained. No automatic deletion.

Limits: 64 MiB combined allowance, 32 MiB target and 32 MiB host backup; main 768 MiB address space, 1 MiB stacks, CPU2/3 shared200%, Tasks64, 300-second service/60-second Stop, 8 MiB per-file limit. Main UI protocol is bounded to60seconds, launch admission120seconds. Initial850MiB available RAM, sampled192MiB floor/640MiB aggregate RSS stops, fixed Pi5GiB reserve. Kernel MEMCG is absent; sampled RSS is not a hard aggregate memory cap. Original rc5 remains running. This is neither endurance nor a field release. Default hardware and research leases must be free before dispatch.

Run only against fresh unused output names after current owner/lease/space checks. The dispatcher verifies the old supervisor and all isolated D1 host owners, exact Pi boot/PID/start ticks, units, original install/config and target-inclusive budget before staging. It refuses existing run/evidence directories. Do not rerun a completed pass or change an admitted source in place.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_postrun_v2.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V136.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_postrun_v2.py
```

CMD and Anaconda Prompt use the existing environment; do not install anything:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_postrun_v2.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V136.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_postrun_v2.py
```

The reader uses strict SSH and CPU14 on the host, CPU3/256MiB on Pi, disables bytecode writes, independently verifies installed manifest/source/copy/metadata/sample/PCM hashes and actual closure, and backs up every run file with exact hashes. It does not execute models, GUI, or capture. Diagnostic helpers are imported by the protocol, not standalone microphone launchers. Rollback is simply closing this isolated candidate; no original baseline pointer/config/data is changed. Source manifests and code/config backups permit exact restoration verification before any later activation work.

## V2 correction and preserved failure

V1 completed three actual copied-data Open/Save/Open actions, then failed its first stopped-text assertion: the ActiveCaptionPane cache returned early because both row lists were empty. The new wording helper alone did not repaint a state change. V1's exact code, release v6, result, callback traceback and640-file private backup remain immutable. Its failure reader's `GUI_opened=false` tests whether PNGs existed; it does not establish that no GUI opened. The actual GUI action receipts and Tk traceback prove it opened, while no screenshot was reached. This clarification preserves that original reader output.

V2 includes the empty placeholder in the pane cache key. Nonempty rows retain their existing cache behavior; transition to/from an empty pane stores or clears the placeholder. The same installed archive and successive explicit no-capture state transitions exercise the corrected render boundary. V2 starts from the unchanged v5 release and constructs fresh v7; it does not edit or reuse the failed v6 tree. Helpers retain their `_v1` names because their bytes are unchanged. Independent read/backup commands point to review_field_postrun_v2.py; V1 commands are historical and must not be rerun.
