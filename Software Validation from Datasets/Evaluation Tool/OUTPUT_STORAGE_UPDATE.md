# Evaluation output storage update

Updated: 2026-08-20

## Purpose

Keep all machine-local Just-Peachy evaluation outputs beside the Evaluation
Tool instead of at the Windows user-profile root. The files remain local and
are excluded from Git.

## Relocation

The five folders below were moved without rewriting their contents:

| Old location under `C:\Users\amiri` | New location under `<Evaluation Tool>` | Files | Bytes | Verified tree SHA-256 |
|---|---|---:|---:|---|
| `JustPeachyGeneratedData` | `JustPeachyGeneratedData` | 188 | 349,283,714 | `4c9afa774daf31e268eac35d4d5785a2595605b28f26738153c78ad7bf186c33` |
| `JustPeachyLogs` | `JustPeachyLogs` | 7 | 263,987 | `a75e8a500415c6584c4d5da0b3d91d651689f33a86dea2bb2a8c6abb4e3070bf` |
| `JustPeachyResearchSummaries` | `JustPeachyResearchSummaries` | 2,899 | 32,194,996 | `1680401ed0f35c2c00436c26231f23b1627952a04b019ad8a56006350aa1e39c` |
| `JustPeachyResults` | `JustPeachyResults` | 3,271 | 30,597,186 | `7fc9a2f6388a529e35fb0a3cd3b4fa35fcc53f281e8fb06b10b9954997e2cd6e` |
| `JustPeachyTransfers` | `JustPeachyTransfers` | 5,851 | 1,787,732,114 | `a073281e5e732b7f5a700ad15ed9f2f5c9b8644731ae7a171045386b249253e8` |

`<Evaluation Tool>` is:
`C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool`.
Each before/after tree identity matched. The identity is SHA-256 over the sorted
relative file path, byte count, and SHA-256 of every file.

## Future inputs and outputs

Inputs are unchanged: normalized metadata, raw datasets, model assets, and
frozen benchmark/configuration files stay where their existing portable
resolvers place them. New generated audio, speaker-research results, compact
research summaries, logs, and transfer packages belong in the corresponding
folder above. Existing environment or command-line overrides still take
precedence; no scientific identity, manifest, dataset, or model file was
changed by this relocation.

## How to check the defaults

From Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
python -c "from app.utils.paths import evaluation_output_root; print(evaluation_output_root('results'))"
```

From PowerShell:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& ..\..\.venv\Scripts\python.exe -c "from app.utils.paths import evaluation_output_root; print(evaluation_output_root('results'))"
```

The check reads the repository location and prints the future results folder;
it creates no output and starts no evaluation.
