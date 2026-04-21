"""On-the-fly audio augmentation for clean single-speaker evaluations."""

from app.augmentation.config import AugmentationCondition, AugmentationPlan, build_augmentation_plan
from app.augmentation.processor import (
    RuntimeAugmentor,
    expand_records_for_augmentation,
    generate_previews,
)

__all__ = [
    "AugmentationCondition",
    "AugmentationPlan",
    "RuntimeAugmentor",
    "build_augmentation_plan",
    "expand_records_for_augmentation",
    "generate_previews",
]

