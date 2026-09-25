# D0 full activity evidence observer

`d0_activity_evidence.py` implements `D0ActivityEvidence`, a bounded, causal
observer for N4 integration. Its purpose is to retain the entire scene timeline:
detected speech without an embedding, silence, overlap, as-yet-unobserved source,
actual anonymous track support and conflicting track claims. It does not run a
model, change an application decision, use references, fill missing track IDs or
replace the production scheduler. **It is not yet connected to the integrated
runner or Controller; its tests are implementation evidence only.**

Inputs are the scene sample count, an explicit modeled or observed clock kind,
full `research_segmentation` binary masks and the actual anonymous scheduler
decisions joined to their original embedding observation's clean intervals.
Call segmentation/track methods in availability order, using distinct immutable
event IDs. The caller must hash-verify source logs and bind decision/observation
IDs; this module cannot authenticate arbitrary Python objects. For observed
mode, supply the actual `observed_available_at_sec`, never a modeled timestamp
under that name. No names, gallery scores or reference boundaries are accepted.

Output is `snapshot()`, a JSON-serializable dictionary covering exactly [0,
source duration], including the unanalyzed tail. It records first and latest
mask observations with their original availability, and every exact supporting
track event. The original 16.875-ms frame-cell support uses exact half-sample
ticks around the model's frame centers (61.9375-ms receptive duration). This is
the existing estimated frame convention, not a phonetic boundary or alignment.
Raw source probabilities/logs must still be retained separately.

Each clean track claim is intersected with actual mask support. It never extends
past that claim's clean interval. Multiple distinct IDs become an explicit
conflict; overlap stays unassigned to global sources. Provisional and unresolved
claims remain flagged. This is the union of observed support claims, not an
inferred lineage resolution: a later different track does not silently rewrite
an earlier claim. First-mask observation is not first caption/widget visibility.
Snapshots are detached copies; later observations cannot mutate earlier reports.

An unassigned speech span is **not** one shared unknown person. Do not turn all
such spans into a collapsed `Unknown` speaker, delete them from the denominator,
or substitute clean embedding windows for the detected speech timeline. The
output deliberately has `global_diarization_or_DER_qualified: false`. A complete
global-source decoder/scoring contract and actual application parity remain
required before claiming full D0 DER or integrated N4 acceptance. Supported
speech, unassigned speech, conflicts, overlap and unobserved duration can already
be reported as explicit coverage diagnostics. No primary metric is improved by
hiding unsupported regions.

Default bounds: one scene <=120 seconds, 4,096 events, 100,000 retained intervals,
at most 1,000 frames per segmentation call. Exceeding them raises an error;
history is not silently dropped. This is an offline evidence observer; its
allocation is not included in a claimed CM5 application memory qualification.

From PowerShell, run the model-free integrity tests:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_d0_activity.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

Command Prompt / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_d0_activity.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```

Integration usage (imports work when this directory is on `sys.path`):

```python
from d0_activity_evidence import D0ActivityEvidence
observer = D0ActivityEvidence(job['frames'], clock_kind='modeled_component_availability')
observer.segmentation('segmentation:00000001', verified_segmentation_payload)
observer.track('decision:00000001', source_start_sec=embedding['source_start_sec'],
    source_end_sec=embedding['source_end_sec'], available_at_sec=decision_available_at,
    track_id=decision['tracker_id'], clean_intervals=embedding['clean_intervals'],
    observation_id=embedding['event_id'], committed=decision['committed'])
private_activity = observer.snapshot()
```

The example variables represent verified real producer objects; do not invent
them or use evaluator identities. `test_d0_activity.py` uses synthetic metadata
only, with no audio capture, synthesis, model, personal profile or network use.

## Actual closed-cell development probe

`probe_d0_activity.py` verifies one to four already-closed component cells, then
feeds their genuine segmentation/embedding events to the frozen native
`build_s6c_policy` with the unchanged nominal anonymous profile and no gallery.
It compares incremental strict-watermark release with a batched causal-scheduler
control, requiring identical anonymous decisions. It also exercises the observer
against real masks and real tracker decisions. No ASR or model inference runs;
ONNX session construction is explicitly forbidden. This is not S7 observed-clock
Controller/application parity, integrated inference, full-bank acceptance or a
calibrated D0/E1 comparison. It uses CPU14 and preserves every producer file.

Inputs: full-bank admission/source/runtime bindings, a closed index entry, exact
audio and event hashes and the listed job IDs. Output: a fresh private directory
containing full activity/decision diagnostics and a small `RESULT.json`. Failures
leave a `FAILED.json`; choose a fresh directory after a repair. Never publish the
per-cell trace as a personal profile or a full global diarization annotation.

```powershell
& $jpPython -B "$jpCode\probe_d0_activity.py" --run 'G:\Just_Peachy_N1\20260924_campaign\local\n4\d0-bank-v1' --encoder E0 --job N2_S45_01_01_O0 --job N2_S45_01_01_O1 --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\d0-activity-probe-v1'
```

```bat
"%JP_PY%" -B "%JP_CODE%\probe_d0_activity.py" --run G:\Just_Peachy_N1\20260924_campaign\local\n4\d0-bank-v1 --encoder E0 --job N2_S45_01_01_O0 --job N2_S45_01_01_O1 --output G:\Just_Peachy_N1\20260924_campaign\local\n4\d0-activity-probe-v1
```
