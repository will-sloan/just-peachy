# Owned native/Tk harness v2: exact render joins and setup cleanup

Purpose: this additive helper repairs the two independently reproduced v1 findings. It retains the accepted GUIv3 application source, fixed original gallery/profile/weights, source-paced engine, single causal dispatcher, bounded queues and eight prospective jobs. The v1 source and adverse receipts remain immutable. This is source and model-free fixture preparation only; it authorizes no model, native, real Tk, device or production execution.

Inputs to `s6d_application_tk_native_v2.py`: the exact reviewed manifest, frozen source/support/helper/profile/gallery/WAV bindings, expected source/identity frames and PCM SHA, fresh G output, root-selected one-to-four CPU affinity and admitted supervisor protocol. The entry remains `run_one(manifest_path, job_id, checkpoint=None)`. C must have at least 50 GiB and G 75 GiB free; the outer supervisor also enforces the campaign's 40 GiB payload cap. Native weights, endpoint settings, decoders and actual GUIv3 source are unchanged. No live audio stream is opened. Only eventual owned Tk windows would be controlled.

Each transcript render receipt now copies the actual triggering `session_id`, `source_native_publication_sequence`, `source_native_publication_monotonic_sec` and `causal_view_input_count` from the payload just stored by the frozen GUI consumer. It includes that display payload and the exact widget text plus its SHA. The separately named `dispatcher_frontier_input_count` may be ahead and is never the causal join key. Missing trigger metadata fails explicitly. Actual widget-command/callback clocks remain distinct from native publication, dispatcher consumption, physical scanout and reference correctness. Concurrent T0/T1/T2 views still share one causal native stream and add declared UI load; eight probes do not replace the required per-condition paced coverage.

The setup/loop cleanup scope now begins before Tk, consumer-file, gallery-spy and window allocation. A partially constructed window is retained before initialization. Every owned cleanup action is attempted independently, never-started threads are not joined, and a late startup is checked/stopped again. `OWNED_RESOURCE_CLOSURE.json` records acquisitions, joins, original setup/loop error and cleanup errors even when construction fails and the original exception propagates. That receipt makes no session-completion claim. A cleanup error prevents COMPLETE; actual native completion still requires the accepted full-input PCM/dispatch/drain guard and separate owner/protocol closure.

Normal outputs remain full native `consumer_events.jsonl`, resources/progress, source/session journals, per-view `s6d_gui_render.jsonl`, gallery score-call observations, cleanup receipt and semantically validated RESULT. `GalleryScoreSpy` counts actual `gallery.score` invocations, not unique identity queries or enrollment duration: the resolver may call the gallery for both center and current vectors. Selected presentation consumers issue no gallery calls.

`s6d_application_tk_cleanup_checks_v2.py` takes `--helper`, `--app-source` and a fresh G `--output`; it emits four tiny fixture logs/observations/receipts. It uses fake Tk/threads and no models or devices. It tests consumer-file open failure, a partially initialized second window, independent cleanup after engine-stop failure and not joining an unstarted worker. The unchanged independent eight-probe fixture remains `s6d_native_tk_review_checks_v1.py` with its own README. Neither fixture demonstrates actual Tk execution or acoustic efficacy.

PowerShell:

```powershell
$s6dScripts = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$s6dApp = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6D\20260913T195357Z\source_epochs\application_direction_gui_v3\edge_speech_pipeline'
$s6dPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $s6dPython -B "$s6dScripts\s6d_application_tk_cleanup_checks_v2.py" --helper "$s6dScripts\s6d_application_tk_native_v2.py" --app-source "$s6dApp" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_tk_v2_cleanup_reproduction'
& $s6dPython -B "$s6dScripts\s6d_native_tk_review_checks_v1.py" --helper "$s6dScripts\s6d_application_tk_native_v2.py" --app-source "$s6dApp" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_tk_v2_independent_reproduction'
```

Anaconda Prompt / CMD (existing environment, no installation):

```bat
set "S6DSCRIPTS=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set "S6DAPP=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6D\20260913T195357Z\source_epochs\application_direction_gui_v3\edge_speech_pipeline"
set "S6DPYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6DPYTHON%" -B "%S6DSCRIPTS%\s6d_application_tk_cleanup_checks_v2.py" --helper "%S6DSCRIPTS%\s6d_application_tk_native_v2.py" --app-source "%S6DAPP%" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_tk_v2_cleanup_reproduction"
"%S6DPYTHON%" -B "%S6DSCRIPTS%\s6d_native_tk_review_checks_v1.py" --helper "%S6DSCRIPTS%\s6d_application_tk_native_v2.py" --app-source "%S6DAPP%" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_tk_v2_independent_reproduction"
```

Use a fresh suffix for each deliberate reproduction. Current `native_tk_consumer_v2/MANIFEST.json` is prospective and keeps null CPU affinity to prevent an unadmitted launch. After independent review, root must adopt exact source/manifest/affinity/owner bindings and validate the supervised queue first. Wrapper commands are documented in `R/runner/source_epoch_ready_v2/s6d_runner_native_pilot_README.md` and `s6d_runner_README.md`; no direct helper invocation substitutes for that admission.
