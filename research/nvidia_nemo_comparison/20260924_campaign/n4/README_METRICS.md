# Isolated evaluation tools

Purpose: use the established MeetEval 0.4.3 lexical/cpWER/MIMO algorithms and
pyannote.metrics 4.1 DER/JER without modifying the app or the active N2/N3 env.
These tools score saved predictions against evaluator-only references. They
perform no neural inference. tcpWER stays unavailable without timed gold words.

Private environment:
`G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env` (Python 3.12).
The original app and NeMo environments are untouched. First-party sources:
[MeetEval](https://github.com/fgnt/meeteval) (MIT) and
[pyannote.metrics](https://github.com/pyannote/pyannote-metrics) (MIT).
Dependency/install receipts retain versions, URLs and distribution hashes.

MeetEval's exact official 0.4.3 source archive SHA-256 is
`02d3a359f375d39c67dfb8fe1c061e7dac19d6fc1fb89ee72d793a5813dafeb2`.
The source build script and license were reviewed. Default Windows MSVC failed
with C7555 because designated initializers need C++20. `build_meeteval.py` passes
`CL=/std:c++20` to the existing compiler, no source/algorithm edits. The program
uses one CPU4 worker with BelowNormal priority, a 15-minute timeout and a fresh
output directory. Inputs are the archive and isolated Python interpreter; outputs
are `build.log`, pip's installation report and a hash-bound BUILD_RECEIPT.

PowerShell (from the worktree):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\build_meeteval.py --python 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe' --archive 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\downloads\meeteval-0.4.3.tar.gz' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\msvc20-v1'
```

CMD/Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\build_meeteval.py --python G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe --archive G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\downloads\meeteval-0.4.3.tar.gz --output G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\msvc20-v1
```

Do not repeat an installation into an environment currently scoring results.
Choose a new output path for another build. An install receipt is not metric
validation; the adversarial scoring fixtures must pass before campaign scoring.

`record_metrics_environment.py` records exact installed versions, code/native-file
hashes and dependency license files from this evaluator environment. Outputs are
ENVIRONMENT.json, requirements.txt, THIRD_PARTY_NOTICES.md and SUMMARY.json.
The actual `local\n4\metrics\environment-v1` receipt includes 31 distributions
with license files. Pip's dependency-install.json and msvc20-v1\install.json
additionally bind distribution downloads. To reproduce in a fresh directory:

```powershell
& 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\record_metrics_environment.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\environment-v2'
```

```bat
"G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\record_metrics_environment.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\environment-v2
```

`metrics.py` and `paired.py` are evaluator libraries. Inputs are complete
reference/prediction records and paired integer edit/word counts. Outputs retain
failed/missing denominators, separate overlap metrics, estimated-activity limits,
dependency clusters and leave-group-out sensitivity. `test_n4.py` exercises lost
words, empty/overlap cases, permutation, all-one-track controls, invalid timing,
cache invalidation and paired denominator faults. It opens no audio or model.

Run tests with the isolated evaluator interpreter in either shell:

```powershell
& 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\test_n4.py
```

```bat
"G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\test_n4.py
```
