# Review native performance and numerical output

`review_benchmark.py` reads a complete, independently verified private mirror
from the native job monitor. It streams timing records across 16 MiB part
boundaries and summarizes numeric values without loading hour-long logs in RAM.
An optional exact SHA-pinned historical NumPy array compares all probability
rows at 1e-5 absolute tolerance. This tests same-geometry numerical agreement,
not diarization accuracy. Before comparison, separately check the input SHA,
geometry, native-library and source-clock provenance match.

Inputs: `--mirror` is the directory containing `benchmark/`; `--output` must
be fresh. Optional `--reference` requires `--reference-sha256`. Outputs are an
early CPU14 host owner and private `REVIEW.json` with the native plan/result,
call statistics, and optional numerical comparison. The tool does not establish
SSH closure, output completeness or 4/8 GB performance; use the monitor receipt.

PowerShell, from this source directory:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./review_benchmark.py --mirror 'G:/PRIVATE/CLOSED_MIRROR' --output 'G:/PRIVATE/FRESH_REVIEW'
```

Command Prompt / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_benchmark.py --mirror "G:\PRIVATE\CLOSED_MIRROR" --output "G:\PRIVATE\FRESH_REVIEW"
```

With a known matching reference, append `--reference PATH --reference-sha256
SHA256`. Keep all inputs and detailed results private; publish aggregate
performance and evidence identifiers, not recordings or probability artifacts.
