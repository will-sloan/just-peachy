# Bounded native script/reference check

Purpose: run existing Sherpa/Pyannote/ReDimNet on a small local prerecorded CMU
ARCTIC subset, build real optional references, and test fresh queries through the
ordinary C088 naming pipeline with alternate diagnostics enabled. No microphone,
speaker output, network, training, threshold tuning or automatic downloads.

From `C:\Users\amiri\Documents\GitHub\just-peachy`, PowerShell:

```powershell
& .\.edge-speech-env\python.exe prototype/tools/check_script_evidence.py --output Resumes/.uiiter2_09/native_new
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
.edge-speech-env\python.exe prototype\tools\check_script_evidence.py --output Resumes\.uiiter2_09\native_new
```

`--output` must be fresh and outside `prototype`. Optional `--corpus` points to the
existing `CMU Arctic` parent of `cmu_us_awb_arctic`, `cmu_us_bdl_arctic` and
`cmu_us_clb_arctic`; default is the repository's existing Raw Datasets directory.
Models resolve from the existing `JUST_PEACHY_MODELS`/shared model store. Do not
point outputs at production people or alter fixtures to satisfy a check.

Inputs: each speaker's original mono16k PCM16 files and `etc/txt.done.data`;
four complete reference recordings (awb/bdl a0001,a0003), fresh awb/bdl a0016,
outsider clb a0001,a0016; extended known query concatenates the **complete distinct
recordings** awb a0016–a0018, explicitly labelled as a constructed query. No query
is used for references. The same-person/same-text check reuses a reference and
is explicitly in-sample, not independent accuracy. No arbitrary phone fragments
are spliced into enrollment.

Outputs: `NATIVE_SCRIPT_CHECK.json`, private `PRIVATE_SCRIPT_EXAMPLE.json`, exact
profile vectors/sidecars, constructed query WAV, native session journals, timing,
sampled process RSS, model/source hashes and base/alternate raw scores. Keep the
whole folder private; use the redacted/synthetic public sample in docs to share
schema. The status distinguishes completed native execution, known confirmation
and outsider Unknown. Short query tentativeness is not relabelled as a confirmed
name. A nonzero exit or partial folder is failed/diagnostic evidence, not PASS.

Derived overlap (two real voices mixed once), low-level and 0.4s input test
quality/fallback; wrong/skipped/repeated intended-text variants reuse original
audio/ordinary ASR. No rerecording or accuracy study is implied. A tiny resident
dot-product timing comparison measures diagnostic-score overhead without another
model inference. Desktop resource measurements do not qualify CM5.
