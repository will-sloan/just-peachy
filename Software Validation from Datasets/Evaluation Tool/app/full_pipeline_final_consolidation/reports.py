"""Final bounded-scope reports, handoff, and reproducibility documents."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from . import COMPLETION_MARKERS, FINAL_OUTPUTS, scope_fields
from .analysis import FailureAnalysis, PROPAGATION
from .evidence import EvidenceBundle
from .io import (
    artifact_ref,
    canonical_json_bytes,
    read_json,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
    write_text_atomic,
)
from .ranking import RankingResult


def write_markdown_reports(
    *,
    output_root: Path,
    workspace_root: Path,
    bundle: EvidenceBundle,
    rankings: RankingResult,
    failures: FailureAnalysis,
    inventory_rows: Sequence[Mapping[str, object]],
    pi_handoff: Mapping[str, object],
) -> list[Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "FINAL_PIPELINE_REPORT.md": _final_report(
            bundle, rankings, failures, inventory_rows, pi_handoff
        ),
        "PIPELINE_FAILURE_ANALYSIS.md": _failure_report(failures),
        "FINE_TUNING_CANDIDATES.md": _fine_tuning_report(failures),
        "XVF3800_INTEGRATION_HANDOFF.md": _xvf_handoff(),
        "FINAL_RUNBOOK.md": _runbook(output_root, workspace_root),
    }
    return [write_text_atomic(output_root / name, text) for name, text in paths.items()]


def write_reproducibility_manifest(
    *,
    output_root: Path,
    bundle: EvidenceBundle,
    rankings: RankingResult,
    inventory_rows: Sequence[Mapping[str, object]],
    pre_state_snapshot_path: Path,
) -> Path:
    prior_outputs = [
        output_root / name
        for name in FINAL_OUTPUTS
        if name != "REPRODUCIBILITY_MANIFEST.json"
    ]
    missing = [path.name for path in prior_outputs if not path.is_file()]
    if missing:
        raise RuntimeError(
            "reproducibility manifest must be written after other final outputs: "
            + ", ".join(missing)
        )
    pre_state_snapshot = read_json(pre_state_snapshot_path)
    document = {
        "schema_version": "full-pipeline-final-reproducibility-manifest.v1",
        **scope_fields(),
        "status": "PASS",
        "completion_marker_on_success": COMPLETION_MARKERS[8],
        "original_full_scope_marker_emitted": False,
        "input_completion_chain": [
            {
                "prompt_index": prompt,
                "completion_marker": completion.marker,
                "path": str(completion.path),
                "sha256": completion.sha256,
                "artifact_manifest_path": str(completion.manifest_path),
                "artifact_manifest_sha256": completion.manifest_sha256,
            }
            for prompt, completion in sorted(bundle.completions.items())
        ],
        "authorities": {
            "amendment": artifact_ref(bundle.amendment_path),
            "program_state_before_prompt8": {
                "mutable_source_path": str(bundle.program_state_path),
                "mutable_source_sha256_before_prompt8": bundle.program_state_sha256,
                "immutable_snapshot": artifact_ref(pre_state_snapshot_path),
                "embedded_document": pre_state_snapshot,
                "embedded_canonical_sha256": sha256_bytes(
                    canonical_json_bytes(pre_state_snapshot)
                ),
            },
            "execution_policy_addendum": {
                **artifact_ref(bundle.execution_policy_path),
                "embedded_document": dict(bundle.execution_policy),
                "embedded_canonical_sha256": sha256_bytes(
                    canonical_json_bytes(bundle.execution_policy)
                ),
            },
            "adapter_registry": artifact_ref(bundle.adapter_registry_path),
            "raspberry_pi_deployment_steering": {
                **artifact_ref(bundle.pi_deployment_steering_path),
                "embedded_document": dict(bundle.pi_deployment_steering),
                "embedded_canonical_sha256": sha256_bytes(
                    canonical_json_bytes(bundle.pi_deployment_steering)
                ),
            },
            "matrix": artifact_ref(bundle.matrix_path),
            "runtime": artifact_ref(bundle.runtime_path),
            "license_and_asset_manifest": artifact_ref(bundle.license_document_path),
        },
        "frozen_policy_refs": bundle.frozen_policy_refs,
        "pipeline_count": len(bundle.pipeline_ids),
        "pipeline_ids": list(bundle.pipeline_ids),
        "selection_policy": dict(rankings.policy),
        "source_inventory_row_count": len(inventory_rows),
        "source_inventory_all_hash_validated": all(
            row.get("hash_validated") is True for row in inventory_rows
        ),
        "generated_output_sha256s": {
            path.name: sha256_file(path)
            for path in sorted(prior_outputs, key=lambda item: item.name)
        },
        "package_policy": {
            "member_allowlist": sorted(FINAL_OUTPUTS),
            "raw_datasets_included": False,
            "model_weights_included": False,
            "credentials_included": False,
            "large_caches_included": False,
            "biometric_vectors_included": False,
        },
        "scientific_actions": {
            "new_campaign_launched": False,
            "retuning_performed": False,
            "fine_tuning_performed": False,
            "xvf_implemented": False,
            "prompt7_roles_reselected": False,
        },
        "execution_time_policy": {
            "policy_id": "ADVISORY_ONLY_NO_AUTOMATIC_STOP",
            "total_planning_target_hours": 192,
            "prompt8_planning_target_hours": 4,
            "elapsed_time_kill_switch_enabled": False,
            "elapsed_time_admission_gate_enabled": False,
        },
    }
    return write_json_atomic(output_root / "REPRODUCIBILITY_MANIFEST.json", document)


def _final_report(
    bundle: EvidenceBundle,
    rankings: RankingResult,
    failures: FailureAnalysis,
    inventory_rows: Sequence[Mapping[str, object]],
    pi_handoff: Mapping[str, object],
) -> str:
    alternative = rankings.alternative or "None justified by Prompt-7 hardening"
    selected_lookup = {str(row["pipeline_id"]): row for row in rankings.rows}

    def line(role: str, pipeline_id: str | None) -> str:
        if not pipeline_id:
            return f"- {role}: none"
        row = selected_lookup[pipeline_id]
        return (
            f"- {role}: `{pipeline_id}` (technical rank {row['technical_performance_rank']}, "
            f"UX-safety rank {row['user_experience_safety_rank']}, "
            f"resource rank {row['resource_efficiency_rank']})"
        )

    def ranking_view(title: str, field: str) -> str:
        ordered = sorted(
            rankings.rows,
            key=lambda row: (int(row[field]), str(row["pipeline_id"])),
        )[:5]
        body = [
            f"### {title}",
            "",
            "| Rank | Pipeline | Evidence boundary |",
            "|---:|---|---|",
        ]
        for row in ordered:
            body.append(
                f"| {row[field]} | `{row['pipeline_id']}` | "
                f"P5 exact all-18; P6 {row['extended_evidence_status']} |"
            )
        return "\n".join(body)

    technical_view = ranking_view(
        "A. Technical performance", "technical_performance_rank"
    )
    ux_view = ranking_view("B. User-experience safety", "user_experience_safety_rank")
    resource_view = ranking_view("C. Resource efficiency", "resource_efficiency_rank")
    licensing_view = ranking_view(
        "D. Deployment/licensing review readiness",
        "deployment_licensing_readiness_rank",
    )
    pi_ids = [
        str(row.get("pipeline_id"))
        for row in pi_handoff.get("candidates", [])
        if isinstance(row, Mapping)
    ]
    pi_rows = [
        "| Pipeline | 2-GiB class | Linux ARM64 portability |",
        "|---|---|---|",
        *(
            f"| `{row.get('pipeline_id')}` | "
            f"{row.get('two_gib_feasibility_class')} | "
            f"{row.get('linux_arm64_portability_class')} |"
            for row in pi_handoff.get("candidates", [])
            if isinstance(row, Mapping)
        ),
    ]
    pi_table = "\n".join(pi_rows)

    return f"""# Final complete-pipeline report — reduced eight-day program

