# Record V2 restore / V7 owner root source review

`s6d_build_telemetry_recovery_review_v2.py` materializes root's completed narrow review after the real V1 socket-probe refusal. It uses exact frozen V2 restoration and V7 owner sources, the 20+10 affected checks, unchanged V2 telemetry and native-row evidence, the preserved original root review and the failed pre-device V1 restoration result. It writes immutable `ROOT_SOURCE_REVIEW_V2.json` and `ROOT_SOURCE_INPUT_VERIFICATION_V2.json` under this run's `capture_telemetry_recovery_v1` report directory. It performs no process, TCP, lock, device, playback or model action.

There are no CLI inputs; exact paths/hashes are fixed in this run-specific builder. Existing outputs reject; missing/changed sources or old failure evidence reject. Root has read both complete narrow source diffs and accepted their existing checks. This builder records that review; it is not an automatic source-approval system. V1 files stay unchanged. The actual recovery must use fresh `closed_telemetry_restore_v2` output and the exact printed review/hash.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_build_telemetry_recovery_review_v2.py"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_build_telemetry_recovery_review_v2.py"
```

For separately admitted actual restoration, follow `README_S6D_CLOSED_TELEMETRY_RESTORE_V2.md` using `execute`, this exact review/hash, and a root-owned exiting launcher. Actual fresh TCP/process/ownership/readback proof is still required. Then use `README_S6D_BANK_REMAINING_ADMIT_V2.md` with the exact V7 freeze/hash; metadata admission does not itself launch a capture. All physical limits remain unchanged at 40 GiB/480 attempts/21,600 charged seconds; the separately justified future offline allowance is not applied here.
