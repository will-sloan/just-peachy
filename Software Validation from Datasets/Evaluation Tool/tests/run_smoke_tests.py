"""Run Evaluation Tool smoke checks independently and summarize results.

Smoke checks exercise real commands and local artifacts. They are intentionally
separate from pytest unit tests because they may load model packages, touch
cache directories, and write workflow outputs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


TESTS_ROOT = Path(__file__).resolve().parent
TOOL_ROOT = TESTS_ROOT.parent
PROJECT_ROOT = TOOL_ROOT.parent


@dataclass(frozen=True)
class SmokeCheck:
    """One runnable smoke check command plus lightweight output validation."""

    name: str
    milestone: str
    group: str
    command: list[str]
    source: str
    output_jsonl: Path | None = None
    expected_dimension: int | None = None
    requires_package: str | None = None
    requires_path: Path | None = None
    default: bool = False


@dataclass(frozen=True)
class SmokeResult:
    """Result for one smoke command."""

    name: str
    milestone: str
    status: str
    exit_code: int | None
    duration_sec: float
    detail: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run registered Evaluation Tool smoke checks.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for smoke commands. Defaults to this interpreter.",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Run only one smoke check.",
    )
    parser.add_argument(
        "--group",
        choices=["default", "quick", "dataset", "model", "gui", "all"],
        default="default",
        help="Smoke group to run. Defaults to the short default set.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered smoke checks without running them.",
    )
    args = parser.parse_args()

    checks = smoke_checks(args.python)
    if args.list:
        print_registered_checks(checks)
        return 0
    if args.only is not None:
        checks = [check for check in checks if check.name == args.only]
        if not checks:
            print(f"Unknown smoke check: {args.only}", file=sys.stderr)
            return 2
    else:
        checks = select_group(checks, args.group)

    results = [run_smoke(check) for check in checks]
    print_summary(results)
    return 1 if any(result.status == "FAIL" for result in results) else 0


def smoke_checks(python: str) -> list[SmokeCheck]:
    """Return registered smoke checks."""

    return [
        SmokeCheck(
            name="m4-external-bridge-cli",
            milestone="M4",
            group="dataset",
            command=[
                python,
                "run_evaluation.py",
                "full",
                "--project-root",
                str(PROJECT_ROOT),
                "--dataset",
                "cmu_arctic",
                "--max-recordings",
                "1",
                "--runner",
                "external-stub",
                "--run-name",
                "m4_external_bridge_smoke_runner",
                "--runs-root",
                "m9_test/smoke/evaluation_runs",
            ],
            source="reports/milestones/M4_external_bridge_report.md",
            requires_path=PROJECT_ROOT / "RawDatasets",
        ),
        SmokeCheck(
            name="m5-vad-silero-cli",
            milestone="M5",
            group="dataset",
            command=[
                python,
                "run_evaluation.py",
                "full",
                "--project-root",
                str(PROJECT_ROOT),
                "--dataset",
                "cmu_arctic",
                "--max-recordings",
                "1",
                "--runner",
                "external-stub",
                "--run-name",
                "m5_vad_silero_smoke_runner",
                "--runs-root",
                "m9_test/smoke/evaluation_runs",
            ],
            source="reports/component_reports/vad/vad_comparison_m5_vad_silero_smoke_blocked.md",
            requires_path=PROJECT_ROOT / "RawDatasets",
        ),
        SmokeCheck(
            name="m6-segmentation-direct",
            milestone="M6",
            group="quick",
            command=[
                python,
                "-c",
                m6_segmentation_direct_code(),
            ],
            source="reports/component_reports/segmentation/segmentation_report_m6_segmentation_smoke.md",
            default=True,
        ),
        SmokeCheck(
            name="m6-segmentation-cli",
            milestone="M6",
            group="dataset",
            command=[
                python,
                "run_evaluation.py",
                "full",
                "--project-root",
                str(PROJECT_ROOT),
                "--dataset",
                "cmu_arctic",
                "--max-recordings",
                "1",
                "--runner",
                "external-stub",
                "--run-name",
                "m6_segmentation_smoke_runner",
                "--runs-root",
                "m9_test/smoke/evaluation_runs",
            ],
            source="reports/component_reports/segmentation/segmentation_report_m6_segmentation_smoke.md",
            requires_path=PROJECT_ROOT / "RawDatasets",
        ),
        SmokeCheck(
            name="m7-asr-fixed-direct",
            milestone="M7",
            group="quick",
            command=[
                python,
                "-c",
                m7_asr_fixed_direct_code(),
            ],
            source="reports/component_reports/asr/asr_model_report_m7_asr_smoke.md",
            default=True,
        ),
        SmokeCheck(
            name="m7-asr-cli",
            milestone="M7",
            group="dataset",
            command=[
                python,
                "run_evaluation.py",
                "full",
                "--project-root",
                str(PROJECT_ROOT),
                "--dataset",
                "cmu_arctic",
                "--max-recordings",
                "1",
                "--runner",
                "external-stub",
                "--augmentation",
                "none",
                "--run-name",
                "m7_asr_smoke_runner",
                "--runs-root",
                "m9_test/smoke/evaluation_runs",
            ],
            source="reports/component_reports/asr/asr_model_report_m7_asr_smoke.md",
            requires_path=PROJECT_ROOT / "RawDatasets",
        ),
        SmokeCheck(
            name="m8-asr-benchmark",
            milestone="M8",
            group="model",
            command=[
                python,
                "scripts/run_asr_benchmark.py",
                "--project-root",
                str(PROJECT_ROOT),
                "--dataset",
                "cmu_arctic",
                "--max-recordings",
                "1",
                "--run-id",
                "m8_asr_benchmark_smoke_runner",
                "--runs-root",
                "m9_test/smoke/asr_benchmarks",
            ],
            source="reports/milestones/M8_asr_benchmark_report.md",
            requires_path=PROJECT_ROOT / "RawDatasets",
        ),
        SmokeCheck(
            name="m8-whisper-direct",
            milestone="M8",
            group="model",
            command=[
                python,
                "-c",
                m8_whisper_direct_code(),
            ],
            source="reports/milestones/M8_asr_benchmark_report.md",
            requires_package="whisper",
            requires_path=PROJECT_ROOT / "RawDatasets/CMU Arctic/cmu_us_aew_arctic/wav/arctic_a0001.wav",
        ),
        SmokeCheck(
            name="m9-fake",
            milestone="M9",
            group="quick",
            command=[
                python,
                "scripts/embed_speaker_folder.py",
                "m9_test/audio",
                "--backend",
                "fake",
                "--output",
                "m9_test/smoke/fake_embeddings.jsonl",
                "--report",
                "m9_test/smoke/fake_report.md",
                "--labels-csv",
                "m9_test/labels.csv",
                "--dimension",
                "8",
                "--min-duration-sec",
                "0.1",
                "--run-id",
                "m9_fake_smoke_runner",
            ],
            source="m9_test/README.md",
            output_jsonl=Path("m9_test/smoke/fake_embeddings.jsonl"),
            expected_dimension=8,
            default=True,
        ),
        SmokeCheck(
            name="m9-speechbrain-cached",
            milestone="M9",
            group="model",
            command=[
                python,
                "scripts/embed_speaker_folder.py",
                "m9_test/audio",
                "--backend",
                "speechbrain",
                "--savedir",
                "models/cache/speechbrain/spkrec-ecapa-voxceleb",
                "--output",
                "m9_test/smoke/speechbrain_cached_embeddings.jsonl",
                "--report",
                "m9_test/smoke/speechbrain_cached_report.md",
                "--labels-csv",
                "m9_test/labels.csv",
                "--min-duration-sec",
                "0.1",
                "--run-id",
                "m9_speechbrain_cached_smoke_runner",
            ],
            source="m9_test/README.md",
            output_jsonl=Path("m9_test/smoke/speechbrain_cached_embeddings.jsonl"),
            expected_dimension=192,
            requires_package="speechbrain",
            requires_path=Path("models/cache/speechbrain/spkrec-ecapa-voxceleb"),
            default=True,
        ),
        SmokeCheck(
            name="m11-speaker-matching-calibration-direct",
            milestone="M11",
            group="quick",
            command=[
                python,
                "-c",
                m11_speaker_matching_direct_code(),
            ],
            source="reports/component_reports/speaker_matching/threshold_calibration_m11_speaker_matching.md",
            default=True,
        ),
        SmokeCheck(
            name="gui-validation-harness",
            milestone="GUI",
            group="gui",
            command=[
                python,
                "-m",
                "app.gui.validation_harness",
                "--run-smoke",
            ],
            source="app/gui/validation_harness.py",
            requires_path=PROJECT_ROOT / "RawDatasets",
        ),
    ]


def select_group(checks: list[SmokeCheck], group: str) -> list[SmokeCheck]:
    """Select a runnable smoke subset."""

    if group == "all":
        return checks
    if group == "default":
        return [check for check in checks if check.default]
    return [check for check in checks if check.group == group]


def print_registered_checks(checks: list[SmokeCheck]) -> None:
    """Print registered smoke checks and where they were copied from."""

    name_width = max(len("Smoke"), *(len(check.name) for check in checks))
    milestone_width = max(len("Milestone"), *(len(check.milestone) for check in checks))
    group_width = max(len("Group"), *(len(check.group) for check in checks))
    print(
        f"{'Smoke':<{name_width}}  "
        f"{'Milestone':<{milestone_width}}  "
        f"{'Group':<{group_width}}  "
        "Default  Source",
        flush=True,
    )
    print(
        f"{'-' * name_width}  "
        f"{'-' * milestone_width}  "
        f"{'-' * group_width}  "
        "-------  ------",
        flush=True,
    )
    for check in checks:
        default = "yes" if check.default else "no"
        print(
            f"{check.name:<{name_width}}  "
            f"{check.milestone:<{milestone_width}}  "
            f"{check.group:<{group_width}}  "
            f"{default:<7}  "
            f"{check.source}",
            flush=True,
        )


def m6_segmentation_direct_code() -> str:
    """Return the copied M6 direct synthetic segmentation smoke."""

    return (
        "from pathlib import Path; "
        "from app.inference_pipeline.contracts import EvaluationRecord, SpeechRegion; "
        "from app.inference_pipeline.segmentation.vad_chunker import VADChunker; "
        "from app.inference_pipeline.segmentation.base import trace_segments; "
        "from app.inference_pipeline.segmentation.report import summarize_segments; "
        "record=EvaluationRecord(recording_id='smoke-rec', utt_id='smoke-utt', "
        "inference_audio_path=Path('synthetic.wav'), start_sec=0.0, end_sec=6.0, "
        "duration_sec=6.0); "
        "regions=[SpeechRegion(0.2,1.0), SpeechRegion(1.1,1.8), SpeechRegion(3.0,5.8)]; "
        "segmenter=VADChunker({'min_chunk_sec':0.2,'max_chunk_sec':2.0,"
        "'merge_gap_sec':0.2,'left_pad_sec':0.1,'right_pad_sec':0.1,"
        "'clip_to_record_bounds':True}); "
        "segments=segmenter.segment(record, regions); "
        "traces=trace_segments(record, segments); "
        "metrics=summarize_segments(segments, audio_duration_sec=6.0); "
        "assert len(segments) == 3; "
        "print([segment.to_jsonable() for segment in segments]); "
        "print([trace.to_jsonable() for trace in traces]); "
        "print(metrics)"
    )


def m7_asr_fixed_direct_code() -> str:
    """Return the copied M7 direct external-runner ASR smoke."""

    return (
        "import json, logging; "
        "from dataclasses import asdict; "
        "from pathlib import Path; "
        "from app.inference_pipeline.asr.base import FixedASR; "
        "from app.inference_pipeline.dummy_components import DummyAudioReader, DummySpeakerLabeler; "
        "from app.inference_pipeline.pipeline import PipelineRunner; "
        "from app.model_runner.external_stub import ExternalStubRunner; "
        "run_dir=Path('m9_test/smoke/m7_asr_runner_smoke'); "
        "predictions_dir=run_dir/'predictions'; "
        "record={'recording_id':'m7-rec','utt_id':'m7-utt','audio_path_resolved':'synthetic.wav',"
        "'inference_audio_path':'synthetic.wav','start_sec':0.0,'end_sec':1.0}; "
        f"run_config={{'project_root':{str(PROJECT_ROOT)!r},'run_dir':str(run_dir),"
        "'augmentation':{'mode':'none','conditions':[{'condition_id':'clean','mode':'none'}]}}; "
        "pipeline=PipelineRunner(audio_reader=DummyAudioReader(), "
        "asr=FixedASR('M7 adapter transcript'), speaker_labeler=DummySpeakerLabeler()); "
        "result=ExternalStubRunner(pipeline).run_batch([record], predictions_dir, run_config, "
        "logging.getLogger('m7_smoke')); "
        "stats=pipeline.asr.last_runtime_stats; "
        "result_dict=asdict(result); "
        "result_dict['predictions_path']=str(result_dict['predictions_path']); "
        "rows=(predictions_dir/'utterances.jsonl').read_text().splitlines(); "
        "assert rows; "
        "print(json.dumps({'result': result_dict, 'runtime_stats': stats.to_jsonable(), "
        "'jsonl': rows}, indent=2))"
    )


def m8_whisper_direct_code() -> str:
    """Return the copied M8 direct Whisper adapter smoke."""

    audio_path = PROJECT_ROOT / "RawDatasets/CMU Arctic/cmu_us_aew_arctic/wav/arctic_a0001.wav"
    return (
        "import json, logging; "
        "from dataclasses import asdict; "
        "from pathlib import Path; "
        "from app.inference_pipeline.asr.whisper_adapter import WhisperASR; "
        "from app.inference_pipeline.dummy_components import DummyAudioReader, DummySpeakerLabeler; "
        "from app.inference_pipeline.pipeline import PipelineRunner; "
        "from app.model_runner.external_stub import ExternalStubRunner; "
        f"project=Path({str(PROJECT_ROOT)!r}); "
        f"audio=Path({str(audio_path)!r}); "
        "run_dir=Path('m9_test/smoke/m8_whisper_direct_smoke'); "
        "record={'recording_id':'CMU_ARCTIC_aew_arctic_a0001','utt_id':'arctic_a0001',"
        "'audio_path_resolved':str(audio),'inference_audio_path':str(audio),"
        "'start_sec':0.0,'end_sec':3.880063,"
        "'reference_text':'author of the danger trail philip steels etc'}; "
        "run_config={'project_root':str(project),'run_dir':str(run_dir),"
        "'augmentation':{'mode':'none','conditions':[{'condition_id':'clean','mode':'none'}]}}; "
        "asr=WhisperASR({'model_size':'tiny','model_name':'whisper_tiny','language':'en',"
        "'device':'cpu','dtype':'float32','cache_dir':'models/cache/whisper',"
        "'allow_model_downloads':False}); "
        "pipeline=PipelineRunner(audio_reader=DummyAudioReader(), asr=asr, "
        "speaker_labeler=DummySpeakerLabeler()); "
        "result=ExternalStubRunner(pipeline).run_batch([record], run_dir/'predictions', "
        "run_config, logging.getLogger('m8_whisper_direct')); "
        "result_dict=asdict(result); "
        "result_dict['predictions_path']=str(result_dict['predictions_path']); "
        "rows=(run_dir/'predictions/utterances.jsonl').read_text().splitlines(); "
        "assert rows; "
        "print(json.dumps({'result':result_dict,'runtime':asr.last_runtime_stats.to_jsonable() "
        "if asr.last_runtime_stats else None,'predictions':rows}, indent=2))"
    )


def m11_speaker_matching_direct_code() -> str:
    """Return the M11 synthetic speaker matching calibration smoke."""

    return (
        "from pathlib import Path; "
        "from app.inference_pipeline.enrollment import EnrollmentDatabase, add_enrollment_exemplar; "
        "from app.inference_pipeline.speaker_matching import CosineThresholdSpeakerMatcher; "
        "from app.inference_pipeline.speaker_matching.thresholds import CalibrationSample, "
        "calibrate_thresholds, write_threshold_calibration_report; "
        "model='speaker-embedder@1'; "
        "db=EnrollmentDatabase.empty(created_at='2026-05-28T00:00:00Z'); "
        "db,_=add_enrollment_exemplar(db, display_name='Alice', "
        "prompt_id='clean_enrollment_v1', audio_path=Path('alice.wav'), "
        "embedding=(1.0,0.0,0.0), model_id=model, "
        "created_at='2026-05-28T00:00:01Z', duration_sec=1.0, "
        "validate_audio_path=False); "
        "db,_=add_enrollment_exemplar(db, display_name='Bob', "
        "prompt_id='clean_enrollment_v1', audio_path=Path('bob.wav'), "
        "embedding=(0.0,1.0,0.0), model_id=model, "
        "created_at='2026-05-28T00:00:02Z', duration_sec=1.0, "
        "validate_audio_path=False); "
        "matcher=CosineThresholdSpeakerMatcher(threshold=0.95, min_margin=0.05, "
        "runtime_model_id=model); "
        "known=matcher.match({'embedding_id':'alice-q','vector':[0.99,0.01,0.0],"
        "'model_id':model}, db); "
        "unknown=matcher.match({'embedding_id':'unknown-q','vector':[0.6,0.8,0.0],"
        "'model_id':model}, db); "
        "assert known.speaker_label == 'Alice'; "
        "assert unknown.speaker_label == 'Unknown'; "
        "samples=(CalibrationSample('alice-q','Alice',(0.99,0.01,0.0),model), "
        "CalibrationSample('bob-q','Bob',(0.01,0.99,0.0),model), "
        "CalibrationSample('unknown-near-bob','Mallory',(0.60,0.80,0.0),model)); "
        "result=calibrate_thresholds(samples, db, run_id='m11_smoke', "
        "thresholds=(0.5,0.8,0.95), min_margin=0.05, runtime_model_id=model); "
        "assert result.recommended_threshold == 0.95; "
        "report=Path('/private/tmp/m11_speaker_matching_smoke/threshold_calibration_m11_smoke.md'); "
        "write_threshold_calibration_report(report, result, "
        "files_changed=['app/inference_pipeline/speaker_matching'], "
        "test_commands=[], smoke_commands=[], "
        "runner_contract='Synthetic smoke does not touch the runner contract.'); "
        "assert report.is_file(); "
        "print({'known': known.to_jsonable(), 'unknown': unknown.to_jsonable(), "
        "'recommended_threshold': result.recommended_threshold, 'report': str(report)})"
    )


def run_smoke(check: SmokeCheck) -> SmokeResult:
    """Run one smoke check and return a pass, fail, or skip result."""

    print(f"\n== Running {check.name} [{check.milestone}] ==", flush=True)
    skip_reason = skip_reason_for(check)
    if skip_reason is not None:
        print(f"SKIP: {skip_reason}", flush=True)
        return SmokeResult(
            name=check.name,
            milestone=check.milestone,
            status="SKIP",
            exit_code=None,
            duration_sec=0.0,
            detail=skip_reason,
        )

    started_at = time.perf_counter()
    try:
        completed = subprocess.run(check.command, cwd=TOOL_ROOT, check=False)
        exit_code = completed.returncode
    except Exception as exc:  # pragma: no cover - defensive command boundary
        return SmokeResult(
            name=check.name,
            milestone=check.milestone,
            status="FAIL",
            exit_code=1,
            duration_sec=round(time.perf_counter() - started_at, 2),
            detail=str(exc),
        )
    duration_sec = round(time.perf_counter() - started_at, 2)
    if exit_code != 0:
        return SmokeResult(
            name=check.name,
            milestone=check.milestone,
            status="FAIL",
            exit_code=exit_code,
            duration_sec=duration_sec,
            detail="command exited non-zero",
        )

    validation_error = validate_output(check)
    if validation_error is not None:
        return SmokeResult(
            name=check.name,
            milestone=check.milestone,
            status="FAIL",
            exit_code=exit_code,
            duration_sec=duration_sec,
            detail=validation_error,
        )
    return SmokeResult(
        name=check.name,
        milestone=check.milestone,
        status="PASS",
        exit_code=exit_code,
        duration_sec=duration_sec,
        detail="ok",
    )


def skip_reason_for(check: SmokeCheck) -> str | None:
    if check.requires_package is not None and importlib.util.find_spec(check.requires_package) is None:
        return f"missing python package {check.requires_package!r}"
    if check.requires_path is not None and not (TOOL_ROOT / check.requires_path).exists():
        return f"missing required path {check.requires_path}"
    return None


def validate_output(check: SmokeCheck) -> str | None:
    if check.output_jsonl is None:
        return None
    output_path = TOOL_ROOT / check.output_jsonl
    if not output_path.is_file():
        return f"missing output JSONL {check.output_jsonl}"
    rows = read_jsonl(output_path)
    if not rows:
        return f"output JSONL {check.output_jsonl} has no rows"
    successful = [row for row in rows if row.get("status") == "ok"]
    if not successful:
        return f"output JSONL {check.output_jsonl} has no successful rows"
    if check.expected_dimension is not None:
        dimensions = {row.get("dimension") for row in successful}
        if dimensions != {check.expected_dimension}:
            return (
                f"expected dimension {check.expected_dimension}, "
                f"got {sorted(str(value) for value in dimensions)}"
            )
    return None


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"expected JSON object on {path}:{line_number}")
            rows.append(value)
    return rows


def print_summary(results: list[SmokeResult]) -> None:
    """Print a compact pass/fail/skip table."""

    print("\n== Smoke Summary ==", flush=True)
    if not results:
        print("No smoke checks selected.", flush=True)
        return

    name_width = max(len("Smoke"), *(len(result.name) for result in results))
    milestone_width = max(len("Milestone"), *(len(result.milestone) for result in results))
    print(
        f"{'Smoke':<{name_width}}  "
        f"{'Milestone':<{milestone_width}}  "
        "Status  Exit  Seconds  Detail",
        flush=True,
    )
    print(
        f"{'-' * name_width}  "
        f"{'-' * milestone_width}  "
        "------  ----  -------  ------",
        flush=True,
    )
    for result in results:
        exit_text = "n/a" if result.exit_code is None else str(result.exit_code)
        print(
            f"{result.name:<{name_width}}  "
            f"{result.milestone:<{milestone_width}}  "
            f"{result.status:<6}  "
            f"{exit_text:<4}  "
            f"{result.duration_sec:>7.2f}  "
            f"{result.detail}",
            flush=True,
        )

    failures = [result for result in results if result.status == "FAIL"]
    skipped = [result for result in results if result.status == "SKIP"]
    if failures:
        print(f"\n{len(failures)} smoke check(s) failed.", flush=True)
    elif skipped:
        print(f"\nSmoke checks passed with {len(skipped)} skipped.", flush=True)
    else:
        print("\nAll smoke checks passed.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
