"""Headless validation harness for GUI state and command serialization."""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

from app.dataset_registry.loader import load_filter_option_values, parse_subset_filters
from app.dataset_registry.registry import get_dataset
from app.gui.launcher import BatchLauncher
from app.gui.preview import generate_preview_only
from app.gui.state import (
    GuiRunConfig,
    RIR_LISTBOX_HEIGHT,
    augmentation_visibility,
    build_cli_commands,
    parse_snr_values,
    validate_gui_config,
)
from app.plotting.plots import build_plots
from app.prediction_io.jsonl import write_utterance_predictions
from app.reporting.reporter import build_report
from app.scoring.scorer import score_run
from app.utils.run_artifacts import ensure_run_subdirs
from app.gui.widgets import MULTISELECT_DROPDOWN_HEIGHT, VerticalScrolledFrame
from app.utils.json_utils import read_json
from app.utils.paths import find_project_root, tool_root


def run_validation_harness(run_smoke: bool = False) -> None:
    """Run lightweight assertions for the GUI flow."""

    project_root = find_project_root()
    root = tool_root(project_root)

    assert augmentation_visibility("none").show_rir_controls is False
    assert augmentation_visibility("reverb").show_rir_controls is True
    assert augmentation_visibility("noise").show_noise_controls is True
    assert augmentation_visibility("reverb_noise").show_rir_controls is True
    assert augmentation_visibility("reverb_noise").show_noise_controls is True
    assert RIR_LISTBOX_HEIGHT <= 10
    assert MULTISELECT_DROPDOWN_HEIGHT <= 10
    _validate_dropdown_widget()

    cmu_options = load_filter_option_values(project_root, get_dataset("cmu_arctic"))
    libri_options = load_filter_option_values(project_root, get_dataset("librispeech"))
    hifitts_options = load_filter_option_values(project_root, get_dataset("hifitts"))
    ami_options = load_filter_option_values(project_root, get_dataset("ami"))
    voices_options = load_filter_option_values(project_root, get_dataset("voices"))
    chime6_options = load_filter_option_values(project_root, get_dataset("chime6"))
    assert cmu_options["gender"], "CMU Arctic gender options should come from metadata"
    assert "dev-clean" in libri_options["split"], "LibriSpeech split options should come from metadata"
    assert "6097_clean" in hifitts_options["reader_split"], "HiFiTTS reader_split options should come from metadata"
    assert "array" in ami_options["stream_type"], "AMI stream_type options should come from metadata"
    assert "headset" in ami_options["stream_type"], "AMI stream_type options should come from metadata"
    assert "rm1" in voices_options["room"], "VOiCES room options should come from metadata"
    assert "none" in voices_options["distractor"], "VOiCES distractor options should include native none condition"
    assert "far" in voices_options["position"], "VOiCES position options should come from metadata"
    assert "dev" in chime6_options["split"], "CHiME-6 split options should come from metadata"
    assert "S02" in chime6_options["session_id"], "CHiME-6 session options should come from metadata"
    assert "farfield_array" in chime6_options["stream_type"], "CHiME-6 stream_type options should come from metadata"
    assert "U01_CH1" in chime6_options["microphone_id"], "CHiME-6 microphone options should come from metadata"
    _validate_grouped_metric_outputs(root)

    parsed_filters = parse_subset_filters(
        ["split=dev-clean,test-clean"],
        get_dataset("librispeech"),
    )
    assert parsed_filters["split"] == ["dev-clean", "test-clean"]

    assert parse_snr_values("5, 10,20") == (5.0, 10.0, 20.0)
    try:
        parse_snr_values("10, nope")
    except ValueError:
        pass
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Invalid SNR text should fail")

    no_dataset = GuiRunConfig(dataset_keys=())
    assert validate_gui_config(no_dataset)

    needs_rir = GuiRunConfig(dataset_keys=("cmu_arctic",), augmentation="reverb")
    assert any("RIR" in error for error in validate_gui_config(needs_rir))

    needs_snr = GuiRunConfig(
        dataset_keys=("hifitts",),
        augmentation="noise",
        noise_types=("pink",),
    )
    assert any("SNR" in error for error in validate_gui_config(needs_snr))

    ami_clean = GuiRunConfig(dataset_keys=("ami",), augmentation="none")
    assert validate_gui_config(ami_clean) == []

    ami_reverb = GuiRunConfig(dataset_keys=("ami",), augmentation="reverb", rir_paths=("example.wav",))
    assert any("augmentation" in error.lower() for error in validate_gui_config(ami_reverb))

    voices_clean = GuiRunConfig(dataset_keys=("voices",), augmentation="none")
    assert validate_gui_config(voices_clean) == []

    voices_noise = GuiRunConfig(dataset_keys=("voices",), augmentation="noise", noise_types=("white",), snr_db=(20.0,))
    assert any("augmentation" in error.lower() for error in validate_gui_config(voices_noise))

    chime6_clean = GuiRunConfig(dataset_keys=("chime6",), augmentation="none")
    assert validate_gui_config(chime6_clean) == []

    chime6_noise = GuiRunConfig(dataset_keys=("chime6",), augmentation="noise", noise_types=("white",), snr_db=(20.0,))
    assert any("augmentation" in error.lower() for error in validate_gui_config(chime6_noise))

    config = GuiRunConfig(
        dataset_keys=("cmu_arctic", "hifitts"),
        runner="simulation",
        simulation_mode="noisy",
        augmentation="noise",
        noise_types=("white", "pink"),
        snr_db=(10.0, 20.0),
        max_recordings=3,
        run_name="gui_batch",
        filters_by_dataset={
            "cmu_arctic": {"gender": ("male",)},
            "hifitts": {"reader_split": ("6097_clean",)},
        },
    )
    errors = validate_gui_config(config)
    assert errors == [], errors
    commands = build_cli_commands(config, root, python_executable=sys.executable)
    assert len(commands) == 2
    assert all(str(root / "run_evaluation.py") in command for command in commands)
    assert any("cmu_arctic" in command for command in commands)
    assert any("hifitts" in command for command in commands)
    assert any("gender=male" in command for command in commands)
    assert any("reader_split=6097_clean" in command for command in commands)
    assert all("--simulation-mode" in command for command in commands)
    assert all("--augmentation" in command for command in commands)

    multi_filter_config = GuiRunConfig(
        dataset_keys=("librispeech",),
        filters_by_dataset={"librispeech": {"split": ("dev-clean", "test-clean")}},
    )
    multi_filter_command = build_cli_commands(multi_filter_config, root, python_executable=sys.executable)[0]
    assert "split=dev-clean,test-clean" in multi_filter_command

    drop_some_batch = GuiRunConfig(
        dataset_keys=("cmu_arctic", "librispeech"),
        runner="simulation",
        simulation_mode="drop_some",
        augmentation="none",
        max_recordings=21,
        run_name="gui_drop_some_batch",
        filters_by_dataset={"librispeech": {"split": ("dev-clean",)}},
    )
    drop_some_commands = build_cli_commands(drop_some_batch, root, python_executable=sys.executable)
    assert len(drop_some_commands) == 2
    assert all("--simulation-mode" in command and "drop_some" in command for command in drop_some_commands)

    ami_command = build_cli_commands(
        GuiRunConfig(
            dataset_keys=("ami",),
            filters_by_dataset={"ami": {"stream_type": ("headset",), "seen_type": ("training",)}},
            run_name="ami_gui",
        ),
        root,
        python_executable=sys.executable,
    )[0]
    assert "--augmentation" in ami_command
    assert "none" in ami_command
    assert "--noise-type" not in ami_command
    assert "stream_type=headset" in ami_command

    voices_command = build_cli_commands(
        GuiRunConfig(
            dataset_keys=("voices",),
            filters_by_dataset={"voices": {"room": ("rm1",), "position": ("far",)}},
            run_name="voices_gui",
        ),
        root,
        python_executable=sys.executable,
    )[0]
    assert "--augmentation" in voices_command
    assert "none" in voices_command
    assert "--noise-type" not in voices_command
    assert "room=rm1" in voices_command

    chime6_command = build_cli_commands(
        GuiRunConfig(
            dataset_keys=("chime6",),
            filters_by_dataset={"chime6": {"split": ("dev",), "session_id": ("S02",), "stream_type": ("farfield_array",)}},
            run_name="chime6_gui",
        ),
        root,
        python_executable=sys.executable,
    )[0]
    assert "--augmentation" in chime6_command
    assert "none" in chime6_command
    assert "--noise-type" not in chime6_command
    assert "split=dev" in chime6_command
    assert "session_id=S02" in chime6_command

    if run_smoke:
        launcher = BatchLauncher(root, sys.executable)
        smoke_config = GuiRunConfig(
            dataset_keys=("cmu_arctic",),
            runner="simulation",
            simulation_mode="perfect",
            augmentation="noise",
            noise_types=("white",),
            snr_db=(20.0, 30.0),
            max_recordings=1,
            run_name="gui_validation_smoke",
        )
        result = launcher.run_batch(
            smoke_config,
            on_line=lambda line: print(line),
            on_progress=lambda done, total, msg: print(f"[GUI smoke] {done}/{total} {msg}"),
        )
        assert result.success, result.message
        smoke_run_dir = _latest_run_dir(root, "*_cmu_arctic_full_gui_validation_smoke")
        assert (smoke_run_dir / "predictions" / "noise_white_20db" / "utterances.jsonl").exists()
        assert (smoke_run_dir / "predictions" / "noise_white_30db" / "utterances.jsonl").exists()
        assert (smoke_run_dir / "metrics" / "noise_white_20db" / "per_recording_metrics.csv").exists()
        assert (smoke_run_dir / "metrics" / "noise_white_30db" / "per_recording_metrics.csv").exists()
        assert (smoke_run_dir / "metrics" / "gender_metrics.csv").exists()
        assert (smoke_run_dir / "metrics" / "accent_metrics.csv").exists()
        assert (smoke_run_dir / "metrics" / "accent_group_metrics.csv").exists()
        assert (smoke_run_dir / "metrics" / "speaker_variant_group_metrics.csv").exists()

        preview_config = GuiRunConfig(
            dataset_keys=("cmu_arctic",),
            runner="simulation",
            simulation_mode="perfect",
            augmentation="noise",
            noise_types=("pink",),
            snr_db=(25.0,),
            max_recordings=1,
            run_name="gui_preview_validation",
        )
        preview_result = generate_preview_only(
            config=preview_config,
            project_root=project_root,
            on_line=lambda line: print(f"[GUI preview] {line}"),
        )
        assert preview_result.preview_count == 1
        assert preview_result.preview_manifest_path.exists()
        preview_files = list((preview_result.run_dir / "preview_audio" / "noise_pink_25db").glob("*.wav"))
        assert preview_files, "Expected condition-specific preview WAV output"

        ami_config = GuiRunConfig(
            dataset_keys=("ami",),
            runner="simulation",
            simulation_mode="perfect",
            augmentation="none",
            max_recordings=2,
            run_name="gui_ami_validation_smoke",
            filters_by_dataset={"ami": {"stream_type": ("headset",), "meeting_id": ("IS1000a",)}},
        )
        ami_result = launcher.run_batch(
            ami_config,
            on_line=lambda line: print(line),
            on_progress=lambda done, total, msg: print(f"[GUI AMI smoke] {done}/{total} {msg}"),
        )
        assert ami_result.success, ami_result.message
        ami_run_dir = _latest_run_dir(root, "*_ami_full_gui_ami_validation_smoke")
        assert (ami_run_dir / "metrics" / "per_recording_metrics.csv").exists()
        assert (ami_run_dir / "metrics" / "stream_type_metrics.csv").exists()
        assert (ami_run_dir / "metrics" / "speaker_label_confusion.csv").exists()
        assert (ami_run_dir / "plots" / "speaker_label_confusion_summary.png").exists()

        voices_config = GuiRunConfig(
            dataset_keys=("voices",),
            runner="simulation",
            simulation_mode="perfect",
            augmentation="none",
            max_recordings=2,
            run_name="gui_voices_validation_smoke",
            filters_by_dataset={"voices": {"room": ("rm1",), "position": ("far",)}},
        )
        voices_result = launcher.run_batch(
            voices_config,
            on_line=lambda line: print(line),
            on_progress=lambda done, total, msg: print(f"[GUI VOiCES smoke] {done}/{total} {msg}"),
        )
        assert voices_result.success, voices_result.message
        voices_run_dir = _latest_run_dir(root, "*_voices_full_gui_voices_validation_smoke")
        assert (voices_run_dir / "metrics" / "per_recording_metrics.csv").exists()
        assert (voices_run_dir / "metrics" / "room_metrics.csv").exists()
        assert (voices_run_dir / "metrics" / "distractor_metrics.csv").exists()
        assert (voices_run_dir / "plots" / "voices_room_summary.png").exists()

        chime6_config = GuiRunConfig(
            dataset_keys=("chime6",),
            runner="simulation",
            simulation_mode="perfect",
            augmentation="none",
            max_recordings=2,
            run_name="gui_chime6_validation_smoke",
            filters_by_dataset={"chime6": {"split": ("dev",), "session_id": ("S02",), "stream_type": ("participant_close",)}},
        )
        chime6_result = launcher.run_batch(
            chime6_config,
            on_line=lambda line: print(line),
            on_progress=lambda done, total, msg: print(f"[GUI CHiME-6 smoke] {done}/{total} {msg}"),
        )
        assert chime6_result.success, chime6_result.message
        chime6_run_dir = _latest_run_dir(root, "*_chime6_full_gui_chime6_validation_smoke")
        assert (chime6_run_dir / "metrics" / "per_recording_metrics.csv").exists()
        assert (chime6_run_dir / "metrics" / "stream_type_metrics.csv").exists()
        assert (chime6_run_dir / "metrics" / "session_id_metrics.csv").exists()
        assert (chime6_run_dir / "metrics" / "speaker_label_confusion.csv").exists()
        assert (chime6_run_dir / "plots" / "chime6_stream_type_summary.png").exists()

        drop_result = launcher.run_batch(
            drop_some_batch,
            on_line=lambda line: print(line),
            on_progress=lambda done, total, msg: print(f"[GUI drop_some smoke] {done}/{total} {msg}"),
        )
        assert drop_result.success, drop_result.message
        assert "warnings" in drop_result.message
        cmu_drop_dir = _latest_run_dir(root, "*_cmu_arctic_full_gui_drop_some_batch_cmu_arctic")
        libri_drop_dir = _latest_run_dir(root, "*_librispeech_full_gui_drop_some_batch_librispeech")
        for run_dir in (cmu_drop_dir, libri_drop_dir):
            aggregate = read_json(run_dir / "metrics" / "aggregate_metrics.json")
            assert aggregate["missing_prediction_count"] >= 1
            assert aggregate["processed_prediction_count"] >= 1
            assert 0 < aggregate["missing_prediction_rate"] < 1
            assert (run_dir / "metrics" / "missing_predictions.csv").exists()
            assert (run_dir / "plots" / "wer_histogram.png").exists()
            assert (run_dir / "report" / "report.md").exists()

    print("GUI validation harness passed.")


