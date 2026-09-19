"""Offline, conservative acoustic marker candidates for the V2 sweep pack.

This is an acquisition sanity check, not a clock calibration or an IR alignment
algorithm. Neither the microphone recordings nor their sample clocks are changed.
The thresholds are engineering review gates informed by the laptop pilots; they
have not been validated for every loudspeaker, room, or playback level.
"""
from pathlib import Path
import hashlib
import math

import numpy as np
import soundfile as sf


RATE = 16000
VERSION = "v2-actual48k-fourmic-fir-1"
PADDING = 128
MIN_FUSED = 0.30
MIN_CHANNEL = 0.30
MIN_CHANNELS = 2
MIN_PROMINENCE = 1.15
START_RADIUS_S = 1.0
END_RADIUS_S = 0.30
REPEAT_TOLERANCE_S = 0.005
GLOBAL_TOLERANCE_S = 0.020


def _lowpass(cutoff, rate, half_length):
    positions = np.arange(-half_length, half_length + 1, dtype=float)
    coefficients = 2 * cutoff / rate * np.sinc(2 * cutoff / rate * positions)
    coefficients *= np.blackman(len(positions))
    return coefficients / coefficients.sum()


def _bandpass_coefficients():
    # Retain the marker's upper mid-band. This suppresses low-frequency speech,
    # room coloration and mains noise while avoiding the 8 kHz Nyquist edge.
    return _lowpass(6000, RATE, 64) - _lowpass(1500, RATE, 64)


def _templates(excitation):
    path = excitation.get("path")
    if path is None:
        path = Path(__file__).parent / "assets/excitation_v2" / excitation["id"]
    path = Path(path)
    played, rate = sf.read(path, dtype="float64")
    if rate != 48000 or played.ndim != 1:
        raise ValueError("Marker templates require the exact mono 48 kHz excitation file")
    extra = 1 if "2S_GAP" in excitation["id"] else 0
    expected = [2.0, 16.0 + extra, 16.2 + extra]
    # Centered convolution removes filter group delay from the TEMPLATE only.
    # The actual 48 kHz file is anti-aliased before 3:1 sample-rate reduction.
    # Whole-file filtering and padding retain the short marker's filter tails.
    reduced = np.convolve(played, _lowpass(7200, 48000, 96), mode="same")[::3]
    bandpass = _bandpass_coefficients()
    templates = []
    for event in expected:
        at = round(event * RATE)
        burst = reduced[at - PADDING:at + 320 + PADDING]
        if len(burst) != 320 + 2 * PADDING or not np.any(burst):
            raise ValueError("Excitation does not contain the documented V2 markers")
        templates.append(np.convolve(burst, bandpass, mode="same"))
    return templates, expected, path


def _normalized_correlations(microphones, template):
    length = len(template)
    if len(microphones) < length:
        return np.empty((0, 4)), np.empty((0, 4))
    nfft = 1 << (len(microphones) + length - 2).bit_length()
    numerator = np.fft.irfft(
        np.fft.rfft(microphones, nfft, axis=0)
        * np.fft.rfft(template[::-1], nfft)[:, None], nfft, axis=0
    )[length - 1:len(microphones)]
    sums = np.vstack([np.zeros((1, 4)), np.cumsum(microphones * microphones, axis=0)])
    energy = np.maximum(sums[length:] - sums[:-length], 0)
    template_energy = float(np.dot(template, template))
    denominator = np.sqrt(energy * template_energy)
    # Exact digital silence can leave FFT roundoff or cumsum subtraction residue.
    # Do not normalize numerical noise into an apparently perfect correlation.
    usable = energy > np.max(energy, axis=0, keepdims=True) * 1e-12
    result = np.divide(numerator, denominator, out=np.zeros_like(numerator), where=usable & (denominator > 0))
    projection = np.where(usable, numerator / template_energy, 0)
    return np.clip(result, -1.0, 1.0), projection


