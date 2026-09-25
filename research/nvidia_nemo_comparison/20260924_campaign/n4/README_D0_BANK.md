# Full-bank D0 component evidence

`d0_bank_components.py` executes the unchanged frozen D0 speaker lane on all
480 accepted saved scene/tap files, first with E0, then E1 in separate sequential
processes. The purpose is reusable actual segmentation and exact embedding
evidence for downstream N4 comparison. This is 960 component cells, **zero
integrated ASR/diarization/identity cells** until integration actually runs.

Inputs: the verified prior C-collection admission (source/model bindings only),
accepted `preparation-v2/AUDIO_ONLY_480.json` and its preparation receipt,
existing waveforms/models, conservative payload inventory and fresh output root.
All waveform hashes and headers are checked before preparation and each run.
The model receives audio only, at the manifest's existing once-applied gain.
There is no C/Q truth, roster, text, activity annotation or name in the predictor.
The C-fit proposal failed; this component collection does not adopt it or claim
that D0/E1's nominal association profile is qualified.

The collector reuses the tested `LaneCapture` and the actual immutable
`run_speaker_lane_v3`. Fixed cadence without cues is mandatory, so query-window
selection does not depend on ASR, tracker scores, names or future data. The
speaker lane reads ordinary sequential 0.25-second dispatches, has the original
Pyannote ten-second left-padded receptive field, and resets once per scene. It
preserves partial unanalyzed tails. E0/E1 receive exact real contiguous windows,
whose float32 waveform hashes, clean intervals and short/mature roles persist.

Outputs: immutable admission and worker spec; per-encoder per-scene
`RESULT.json` with actual vectors and exact query geometry; complete
`LANE_EVENTS.jsonl.gz`; progressively updated indexes and a terminal result.
The entire event stream is compressed as it is written, then decompressed to EOF
to verify its gzip CRC and record expanded SHA-256/byte count. Raw probabilities,
speech/overlap masks and rejected embedding admissions are retained. No original
file is pruned. Vectors, events and complete per-cell evidence stay outside Git.

The cache key binds admission, audio, tap/gain, encoder, actual profile, causal
state/reset and execution policy. Admission binds source/model hashes and exact
Python/NumPy/ORT/SoundFile/psutil versions. Altered waveform windows, model,
preprocessing, source, profile, state or runtime invalidate reuse. This supplies
no ASR or track assignment and cannot be silently promoted into a complete
application result. Accelerated call times are not live caption latency.

One model process uses CPU4, one thread per model, CPU-only ORT; the coordinator
uses CPU14. No candidate overlaps another. One resident encoder plus Pyannote
is reused across independent scenes; a fresh child releases it before changing
encoder. No GUI, audio playback, microphone, training or hardware calls occur.
New storage is capped at 4 GiB, with 32 MiB reserved before every <=120-second
clip. The conservative inventory plus this allocation and a further 1 GiB
contingency must fit the existing 50 GiB allowance. Physical C:50/G:75 GiB floors
and the packaging cutoff are checked per clip. This is a cooperative guard,
not an OS filesystem quota or complete-stack resource qualification.

A failed lane stops the run and preserves all completed/failed evidence. A
fresh run is required for a different contract. There is no automatic in-place
retry; before recovery inspect exact process identities and retain checkpoints.
On completion, verify E0/E1 window geometry with `validate_pair` from the paired
review tool, adapting only the full-bank index/manifest schema in a new reviewer.
The C-only review command does not accept this different population.

PowerShell preparation:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\n4\d0_bank_components.py" prepare --collection-admission "$jpLocal\n4\d0-calibration-v1\ADMISSION.json" --manifest "$jpLocal\n4\preparation-v2\AUDIO_ONLY_480.json" --payload-inventory "$jpLocal\n4\payload-inventory-20260925T0224-v2.json" --output "$jpLocal\n4\d0-bank-v1" --state "$jpLocal\supervision"
```

After verifying the numerical slot is free, use the existing supervisor:

```powershell
& $jpPython -B "$jpCode\supervision\supervisor.py" phase --root "$jpLocal\supervision" --phase inference --stage N4
& $jpPython -B "$jpCode\supervision\supervisor.py" start --root "$jpLocal\supervision" --spec "$jpLocal\n4\d0-bank-v1\worker.json"
```

The supervisor host may inherit the launcher's affinity. Verify exact PID and
creation time before restricting only the owned host to CPU14. The numerical
child independently pins CPU4 before model import/load. Prefer launching the
supervisor from a process already restricted to the admitted CPUs [4,14].

Command Prompt / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\n4\d0_bank_components.py" prepare --collection-admission "%JP_LOCAL%\n4\d0-calibration-v1\ADMISSION.json" --manifest "%JP_LOCAL%\n4\preparation-v2\AUDIO_ONLY_480.json" --payload-inventory "%JP_LOCAL%\n4\payload-inventory-20260925T0224-v2.json" --output "%JP_LOCAL%\n4\d0-bank-v1" --state "%JP_LOCAL%\supervision"
"%JP_PY%" -B "%JP_CODE%\supervision\supervisor.py" phase --root "%JP_LOCAL%\supervision" --phase inference --stage N4
"%JP_PY%" -B "%JP_CODE%\supervision\supervisor.py" start --root "%JP_LOCAL%\supervision" --spec "%JP_LOCAL%\n4\d0-bank-v1\worker.json"
```

`test_d0_bank.py` tests cache separation, truth/gain/reset rejection, exact gzip
bytes and corrupt trailers, storage headroom and the packaging cutoff. It uses
temporary fixtures and mocked limits, with no models or saved-audio reads.

```powershell
& $jpPython -B -m unittest discover -s "$jpCode\n4" -p 'test_d0_bank.py' -v
```

```bat
"%JP_PY%" -B -m unittest discover -s "%JP_CODE%\n4" -p "test_d0_bank.py" -v
```
