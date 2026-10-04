# Independent host review of a closed GUI recording

`review_gui_recording.py` reads a complete private PC mirror and one exact kept
session ID. It performs no SSH, playback, capture, model load, GUI action or
source-store mutation. It displays only aggregate metadata and hashes, never
recorded audio or transcript text. CPU14 and an fsynced actual PC owner receipt
precede project/data access.

The review checks exact mirror file membership and every byte/hash, job/unit
closure, GUI/worker/source identity receipts, monitor utility closure, read-only
immutable SQLite metadata, contiguous processed/raw segment sample ranges,
PCM16 replay WAV headers, independently concatenated physical raw bytes and the
source raw SHA. It verifies that the replay session was discarded while the
original selected kept session survives. It also calculates the existing
Store.export allocation and emits a reviewed payload template; it never exports
or authorizes an expired payload itself.

Outputs in a fresh private directory are REGISTERED_OWNER, REVIEW.json and
EXPORT_PAYLOAD.json. The payload's label and600-second expiry describe preparation
time. Preserve the original payload and create a fresh reviewed label/admission
before any later root-owned external action. Export01 failed before storage
import; use the separate V2 path documented in README_OWNED_EXPORT.md.

## Actual08 GUI02 evidence

The complete closed mirror is
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/gui-qualification-02-monitor-01`.
The host-only review is `storage-preparation/gui02-review-02/REVIEW.json` beneath
that same private campaign root. It independently checked201 files totaling
128,430,667 bytes and309 closed monitor phases. The actual admitted08 manifest
SHA is `2ec99c80d5d070c30a1b4a7959be1a9e552d5fc7688fe703ab9ad650891ee841`.

Kept session `5e9d3ff46f654c178ea2e2dffa497433` contains exactly4,800,000 samples:
30 processed float32 segments (19,200,000 bytes),30 raw4-channel16 kHz PCM32
segments (76,800,000 bytes), and30 PCM16 replay WAV segments (9,600,000 payload
bytes plus1,320 header bytes). The independent concatenated raw SHA is
`bf16c6abe3e25f1f1fb19eb9106fbfd762f00a6fb3da920860e9cd35ffd0be76`.
Physical source closure and route restoration were recorded; dropped frames and
marker errors were zero. Maximum observed source lag was0.326967508 seconds.

The actual workflow reached the normal300-second policy boundary, used Save raw + processed
after closure, replayed the complete kept timeline to natural EOF,
discarded only the replay, and invoked Exit. The driver performed10 stable
fullscreen480×800+0+0 checks, retained270-degree display orientation, and invoked
direction debug/visual recenter controls. It exercised real Tk widgets
programmatically; this is not physical-touch or screenshot-based visual proof.

Both session caption tables contain **zero rows**. This run therefore does not
prove caption rendering, speech recognition quality or speaker accuracy. It is
also not a sustained-hour qualification. The kept session metadata ledger used
12,407,558 of24,903,680 bytes; the discarded replay used846,014 bytes. SQLite was
7,221,248 bytes. The computed selected export bound is156,187,024 bytes,
112 entries; including independent16 MiB metadata and rounding gives a
173,015,040-byte allocation on both native and PC sides. Export success remains
a separate evidence gate.

## PowerShell

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$n/review_gui_recording.py" --mirror "$q/gui-qualification-02-monitor-01" --session-id 5e9d3ff46f654c178ea2e2dffa497433 --output "$q/storage-preparation/gui02-review-FRESH"
```

## Command Prompt and Anaconda Prompt

Run `powershell -NoProfile` and paste the same block, choosing a fresh output
directory. The qualified interpreter requires no environment activation or new
package installation. This repeat is read-only review, not another native run.

## Actual selected-recording export03

The root operator subsequently completed export03 from the kept GUI02 session.
The complete closed mirror is `recording-export-03-monitor-01`; independent PC
verification is `recording-export-03-pc-readback-01/VERIFY.json`. The archive has
112 members and 142,926,668 bytes, SHA256
`923edafd8513ef39d82ee08aefb1bc7204a106eb72a9cbadb2650920720f5b4a`.
The selected source recording remained unchanged. This establishes the bounded
fresh export child, shared source lease, actual native archive and PC readback
for that recording. The separate actual History-button invocation is a pending
targeted check; export03 alone does not establish it. No additional capture,
caption-content or physical-touch result is claimed.