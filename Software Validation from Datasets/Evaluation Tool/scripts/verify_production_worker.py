"""Run one real ordinary-evaluator smoke for an explicit CPU or CUDA worker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import sys


TOOL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.campaign_exchange.common import atomic_write_json  # noqa: E402
from scripts.run_cuda_qualification import _run_case  # noqa: E402


class WorkerVerificationError(RuntimeError):
    """Raised when the real evaluator does not use the explicitly selected mode."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--machine-id", choices=("machine_a", "machine_b"), required=True
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=TOOL_ROOT / "artifacts" / "production_verification",
    )
    return parser


def verify_worker(
    *, machine_id: str, device: str, output_root: Path
) -> dict[str, object]:
    root = output_root.resolve() / machine_id / device
    root.mkdir(parents=True, exist_ok=True)
    config = TOOL_ROOT / "configs" / "inference" / (
        "whisper_base_cuda_float32.yaml"
        if device == "cuda"
        else "live_mic_whisper_base.yaml"
    )
    result = _run_case(
        name=f"{machine_id}_{device}_float32",
        python=Path(sys.executable),
        config=config,
        gpu_index="0" if device == "cuda" else None,
        max_recordings=1,
        output_root=root,
        interval_sec=0.25,
    )
    observed_device = str(result.get("device") or "").lower()
    observed_dtype = str(result.get("dtype") or "").lower()
    if device == "cuda":
        if not observed_device.startswith("cuda"):
            raise WorkerVerificationError(
                f"CUDA was requested but evaluator reported {observed_device!r}"
            )
        if float(result.get("peak_allocated_vram_mb") or 0.0) <= 0.0:
            raise WorkerVerificationError(
                "CUDA evaluator produced no nonzero allocated-VRAM evidence"
            )
    elif observed_device != "cpu":
        raise WorkerVerificationError(
            f"CPU was requested but evaluator reported {observed_device!r}"
        )
    if observed_dtype != "float32":
        raise WorkerVerificationError(
            f"production dtype changed: expected float32, observed {observed_dtype!r}"
        )
    if int(result.get("prediction_count") or 0) != 1 or int(
        result.get("failure_count") or 0
    ):
        raise WorkerVerificationError("ordinary evaluator smoke did not produce one success")
    run_dir = Path(str(result["run_dir"]))
    for relative in (
        "predictions/utterances.jsonl",
        "metrics/aggregate_metrics.json",
        "report/report.md",
    ):
        if not (run_dir / relative).is_file():
            raise WorkerVerificationError(
                f"ordinary evaluator output is missing: {run_dir / relative}"
            )
    report = {
        "schema_version": "production-worker-verification.v1",
        "machine_id": machine_id,
        "host": socket.gethostname(),
        "requested_device": device,
        "observed_device": result["device"],
        "observed_dtype": result["dtype"],
        "python": sys.executable,
        "prediction_count": result["prediction_count"],
        "failure_count": result["failure_count"],
        "wer": result["wer"],
        "cer": result["cer"],
        "total_elapsed_sec": result["total_elapsed_sec"],
        "asr_inference_sec": result["asr_inference_sec"],
        "peak_allocated_vram_mb": result["peak_allocated_vram_mb"],
        "peak_reserved_vram_mb": result["peak_reserved_vram_mb"],
        "run_dir": str(run_dir),
        "passed": True,
    }
    atomic_write_json(root / "worker_verification.json", report)
    return report


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = verify_worker(
            machine_id=args.machine_id,
            device=args.device,
            output_root=args.output_root,
        )
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"worker verification failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
