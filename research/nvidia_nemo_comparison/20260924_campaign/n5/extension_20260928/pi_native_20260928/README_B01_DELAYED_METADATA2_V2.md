# B01 shared-controller delayed recipe with smaller metadata reservations

Purpose: test simultaneous Sherpa ASR, delayed native Nemotron D1 and retained ReDimNet E0 within the existing 768 MiB virtual limit. This is an isolated native application diagnostic, not an installed release or GUI qualification. It retains the shared controller's previously qualified failed-start cleanup and all existing inference/drain gates.

Inputs: immutable shared-app-v2 and B01 V9 bindings, the exact first 12 seconds of saved PCM, installed Sherpa/ReDimNet/punctuation assets, reviewed native-profiles-v2 adapter, and the independently reviewed full-file delayed metadata2 component. A fresh copy of application source changes only the adapter and the B01 composition: explicit delayed profile plus runtime hashes, with a newly computed manifest ID. The parent and active rc5 installation remain unchanged. No personal gallery is copied; this anonymous-conversation diagnostic retains the E0 encoder but cannot prove personal naming.

`dispatch_b01_delayed_metadata2_v2.py` verifies all parent/asset hashes and exact closed ownership, copies code through hard links and replaces only fresh derivative inodes, then writes new runtime bindings and admission. `b01_native_delayed_metadata2_v2.py` uses the existing shared-controller protocol, explicitly checks the selected delayed profile, records model/encoder load evidence, caption rows, progress, memory, terminal state and closure. Native aborts may prevent RESULT/finalization; retain them as failures and verify exact OS closure separately. A process exit is not application acceptance.

Outputs stay private: OWNER, MEMORY.jsonl, RESULT, FINAL_SNAPSHOT, PROGRESS, session journals and admitted source/runtime hashes. Independently review source/ASR/identity passage and writer/worker/model drainage. Do not score ASR/WER or infer accuracy from saved text. This 12-second prefix is a constructed diagnostic, not independent real-world evidence.

## PowerShell

From this directory, after the metadata2 delayed component's independent review and with a census less than 15 minutes old:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py dispatch_b01_delayed_metadata2_v2.py --run-id b01-delayed-metadata2-v2 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V11.json'
```

## CMD / Anaconda Prompt

Use `cd /d` to this directory, run the same explicit quoted Python path, omit `&` and retain the arguments. No activation/install/download is needed. Strict SSH stdin stages the new diagnostic; its systemd unit uses the installed Pi Python. Refuse existing output paths. Preserve old admissions and shared ledgers.

Keep CPUs 2/3, total CPU 200%, one thread per model, 64 tasks, 180 seconds, hard 768 MiB RLIMIT_AS, at least 850 MiB available RAM and 5 GiB target disk. Process-local arena=1 and mmap/trim thresholds=128 KiB match preserved V9; Python thread-stack setter remains 1 MiB without the resetting getter. Reserve 16 MiB within the shared 1 GiB output allowance. No higher cap, OS/swap change, capture/playback, training, enrollment, visible UI or silent fallback is authorized by this test. Full-file/restart/Stop/UI/endurance and real-life validation remain separate gates.

## V2 process-local ONNX Runtime initialization change

V1 is preserved as a failed inference run. Application queues/files finalized, but native ONNX Runtime exit handlers did not terminate; the exact failed test unit was stopped. A live native stack and open-handle snapshot identify ONNX Runtime workers and its DeveloperTools telemetry database. This supports investigating telemetry initialization; it does not prove all allocation failures were caused by telemetry.

The installed binary contains ORT_DISABLE_TELEMETRY. Official ONNX Runtime documentation and the v1.29.0 release notes document setting it to 1 **before initialization** on non-Windows systems. V2 does so in the process environment and harness before app imports, with an explicit new composition manifest. This preserves model graphs/weights and all existing inference/drain/resource guards. It changes only the new test process, not the original installed app, OS or user environment. No cache/database is read or deleted.

Sources checked September 29, 2026: [official privacy/runtime switch documentation](https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md) and [v1.29.0 release notes](https://github.com/microsoft/onnxruntime/releases/tag/v1.29.0). A fresh test must establish actual memory and complete process shutdown; disabling telemetry is not itself proof of a fix. The earlier 768 MiB cap and pending higher-cap question remain unchanged.
