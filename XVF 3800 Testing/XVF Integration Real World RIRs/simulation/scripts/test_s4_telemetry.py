"""Offline regression tests. No test opens USB or an audio endpoint."""
import copy
import json
import math
import unittest

from s4_geometry import ANGLE_POLICY, angle_error, coarse_sector, lab_to_native_deg, source_label
from s4_telemetry import CallbackAvailabilityMap, CausalSpatialReader, TIMING_TELEMETRY_POLICY, normalize_observation


def row(receipt=1_000_000_000, values=None, command="AUDIO_MGR_SELECTED_AZIMUTHS"):
    return {"command": command, "sequence": 12, "receipt_sequence": 9,
            "logical_request_start_monotonic_ns": receipt - 20_000_000,
            "response_end_monotonic_ns": receipt - 1_000_000,
            "host_line_arrival_monotonic_ns": receipt,
            "values": values if values is not None else [math.pi / 2, math.pi / 3],
            "invalid_reasons": [None, None], "parse_ok": True,
            "units": "radians", "raw_reply": "preserved", "raw_response_base64": "AAAA"}


class GeometryTests(unittest.TestCase):
    def test_nominal_orientation(self):
        for lab, native in [(0, 90), (75, 165), (-80, 10), (180, 90)]:
            self.assertAlmostEqual(lab_to_native_deg(lab), native)

    def test_wrapped_manual_interval(self):
        label = source_label(179)
        self.assertEqual(label["source_interval_lab_wrapped_deg"], [[-180.0, -176.0], [174.0, 180.0]])
        self.assertAlmostEqual(label["expected_native_interval_deg"][0], 86)
        self.assertAlmostEqual(label["expected_native_interval_deg"][1], 96)

    def test_endfire_fold_includes_interior_extremum(self):
        for sign, expected in [(1, [174, 180]), (-1, [0, 6])]:
            interval = source_label(89 * sign)["expected_native_interval_deg"]
            for value, truth in zip(interval, expected):
                self.assertAlmostEqual(value, truth)

    def test_front_rear_are_ambiguous(self):
        self.assertAlmostEqual(lab_to_native_deg(30), lab_to_native_deg(150))
        self.assertFalse(source_label(30)["front_rear_resolved"])

    def test_raw_label_and_manual_uncertainty_are_preserved(self):
        label = source_label(-179)
        self.assertEqual(label["source_angle_lab_signed_deg"], -179)
        self.assertEqual(label["source_angle_manual_uncertainty_deg"], 5)
        self.assertFalse(label["independently_calibrated"])
        self.assertEqual(label["authority"], "user_reported_manual_measurement")

    def test_error_columns_not_device_accuracy(self):
        errors = angle_error(169, source_label(75))
        self.assertAlmostEqual(errors["nominal_error_deg"], 4)
        self.assertEqual(errors["interval_error_deg"], 0)
        self.assertEqual(errors["device_accuracy_claim"], "not_established")
        self.assertFalse(ANGLE_POLICY["manual_label_uncertainty_is_device_tolerance"])
        self.assertEqual(coarse_sector(119), "central_ambiguous")

    def test_invalid_observation_has_no_error(self):
        errors = angle_error(float("nan"), source_label(75))
        self.assertFalse(errors["device_native_valid"])
        self.assertIsNone(errors["nominal_error_deg"])
        json.dumps(errors, allow_nan=False)


