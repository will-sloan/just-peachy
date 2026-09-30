# Mode-aware D1 entry preparation V1

Purpose: make Streaming, Chunk52 and Delayed select their own qualified saved-app and endpoint lineage before a future fresh-process launcher constructs the application. The prior mode-specific app sources and results remain immutable. This is an entry implementation and changed contract/wiring check, **not a completed launcher or native integration pass**.

`d1_mode_entry_v1.py` verifies D1_MODE_ENTRY_MANIFEST_V1 against an externally bound SHA, exact mode catalogue/geometry/all-assets metadata and eighteen retained source/input/receipt/endpoint/method files. Requests are detached, canonical, saved-only and require a new explicit session. Retained sessions, modified geometry, endpoint substitution, live enablement, extra skip flags and arbitrary metadata paths are rejected. The selected native model still must perform its unchanged actual asset-byte/CABI/mapped-library checks when a future admitted worker starts it; these metadata checks do not replace that work.

The fresh saved/method/recovery mode-entry modules forward one explicit endpoint module through all three factories. The saved worker closes over its selected endpoint functions instead of importing Chunk52's helper globally. Streaming binds endpointV1/LRU8, Chunk52 bindsV2/LRU8, and Delayed bindsV3/distinctLRU1. The method/worker/Stop/recovery bodies are retained. Class construction in the host checker uses an `object` Base without constructing it; no source/model or UI is created.

`claim_process` is prepared to reject a second binding or already mapped Nemo/GGML libraries and latch subsequent binding failures. The exact-origin endpoint loader checks its contract SHA. Neither path has native execution credit from the host check. A guarded child supervisor, independent owner handshake, deadline/Stop/reap and actual selection-to-Start/Stop passage must be composed and verified next. Do not infer new Start or recovery acceptance from unchanged bodies.

Inputs: public entry manifest and derivation; private HOST_MIRROR_V1 maps the native pins to previously verified exact host backups. The checker reads real retained metadata through that map, injects in-memory malformed requests, and inspects actual Python factory closures for each endpoint. It does not rerun old frame-count, model, control or helper suites. Outputs: exclusive small host check receipt, source/static/allocation review, optional read-only Pi pin receipt and exact private source backup. No audio, transcripts, models or private gallery data enter Git.

Host work stays onCPU14. Fresh2MiB metadata allowance, existing WINDOW_V5 caps and fixed Pi32GB/5GiB reserve apply. No new target payload/model process is dispatched by these commands. Hard completion boundary: October1 17:42:44UTC; finalization starts16:42:44UTC.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$private='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\d1-mode-entry-v1-preparation'
& $py -B check_d1_mode_entry_v1.py --mirror "$private\HOST_MIRROR_V1.json" --output "$private\HOST_CHECKS_V1.json"
```

## Command Prompt / Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B check_d1_mode_entry_v1.py --mirror "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\d1-mode-entry-v1-preparation\HOST_MIRROR_V1.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\d1-mode-entry-v1-preparation\HOST_CHECKS_V1.json"
```

Run once after a fresh owner/census/allocation review. A closed receipt is immutable; changed work needs a fresh output label and source derivative. To embed later, construct Registry from a pinned manifest, request/validate a mode and fresh session, and pass its exact selected endpoint to the prepared controller factory **inside an admitted fresh native child**. No standalone launch command is published until that child lifecycle is implemented and verified. Display270, original rc5, old policies and old evidence remain unchanged.
