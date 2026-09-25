# Read-only A3 GUI finalization diagnosis

`diagnose_gui_drain.py` compares the preserved passing and failing A3 boundary
cells for A3/D1/E0 on CPU4. Other A3 compositions/resource profiles are not
qualified or rejected by this pair. It loads no model or GUI and changes no application, timeout, admission,
audio or evidence. Inputs are the two exact private cell directories and a
fresh public JSON output path. It verifies equal application, runtime, audio,
common UI/layout and CPU contracts, one source origin, contiguous ASR sample
coverage, the successful final tail, and the exact failed lane-timeout reason.

Output: a redacted, hash-bound timing/census report. It includes actual source
duration, ASR progress, missing/unprocessed duration, decode wall time, tail
completion, archive status and sampled process CPU/RSS. It does not copy private
words, identities, vectors, audio or screenshots. Different callbacks and host
activity mean it cannot causally attribute the slowdown to one change. A queue
verification overlapped the failed panel; no isolated estimate of its cost is
available. Do not use the passing slow completion as real-time qualification
or erase the later failure. The finalization limit is not increased.

PowerShell, from the worktree:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/diagnose_gui_drain.py --passed-cell G:/Just_Peachy_N1/20260924_campaign/local/n3/numerical-guilabelsv1/gui-A3/private_cells/A3_boundary/cells/A3_boundary --failed-cell G:/Just_Peachy_N1/20260924_campaign/local/n3/numerical-guifinalv1/gui-A3/private_cells/A3_boundary/cells/A3_boundary --output research/nvidia_nemo_comparison/20260924_campaign/n3/GUI_DRAIN_REVIEW_20260925.json
```

CMD or Anaconda Prompt (explicit interpreter; no activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/diagnose_gui_drain.py --passed-cell G:/Just_Peachy_N1/20260924_campaign/local/n3/numerical-guilabelsv1/gui-A3/private_cells/A3_boundary/cells/A3_boundary --failed-cell G:/Just_Peachy_N1/20260924_campaign/local/n3/numerical-guifinalv1/gui-A3/private_cells/A3_boundary/cells/A3_boundary --output research/nvidia_nemo_comparison/20260924_campaign/n3/GUI_DRAIN_REVIEW_20260925.json
```

Use a new output filename for another review. Old evidence and reports are
immutable. The real-data invariants above are checked on every invocation;
there are no synthetic accuracy results or new neural runs. A hardware/CM5
claim, repaired runtime or N3/N4 stage acceptance is outside this diagnostic.
