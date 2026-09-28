# Early Stop and full-file restart

Purpose: exercise actual A0/D1/E0 or A2/D1/E0 on the existing 44.695-second saved source, request Stop after at least eight seconds have entered the journal, verify every accepted prefix sample drains through ASR and D1, then start the complete source from sample zero using the same resident models. Compare the full restarted output with the independently reviewed one-file reference. This is a new lifecycle case, not a repeat of the passed EOF-reuse test.

Inputs: hash-bound prior E0 lifecycle/launcher/reviewer scripts, current E0-only derivative, accepted N3 ancestry and assets, saved WAV and paired reference, fresh extended-window census/admission. Outputs: three reviewable generated scripts and a derivation receipt; private phase/result/ownership evidence, prefix hash/drain metrics and full-file parity; a separate independent review. No application source is edited. Shadow observers retain every delivered sample. Both isolated test sessions are deleted through the application after reopen; the sentinel profile fixture remains.

The original 60-second inference drain and five-second late-worker cleanup remain unchanged. The test retains a 240-second phase limit, 600-second admission, 128-MiB output cap, two host CPUs, single native threads, GPU off and private desktop. It verifies start_file resets to sample zero, two streams use one loaded ASR and E0 bundle, source-time/caption/activity parity and normal process closure. Failed prefix drain must remain a failure; successful cleanup cannot conceal it.

PowerShell / Anaconda PowerShell, from this directory:

```powershell
$researchPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $researchPython -B build_early_stop_v1.py
& $researchPython -B prepare_early_stop_v1.py --name a0-early-stop-v1 --backend nemotron_hybrid
# After the worker is terminal and all exact owners are confirmed closed:
& $researchPython -B review_early_stop_v1.py --run 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-early-stop-v1' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-early-stop-v1-REVIEW.json'
# Only after closed review, admit A2 separately with name a2-early-stop-v1.
```

Command Prompt / Anaconda Prompt:

```bat
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B build_early_stop_v1.py
"%RESEARCH_PY%" -B prepare_early_stop_v1.py --name a0-early-stop-v1 --backend nemotron_hybrid
"%RESEARCH_PY%" -B review_early_stop_v1.py --run "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-early-stop-v1" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-early-stop-v1-REVIEW.json"
```

Builder refuses existing generated scripts; launcher/reviewer require fresh names. Preserve all attempts. Review generated source before dispatch. Saved audio only: no microphone enumeration, capture, playback, enrollment, training or Pi access. Passing this case does not complete the N4 controls panel, N5 release, or real-time/native Pi qualification.
