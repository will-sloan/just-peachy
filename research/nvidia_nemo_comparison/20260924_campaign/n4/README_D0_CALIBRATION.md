# D0 C-only short/mature evidence collection

`d0_calibration_windows.py` extracts calibration evidence with the unchanged
`run_speaker_lane_v3` from the frozen `n4-catalog-v3` application. The earlier
N2 C vectors represented whole clips; D0's actual fixed-cadence query windows
are 0.5 and 1.5 seconds. This collection supplies both encoders with the same
actual predicted-clean waveform spans. It does not choose a threshold, fit a
tracker profile, change the application or certify names on processed audio.

Inputs are the accepted N2 window manifest, frozen N4 application receipt,
existing CPU model binding and model files. Preparation verifies source hashes,
the original E0/E1 split contracts, C/E/Q source-ID and PCM-hash disjointness,
and all 367 whole C waveform bindings. The 1,239.816 seconds of clean C audio
are existing reference recordings, not a new acoustic bank. Identities live in
`C_LABELS_EVALUATOR_ONLY.json`; the lane receives `C_AUDIO_ONLY.json` only.
No E/Q audio, truth activity, names or text enters window admission. Nominal
Balanced fixed cadence and original Pyannote gates remain unchanged. The lane
resets once per original clip, preserves the unanalyzed sub-dispatch tail, and
does not trim silence, concatenate turns, pad embeddings or use future samples.
Pyannote's original left-padded ten-second receptive field is preserved.

Processed E/Q window rows lack individual clean-source IDs. Preparation verifies
the original ECQ and Q-manifest hashes, exact-empty source/PCM/text leakage audit,
and each C source's role, identity and decoded PCM against that protected record.
It directly rechecks clean E/C rows. This retains the accepted audit's stated
limits on undocumented cross-corpus aliases; missing IDs alone never pass.

Outputs are private `ADMISSION.json`, `worker.json`, separate E0/E1 clip
`RESULT.json` files, exact float32 waveform-slice hashes, 192-dimensional unit
vectors, all segmentation frames, embedding rejection records and final census.
Each encoder runs in its own sequential child process, one model thread on CPU4;
the lightweight coordinator uses CPU14. CUDA is disabled. Source bindings are
verified before execution. The entire new output has a conservative 1 GiB cap
with 16 MiB reserved before each bounded clip; C:50/G:75 GiB floors and the
packaging cutoff are checked every clip. Failed attempts are retained and no
old output is adopted or deleted. There is no automatic resume into an existing
encoder directory; review any partial result before preparing a fresh attempt.

This is accelerated causal *component collection*, not a Controller, GUI,
streaming latency, naming accuracy or complete-stack memory result. It earns
zero of the 7,680 integrated N4 cells. The source-time neural lane is unchanged,
but no wall-clock policy scheduler or ASR runs. Fixed cadence is required
precisely because it does not consume tracker state. A tracker-dependent cadence
raises an error. Clean-C calibration cannot authorize processed-query names.

PowerShell preparation (no Conda activation needed):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\n4\d0_calibration_windows.py" prepare --source-receipt "$jpLocal\releases\n4-catalog-v3\SOURCE_RECEIPT.json" --manifest "$jpLocal\n2\evaluation\WINDOW_MANIFEST.json" --runtime "$jpLocal\n2\runtime\cpu\n2_runtime.json" --models 'C:\Users\amiri\JustPeachy\shared\models' --output "$jpLocal\n4\d0-calibration-v1" --state "$jpLocal\supervision"
```

After checking current supervisor ownership, use its existing interface. Do not
launch a second worker or write the shared ledger manually:

```powershell
& $jpPython -B "$jpCode\supervision\supervisor.py" phase --root "$jpLocal\supervision" --phase inference --stage N4
& $jpPython -B "$jpCode\supervision\supervisor.py" start --root "$jpLocal\supervision" --spec "$jpLocal\n4\d0-calibration-v1\worker.json"
```

Command Prompt or Anaconda Prompt equivalents:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\n4\d0_calibration_windows.py" prepare --source-receipt "%JP_LOCAL%\releases\n4-catalog-v3\SOURCE_RECEIPT.json" --manifest "%JP_LOCAL%\n2\evaluation\WINDOW_MANIFEST.json" --runtime "%JP_LOCAL%\n2\runtime\cpu\n2_runtime.json" --models "C:\Users\amiri\JustPeachy\shared\models" --output "%JP_LOCAL%\n4\d0-calibration-v1" --state "%JP_LOCAL%\supervision"
"%JP_PY%" -B "%JP_CODE%\supervision\supervisor.py" phase --root "%JP_LOCAL%\supervision" --phase inference --stage N4
"%JP_PY%" -B "%JP_CODE%\supervision\supervisor.py" start --root "%JP_LOCAL%\supervision" --spec "%JP_LOCAL%\n4\d0-calibration-v1\worker.json"
```

`test_d0_calibration.py` checks the split/firewall, unchanged native lane with
test-double models, matching actual waveform slices, short tails, retained
failures and rejection of tracker-dependent cadence. No real model or audio
is loaded by the tests. They require the frozen derivative and NumPy:

```powershell
& $jpPython -B -m unittest discover -s "$jpCode\n4" -p 'test_d0_calibration.py' -v
```

```bat
"%JP_PY%" -B -m unittest discover -s "%JP_CODE%\n4" -p "test_d0_calibration.py" -v
```

Keep private vectors/events/labels outside Git. After collection, verify equal
E0/E1 window geometry and vector validity, then freeze an explicit C-only scale
selection protocol before fitting. Retain nominal D0/E1 as a labelled sensitivity
condition. A completed collection is not calibrated-profile acceptance.
