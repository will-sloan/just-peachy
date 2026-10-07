# Preserve the exact old unsent recovery failure

The read-only Pi inspection observed one completed recovery attempt that failed
before any command because the old helper subtracted a manual GUI's `None`
deadline. All seven original files (2312bytes), their hashes, exact closed helper
and old source pins are retained. No restart intent, command or maintenance send
was present. Build27 fixes that lifetime check but intentionally fences failed
recovery roots; it remains preserved as prepared history.

The next runtime acknowledges only this exact unchanged seven-file artifact.
`qualifying_unsent_manual_failure` is a pure byte/schema/identity validator.
`preserved_unsent_manual_failure` reads stable bounded real files, current
fault/closure hashes, actual old build26 source/package pins and current-boot
closed identities. Extra/changed files, intent, sends, uncertain closure, live
owners or another error do not qualify.

For this acknowledgment, an explicit new **Start** skips the old repair
preflight and launches a fresh ordinary source. It does not retry or rewrite the
old helper/root, consume the new Start's continuation budget or claim a
microphone pass. If the fresh source reports the exact empty AEC255 fault and
closes naturally, its new source receipt/hash can admit one fixed asynchronous
helper and one same-Start continuation. Stop/Exit still cancel capture restart.
All other failed or uncertain recovery roots retain their ordinary fence.

Inputs are the exact fixed old file bytes; current fault/closure paths/hashes;
old readiness/helper/package source pins; current boot; and exact owner probes.
The acknowledgment writes nothing. Normal fresh sessions and any new helper
create their own UUID/hash receipts and retain normal storage/ownership guards.
There is no raw/source/route/firmware behavior change.

Operator steps: open the single Just Peachy shortcut, choose the backend, press
OK and then Start. Use Stop/Exit normally. Do not manually delete or edit the old
recovery directory and do not directly invoke the native helper.

PowerShell can read this guide and the shared implementation guide:

```powershell
$runtimeSource = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005'
Get-Content -LiteralPath "$runtimeSource\README_UNSENT_RECOVERY_ACKNOWLEDGMENT.md"
Get-Content -LiteralPath "$runtimeSource\README_XVF_START_CONTINUATION.md"
```

CMD and Anaconda Prompt require no environment installation:

```bat
set "RUNTIME_SOURCE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005"
type "%RUNTIME_SOURCE%\README_UNSENT_RECOVERY_ACKNOWLEDGMENT.md"
type "%RUNTIME_SOURCE%\README_XVF_START_CONTINUATION.md"
```

The focused host acknowledgment check and actual literal Pi Start report are
separate evidence. Implementation alone does not establish successful capture.

The changed validator check `check_unsent_recovery_acknowledgment.py` reconstructs
the original seven files from the independent native read-only inspection and
requires every size/SHA to match before using them. It tests exact acceptance and
rejects sends/intent, uncertain closure, extra/missing members, changed source/
fault/provenance, another error and live owners. The owner callback is synthetic;
it performs no native operation. CPU14/early owner and independent source
restores precede actual function compilation. Outputs are a unique private
`audit-preparation/unsent-recovery-check-<UUID>` directory bounded to2MiB/60seconds,
with owner/scope, sources/restores, `SOURCE_CLOSED.json` and `RESULT.json`.

PowerShell (no input arguments):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$runtimeSource\check_unsent_recovery_acknowledgment.py"
```

CMD and Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%RUNTIME_SOURCE%\check_unsent_recovery_acknowledgment.py"
```
