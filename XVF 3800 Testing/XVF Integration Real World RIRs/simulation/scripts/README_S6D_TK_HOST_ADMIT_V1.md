# Existing Tk8 then HOST2: mechanical admission

`s6d_tk_host_admit_v1.py` prepares unapproved metadata and provides a separate root-only admission command for the **unchanged** eight Tk and two HOST jobs in `reports/S6D/20260913T195357Z/runner/native_execution_queue_preparation_v1`. It never launches a model, GUI, recorder, or supervisor. Production must use this maintained helper path; frozen copies are review evidence.

## Inputs and outputs

Inputs are the exact pinned original queue/proposal files, their small source/manifest guards, accepted C12 closure `6d02b3fd`, accepted native176/68 receipt `7c397863`, V4 runner `fdffb4ca`, and reviewed inventory predicate `6730ecf6`. No source WAV, journal, model asset, or full payload census is read by preparation. The original supervisor still performs its full source/resource preflight before any model starts.

`--prepare` writes four files in a fresh directory: `TK8_PLAN.json`, `TK8_ROOT_REVIEW_PROPOSAL.json`, `HOST2_PLAN.json`, and `HOST2_ROOT_REVIEW_PROPOSAL.json`. Proposals have `allow_admission=false`; no actual approval is written. This path makes no process, disk-free, audio, device, or model query. Preparation cannot be used as authority.

`--admit` is for the root agent only, after source/queue review and predecessor closure. It requires an exact separately written root-review SHA. Before writing any accepted file it validates that review, all pinned literals, fresh output/state paths, completed prerequisite metadata, a complete fresh process inventory (one NN slot, no physical/other Python workload except the exact unrelated H2 maintenance script), C50/G75 GiB floors, and the original deadline/reserve; it calls the unchanged V4 `validate_queue`. Only then it writes `ADMISSION_PREFLIGHT.json`, `ROOT_ADMISSION.json`, and `APPROVAL.json` (last) in the original group directory. Partial writes are not runnable authority and must not be bypassed or overwritten. The helper does not claim a new cross-process mutex: root must withhold conflicting starts for the whole interval.

## Allocation and scope

Order: accepted C12 runtime closure → **physical bank closure** → Tk8 → actual full-source/Tk-view/owner closure → HOST2 → full-source/correctness/owner closure. Serial892 has its separate existing admission afterward. No physical overlap is allowed by this root launch policy. This is conservative allocation, not a changed scientific predicate; general permission to consider recording overlap is not a concrete current allocation. CPU logical IDs12–15, one neural worker, inner pools1, and shared40 GiB remain unchanged. The offline80 exception is not used. The physical bank shares the same40 GiB campaign roots. No core topology claim.

Tk8 uses actual Tk callbacks/widgets and fixed T0/T1/T2 views already declared in the original manifest. HOST2 is headless, two original1827.426625-second source sessions (29238826 frames each), distinct from the physical900-second sessions. Neither headless clocks nor Tk callbacks imply OS scanout. Original BB1 full-source/PCM/journal/dispatch/consumer gates and wrapper874d remain intact; this wrapper loads the persisted JSON RESULT, so it does not need the separate beam N6h serialization change.

## Root-review fields (never fill these as an unapproved fixture)

The root creates a fresh review from the proposal with status `ROOT_ACCEPTED_EXACT_TK_HOST_GROUP_FOR_ADMISSION`, the exact unchanged `plan`, `allow_admission=true`, owner/run, NN1 and physical overlapfalse. `prerequisite_acceptances.C12` is already the exact actual6d02 binding. The helper reads its two exact FINISH/checkpoint/census/keep-awake closures and all14 closed identities; it does not infer calibration efficacy from collection closure.

`prerequisite_acceptances.PhysicalBank` must contain `{binding, expected_status}` for a separately root-accepted closure receipt. That receipt must have the declared root status, owner/run, `queue` equal the plan's exact bank_queue_v6 binding, `all_owners_closed=true`, and explicit `closed_instances` (PID/creation pairs). A stopped or merely absent process does not substitute for root closure acceptance. A replacement physical queue requires a separately reviewed additive admission update.

HOST additionally requires `prerequisite_acceptances.Tk8` as a binding to actual status `ROOT_ACCEPTED_TK8_FULL_SOURCE_UI_AND_OWNER_CLOSURE`. Required fields: owner/run, exact Tk queue binding, accepted=planned=8, all_owners_closed=true, full_source_evidence_validated=true, all_declared_Tk_view_evidence_validated=true, nine closed process identities, and `phase_closure={state_dir,queue,checkpoint,supervisor_closure}`. Both saved checkpoint and supervisor closure must be FINISH for all eight exact jobs; census, owner lock and keep-awake closure remain mandatory. Root creates this only after separately validating the declared actual full-source/view artifacts. No future receipt is fabricated by preparation.

## PowerShell: prepare only

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' "$sim\scripts\s6d_tk_host_admit_v1.py" --prepare "$sim\reports\S6D\20260913T195357Z\runner\tk_host_admission_preparation_v1"
```

Choose a fresh suffix if that proposal directory exists; never overwrite history.

## Anaconda Prompt / CMD: prepare only

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" "%SIM%\scripts\s6d_tk_host_admit_v1.py" --prepare "%SIM%\reports\S6D\20260913T195357Z\runner\tk_host_admission_preparation_v1"
```

## Root only: admission and the existing launcher

After physical closure and independent source/queue review, supply the actual review path and SHA; placeholders below are deliberately not valid authority.

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' "$sim\scripts\s6d_tk_host_admit_v1.py" --admit tk8 --root-review '<actual root Tk8 review path>' --root-review-sha256 '<actual SHA256>'
& "$sim\reports\S6D\20260913T195357Z\runner\native_execution_queue_preparation_v1\Invoke-Native-Queue.ps1" -Group tk8
# Root only, after successful validation and current controlled allocation:
& "$sim\reports\S6D\20260913T195357Z\runner\native_execution_queue_preparation_v1\Invoke-Native-Queue.ps1" -Group tk8 -Execute
```

```bat
"C:\Users\amiri\anaconda3\python.exe" "%SIM%\scripts\s6d_tk_host_admit_v1.py" --admit tk8 --root-review "<actual root Tk8 review path>" --root-review-sha256 "<actual SHA256>"
powershell -NoProfile -File "%SIM%\reports\S6D\20260913T195357Z\runner\native_execution_queue_preparation_v1\Invoke-Native-Queue.ps1" -Group tk8
```

For HOST2, repeat admission with `--admit host2` and a distinct actual root HOST review **after Tk8 acceptance**, then use the same existing launcher with `-Group host2`. Validation alone launches no native job; `-Execute` is an explicit subsequent root action. See the original `README_RUN.md` for launch/state/stop details. No new supervisor or fresh native queue is constructed by this helper.

## Tiny model-free admission checks

`s6d_tk_host_admit_checks_v1.py` uses synthetic small metadata and injected process/V4 services; it does not query real processes or call production admission. It also reads the actual accepted C12 closure shape without touching result/audio/journals.

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' "$sim\scripts\s6d_tk_host_admit_checks_v1.py" --source-root "$sim\scripts" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\tk_host_admit_v1\checks_v1'
```

```bat
"C:\Users\amiri\anaconda3\python.exe" "%SIM%\scripts\s6d_tk_host_admit_checks_v1.py" --source-root "%SIM%\scripts" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\tk_host_admit_v1\checks_v1"
```
