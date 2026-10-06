# Source observations after a failed session

Purpose: show whether capture was actually observed independently of whether the speech pipeline completed. A missing engine result or source directory does not prove that the microphone never opened.

`worker.py` preserves numeric sample/start facts in its bounded RESULT receipt. `launcher.py` requires exact external source-owner closure for live microphones. Positive physical start facts with a missing owner receipt block subsequent sessions. Saved replay uses an in-process reader and binds its request, worker, session, reader-join and source-verification facts to actual worker OS absence; see README_SAVED_SOURCE_CLOSURE.md for the separate branch. `classic_frontend.py` presents observations in the retained portrait application; it keeps the primary failure in diagnostics and preserves the failed recording.

Inputs: the pinned deployment binding, owned recording store, exact worker/source owner receipts and worker RESULT. Outputs: the existing host closure receipt and concise portrait status. No models, microphone or storage policy are changed by this presentation fix. Source-process closure is separate from logical model cleanup and successful recording completion.

Use the single deployed Just Peachy shortcut, choose a backend/source, and press Start in the portrait application. The implementation runs through the normal launcher; do not execute these modules against an unadmitted production store.

Run the focused changed source-facts check from this source directory:

PowerShell:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B './check_source_failure_status.py'
```

CMD / Anaconda Prompt:
```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B check_source_failure_status.py
```

The check takes no arguments. It extracts the actual changed methods, validates
strict result/source-fact types and checks controlled missing/malformed receipts,
exact owner-probe routing and portrait failure wording. It registers CPU14 before
source reads and creates a fresh private receipt with exact source backups and
independent restores. It opens no production store, model, microphone or GUI.
The versioned package builder pins these sources before a fresh native admission.

Positive physical sample/start facts with missing source identity are fenced. Malformed
worker receipts are not treated as empty evidence, including a malformed receipt
with an independently absent known owner. Missing observations are presented as
unverified rather than "never started." An actual metadata CapacityError shows
"metadata storage limit" in the normal status; its full primary error remains in
diagnostics. Session19's historical extractor contradiction stays preserved:
actual capture/captions preceded failure, while its old null-result extractor
incorrectly reported no capture. This presentation change does not rewrite it.
