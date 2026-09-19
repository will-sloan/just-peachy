# S6C joint anonymous tracker

`research_tracking_v3.py` is the versioned opt-in S6C policy used by the shared
native/replay scheduler. It preserves the default and v1/v2 code. It does not
read a recording, model, reference transcript, roster or private gallery.

## Inputs, outputs and purpose

Input is a finite normalized 192-dimensional ReDim embedding, its actual .5–3 s
contiguous waveform support, causal availability, short/mature role, optional
arrived segmentation clean-support estimates and a delivered XVF observation.
No nominal geometry/person truth is accepted by this predictor. A diagnostic
provider may be supplied by the explicitly labeled offline study.

`S6CTrackingConfig.from_mapping({...})` validates settings and rejects unknown or
changed inactive fields. `S6CTracker(config).update(...)` returns an anonymous
decision with immutable decision ID, source/availability clocks, joint scores,
cue authority, lifecycle counts and append-only lineage events. `snapshot()`
returns bounded state and counters. Names are handled separately by the shared
v3 identity resolver after association. `scheduling_state(now)` is only for the
owning scheduler: the inference lane consumes an already published snapshot
whose availability does not exceed its dispatch, never future mutable state.

Eight modes implement an old voice-gate control, joint normalized/reliability
scores, bounded temporal hypotheses, semi-Markov dwell penalties, bounded
global arrived-voice reconciliation, prototype escrow/rollback and a clean
shadow prototype. NEW and UNRESOLVED compete with existing hypotheses in joint
modes. A severe voice conflict is never rescued by bearing. Scores/tempered
hypotheses are engineering quantities, not calibrated identity probabilities.

Live capacity counts active plus dormant tracks. Retirement moves eligible
tracks to a bounded archive or discards their state; archive reentry requires
strong voice agreement. External integer IDs increase and are never recycled.
Prototype/revision/hypothesis/seen-event buffers are finite. Unique clean
duration is an interval union, with separate role-specific mature disjoint
counts so a short observation cannot starve the mature lane. Whole-span legacy
gates are labeled estimates and not exact phonetic activity.

Structural split/merge are explicit off-by-default experiments. Splits create
an actual child track after rollback evidence; merges retire an actual track
and emit lineage. Neither changes preserved initial transcript decisions.
Retained clean duration at merge is a conservative maximum, since old
compressed supports cannot be safely added. Native tests and corpus results
are required before making any recommendation.

## Run the model-free smoke check

PowerShell (the environment already exists):

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\app'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -c "import numpy as np; from edge_speech_pipeline.research_tracking_v3 import S6CTracker; t=S6CTracker(); v=np.eye(1,192,dtype=np.float32)[0]; print(t.update(v,0,.5,.51)); print(t.snapshot()['counts'])"
```

Anaconda Prompt or CMD (use the existing project interpreter, no install):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\app"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -c "import numpy as np; from edge_speech_pipeline.research_tracking_v3 import S6CTracker; t=S6CTracker(); v=np.eye(1,192,dtype=np.float32)[0]; print(t.update(v,0,.5,.51)); print(t.snapshot()['counts'])"
```

This prints a constructed-vector decision/state and creates no files. It is a
reachability smoke check, not model inference or empirical speaker accuracy.
The S6C campaign README and generated exact profiles document full-file,
gallery, cache, replay, paced, resume and rollback commands after integration.

## Status and rollback

Implementation is under pre-freeze review. No S6C profile is a default or a
qualified CM5 configuration. To leave this branch unused, run the historical
entry without a v3 research profile. The exact pre-S6C application snapshot is
listed in `simulation/reports/S6C/20260910T123540Z/INTAKE_AND_SNAPSHOT.json`.
Do not overwrite a running or frozen epoch, reset Git, or replace unrelated
user edits to roll back an opt-in experiment.
