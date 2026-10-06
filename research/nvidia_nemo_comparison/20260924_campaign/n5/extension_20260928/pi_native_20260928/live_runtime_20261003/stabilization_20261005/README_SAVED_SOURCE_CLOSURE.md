# Saved reader closure

`launcher.py` now distinguishes a saved recording/WAV reader from a physical microphone subprocess. A saved reader runs inside the owned worker process; its positive processed sample count does not require a nonexistent microphone `REGISTERED_OWNER.json`.

The added `Manager._saved_source` check binds the original launch `REQUEST.json` hash in `CHILD_LAUNCH.json`, exact worker identity, envelope policy and `SESSION.json`. A successful replay additionally requires matching engine selection/policy/sample counts, reader join and actual `source_stop_join` cleanup. Recorded spatial replay requires its original kept-session ID, metadata hash, verified source after drain, released shared lease, and `current_motion_used=false`. A replay WAV cannot claim recorded spatial evidence. Physical source owners, child returns or start packets are rejected for saved input.

Exact worker OS absence proves the in-process reader threads are gone. This is physical ownership closure, not a conversion of a failed recording into success: failure and logical cleanup fields remain separate and unchanged. Missing or malformed receipts are fenced. Existing Live microphone closure statements are unchanged.

## Inputs and outputs

Runtime input is the existing saved selection from the classic application's Start control: either a kept recording from the same store or one processed replay WAV. Output is the normal `HOST_CLOSURE.json` with nested state `SAVED_INPROCESS_SOURCE_CLOSED`, request hash, actual worker probe and preserved logical outcome. No separate command, capture or model is added.

The focused host check reads the immutable build25 launcher/support code, the new launcher, this README, and actual Saved27 read-only inspection scalars. It writes a unique private audit directory with full early CPU14/FILETIME owner registration, finite scope, exact source backup plus independent restore, AST review and fixture results. It never contacts the Pi, constructs speech models, opens audio, or changes prior recordings/receipts.

## Run the focused host check

PowerShell:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005/check_saved_source_closure.py'
```

CMD or Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005\check_saved_source_closure.py"
```

No environment activation or package installation is needed. Run only when the parent coordinator permits a host check before its next all-owner native preread. Success prints a compact JSON status/path/owner. The parent independently checks exact owner absence afterwards.

## Evidence scope and native acceptance

Saved27's actual worker had completed 966400 saved samples, joined its reader, verified/released recorded spatial input, and was independently absent. The old launcher nevertheless waited for a physical microphone owner. Its failed GUI job and original fence remain preserved; this fix does not retroactively pass that job.

The host fixtures verify rich spatial, plain kept and WAV closure, failure preservation, setup failure without reader launch, and strict rejection of mismatched pins/types/identities, unjoined success, physical-source facts and unverified spatial success. Native acceptance requires a fresh versioned package: complete Saved replay through Stop/drain, normal launcher closure and post-Stop choice, followed by another session. Existing Live source ownership must still close through its unchanged physical-owner path. No new quality or sustained performance claim follows from this closure fix.
