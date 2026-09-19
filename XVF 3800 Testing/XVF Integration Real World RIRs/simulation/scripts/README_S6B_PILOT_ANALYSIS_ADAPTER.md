# Independent S6B pilot analysis adapter

`s6b_pilot_analysis_adapter.py` replays four predeclared pilot scenes through the actual frozen epoch2 application scheduler using existing admitted native vectors, segmentation and ASR observations. It runs no neural inference and modifies no native evidence or application code.

It validates14 profiles (B00, B01, B05, B16, B17, B18, B20, B22, B24, B26, B28, B36, B37, B38), four cases and both taps:112 predictions. The four cases follow the root pilot rule: first challenge case in each of F01/F03/F04/F06. Every required neural receipt must be complete before replay; otherwise it reports WAITING_FOR_COMPLETE_NATIVE_PILOT without generating predictions.

Inputs are the frozen epoch execution manifest, compiled effective profiles, input/telemetry bindings, exact epoch2 native receipts and vector/evidence files. All declared execution/input bytes are checked. No reference labels or geometry are passed to `run_scheduler`. Outputs are separate `pilot_validation_predictions/` files and `PILOT_VALIDATION_PREDICTION_INDEX.json`; they never replace or populate the main challenge/full-bank caches.

## PowerShell

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\s6b_pilot_analysis_adapter.py" --epoch epoch2
& "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "$sim\scripts\s6b_analysis.py" --index PILOT_VALIDATION_PREDICTION_INDEX.json --output-subdir pilot_analysis_v1 --require-complete
```

## Anaconda Prompt or Command Prompt

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_pilot_analysis_adapter.py" --epoch epoch2
"%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "%SIM%\scripts\s6b_analysis.py" --index PILOT_VALIDATION_PREDICTION_INDEX.json --output-subdir pilot_analysis_v1 --require-complete
```

No new packages are required. `--report` selects a different report directory and `--epoch` selects its frozen manifest. The script deliberately uses the root-defined G: native payload root. Repeated execution reuses an identical pilot prediction identity; changed dependencies require a separately named output version, not silent overwrite.

These results validate scheduling and scoring on the bounded pilot. They do not certify all44 challenge configurations, all240 scenes, native paced timing or a final shortlist.

