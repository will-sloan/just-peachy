# H2 enrollment and held-out firewall audit

## Purpose

`audit_h2_enrollment_firewall.py` creates a compact, signed metadata receipt
proving that the frozen H2 development and evaluation partitions are separate.
It checks enrollment identities, reserved enrollment clips, case identities,
audio hashes, gallery membership, and the held-out queue's pre-open state.

The audit does **not** open or copy audio, embeddings, biometric templates,
model weights, evaluation predictions, or evaluation metrics. Large case
manifests remain in their authoritative benchmark location and are represented
in the receipt by exact SHA-256 identities and compact set digests.

## Inputs

The default H2 v16 workspace must contain:

- `protocol_manifest.json`;
- `job_manifest.json`;
- `program_state.json`;
- `runtime_implementation_identity.json`;
- `campaign.sqlite3`.

The prepared protocol named by `protocol_manifest.json` must contain:

- `protocol_summary.json`;
- development and evaluation `case_manifest.jsonl` files;
- development and evaluation `enrollment_registry.jsonl` files.

## Output

The default output is:

```text
automated_runs\h2_complete_product_pipeline_v17\engineering_validation\enrollment_firewall_audit_receipt.json
```

The receipt contains no audio or biometric payload. It contains counts,
zero-overlap assertions, source-file hashes, partition identities, frozen
runtime/protocol bindings, held-out pre-open evidence, and a canonical receipt
signature. The final-package supplement packages this compact receipt and the
audit source/test/README, not the large manifests.

## Run from PowerShell

```powershell
cd "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -B .\scripts\audit_h2_enrollment_firewall.py
```

To select explicit inputs and output:

```powershell
$Workspace = "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17"
$Output = Join-Path $Workspace "engineering_validation\enrollment_firewall_audit_receipt.json"
& "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -B .\scripts\audit_h2_enrollment_firewall.py --workspace $Workspace --output $Output
```

Validate an existing receipt without reading scientific data:

```powershell
& "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -B .\scripts\audit_h2_enrollment_firewall.py --validate $Output
```

## Run from Anaconda Prompt or Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -B scripts\audit_h2_enrollment_firewall.py
```

## Tests

```powershell
cd "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest -q .\tests\test_h2_enrollment_firewall_audit.py
```

## Interpretation

`status: VALID` means all required cross-split identity and source overlap
counts are zero, each split's gallery and speaker membership exactly matches
its enrollment registry, and every frozen evaluation job was still pending
with no attempt/result/freeze artifact at audit time. Any mismatch fails closed
and no receipt is published.
