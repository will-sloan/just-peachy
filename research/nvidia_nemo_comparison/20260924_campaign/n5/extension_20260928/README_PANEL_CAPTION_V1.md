# Targeted application caption lineage

Purpose: independently interpret the complete retained raw ASR and caption events from a closed V3 targeted application retry. This read-only adapter reuses the existing N4 `review_native_text.py` and `review_native_captions.py` assertions; their files are already bound by the numerical admission. It additionally requires every raw revision to have a caption and no partial-only utterance at closure. No inference, training, audio playback, device access, or GUI is started.

Inputs: the run's passing independent structural review, immutable admission and full source/code/input bindings, complete event journal and terminal receipts. The adapter verifies exact run-owner closure and source hashes. A different healthy supervised run may continue; the lightweight reader pins itself to CPU14 within the existing two-CPU total. Output: one fresh private `RUN-CAPTION_REVIEW_V1.json` under `local/n5/research-extension-20260928`, bounded below 1 MiB before writing. It retains transcript-derived content privately. Existing results are never overwritten. Do not put this raw output in Git.

A pass proves recorded raw-text/caption revision, ordering, source-support and token/fragment lineage only. It does not prove WER, speaker accuracy, actual Tk pane interpretation, source-to-widget latency, complete N4 panel coverage or N5 release acceptance. Recorded model predictions remain predictions. Source/owner/delivery checks remain in the separately required structural review. Numerical reruns are unnecessary for this reader.

PowerShell / Anaconda PowerShell, from this directory:

```powershell
$p='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $p -B review_panel_caption_v1.py --name a0-panel-retry-v3
& $p -B review_panel_caption_v1.py --name a2-panel-retry-v3
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B review_panel_caption_v1.py --name a0-panel-retry-v3
"%RESEARCH_PY%" -B review_panel_caption_v1.py --name a2-panel-retry-v3
```

Run each command only after that run's terminal supervisor result, exact-owner closure and passing V3 structural review. A failure is preserved for investigation; use a fresh reader version for any later correction. The README's command examples do not assert that either review has executed.
