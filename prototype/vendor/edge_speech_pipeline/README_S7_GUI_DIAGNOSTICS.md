# Bound the S7 diagnostic widget without delaying captions

The first real Tk C065 pilot preserved source/model timing but its GUI consumer reached31.21seconds of age, with1116queued events and an approximately79second wall run for44.70seconds of source. The policy queue stayed below3ms maximum age and scientific journal below30ms; first observed ready-text publication was39ms after that ASR source end but GUI consumption was11.68seconds later. This identifies a GUI-side delivery problem, not slow speaker inference. The original GUI serializes and appends every full scientific event, including long model vectors, to a word-wrapped diagnostic widget. The proposed repair tests bounded compact diagnostic batching; it does not claim an exact pre-repair split between JSON serialization and Tk rendering costs.

Build.py verifies/copies the51bound original application files into a fresh source_epochs/gui_diagnostics_v1. Only gui.py changes among those files. For opted-in S7 presentation, each GUI-dequeued event contributes a compact diagnostic summary capped at320characters. At most64pending summaries are kept; replaced diagnostic summaries are counted. A widget batch is flushed no more than every250ms during operation, with an explicit final flush. Complete scientific journal/consumer/trace recording and caption event rendering remain unchanged. Historical default GUI behavior is unchanged when S7 is absent. This is optional diagnostic-display coalescence, not scientific event dropping or caption coalescence. Batch timing and counts are acknowledgment records.

Inputs: immutable observed-presentation epoch and original real-GUI/continuous manifests and root job authorities. Outputs: repaired immutable epoch, SOURCE_REPAIR.json, and two HELD queues: gui_diagnostic_repair_pilot_v1 (same four GUI controls, fresh outputs) and observed_continuity_v2 (four integrated long sessions on the repaired epoch). Existing unsuccessful GUI outputs and the unstarted continuity_v1 preparation are preserved. Neither queue is launched by this script. GUI/native helper, runtime, producer, ASR, identity and profile/model settings are unchanged. Existing helper files remain bound at their original frozen locations.

PowerShell:

```powershell
$R7 = 'C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/reports/S7/20260917T141700Z'
$Py = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $Py -B "$R7/application/gui_diagnostic_repair_v1/Build.py"
```

Anaconda Prompt / CMD:

```bat
set "R7=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%R7%\application\gui_diagnostic_repair_v1\Build.py"
```

All outputs must be fresh. Read PREPARATION.json for exact queue/approval hashes. Before production launch, root must review bounded diagnostic fixtures, source changes and closure of the currently active native queue. Run the four repaired GUI pilots serially before admitting observed_continuity_v2. Use s7_runner_v1.py with the exact queue/approval paths/hashes and --state-dir; --validate-only first, then --keep-awake after review. Native inference remains one process at a time; no hardware, downloads or default promotion. Source32/headless controller/16-control evidence remains unchanged with its original epoch; do not silently relabel it as GUI-repaired evidence.

This repair is not M7 efficacy, power measurement or full GUI qualification. Actual queue-age and caption/widget timing must improve in new native tests before acceptance. All first-caption omissions/coalescence, unknown/name exposure and reference correctness remain scored separately. No arbitrary post-result timing threshold or identity threshold is relaxed.
