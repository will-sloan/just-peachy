"""Audit large queued captures using memory proportional to successful samples.

Each retry transaction is parsed and discarded immediately. No hardware access.
"""
import argparse
import base64
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct

NAMES = ("AEC_AZIMUTH_VALUES", "AEC_SPENERGY_VALUES")


def lines(path):
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            yield json.loads(line)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def percentile(values, percent):
    if not values:
        return None
    v = sorted(values)
    at = (len(v) - 1) * percent / 100
    a, b = math.floor(at), math.ceil(at)
    return v[a] + (v[b] - v[a]) * (at - a)


def audit(directory):
    directory = Path(directory)
    result = json.loads((directory / "result.json").read_text(encoding="utf-8-sig"))
    meta = json.loads((directory / "command_map_inspection.json").read_text(encoding="utf-8-sig"))
    freq = meta["stopwatch_frequency"]
    errors = []
    error_count = 0
    def check(condition, message):
        nonlocal error_count
        if not condition:
            error_count += 1
            if len(errors) < 100:
                errors.append(message)
    samples = iter(lines(directory / "samples.jsonl"))
    groups = {}
    transfers = retries = sample_count = warmup = max_pending = 0
    cycles = defaultdict(list)
    completion = defaultdict(list)
    field = {n: dict(times=[], durations=[], retries=[], distinct=set(), finite=0, nonfinite=0,
                     minimum=[None]*4, maximum=[None]*4) for n in NAMES}
    previous_end = None
    for row in lines(directory / "transactions.jsonl"):
        seq = transfers
        transfers += 1
        check(row["sequence"] == seq, f"Transfer sequence mismatch {seq}")
        check(row["transport_return"] == 0, f"Transport error {seq}")
        check(row["device_status"] in (0, 64), f"Device error {seq}")
        begin, end = row["request_start_qpc_ticks"], row["request_end_qpc_ticks"]
        check(end >= begin, f"Negative duration {seq}")
        check(previous_end is None or begin >= previous_end, f"Overlapping serialized calls {seq}")
        previous_end = end
        raw = base64.b64decode(row["raw_response_base64"], validate=True)
        check(len(raw) == 17, f"Invalid response length {seq}")
        if len(raw) == 17 and row["transport_return"] == 0:
            check(raw[0] == row["device_status"], f"Raw/status mismatch {seq}")
        for prefix in ("request_start", "request_end"):
            ticks = row[prefix + "_qpc_ticks"]
            ns = ticks // freq * 1_000_000_000 + ticks % freq * 1_000_000_000 // freq
            check(ns == row[prefix + "_monotonic_ns"], f"QPC conversion mismatch {seq}")
        retries += row["device_status"] == 64
        key = (row["phase"], row["cycle"], row["command"])
        if row["phase"] == "cleanup":
            if row["device_status"] == 0:
                groups.pop(("measurement", row["cycle"], row["command"]), None)
            continue
        group = groups.setdefault(key, dict(attempts=0, first_status=row["device_status"], start=row["request_start_monotonic_ns"]))
        group["attempts"] += 1
        check(row["attempt"] == group["attempts"], f"Attempt sequence mismatch {key}")
        max_pending = max(max_pending, len(groups))
        if row["device_status"] != 0:
            continue
        sample = next(samples, None)
        if sample is None:
            check(False, f"Success without sample {key}")
            del groups[key]
            continue
        check(sample["sequence"] == sample_count, f"Sample sequence mismatch {sample_count}")
        sample_count += 1
        check((sample["phase"], sample["cycle"], sample["command"]) == key, f"Transfer/sample order mismatch {key}")
        check(sample["attempts"] == group["attempts"], f"Sample attempt count mismatch {key}")
        check(sample["raw_response_base64"] == row["raw_response_base64"], f"Sample bytes mismatch {key}")
        check(sample["response_end_monotonic_ns"] == row["request_end_monotonic_ns"], f"Sample timestamp mismatch {key}")
        check(sample["logical_request_start_monotonic_ns"] <= group["start"], f"Logical start after first transfer {key}")
        values = struct.unpack("<4f", raw[1:]) if len(raw) == 17 else [float("nan")] * 4
        for i, value in enumerate(values):
            finite = math.isfinite(value)
            check(sample["finite"][i] == finite, f"Finite mask mismatch {key}/{i}")
            check(sample["values"][i] == value if finite else sample["values"][i] is None, f"Float32 mismatch {key}/{i}")
        if sample["phase"] == "measurement":
            check(group["first_status"] == 64, f"New request was not enqueued {key}")
            stamp = sample["response_end_monotonic_ns"]
            cycles[sample["cycle"]].append(sample["command"])
            completion[sample["cycle"]].append(stamp)
            stats = field[sample["command"]]
            stats["times"].append(stamp)
            stats["durations"].append((stamp - sample["logical_request_start_monotonic_ns"]) / 1e9)
            stats["retries"].append(sample["attempts"] - 1)
            stats["distinct"].add(tuple(sample["values"]))
            for i, value in enumerate(values):
                if math.isfinite(value):
                    stats["finite"] += 1
                    stats["minimum"][i] = value if stats["minimum"][i] is None else min(stats["minimum"][i], value)
                    stats["maximum"][i] = value if stats["maximum"][i] is None else max(stats["maximum"][i], value)
                else:
                    stats["nonfinite"] += 1
        elif sample["phase"] == "warmup":
            warmup += 1
        del groups[key]
    check(next(samples, None) is None, "Extra sample without successful transfer")
    check(not groups, "Incomplete transfer groups")
    check(transfers == result["transactions"], "Result transfer count mismatch")
    check(retries == result["retry_responses"], "Result retry count mismatch")
    check(set(cycles) == set(range(result["completed_cycles"])), "Cycle sequence incomplete")
    for cycle, names in cycles.items():
        check(sorted(names) == sorted(NAMES), f"Incomplete/duplicate pair {cycle}")
    skews = [abs(v[0] - v[1]) / 1e9 for v in completion.values() if len(v) == 2]
    per_field = {}
    for name, stats in field.items():
        times = stats["times"]
        gaps = [(b - a) / 1e9 for a, b in zip(times, times[1:])]
        durations = stats["durations"]
        per_field[name] = {
            "count": len(times), "first_response_end_monotonic_ns": times[0] if times else None,
            "last_response_end_monotonic_ns": times[-1] if times else None,
            "mean_response_rate_hz": (len(times)-1)*1e9/(times[-1]-times[0]) if len(times)>1 else None,
            "interval_median_s": statistics.median(gaps) if gaps else None,
            "interval_p95_s": percentile(gaps,95), "interval_max_s": max(gaps) if gaps else None,
            "request_duration_median_s": statistics.median(durations) if durations else None,
            "request_duration_max_s": max(durations) if durations else None,
            "retries_median": statistics.median(stats["retries"]) if stats["retries"] else None,
            "distinct_float32_arrays": len(stats["distinct"]), "finite_values": stats["finite"],
            "nonfinite_values": stats["nonfinite"], "minimum_per_beam": stats["minimum"], "maximum_per_beam": stats["maximum"],
        }
        check(len(times) == result["per_field"][name]["count"], f"Result field count mismatch {name}")
    check(result["cleanup_return"] == 0 and not any(result["pending_reads_at_exit"]), "Cleanup incomplete")
    return dict(status="PASS" if not error_count and result["status"]=="PASS" else "FAIL", capture=str(directory.resolve()),
                mode=result["mode"], errors=errors, error_count=error_count, checked_transfers=transfers,
                checked_samples=sample_count, warmup_samples_excluded=warmup, max_pending_transfer_groups=max_pending,
                measurement_cycles=len(cycles), per_field=per_field, streaming_audit=True,
                paired_host_completion_skew_median_s=statistics.median(skews) if skews else None,
                paired_host_completion_skew_max_s=max(skews) if skews else None,
                timing_limitation="Host transaction timing and complete pairs do not prove device-frame freshness or atomic same-frame pairs.",
                source_hashes={name:digest(directory/name) for name in ("transactions.jsonl","samples.jsonl","result.json","command_map_inspection.json")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    result = audit(args.capture)
    with args.output.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps(result,indent=2,allow_nan=False))
    raise SystemExit(result["status"] != "PASS")
