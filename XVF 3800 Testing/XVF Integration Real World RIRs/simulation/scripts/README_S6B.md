# S6B joint comparison

This stage compares causal anonymous speaker tracking and bounded component recipes on the existing 240-scene, two-output XVF bank. It preserves S6A and the original H2 baseline. It does not record audio, regenerate RIRs, train models, or start S6C.

## Admission and snapshot

Inputs: the S6B pack and Downloads prompt, Revision 15 workbook, immutable S6A handoff, scene manifest, and current application source. Outputs: an uncached SHA256 admission receipt, an exact S6A V2 application snapshot, and extracted workbook text under `simulation/reports/S6B/20260909T230840Z` and `simulation/staging/s6b/20260909T230840Z`. Large outputs use `G:\Just_Peachy_S6B\20260909T230840Z`.

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' .\s6b_common.py
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s6b_common.py
```

The admission command is idempotent after a completed receipt. It refuses an incomplete snapshot or a changed hash instead of replacing evidence.

## Current execution and analysis

Epoch2 is the frozen native/replay implementation. The64-output balanced pilot and exact native/replay/cache checks passed. All480 historical B00 outputs have been scored with accepted counts reproduced. The broad44-scene/18-recipe challenge is running through the atomic_io_v1 JSON-persistence repair; its40 core plus four disclosed limited diagnostics are all enumerated. Use `README_S6B_EXECUTION.md` and `README_S6B_LAUNCH.md` for current run/resume commands, reserves and STOP_REQUEST. They call the repository `.edge-speech-env` interpreter, including from Anaconda Prompt.

`README_S6B_PROFILES.md` documents actual profiles and dependencies; `README_S6B_REPLAY.md` documents common-scheduler prediction outputs. `README_S6B_ANALYSIS.md` and `README_S6B_REVISION_ANALYSIS.md` describe the pinned MeetEval scorer and event supplement. `README_S6B_CAMPAIGN_AUDIT.md` gives measured admission/ETA and exact saved-baseline parity checks. The current Word master remains unchanged.

## Bind consumed inputs

Run `s6b_inputs.py` with the same Python and working directory shown above. In PowerShell use `& 'C:\Users\amiri\anaconda3\python.exe' .\s6b_inputs.py`; in Anaconda Prompt/CMD use `"C:\Users\amiri\anaconda3\python.exe" s6b_inputs.py`.

It verifies the 480 accepted baseline journals, events and feature vectors, plus 240 shared sanitized cue traces and frozen reference-support records. It writes one PCM16 WAV per output on G: with audio payload bytes identical to the completed baseline journal, then writes `INPUT_INDEX.json`. Main inputs already contain the historical gain and are consumed at unity. This is input preparation, not new XVF capture or RIR rendering. A completed rerun verifies exact consumed-file hashes; unreceipted partial outputs require inspection and are not overwritten.

For the predeclared gain interaction, append `--gain-alternatives` to the same `s6b_inputs.py` command. This reads raw accepted captures and applies the selected gain once: O0 unity and O1 -3 dB, each 3 dB below its historical preparation. It writes separate FLOAT WAVs and `GAIN_INPUT_INDEX.json`; runtime consumes these at unity. It refuses numerical overflow and preserves historical captures and gain inputs.
