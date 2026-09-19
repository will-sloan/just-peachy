# Opt-in S6 anonymous tracking

`research_tracking.py` implements five causal, bounded research trackers used by
the actual H2 application and the S6A replay harness. The production default
`SpeakerTracker` is unchanged. These methods are exploratory configurations,
not a demonstrated identity system or a CM5 qualification.

Inputs are a normalized, 192-dimensional ReDimNet2 embedding, its exact audio
span, its availability time, speech/overlap flags, and optionally a delivered
XVF observation. All times must share one explicit seconds axis. Historical
capture QPC cannot be mixed with accelerated inference wall time. Reference
identities, transcripts, source schedules, rooms, seats, and future samples
are not accepted by this interface.

Outputs include anonymous/provisional/committed track IDs, unique evidence
seconds, creation/commit/prototype/proposal lineage, reasons for Unknown, and
the source and availability times. A direction change is only a proposal;
there is no automatic ASR reset, retroactive correction, named identity,
forced speaker count. A qualified direction-change/voice-conflict event can
create an explicit provisional branch from an established track. If fresh,
overlapping acoustic evidence confidently returns to its established parent
(cosine at least 0.65), a branch that is still provisional can merge within a
two-second revision horizon. The tracker emits forward label-revision events
referencing immutable first decisions; uncertain branch vectors/evidence are
not pooled. The revision queue is capped at 64 records. These operations are
tested mechanisms and must be separately counted in real-bank results; a
fixture does not establish that a bank revision was correct.

The spatial-only mode is explicitly an
anonymous location diagnostic, not a person tracker. Native angles are linear
0–180 degrees, so the endpoints are not adjacent. Missing/stale/reordered
metadata falls back to voice-only association in fusion modes.

The configuration validates ranges and caps track storage at 16 by default
(64 maximum). A prototype contributes only newly covered audio seconds;
overlapping windows do not count as independent evidence. Prototype updates
require voice similarity at least 0.45, separately from association at 0.35.
The values are initial engineering settings, not calibrated probabilities.

## Run tests in PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest -v test_s6a_cues
```

## Run tests in Anaconda Prompt or Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" -m unittest -v test_s6a_cues
```

The tests need NumPy but do not load model checkpoints or open hardware. See
`simulation/scripts/README_S6A_CUES.md` for extraction, all-scene replay and
scoring commands. The application research-profile README describes the
explicit CLI opt-in. To roll back, omit the research profile; no GUI default
is changed by this module.
