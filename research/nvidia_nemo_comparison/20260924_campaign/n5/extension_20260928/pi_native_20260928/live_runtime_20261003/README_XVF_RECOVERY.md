# One conditional recovery for the actual closed raw06 AEC fault

Purpose: prepare and perform one fresh conditional use of the retained
`xvf_host -u i2c TEST_CORE_BURN 0` procedure, without capture, models, firmware
flash, driver changes, config changes or periodic resets. This is an external
action against the unchanged package; no v27/v28/build07 bytes are edited.

The actual raw-qualification-06 failure happened after the physical stream
opened and54,720 priming frames arrived: VERSION3.2.1 and build
`intdev-lr48-lin-i2c` succeeded, then AEC_MIC_ARRAY_TYPE returned255 with
`Resource could not respond`. No route had been applied and no speech/raw
samples were accepted. Source stream and hardware lease closed; the entire
failed job was independently mirrored after actual owner/cgroup closure.
The failed source SHA is
`b61f6df26ddfdf149c5bb98e9bf25a84a8ffe6d3edb46bd8bc17b4e139749788`.
This matches the prior V116/V4 conditional trigger. It does not establish the
board's uptime or prove that an evaluation-firmware timer caused the fault.

## Inputs, outputs and bounds

`prepare_xvf_recovery_v2.py` is PC-only. Inputs: the actual current baseline
`RESULT.json`, the complete closed failed-job mirror, fresh private output and
fresh recovery label. It pins CPU14, writes the actual early owner, verifies
the source failure and mirror closure, and writes two independent PC copies
of the exact control tool, live configuration, current install selector,
settings and270-degree kanshi configuration. The exercised tool is1,773,304B,
SHA256 `8cc5eebcb499faa61278c9378f7fcb92c6063a437176218404e56e610265e982`.
It uses the retained V4 before/restore tool pair as byte sources and actual
baseline config bytes. All files are rechecked natively before any command.
Unreadable prior volatile DSP state cannot be backed up or claimed restored.

`launch_xvf_recovery_action_v2.py` runs through the current `host_operations.py`
full ownership/lease precheck. It checks actual closed source owner and job,
full immutable package, fault hash, current tool/config pins and native floor.
Two independently read-back native copies precede maintenance. A fresh
`xvf-recovery-NN` owned service has CPU2–3/200%,64 tasks,90-second lifetime,
10-second Stop and a finite file bound. The actual maintenance driver is
CPU3/128MiB AS/1MiB stack and lowers file size to64KiB. The shared wrapper
publishes exact early OWNER before project reads and verifies its real unit,
invocation and cgroup. Preparation and independent full output reservations
are16MiB each; Pi5GiB and C:50GiB/G:75GiB floors remain.

Under the exclusive research and hardware leases, with every capture stream
closed, it reads VERSION/build/AEC. An already-readable AEC sends nothing.
Only the exact fresh AEC255 response permits a durable intent and one literal
maintenance command. Any timeout/nonzero/uncertain send ends the attempt;
no retry occurs. Each of at most7 control commands has a2-second timeout,
actual PID/start/boot receipt, directly owned reap, bounded raw stdout/stderr
and hashes. An existing intent for the same source-fault hash in another
recovery root refuses another send, including after uncertain outcomes.

After a successful send it waits2seconds, requires exact unchanged VERSION
and build, and records a fresh AEC read. Closed-stream AEC readability is
reported explicitly; the action never labels that readback as audio
qualification. Tool/config/install/display hashes are checked again, all
capture streams must remain closed, and leases release before job exit.
`RECOVERY.json`, raw command outputs/receipts, before/restore copies and
normal JOB/OWNER/UNIT/JOB_EXIT form the complete private output. Use the
existing normal job monitor to retain all files after actual closure.

## PowerShell

