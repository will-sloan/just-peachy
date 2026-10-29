# Whistle completed rerun backup

This backup preserves the completed 26-29 October 2026 full-parameter Whistle
training run, its results, the analysis Word document, and the code needed to
understand or reproduce the frozen workflow. It does not launch training.

Repository: https://github.com/will-sloan/just-peachy

Backup branch: `codex/whistle-full-rerun-backup-2026-10-29`

## Completion and result

All three passes completed: 884,220 updates and 6,158,253 visits over
2,052,751 qualified training views per pass, covering 220,174 distinct source
utterances. All six development checkpoints and the single frozen confirmation
comparison completed. Original four-domain objective weights were preserved.

Development selected step 442,110. Its nine-cohort macro WER improved from
18.511% to 17.402%, and confirmation improved from 18.698% to 18.148%.
Confirmation nevertheless failed the CMU Arctic clean retention guard:
5.093% to 5.416% WER, a 0.323-point increase above the 0.250-point limit.
The original initial tuned model remains the default; the selected full-tuned
model is preserved as experimental. No runner-up, extra trial or refit was run.

Development uncertainty is exploratory and unadjusted for choosing among six
checkpoints. The full confirmation interval is undefined because HiFiTTS clean
has one reader. These are reused evaluation populations, with sparse VOiCES
coverage, no product-microphone validation, and no independent final age test.
Both models returned no words on the 20 silence/noise probes in each panel.

## Included inputs and outputs

- `Software Validation from Datasets/Training Tool/whistle_lab/`: training,
  evaluation, reporting and supervisor code, with its maintained READMEs.
- `training/whistle_full_rerun_v1/`: frozen settings, execution/split hashes,
  verification receipts, checkpoint/export metadata, all six native exports,
  full weights, latest and previous optimizer checkpoints, completed scores,
  uncertainty, selection, confirmation and final summary.
- `training/whistle_age_robust_v1/`: initial default native model, final adapter,
  pinned base/runtime assets, requirements and provenance needed to identify
  the comparison and initialization.
- `training/whistle_followups_v1/reporting/`: Word findings, all analyst notes,
  report status, and the existing evidence snapshots. Small JSON files cited
  by historical analyst notes are also preserved where available.
- `backup_manifest_20261029.json`: byte counts and SHA256 hashes for the
  preserved source, evidence and model files. The manifest itself, this README
  and Git attribute files are additional repository metadata.
- `shutdown_receipt_20261029.json`: verified process/task shutdown state.

This is a backup of code, findings and trained artifacts. Raw audio datasets,
row-level Parquet manifests, prediction JSONL, logs, caches and unrelated
workspace work are not included. A full training rerun additionally requires
the original licensed datasets and qualified row manifests referenced by the
frozen execution snapshot. Source and artifact hashes remain unchanged.

## Restore from Anaconda Prompt or Command Prompt

Install Git with Git LFS if unavailable. No Conda activation is needed to
download and inspect this backup. Choose a new destination directory:

```bat
git lfs install
git clone --branch codex/whistle-full-rerun-backup-2026-10-29 --single-branch https://github.com/will-sloan/just-peachy.git whistle-restored
cd whistle-restored
git lfs pull
git lfs fsck --objects HEAD
certutil -hashfile "training\whistle_followups_v1\reporting\Whistle_Fine_Tuning_Findings.docx" SHA256
start "" "training\whistle_followups_v1\reporting\Whistle_Fine_Tuning_Findings.docx"
```

Git LFS retrieves the actual model files; GitHub's source ZIP alone may contain
only LFS pointers. Expected Word SHA256:

`0826b8143acca5b47718c69e5e94b5b8e38a6c30d3f6a1b9ea4d1e1b67f81cc6`

## Restore from PowerShell

```powershell
git lfs install
git clone --branch codex/whistle-full-rerun-backup-2026-10-29 --single-branch https://github.com/will-sloan/just-peachy.git whistle-restored
Set-Location 'whistle-restored'
git lfs pull
git lfs fsck --objects HEAD
Get-FileHash -Algorithm SHA256 -LiteralPath 'training\whistle_followups_v1\reporting\Whistle_Fine_Tuning_Findings.docx'
Invoke-Item -LiteralPath 'training\whistle_followups_v1\reporting\Whistle_Fine_Tuning_Findings.docx'
```

The output is a restored checkout containing source, results, report and real
model files. Compare other restored files against the SHA256 manifest when
needed. The original launch scripts contain machine-specific paths; follow the
training README and deliberately adapt paths before using another machine.

## Models and provenance

Default native model:
`training/whistle_age_robust_v1/whistle.final.cact`.

Selected experimental native model:
`training/whistle_full_rerun_v1/whistle.experimental.cact` (step 442,110).

Its full parameter weights are `weights.experimental.msgpack` in the same
directory. They are not LoRA adapters. The terminal step 884,220 export is
preserved separately. Score ID zero means the preserved initial tuned
comparator; `whistle.base_zero.cact` is the distinct fresh pretrained export.

Recorded licenses are Common Voice CC0-1.0; AMI and VOiCES CC-BY-4.0;
CHiME-6 CC-BY-SA-4.0, resolved by the user on 23 October; base/runtime
Apache-2.0. See the retained license review, attribution/provenance records and
base/runtime license files.

All Whistle monitor tasks are disabled and its heartbeat is paused. The older
dashboard/watch processes were closed after all four runs were confirmed
complete. The Word report was published and its content/file structure verified;
visual layout remains unreviewed because an approved renderer was unavailable.