def _candidates(evidence, center_sample, radius_s, count=10):
    # Squared per-mic scores combine evidence without cancelling acoustic phase.
    # The score is evaluated at one common frame; actual audio is never shifted.
    correlations, projection = evidence
    fused = np.sqrt(np.mean(correlations * correlations, axis=1))
    amplitude = np.sqrt(np.mean(projection * projection, axis=1))
    lo = max(0, round(center_sample - radius_s * RATE) - PADDING)
    hi = min(len(fused), round(center_sample + radius_s * RATE) - PADDING + 1)
    if lo >= hi:
        return []
    # Rank coherent matched amplitude, then gate its normalized correlation.
    # Normalized correlation alone gives a tiny isolated echo the same rank as
    # the direct burst; amplitude prominence preserves that useful distinction.
    available = np.ones(hi - lo, dtype=bool)
    confident = (fused >= MIN_FUSED) & (np.count_nonzero(np.abs(correlations) >= MIN_CHANNEL, axis=1) >= MIN_CHANNELS)
    found = []
    for _ in range(count):
        eligible = available & confident[lo:hi]
        # Prefer candidates that actually resemble the burst over louder speech
        # with weak similarity. Retain weaker shape matches as labelled evidence
        # when no candidate meets the confidence gate.
        rank = np.where(eligible, amplitude[lo:hi], 0) if np.any(eligible) else np.where(available, fused[lo:hi], 0)
        relative = int(np.argmax(rank))
        if float(rank[relative]) <= 0:
            break
        at = lo + relative
        matched_amplitude = float(amplitude[at])
        score = float(fused[at])
        values = correlations[at]
        channels_above = int(np.count_nonzero(np.abs(values) >= MIN_CHANNEL))
        found.append({
            "sample": at + PADDING,
            "time_s": (at + PADDING) / RATE,
            "normalized_correlation": score,
            "matched_filter_amplitude": matched_amplitude,
            "per_microphone_signed_correlation": values.tolist(),
            "channels_above_threshold": channels_above,
            "confidence_thresholds_pass": score >= MIN_FUSED and channels_above >= MIN_CHANNELS,
        })
        # One candidate per 20 ms burst/neighbourhood; side-lobes do not provide
        # independent confidence or a second end marker.
        available[max(0, relative - 320):relative + 321] = False
    return found


def _prominence(best, alternative):
    if best <= 0:
        return 0.0
    # Finite representation for JSON: 1e6 means no nonzero alternative found.
    return min(1e6, best / alternative) if alternative > 0 else 1e6


