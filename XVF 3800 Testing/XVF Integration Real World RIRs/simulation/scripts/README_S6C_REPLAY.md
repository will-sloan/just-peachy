# Shared native-policy replay

`s6c_replay.py` feeds verified actual neural observations through the same v3
incremental scheduler, anonymous tracker and identity resolver used by the
native application. It does not create embeddings, infer reference speakers
or rename a final transcript in the evaluator. Each source timestamp is
released only after both lanes seal its availability. Partial/final words,
initial/latest labels, names, forward revisions and bounded state are retained.

Inputs are a frozen S6C execution epoch, exact effective profiles, bound S6B R0
native receipts/vectors/segmentation/ASR and optional frozen cue variants.
N00 reuses historical .5-second single-lane vectors in the mature API role so
prototype updates remain active; it is explicitly not new long-mature evidence.
Clean intervals are reconstructed from the actual latest arrived powerset
frames using the original 16.875ms frame-center convention, and must reproduce
the native stored clean fraction. Reference speech boundaries never enter.

Outputs are gzip JSON predictions under the S6C G: payload and a compact bound
prediction index/status in the S6C report. Exact matching results are reused;
changed identities require a new named source epoch/revision. Compressed output
preserves all decisions and event rows; it is not selective reporting.

## Commands

Run after the frozen epoch and required cue variants exist. For a targeted
ordinary-cue smoke, provide candidate IDs from the effective registry with
`--candidates`; omitting it includes all registered N00 conditions and requires
the frozen diagnostic cue index. `--panel all` selects all 240 scenes/both taps.

PowerShell:

```powershell
$env:JP_S6C_SIM='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cReplay=Join-Path $env:JP_S6C_SIM 'staging\s6c\20260910T123540Z\epoch1\scripts\s6c_replay.py'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' $s6cReplay --epoch epoch1 --panel challenge --candidates C011 C012
```

Anaconda Prompt / CMD:

```bat
set "JP_S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%JP_S6C_SIM%\staging\s6c\20260910T123540Z\epoch1\scripts\s6c_replay.py" --epoch epoch1 --panel challenge --candidates C011 C012
```

The same command resumes identical predictions. A native-evidence hash or
clean-support parity error stops the run. Gzip JSON can be read with
`s6c_replay.read_prediction(path)`. `run_policy(..., cutoff=...)` exposes the
same incremental API for prefix/different-future checks, without finishing or
accessing later input events. Native event clocks remain distinct from modeled
replay readiness and measured policy cost. This is never a substitute for
actual changed frontend inference, split-route checks or paced endurance.

Only NOMINAL_GEOMETRY_DIAGNOSTIC may use explicitly marked truth-derived
numeric angles; that condition is oracle-like and cannot support deployment
or independent-performance claims. Normal conditions reject reference fields
at the shared scheduler/provider boundary. See README_S6C.md for resources,
stop and rollback; no hardware playback occurs here.