Final status: `{COMPLETION_MARKERS[8]}`

This is the amended **BOUNDED_REDUCED** C:-only program. It does not claim the original full-scope marker `COMPLETE_FULL_PIPELINE_PROGRAM`, exhaustive native coverage, real Beaker/XVF performance, or commercial license clearance.

## Recommendations

{line("Primary", rankings.primary)}
{line("Fallback", rankings.fallback)}
{line("Alternative", rankings.alternative)}
- Pipeline not worth continuing: `{rankings.not_worth_continuing}` — {rankings.not_worth_reason}.

The production roles above were consumed from the completed Prompt-7 hardening catalog; Prompt 8 did not reselect or retune them. Alternative: {alternative}.

## A. Desktop / software scientific ranking

The desktop ranking and frozen Prompt-7 software roles are authoritative only for the completed desktop evaluation. Ordinary accuracy effect sizes and speaker-bootstrap confidence intervals remain explicit; there is no universal “within 1% means equivalent” rule. High-cost wrong-known, stranger false-known, and severe contamination errors are not discounted as ordinary small differences.

## Separate ranking views

{technical_view}

{ux_view}

{resource_view}

{licensing_view}

### E. Overall recommendation

The overall recommendation is the frozen Prompt-7 role assignment shown above. It is not a fifth composite rank. The full all-18 rows, explicit missing/unsupported statuses, component licensing declarations, and Pareto membership are in `FINAL_PIPELINE_RANKING.csv`.

