from __future__ import annotations

from pathlib import Path

import pytest

from app.full_pipeline_demo import cli
from app.full_pipeline_demo.enrollment import LabelledWav


class _ImmediateManager:
    calls: list[tuple[str, dict[str, object]]] = []
    init_calls: list[dict[str, object]] = []
    default_product_mode = "H2_SESSION_MEMORY_ENHANCED"

    def __init__(self, **kwargs: object) -> None:
        self.init_calls.append(dict(kwargs))
        self.session_id = "session"

    def start_file(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("file", dict(kwargs)))
        return {"session_id": "session"}

    def start_microphone(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("live", dict(kwargs)))
        return {"session_id": "session"}

    def join(self, _session_id: str | None = None, timeout: float | None = None) -> dict[str, object]:
        del timeout
        return {"session_id": "session", "state": "completed", "runtime_status": {}}

    def shutdown(self, *, timeout_per_session: float) -> None:
        del timeout_per_session


def test_file_and_live_cli_route_recording_only_to_microphone(
    tmp_path: Path, monkeypatch
) -> None:
    _ImmediateManager.calls.clear()
    monkeypatch.setattr(cli, "DemoSessionManager", _ImmediateManager)
    source = tmp_path / "input.wav"
    source.write_bytes(b"RIFF")

    file_args = cli._parser().parse_args(["file", "--input", str(source)])
    assert cli._run_session_command(file_args)["state"] == "completed"
    kind, file_values = _ImmediateManager.calls[-1]
    assert kind == "file"
    assert "record_input_audio" not in file_values
    assert file_values["pipeline_id"] == "fullpipe_v1_ag_dr_ir"
    assert file_values["product_mode"] == "H2_SESSION_MEMORY_ENHANCED"

    live_args = cli._parser().parse_args(
        ["live", "--duration-sec", "1", "--record-input-audio"]
    )
    assert cli._run_session_command(live_args)["state"] == "completed"
    kind, live_values = _ImmediateManager.calls[-1]
    assert kind == "live"
    assert live_values["record_input_audio"] is True
    assert live_values["product_mode"] == "H2_SESSION_MEMORY_ENHANCED"


def test_session_cli_rejects_audio_inclusion_without_export_root(
    tmp_path: Path,
) -> None:
    source = tmp_path / "input.wav"
    source.write_bytes(b"RIFF")
    args = cli._parser().parse_args(
        ["file", "--input", str(source), "--include-audio"]
    )
    with pytest.raises(ValueError, match="requires --export-root"):
        cli._run_session_command(args)


def test_cli_forwards_checksum_bound_runtime_config_to_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ImmediateManager.init_calls.clear()
    monkeypatch.setattr(cli, "DemoSessionManager", _ImmediateManager)
    source = tmp_path / "input.wav"
    source.write_bytes(b"RIFF")
    binding = tmp_path / "binding.json"
    binding.write_text("{}", encoding="utf-8")
    args = cli._parser().parse_args(
        [
            "file",
            "--input",
            str(source),
            "--h2-runtime-config",
            str(binding),
            "--h2-runtime-config-sha256",
            "a" * 64,
        ]
    )
    assert cli._run_session_command(args)["state"] == "completed"
    assert _ImmediateManager.init_calls[-1]["runtime_config_path"] == binding
    assert _ImmediateManager.init_calls[-1][
        "runtime_config_expected_sha256"
    ] == "a" * 64


def test_default_smoke_audio_uses_portable_data_resolver(
    tmp_path: Path, monkeypatch
) -> None:
    observed: list[Path] = []
    expected = tmp_path / "external" / "arctic_a0281.wav"

    def resolve(logical: str | Path) -> Path:
        observed.append(Path(logical))
        return expected

    monkeypatch.setattr(cli, "resolve_data_path_from_logical", resolve)

    assert cli._parser().parse_args(["smoke"]).input is None
    assert cli._default_smoke_audio_path() == expected.resolve()
    assert observed == [cli.DEFAULT_SMOKE_AUDIO_LOGICAL]


def test_cli_requires_exact_matrix_enrollment_count_and_unique_prompts(
    tmp_path: Path,
) -> None:
    matrix = cli.FullPipelineMatrix(cli.MATRIX_PATH, cli.RUNTIME_CONFIG_PATH)
    two = tuple(
        LabelledWav(f"prompt_{index}", tmp_path / f"take_{index}.wav")
        for index in (1, 2)
    )
    with pytest.raises(ValueError, match="exactly 3"):
        cli._require_policy_take_count(matrix, cli.DEFAULT_PIPELINE, two)
    duplicate = tuple(
        LabelledWav("prompt_1", tmp_path / f"take_{index}.wav")
        for index in (1, 2, 3)
    )
    with pytest.raises(ValueError, match="must be unique"):
        cli._require_policy_take_count(matrix, cli.DEFAULT_PIPELINE, duplicate)


@pytest.mark.parametrize("state", ["repeat_required", "invalid", "failed"])
def test_cli_returns_nonzero_for_unsuccessful_enrollment_state(
    state: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_dispatch", lambda _args: {"state": state})
    assert cli.main(["presets"]) == 1


def test_live_wrapper_only_forwards_include_audio_with_recording_consent() -> None:
    script = (
        Path(__file__).resolve().parents[2] / "scripts/run_full_pipeline_demo.ps1"
    ).read_text(encoding="utf-8")
    assert "if ($IncludeAudio -and -not $RecordInputAudio)" in script
    assert 'if ($IncludeAudio) { $arguments += "--include-audio" }' in script
    assert (
        'if ($IncludeAudio -and $Action -in @("File", "Live") -and -not $ExportRoot)'
        in script
    )
    assert '[Nullable[double]]$DurationSec = $null' in script
    assert '$liveDurationSec = 30.0' in script
    assert "$Wav.Count -ne $requiredEnrollmentWavCount" in script
    assert '[string]$Wav1' in script
    assert '[string]$Wav2' in script
    assert '[string]$Wav3' in script
    assert '$Wav = @($Wav1, $Wav2, $Wav3)' in script
    assert '[string]$PipelineId = "fullpipe_v1_ag_dr_ir"' in script
    assert "[string]$ProductMode," in script
    assert "[string]$H2RuntimeConfig," in script
    assert "[string]$H2RuntimeConfigSha256," in script
    assert 'if ($ProductMode -and $Action -in @("File", "Live"))' in script
    assert '"--product-mode", $ProductMode' in script
    assert '"--h2-runtime-config", $H2RuntimeConfig' in script
    assert '"--h2-runtime-config-sha256", $H2RuntimeConfigSha256' in script
