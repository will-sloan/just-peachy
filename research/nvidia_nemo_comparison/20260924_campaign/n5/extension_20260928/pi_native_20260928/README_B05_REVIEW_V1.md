# Independent B05 native application reader

Purpose: verify collected short/full B05 anonymous saved-file application evidence independently of launcher success. Inputs are the immutable target ADMISSION/assets, RESULT, complete session event journal, summary, finalization, consumer/archival closure and exact boot/PID/start ticks; full-file comparison also uses the preserved delayed D1 reference array. Raw text/probabilities remain private. No inference/capture/playback is run.

Checks: input hashes; natural launcher zero and exact OS closure; all source/ASR/D1 input samples; finite contiguous eight-channel probabilities; no encoder loads/calls; learned punctuation without inference failures (terminal period/question heuristic counted separately); all application/consumer/archive queues drained and handles closed; actual caption output. Full44.695s additionally requires4470x8 probabilities within the unchanged1e-5 reference gate. The short12s result records actual native frame count without claiming full-source probability parity. Source input pacing and first-text/probability/EOF-drain times are observed event clocks; none is speech/identity accuracy or final GUI/release acceptance.

Outputs: private AUDIT_INPUTS.json, RESULT copy, probability array and REVIEW on host and target, with no overwrite of previous reviews. The target receipt is a permitted per-stage review, not a shared-ledger edit. Some summary snapshots occur before final closure; finalization and fully drained consumer/archive records take precedence. No raw text or vectors are copied to Git.

## PowerShell

From this directory:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py review_b05_native_v1.py --run-id b05-anonymous-v1 --samples 192000
# Only after the separate full-file job has closed:
& $py review_b05_native_v1.py --run-id b05-anonymous-full-v1 --samples 715127
```

## CMD / Anaconda Prompt

Use `cd /d` here, invoke the same quoted Python executable and arguments without `&`. Existing host NumPy/psutil and strict SSH helper are reused; no downloads. Reader pins host CPU14 and target read-only processing toCPU3. It does not start another numerical worker. An assertion failure blocks its stated scope and preserves existing evidence; inspect the actual condition rather than relaxing gates.
