# Complete empty-caption sessions through the actual Controller

Purpose: allow a successful saved-audio run with no ASR output to finish normally
through the real Controller. An empty hypothesis must retain every missed
reference word in later scoring; it must not be turned into a failed execution
or an invented caption. A preliminary audit of the closed A0 metadata found
19 zero-observation cells out of 480; the full ASR terminal review is still
required. No reference text or activity enters this predictor path.

`controller_projection_v2.py` is a fresh copy of the immutable V1 implementation,
with an explicit complete-empty-publication admission path and an output flag.
V1 and its running 160-case publication probe remain unchanged. Nonempty input
validation, actual Controller construction/backend/mode switch/consumer/snapshot/
closure/cleanup and inference forbidding retain the V1 implementation. See
README_CONTROLLER_PROJECTION.md for the original API and timing limitations.

Inputs: the same verified modeled publication result, fixed gallery binding,
explicit audio tap, N2/N3 runtime metadata and fresh private Controller directory.
An empty result additionally requires publication_method_qualification from
application_publication.py, zero raw/final/formatting counts, empty actual state,
a closed fully drained policy worker, contiguous ordered publication serials in
one session, and exactly one closing watermark for each source lane. Any raw
ASR, caption, text-ready, punctuation or transcript event makes an empty display
invalid. Arbitrary empty JSON and missing output are rejected.

Outputs: the same private Controller projection result with display_inputs=0,
empty history/final/raw rows, actual consumer closure and closed owner/thread
checks; empty_caption_session distinguishes this case. Actual Controller counts
the completed empty session. No placeholder caption/name is emitted. Model
acquisition remains forbidden and saved_audio_only remains enabled. This is
modeled method evidence, not GUI visibility, real-time latency, full coupled
inference or N4 acceptance. The Pi and user desktop are untouched.

Tests use actual publication methods and frozen research/runtime metadata,
covering empty anonymous/named paths, hidden-text/incomplete/foreign/corrupt
closure rejection, and nonempty baseline/N2 regression. Outputs are temporary
private Controller directories. No model, hardware, audio synthesis or personal
profile is used. Callers must reverify complete source/result bindings before
production reuse; these tests are not bank admission.

PowerShell from the campaign worktree:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_controller_projection_v2.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

Command Prompt / Anaconda Prompt (existing interpreter):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_controller_projection_v2.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```

`probe_empty_publication.py` verifies the complete gzip data and actual command
closure for all 19 zero-observation A0 files, joins their reviewed D0/E0 evidence
by exact audio/job/admission binding, and checks anonymous and selected-closed
baseline modes (38 cases). It follows EMPTY_ASR_OUTPUT_AUDIT_V1.json, the public
D0 full-bank review and fixed Controller/gallery receipt. A0's whole ASR bank
still awaits terminal review: this is closed-cell development evidence only.
The probe writes a fresh ADMISSION.json, private publication/projection gzip and
Controller closure receipts, then RESULT.json or FAILED.json. The same CPU14,
C50/G75 floors, shared inventory/reservations, 512-MiB cap and packaging cutoff
as the publication probe apply. No model is loaded, no existing evidence edited.

PowerShell / Command Prompt / Anaconda, with the variables above:

```powershell
& $jpPython -B "$jpCode\probe_empty_publication.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\empty-controller-v1'
```

```bat
"%JP_PY%" -B "%JP_CODE%\probe_empty_publication.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\empty-controller-v1"
```
