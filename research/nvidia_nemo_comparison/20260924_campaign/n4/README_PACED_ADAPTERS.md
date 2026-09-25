# N4 application roster and source clock adapters

Purpose: prepare the actual source-paced Controller runs without changing the
frozen application, inference, naming policy, template vectors or GUI. These
adapters are not a completed N4 application evaluation or candidate shortlist.

`paced_adapters.py` provides `PacedResearchPeople`, a fixed read-only view loaded
through the verified N4 gallery preparation, and `CountedBaselineGallery`, which
counts real attempted calls and delegates each score to ResearchGallery unchanged.
N2Gallery retains its existing implementation and query counter. The facade
checks the exact tap/gain/preprocessing/bypass route and fixed selected roster.
It has no enrollment, mutation, promotion or personal-profile import API.
Original baseline C088 thresholds remain nominal; N2 open gates remain the
prepared reject-all gates. Closed choices are assumptions, not recognition.

`ConsumerSourceClock` installs an instance observer at Controller._adaptation_event
before a fresh session. It delegates the original hook once with the same event,
including preserving original exceptions. It records the original FileSource
source_started origin separately from consumer receipt time. A changed engine,
epoch, source, duplicate start, malformed clock or observer error invalidates the
clock evidence without interrupting the normal consumer. Counters and up to 32
violations are bounded; no full transcript/vector event history is retained.
It must be detached after the consumer exits, with ownership checked. Make a
new observer for each independent scene; do not reset it at reference turns.

The clock alone does not verify actual source delivery, sample counts, journal
closure, inference, complete publication or source-to-widget latency. Those must
be joined to the future actual FileSource, journal, consumer and widget receipts.
This qualification uses synthetic source events through the real consumer, not
source execution. The observer never replaces the payload origin with its own
receipt stamp. Optional adaptation, alternate scoring and enhancement stay off.

## Inputs and outputs

`probe_paced_adapters.py` reads APPLICATION_PUBLICATION_CHECK_V1.json for the
immutable source and prepared research galleries; ACCEPTED_SOURCE_CATALOG_CHECK
provides the two pinned runtime manifests. No evaluator truth/audio is supplied
to prediction; no microphone, USB, playback, GUI or model is opened. Existing
E-vector rows, negative rows and zero-vector tie controls exercise unchanged
scores over 16 catalog tuples x 5 modes x 2 taps. Three actual Controller/engine
classes consume fixture source events and complete their original final drain.

Seven tests cover score equality/counting, route/roster rejection, no template
change, clock validation/order, duplicate/foreign epoch rejection, delegate error
behavior and ownership/teardown. Model acquisition and ONNX construction are
forbidden during the tests. The output must be a fresh directory beneath private
local/n4. Outputs: immutable ADMISSION.json, unittest.txt, CHECKS.json, RESULT.json
and isolated Controller fixture directories. CHECKS contains research identities
only indirectly through private app artifacts and must remain outside Git.

The helper pins CPU14, one math thread, GPU off, below-normal priority; it checks
the shared 50-GiB allowance with 6 GiB reserved, drive floors and packaging reserve.
It may accompany component extraction because it loads no neural model and makes
no controlled resource or pacing claim. Actual neural source-paced tests must
wait for the sole model slot and all other evaluation helpers to finish.

## Run from PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'research\nvidia_nemo_comparison\20260924_campaign\n4\probe_paced_adapters.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-adapters-v1'
```

## Run from CMD or Anaconda Prompt

No new conda activation/install is needed; use the existing pinned interpreter.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_paced_adapters.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-adapters-v1
```

Never overwrite an attempted output or change its bound code. A failure is
preserved and a repair needs fresh derivative code and a new output directory.
Full paced panel admission, source/journal closure, resource accounting, timing
repeats and continuity still require separate implementation and real runs.
