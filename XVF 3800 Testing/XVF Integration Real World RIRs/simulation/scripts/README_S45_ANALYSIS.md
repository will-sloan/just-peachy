# S4.5 capture analysis and reserve protection

`s45_capture_analysis.py` consumes the frozen scene manifest and `reports/S4_5/20260909T031300Z/ACCEPTED_CAPTURES.json`. Accepted development captures reuse the S4 audio/converter and corrected causal spatial scorers. Reserve captures receive only output-level, native-conversion, transport and telemetry-integrity checks; reference-matched delay/direction/transcription/identity scoring is prohibited. No models or hardware are opened.

Outputs are per-capture `audio_metrics.json`, development-only `spatial_metrics.json`, `s45_analysis_receipt.json` and compact report `CAPTURE_ANALYSIS.json`. Existing compatible results are retained. The original PCM24 output remains unchanged. Rail samples retain their measured limitation; no clipped waveform is repaired by attenuation.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s45_capture_analysis -v
& 'C:\Users\amiri\anaconda3\python.exe' s45_capture_analysis.py
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s45_capture_analysis -v
"C:\Users\amiri\anaconda3\python.exe" s45_capture_analysis.py
```

Run after a restored hardware batch, or after the campaign completes. It is not a command to capture new data. Later sentinel H2 commands use only the predeclared development IDs and frozen output gains.
# Optional reference and cache policy

The same command also reads `REFERENCE_CAPTURES.json` when present and writes `REFERENCE_CAPTURE_ANALYSIS.json`. Optional reference outputs receive raw level/conversion/integrity checks only; no transcription, identity or direction score. They remain separate from the 240 canonical scenes. Existing analysis receipts are reused only when their exact accepted case-result and analysis-code SHA-256 still match. An incompatible cached receipt is preserved and raises an error instead of being silently overwritten.

`test_s45_capture_analysis.py` contains model-free integration fixtures for both protected branches. It runs the actual `run()` coordinator with temporary BANK/REPORT/capture JSON, a quiet mocked progress context, synthetic integer counts supplied by a mocked WAV reader, and a mocked native converter. Neither development scorer may be called. No real audio, model, device or campaign report is accessed or written. The fixtures verify output-only rail counts and quarantine labels, absence of reference-matched fields/spatial files, exact compatible-cache reuse without reopening audio, rejection/preservation of stale code/case hashes, and rejection of modified unbound case receipts before raw data access. Run the unittest command alone for this safe offline check; it does not start the subsequent real analysis command.
