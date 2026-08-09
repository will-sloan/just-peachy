"""Campaign-level analysis, reporting, coverage, and release qualification."""

from .analysis import analyze_campaign
from .index import build_analysis_manifest
from .release import evaluate_release_gates
from .statistics import paired_comparison

__all__ = [
    "analyze_campaign",
    "build_analysis_manifest",
    "evaluate_release_gates",
    "paired_comparison",
]
