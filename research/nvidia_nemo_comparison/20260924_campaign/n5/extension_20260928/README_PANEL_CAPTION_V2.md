# Exact serialized bound for caption reviews

Purpose: retain V1's caption interpretation and all source/owner checks while enforcing its output limit against the bytes actually written. V1 tested a compact serialization but wrote indented JSON through `freeze`: the resulting 1,254,602-byte A0 and 1,356,025-byte A2 files exceeded its stated 1-MiB per-review bound. Those files and code remain preserved. Their semantic assertions passed, but their output-size guarantee did not. The combined campaign allowance was not exhausted.

`review_panel_caption_v2.py` is a fresh derivative of V1 (parent SHA-256 recorded in PANEL_RETRY_CHECK_SUMMARY_V3.json). It serializes once as compact UTF-8 JSON, rejects non-finite numbers, checks that exact byte array below 1 MiB, writes exclusively to a fresh file, and verifies actual size and parsed equality afterward. Caption assertions and numerical inputs are unchanged. The only other changes are the versioned script, README and output names. V2 review is required for a valid size-bounded receipt; no model rerun is needed.

Inputs: the same passing V3 structural review, immutable source/input bindings, closed exact owners and complete private journal as V1. Outputs: fresh private `RUN-CAPTION_REVIEW_V2.json` under `local/n5/research-extension-20260928`, never in Git. Both semantic and exact serialization checks must pass. CPU14 only; no inference, target contact, capture, playback, downloads, enrollment or training. Purpose and interpretation limits in README_PANEL_CAPTION_V1.md still apply: no accuracy, actual widget timing, N4 population or N5 acceptance is established.

PowerShell / Anaconda PowerShell:

```powershell
$p='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $p -B review_panel_caption_v2.py --name a0-panel-retry-v3
& $p -B review_panel_caption_v2.py --name a2-panel-retry-v3
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B review_panel_caption_v2.py --name a0-panel-retry-v3
"%RESEARCH_PY%" -B review_panel_caption_v2.py --name a2-panel-retry-v3
```

Only use a closed, independently reviewed run; never overwrite or delete an earlier result. The two existing complete evidence sets exercise the serialization repair and inherited caption checks directly. This is evidence re-interpretation, not another numerical experiment.
