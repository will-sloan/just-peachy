# Actual kept-session backend replay check

`native_saved_stabilization_check.py` is fresh injected test instrumentation over
the backed live stabilization helper. It opens the actual six-profile chooser,
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
- Both `maximum_output_bytes` and `independent_pc_copy_bytes`: **100663296**,
  separate 96 MiB target and PC reservations.

The kept source must be mono16k, completed, at most 30 seconds, and visible in the
current bounded 25-item History page. Source tree readback is at most 512 regular
files/768 entries/96 MiB with 32 MiB per-file ceiling. The original complete tree
and file identities/hashes are checked before and after replay under a shared
source lease. Missing, changed or ambiguous History/source pins reject.

The injected source policy is finite 30 seconds; the UI driver deadline is 180
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

Native execution is through the backed admission dispatcher only. For the small
host-only source/AST review, use the registered CPU14 wrapper below after its
source is backed. Pick a new output directory; do not rerun a healthy check just
to publish a new version. The wrapper registers its actual owner before project
reads and creates exact backups plus independent restores before compilation.

PowerShell:

```powershell
$review = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/check_native_saved_stabilization_source.py'
$source = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$output = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/native-saved-stabilization-static-check-FRESH'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B $review --source ($source+'/native_saved_stabilization_check.py') --reference ($source+'/native_stabilization_check.py') --readme ($source+'/README_NATIVE_SAVED_STABILIZATION_CHECK.md') --output $output
```

CMD and Anaconda Prompt, using the same pinned project Python:

```cmd
set JP_REVIEW=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/check_native_saved_stabilization_source.py
set JP_SOURCE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005
set JP_OUTPUT=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/native-saved-stabilization-static-check-FRESH
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_REVIEW%" --source "%JP_SOURCE%/native_saved_stabilization_check.py" --reference "%JP_SOURCE%/native_stabilization_check.py" --readme "%JP_SOURCE%/README_NATIVE_SAVED_STABILIZATION_CHECK.md" --output "%JP_OUTPUT%"
```

The helper itself is not installed into the runtime. The old live helper remains
unchanged. `finalize`, original source/worker identity checks, reviewed guarded
wrapper handoff, CPU/RAM/filesystem floors, whole-copy bounds and deadlines are
preserved. Programmatic UI actions are not physical touch evidence.