## B. Raspberry Pi / approximately 2-GB ARM candidate shortlist

The separate, unordered future-deployment shortlist is: {", ".join(f"`{item}`" for item in pi_ids)}. Exact 26-field candidate records, all 25 known/unknown deployment attributes, feasibility classes, paired effects/confidence intervals, the 14 required ARM tests, and the seven Linux ARM64 portability tests are in `RASPBERRY_PI_DEPLOYMENT_HANDOFF.json`.

{pi_table}

This shortlist is not a Raspberry Pi ranking and names no final Pi winner. Desktop RTF, RAM, and accuracy indicate burden and scientific credibility but do not predict optimized ARM performance. Windows x86-64 evidence is not relabelled as Linux ARM64 portability; Windows-specific process, path, audio, permission, and service assumptions remain explicit. H2 sharing/reuse is a potential optimization only—not an observed current saving. H5's distinct ECAPA identity model retains a safety-versus-two-model trade-off. WeSpeaker and both Original Sherpa and Sherpa Giga paths remain explicitly audited without predicting the ARM result. The approximately 2-GB target is a design constraint, not a retrospective scientific filter.

## Evidence and ranking method

- All 18 frozen pipelines have one checksum-validated held-out summary row.
- Prompts 4–7 form an exact SHA-256 predecessor chain and passed their universal hash, firewall, and prerequisite gates.
- {len(inventory_rows)} source result/artifact records were inventoried and hash-validated, including all four failure inventories and both later-stage licensing records.
- Technical, user-experience safety, resource, and deployment/licensing rankings are separate.
- Technical ranking maps the matrix's exact twelve ordered priorities lexicographically. Missing or unsupported evidence is explicit at its own priority. Priority 11 contains reliability and real-time operation; priority 12 contains CPU, RAM, and model complexity. UX and resource views remain separate. No weighted composite score exists.
- P5 exact all-18 evidence supplies comparable core ranks. P6 predeclared-extended metrics and P7 acceptance/role evidence are retained in separate fields; Prompt 8 does not silently mix the extended subset into the all-18 rank.
- Pareto membership uses wrong-known time, stranger false-known time, speaker-attributed WER, correctly named known rate, serial RTF, and peak RAM. Missing/failing/non-real-time rows are explicitly ineligible.
- Licensing rank describes review readiness only and is not a legal or commercial-clearance opinion.

## Major failure or limitation

`{failures.major_failure}`: {failures.major_failure_detail}

Retained source failure rows: {len(failures.failed_records)} of {failures.source_row_count} terminal/inventory rows. Failed records remain referenced in `RESULT_FILE_INVENTORY.csv` and are decomposed in `PIPELINE_FAILURE_ANALYSIS.md`; none were silently removed.

## Fine-tuning and XVF

Fine-tuning decision: `{failures.fine_tuning_decision}`. No training occurred. `FINE_TUNING_CANDIDATES.md` admits neural adaptation only from a source-declared reproducible failed case with a reason and frozen regression tests. Aggregate held-out identity exposure can support `POLICY_CHANGE_ONLY`, never neural adaptation.

XVF remains future work. `XVF3800_INTEGRATION_HANDOFF.md` defines timestamped processed audio, energy, AoA, confidence, and direction-change inputs plus the five required ablations; no XVF path was implemented or evaluated here.

## Reproducibility boundary

