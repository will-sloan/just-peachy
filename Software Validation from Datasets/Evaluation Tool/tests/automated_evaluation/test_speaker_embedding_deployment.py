from __future__ import annotations

import numpy as np

from app.speaker_deployment.replay import calibrate_open_set_policy


def test_open_set_policy_caps_unknown_and_wrong_name_on_calibration_only():
    policy = calibrate_open_set_policy(
        known_scores=np.asarray([0.90, 0.82, 0.79, 0.76, 0.70]),
        known_margins=np.asarray([0.30, 0.20, 0.10, 0.01, 0.01]),
        known_correct=np.asarray([True, True, True, False, False]),
        unknown_scores=np.asarray([0.85, 0.75, 0.65, 0.55, 0.45]),
        unknown_margins=np.asarray([0.01, 0.02, 0.03, 0.04, 0.05]),
        fpir_target=0.20,
        wrong_name_rate_cap=0.0,
        margin_grid=[0.0, 0.02, 0.05],
    )
    accepted_unknown = (np.asarray([0.85, 0.75, 0.65, 0.55, 0.45]) >= policy["score_threshold"]) & (np.asarray([0.01, 0.02, 0.03, 0.04, 0.05]) >= policy["margin_threshold"])
    assert accepted_unknown.mean() <= 0.20
    assert policy["calibration_known_wrong_name_rate"] == 0.0
    assert policy["evaluation_used_for_selection"] is False


def test_margin_gate_can_reject_ambiguous_high_scores():
    policy = calibrate_open_set_policy(
        known_scores=np.asarray([0.9, 0.88]),
        known_margins=np.asarray([0.2, 0.01]),
        known_correct=np.asarray([True, False]),
        unknown_scores=np.asarray([0.86, 0.5]),
        unknown_margins=np.asarray([0.01, 0.2]),
        fpir_target=0.0,
        wrong_name_rate_cap=0.0,
        margin_grid=[0.0, 0.05],
    )
    assert policy["margin_threshold"] == 0.05
    assert policy["calibration_known_correct_acceptance"] == 0.5
