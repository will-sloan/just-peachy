# Closed build29 repeated-speech hour review

Purpose: review the complete private PC mirror of one actual integrated,
continuous 3600-second headless application run. This is a narrow derivative
of `../review_full_app_hour.py` (base SHA
1b9e4f4ede3b3c4af60790fe79511ec90f4d61068f4afaf3b99392a1b0324f51).
It retains complete mirror hashing, exact owner/cgroup closure, final source
clocks, 600-second numeric bins and post-warmup memory slopes. It removes the
obsolete logical metadata-quota completion gate and instead checks the recorded
physical capacity/FSIZE plan and absence of output-budget failure. Historical
metadata used_bytes/limit_bytes remain visible as bookkeeping.

Additional checks: exactly one source epoch/start/stop; 57,600,000 accepted
samples; all 59 wrap ordinals and sample offsets with models_reset=False; no
source append failure; nonempty captions; actual ASR, diarizer and embedding
call completion; one measured model setup/diarizer setup; fully drained PnC
worker. Actual final bounded queue/scheduler state is reported. This does not
certify natural conversation, recognition/speaker quality, GUI endurance,
physical microphone capture or recorded spatial evidence. Memory slopes are
descriptive; they do not automatically prove leaks or thermal throttling.

Inputs: `--mirror` is the already accepted FULL_CLOSED_OUTPUT_MIRRORED private
directory containing RESULT, MIRROR_COMPLETE, MIRROR_MANIFEST and closed-output.
`--package` is the exact inventoried PC build29 package; `--manifest-sha256` is
331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b.
`--output-root` is an existing private parent for a fresh review directory.
The package supplies verified pure storage/event-compaction dependencies;
loader paths and actual imported module origins/hashes are checked. No model
code or original/native database is opened. Only a fully closed copied SQLite
database without nonempty journal/WAL/SHM sidecars is read with query_only,
immutable access, a 2 MiB cache and a 30-second progress bound for quick_check.
If sidecars exist, review rejects instead of silently ignoring recovery data.

Outputs: early registered CPU14 owner, source backup/independent restore and
REVIEW.json containing completion gates, numeric counters, memory/thermal bins,
source append statistics, final queue state, capacity evidence and limitations.
No transcript, audio samples, names or vectors are printed. Mirror files,
frozen package and native runtime are never written. Root independently checks
the review process's physical closure afterward.

Run only in the coordinated host slot after the actual hour and collector close:

```powershell
$repairDir = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
Set-Location -LiteralPath $repairDir
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B review_core_full_app_hour.py --mirror 'ACTUAL_FULL_CLOSED_HOUR_MIRROR' --package 'ACTUAL_BUILD29_HOST_PACKAGE' --manifest-sha256 331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b --output-root 'ACTUAL_PRIVATE_REVIEW_PARENT'
```

CMD and Anaconda Prompt use the same existing interpreter, without installation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B review_core_full_app_hour.py --mirror ACTUAL_FULL_CLOSED_HOUR_MIRROR --package ACTUAL_BUILD29_HOST_PACKAGE --manifest-sha256 331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b --output-root ACTUAL_PRIVATE_REVIEW_PARENT
```

Replace every ACTUAL input with accepted evidence. Source preparation/compile
alone cannot establish any hour completion gate. Status: prepared source only;
no hour mirror review or sustained qualification has run. Keep this README
updated with the eventual exact review receipts and limitations.
