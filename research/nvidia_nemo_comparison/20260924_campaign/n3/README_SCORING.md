# N3 evaluator firewall

`test_scoring.py` uses four text-only fixtures to verify that missed words keep
their denominator, complete overlap gets separate cpWER, empty controls count
false words and incomplete ambient references never receive primary WER.
Run in PowerShell with `& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_scoring.py`.
In CMD/Anaconda Prompt omit `&` and use double quotes around the interpreter.
The tests print unittest results; no neural model or audio is loaded.

`score_asr.py` reads completed private inference receipts and the evaluator-only
truth after inference. Inputs are explicit `--run` directories and `--truth`;
output is redacted numeric JSON/Markdown. Every referenced result/event hash is
rechecked. No transcript, identity or turn boundary is provided to the ASR worker.

PowerShell (`CMD/Anaconda` omit the initial `&`):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' research/nvidia_nemo_comparison/20260924_campaign/n3/score_asr.py --truth G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/EVALUATOR_TRUTH.json --run <A0_RUN_DIRECTORY> --run <A1_RUN_DIRECTORY> --run <A2_RUN_DIRECTORY> --run <A3_RUN_DIRECTORY> --output <ANALYSIS_DIRECTORY>
```

Complete nonoverlap WER/CER are primary. Overlap has separate fixed chronological
diagnostics and single-output cpWER against complete per-speaker references; a
mono ASR output has no predicted per-speaker transcript, so this is not full
diarized-system cpWER. Ambient metrics are explicitly target-only. Empty controls
use all produced words per minute. Missing audio never removes reference words.
The scoring normalization matches N2's retained evaluator. Model-native numbers,
punctuation and casing remain separately available in private raw events.
