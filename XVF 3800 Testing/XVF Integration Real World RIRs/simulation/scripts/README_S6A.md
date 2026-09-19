# S6A joint pipeline study

Purpose: validate and extend the prior baseline to all 240 existing physical scenes, then run bounded component and metadata research while preserving old results. The original 180/60 split remains descriptive. No hardware playback or new model weights are needed.

Inputs: canonical S4.5 scene manifest, accepted captures, existing S5 native receipts, pinned H2 models and Revision 14 workbook. O0 receives its fixed +3 dB scalar once; O1 is unity. Already gained FLOAT adapters and native PCM16 journals are consumed at unity.

Outputs: versioned reports in `simulation\reports\S6A\20260909T202250Z`, payloads in `G:\Just_Peachy_S6A\20260909T202250Z`, caches and archived original application under `simulation\staging\s6a\20260909T202250Z`, and a compact handoff ZIP. Raw recordings and old reports are unchanged.

From PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' .\s6a_prepare.py
& 'C:\Users\amiri\anaconda3\python.exe' .\s6a_baseline.py
```

From Anaconda Prompt or Windows Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s6a_prepare.py
"C:\Users\amiri\anaconda3\python.exe" s6a_baseline.py
```

Preparation is immutable and verifies existing jobs. The baseline runner is resumable by the same command; it has one coordinator lock, one native model child, creation-time ownership, at most one identical retry, 20-second status updates, a 12-hour invocation budget with 45-minute closure reserve, disk/RAM checks and exact journal verification. A later invocation after the fixed deadline needs a separately recorded continuation budget; do not edit a running script. Follow the phase READMEs below for the implemented profile/probe commands.

`s6a_baseline_entry.py` loads the exact copied original Python modules. It restores their original repository/asset discovery paths after relocation; all scientific values and model files stay identical. Optional research profiles in the actual application are separate from this B0 launcher. Rollback is simply omitting the research-profile flag; the snapshot preserves exact old code for reproduction.

Source support and scoring use the existing isolated S5 analysis environment (MeetEval 0.4.3). After preparation, run in PowerShell from the scripts folder:

```powershell
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' .\s6a_score.py freeze --workers 3
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' .\s6a_score.py score --workers 3 --require-complete
```

Anaconda Prompt or Command Prompt uses the same arguments without PowerShell's `&`:

```bat
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6a_score.py freeze --workers 3
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6a_score.py score --workers 3 --require-complete
```

`freeze` creates input-only source support for all 240 scenes. `score` resumes completed outputs and compares all 360 historical S5 results for exact numeric parity. Omit `--require-complete` only for an intermediate snapshot while baseline inference runs. Pending/failed jobs are never treated as empty successful outputs. `s6a_text_metrics.py` and `s6a_support_metrics.py` preserve S5 definitions with explicit all-bank access; old split fields are not relabelled. `s6a_alignment.py` derives the same waveform-correlation delay estimates for formerly deferred scenes in new report files; missing qualified lags remain unavailable.

Never run preparation, source-freeze correction or code edits concurrently with a consumer of the files being changed. Archived preflight corrections and original code are retained in staging. Derived report hashes identify the exact version used.

## Phase guide and completed-result use

Read the final report's `START_HERE.md` and completion receipts before executing commands. Existing compatible native results should be reused, not regenerated. The code in the compact handoff is an exact source record for this repository, not a standalone application distribution: the existing historical simulation helpers, pinned model assets, environments and local evidence are required. Source paths and hashes are retained in the receipts and local artifact index.

| Purpose | Code and maintained instructions |
|---|---|
| Original-setting baseline, source support and text scoring | This README; `s6a_prepare.py`, `s6a_alignment.py`, `s6a_baseline_entry.py`, `s6a_baseline.py`, `s6a_score.py`, `s6a_text_metrics.py`, `s6a_support_metrics.py`, shared `s6a_common.py` |
| Full-bank baseline aggregation, conditional uncertainty and geometry audit | `README_S6A_BASELINE_RESULTS.md` |
| Physical cues, exact feature reuse, six references, controls, tests and reporting | `README_S6A_CUES.md` |
| Actual native component profiles, guarded resume and authoritative v4 scoring | `README_S6A_PROBES.md`, `README_s6a_probe_resume.md` |
| Paired component effects, evidence/lineage and short-turn tables | `README_S6A_PROBE_REPORT.md` |
| Component accuracy and measured compute plots | `README_S6A_PROBE_FIGURES.md` |
| Paced desktop CPU/thread/queue experiment | `README_s6a_runtime_profile.md` |
| Actual neural prefix and delivered-telemetry causality checks | `README_s6a_causality_checks.md` |
| Native completed-result cache mutation checks | `README_s6a_native_cache_checks.md` |
| Extended mechanisms, supported bindings and proposed S6B design | `README_S6A_DESIGN.md` |
| Final verification, process closure and compact ZIP | `README_S6A_HANDOFF.md` |

The actual application's `README.md`, `README_RESEARCH_PROFILES.md` and any adjacent research README document opt-in CLI use, parameter sections, inputs/outputs and rollback. Consult the filenames included under `code/application` in the handoff. Do not copy a candidate profile into global defaults or treat a proposed S6B extension as an implemented field.

For this invocation, the final native manifest is `PROBE_JOB_MANIFEST_V2.json`, with720 outputs (10 profiles ×36 scenes ×2 taps). Earlier48 native V1 outputs and earlier intermediate analysis namespaces remain archived and excluded. Worker allocation changed from two to four only after a graceful stop at118 valid V2 results; the guarded resume retained the same job identities. Numeric pool variables are fixed before model imports. These concurrent research workers are not a target-device deployment recipe.

The ordinary research application profile CLI does not replace exact B0 reproduction: use the archived baseline launcher when the claim requires the old code and historical attribution policy. Raw ASR text and first labels, prospective tracker revisions and final display punctuation have separate meanings. The reports describe which one is scored.
