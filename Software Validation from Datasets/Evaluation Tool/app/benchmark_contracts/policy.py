"""Benchmark panel eligibility and augmentation enforcement."""

from __future__ import annotations

from typing import Mapping


PANELS = frozenset({"controlled_clean", "native_robustness", "speaker_protocol"})
AUGMENTATION_POLICIES = frozenset({"allow", "native_only", "review"})
NATIVE_DATASETS = frozenset({"ami", "voices", "chime6"})
NOISY_METADATA_FIELDS = (
    "is_noisy",
    "native_noisy",
    "is_reverberant",
    "native_reverberant",
    "reverberation_status",
    "noise_condition",
    "native_condition",
)


class AugmentationPolicyError(ValueError):
    """Raised when a condition violates a row's immutable policy."""


def augmentation_policy_for_record(
    panel: str,
    dataset: str,
    record: Mapping[str, object],
) -> str:
    """Derive the explicit allow/native_only/review policy from source metadata."""

    if panel not in PANELS:
        raise AugmentationPolicyError(f"unknown benchmark panel {panel!r}")
    dataset_key = dataset.strip().lower()
    if panel == "native_robustness" or dataset_key in NATIVE_DATASETS:
        return "native_only"
    if _metadata_marks_native_degradation(record):
        return "native_only"
    if dataset_key == "cmu_arctic":
        return "allow"
    if dataset_key == "librispeech":
        subset_group = _text(record.get("subset_group"))
        split = _text(record.get("split"))
        return "allow" if subset_group == "clean" and split.endswith("-clean") else "native_only"
    if dataset_key == "hifitts":
        quality = _text(record.get("audio_quality") or record.get("clean_vs_other"))
        return "allow" if quality == "clean" else "native_only"
    return "review"


def validate_augmentation_request(
    record: Mapping[str, object],
    condition: Mapping[str, object],
) -> None:
    """Reject illegal or internally incomplete acoustic conditions."""

    panel = _text(record.get("panel"))
    dataset = _text(record.get("dataset"))
    policy = _text(record.get("augmentation_policy"))
    if policy not in AUGMENTATION_POLICIES:
        raise AugmentationPolicyError(f"invalid augmentation policy {policy!r}")
    expected = augmentation_policy_for_record(panel, dataset, record)
    if expected == "native_only" and policy != "native_only":
        raise AugmentationPolicyError(
            f"{panel}/{dataset} requires native_only, got {policy}"
        )

    mode = _text(condition.get("augmentation"))
    noise_type = condition.get("noise_type")
    snr_db = condition.get("snr_db")
    rir = condition.get("rir")
    if mode == "none":
        if noise_type is not None or snr_db is not None or rir is not None:
            raise AugmentationPolicyError("none condition must have null noise, SNR, and RIR")
        return
    if panel == "native_robustness" or dataset in NATIVE_DATASETS or policy != "allow":
        raise AugmentationPolicyError(
            f"augmentation {mode!r} is forbidden for {panel}/{dataset}/{policy}"
        )
    if mode == "noise":
        if _text(noise_type) not in {"white", "pink"} or not _is_number(snr_db) or rir is not None:
            raise AugmentationPolicyError("noise requires white/pink, numeric SNR, and null RIR")
        return
    if mode == "reverb":
        if noise_type is not None or snr_db is not None or not isinstance(rir, Mapping):
            raise AugmentationPolicyError("reverb requires exact RIR and null noise/SNR")
        return
    if mode == "reverb_noise":
        if (
            _text(noise_type) not in {"white", "pink"}
            or not _is_number(snr_db)
            or not isinstance(rir, Mapping)
        ):
            raise AugmentationPolicyError("reverb_noise requires exact RIR, noise, and SNR")
        return
    raise AugmentationPolicyError(f"unsupported augmentation mode {mode!r}")


def _metadata_marks_native_degradation(record: Mapping[str, object]) -> bool:
    for field in NOISY_METADATA_FIELDS:
        value = record.get(field)
        if isinstance(value, bool) and value:
            return True
        text = _text(value)
        if text and text not in {"0", "false", "none", "clean", "no"}:
            return True
    return False


def _text(value: object) -> str:
    return "" if value is None else str(value).strip().lower()


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
