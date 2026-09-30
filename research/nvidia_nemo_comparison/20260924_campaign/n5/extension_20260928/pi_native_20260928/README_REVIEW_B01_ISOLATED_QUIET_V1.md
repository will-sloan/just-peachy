# Independent combined quiet B01 review

Purpose: independently inspect the closed b01-isolated-quiet-v1 admission, actual native envelope, baseline/leases/owners, terminal ACK, readable route restoration, every accepted source-block hash and timestamp, full ASR/D1/EOF sample coverage, bounded float/PCM archives, compact event decoding, Save/Open and withdrawn Tk. It does not load models, open a microphone, play audio or score acoustic quality. New captured-audio numerical references remain pending. Natural collection exit alone is not acceptance.

Inputs: immutable Pi run files and host launch receipt. Outputs: private REVIEW.json on host and target with exact bindings, counts, component costs, current per-owner sampled memory (separate from inherited child ru_maxrss), latencies, restoration/closure and explicit scope. Failed evidence is preserved. The reader requires current baseline/closed capture/free leases and uses CPU3/256MiB on Pi; host coordinator14. It is not a hardware retry or model rerun.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_b01_isolated_quiet_v1.py
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_b01_isolated_quiet_v1.py
```

Run once on closed evidence; outputs refuse overwrite. Then run `backup_b01_isolated_quiet_v1.py` using the same Python command in PowerShell or CMD/Anaconda (replace the reader filename). It accepts only the independently passed closed run, lists and hashes target files read-only, rejects tar links/traversal/duplicates, writes an exclusive private target directory, verifies every byte count/hash and records BACKUP.json. Original target files and all failures remain intact; combined host/target output must fit64MiB. No general field, endurance, visible GUI, physical touch or new model-parity acceptance follows.