def _validate_grouped_metric_outputs(root: Path) -> None:
    """Regression-check grouped metrics for multiple values and missing predictions."""

    logger = logging.getLogger("evaluation_tool_grouping_validation")
    logger.addHandler(logging.NullHandler())
    with tempfile.TemporaryDirectory(prefix="evaluation_tool_grouping_") as temp_dir_name:
        temp_root = Path(temp_dir_name)
        _validate_dataset_grouping(
            temp_root,
            "cmu_arctic",
            "gender",
            ("female", "male"),
            [
                _record("cmu_f_1", "female", {"gender": "female", "accent": "US"}),
                _record("cmu_m_1", "male", {"gender": "male", "accent": "US"}),
                _record("cmu_f_missing", "female", {"gender": "female", "accent": "US"}),
            ],
            logger,
        )
        _validate_dataset_grouping(
            temp_root,
            "librispeech",
            "split",
            ("dev-clean", "test-clean"),
            [
                _record("libri_dev_1", "1272", {"split": "dev-clean", "subset_group": "clean", "gender": "M"}),
                _record("libri_test_1", "1995", {"split": "test-clean", "subset_group": "clean", "gender": "F"}),
                _record("libri_test_missing", "1995", {"split": "test-clean", "subset_group": "clean", "gender": "F"}),
            ],
            logger,
        )
        _validate_dataset_grouping(
            temp_root,
            "hifitts",
            "reader_split",
            ("6097_clean", "11614_other"),
            [
                _record("hifi_6097_1", "6097", {"reader_split": "6097_clean", "clean_vs_other": "clean", "split": "dev"}),
                _record("hifi_11614_1", "11614", {"reader_split": "11614_other", "clean_vs_other": "other", "split": "train"}),
                _record("hifi_11614_missing", "11614", {"reader_split": "11614_other", "clean_vs_other": "other", "split": "train"}),
            ],
            logger,
        )