class CausalTests(unittest.TestCase):
    def test_missing_preserves_audio_text(self):
        result = CausalSpatialReader().at(1_000_000_000)
        self.assertEqual(result["spatial_state"], "spatial_unavailable")
        self.assertTrue(result["audio_text_allowed"])

    def test_future_receipt_never_used(self):
        reader = CausalSpatialReader()
        reader.ingest(row())
        self.assertEqual(reader.at(999_999_999)["spatial_state"], "spatial_unavailable")
        self.assertEqual(reader.at(1_000_000_000)["spatial_state"], "available")

    def test_gap_expires_without_a_new_reply(self):
        reader = CausalSpatialReader()
        reader.ingest(row())
        self.assertEqual(reader.at(1_250_000_000)["spatial_state"], "available")
        self.assertEqual(reader.at(1_250_000_001)["spatial_state"], "spatial_unavailable")

    def test_held_value_does_not_imply_stale_or_new_dsp_frame(self):
        reader = CausalSpatialReader()
        reader.ingest(row())
        reader.ingest(row(2_000_000_000))
        result = reader.at(2_000_000_000)
        self.assertEqual(result["spatial_state"], "available")
        self.assertEqual(result["dsp_freshness"], "unknown_not_exposed")
        self.assertFalse(result["beam_id_is_person_id"])

    def test_late_transaction_unavailable(self):
        value = row()
        value["logical_request_start_monotonic_ns"] = 0
        reader = CausalSpatialReader()
        reader.ingest(value)
        self.assertEqual(reader.at(1_000_000_000)["spatial_state"], "spatial_unavailable")
        self.assertIn("late_transaction", normalize_observation(value)["transaction_invalid_reasons"])

    def test_late_line_delivery_unavailable(self):
        value = row()
        value["host_line_arrival_monotonic_ns"] += 300_000_000
        self.assertIn("late_line_delivery", normalize_observation(value)["transaction_invalid_reasons"])

    def test_invalid_time_order_and_missing_bounds(self):
        for mutate in (lambda r: r.pop("response_end_monotonic_ns"),
                       lambda r: r.update(response_end_monotonic_ns=2_000_000_000)):
            value = row()
            mutate(value)
            self.assertFalse(normalize_observation(value)["transaction_valid"])

    def test_no_speech_nan_is_null_with_reason_not_zero_or_failure(self):
        value = row(values=[None, 0.0])
        value["invalid_reasons"] = ["documented_no_fixed_beam_speech", None]
        normalized = normalize_observation(value)
        self.assertTrue(normalized["transaction_valid"])
        self.assertEqual(normalized["value_valid"], [False, True])
        self.assertIsNone(normalized["values"][0])
        self.assertEqual(normalized["values"][1], 0)
        self.assertEqual(normalized["raw_reply"], "preserved")
        json.dumps(normalized, allow_nan=False)

    def test_null_without_native_reason_not_assumed_no_speech(self):
        normalized = normalize_observation(row(values=[None, 0.0]))
        self.assertEqual(normalized["value_invalid_reasons"][0], "missing_or_nonfinite_value")

    def test_invalid_new_reply_masks_old_valid(self):
        reader = CausalSpatialReader()
        reader.ingest(row())
        bad = row(1_100_000_000)
        bad["parse_ok"] = False
        reader.ingest(bad)
        self.assertEqual(reader.at(1_100_000_000)["spatial_state"], "spatial_unavailable")

    def test_out_of_range_and_malformed_values(self):
        self.assertFalse(normalize_observation(row(values=[4, 0]))["value_valid"][0])
        self.assertFalse(normalize_observation(row(values=[0]))["transaction_valid"])
        self.assertFalse(normalize_observation(row(values=[-1, 0, 0, 0], command="AEC_SPENERGY_VALUES"))["value_valid"][0])


class CallbackTests(unittest.TestCase):
    def setUp(self):
        self.callbacks = [{"first_native_frame": 0, "frames": 48, "host_callback_monotonic_ns": 1_000_000},
                          {"first_native_frame": 48, "frames": 48, "host_callback_monotonic_ns": 2_000_000}]

    def test_packed_alignment_uses_last_frame_of_triplet(self):
        mapping = CallbackAvailabilityMap(self.callbacks, 9, 10)
        result = mapping.recaptured_source_sample(5)
        self.assertEqual(result["native_frame"], 56)
        self.assertEqual(result["available_monotonic_ns"], 2_000_000)
        self.assertIsNone(result["device_or_acoustic_time_ns"])

    def test_no_edge_extrapolation(self):
        mapping = CallbackAvailabilityMap(self.callbacks)
        self.assertFalse(mapping.native_frame(-1)["available"])
        self.assertFalse(mapping.native_frame(96)["available"])

    def test_noncontiguous_sample_range_rejected(self):
        self.callbacks[1]["first_native_frame"] = 49
        with self.assertRaises(ValueError):
            CallbackAvailabilityMap(self.callbacks)

    def test_write_receive_processed_are_separate(self):
        mapping = CallbackAvailabilityMap(self.callbacks, 9, 10)
        self.assertEqual(mapping.written_source_sample(5)["native_frame"], 17)
        self.assertEqual(mapping.recaptured_source_sample(5)["native_frame"], 56)
        result = mapping.processed_source_sample(5, 2)
        self.assertEqual(result["native_frame"], 62)
        self.assertFalse(result["delay_is_absolute_device_latency"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
