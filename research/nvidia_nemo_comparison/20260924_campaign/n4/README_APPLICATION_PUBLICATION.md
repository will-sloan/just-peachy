# Actual application publication method checks

Purpose: exercise the frozen PrototypeEngine/N2Engine/N3IdentityEngine
constructors and begin-mode routing, PipelineEngine._transcript_event,
_scheduled_event, _scheduler_advance, _s6d_punctuate and the actual inherited
_emit chain. This extends the earlier mode/Controller helpers to the producer
publication methods. It is explicitly modeled, not a complete live application
or GUI/first-visible/resource test.

Inputs: verified ASR/D0 commands or sealed D1 native events plus exact saved
float32 waveform; fixed GALLERIES.json binding; backend, mode, tap and matching
encoder namespace; safe per-scene session ID; exact final-formatting parents.
The same actual S7 bounded worker, tracker/name resolver, publication expiry,
caption state and recursive annotated display publication run. D1 uses its
actual engine RLock and activity/history/span methods through CooperativeActivity;
unfinished cached queries cannot license names for independently arriving text.

No weights, microphone, playback, enrollment or personal root is opened. The
actual constructor receives only model namespace metadata. The instance's
_begin_session is suppressed to avoid source/model/session-file startup; begin
itself and the publication methods are unchanged. Model acquisition and ONNX
construction are forbidden. Files in the frozen source are never edited.

Clock contract: one harness owner per process replaces only the runtime and
research_s7_presentation modules' local time references with a facade whose
perf_counter returns the injected monotone zero-origin clock. The global time
module, watchdog/condition deadlines and other processes remain unchanged.
Facades are restored after the policy worker exits, including failure paths.
Source cursor follows declared modeled 100-ms delivery plus the exact final
tail. Native D1 history and noise-coordinator host stamps remain diagnostics.
Inherited observed/GUI field names contain modeled values only. No clock in
these results qualifies as physical latency or first-visible naming evidence.

Outputs: a bounded private publication trace (all emitted kinds and exact
serials), actual unannotated state plus annotated display events, final raw
caption state, raw/final/formatting counts, worker closure and scope flags.
The display envelope intentionally retains the compatible modeled-mode schema
for controller_projection.py; publication_method_qualification distinguishes
this producer-method implementation. The full event trace omits startup/I-O and
ASR/D0 raw dispatch diagnostics; it is not an exact original full-session trace.
The actual application generates every retained publication sequence; numbers
are scoped to this harness. Integrated acceptance remains zero.

At most 120 seconds per scene, 100,000 commands/events, 512 retained caption rows
and 24 MiB serialized publication trace are admitted. Raw observation fields
must reproduce the exact sealed ASR parent. Formatting is applied once to its
exact raw final through the real punctuation publication method. Every query
waveform/namespace and short-run coverage must reproduce D1 component evidence.
The caller verifies hashes before invoking these APIs; keep detailed output
private. Never commit transcripts, roster names or vectors.

Tests from PowerShell in the campaign worktree:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_application_publication.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

Command Prompt / Anaconda Prompt (use existing interpreter; no installation):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_application_publication.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```

The test fixtures use the existing frozen source and temporary research E
metadata. No predictor receives Q labels, transcripts or activity truth. A
future coupled source/model/Controller/GUI test remains required for application
acceptance and observed delivery metrics.

`probe_application_publication.py` follows the sealed Controller/mode receipts
and verifies source, code, full gzip, exact audio and runtime/gallery bindings.
The predeclared smoke16 subset is selected-closed O0 for each of the 16 catalog
tuples; all160 covers five modes and both taps on the same two smoke sources.
It regenerates actual publication-method output, consumes it through the actual
Controller and compares all display-history/final projected semantic fields
against the preserved earlier method result. Differences are retained explicitly
as comparison results; passing execution alone does not mean parent parity.
The complete private artifacts retain all details for investigation.

The probe runs CPU14 below normal, single-thread math, GPU disabled, with no
neural model. It enforces C50/G75-GiB floors, a 512-MiB fresh output cap and the
packaging cutoff. Existing private bytes plus 6 GiB conservative pending
ASR/D1/contingency/helper reserves must fit the shared allowance (at most 50 GiB).
ADMISSION.json binds its exact code and PID/creation identity before execution;
RESULT.json or FAILED.json preserves the outcome. Do not edit bound files or
overwrite old attempts. Reuse only a passed unchanged smoke16 result; all
compressed/expanded artifacts are reverified and reused cases are explicit.

PowerShell (same variables as above):

```powershell
& $jpPython -B "$jpCode\probe_application_publication.py" --scope smoke16 --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\publication-smoke-v1'
# Review every comparison before proceeding; preserve failures/differences.
& $jpPython -B "$jpCode\probe_application_publication.py" --scope all160 --reuse 'G:\Just_Peachy_N1\20260924_campaign\local\n4\publication-smoke-v1\RESULT.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\publication-modes-v1'
```

Command Prompt / Anaconda Prompt:

```bat
"%JP_PY%" -B "%JP_CODE%\probe_application_publication.py" --scope smoke16 --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\publication-smoke-v1"
rem Review the complete smoke result before continuing.
"%JP_PY%" -B "%JP_CODE%\probe_application_publication.py" --scope all160 --reuse "G:\Just_Peachy_N1\20260924_campaign\local\n4\publication-smoke-v1\RESULT.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\publication-modes-v1"
```