def _validate_dataset_grouping(
    temp_root: Path,
    dataset_key: str,
    group_column: str,
    expected_values: tuple[str, ...],
    records: list[dict[str, object]],
    logger: logging.Logger,
) -> None:
    definition = get_dataset(dataset_key)
    run_dir = temp_root / f"{dataset_key}_grouping_validation"
    ensure_run_subdirs(run_dir)
    prediction_rows = [
        {
            "recording_id": record["recording_id"],
            "utt_id": record["utt_id"],
            "start_sec": record["start_sec"],
            "end_sec": record["end_sec"],
            "speaker_label": record["speaker_label"],
            "text": record["reference_text"],
        }
        for record in records
        if not str(record["recording_id"]).endswith("_missing")
    ]
    write_utterance_predictions(run_dir / "predictions" / "utterances.jsonl", prediction_rows)
    score_run(run_dir, definition, records, logger)
    build_plots(run_dir, dataset_key, logger)
    build_report(run_dir, logger)

    grouped_path = run_dir / "metrics" / f"{group_column}_metrics.csv"
    grouped = _read_csv(grouped_path)
    observed_values = set(grouped[group_column].astype(str).tolist())
    assert set(expected_values).issubset(observed_values), (
        f"{dataset_key} {group_column} metrics missing values: "
        f"expected {expected_values}, observed {sorted(observed_values)}"
    )
    assert grouped["missing_prediction_count"].sum() >= 1
    assert (run_dir / "plots" / f"{dataset_key}_{group_column}_summary.png").exists()
    assert (run_dir / "metrics" / "missing_predictions.csv").exists()
    aggregate = read_json(run_dir / "metrics" / "aggregate_metrics.json")
    assert aggregate["missing_prediction_count"] >= 1


