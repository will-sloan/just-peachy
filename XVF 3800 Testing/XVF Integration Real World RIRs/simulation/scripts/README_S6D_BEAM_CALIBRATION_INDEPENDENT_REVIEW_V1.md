This independent helper reviews frozen C calibration source9165da50 with eight tiny model-free probes. It is review code, not a calibration or acceptance tool. It imports only the frozen metadata helpers and standard-library evidence reader. It never starts a model, process or device, opens actual C audio/journals, or creates real experiment authority.

Inputs: exact frozen source files under R/application/beam_C_calibration_source_v1/helpers and a fresh G-only --output directory. The frozen helper hash is checked. The fixtures construct clearly synthetic C metadata, zero-byte-valued PCM journals (128kB per stream), and tiny JSONL events beneath that G directory. Full extract is exercised against those synthetic files. The exact frozen BeamSelector.choose AST is used with an explicitly fake scalar correlation function to isolate candidate eligibility/ranking without model or waveform computation.

Outputs: TESTS.log, RECEIPT.json and synthetic fixture subdirectories. Three tests document reproduced concerns, so a passing probe suite does not mean calibration source approval. They show unknown auto competitors omitted from fitted populations, semantically unchecked root-acceptance status, and per-gate support that does not prove joint selector retention. Five probes verify fail-closed empty/Q/foreign support, possible-overlap exclusion and inadequate retained-source separation. Original author fixtures are independent and not reimplemented.

PowerShell / Anaconda PowerShell Prompt:
```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -B 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_beam_calibration_independent_review_v1.py' --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_calibration_independent_v1'
Get-Content -LiteralPath 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_calibration_independent_v1\RECEIPT.json'
```

Anaconda Prompt / CMD:
```bat
"C:\Users\amiri\anaconda3\python.exe" -B "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_beam_calibration_independent_review_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_calibration_independent_v1"
type "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_calibration_independent_v1\RECEIPT.json"
```

Choose another fresh G-only output name for an explicitly requested repeat. Existing directories fail without overwrite. Run the maintained helper at SIM/scripts; frozen snapshots are for inspection. Bytecode writes are disabled. Synthetic acceptance/status fields are test inputs only, never actual root approval. No production source or active queue is changed.

