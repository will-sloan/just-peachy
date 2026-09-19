"""Nominal linear-array geometry; manual label uncertainty is not device accuracy."""
from __future__ import annotations

import math

TRANSFORM_ID = "nominal_linear_mic0_left_mic3_right_acos_minus_sin_v1"


def wrap_lab_deg(angle: float) -> float:
    if not math.isfinite(angle):
        raise ValueError("Source angle must be finite")
    return (float(angle) + 180.0) % 360.0 - 180.0


def lab_to_native_deg(angle: float) -> float:
    """Nominal lab forward=0, left positive; native MIC3=0/MIC0=180."""
    return math.degrees(math.acos(max(-1.0, min(1.0, -math.sin(math.radians(wrap_lab_deg(angle)))))))


def source_label(angle: float, uncertainty_deg: float = 5.0) -> dict:
    """Map the WHOLE circular manual interval, including folds at +/-90."""
    angle = float(angle)
    if not math.isfinite(uncertainty_deg) or not 0 <= uncertainty_deg <= 180:
        raise ValueError("Manual uncertainty must be finite within 0..180 degrees")
    centre = wrap_lab_deg(angle)
    low, high = centre - uncertainty_deg, centre + uncertainty_deg
    if uncertainty_deg == 180:
        wrapped = [[-180.0, 180.0]]
    elif low < -180:
        wrapped = [[-180.0, high], [low + 360.0, 180.0]]
    elif high > 180:
        wrapped = [[-180.0, high - 360.0], [low, 180.0]]
    else:
        wrapped = [[low, high]]
    # Piecewise-linear folded transform: endpoints and every interior +/-90
    # extremum suffice. Mapping only the endpoints fails near endfire.
    candidates = [low, high]
    for k in range(-4, 5):
        critical = 90.0 + 180.0 * k
        if low <= critical <= high:
            candidates.append(critical)
    native = [lab_to_native_deg(v) for v in candidates]
    return {
        "source_angle_lab_signed_deg": angle,
        "source_angle_lab_wrapped_deg": centre,
        "source_angle_manual_uncertainty_deg": uncertainty_deg,
        "authority": "user_reported_manual_measurement",
        "independently_calibrated": False,
        "source_interval_lab_wrapped_deg": wrapped,
        "coordinate_transform_id": TRANSFORM_ID,
        "expected_native_nominal_deg": lab_to_native_deg(centre),
        "expected_native_interval_deg": [min(native), max(native)],
        "transform_status": "nominal_geometry_not_independent_angle_calibration",
        "front_rear_resolved": False,
    }


def angle_error(native_deg: float | None, label: dict) -> dict:
    valid = native_deg is not None and math.isfinite(native_deg) and 0 <= native_deg <= 180
    result = {"device_native_deg": native_deg if valid else None,
              "device_native_valid": valid,
              "coordinate_transform_id": label["coordinate_transform_id"],
              "nominal_error_deg": None, "interval_error_deg": None,
              "device_accuracy_claim": "not_established"}
    if valid:
        lo, hi = label["expected_native_interval_deg"]
        result["nominal_error_deg"] = abs(native_deg - label["expected_native_nominal_deg"])
        result["interval_error_deg"] = max(lo - native_deg, native_deg - hi, 0.0)
    return result


def coarse_sector(native_deg: float | None) -> str | None:
    if native_deg is None or not math.isfinite(native_deg) or not 0 <= native_deg <= 180:
        return None
    return "right" if native_deg < 60 else "left" if native_deg > 120 else "central_ambiguous"


ANGLE_POLICY = {
    "schema_version": "jp_s4_angle_label_policy_v1",
    "source_angle_manual_uncertainty_deg": 5,
    "authority": "user_reported_manual_measurement",
    "independently_calibrated": False,
    "coordinate_transform_id": TRANSFORM_ID,
    "transform_equation": "native_degrees = degrees(acos(-sin(radians(lab_degrees))))",
    "authority_for_nominal_transform": "User-reported MIC0 left/MIC3 right and local XMOS 3.2.1 user guide Figure 3.3",
    "native_range_deg": [0, 180],
    "manual_label_uncertainty_is_device_tolerance": False,
    "device_accuracy_claim": "not_established",
    "front_rear_resolved": False,
    "error_columns": ["nominal_error_deg", "interval_error_deg"],
    "coarse_sectors": {"right": "0 <= native < 60", "central_ambiguous": "60 <= native <= 120", "left": "120 < native <= 180"},
}
