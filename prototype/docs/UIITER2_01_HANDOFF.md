# UIITER2 task 01 — live timing and Stop

Implemented locally on 20 September 2026 against Git baseline
`5b12f88430e619e37ce3397e005ca683b1fb9094` (PROTO1 0.1.4). No automatic commit,
push, replacement export, new model, sweep or later task was started.

## Cause and confidence

Four original 19 September sessions failed with the exact reported
`LIVE_SOURCE_TIMING: source support is ahead of the fixed capture timeline`.
They admitted 5,120 / 6,880 / 10,400 / 13,920 model samples before failing;
each recorded zero dropped native frames and the 110 ms latency-estimate
fallback. Their original logs remain in
`C:\Users\amiri\JustPeachy\data\sessions`. Today's newest pre-task log instead
failed endpoint discovery before capturing any samples; that is a separate fault.

The old bridge anchored sample zero to **first callback arrival − estimated input
latency**, then treated that as an exact fixed capture timeline. The first
callback can be late, while later callbacks arrive in driver batches. A latency
estimate is not a bound on that changing arrival delay. A deterministic 22-block
fixture reproduces a 25 ms false lead in the old expression with contiguous,
valid input; the repaired frame-count contract accepts the identical samples.

Actual metadata probes also found future ADC values on the installed WASAPI
path, explaining the fallback. sounddevice 0.5.5 and the installed PortAudio
V19.7.0-devel DLL hashes are recorded in `UIITER2_01_CHECKS.json`. The upstream
[PortAudio 19.7.0 reference](https://github.com/PortAudio/portaudio/blob/v19.7.0/src/hostapi/wasapi/pa_win_wasapi.c#L4559-L4568)
contains the same future-ADC construction observed here, but the bundled DLL's
precise source revision is unknown. The [sounddevice stream contract](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html)
distinguishes callback/ADC time and describes latency as an estimate.

**Confidence:** the invalid bound and its causal failure are demonstrated. The
historical sessions did not save per-callback traces or loaded-code hashes, so
their exact jitter/rate sequence cannot be reconstructed. Zero drop flags alone
do not establish fault-free hardware. New epochs record source/config hashes
and bounded timing traces; no historical evidence was relabeled as a pass.

## Changed contracts

| Location | Change |
|---|---|
| `app/live_audio.py:437` | Record perf-counter bounds around actual stream start; bind first admitted frame to the exact priming count and a fresh epoch. Separate post-Stop restoration frames from startup priming. |
| `app/live_timing.py:16` | New integer native/model continuity checker. Fixed origin uses stream-start entry plus counted priming, independent of callback arrival jitter and reported latency. Reject stale epochs, count/phase mismatches, impossible host ordering, priming discontinuity and frames ahead of the startup bound. |
| `app/live_timing.py:58` | Validate against callback time before journal admission; a delayed consumer cannot hide an impossible block. Retain 64 diagnostic rows, not audio. |
| `app/pipeline.py:181` | Use that immutable origin, retain the existing bridge and S7 timing guards, emit structured failure/stop evidence and actual runtime bindings. |
| `vendor/edge_speech_pipeline/runtime.py:972` | An already reported source failure re-raised by Stop no longer bypasses lane joining, scheduler finalization and recoverable transcript/writer cleanup. State remains FAILED. |
| `app/controller.py:110` | Preserve terminal failures, retry incomplete source cleanup before ownership release, and clear the old GUI error only on a fresh epoch after cleanup. |

Integer sample counts remain canonical. The causal factor-three FIR is unchanged:
its last emitted sample needs no future input, while its exclusive output interval
can extend two native ticks beyond that receptive support. The scheduler origin
accounts for exactly `2/48000` s of representation offset, separately from the
unchanged 1 ms FIR delay. There is no timestamp clamp, rebase, widened tolerance,
added pacing sleep, gap padding, gain change or discarded accepted speech.
The startup bound is a feasibility check, not acoustic-latency calibration.

## Executed checks

| Check | Actual result |
|---|---|
| Final focused suite | **156 passed**, no failures/errors/skips; 10.65 s. Includes delayed first callback, batched/variable blocks, partial tails, delayed consumers, mismatches, disconnect/overrun, ownership, enrollment cleanup, gains and existing UI/spatial contracts. |
| Real Balanced/O0 → Strong spatial/O1 transition | **6.06 s on each tap**, both native COMPLETED; zero drops, restored routes and unchanged Windows render defaults. |
| Two immediate real Start/Stop cycles | Both completed and released capture; 160 accepted samples each, with remaining unaccepted tail explicitly accounted. |
| Native prepared speech | **96,073 samples**, including a 73-sample final partial dispatch; final transcript events produced. No microphone playback. |
| Final capture-accounting check | **5.06 s**, zero drops, native COMPLETED and closed. |
| Injected bad endpoint → actual fresh Start | Expected failure cleaned up; **5.07 s** subsequent capture completed, GUI error cleared, original failure receipt unchanged; 8.98 s total check time. |

The five-case native lifecycle run took **29.65 s wall / 5.80 s process CPU**,
with **437.75 MiB observed peak process RSS**. ASR and speaker models each loaded
once across five streams. These are desktop observations, not CM5 qualification.
The final runtime/config and test hashes, detailed scopes and original-log hashes
are in `UIITER2_01_CHECKS.json`; full private receipts remain under
`C:\Users\amiri\Documents\GitHub\just-peachy\Resumes\.uiiter2_01`.

Human scripted Start → speech → Stop accuracy is **AWAITING_USER** because the
user consented to unattended tests and stepped away. Live hardware lifecycle was
tested; actual speech processing was tested with the existing prerecorded fixture.
No unattended enrollment was performed. Long-session oscillator drift, physical
CM5/ARM64 and acoustic latency are **NOT_TESTED**. A true rate/clock discrepancy
still fails explicitly. No blocker prevents the next queued implementation task.

## Launch, toggles and rollback

Close any existing prototype window normally. PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
& .\prototype\Start-Prototype.ps1
```

CMD/Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
prototype\Start-Prototype.cmd
```

All existing modes, recipes, spatial display and applicable O0/O1 choices remain.
There is no new timing toggle. Start still requires microphone consent. Stop
keeps captions/failure evidence; a new Start creates a new audio/identity epoch.
Personal profiles/configuration and model hashes are unchanged. An old
`runtime.lock` belonged to absent PID 195776; it was preserved under the rollback
folder rather than deleting data or terminating a process.

For rollback, close the app normally and launch the preserved original source
alongside the modified checkout. This does not overwrite current work or people:

```powershell
$jpOld = 'C:\Users\amiri\Documents\GitHub\just-peachy\Resumes\.uiiter2_01\rollback\source_5b12f884'
Expand-Archive -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\Resumes\.uiiter2_01\rollback\prototype-before-5b12f884.zip' -DestinationPath $jpOld
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$jpOld\prototype\main.py" gui --data-root 'C:\Users\amiri\JustPeachy\data' --models 'C:\Users\amiri\JustPeachy\shared\models'
```

Extract once to that unused directory; later launches can omit Expand-Archive.
In CMD/Anaconda, run the same quoted Python path followed by the full extracted
`main.py` path and arguments. Do not restore the defunct runtime lock. The backup
ZIP SHA256 is in the checks receipt. It includes source/tests only, never people
or voice recordings. Reproduction tool inputs/outputs and commands are in
`../tools/README_LIVE_TIMING.md` and `../app/README_LIVE_TIMING.md`.