def _record(
    recording_id: str,
    speaker_label: str,
    extra: dict[str, object],
) -> dict[str, object]:
    row: dict[str, object] = {
        "recording_id": recording_id,
        "utt_id": f"{recording_id}_utt",
        "speaker_label": speaker_label,
        "start_sec": 0.0,
        "end_sec": 1.0,
        "reference_text": "the quick brown fox",
        "duration_sec": 1.0,
        "audio_exists": True,
        "audio_path_project_relative": f"synthetic/{recording_id}.wav",
        "audio_path_resolved": "",
        "augmentation_condition_id": "clean",
        "augmentation_mode": "none",
    }
    row.update(extra)
    return row


def _read_csv(path: Path):
    import pandas as pd

    if not path.exists():
        raise AssertionError(f"Expected grouped metrics file: {path}")
    return pd.read_csv(path)


def _validate_dropdown_widget() -> None:
    """Exercise the compact multi-select widget when tkinter can open locally."""

    try:
        import tkinter as tk
    except Exception as exc:  # pragma: no cover - environment boundary
        print(f"Skipping tkinter widget check: {exc}")
        return

    from app.gui.widgets import MultiSelectDropdown

    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless boundary
        print(f"Skipping tkinter widget check: {exc}")
        return
    root.withdraw()
    scrolled = VerticalScrolledFrame(root, padding=4)
    scrolled.pack(fill=tk.BOTH, expand=True)
    for index in range(20):
        tk.Label(scrolled.content, text=f"scroll row {index}").pack()
    root.update_idletasks()
    assert scrolled.canvas.bbox(tk.ALL) is not None

    widget = MultiSelectDropdown(scrolled.content, ["dev-clean", "test-clean", "train-clean-100"], selected=("dev-clean",))
    widget.pack()
    root.update_idletasks()
    assert widget.get_selected() == ("dev-clean",)
    widget.open_popup()
    root.update_idletasks()
    assert widget._popup is not None and widget._popup.winfo_exists()
    assert widget._listbox is not None
    widget._listbox.selection_clear(0, tk.END)
    widget._listbox.selection_set(1)
    widget._listbox.selection_set(2)
    widget._on_select()
    assert widget.get_selected() == ("test-clean", "train-clean-100")
    widget.clear_selection()
    assert widget.get_selected() == ()
    assert validate_gui_config(
        GuiRunConfig(
            dataset_keys=("librispeech",),
            filters_by_dataset={"librispeech": {"split": widget.get_selected()}},
        )
    ) == []

    widget.set_selected(("dev-clean",))
    assert widget.get_selected() == ("dev-clean",)
    assert widget._popup is not None
    widget._popup.destroy()
    root.update_idletasks()
    assert widget.get_selected() == ("dev-clean",)
    widget.clear_selection()
    assert widget.get_selected() == ()
    widget.open_popup()
    root.update_idletasks()
    assert widget._popup is not None and widget._popup.winfo_exists()
    widget.close_popup()
    root.update_idletasks()
    assert widget._popup is None
    root.destroy()


def _latest_run_dir(root: Path, pattern: str) -> Path:
    runs_root = root / "runs"
    matches = [path for path in runs_root.glob(pattern) if path.is_dir()]
    if not matches:
        raise AssertionError(f"No run directory matched {pattern}")
    return max(matches, key=lambda path: path.stat().st_mtime)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate GUI state and launch logic.")
    parser.add_argument(
        "--run-smoke",
        action="store_true",
        help="Also launch a one-record CMU Arctic simulation through the GUI batch launcher.",
    )
    args = parser.parse_args()
    run_validation_harness(run_smoke=args.run_smoke)