The final ZIP contains only the ten fixed text/CSV/JSON outputs. It excludes datasets, model weights, credentials, large caches, prediction trees, and biometric vectors. Exact source and output hashes are in `REPRODUCIBILITY_MANIFEST.json`.
"""


def _failure_report(failures: FailureAnalysis) -> str:
    lines = [
        "# Pipeline failure analysis",
        "",
        "This report retains all failed/missing terminal records from Prompts 4–7 and associates them with components. Association is not asserted as causation unless the source inventory itself provided that attribution.",
        "",
        f"Source inventory rows: {failures.source_row_count}. Failed/missing records: {len(failures.failed_records)}.",
        "",
        "## Component propagation map",
        "",
        "| Component | Retained failures | Can propagate into |",
        "|---|---:|---|",
    ]
    for component, propagation in PROPAGATION.items():
        lines.append(
            f"| {component} | {failures.component_counts.get(component, 0)} | {', '.join(propagation)} |"
        )
    lines.extend(
        [
            "",
            "## Measured error exposure",
            "",
            "These are observed end-to-end metrics associated with a component's possible propagation path. They are not causal attribution to that component.",
            "",
            "| Component association | Metric | Computed pipelines | Missing/unsupported pipelines | Mean | Maximum |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in failures.measured_error_exposure:
        mean = "—" if row["mean"] is None else f"{float(row['mean']):.6g}"
        maximum = "—" if row["maximum"] is None else f"{float(row['maximum']):.6g}"
        lines.append(
            f"| {row['component']} | {row['metric']} | {row['computed_pipeline_count']} | "
            f"{row['missing_pipeline_count']} | {mean} | {maximum} |"
        )
    lines.extend(
        [
            "",
            "## Terminal status inventory",
            "",
            "| Status | Source rows |",
            "|---|---:|",
        ]
    )
    for status, count in failures.terminal_status_counts.items():
        lines.append(f"| {status} | {count} |")
    lines.extend(
        [
            "",
            "## Failed/missing records",
            "",
            "| Prompt | Pipeline | Case/job | Status | Component association | Attribution | Reason digest | Source row |",
            "|---:|---|---|---|---|---|---|---:|",
        ]
    )
    if failures.failed_records:
        for row in failures.failed_records:
            lines.append(
                f"| {row['source_prompt']} | {row['pipeline_id']} | {row['case_or_job_id']} | "
                f"{row['terminal_status']} | {', '.join(row['component_candidates'])} | "
                f"{row['component_attribution']} | {row['failure_reason_sha256'] or '—'} | "
                f"{row['source_row_index']} |"
            )
    else:
        lines.append(
            "| — | — | — | No failed/missing terminal records | — | — | — | — |"
        )
    lines.extend(
        [
            "",
            "Raw error text is intentionally not copied into this compact package. The exact source file, row, and SHA-256 remain in `RESULT_FILE_INVENTORY.csv`, preserving auditability without copying credentials or sensitive logs.",
            "",
            "## Major failure",
            "",
            f"`{failures.major_failure}` — {failures.major_failure_detail}",
            "",
        ]
    )
    return "\n".join(lines)


def _fine_tuning_report(failures: FailureAnalysis) -> str:
    lines = [
        "# Fine-tuning candidates",
        "",
        "No fine-tuning or training was performed. Neural adaptation is admitted only from a source-declared reproducible failed case with a reason and frozen regression tests; a single failed job is insufficient. Checksum-bound aggregate held-out identity exposure may support POLICY_CHANGE_ONLY, which is policy triage rather than neural adaptation evidence.",
        "",
        f"Decision: `{failures.fine_tuning_decision}`",
        "",
        "| Decision | Observed failure | Scenario | Training target | Frozen tests | Regression risk | Real Beaker/XVF audio first? | Admission basis | Source evidence |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    if failures.adaptation_candidates:
        for row in failures.adaptation_candidates:
            lines.append(
                f"| {row['decision']} | {row['observed_failure']} | {row['affected_scenario']} | "
                f"{row['expected_training_target']} | {row['frozen_tests_to_rerun']} | "
                f"{row['regression_risk']} | {str(row['real_beaker_xvf_audio_required_first']).lower()} |"
                f" {row['admission_basis']} | {Path(str(row['source_file'])).name} row {row['source_row_index']}; "
                f"reason SHA-256 `{row['source_failure_reason_sha256'] or 'not-recorded'}` |"
            )
    else:
        lines.append(
            "| NO_FINE_TUNING_CURRENTLY_JUSTIFIED | No source row met the reproducible neural-evidence gate and no aggregate policy exposure was present | — | — | — | Avoid regression from unsupported adaptation | Collect real device evidence before deciding | NO_QUALIFYING_EVIDENCE | No qualifying evidence |"
        )
    lines.extend(
        [
            "",
            "Policy-only threshold, hysteresis, buffering, or UI changes are not relabeled as neural fine-tuning. Any future adaptation must rerun the frozen held-out, extended, safety, resource, and reliability tests and must not inspect evaluation data while tuning.",
            "",
        ]
    )
    return "\n".join(lines)


def _xvf_handoff() -> str:
    return """# XVF3800 future integration handoff

XVF is not implemented or evaluated by this Prompt-8 package. The future adapter must preserve the frozen audio-only path and align every metadata sample to the same monotonic session clock.

## Input contract

