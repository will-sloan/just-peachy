# Application source and shutdown closure

Purpose: check the real source, audio journals, model-lane owners, event inbox,
writers and archive before treating a completed saved-file application session
as losslessly closed. `application_closure.py` reads facts and receipts; it does
not stop, join, close or load any source/model or change the application's state.

For a future actual application run, keep engine and consumer references before
Controller.close clears them. After its normal drain/closure, call capture_engine
with those owners, the installed V3 ConsumerSourceClock and the exact admitted
audio-only job. Then call capture_archive on the closed Controller and retained
engine, and validate_complete. Preserve observations on failure. The clock's
actual EventInbox census must reconcile publication/consumption/coalescence.
Snapshots before shutdown, incomplete startup, missing owners and unavailable
receipts cannot become success by substituting zeros.

Checks include actual FileSource identity/path/zero offset and exact sent samples;
the input, ASR and identity MemoryJournal objects share the bypass source journal
and finish without gaps/errors; ASR drains the full input; both model lanes and
all source, consumer, finalizer, policy, punctuation, event, trace and text owners
exit; queues drain and accepted/completed counts match; all native text sinks
close. Late trace failure invalidates success even if the earlier native final
checkpoint says COMPLETED. Terminal receipts must belong to the same session.

The finalization and consumer receipts are read after joining the owner. The
earlier session_summary is not substituted. Actual inbox obsolete-partial
coalescence stays explicit and must reconcile to the event journal's published
count. The existing N3 joined archive-integrity validator is reused unchanged;
the archive must belong to this native session and record no new audio in the
primary campaign. Wrong samples, queue loss, early closure, foreign archives and
missing/late-failed writers are rejected. Acceptance here covers closure only:
accuracy, viewport timing, full publication content, controlled resources and
whole-stage acceptance still require their independent evidence.

## Qualification inputs and outputs

`probe_application_closure.py` verifies the frozen N4 source and accepted N3
metrics/reports. It checks terminal and archive receipts from all nine accepted
historical GUI sessions. The report and archive hashes are inherited; native
finalization/consumer files are freshly hash-bound through their accepted session
paths. No older terminal-file hash is invented. Historical persisted checks do
not observe today's source/worker objects and give no new N4 execution credit.

Seven tests include those nine sessions, synthetic in-memory positive and failure
fixtures, and a real partial Controller/engine startup with model acquisition
forbidden. That partial startup starts only private bounded journal/policy/trace
workers, then exercises original cancellation/closure; no source, GUI or model
starts, and the helper must reject it as an incomplete application run. There is
no microphone, USB, playback, training, enrollment or personal-store access.

Outputs in a fresh private local/n4 directory: ADMISSION.json, unittest.txt,
CHECKS.json, RESULT.json, the cancelled startup's private metadata and explicitly
labelled negative fixtures. Keep private metadata/receipts outside Git. The
launcher uses CPU14, below-normal priority, one math thread and GPU off; checks
the shared allowance plus 6 GiB reserved, drive floors and packaging cutoff; and
caps its private output at 128 MiB. It is not a controlled resource/pacing test.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'research\nvidia_nemo_comparison\20260924_campaign\n4\probe_application_closure.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\application-closure-v1'
```

## CMD / Anaconda Prompt

Use the pinned existing interpreter; no new conda activation/install is needed.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_application_closure.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\application-closure-v1
```

After admission preserve all bound source and failed outputs. Repairs use fresh
derivatives and output directories. Do not interpret these tests or the helper's
closure status as actual N4 inference/GUI/continuity or CM5 qualification.
