# Bounded native stabilization UI check

`native_stabilization_check.py` is a fresh derivative of the retained
`full_application_20261004/native_full_application_check_v4.py`. It is injected
test instrumentation, not an installed launcher or an ordinary recording limit.

It selects one of the six actual operator radio buttons, selects Live microphone,
presses Open Application, then uses the retained portrait application's Mode,
People, Settings, microphone consent, Start, Stop, Save/Discard and Exit controls.
It explicitly selects `enrolled_names`; it does not enroll a person or fabricate
a gallery. Normal manual Stop behavior remains unchanged.

## Inputs and outputs

The reviewed native dispatcher supplies globals `PAYLOAD` and `BASELINE`.
Launch requires a fresh boot identity, cleared prior-owner inspection, a pinned
immutable runtime package and manifest, a unique `classic-ui-check-NN` label,
exact helper source/base64/SHA, the actual operator `chooser_label` and validated
selection, canonical owned data root and an admission expiring within 600 seconds.
The selected input must be live, with ReDimNet or TitaNet and one diarizer.
Parallel refinement and the old long manual-Stop qualification are rejected.

Set `stop_after_seconds` to 12–20 (default 20). The injected test source policy is
30 seconds, the actual UI driver deadline is 180 seconds, and the retained model
load/drain/cleanup and ownership limits still apply. Set both
`maximum_output_bytes` and `independent_pc_copy_bytes` to **100663296** (96 MiB).
The full measured processed/raw plan must fit that explicit fresh reserve; the
old 64 MiB admissions are unchanged. `prepare_gallery` and `discard_session`
are typed optional booleans; default save preserves the one new recording.

Launch returns the existing asynchronous JOB. The independent reviewed collector
must reap/close the exact unit, then invoke `operation='finalize'` with its output
root, package/manifest and data root. Actual worker/source closure precedes any
audio disposition. Full private PC copy and readback remain required.

Private outputs are numbered ACTION receipts, the private portrait image,
ADMISSION/JOB, normal unit/worker/source closure, COMPLETE and NATIVE_CHECK_V2.
`actual_processing_evidence` records actual indexed caption count, nonempty-text
count, current view existence and model-call counts by the engine's actual cost
keys. It copies no transcript into the diagnostics. A quiet functional pass does
not demonstrate ASR, embeddings, named-speaker accuracy or sustained real time.
Missing model events remain explicitly unqualified.

## Running it

Do not run this file as an unguarded SSH command. The existing admission dispatcher
loads the backed source, supplies the globals and closes the JOB independently.
The operator may speak only during a separately authorized actual microphone
window; no playback or enrollment is part of this check.

For a host source review, use the registered CPU14 wrapper. It writes the actual
REGISTERED_OWNER before project reads, backs up the helper/reference/README,
creates independent restores, compiles in memory and reviews every function AST.
Its two synthetic contract groups check radio invocation and private caption/cost
counts; no Tk, microphone, project model or native process is run. Choose a new
output label on each run, then independently check exact host process closure.
The first complete host review is already closed; do not rerun it merely because
this README is being published.

PowerShell (substitute a fresh output label; the pinned wrapper and paths are inputs):

```powershell
$review = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/check_native_stabilization_source.py'
$source = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$reference = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/full_application_20261004/native_full_application_check_v4.py'
$output = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/native-stabilization-static-check-FRESH'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B $review --source ($source+'/native_stabilization_check.py') --reference $reference --readme ($source+'/README_NATIVE_STABILIZATION_CHECK.md') --output $output
```

CMD and Anaconda Prompt (use the same pinned Python):

```cmd
set JP_REVIEW=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/check_native_stabilization_source.py
set JP_SOURCE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005
set JP_REFERENCE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/full_application_20261004/native_full_application_check_v4.py
set JP_OUTPUT=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/native-stabilization-static-check-FRESH
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_REVIEW%" --source "%JP_SOURCE%/native_stabilization_check.py" --reference "%JP_REFERENCE%" --readme "%JP_SOURCE%/README_NATIVE_STABILIZATION_CHECK.md" --output "%JP_OUTPUT%"
```
## Changes and limits

The old immutable helper stays intact. Changed driver methods are chooser_tick,
tick and the new processing_evidence. Changed top-level functions are inside and
launch; finalize and all other inherited functions retain their exact AST.
Discard now checks the actual `store.root/sessions/UUID` directory.
Fresh labels remain in the existing reviewed classic-ui-check collector namespace.
All baseline, manifest, lease-handoff, exact unit, source/worker closure, per-file,
RAM/CPU, storage-floor, deadline and full-copy guards remain. Programmatic controls
are not physical touch evidence. Neither this helper nor its host syntax check
alone qualifies the six native modes.