| Field | Type/unit | Requirement |
|---|---|---|
| `session_id` | UTF-8 identifier | Stable within one capture; no cross-session identity reuse |
| `timestamp_start_ns` / `timestamp_end_ns` | monotonic nanoseconds | Half-open interval, nondecreasing, same epoch as audio events |
| `processed_audio_pcm16le` | bytes | Declared sample rate/channels; no implicit resampling |
| `sample_rate_hz` | integer | Must match payload and runtime capability |
| `energy_dbfs` | float or null | Window definition and calibration identity recorded |
| `aoa_degrees` | float or null | Coordinate convention fixed and documented |
| `aoa_confidence` | calibrated float [0,1] or null | Must say calibrated; never present raw score as probability |
| `direction_change` | boolean/event | Includes old/new angle, confidence, timestamp, detector version |
| `xvf_firmware_id` | string | Exact firmware/config identity and hash where exportable |
| `clock_sync_error_ns` | integer | Measured synchronization uncertainty; missing is explicit |

The runtime should consume a versioned `XvfFrame` at its backend-neutral event boundary. Audio remains independently usable when any metadata field is missing. Reject backward timestamps, impossible angles/confidence, format changes without a boundary event, or session-ID mismatch. Record late/dropped metadata and never block audio indefinitely waiting for AoA.

## Frozen future ablations

1. audio only;
2. audio + energy;
3. audio + AoA;
4. audio + energy + AoA;
5. processed XVF audio + metadata.

Use identical recordings, enrollment profiles, pipeline hashes, and scoring for paired comparisons. Report safety (wrong-known/stranger false-known), attribution, latency decomposition, dropped/late metadata, RTF/RAM, and reliability separately. Do not infer real Beaker power from desktop telemetry.

## Work remaining

- implement and validate the timestamp synchronizer and versioned event adapter;
- capture leakage-safe real Beaker/XVF development and untouched evaluation audio;
- freeze coordinate/calibration/firmware identities before evaluation;
- run the five paired ablations on the selected primary/fallback/optional alternative;
- repeat resource/power tests on actual target hardware.
"""


def _runbook(output_root: Path, workspace_root: Path) -> str:
    tool_root = Path(__file__).resolve().parents[2]
    wrapper = tool_root / "scripts/run_full_pipeline_final_consolidation.ps1"
    completion = workspace_root / "completion_marker.json"
    return f"""# Final reproducibility runbook

Purpose: validate completed reduced eight-day Prompts 4–7, consolidate results, create transparent rankings/failure analysis, and produce the compact final package. This command performs no inference, retuning, training, or XVF implementation.

## PowerShell / Anaconda Prompt

```powershell
Set-Location "{tool_root}"
& "{wrapper}" -Action RunAll -WorkspaceRoot "{workspace_root}"
```

The controller normally supplies the Prompt-7 completion through `JP8_PREDECESSOR_COMPLETION_PATH`. For a direct manual run, add:

```powershell
-Prompt7Marker "C:\\absolute\\C-only\\prompt7\\completion_marker.json"
```

Status and validation:

```powershell
& "{wrapper}" -Action Status -WorkspaceRoot "{workspace_root}"
& "{wrapper}" -Action ValidateCompletion -WorkspaceRoot "{workspace_root}"
```

Graceful stop:

```powershell
& "{wrapper}" -Action Stop -WorkspaceRoot "{workspace_root}"
```

Inputs are the exact Prompt-7 universal completion and its SHA-linked Prompt-6→5→4 chain, canonical `PROGRAM_STATE.json`, eight-day amendment, advisory execution-policy addendum, exact adapter registry, Raspberry Pi/Linux ARM64 steering authority, matrix/runtime configs, frozen policies, all result inventories, failure inventories, and licensing/provenance records. The chain must contain checksum-bound Prompt-5 all-18 deployment evidence, Prompt-6 extended deployment evidence, and Prompt-7's authoritative unordered 2–4 candidate shortlist. All paths must resolve to drive C: and at least 35 GiB must remain free before writes. The 192-hour program target and 4-hour Prompt-8 target are advisory planning estimates only; neither is an elapsed-time stop or admission gate.

Outputs are written to `{output_root}`. The authoritative bounded completion is `{completion}`. `RunAll` prints `UPLOAD THIS FILE TO CHATGPT` followed by the absolute ZIP path and SHA-256.

The package contains exactly ten allowlisted files, including a separate machine-readable Raspberry Pi deployment handoff. It does not claim a final Raspberry Pi winner or treat desktop Windows/x86 measurements as Linux ARM64 results. It does not claim the original full-scope marker and excludes raw datasets, model weights, credentials, large caches, prediction trees, and biometric vectors.
"""


__all__ = ["write_markdown_reports", "write_reproducibility_manifest"]
