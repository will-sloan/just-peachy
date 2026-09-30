# Smaller whole-run allocation proposal V3

Purpose: retain the audio/native journal/TRACE/archive bounds while preparing a smaller complete arithmetic envelope:72MiB target,72MiB exact host copy plus4MiB host metadata,148MiB combined. V2 remains immutable. V3 is not loaded by any admitted dispatcher, is not a WINDOW policy revision, and does not admit capture.

Inputs: immutable V2 allocation and V81 measured staged code13files/73826bytes. Proposed changes: code512KiB total/128KiB per file and write/32files; receipts1MiB total/16files with64KiB file/write; closure2462164bytes total with unchanged1MiB file/16files. All other component and sidecar bounds, directory reserve/count,5GiB free floor,4MiB host metadata and retained campaign usage stay unchanged. The declared file ceilings plus1MiB directory reserve sum exactly72MiB. This assigns every arithmetic byte; it does not prove every writer is integrated or simultaneous maxima/failure-tail closure fit.

Next implementation must bind this exact descriptor into a fresh complete source/controller/outer/staging/backup capsule, enumerate mapped receipt/code/closure producers, and enforce per-producer closure reservations. The observed small code stage only motivates its proposed cap; larger future source must reject before publication. Existing V81 stage still uses V2 and does not qualify V3. Host metadata and archive/transport directory enforcement remain open. No old admitted limits are edited or removed.

Outputs: FIELD_WHOLE_RUN_ALLOCATION_V3.json only; new private ALLOCATION_REVIEW_V13 compares both proposals against closureV173. At that closure148MiB leaves8560838bytes under52GiB before later metadata, but still exceeds the5GiB output cap by62044607bytes. A fresh measured admission and explicit output-policy revision would still be needed after enforcement. No automatic deletion/reset/52GiB increase.

To inspect the proposal in PowerShell:

```powershell
Get-Content -Raw 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\FIELD_WHOLE_RUN_ALLOCATION_V3.json'
```

Command Prompt / Anaconda Prompt (inspection only):

```bat
type G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\FIELD_WHOLE_RUN_ALLOCATION_V3.json
```

There is no execution or capture command for this unapplied proposal. Use the separately documented fresh dispatcher only after complete review/admission.
