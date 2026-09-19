# Prepare the complete predeclared S6D physical bank

Purpose: resolve all mandatory capture groups from the existing predeclaration, using unchanged canonical microphone WAVs and the already built disjoint E/continuous inputs. This script performs read-only waveform/hash/header/finiteness/headroom checks and writes proposal JSON. It never accesses a device, computes RIRs, changes gain/timing, runs models or creates hardware authorization.

Inputs: physical_preparation_v2/CAMPAIGN_BATCH_PROPOSAL.json and its three immutable authorities, the current reviewed qualification proposal, G/enrollment_continuous_inputs_v1/ROOT_ADOPTION_MAP.json and exact existing4MIC16k source WAVs. Outputs: reports/S6D/20260913T195357Z/physical_bank_preparation_v1 with20 group proposals and a complete PREPARATION_RESULT.json. Each group retains separate pre-QA, body and post-QA owners. The total is240 MAIN+48 SCAN+4 repeats+60E+2 uninterrupted900s+40QA=394 attempts, or427 with all33 qualification attempts. No optional hypotheses are silently added. Current actual ledger failures still count against global limits at later admission.

PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_bank_capture_prepare_v1.py'
```

Anaconda Prompt / CMD, no activation:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_bank_capture_prepare_v1.py"
```

Existing outputs are refused. Before any execution, root must review actual MAIN/SCAN route, delay/tail, telemetry/observer and QA/restoration evidence, then create literal bounded capture plans/queues under the accepted runner. Source WAV hashes remain in those plans and are validated by the owner; periodic runner source lists contain small code/configuration only. Raw bank outputs are proposed under G:/Just_Peachy_S6D/20260913T195357Z/bank_captures_v1. The device owner appends beam_bank/case/profile/attempt. Historical recordings remain untouched. Baseline DSP recipe, unity scaling,1s/3s guards,480attempt/21600s/40GiB/C50GiB/G75GiB and the unchanged72h deadline all apply.
