"""Independently verify a completed queued-telemetry capture; no device access."""
from __future__ import annotations
import argparse
from collections import defaultdict
import base64
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct


def audit(directory: Path) -> dict:
    result = json.loads((directory / "result.json").read_text(encoding="utf-8-sig"))
    metadata = json.loads((directory / "command_map_inspection.json").read_text(encoding="utf-8-sig"))
    frequency = metadata["stopwatch_frequency"]
    transactions = [json.loads(v) for v in (directory / "transactions.jsonl").read_text(encoding="utf-8-sig").splitlines()]
    samples = [json.loads(v) for v in (directory / "samples.jsonl").read_text(encoding="utf-8-sig").splitlines()]
    errors = []
    def check(condition, message):
        if not condition:
            errors.append(message)
    groups = defaultdict(list)
    for expected, row in enumerate(transactions):
        check(row["sequence"] == expected, f"Transfer sequence mismatch at {expected}")
        check(row["transport_return"] == 0, f"Transport error at {expected}")
        check(row["device_status"] in (0, 64), f"Device error at {expected}")
        check(row["request_end_qpc_ticks"] >= row["request_start_qpc_ticks"], f"Negative transfer duration at {expected}")
        raw = base64.b64decode(row["raw_response_base64"], validate=True)
        check(len(raw) == 17, f"Invalid response length at {expected}")
        check(raw[0] == row["device_status"], f"Status/raw-byte mismatch at {expected}")
        for key in ("request_start", "request_end"):
            ticks = row[key + "_qpc_ticks"]
            ns = (ticks // frequency) * 1_000_000_000 + (ticks % frequency) * 1_000_000_000 // frequency
            check(ns == row[key + "_monotonic_ns"], f"QPC conversion mismatch at {expected}")
        groups[(row["phase"], row["cycle"], row["command"])].append(row)
    measurement = []
    seen_groups = set()
    for expected, sample in enumerate(samples):
        check(sample["sequence"] == expected, f"Sample sequence mismatch at {expected}")
        key = (sample["phase"], sample["cycle"], sample["command"])
        check(key not in seen_groups, f"Duplicate sample group {key}")
        seen_groups.add(key)
        group = groups[key]
        if not group:
            errors.append(f"Sample without transfers {key}")
            continue
        final = group[-1]
        check(final["device_status"] == 0, f"Sample did not end in success {key}")
        check(all(row["device_status"] == 64 for row in group[:-1]), f"Unexpected intermediate status {key}")
        check([row["attempt"] for row in group] == list(range(1, len(group) + 1)), f"Attempt sequence mismatch {key}")
        check(sample["attempts"] == len(group), f"Sample attempt count mismatch {key}")
        check(sample["raw_response_base64"] == final["raw_response_base64"], f"Sample byte mismatch {key}")
        check(sample["response_end_monotonic_ns"] == final["request_end_monotonic_ns"], f"Sample timestamp mismatch {key}")
        raw_values = struct.unpack("<4f", base64.b64decode(sample["raw_response_base64"])[1:])
        for i, value in enumerate(raw_values):
            finite = math.isfinite(value)
            check(sample["finite"][i] == finite, f"Finite mask mismatch {key}/{i}")
            check(sample["values"][i] == value if finite else sample["values"][i] is None,
                  f"Float32 decoding mismatch {key}/{i}")
        if sample["phase"] == "measurement":
            measurement.append(sample)
            check(group[0]["device_status"] == 64, f"New measurement request was not enqueued {key}")
    expected_names = ("AEC_AZIMUTH_VALUES", "AEC_SPENERGY_VALUES")
    check(len(transactions) == result["transactions"], "Result transfer count mismatch")
    check(sum(row["device_status"] == 64 for row in transactions) == result["retry_responses"], "Result retry count mismatch")
    cycles = defaultdict(list)
    for row in measurement:
        cycles[row["cycle"]].append(row["command"])
    check(set(cycles) == set(range(result["completed_cycles"])), "Cycle sequence incomplete")
    for cycle, fields in cycles.items():
        check(sorted(fields) == sorted(expected_names), f"Incomplete/duplicate pair in cycle {cycle}")
    by_cycle = defaultdict(list)
    for row in measurement:
        by_cycle[row["cycle"]].append(row)
    completion_skews = []
    for rows in by_cycle.values():
        if len(rows) == 2:
            completion_skews.append(abs(rows[0]["response_end_monotonic_ns"] - rows[1]["response_end_monotonic_ns"]) / 1e9)
    statistics_out = {}
    for name in expected_names:
        field_rows = [row for row in measurement if row["command"] == name]
        times = [row["response_end_monotonic_ns"] for row in field_rows]
        gaps = [(b - a) / 1e9 for a, b in zip(times, times[1:])]
        requests = [(row["response_end_monotonic_ns"] - row["logical_request_start_monotonic_ns"]) / 1e9 for row in field_rows]
        statistics_out[name] = {
            "count": len(times),
            "mean_response_rate_hz": (len(times) - 1) * 1e9 / (times[-1] - times[0]) if len(times) > 1 else None,
            "interval_median_s": statistics.median(gaps) if gaps else None,
            "interval_max_s": max(gaps) if gaps else None,
            "request_duration_median_s": statistics.median(requests) if requests else None,
            "request_duration_max_s": max(requests) if requests else None,
            "retries_median": statistics.median(row["attempts"] - 1 for row in field_rows) if field_rows else None,
            "distinct_float32_arrays": len({tuple(row["values"]) for row in field_rows}),
        }
        check(len(times) == result["per_field"][name]["count"], f"Result field count mismatch {name}")
    check(result["cleanup_return"] == 0 and not any(result["pending_reads_at_exit"]), "Cleanup did not complete")
    return {
        "status": "PASS" if not errors and result["status"] == "PASS" else "FAIL",
        "capture": str(directory.resolve()), "mode": result["mode"], "errors": errors,
        "checked_transfers": len(transactions), "checked_samples": len(samples),
        "measurement_cycles": len(cycles), "per_field": statistics_out,
        "paired_host_completion_skew_median_s": statistics.median(completion_skews) if completion_skews else None,
        "paired_host_completion_skew_max_s": max(completion_skews) if completion_skews else None,
        "timing_limitation": "Host transaction timing and pair completeness do not prove device frame freshness or atomic same-frame pairs.",
        "source_hashes": {name: hashlib.sha256((directory/name).read_bytes()).hexdigest()
                          for name in ("transactions.jsonl", "samples.jsonl", "result.json", "command_map_inspection.json")},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.capture)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps(result, indent=2, allow_nan=False))
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
