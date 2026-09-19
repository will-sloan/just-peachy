# S6D N6h calibration restart: one case, then eleven

Purpose: apply the independently reviewed tuple/list JSON closure-comparison repair to the existing twelve calibration jobs. Run one real case first. The remaining eleven require a separate root review of the actual pilot. This preserves the full research population while avoiding a large smoke batch. Old N6f/N6g failures remain unchanged and uncredited. All 48 application sources, model/audio inputs, source frames, three-journal/drain guards, profiles, no-overlap allocation, disk/payload limits and original deadline remain.

Inputs: exact pinned N6g queue/preparation/admission, N6h freeze and independent review, small diagnosis and original failed runtime closure. The script reuses the reviewed queue transformation and process-allocation functions from `s6d_C12_root_admit_v2.py`; it does not call its original production prepare/admit entry points. Preparation and launch both require complete current process inventory, absent old owner instances and sufficient storage. H2 maintenance is retained. No hardware is opened. One neural worker is allowed, and physical/other neural jobs must stay held until all twelve close.

Outputs: additive metadata under `simulation/reports/S6D/20260913T195357Z/runner/beam_C_queue_proposed_v4`, fresh runtime journals under `G:/Just_Peachy_S6D/20260913T195357Z/runner/beam_C_queue_proposed_v4`, and native outputs under `G:/Just_Peachy_S6D/20260913T195357Z/application/beam_C_collection_closure_wire_v1`. No original source audio or old run is changed. `pilot_QUEUE.json` has one original scientific job; `rest_QUEUE.json` has the other eleven. The shared manifest has all twelve, each with a fresh output path.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $python -B "$sim\scripts\s6d_C12_n6h_resume_v1.py" --prepare
# Root inspects actual prepared job/source/limit bindings and writes an exact review.
& $python -B "$sim\scripts\s6d_C12_n6h_resume_v1.py" --run-phase pilot --root-review '<root review path>' --root-review-sha256 '<its SHA256>'
# After actual pilot closure and separate root acceptance, use --run-phase rest.
```

Anaconda Prompt or Command Prompt (uses the existing environment directly):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PYTHON%" -B "%SIM%\scripts\s6d_C12_n6h_resume_v1.py" --prepare
"%PYTHON%" -B "%SIM%\scripts\s6d_C12_n6h_resume_v1.py" --run-phase pilot --root-review "<root review path>" --root-review-sha256 "<its SHA256>"
```

Preparation is not model execution. Root review must bind the exact `PREPARATION.json`, owner task, phase, and no-overlap policy. The rest review additionally binds `ROOT_ACCEPTED_ACTUAL_N6H_PILOT` evidence. Launch runs the existing V4 supervisor hidden, with keep-awake and its unchanged per-job validation/watchdogs. No automatic failed-run credit, forced termination or uncontrolled retry is permitted. Check the compact phase-state `CHECKPOINT.json` and immutable supervisor closure after completion; do not repeatedly rescan large journals or source audio.