These commands are for the authorized operator after a fresh admission.
Preparation does not contact the Pi. The dispatch command does; the preparing
agent did not execute it. Change labels/output suffixes for fresh attempts.

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B "$n\prepare_xvf_recovery_v2.py" --baseline "$q\operation-post-soak-baseline-02\dispatch\RESULT.json" --fault-mirror "$q\raw-qualification-06-monitor-01" --label xvf-recovery-02 --output "$q\xvf-recovery-02-preparation"
& $py -B "$n\host_operations.py" --label xvf-recovery-02 --action "$n\launch_xvf_recovery_action_v2.py" --payload "$q\xvf-recovery-02-preparation\PAYLOAD.json" --writes
# Preserve the actual returned action_result as xvf-recovery-02-JOB.json.
& $py -B "$n\monitor_native_job.py" --job "$q\xvf-recovery-02-JOB.json" --output "$q\xvf-recovery-02-monitor-01"
```

## Command Prompt and Anaconda Prompt

Use the same qualified interpreter, with `N`, `Q`, `PY` set to the values
above; no environment install or activation is needed:

```bat
"%PY%" -B "%N%\prepare_xvf_recovery_v2.py" --baseline "%Q%\operation-post-soak-baseline-02\dispatch\RESULT.json" --fault-mirror "%Q%\raw-qualification-06-monitor-01" --label xvf-recovery-02 --output "%Q%\xvf-recovery-02-preparation"
"%PY%" -B "%N%\host_operations.py" --label xvf-recovery-02 --action "%N%\launch_xvf_recovery_action_v2.py" --payload "%Q%\xvf-recovery-02-preparation\PAYLOAD.json" --writes
"%PY%" -B "%N%\monitor_native_job.py" --job "%Q%\xvf-recovery-02-JOB.json" --output "%Q%\xvf-recovery-02-monitor-01"
```

The payload expires after600seconds. Expired unused preparation may be
re-prepared under a fresh PC path, preserving the old path. A recorded
maintenance intent consumes the exact fault's single-send allowance; do not
repeat it. Read the actual recovery result and full closure before a separately
admitted new raw qualification root. Keep raw06 and recovery failures intact.
No `RAW_NATIVE_QUALIFICATION_PASSED` claim comes from this procedure.

Host tests: use the early CPU14 owner wrapper in `README_STORAGE.md` with
`test_xvf_recovery`. They check the real closed fault's eligibility, readable
control/no-send, one-send/order/post-readback, uncertain/nonzero refusal and
firmware mismatch. All command replies in sequence tests are fakes; these tests
do not operate the device or prove recovery. Retained precedent:
`../README_XVF_RECOVERY_V4.md`, `../xvf_recovery_protocol_v4.py`, and
`../FIELD_LIVE_RECOVERY_FINDINGS_V1.md`; their expired dispatchers are not run.

## Version 2 dependency correction

Recovery01 failed in preparation before native output-directory creation, device
commands or a restart intent: the frozen build07 package intentionally did not
contain `native_job_probe.py`. Keep its failed receipts and the version1 action
unchanged. Version2 injects the exact already-reviewed monitor backup from the
complete raw06 mirror:15,768 bytes, SHA256
`40b6a7540a5dbab8c1a4bf7e89fa7ce7975740eb2cd29fef59d3158d41688b36`.
The preparer verifies independent backup/restore equality and the monitor's
source receipt, then embeds bounded base64 bytes. The action requires that
literal reviewed SHA/length before compilation; no dependency is imported from
or added to the package. Its command sequence, lease and identity checks are
unchanged. Fresh recovery02 is a preparation correction for the same unconsumed
fault, not a repeated device-maintenance attempt. Wait for all current jobs to
close and their mirrors to finish before dispatch.

Run `test_xvf_recovery_v2` with the documented CPU14 early-owner test wrapper.
Five focused host checks cover actual07 missing dependency, independently
backed stdlib source, missing pins/extent, altered code/encoding refusal and
unchanged maintenance sequence. They do not contact the device.
