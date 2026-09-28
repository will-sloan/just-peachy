# Review the D1 anonymous Windows pair

Purpose: independently rehash and review both closed runs of the paired
qualification described in README_D1_ANONYMOUS_LIFECYCLE_V4.md. This uses no
model inference or GUI. It verifies source/model/audio and runner bindings,
sample completeness, semantic parity, zero candidate encoder loads/calls,
save/reopen/delete receipts, normal unforced job closure and absent exact owners.

Inputs: the completed parent and candidate private run directories. Outputs:
one new small public JSON receipt containing counts, hashes and local evidence
bindings, without transcripts/audio/profiles/weights. It cannot establish N4
full-bank acceptance, calibrated naming, real-time operation, ARM64 or CM5.
An existing different output is refused. The read-only process uses CPU14 below
normal. A failed gate raises an error and must not be bypassed.

PowerShell:

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$d1Py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $d1Py -B review_d1_anonymous_lifecycle_v1.py --parent 'G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-anonymous-lifecycle-parent-v4' --candidate 'G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-anonymous-lifecycle-candidate-v4' --output D1_ANONYMOUS_WINDOWS_CHECK_V1.json
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "D1_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%D1_PY%" -B review_d1_anonymous_lifecycle_v1.py --parent "G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-anonymous-lifecycle-parent-v4" --candidate "G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-anonymous-lifecycle-candidate-v4" --output D1_ANONYMOUS_WINDOWS_CHECK_V1.json
```

The explicit interpreter needs no environment activation or installation.
