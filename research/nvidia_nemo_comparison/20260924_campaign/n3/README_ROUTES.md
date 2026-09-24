# Native and reference route comparisons

`compare_routes.py` reads completed hash-bound N3 ASR receipts. For A2/A3 it
compares the same four preselected audio hashes across native CPU Q8, native
CUDA Q8, NeMo CPU FP32 and the single lower-buffer CUDA contrast. Inputs are
the numerical root and output directory. Outputs are redacted JSON/Markdown
with exact lexical agreement, edit distances, input counts and measured compute.
Missing or failed route evidence produces an explicit partial result.

This compares lexical outputs, not hidden tensors. Precision, model runtime and
endpoint behavior can differ. No equality is fabricated by normalizing spoken
numbers to expected words, aligning favorable subsequences or dropping silence.
No reference transcript is used. Raw text remains in the private inference files.

PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n3/compare_routes.py --root G:/Just_Peachy_N1/20260924_campaign/local/n3/numerical-v2 --output G:/Just_Peachy_N1/20260924_campaign/local/n3/numerical-v2/routes
```

CMD / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/compare_routes.py --root G:/Just_Peachy_N1/20260924_campaign/local/n3/numerical-v2 --output G:/Just_Peachy_N1/20260924_campaign/local/n3/numerical-v2/routes
```