def marker_qc(mics, excitation, playback_offset_s):
    """Return reviewable candidates, or RETAKE when confidence/timing fails.

    mics must be the four simultaneous physical microphones at 16 kHz, in either
    raw or fixed-gain domain. playback_offset_s is only a broad host-time search
    hint, expressed relative to the saved decoded microphone recording.
    """
    microphones = np.asarray(mics, dtype=np.float64)
    if microphones.ndim != 2 or microphones.shape[1] != 4:
        raise ValueError("Acoustic marker QC requires all four simultaneous microphones")
    if not np.isfinite(microphones).all() or not math.isfinite(float(playback_offset_s)):
        raise ValueError("Marker input and playback offset must be finite")
    templates, expected, path = _templates(excitation)
    bandpass = _bandpass_coefficients()
    if len(microphones) >= len(bandpass):
        filtered = np.column_stack([
            np.convolve(microphones[:, channel], bandpass, mode="same") for channel in range(4)
        ])
    else:
        filtered = np.empty((0, 4))
    correlations = [_normalized_correlations(filtered, template) for template in templates]
    starts = _candidates(correlations[0], (playback_offset_s + expected[0]) * RATE, START_RADIUS_S)
    start = starts[0] if starts else None
    start_sample = start["sample"] if start else (playback_offset_s + expected[0]) * RATE
    ends = [
        _candidates(correlations[k], start_sample + (expected[k] - expected[0]) * RATE, END_RADIUS_S)
        for k in (1, 2)
    ]
    # Overlapping search windows must never assign the same physical burst twice.
    # Select the strongest DISTINCT ordered pair over a broad 100--300 ms range,
    # then test its independently measured separation. Do not force 200 ms by
    # construction: a 260 ms interval must remain visible as a timing failure.
    pairs = []
    for first in ends[0]:
        for second in ends[1]:
            separation = (second["sample"] - first["sample"]) / RATE
            if 0.100 <= separation <= 0.300:
                score = math.sqrt(first["matched_filter_amplitude"] * second["matched_filter_amplitude"])
                pairs.append((score, first, second))
    confident_pairs = [p for p in pairs if p[1]["confidence_thresholds_pass"] and p[2]["confidence_thresholds_pass"]]
    pairs = confident_pairs or pairs
    pairs.sort(key=lambda item: item[0], reverse=True)
    if pairs:
        _, end1, end2 = pairs[0]
        pair_prominence = _prominence(pairs[0][0], pairs[1][0] if len(pairs) > 1 else 0) if confident_pairs else 0.0
    else:
        end1 = end2 = None
        pair_prominence = 0.0
    found = [start, end1, end2]
    other_confident_starts = [candidate for candidate in starts[1:] if candidate["confidence_thresholds_pass"]]
    start_prominence = _prominence(
        start["matched_filter_amplitude"],
        other_confident_starts[0]["matched_filter_amplitude"] if other_confident_starts else 0,
    ) if start and start["confidence_thresholds_pass"] else 0.0
    repeat_error = ((end2["sample"] - end1["sample"]) / RATE - (expected[2] - expected[1])) if end1 and end2 else None
    global_error = ((end1["sample"] - start["sample"]) / RATE - (expected[1] - expected[0])) if start and end1 else None
    gates = {
        "all_three_markers_have_four_channel_evidence": all(v is not None for v in found),
        "all_markers_meet_correlation_thresholds": all(v and v["confidence_thresholds_pass"] for v in found),
        "start_candidate_is_distinct": start_prominence >= MIN_PROMINENCE,
        "end_pair_is_distinct": pair_prominence >= MIN_PROMINENCE,
        "end_repeat_interval_within_tolerance": repeat_error is not None and abs(repeat_error) <= REPEAT_TOLERANCE_S,
        "start_to_end_interval_within_tolerance": global_error is not None and abs(global_error) <= GLOBAL_TOLERANCE_S,
    }
    # all() above can return None for an absent candidate; serialize booleans.
    gates = {key: bool(value) for key, value in gates.items()}
    accepted_for_review = all(gates.values())
    confidence_pass = all(gates[key] for key in list(gates)[:4])
    failed = [name for name, passed in gates.items() if not passed]
    return {
        "status": "REVIEW" if accepted_for_review else "RETAKE",
        "algorithm_version": VERSION,
        "markers": found,
        "expected_event_times_s": expected,
        "sample_rate_hz": RATE,
        "template_source": "Exact played mono 48 kHz file; separate start/end templates, anti-aliased 3:1 reduction for matching only",
        "source_file": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "template_sha256": [hashlib.sha256(t.astype("<f8").tobytes()).hexdigest() for t in templates],
        "filter": {
            "anti_alias": "193-tap symmetric Blackman-windowed sinc, 7200 Hz cutoff at 48000 Hz; centered convolution before decimation",
            "analysis_band": "129-tap symmetric Blackman-windowed FIR, 1500--6000 Hz, applied to all four mics and templates",
            "template_padding_samples_each_side": PADDING,
            "group_delay_compensated_in_analysis_only": True,
        },
        "thresholds": {
            "minimum_fused_rms_correlation": MIN_FUSED,
            "minimum_per_channel_absolute_correlation": MIN_CHANNEL,
            "minimum_channels": MIN_CHANNELS,
            "minimum_peak_prominence_ratio": MIN_PROMINENCE,
            "prominence_basis": "RMS matched-filter amplitude among candidates that meet the four-mic normalized correlation gates; 1e6 denotes no competing qualifying candidate",
            "start_search_radius_s": START_RADIUS_S,
            "end_search_radius_s": END_RADIUS_S,
            "end_repeat_interval_tolerance_s": REPEAT_TOLERANCE_S,
            "start_to_end_interval_tolerance_s": GLOBAL_TOLERANCE_S,
            "scope": "Provisional coarse acquisition review gates; not sample-accurate IR or clock qualification",
        },
        "gates": gates,
        "start_peak_prominence_ratio": start_prominence,
        "end_pair_prominence_ratio": pair_prominence,
        "end_marker_separation_error_s": repeat_error,
        "start_to_end_interval_error_s": global_error,
        "interval_candidate_confidence_pass": confidence_pass,
        "approx_drift_ppm_if_same_arrival_peak": None,
        "automatic_alignment_accepted": False,
        "clock_drift_qualified": False,
        "candidate_alternatives": {
            "start": starts[:5], "end1": ends[0][:5], "end2": ends[1][:5],
        },
        "reason": (
            "Marker candidates pass coarse confidence and interval gates; review acoustic paths and repeatability before IR alignment."
            if accepted_for_review else "Retake or investigate: " + ", ".join(failed) + "."
        ) + " These are candidate arrival peaks, not calibrated direct-path arrivals. No audio resampling or final RIR was performed.",
    }
