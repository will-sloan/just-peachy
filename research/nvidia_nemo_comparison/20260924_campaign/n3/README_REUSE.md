# N3 recovery without repeating unchanged inference

Purpose: preserve completed A0/A1 runs and A2/A3 FP32 reference panels while
repairing the native ctypes configuration and A1 export-port metadata.
`prepare.py --reuse-from` accepts a terminal prior plan. `reuse_results.py`
verifies its plan/result hashes, dead coordinator identity, original source,
models, input/configuration bindings, complete cells and event hashes. Only the
reviewed native adapter, its README/test, and preparation/export helpers may
differ. Any other inference-source or command change refuses reuse.

Inputs: the original private plan, complete evidence and a fresh version name.
Outputs: a frozen source release, recovery plan, private reuse manifest and
exact copies of small result/configuration receipts. Cell/event paths continue
to point at the preserved original evidence. Each copied result has a separate
`REUSE_RECEIPT.json` with `new_inference=false`; no timestamp, source contract,
word, measurement or model output is rewritten. Audio and weights are not copied.
The queue still checks prerequisites. The source suite, A1 export, all native
jobs and aggregate lexical/text/route comparisons run afresh.

PowerShell, from the campaign worktree (v4 paths must not already exist):

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_recovery.py
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_queue.py
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare.py --version v4 --reuse-from G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v3.json
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v4.json
```

CMD or Anaconda Prompt (no activation required):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_recovery.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_queue.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare.py --version v4 --reuse-from G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v3.json
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v4.json
```

After verifying no numerical owner remains, dispatch this plan through the
hidden `supervise_n3.py wait` procedure in README_QUEUE.md. Never launch an
individual copied job to pretend inference occurred. `test_recovery.py` tests
export input mapping, source/evidence tampering, failed-result refusal, exact
receipt preservation and fresh-output protection without models or hardware.
Rollback is the untouched v3 evidence and prior immutable baseline. A successful
recovery queue still requires review and N3 acceptance before N4 promotion.
