# N4 preparation checkpoint packaging

`package_checkpoint.py` publishes small redacted preparation receipts and creates
an analysis ZIP explicitly marked PARTIAL, not a finished N4 handoff. It accepts
the private campaign root (`--local`), the reviewed flat N4 source/report directory
(`--public`) and a fresh ZIP path (`--zip`). It refuses existing checkpoint reports
or ZIPs. It copies only selected redacted receipts/figures/notices and the reviewed
flat source/docs; private audio, models, transcripts, research galleries/vectors
and raw logs are excluded. Every ZIP member is rehashed after writing. Target is
10 MiB, hard limit 20 MiB. The command performs no Git actions or shared-ledger writes.

PowerShell, from the worktree:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\package_checkpoint.py --zip 'G:\Just_Peachy_N1\20260924_campaign\local\n4\handoffs\N4_PREPARATION_CHECKPOINT_20260924_rc1.zip'
```

CMD/Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\package_checkpoint.py --zip G:\Just_Peachy_N1\20260924_campaign\local\n4\handoffs\N4_PREPARATION_CHECKPOINT_20260924_rc1.zip
```

For subsequent checkpoints, use fresh reviewed public and ZIP destinations; do
not overwrite historical evidence. A Git mapping receipt can be added after
the reviewed source commit/push is verified. It is external to this first ZIP
to avoid claiming a future Git hash in an immutable archive.

Recreate the isolated metric environment with Python 3.12 and the copied
`metric-dependency-requirements.txt` (wheels only), then build the exact reviewed
MeetEval archive using README_METRICS.md. `metric-requirements.txt` records the
entire resolved set; MeetEval requires a source build with the documented flags.

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -m venv 'G:\path\to\fresh-metrics-env'
& 'G:\path\to\fresh-metrics-env\Scripts\python.exe' -m pip install --only-binary=:all: -r research\nvidia_nemo_comparison\20260924_campaign\n4\metric-dependency-requirements.txt
```

```bat
"C:\Users\amiri\anaconda3\python.exe" -m venv G:\path\to\fresh-metrics-env
"G:\path\to\fresh-metrics-env\Scripts\python.exe" -m pip install --only-binary=:all: -r research\nvidia_nemo_comparison\20260924_campaign\n4\metric-dependency-requirements.txt
```

Replace illustrative environment paths. METRIC_DISTRIBUTIONS.json records exact
download hashes/URLs; inspect those when reproducing. Install into a new isolated
environment, not the running app or active N2/N3 interpreters.
