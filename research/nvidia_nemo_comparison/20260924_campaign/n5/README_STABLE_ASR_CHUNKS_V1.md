# Deterministic ASR journal input

Purpose: repair a schedule-dependent coarse ASR timestamp discrepancy found in
the paired anonymous-mode test. MemoryJournal.read returns up to the requested
size. NativeStream records input_end_sec from delivered samples; partial reads
therefore gave different coarse boundaries on one versus two CPUs. The fresh
derivative gathers the configured read quantum before each native feed, except
the exact final tail. It does not relabel native word offsets as gold timing.

Inputs: a hash-bound immutable parent SOURCE_RECEIPT.json or DERIVATIVE.json,
existing code, and a fresh private output directory. Outputs: a new prototype,
patch and DERIVATIVE.json. Only app/n3_pipeline.py application code changes;
this README and three meaningful fragmentation/failure tests are included.
No models, audio, personal data, active sources or old evidence are changed.
No microphone, playback, training, GUI or Pi access occurs during preparation.

The configured 100 ms quantum may wait up to 100 ms for source audio. This is
a documented delivery change; it does not prove word timing, preserve old
coarse timestamps, or establish real-time throughput. Compare both fresh arms
under the same delivery contract. Model settings, all-sample accounting,
60-second drain and exact paired-parity gates remain unchanged. Stage acceptance
still requires the original coverage, beyond this one-file qualification.

PowerShell (from this n5 directory):

```powershell
$d1Py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $d1Py -B prepare_stable_asr_chunks_v1.py --parent-receipt 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n3-common-a1controllerv2\SOURCE_RECEIPT.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n3-stable-asr-chunks-v1'
& $d1Py -B prepare_stable_asr_chunks_v1.py --parent-receipt 'G:\Just_Peachy_N1\20260924_campaign\local\releases\d1-anonymous-v1\DERIVATIVE.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\releases\d1-stable-asr-chunks-v1'
```

CMD / Anaconda Prompt (no activation or install needed):

```bat
set "D1_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%D1_PY%" -B prepare_stable_asr_chunks_v1.py --parent-receipt "G:\Just_Peachy_N1\20260924_campaign\local\releases\n3-common-a1controllerv2\SOURCE_RECEIPT.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\releases\n3-stable-asr-chunks-v1"
"%D1_PY%" -B prepare_stable_asr_chunks_v1.py --parent-receipt "G:\Just_Peachy_N1\20260924_campaign\local\releases\d1-anonymous-v1\DERIVATIVE.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\releases\d1-stable-asr-chunks-v1"
```

Run the included test from each resulting prototype using that interpreter,
with vendor and prototype on PYTHONPATH:
`python -B -m unittest discover -s tests -p test_stable_asr_chunks_v1.py -v`.
README_D1_ANONYMOUS_LIFECYCLE_V4.md describes supervised actual GUI qualification.
