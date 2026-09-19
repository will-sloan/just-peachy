# Register the S6C study

Purpose: `s6c_design.py` freezes the comparison hypotheses and metadata-only
panel before new S6C results. It carries all 44 old candidates and registers
finite lifecycle capacities, eight association families, three seeded
uninformative cue controls, an explicitly oracle-like nominal-angle diagnostic,
local parameter neighborhoods, actual neural/component recipes, four split
routes and nested enrollment conditions. Requested effective settings remain
subject to strict implementation validation; unsupported settings must receive
an explicit disposition and may not be reported as failed accuracy.

Inputs: immutable S6B effective profiles/input index/balanced panel, canonical
scene manifest and bound per-scene reference support. Selection reads metadata
only. It adds every complete under-two-second clip occurrence and every scene
without known source turns. It preserves all 240 rows for broad confirmation.

Outputs: `reports/S6C/20260910T123540Z/design/REGISTERED_DESIGN_V1.json`,
`REGISTERED_PANEL_V1.json`, `CANDIDATE_COVERAGE_AND_DISPOSITION.csv` and the
current checkpoint. The design freezes once. A changed hypothesis requires a
named amendment before its outcomes, not overwriting the registered document.

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' .\s6c_design.py
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_design.py
```

No model runs or audio playback occur. Successful output reports registered
configuration and panel counts. To resume registration, use the same command;
it returns the existing immutable design. See README_S6C.md for resource,
checkpoint, stop, invocation-time and rollback constraints.

`--calibration-amendment` registers seven additional C-only resolver companions
before new model outcomes: rotations A/B at 5/15/30 s and the large cohort at
15 s. It preserves the 153-row base design, bringing registered total to 160.
The exact cosine/margin grid, lexicographic calibration objective, minimum
coverage and no-Q dependency are saved in
`design/C_ONLY_CALIBRATION_AMENDMENT_V1.json`. These companions remain pending
until C is measured and its fitted settings are explicitly admitted; control
thresholds are never silently overwritten.

PowerShell: append `--calibration-amendment` to the Python command above.
Anaconda Prompt / CMD: append the same `--calibration-amendment` argument.
