# N4 actual gallery and publication-clock compatibility repair

Purpose: qualify the research facade with the actual baseline admission type
check and the actual engine publication stamps. The failed V1 code, admission,
log and result remain immutable in paced-adapters-v1. Its 160 score/route checks
passed, but Controller engine construction rejected its plain gallery wrapper.

`paced_adapters_v2.py` makes the delegating counter an actual ResearchGallery
subclass. Its initializer still delegates to the already loaded research gallery;
it does not load again, copy templates, normalize again or change score results.
N2 galleries remain unchanged. The source observer now checks the complete real
FileSource plus S6D publication payload. It preserves the original source origin,
publication time, sequence, session and consumer receipt time separately. Every
observed event must advance the actual publication sequence by one from 1 and
retain the same session. Missing/reordered events invalidate observer evidence.

Inputs, bounds and scope follow README_PACED_ADAPTERS.md. This derivative imports
the bound application before its module, so use the probe launcher below. It
accepts only the prepared routes/rosters, saved audio and adaptation/enhancement
off. No personal-store import or reference mutation is provided. The tests forbid
model acquisition. No audio, source process, GUI, microphone or playback is run.

`test_paced_adapters_v2.py` executes 160 saved gallery/mode/tap checks, invalid
metadata/ownership cases and three real Controller drains. Those engine classes
publish synthetic source-start payloads using their actual `_emit` method;
they do not execute FileSource or inference. Source delivery, journal closure,
widget timing, resource qualification and full N4 acceptance remain pending.
The observer alone always marks these claims false, even with a valid origin.

Outputs under a fresh private local/n4 folder: ADMISSION.json, unittest.txt,
CHECKS.json, RESULT.json and isolated Controller artifacts. Keep all private
artifacts outside Git; only the small redacted qualification receipt is public.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'research\nvidia_nemo_comparison\20260924_campaign\n4\probe_paced_adapters_v2.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-adapters-v2'
```

## CMD / Anaconda Prompt

Use the exact existing interpreter; no environment installation or activation.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_paced_adapters_v2.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-adapters-v2
```

The launcher pins CPU14, GPU off and single math threads. Shared payload reserve,
drive floors and packaging cutoff are checked. This is a model-free development
check, not a controlled timing/resource run. Use a new code derivative and output
after a failure; never edit admitted code or delete a failed attempt.
