# A1 export parity diagnostic

Purpose: distinguish a test-input/state defect from a graph defect without
changing the running v4 source or relaxing numerical tolerance. The v4 exporter
now emits both ONNX graphs and passes NeMo's built-in trace checks, but its
independent first dynamic-state case differs by about 10.18. A1 remains
unqualified for portable streaming.

The actual a1diagv1 diagnostic completed: all eight cases and every encoder/
cache output passed the original tolerance, with exactly equal integer state
lengths and identical eager no-grad/inference-mode results. Maximum absolute
error was 3.0517578125e-5. This establishes parity against a fresh reference
instance for those cases. It does not yet explain the post-export instance's
earlier mismatch or qualify the decoder, EOU, frontend or saved-audio rollout.

`diagnose_a1_parity.py` restores a fresh exact A1 reference model and reads the
preserved v4 encoder graph. It checks random examples and zero-initialized,
carried common reference caches at batches one/two and nominal/longer windows.
Both implementations receive independent copies of identical inputs. Eager
no-grad and inference-mode outputs are compared separately. All encoder/cache
outputs use the existing 2e-4 tolerance; integer state lengths must match exactly.
Synthetic feature tensors are protocol fixtures, not a new acoustic scene bank.

Inputs: the parent plan, exact pinned model/source and a fresh output directory.
Outputs: private RESULT.json with shapes, hashes, errors and mismatch counts;
an exception file if execution fails. Original graphs, model and parent evidence
are unchanged. DIAGNOSTIC_COMPLETE means the diagnostic ran, even if parity
failed. It never qualifies decoder/EOU/real-audio or ARM64 operation.

`prepare_a1_diagnostic.py` creates a single-job plan and worker specification,
retaining the parent source/model bindings and adding the exact diagnostic and
graph hashes. The existing `supervise_n3.py wait` waits for ownership to become
available. The diagnostic then requires the exact v4 parent to be terminal and
its coordinator gone. It refuses an unexpected parent failure before model use.
One CPU4 thread, no CUDA, no devices, no GUI or audio playback. No parallel
candidate execution is added to the current native resource measurements.

PowerShell, from the worktree:

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_a1_diagnostic.py
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_a1_diagnostic.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v4.json --version a1diagv1
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1diagv1.json
```

CMD or Anaconda Prompt (explicit Python, no activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_a1_diagnostic.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_a1_diagnostic.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v4.json --version a1diagv1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1diagv1.json
```

Use the hidden-background `wait --plan` launch procedure in README_QUEUE.md
only once after checking existing queue identities. Do not run the diagnostic
directly during another candidate's evaluation. The version/output must be
fresh; failed diagnostic evidence remains available for review. The no-model
tests cover independent input storage, incomplete mappings, exact integer
checks and serialization of nonfinite/shape failures.
