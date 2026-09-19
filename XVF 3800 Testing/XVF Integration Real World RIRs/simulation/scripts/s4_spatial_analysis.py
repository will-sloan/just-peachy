"""Offline S4 spatial scoring; no USB/audio handles, no future telemetry. README_S4_SPATIAL.md."""
from __future__ import annotations
import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path
import statistics
import unittest
from unittest.mock import patch
from s4_geometry import angle_error, coarse_sector, source_label
from s4_telemetry import normalize_observation, TIMING_TELEMETRY_POLICY

S4_SPATIAL_POLICY = {
    "schema_version": "jp_s4_spatial_metrics_v2",
    "frozen_before_physical_output_inspection": True,
    "definition_authority": "Root S4 instruction before physical regression: 80 percent over one second",
    "supersedes": "Non-operative 0.5-second contiguous direction_metrics placeholder in telemetry helper",
    "coarse_sectors": {"right": "[0,60)", "central_ambiguous": "[60,120]", "left": "(120,180]"},
    "max_receipt_age_s": 0.25,
    "max_transaction_duration_s": 0.25,
    "max_response_to_receipt_s": 0.25,
    "sustained_window_s": 1.0,
    "sustained_minimum_occupancy": 0.8,
    "sustained_max_receipt_gap_s": 0.25,
    "sustained_decision_candidates": "Actual valid matching-sector angle receipt times, after at least one full second of the scored envelope",
    "first_hit": "First causal matching sector in envelope; pre-existing match at onset is separately flagged",
    "coverage": "Duration of usable direction, separately angle-only and speech-energy-gated, over quantized estimated activity support",
    "raw_beam_energy_gate": "Latest causal same-index AEC_SPENERGY_VALUES > 0 and fresh; fields are not atomic",
    "selected_processed_gate": "Finite selected value 0; documented NaN means no fixed-beam speech",
    "selected_auto_gate": "Finite selected value 1 plus latest causal raw-auto energy > 0",
    "off_delay": "From final estimated active-support availability to first unavailable/no-speech/wrong sector; censor at next speech or capture end",
    "primary_timing": "Recaptured source alignment + retained 50 ms RIR convention + estimated source activity, mapped to copy-complete callback availability",
    "processed_timing": "Optional separately reported views using externally measured output vs MIC0 delay, never fitted to angle or source schedule",
    "activity_mapping": "Each callback containing estimated active samples is scored from its copy completion to the next callback copy completion; terminal span uses its native sample duration",
    "activity_mapping_limit": "Coarse callback availability support, not exact phonetic timing; short activity ranges may expand to one callback block",
    "no_future_interpolation": True,
    "fitted_angle_or_energy_shift": False,
    "internal_dsp_observation_time": "unknown_not_exposed",
    "manual_five_degrees_is_device_tolerance": False,
    "overlap": "Retain per-source diagnostics with LIMITED_MULTISPEAKER_TRUTH; one selected angle cannot uniquely represent simultaneous source truth",
    "never_acquired": "Keep null acquisition and censored true",
}

