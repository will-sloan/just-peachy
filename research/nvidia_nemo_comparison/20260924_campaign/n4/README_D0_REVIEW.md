# Review matching D0 calibration windows

`review_d0_collection.py` verifies completed C-only extraction without fitting
or selecting a profile. It refuses an unfinished or still-owned run. It checks
all source/model/code/result/event bindings, exact clip census and the frozen
scale protocol's collection binding. Every actual waveform slice is rehashed.
E0/E1 must have identical source, window, role, clean-support and waveform
geometry, with finite unit 192-dimensional vectors. An actual clip with no
admitted speech remains a counted empty observation; a missing clip fails.

Inputs: private `d0-calibration-v1`, `D0_C_SCALE_PROTOCOL_V1.json`, original
C audio and a fresh review directory. Outputs: private detailed `REVIEW.json`
and aggregate `REDACTED_REVIEW.json`. Only the redacted summary can be copied
to the campaign reports. No vectors, identities or transcript content belongs
in Git. The tool runs read-only verification on CPU14, below normal priority,
without model loading, GUI or hardware access. It creates only the new review
directory. A passing collection review is not calibration or N4 acceptance.

PowerShell, after the collection and its owner processes finish:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B "$jpCode\review_d0_collection.py" --run "$jpLocal\d0-calibration-v1" --protocol "$jpCode\D0_C_SCALE_PROTOCOL_V1.json" --output "$jpLocal\d0-calibration-review-v1"
& $jpPython -B -m unittest discover -s $jpCode -p 'test_d0_review.py' -v
```

Command Prompt / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B "%JP_CODE%\review_d0_collection.py" --run "%JP_LOCAL%\d0-calibration-v1" --protocol "%JP_CODE%\D0_C_SCALE_PROTOCOL_V1.json" --output "%JP_LOCAL%\d0-calibration-review-v1"
"%JP_PY%" -B -m unittest discover -s "%JP_CODE%" -p "test_d0_review.py" -v
```

Tests check waveform/support mismatch, missing/duplicate windows, invalid
vectors, source census, failure propagation and legitimate zero-admission clips.
The tests use in-memory fixtures, with no model or audio files.
