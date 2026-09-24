# Bounded native assigned-seat check

`check_seat_modes.py` uses genuine saved CMU ARCTIC audio and admitted ReDimNet
enrollment fixtures from task 04. It executes three 12-second source-paced files
through the real controller, models, seat resolver and Tk widgets. Direction
receipts are explicitly **synthetic**, fed through the actual causal adapter.
This tests inference-to-widget wiring, not live XVF acoustic seat accuracy.
No microphone, speaker playback, real-person enrollment, model download or training.

Inputs: an existing task 04 native fixture directory containing `people`,
`A_12s.wav`, `B_12s.wav` and `ROSTER_NATIVE_CHECK.json`; unchanged local models.
Outputs: a fresh private data root with native/linked logs, source/model/reference
hash bindings, `SEAT_NATIVE_CHECK.json`, timings/RSS, and annotated fixture screenshots.
The output must not exist, and must be outside the application/release directory.

From the repository root, PowerShell:

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tools\check_seat_modes.py --fixture .\Resumes\.uiiter2_04\native_v2 --data-root .\Resumes\.uiiter2_05\native_v1
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B prototype\tools\check_seat_modes.py --fixture Resumes\.uiiter2_04\native_v2 --data-root Resumes\.uiiter2_05\native_v1
```

Use a different fresh output directory for an intentional rerun. Three cases
can be reduced to the direction/UI regression alone with
`--case direction_change_motion` when the other paths have already been verified.
The three cases
cover direction-only seat changes and motion, hybrid known voice with conflicting
seat direction, and a hybrid outsider. Synthetic unit checks cover collisions,
missing/stale directions, front/back folding and music/overlap rejection. A real
multi-person seating protocol remains a separate participatory field check.
