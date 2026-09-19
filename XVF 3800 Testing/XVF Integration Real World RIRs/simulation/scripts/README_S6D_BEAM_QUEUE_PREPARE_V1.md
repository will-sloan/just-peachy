# Held native beam-stage queue

Purpose: `s6d_beam_queue_prepare_v1.py` turns an exact bound beam execution manifest into a literal code-only supervisor queue. Inputs are `--manifest`, its `--manifest-sha256`, and a fresh `--output` directly under the S6D report's runner directory. It verifies small exact source/metadata bindings and fresh native/protocol output paths. Outputs are `QUEUE.json`, an unapproved `APPROVAL_PROPOSAL.json` with an empty approved-job list, and `QUEUE_RECEIPT.json`. It never creates root approval, starts a supervisor/child/model, accesses hardware, or changes sources.

Each cell uses the frozen additive runner in the same process, exact full multistream audit including every journal hash, completed native loop and closed observer/consumer. The queue retains original owner IDs, C50/G75GiB floors, shared40GiB cap, original72h deadline/45-minute reserve, sensitive serial workload and75-second checked offline STOP grace. Hardware is not involved. Root must allocate nonoverlap with active176 paced work and independently review this proposal before adoption. A plain inner RESULT is insufficient.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_beam_queue_prepare_v1.py" --manifest '<exact bound C or native stage MANIFEST.json>' --manifest-sha256 '<SHA256>' --output "$sim\reports\S6D\20260913T195357Z\runner\beam_C_queue_proposed_v1"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_beam_queue_prepare_v1.py" --manifest "<exact bound MANIFEST.json>" --manifest-sha256 "<SHA256>" --output "%SIM%\reports\S6D\20260913T195357Z\runner\beam_C_queue_proposed_v1"
```

The output receipt supplies exact queue/runner hashes and G state directory. Root separately writes literal `ROOT_ADMISSION.json` and `APPROVAL.json`, validates using accepted V4's `--validate-only`, and decides any later launch. This helper supplies no automatic execution command and never copies proposed job hashes into an approved list. Use a fresh suffix for changed proposals; preserve earlier epochs.