FIELDS = ("AEC_AZIMUTH_VALUES", "AEC_SPENERGY_VALUES", "AUDIO_MGR_SELECTED_AZIMUTHS")
STREAMS = {
    "selected_processed": (FIELDS[2], 0, None),
    "selected_auto": (FIELDS[2], 1, 3),
    "raw_auto": (FIELDS[0], 3, 3),
    "focused_1": (FIELDS[0], 0, 0),
    "focused_2": (FIELDS[0], 1, 1),
    "scanning": (FIELDS[0], 2, 2),
}
AGE_NS = 250_000_000


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    p = Path(path)
    return {"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}


def union(ranges):
    result = []
    for a, b in sorted(ranges):
        if b <= a:
            continue
        if result and a <= result[-1][1]:
            result[-1][1] = max(b, result[-1][1])
        else:
            result.append([a, b])
    return result


def duration(ranges):
    return sum(b - a for a, b in union(ranges)) / 1e9


def intersect(ranges, a, b):
    return union([[max(a, x), min(b, y)] for x, y in ranges if x < b and y > a])


class ReceiptTimeline:
    """Last-received only. Value and energy freshness are independently checked."""
    def __init__(self, rows):
        normalized = [normalize_observation(row) for row in rows]
        self.fields = {name: sorted([r for r in normalized if r["command"] == name and isinstance(r["available_monotonic_ns"], int)],
                                   key=lambda r: r["available_monotonic_ns"]) for name in FIELDS}
        self.stamps = {name: [r["available_monotonic_ns"] for r in self.fields[name]] for name in FIELDS}

    def latest(self, field, when):
        i = bisect.bisect_right(self.stamps[field], when) - 1
        if i < 0:
            return None, False
        row = self.fields[field][i]
        return row, when - row["available_monotonic_ns"] <= AGE_NS

    def state(self, stream, when):
        field, index, energy_index = STREAMS[stream]
        row, fresh = self.latest(field, when)
        valid = row is not None and fresh and len(row["value_valid"]) > index and row["value_valid"][index]
        angle = math.degrees(row["values"][index]) if valid else None
        energy = None
        gated = valid
        if energy_index is not None:
            e, e_fresh = self.latest(FIELDS[1], when)
            e_ok = e is not None and e_fresh and len(e["value_valid"]) > energy_index and e["value_valid"][energy_index]
            energy = e["values"][energy_index] if e_ok else None
            gated = valid and e_ok and energy > 0
        return {"angle_deg": angle, "angle_available": bool(valid), "available": bool(gated),
                "sector": coarse_sector(angle) if gated else None, "energy": energy,
                "receipt_ns": row["available_monotonic_ns"] if row else None,
                "dsp_freshness": "unknown_not_exposed"}

    def boundaries(self, stream, start, stop):
        field, _, energy_index = STREAMS[stream]
        fields = [field] + ([FIELDS[1]] if energy_index is not None else [])
        result = {start, stop}
        for name in fields:
            stamps = self.stamps[name]
            lo = bisect.bisect_left(stamps, start - AGE_NS - 1)
            hi = bisect.bisect_right(stamps, stop)
            for t in stamps[lo:hi]:
                if start < t < stop:
                    result.add(t)
                expiry = t + AGE_NS + 1
                if start < expiry < stop:
                    result.add(expiry)
        return sorted(result)

    def intervals(self, stream, start, stop):
        bounds = self.boundaries(stream, start, stop)
        return [(a, b, self.state(stream, a)) for a, b in zip(bounds, bounds[1:])]

    def max_gap(self, stream, start, stop):
        field, _, energy_index = STREAMS[stream]
        worst = 0
        for name in [field] + ([FIELDS[1]] if energy_index is not None else []):
            stamps = self.stamps[name]
            lo = bisect.bisect_left(stamps, start)
            hi = bisect.bisect_right(stamps, stop)
            # If a long observed gap straddles the left boundary, retain its
            # actual preceding receipt. Starting exactly on a fresh receipt
            # permits a new clean window without carrying an earlier gap in.
            preceding = stamps[lo-1] if lo > 0 and (lo >= len(stamps) or stamps[lo] != start) else start
            window = [preceding] + stamps[lo:hi] + [stop]
            worst = max(worst, max((b - a for a, b in zip(window, window[1:])), default=stop - start))
        return worst / 1e9

    def field_stats(self):
        result = {}
        for field, rows in self.fields.items():
            stamps = self.stamps[field]
            gaps = [(b - a) / 1e9 for a, b in zip(stamps, stamps[1:])]
            same = [a["values"] == b["values"] for a, b in zip(rows, rows[1:])]
            result[field] = {
                "count": len(rows), "receipt_rate_hz": (len(rows) - 1) * 1e9 / (stamps[-1] - stamps[0]) if len(rows) > 1 and stamps[-1] > stamps[0] else None,
                "receipt_gap_median_s": statistics.median(gaps) if gaps else None,
                "receipt_gap_max_s": max(gaps) if gaps else None,
                "receipt_gaps_above_age_limit": sum(g > .25 for g in gaps),
                "invalid_transactions": sum(not r["transaction_valid"] for r in rows),
                "nonfinite_or_invalid_values": sum(sum(not v for v in r["value_valid"]) for r in rows),
                "identical_adjacent_arrays": sum(same), "adjacent_comparisons": len(same),
                "held_value_interpretation": "Not evidence of stale DSP or independent DSP updates",
            }
        return result


class Availability:
    def __init__(self, metadata, startup, offset):
        self.rows = metadata["callback_times"]
        self.startup, self.offset = startup, offset
        self.starts = [r["first_native_frame"] for r in self.rows]
        self.times = [r.get("host_copy_complete_monotonic_ns", r["host_callback_monotonic_ns"]) for r in self.rows]
        for i, r in enumerate(self.rows):
            if r["frames"] <= 0 or (i and r["first_native_frame"] != self.starts[i-1] + self.rows[i-1]["frames"]):
                raise ValueError("Noncontiguous callback sample ranges")
            if i and self.times[i] < self.times[i-1]:
                raise ValueError("Callback availability decreases")
        self.ends = self.times[1:] + [self.times[-1] + round(self.rows[-1]["frames"] / 48000 * 1e9)]

    def source_range(self, start, stop, extra_delay=0):
        if self.offset is None:
            return []
        first = self.startup + 3 * (start + self.offset + extra_delay)
        last = self.startup + 3 * (stop + self.offset + extra_delay) - 1
        selected = []
        for i, row in enumerate(self.rows):
            if row["first_native_frame"] <= last and row["first_native_frame"] + row["frames"] > first:
                selected.append([self.times[i], self.ends[i]])
        return union(selected)

    def support(self, segment, delay=0):
        pre = segment.get("rir_expected_significant_onset_sample", segment["source_start_sample"] + 800) - segment["source_start_sample"]
        # s4_bank stores estimated ranges on the absolute source scene clock
        # with retained RIR pre-onset already included. Only a dry-file-bound
        # fallback needs the convention added here; never add it twice.
        ranges = segment.get("activity_ranges_samples_estimated")
        if not ranges:
            ranges = [[segment["source_start_sample"] + pre, segment["source_stop_sample"] + pre]]
        return union([v for a, b in ranges for v in self.source_range(a, b, delay)])


def summarize_window(timeline, stream, support, target=None):
    support = union(support)
    seconds = duration(support)
    good = match = angle_good = wrong = held_wrong = 0
    weighted_errors = []
    previous_angle = None
    for start, stop in support:
        for a, b, state in timeline.intervals(stream, start, stop):
            dt = (b - a) / 1e9
            angle_good += dt * state["angle_available"]
            good += dt * state["available"]
            if target is not None and state["available"]:
                same = state["sector"] == coarse_sector(target["expected_native_nominal_deg"])
                match += dt * same
                wrong += dt * (not same)
                held_wrong += dt * (not same and previous_angle == state["angle_deg"])
                error = angle_error(state["angle_deg"], target)
                weighted_errors.append((dt, error))
            previous_angle = state["angle_deg"]
    denominator = sum(w for w, _ in weighted_errors)
    return {
        "support_duration_s": seconds,
        "angle_only_coverage": angle_good / seconds if seconds else None,
        "speech_energy_gated_coverage": good / seconds if seconds else None,
        "spatial_unavailable_fraction": 1 - good / seconds if seconds else None,
        "matching_sector_occupancy": match / seconds if seconds and target else None,
        "wrong_sector_duration_s": wrong if target else None,
        "held_wrong_sector_duration_s": held_wrong if target else None,
        "held_wrong_definition": "Matching numeric angle across adjacent causal state intervals in a wrong coarse sector; descriptive, not stale-DSP evidence",
        "nominal_error_mean_deg": sum(w * e["nominal_error_deg"] for w, e in weighted_errors) / denominator if denominator else None,
        "interval_error_mean_deg": sum(w * e["interval_error_deg"] for w, e in weighted_errors) / denominator if denominator else None,
    }


def acquisition(timeline, stream, start, stop, target):
    desired = coarse_sector(target["expected_native_nominal_deg"])
    intervals = timeline.intervals(stream, start, stop)
    hits = [a for a, _, state in intervals if state["available"] and state["sector"] == desired]
    onset = timeline.state(stream, start)
    first = min(hits) if hits else None
    field = STREAMS[stream][0]
    candidates = [t for t in timeline.stamps[field] if start + 1_000_000_000 <= t <= stop]
    sustained = None
    for when in candidates:
        current = timeline.state(stream, when)
        if not current["available"] or current["sector"] != desired:
            continue
        begin = when - 1_000_000_000
        occupancy = sum((b-a)/1e9 for a,b,state in timeline.intervals(stream,begin,when)
                        if state["available"] and state["sector"] == desired)
        if occupancy >= .8 - 1e-12 and timeline.max_gap(stream,begin,when) <= .25 + 1e-12:
            sustained = when
            break
    return {
        "target_coarse_sector": desired,
        "first_sector_hit_s": (first-start)/1e9 if first is not None else None,
        "first_hit_censored": first is None,
        "already_matching_at_onset": onset["available"] and onset["sector"] == desired,
        "sustained_acquisition_s": (sustained-start)/1e9 if sustained is not None else None,
        "sustained_acquisition_censored": sustained is None,
        "observed_envelope_duration_s": (stop-start)/1e9,
        "lag_scope": "Host available cue relative to quantized estimated activity availability; not device reaction latency",
    }


def off_delay(timeline, stream, end, censor, target):
    desired = coarse_sector(target["expected_native_nominal_deg"])
    failure = None
    for a, _, state in timeline.intervals(stream, end, censor):
        if not state["available"] or state["sector"] != desired:
            failure = a
            break
    return {"off_delay_s": (failure-end)/1e9 if failure is not None else None,
            "off_delay_censored": failure is None, "off_delay_observation_s": max(0, (censor-end)/1e9)}


def analyze_case(folder, scene, selected_rirs, output_delay_samples=None):
    folder = Path(folder)
    result = read(folder/"case_result.json")
    metadata = read(folder/"capture_metadata.json")
    raw_path = folder/"telemetry/received_telemetry.jsonl"
    rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8-sig").splitlines()]
    timeline = ReceiptTimeline(rows)
    available = Availability(metadata, result["framing"]["startup_frames_excluded"], result["payload"]["capture_minus_source_offset_samples"])
    rirs = {r["run_id"]: r for r in selected_rirs} if isinstance(selected_rirs, list) else selected_rirs
    utterances = [s for s in scene["segments"] if s["kind"] == "utterance"]
    supports = {s["utterance_label"]: available.support(s) for s in utterances}
    full = [[available.times[0], available.ends[-1]]]
    turns = {}
    for segment in utterances:
        label = rirs[segment["rir_id"]]["geometry"].get("active_angle_label") or source_label(rirs[segment["rir_id"]]["geometry"]["speaker_angle_deg_effective"])
        support = supports[segment["utterance_label"]]
        if not support:
            turns[segment["utterance_label"]] = {"status": "UNAVAILABLE_INPUT_ALIGNMENT"}
            continue
        start, end = support[0][0], support[-1][1]
        future = [v[0][0] for key,v in supports.items() if key != segment["utterance_label"] and v and v[0][0] > end]
        censor = min(future + [available.ends[-1]])
        if any(v and v[0][0] <= end < v[-1][1] for key,v in supports.items() if key != segment["utterance_label"]):
            censor = end
        per_stream = {}
        for stream in STREAMS:
            per_stream[stream] = {**summarize_window(timeline,stream,support,label),
                                  **acquisition(timeline,stream,start,end,label),
                                  **off_delay(timeline,stream,end,censor,label)}
        processed_views = {}
        for output, delay in (output_delay_samples or {}).items():
            if delay is None:
                continue
            shifted = available.support(segment, delay)
            processed_views[output] = {"measured_relative_delay_samples": delay, "scope": "Output vs recaptured MIC0 only; no telemetry fit",
                                      "streams": {stream:summarize_window(timeline,stream,shifted,label) for stream in STREAMS}}
        turns[segment["utterance_label"]] = {
            "status": "LIMITED_MULTISPEAKER_TRUTH" if scene.get("overlap_scoring_limited") else "DESCRIPTIVE_NOMINAL_GEOMETRY",
            "rir_id":segment["rir_id"], "participant_id":segment["participant_id"],
            "source_activity_ranges_samples_estimated":segment.get("activity_ranges_samples_estimated"),
            "activity_range_basis":"Absolute scene samples; bank-estimated ranges already include retained RIR pre-onset once",
            "retained_rir_preonset_samples":segment.get("rir_expected_significant_onset_sample",segment["source_start_sample"]+800)-segment["source_start_sample"],
            "host_activity_ranges_ns":support, "source_angle_label":label, "streams":per_stream,
            "processed_output_availability_views":processed_views,
        }
    nonspeech_controls = {}
    noise_windows = {}
    for segment in [s for s in scene["segments"] if s["kind"] == "synthetic_point_noise"]:
        noise = available.source_range(segment["source_start_sample"] + 800,segment.get("convolution_stop_sample",segment["source_stop_sample"]))
        noise_metrics = {stream:summarize_window(timeline,stream,noise) for stream in STREAMS}
        noise_windows["speech_plus_point_noise" if utterances else "synthetic_point_noise_only"] = {
            "false_speech_indication_interpretation_allowed": not utterances, "streams": noise_metrics}
        if not utterances:
            nonspeech_controls["synthetic_point_noise"] = noise_metrics
    if not utterances:
        nonspeech_controls["whole_nonspeech_capture"] = {stream:summarize_window(timeline,stream,full) for stream in STREAMS}
    receipt = {
        "schema_version":"jp_s4_spatial_case_v2", "case_id":scene["case_id"], "batch":result.get("batch",folder.parent.name),
        "hardware_status":result["status"], "telemetry_status":result.get("telemetry_status"),
        "scoring_policy":S4_SPATIAL_POLICY,
        "raw_field_statistics":timeline.field_stats(),
        "whole_capture_availability":{stream:summarize_window(timeline,stream,full) for stream in STREAMS},
        "turns":turns, "nonspeech_controls":nonspeech_controls, "noise_windows":noise_windows,
        "callback_availability":{
            "basis":"host_copy_complete_monotonic_ns when present; historical callback receipt otherwise",
            "count":len(available.rows), "max_block_span_s":max(r["frames"] for r in available.rows)/48000,
            "max_availability_gap_s":max((b-a)/1e9 for a,b in zip(available.times,available.times[1:])) if len(available.times)>1 else None,
            "capture_minus_source_offset_samples":available.offset,
            "silent_alignment_unidentifiable":available.offset is None,
            "absolute_device_or_acoustic_latency_known":False,
        },
        "bindings":[digest(folder/"case_result.json"),digest(folder/"capture_metadata.json"),digest(raw_path)],
        "claims_excluded":["independent source angle calibration","device accuracy within manual +/-5 degrees","beam ID as person ID","new DSP frame on each read","S5 output winner","S6 cue benefit"],
    }
    return receipt


class OfflineTests(unittest.TestCase):
    @staticmethod
    def rows(angle, end=2.0, missing=False):
        rows=[]
        for i in range(round(end*20)+1):
            t=1_000_000_000+i*50_000_000
            if missing and .5 < i/20 < 1.2: continue
            rows.append({"command":FIELDS[2],"sequence":i,"values":[math.radians(angle),math.radians(angle)],
                         "invalid_reasons":[None,None],"parse_ok":True,"logical_request_start_monotonic_ns":t-1_000_000,
                         "response_end_monotonic_ns":t-100_000,"host_line_arrival_monotonic_ns":t,"units":"radians"})
        return rows

    def test_sustained_and_never_acquired(self):
        left=source_label(75)
        yes=acquisition(ReceiptTimeline(self.rows(165)),"selected_processed",1_000_000_000,3_000_000_000,left)
        self.assertEqual(yes["first_sector_hit_s"],0)
        self.assertEqual(yes["sustained_acquisition_s"],1)
        no=acquisition(ReceiptTimeline(self.rows(10)),"selected_processed",1_000_000_000,3_000_000_000,left)
        self.assertTrue(no["sustained_acquisition_censored"])
        self.assertIsNone(no["first_sector_hit_s"])

    def test_future_and_gap(self):
        timeline=ReceiptTimeline(self.rows(165,missing=True))
        self.assertFalse(timeline.state("selected_processed",999_999_999)["available"])
        self.assertFalse(timeline.state("selected_processed",1_900_000_000)["available"])
        result=acquisition(timeline,"selected_processed",1_000_000_000,3_000_000_000,source_label(75))
        self.assertTrue(result["sustained_acquisition_censored"])

    def test_duration_weighting_and_off_delay(self):
        timeline=ReceiptTimeline(self.rows(165,end=1.0))
        m=summarize_window(timeline,"selected_processed",[[1_000_000_000,3_000_000_000]],source_label(75))
        self.assertAlmostEqual(m["speech_energy_gated_coverage"],.625,places=7)
        off=off_delay(timeline,"selected_processed",2_000_000_000,3_000_000_000,source_label(75))
        self.assertAlmostEqual(off["off_delay_s"],.25,places=7)

    def test_callback_uses_copy_completion_and_silent_alignment(self):
        meta={"callback_times":[{"first_native_frame":0,"frames":48,"host_callback_monotonic_ns":100,"host_copy_complete_monotonic_ns":200},
                                {"first_native_frame":48,"frames":48,"host_callback_monotonic_ns":1_000_100,"host_copy_complete_monotonic_ns":1_000_200}]}
        available=Availability(meta,0,0)
        self.assertEqual(available.source_range(0,1),[[200,1_000_200]])
        self.assertEqual(Availability(meta,0,None).source_range(0,1),[])

    def test_bank_activity_already_includes_retained_rir_margin(self):
        # Bank style: source starts at 3 seconds. Estimated active onset at
        # 3.55 seconds ALREADY contains the 50 ms retained RIR convention.
        meta = {"callback_times": [
            {"first_native_frame": i*480, "frames": 480,
             "host_callback_monotonic_ns": 1_000_000_000+i*10_000_000,
             "host_copy_complete_monotonic_ns": 1_000_000_100+i*10_000_000}
            for i in range(500)]}
        mapping = Availability(meta, 0, 0)
        segment = {"source_start_sample": 48000, "source_stop_sample": 64000,
                   "rir_expected_significant_onset_sample": 48800,
                   "activity_ranges_samples_estimated": [[56800, 60800]]}
        support = mapping.support(segment)
        # Native frame 3 * 56800 == 170400, exactly callback index 355.
        self.assertEqual(3*segment["activity_ranges_samples_estimated"][0][0], 170400)
        self.assertEqual(support[0][0], meta["callback_times"][355]["host_copy_complete_monotonic_ns"])
        self.assertNotEqual(support[0][0], meta["callback_times"][360]["host_copy_complete_monotonic_ns"])
        delayed = mapping.support(segment, delay=160)
        self.assertEqual(delayed[0][0], meta["callback_times"][356]["host_copy_complete_monotonic_ns"])
        fallback = {key:value for key,value in segment.items() if key != "activity_ranges_samples_estimated"}
        self.assertEqual(mapping.support(fallback)[0][0], meta["callback_times"][305]["host_copy_complete_monotonic_ns"])

    def test_case_schema_and_noise_with_speech_is_not_false_positive(self):
        metadata = {"callback_times": [
            {"first_native_frame": i*2400, "frames": 2400,
             "host_callback_monotonic_ns": 1_000_000_000+i*50_000_000,
             "host_copy_complete_monotonic_ns": 1_000_001_000+i*50_000_000}
            for i in range(60)]}
        result = {"case_id": "fixture", "status": "PASS", "telemetry_status": "PASS",
                  "framing": {"startup_frames_excluded": 0},
                  "payload": {"capture_minus_source_offset_samples": 0}}
        scene = {"case_id": "fixture", "segments": [
            {"kind": "utterance", "utterance_label": "A1", "participant_id": "A", "rir_id": "rir",
             "source_start_sample": 0, "source_stop_sample": 24000,
             "activity_ranges_samples_estimated": [[1600, 20000]]},
            {"kind": "synthetic_point_noise", "source_start_sample": 0, "source_stop_sample": 24000}]}
        rir = [{"run_id": "rir", "geometry": {"active_angle_label": source_label(75)}}]
        lines = "\n".join(json.dumps(r) for r in self.rows(165, end=3))
        def fake_read(path):
            return metadata if Path(path).name == "capture_metadata.json" else result
        with patch(__name__ + ".read", side_effect=fake_read), patch(__name__ + ".digest", return_value={}), patch.object(Path, "read_text", return_value=lines):
            metrics = analyze_case(Path("offline_fixture"), scene, rir, {"O0": 880})
        self.assertIn("A1", metrics["turns"])
        self.assertIn("O0", metrics["turns"]["A1"]["processed_output_availability_views"])
        self.assertFalse(metrics["noise_windows"]["speech_plus_point_noise"]["false_speech_indication_interpretation_allowed"])
        self.assertEqual(metrics["nonspeech_controls"], {})
        json.dumps(metrics, allow_nan=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--case-folder",type=Path)
    p.add_argument("--scene-manifest",type=Path)
    p.add_argument("--output",type=Path)
    p.add_argument("--output-delays-json",type=Path,help='Optional JSON object e.g. {"O0":873,"O1":871}; measured samples, not fitted metadata shifts')
    p.add_argument("--policy-output",type=Path)
    a=p.parse_args()
    if a.self_test:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OfflineTests))
        raise SystemExit(0 if result.wasSuccessful() else 1)
    if a.policy_output:
        with a.policy_output.open("x",encoding="utf-8") as f:json.dump(S4_SPATIAL_POLICY,f,indent=2,allow_nan=False)
        return
    if not all((a.case_folder,a.scene_manifest,a.output)):p.error("Provide --case-folder, --scene-manifest and --output")
    manifest=read(a.scene_manifest);case=read(a.case_folder/"case_result.json")["case_id"]
    scene=next(s for s in manifest["scenes"] if s["case_id"]==case)
    metrics=analyze_case(a.case_folder,scene,manifest["selected_rirs"],read(a.output_delays_json) if a.output_delays_json else None)
    with a.output.open("x",encoding="utf-8") as f:json.dump(metrics,f,indent=2,allow_nan=False)
    print(json.dumps({"case_id":case,"status":"ANALYZED","output":str(a.output)}))


if __name__=="__main__":main()
