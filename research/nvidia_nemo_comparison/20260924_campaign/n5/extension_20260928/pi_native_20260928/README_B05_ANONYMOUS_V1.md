# Native B05 anonymous delayed speaker control

Purpose: test the explicitly anonymous alternative of Sherpa captions plus one delayed Nemotron D1 stream, with no external speaker encoder loaded/called. It cannot recognize personal names across sessions. This is a separately labelled composition/control, never a silent replacement for B01 with retained ReDimNet.

Inputs: current native shared-app-v2 lineage and delayed metadata2 runtime, the already Windows-qualified anonymous-mode patch from d1-stable-asr-chunks-v1, and a constructed exact12-second prefix of original saved PCM. `prepare_b05_anonymous_v1.py` applies only three bound patch hunks to the latest native n2_pipeline source; it preserves newer controller/journal code. Default named/research modes keep the prior encoder behavior. The isolated catalog label/policy and recomputed manifest identify anonymous operation. No model conversion, gallery, enrollment, accuracy scoring or microphone use.

Outputs: private source/admission/owner hashes, application memory/progress and actual captions/identity journal, finalization and RESULT if possible, plus independent REVIEW. The harness requires no E0 load and zero speaker-model loads. Independent review must additionally require actual D1 windows, exact source/identity input coverage, no errors or silent fallback, zero embedding calls, closed queues/writers/native handles and natural process exit. A12-second pass is not full-file, UI, persistent naming, performance under dense real speech, release acceptance or sustained operation.

## PowerShell

From this directory:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$private = 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928'
# Reproduction only: output must not exist; the executed derivative is preserved.
& $py prepare_b05_anonymous_v1.py --parent "$private\B05_PARENT_PIPELINE_V1.py.txt" --reference 'G:\Just_Peachy_N1\20260924_campaign\local\releases\d1-stable-asr-chunks-v1\prototype\app\n2_pipeline.py' --out "$private\b05-anonymous-source-v1"
& $py dispatch_b05_anonymous_v1.py --run-id b05-anonymous-v1 --census "$private\HOST_CENSUS_V12.json"
```

The parent snapshot is a read-only copy of the bound remote shared-controller n2_pipeline.py; the preparer rejects any parent/reference/output hash mismatch. The dispatcher verifies all parent assets and exact closed ownership, uses a fresh source tree with replaced inodes for patches, and refuses existing targets. Do not replay immutable names; a new trial needs a new reviewed derivative/admission. Host census must be less than15minutes old.

## CMD / Anaconda Prompt

Use `cd /d` to this directory. Invoke the same explicit quoted Python executable and arguments, omit `&`, and expand the shown private paths (or use `set "JP_PRIVATE=..."` and `%JP_PRIVATE%`). No install/download or environment activation. Strict SSH stdin invokes the installed target Python through a bounded systemd job.

CPU2/3,total200%,one native thread/model,Tasks64,180seconds,hard768MiB virtual limit,>=850MiB available RAM,>=5GiB disk and16MiB fresh-output reservation remain unchanged. Process telemetry-off, glibc arena1/128KiB thresholds and1MiB Python thread-stack match prior combined tests. Original install/app untouched. No capture/playback, higher cap, dropped audio or silence skips. Prior B01 failures and pending higher-cap decision remain separate.
