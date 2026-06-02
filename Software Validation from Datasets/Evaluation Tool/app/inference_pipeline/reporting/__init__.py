"""Reusable reporting layer for inference pipeline component runs."""

__all__ = [
    "GeneratedReportArtifacts",
    "ReportMetadata",
    "generate_report_from_run",
    "render_markdown_report",
    "template_path_for_component",
    "validate_report_contents",
]


def __getattr__(name: str) -> object:
    if name not in __all__:
        raise AttributeError(name)
    from app.inference_pipeline.reporting import component_report

    return getattr(component_report, name)
