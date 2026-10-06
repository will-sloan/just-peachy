# Actual kept-session backend replay check

`native_saved_stabilization_check_v2.py` is a fresh derivative of
the backed Saved helper v1. It opens the actual six-profile chooser,
selects Saved WAV, opens the retained portrait application, selects its Mode,
opens Settings → Sessions, chooses one explicitly pinned kept UUID and invokes
the actual Replay with selected backend button. No microphone, current BMI270,
speaker enrollment, sound playback or parallel refinement is started.

## Inputs

The existing reviewed native dispatcher supplies `PAYLOAD` and `BASELINE`; this
file is not a standalone unguarded SSH launcher. Existing current-boot,
prior-owner, immutable-package/manifest, canonical-data-root, unit and lease
guards remain. Use a fresh `classic-ui-check-NN` label. Provide exact helper
base64/SHA, operator `chooser_label` and validated selection with input_source
`saved`, ReDimNet or TitaNet, and optional refiner/correction disabled.

Additional required fields:

- `saved_session_id`: exact 32-character kept recording UUID.
- `saved_metadata_sha256`: SHA256 of the original **session.json file bytes**.
  The helper separately records the canonical `SessionStore.read()` metadata SHA
  used by the historical spatial provider. These are distinct pins.
- `application_mode`: default `enrolled_names`; also `spatial_assisted`,
  `strongly_spatial_assisted`, `assigned_direction` or `assigned_hybrid`.
- For assigned Modes only, `seating` has exact fields `rows`, `strength` and
  `acknowledged`. Rows must refer to actual compatible enrolled people. The
  retained editor's Apply button performs real layout validation. The injected
  draft refers to the original recording's array reference. It does not create
  people, infer their positions, invent a current pose or certify naming accuracy.
- Both `maximum_output_bytes` and `independent_pc_copy_bytes`: **134217728**,
  separate 128 MiB target and PC reservations.

The kept source must be mono16k, completed, at most 90 seconds, and visible in the
current bounded 25-item History page. Source tree readback is at most 512 regular
files/768 entries/128 MiB with 32 MiB per-file ceiling. The original complete tree
and file identities/hashes are checked before and after replay under a shared
source lease. Missing, changed or ambiguous History/source pins reject.

The injected source policy is finite 90 seconds; the UI driver deadline is 240
seconds, with retained model-load/drain/cleanup limits. EOF processes every source
sample, then closes the actual worker. It does not inject an early Stop or truncate
the recording. Normal application manual-Stop behavior is unchanged. The replay
creates a new session. `discard_session` can discard only that output; by default
the actual post-EOF Save action retains its processed audio and results.

## Outputs and evidence

Launch returns the existing asynchronous JOB. Independent unit/source closure
and finalize precede NATIVE_CHECK_V2 PASS. Full private PC copy/readback remains
required. Numbered ACTION receipts and COMPLETE report actual indexed/current
caption existence and component invocation counts by the engine's cost keys.
Text content is retained privately in the recording, not copied into diagnostics.
Quiet function success is not ASR/embedding/quality or sustained real-time proof.

For spatial Modes, actual results must bind the original session, canonical
metadata SHA, full sample count, consumed recorded anchors/beam receipts, final
source verification and shared-lease closure. Current motion must be false. No
DSP acoustic synchronization or absolute translation proof is invented. Plain
WAV input cannot pass this rich-session check. Enrolled-names replay must not
silently enable spatial inference.

## PowerShell, CMD and Anaconda Prompt

V2 changes only the external test contract: 90-second maximum saved source,
128 MiB target and independent PC copies, and a 240-second UI driver. It replays
the complete retained source without trimming. V1 remains immutable. The normal
field runtime and manual Stop behavior are unchanged.

Run the one focused host-only source review below when the native preread allows
an actual short host owner. The checker sets CPU14, registers its real identity,
backs all seven inputs and independently restores them before reviewing exact
whole-source transformations, compiling three new sources and comparing changed
function ASTs. It does not execute any project module, GUI, source or model. Use
one new output directory; do not rerun a healthy review for publication.

PowerShell:

```powershell
$s = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$out = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/saved-stabilization-v2-source-FRESH'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ($s+'/check_saved_stabilization_v2_source.py') --source $s --output $out
```

CMD and Anaconda Prompt use the same pinned Python:

```cmd
set JP_STABILIZATION=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005
set JP_REVIEW=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/saved-stabilization-v2-source-FRESH
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_STABILIZATION%/check_saved_stabilization_v2_source.py" --source "%JP_STABILIZATION%" --output "%JP_REVIEW%"
```

Native launch/finalize use `prepare_saved_stabilization_payload_v2.py` and the
selected `host_stabilization_operations_v2.py --writes` dispatcher; see
`README_PREPARE_SAVED_STABILIZATION_V2.md`. The preparer requires actual build24,
boot, kept UUID and raw session metadata pins. Never invent a UUID or substitute
a quiet recording for a human phrase. Saved replay and ASR/embedding output are
reported separately from source/closure success and from accuracy or sustained
real-time qualification.