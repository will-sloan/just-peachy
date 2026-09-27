# Concurrent Windows lease-open diagnostic

Purpose: investigate the preserved V9 child setup failure (WinError 2, no
application RESULT). Its exact call site was not captured. Reproduce a possible
race by opening a fixture lease while V6's unchanged Windows rename function
replaces it. This does not establish a production root cause by itself.

Inputs: installed qualified interpreter, immutable V9 code lineage and existing
resource/supervisor receipts. No audio, model, GUI, Pi or device is opened.
The helper requires closed workers, complete resource census and no competing
runtime, reserves a checked 16 MiB projection without editing shared ledgers,
uses CPU14/BelowNormal and performs at most three 30-second rounds of 10,000
renames each. Each round owns one bounded thread, joins it, and retains two
small fixture files and at most 32 missing-open error samples.

Outputs: private local/n4/lease-open-race-v1/PRECHECK.json and RESULT.json plus
fixture files. Existing output is never overwritten. Application acceptance
remains false; a diagnostic reproduction is not a completed panel.

PowerShell (only when the numerical worker is closed):

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B probe_lease_open_race_v1.py
```

CMD / Anaconda Prompt (no environment replacement or conda install):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_lease_open_race_v1.py
```

An existing diagnostic must be inspected, not rerun in place. Keep all private
receipts outside Git; retain a small redacted summary and source hashes only.
