"""Tkinter presentation layer for the local full-pipeline demonstration app.

The UI contains no model logic.  It delegates immutable runtime sessions to
``DemoSessionManager``, local biometric lifecycle operations to
``EnrollmentService``, and renders only projected public events/statuses.
Potentially blocking actions run on daemon background threads; Tk widgets are
updated exclusively by the ``after``-driven UI polling loop.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Callable, Mapping, Sequence

from .devices import AudioInputDevice, enumerate_input_devices
from .enrollment import (
    DEFAULT_ENROLLMENT_PROMPTS,
    EnrollmentService,
    LabelledWav,
)
from .h2_ux import (
    H2_DEFAULT_PRODUCT_MODE,
    H2_KNOWN_ONLY,
    H2_PRODUCT_MODES,
    h2_mode_display_values,
    h2_mode_id_from_display,
    h2_pipeline_role,
    h2_product_mode,
    require_h2_pipeline_id,
)
from .presets import PresetCatalog
from .session import DemoSessionManager, TERMINAL_STATES
from .state import (
    DemoViewState,
    apply_event,
    apply_status,
    clear_anonymous_memory_projection,
    reset_session_projection,
)


POLL_INTERVAL_MS = 100
MAX_RESEARCH_EVENT_LINES = 500


@dataclass(frozen=True)
class PresetTableRow:
    preset_id: str
    asr: str
    diarization: str
    identity: str
    hybrid: str
    status: str
    highlighted: bool


@dataclass(frozen=True)
class EnrollmentTakeDisplay:
    prompt_id: str
    duration_sec: float
    rms_dbfs: float
    peak_dbfs: float
    clipped_fraction: float
    status: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class EnrollmentDisplay:
    state: str
    takes: tuple[EnrollmentTakeDisplay, ...]
    consistency: float | None
    outlier_take_id: str | None
    repeat_prompt_ids: tuple[str, ...]
    recommendation_codes: tuple[str, ...]
    identity_summary: str


@dataclass(frozen=True)
class EmbeddingInspectorDisplay:
    """Research-only raw identity evidence; values are never probabilities."""

    closest_identity: str
    top1_raw_score: str
    top2_raw_score: str
    margin: str
    evidence_duration: str
    quality: str
    backend_identity: str
    checkpoint_identity: str
    cluster_id: str
    decision: str
    warnings: str


@dataclass(frozen=True)
class RosterDisplayRow:
    participant_id: str
    display_label: str
    identity_state: str
    cluster_id: str
    last_seen: str


@dataclass(frozen=True)
class SelectiveRepeatPlan:
    pipeline_id: str
    display_label: str
    speaker_id: str
    all_prompt_ids: tuple[str, ...]
    repeat_prompt_ids: tuple[str, ...]
    retained: Mapping[str, LabelledWav]


def preset_table_rows(catalog: PresetCatalog) -> tuple[PresetTableRow, ...]:
    """Return the complete matrix as presentation-only table rows."""

    return tuple(
        PresetTableRow(
            preset_id=value.preset_id,
            asr=f"{value.asr_alias} · {value.asr_display_name}",
            diarization=(
                f"{value.diarization_alias} · {value.diarization_display_name}"
            ),
            identity=f"{value.identity_alias} · {value.identity_display_name}",
            hybrid=value.hybrid_label,
            status=(
                "Frozen anchor"
                if value.highlight
                else "Research challenger — known-name release off"
            ),
            highlighted=value.highlight is not None,
        )
        for value in catalog.presets
    )


def h2_preset_table_rows(catalog: PresetCatalog) -> tuple[PresetTableRow, ...]:
    """Return only the fixed H2 product pair in primary/fallback order."""

    rows: list[PresetTableRow] = []
    for value in catalog.h2_presets:
        role = h2_pipeline_role(value.preset_id)
        rows.append(
            PresetTableRow(
                preset_id=value.preset_id,
                asr=f"{value.asr_alias} · {value.asr_display_name}",
                diarization=(
                    f"{value.diarization_alias} · {value.diarization_display_name}"
                ),
                identity=(
                    f"{value.identity_alias} · {value.identity_display_name}"
                ),
                hybrid=value.hybrid_label,
                status=(
                    "Primary product pipeline"
                    if role == "PRIMARY"
                    else "Fallback / reference pipeline"
                ),
                highlighted=role == "PRIMARY",
            )
        )
    return tuple(rows)


def embedding_inspector_display(state: DemoViewState) -> EmbeddingInspectorDisplay:
    """Project the latest identity event into an explicit raw-score inspector."""

    candidate = (
        state.top1_candidate_display_label
        or state.top1_candidate_speaker_id
        or "—"
    )
    checkpoint = state.embedding_checkpoint_sha256 or "—"
    quality = state.identity_quality_status or "—"
    if state.identity_quality_reasons:
        quality += " · " + ", ".join(state.identity_quality_reasons)
    warnings = (*state.warnings, *state.errors)
    return EmbeddingInspectorDisplay(
        closest_identity=candidate,
        top1_raw_score=_format_float(state.top1_raw_score),
        top2_raw_score=_format_float(state.top2_raw_score),
        margin=_format_float(state.top1_top2_margin),
        evidence_duration=(
            f"{state.evidence_duration_sec:.3f} s"
            if state.evidence_duration_sec is not None
            else "—"
        ),
        quality=quality,
        backend_identity=(
            " / ".join(
                value
                for value in (state.embedding_backend_id, state.embedding_model_id)
                if value
            )
            or "—"
        ),
        checkpoint_identity=(checkpoint[:16] + "…" if len(checkpoint) > 18 else checkpoint),
        cluster_id=state.current_cluster_id or "—",
        decision=state.identity_decision or "—",
        warnings=" · ".join(warnings[-4:]) or "none",
    )


def roster_display_rows(state: DemoViewState) -> tuple[RosterDisplayRow, ...]:
    """Render active participants while honoring known-only privacy semantics."""

    rows: list[RosterDisplayRow] = []
    for participant in state.active_roster.values():
        if not participant.active:
            continue
        if (
            state.product_mode == H2_KNOWN_ONLY
            and participant.identity_state not in {"tentative", "confirmed", "known"}
        ):
            continue
        rows.append(
            RosterDisplayRow(
                participant_id=participant.participant_id,
                display_label=participant.display_label,
                identity_state=participant.identity_state,
                cluster_id=participant.cluster_id or "—",
                last_seen=(
                    f"{participant.last_seen_audio_sec:.2f} s"
                    if participant.last_seen_audio_sec is not None
                    else "—"
                ),
            )
        )
    return tuple(
        sorted(rows, key=lambda row: (row.display_label.casefold(), row.participant_id))
    )


def parse_pace(value: str) -> float:
    pace = float(value.strip())
    if pace < 0:
        raise ValueError("file pace must be non-negative")
    return pace


def parse_optional_duration(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    duration = float(text)
    if duration <= 0:
        raise ValueError("duration must be positive")
    return duration


def required_enrollment_take_count(catalog: PresetCatalog, pipeline_id: str) -> int:
    count = int(catalog.get(pipeline_id).enrollment_policy["utterance_count"])
    if count < 1:
        raise ValueError("matrix enrollment utterance_count must be positive")
    return count


def enrollment_display(value: Mapping[str, object]) -> EnrollmentDisplay:
    """Project non-biometric enrollment QC fields for explicit UI rendering."""

    takes: list[EnrollmentTakeDisplay] = []
    raw_takes = value.get("takes")
    if isinstance(raw_takes, Sequence) and not isinstance(raw_takes, (str, bytes)):
        for row in raw_takes:
            if not isinstance(row, Mapping):
                continue
            reasons = row.get("reason_codes")
            reason_codes = (
                tuple(str(reason) for reason in reasons)
                if isinstance(reasons, Sequence)
                and not isinstance(reasons, (str, bytes))
                else ()
            )
            takes.append(
                EnrollmentTakeDisplay(
                    prompt_id=str(row.get("prompt_id") or "take"),
                    duration_sec=float(row.get("duration_sec") or 0.0),
                    rms_dbfs=float(row.get("rms_dbfs") or 0.0),
                    peak_dbfs=float(row.get("peak_dbfs") or 0.0),
                    clipped_fraction=float(row.get("clipped_fraction") or 0.0),
                    status=str(row.get("status") or "unknown"),
                    reason_codes=reason_codes,
                )
            )
    repeat = value.get("repeat_prompt_ids")
    recommendations = value.get("recommendation_codes")
    backend = value.get("backend")
    backend_values = backend if isinstance(backend, Mapping) else {}
    consistency = value.get("within_enrollment_consistency")
    return EnrollmentDisplay(
        state=str(value.get("state") or "analyzed"),
        takes=tuple(takes),
        consistency=float(consistency) if consistency is not None else None,
        outlier_take_id=(
            str(value["outlier_take_id"])
            if value.get("outlier_take_id") is not None
            else None
        ),
        repeat_prompt_ids=(
            tuple(str(row) for row in repeat)
            if isinstance(repeat, Sequence) and not isinstance(repeat, (str, bytes))
            else ()
        ),
        recommendation_codes=(
            tuple(str(row) for row in recommendations)
            if isinstance(recommendations, Sequence)
            and not isinstance(recommendations, (str, bytes))
            else ()
        ),
        identity_summary=(
            f"backend {backend_values.get('backend_id') or value.get('backend_id') or '—'}, "
            f"model {backend_values.get('model_id') or '—'} / "
            f"{str(backend_values.get('model_sha256') or '—')[:12]}, profile "
            f"{value.get('profile_id') or 'not created'}"
        ),
    )


def selective_repeat_plan(
    payload: Mapping[str, object],
    *,
    display_label: str,
    repeat_prompt_ids: Sequence[str],
    fallback_pipeline_id: str,
) -> SelectiveRepeatPlan:
    """Retain accepted local takes and identify only the replacements needed."""

    repeat = tuple(dict.fromkeys(str(row) for row in repeat_prompt_ids))
    raw_takes = payload.get("takes")
    takes = (
        tuple(row for row in raw_takes if isinstance(row, Mapping))
        if isinstance(raw_takes, Sequence) and not isinstance(raw_takes, (str, bytes))
        else ()
    )
    retained: dict[str, LabelledWav] = {}
    all_prompt_ids: list[str] = []
    for take in takes:
        prompt_id = str(take.get("prompt_id") or "")
        if not prompt_id:
            continue
        all_prompt_ids.append(prompt_id)
        local_path = take.get("local_audio_path")
        if prompt_id not in repeat and local_path:
            retained[prompt_id] = LabelledWav(
                prompt_id=prompt_id,
                prompt_text=str(take.get("prompt_text") or "Imported labelled take"),
                path=Path(str(local_path)),
            )
    return SelectiveRepeatPlan(
        pipeline_id=str(payload.get("pipeline_id") or fallback_pipeline_id),
        display_label=display_label,
        speaker_id=str(payload.get("speaker_id") or ""),
        all_prompt_ids=tuple(all_prompt_ids),
        repeat_prompt_ids=repeat,
        retained=retained,
    )


def merge_selective_replacements(
    plan: SelectiveRepeatPlan,
    replacements: Sequence[LabelledWav],
) -> tuple[LabelledWav, ...]:
    if tuple(row.prompt_id for row in replacements) != plan.repeat_prompt_ids:
        raise ValueError(
            "replacement prompt IDs do not match the selective repeat plan"
        )
    combined = dict(plan.retained)
    combined.update({row.prompt_id: row for row in replacements})
    if set(combined) != set(plan.all_prompt_ids):
        raise ValueError("selective repeat did not produce a complete prompt set")
    return tuple(combined[prompt_id] for prompt_id in plan.all_prompt_ids)


@dataclass(frozen=True)
class _TaskResult:
    key: str
    value: object | None
    error: BaseException | None
    on_success: Callable[[object], None]
    on_error: Callable[[BaseException], None]


class BackgroundTaskRunner:
    """Small model-neutral bridge from daemon work to the Tk thread."""

    def __init__(self) -> None:
        self._completed: queue.Queue[_TaskResult] = queue.Queue()
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self._closed = False

    def submit(
        self,
        key: str,
        action: Callable[[], object],
        on_success: Callable[[object], None],
        on_error: Callable[[BaseException], None],
    ) -> bool:
        """Start one keyed action; duplicate in-flight keys are coalesced."""

        with self._lock:
            if self._closed or key in self._pending:
                return False
            self._pending.add(key)

        def run() -> None:
            value: object | None = None
            error: BaseException | None = None
            try:
                value = action()
            except BaseException as exc:
                error = exc
            self._completed.put(
                _TaskResult(
                    key=key,
                    value=value,
                    error=error,
                    on_success=on_success,
                    on_error=on_error,
                )
            )

        threading.Thread(
            target=run,
            name=f"full-pipeline-demo-{key}",
            daemon=True,
        ).start()
        return True

    def pending(self, key: str) -> bool:
        with self._lock:
            return key in self._pending

    def drain(self, *, limit: int = 64) -> int:
        """Run completed callbacks on the caller (the Tk) thread."""

        count = 0
        while count < limit:
            try:
                result = self._completed.get_nowait()
            except queue.Empty:
                break
            with self._lock:
                self._pending.discard(result.key)
            if result.error is None:
                result.on_success(result.value)
            else:
                result.on_error(result.error)
            count += 1
            with self._lock:
                if self._closed:
                    break
        return count

    def close(self) -> None:
        with self._lock:
            self._closed = True


class FullPipelineDemoApp:
    """Maintainable Tk shell over the fixed H2 product runtime pair."""

    def __init__(
        self,
        root: tk.Misc,
        *,
        catalog: PresetCatalog,
        session_manager: DemoSessionManager,
        enrollment_service: EnrollmentService,
        device_enumerator: Callable[[], Sequence[AudioInputDevice]] = (
            enumerate_input_devices
        ),
        task_runner: BackgroundTaskRunner | None = None,
    ) -> None:
        self.root = root
        self.catalog = catalog
        self.session_manager = session_manager
        self.enrollment_service = enrollment_service
        self.device_enumerator = device_enumerator
        self.tasks = task_runner or BackgroundTaskRunner()
        self.view_state = DemoViewState()
        self._active_session_id: str | None = None
        self._devices: tuple[AudioInputDevice, ...] = ()
        self._device_by_display: dict[str, AudioInputDevice] = {}
        self._last_logged_sequence = 0
        self._research_line_count = 0
        self._closing = False
        self._last_user_transcript = ""
        self._session_started_monotonic: float | None = None
        self._profile_id_by_item: dict[str, str] = {}
        self._profile_state_by_item: dict[str, str] = {}
        self._pending_enrollment: SelectiveRepeatPlan | None = None

        self._create_variables()
        self._configure_window()
        self._build_widgets()
        self._populate_presets()
        self._render_state()
        self.refresh_devices()
        self.refresh_profiles()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(POLL_INTERVAL_MS, self._tick)

    def _create_variables(self) -> None:
        self.selected_preset_id = tk.StringVar(master=self.root)
        default_mode = h2_product_mode(
            getattr(
                self.session_manager,
                "default_product_mode",
                H2_DEFAULT_PRODUCT_MODE,
            )
        )
        self.selected_product_mode = tk.StringVar(
            master=self.root,
            value=h2_mode_display_values()[
                next(
                    index
                    for index, row in enumerate(H2_PRODUCT_MODES)
                    if row.mode_id == default_mode.mode_id
                )
            ],
        )
        self.product_mode_summary = tk.StringVar(
            master=self.root, value=default_mode.summary
        )
        self.transcript_reset_policy = tk.StringVar(
            master=self.root, value="preserve"
        )
        self.preset_summary = tk.StringVar(master=self.root)
        configuration_status = getattr(
            self.session_manager,
            "scientific_configuration_status",
            "ENGINEERING_BASELINE_NOT_FINAL",
        )
        self.status_message = tk.StringVar(
            master=self.root,
            value=f"Ready · {configuration_status}",
        )
        self.processing_state = tk.StringVar(master=self.root, value="idle")
        self.session_identity = tk.StringVar(master=self.root, value="No session")
        self.device_name = tk.StringVar(master=self.root)
        self.source_rate = tk.StringVar(master=self.root, value="16000")
        self.source_channels = tk.StringVar(master=self.root, value="1")
        self.live_duration = tk.StringVar(master=self.root, value="30")
        self.record_live_audio = tk.BooleanVar(master=self.root, value=False)
        self.file_path = tk.StringVar(master=self.root)
        self.file_pace = tk.StringVar(master=self.root, value="1.0")
        self.file_duration = tk.StringVar(master=self.root)
        self.play_file_audio = tk.BooleanVar(master=self.root, value=False)
        self.export_root = tk.StringVar(master=self.root)
        self.include_input_audio = tk.BooleanVar(master=self.root, value=False)
        self.enrollment_label = tk.StringVar(master=self.root)
        self.enrollment_speaker_id = tk.StringVar(master=self.root)
        self.enrollment_message = tk.StringVar(
            master=self.root,
            value="Profiles and enrollment audio remain local and biometric-sensitive.",
        )
        self.enrollment_details = tk.StringVar(master=self.root)
        self.metric_audio = tk.StringVar(master=self.root, value="0.00 s")
        self.metric_elapsed = tk.StringVar(master=self.root, value="0.00 s")
        self.metric_rtf = tk.StringVar(master=self.root, value="—")
        self.metric_queue = tk.StringVar(master=self.root, value="0")
        self.metric_drops = tk.StringVar(master=self.root, value="0")
        self.metric_asr = tk.StringVar(master=self.root, value="waiting")
        self.metric_segmentation = tk.StringVar(master=self.root, value="waiting")
        self.metric_identity = tk.StringVar(master=self.root, value="—")
        self.metric_resources = tk.StringVar(master=self.root, value="—")
        self.metric_last_event = tk.StringVar(master=self.root, value="—")
        self.inspector_closest = tk.StringVar(master=self.root, value="—")
        self.inspector_top1 = tk.StringVar(master=self.root, value="—")
        self.inspector_top2 = tk.StringVar(master=self.root, value="—")
        self.inspector_margin = tk.StringVar(master=self.root, value="—")
        self.inspector_evidence = tk.StringVar(master=self.root, value="—")
        self.inspector_quality = tk.StringVar(master=self.root, value="—")
        self.inspector_backend = tk.StringVar(master=self.root, value="—")
        self.inspector_checkpoint = tk.StringVar(master=self.root, value="—")
        self.inspector_cluster = tk.StringVar(master=self.root, value="—")
        self.inspector_decision = tk.StringVar(master=self.root, value="—")
        self.inspector_warnings = tk.StringVar(master=self.root, value="none")
        self.warning_message = tk.StringVar(master=self.root)

    def _configure_window(self) -> None:
        self.root.winfo_toplevel().title("Just-Peachy · H2 Streaming Product Demo")
        self.root.winfo_toplevel().geometry("1320x900")
        self.root.winfo_toplevel().minsize(980, 700)
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Anchor.Treeview", background="#eef8ee")
        style.configure("Danger.TLabel", foreground="#8b1a1a")
        style.configure("Local.TLabel", foreground="#215b32")

    def _build_widgets(self) -> None:
        shell = ttk.Frame(self.root, padding=10)
        shell.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        shell.rowconfigure(2, weight=1)
        shell.columnconfigure(0, weight=1)

        self._build_preset_panel(shell)
        self._build_mode_panel(shell)
        self._build_output_panel(shell)
        self._build_status_bar(shell)

    def _build_preset_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="H2 product configuration", padding=8)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)
        title = (
            "Fixed speaker architecture: Pyannote Segmentation 3.0 + "
            "ReDimNet2-B2 diarization and identity"
        )
        ttk.Label(frame, text=title).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="AG-H2 is primary · AO-H2 is fallback/reference",
            style="Local.TLabel",
        ).grid(row=0, column=1, sticky="e")
        columns = ("asr", "diarization", "identity", "hybrid", "status")
        self.preset_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            height=2,
            selectmode="browse",
        )
        widths = (210, 240, 210, 65, 285)
        headings = ("ASR", "Diarization", "Identity", "Hybrid", "Decision status")
        for name, heading, width in zip(columns, headings, widths, strict=True):
            self.preset_tree.heading(name, text=heading)
            self.preset_tree.column(name, width=width, minwidth=60, stretch=True)
        self.preset_tree.tag_configure("anchor", background="#e9f7ea")
        self.preset_tree.tag_configure("challenger", background="#f6f6f6")
        scrollbar = ttk.Scrollbar(
            frame, orient="vertical", command=self.preset_tree.yview
        )
        self.preset_tree.configure(yscrollcommand=scrollbar.set)
        self.preset_tree.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 2))
        scrollbar.grid(row=1, column=2, sticky="ns", pady=(5, 2))
        self.preset_tree.bind("<<TreeviewSelect>>", self._on_preset_selected)
        ttk.Label(
            frame,
            textvariable=self.preset_summary,
            wraplength=1180,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        mode_controls = ttk.Frame(frame)
        mode_controls.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        mode_controls.columnconfigure(3, weight=1)
        ttk.Label(mode_controls, text="Speaker-label mode").grid(
            row=0, column=0, sticky="w", padx=(0, 4)
        )
        self.product_mode_combo = ttk.Combobox(
            mode_controls,
            textvariable=self.selected_product_mode,
            values=h2_mode_display_values(),
            state="readonly",
            width=52,
        )
        self.product_mode_combo.grid(row=0, column=1, sticky="w", padx=(0, 10))
        self.product_mode_combo.bind(
            "<<ComboboxSelected>>", self._on_product_mode_selected
        )
        ttk.Label(
            mode_controls,
            textvariable=self.product_mode_summary,
            wraplength=700,
        ).grid(row=0, column=3, sticky="ew")

    def _build_mode_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)
        self.mode_notebook = ttk.Notebook(frame)
        self.mode_notebook.grid(row=0, column=0, sticky="ew")
        self.live_tab = ttk.Frame(self.mode_notebook, padding=8)
        self.file_tab = ttk.Frame(self.mode_notebook, padding=8)
        self.enrollment_tab = ttk.Frame(self.mode_notebook, padding=8)
        self.mode_notebook.add(self.live_tab, text="Live microphone")
        self.mode_notebook.add(self.file_tab, text="File replay")
        self.mode_notebook.add(self.enrollment_tab, text="Enrollment")
        self.mode_notebook.bind("<<NotebookTabChanged>>", self._on_mode_changed)
        self._build_live_tab()
        self._build_file_tab()
        self._build_enrollment_tab()

        controls = ttk.Frame(frame, padding=(0, 6, 0, 0))
        controls.grid(row=1, column=0, sticky="ew")
        self.start_button = ttk.Button(controls, text="Start", command=self.start)
        self.pause_button = ttk.Button(controls, text="Pause", command=self.pause)
        self.resume_button = ttk.Button(controls, text="Resume", command=self.resume)
        self.stop_button = ttk.Button(controls, text="Stop", command=self.stop)
        for column, widget in enumerate(
            (
                self.start_button,
                self.pause_button,
                self.resume_button,
                self.stop_button,
            )
        ):
            widget.grid(row=0, column=column, padx=(0, 6))
        ttk.Separator(controls, orient="vertical").grid(
            row=0, column=4, sticky="ns", padx=8
        )
        ttk.Label(controls, text="Export folder").grid(row=0, column=5, padx=(0, 4))
        ttk.Entry(controls, textvariable=self.export_root, width=34).grid(
            row=0, column=6, sticky="ew"
        )
        ttk.Button(controls, text="Browse", command=self._browse_export).grid(
            row=0, column=7, padx=4
        )
        ttk.Checkbutton(
            controls,
            text="Include input WAV",
            variable=self.include_input_audio,
        ).grid(row=0, column=8, padx=4)
        self.export_button = ttk.Button(controls, text="Export", command=self.export)
        self.export_button.grid(row=0, column=9, padx=(4, 0))
        controls.columnconfigure(6, weight=1)

    def _build_live_tab(self) -> None:
        tab = self.live_tab
        ttk.Label(tab, text="Input device").grid(row=0, column=0, sticky="w")
        self.live_device_combo = ttk.Combobox(
            tab, textvariable=self.device_name, state="readonly", width=58
        )
        self.live_device_combo.grid(row=0, column=1, sticky="ew", padx=5)
        self.live_device_combo.bind("<<ComboboxSelected>>", self._on_device_selected)
        ttk.Button(tab, text="Refresh devices", command=self.refresh_devices).grid(
            row=0, column=2, padx=5
        )
        ttk.Label(tab, text="Native rate (Hz)").grid(row=0, column=3, padx=(12, 2))
        ttk.Entry(tab, textvariable=self.source_rate, width=9).grid(row=0, column=4)
        ttk.Label(tab, text="Channels").grid(row=0, column=5, padx=(12, 2))
        ttk.Entry(tab, textvariable=self.source_channels, width=5).grid(row=0, column=6)
        ttk.Label(tab, text="Duration (s)").grid(row=0, column=7, padx=(12, 2))
        ttk.Entry(tab, textvariable=self.live_duration, width=7).grid(row=0, column=8)
        ttk.Checkbutton(
            tab,
            text="Record local input WAV",
            variable=self.record_live_audio,
        ).grid(row=0, column=9, padx=(12, 0))
        tab.columnconfigure(1, weight=1)

    def _build_file_tab(self) -> None:
        tab = self.file_tab
        ttk.Label(tab, text="Audio file").grid(row=0, column=0, sticky="w")
        ttk.Entry(tab, textvariable=self.file_path).grid(
            row=0, column=1, sticky="ew", padx=5
        )
        ttk.Button(tab, text="Browse WAV/audio", command=self._browse_file).grid(
            row=0, column=2, padx=5
        )
        ttk.Label(tab, text="Pace").grid(row=0, column=3, padx=(12, 2))
        ttk.Combobox(
            tab,
            textvariable=self.file_pace,
            values=("0", "0.5", "1.0", "1.5", "2.0"),
            width=7,
        ).grid(row=0, column=4)
        ttk.Label(tab, text="Limit (s, optional)").grid(row=0, column=5, padx=(12, 2))
        ttk.Entry(tab, textvariable=self.file_duration, width=9).grid(row=0, column=6)
        ttk.Checkbutton(
            tab,
            text="Play exact source audio",
            variable=self.play_file_audio,
        ).grid(row=0, column=7, padx=(12, 0))
        tab.columnconfigure(1, weight=1)

    def _build_enrollment_tab(self) -> None:
        tab = self.enrollment_tab
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(5, weight=1)
        ttk.Label(
            tab,
            text=(
                "LOCAL ONLY · Enrollment audio and biometric templates are never "
                "uploaded by this application."
            ),
            style="Local.TLabel",
        ).grid(row=0, column=0, columnspan=7, sticky="w", pady=(0, 5))
        ttk.Label(tab, text="Display name").grid(row=1, column=0, sticky="w")
        ttk.Entry(tab, textvariable=self.enrollment_label).grid(
            row=1, column=1, sticky="ew", padx=(4, 10)
        )
        ttk.Label(tab, text="Speaker ID (optional)").grid(row=1, column=2)
        ttk.Entry(tab, textvariable=self.enrollment_speaker_id, width=22).grid(
            row=1, column=3, padx=4
        )
        ttk.Label(tab, text="Input device").grid(row=1, column=4, padx=(10, 2))
        self.enrollment_device_combo = ttk.Combobox(
            tab, textvariable=self.device_name, state="readonly", width=38
        )
        self.enrollment_device_combo.grid(row=1, column=5, sticky="ew", padx=4)
        self.enrollment_device_combo.bind(
            "<<ComboboxSelected>>", self._on_device_selected
        )
        ttk.Label(
            tab,
            text="Prompts: "
            + "  •  ".join(value.text for value in DEFAULT_ENROLLMENT_PROMPTS),
            wraplength=1180,
        ).grid(row=2, column=0, columnspan=7, sticky="w", pady=5)

        buttons = ttk.Frame(tab)
        buttons.grid(row=3, column=0, columnspan=7, sticky="ew", pady=(2, 5))
        ttk.Button(
            buttons, text="Record prompted takes", command=self.record_enrollment
        ).grid(row=0, column=0, padx=(0, 5))
        self.import_enrollment_button = ttk.Button(
            buttons,
            text="Analyze labelled WAVs",
            command=self.import_enrollment,
        )
        self.import_enrollment_button.grid(row=0, column=1, padx=5)
        self.cancel_repeat_button = ttk.Button(
            buttons,
            text="Cancel selective repeat",
            command=self.cancel_enrollment_repeat,
            state="disabled",
        )
        self.cancel_repeat_button.grid(row=0, column=2, padx=5)
        ttk.Button(
            buttons, text="Rebuild selected", command=self.rebuild_enrollment
        ).grid(row=0, column=3, padx=5)
        ttk.Button(
            buttons, text="Remove selected", command=self.remove_enrollment
        ).grid(row=0, column=4, padx=5)
        ttk.Button(
            buttons, text="Refresh profiles", command=self.refresh_profiles
        ).grid(row=0, column=5, padx=5)
        ttk.Label(buttons, textvariable=self.enrollment_message).grid(
            row=0, column=6, sticky="e", padx=(12, 0)
        )
        buttons.columnconfigure(6, weight=1)

        columns = ("label", "backend", "state", "version", "identity", "profile")
        self.profile_tree = ttk.Treeview(
            tab, columns=columns, show="headings", height=4, selectmode="browse"
        )
        for name, heading, width in (
            ("label", "Name", 150),
            ("backend", "Backend", 190),
            ("state", "State", 90),
            ("version", "Version", 70),
            ("identity", "Model / config identity", 230),
            ("profile", "Profile ID", 430),
        ):
            self.profile_tree.heading(name, text=heading)
            self.profile_tree.column(name, width=width, stretch=True)
        self.profile_tree.grid(row=4, column=0, columnspan=7, sticky="ew")

        take_columns = (
            "prompt",
            "duration",
            "rms",
            "peak",
            "clipping",
            "status",
            "reasons",
        )
        self.enrollment_take_tree = ttk.Treeview(
            tab,
            columns=take_columns,
            show="headings",
            height=3,
            selectmode="none",
        )
        for name, heading, width in (
            ("prompt", "Take / prompt", 120),
            ("duration", "Duration", 80),
            ("rms", "RMS dBFS", 85),
            ("peak", "Peak dBFS", 85),
            ("clipping", "Clipped", 75),
            ("status", "QC status", 110),
            ("reasons", "Reason codes", 430),
        ):
            self.enrollment_take_tree.heading(name, text=heading)
            self.enrollment_take_tree.column(name, width=width, stretch=True)
        self.enrollment_take_tree.grid(
            row=5, column=0, columnspan=7, sticky="ew", pady=(5, 0)
        )
        ttk.Label(
            tab,
            textvariable=self.enrollment_details,
            wraplength=1180,
        ).grid(row=6, column=0, columnspan=7, sticky="w", pady=(5, 0))

    def _build_output_panel(self, parent: ttk.Frame) -> None:
        self.view_notebook = ttk.Notebook(parent)
        self.view_notebook.grid(row=2, column=0, sticky="nsew")
        user = ttk.Frame(self.view_notebook, padding=8)
        research = ttk.Frame(self.view_notebook, padding=8)
        self.view_notebook.add(user, text="User view")
        self.view_notebook.add(research, text="Research / embedding inspector")
        user.rowconfigure(2, weight=1)
        user.columnconfigure(0, weight=1)
        ttk.Label(
            user,
            textvariable=self.session_identity,
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        actions = ttk.Frame(user)
        actions.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(actions, text="Reset Session", command=self.reset_session).grid(
            row=0, column=0, padx=(0, 5)
        )
        ttk.Button(
            actions,
            text="Clear Anonymous Memory",
            command=self.clear_anonymous_memory,
        ).grid(row=0, column=1, padx=5)
        ttk.Separator(actions, orient="vertical").grid(
            row=0, column=2, sticky="ns", padx=8
        )
        ttk.Radiobutton(
            actions,
            text="Preserve Transcript",
            value="preserve",
            variable=self.transcript_reset_policy,
            command=self.preserve_transcript,
        ).grid(row=0, column=3, padx=5)
        ttk.Radiobutton(
            actions,
            text="Delete Transcript on Reset",
            value="delete",
            variable=self.transcript_reset_policy,
        ).grid(row=0, column=4, padx=5)
        ttk.Button(
            actions,
            text="Delete Transcript Now",
            command=self.delete_transcript,
        ).grid(row=0, column=5, padx=5)
        ttk.Button(
            actions,
            text="Manage Enrolled Speakers",
            command=self.manage_enrolled_speakers,
        ).grid(row=0, column=6, padx=(12, 0))

        user_content = ttk.Panedwindow(user, orient="horizontal")
        user_content.grid(row=2, column=0, sticky="nsew")
        transcript_frame = ttk.Frame(user_content)
        roster_frame = ttk.LabelFrame(
            user_content, text="Active session participants", padding=5
        )
        user_content.add(transcript_frame, weight=3)
        user_content.add(roster_frame, weight=1)
        transcript_frame.rowconfigure(0, weight=1)
        transcript_frame.columnconfigure(0, weight=1)
        self.transcript_text = scrolledtext.ScrolledText(
            transcript_frame,
            wrap="word",
            height=14,
            state="disabled",
            font=("Segoe UI", 12),
        )
        self.transcript_text.tag_configure("known", foreground="#165a2b")
        self.transcript_text.tag_configure("tentative", foreground="#7a5900")
        self.transcript_text.tag_configure("unknown", foreground="#304c76")
        self.transcript_text.grid(row=0, column=0, sticky="nsew")

        roster_columns = ("label", "state", "cluster", "last_seen")
        self.roster_tree = ttk.Treeview(
            roster_frame,
            columns=roster_columns,
            show="headings",
            height=12,
            selectmode="none",
        )
        for name, heading, width in (
            ("label", "Participant", 140),
            ("state", "State", 90),
            ("cluster", "Cluster", 100),
            ("last_seen", "Last seen", 80),
        ):
            self.roster_tree.heading(name, text=heading)
            self.roster_tree.column(name, width=width, stretch=True)
        self.roster_tree.grid(row=0, column=0, sticky="nsew")
        roster_frame.rowconfigure(0, weight=1)
        roster_frame.columnconfigure(0, weight=1)
        ttk.Label(
            roster_frame,
            text=(
                "Session-local only. The known-only mode deliberately omits "
                "persistent anonymous participants."
            ),
            wraplength=360,
        ).grid(row=1, column=0, sticky="ew", pady=(5, 0))
        ttk.Label(user, textvariable=self.warning_message, style="Danger.TLabel").grid(
            row=3, column=0, sticky="ew", pady=(5, 0)
        )

        research.rowconfigure(2, weight=1)
        research.columnconfigure(0, weight=1)
        metrics = ttk.Frame(research)
        metrics.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        metric_rows = (
            ("State", self.processing_state),
            ("Elapsed", self.metric_elapsed),
            ("Audio", self.metric_audio),
            ("RTF", self.metric_rtf),
            ("Queue", self.metric_queue),
            ("Drops", self.metric_drops),
            ("ASR", self.metric_asr),
            ("Segmentation", self.metric_segmentation),
            ("Identity evidence", self.metric_identity),
            ("Resources", self.metric_resources),
            ("Last event", self.metric_last_event),
        )
        for index, (label, variable) in enumerate(metric_rows):
            column = (index % 4) * 2
            row = index // 4
            ttk.Label(metrics, text=f"{label}:").grid(
                row=row, column=column, sticky="e", padx=(8, 2)
            )
            ttk.Label(metrics, textvariable=variable).grid(
                row=row, column=column + 1, sticky="w", padx=(0, 8)
            )
        inspector = ttk.LabelFrame(
            research,
            text="Embedding inspector · raw technical evidence (never probability)",
            padding=6,
        )
        inspector.grid(row=1, column=0, sticky="ew", pady=(2, 6))
        inspector_rows = (
            ("Closest enrolled identity", self.inspector_closest),
            ("Raw cosine Top-1", self.inspector_top1),
            ("Raw cosine Top-2", self.inspector_top2),
            ("Top-1 − Top-2 margin", self.inspector_margin),
            ("Evidence duration", self.inspector_evidence),
            ("Quality gate", self.inspector_quality),
            ("Embedding backend/model", self.inspector_backend),
            ("Checkpoint SHA-256", self.inspector_checkpoint),
            ("Cluster", self.inspector_cluster),
            ("Decision", self.inspector_decision),
            ("Technical warnings", self.inspector_warnings),
        )
        for index, (label, variable) in enumerate(inspector_rows):
            row = index // 3
            column = (index % 3) * 2
            ttk.Label(inspector, text=f"{label}:").grid(
                row=row, column=column, sticky="e", padx=(8, 2), pady=1
            )
            ttk.Label(inspector, textvariable=variable).grid(
                row=row, column=column + 1, sticky="w", padx=(0, 8), pady=1
            )
        inspector_actions = ttk.Frame(inspector)
        inspector_actions.grid(
            row=(len(inspector_rows) + 2) // 3,
            column=0,
            columnspan=6,
            sticky="ew",
            pady=(5, 0),
        )
        ttk.Button(
            inspector_actions,
            text="Import sample through H2 runtime",
            command=self.select_inspector_sample,
        ).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(
            inspector_actions,
            text="Record sample through H2 runtime",
            command=self.record_inspector_sample,
        ).grid(row=0, column=1, padx=5)
        ttk.Label(
            inspector_actions,
            text=(
                "The inspector reuses the selected full runtime and latest "
                "IdentityEvidenceEvent; it owns no model logic."
            ),
        ).grid(row=0, column=2, sticky="w", padx=(12, 0))

        self.event_log = scrolledtext.ScrolledText(
            research, wrap="none", height=12, state="disabled", font=("Consolas", 9)
        )
        self.event_log.grid(row=2, column=0, sticky="nsew")

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(bar, textvariable=self.status_message).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(bar, textvariable=self.processing_state).grid(
            row=0, column=1, sticky="e"
        )
        bar.columnconfigure(0, weight=1)

    def _populate_presets(self) -> None:
        for value in h2_preset_table_rows(self.catalog):
            self.preset_tree.insert(
                "",
                "end",
                iid=value.preset_id,
                values=(
                    value.asr,
                    value.diarization,
                    value.identity,
                    value.hybrid,
                    value.status,
                ),
                tags=("anchor" if value.highlighted else "challenger",),
            )
        selected = self.catalog.default_h2_preset_id
        self.preset_tree.selection_set(selected)
        self.preset_tree.focus(selected)
        self.preset_tree.see(selected)
        self._select_preset(selected)

    def _on_preset_selected(self, _event: object | None = None) -> None:
        selection = self.preset_tree.selection()
        if selection:
            self._select_preset(str(selection[0]))

    def _select_preset(self, preset_id: str) -> None:
        require_h2_pipeline_id(preset_id)
        preset = self.catalog.get(preset_id)
        self.selected_preset_id.set(preset_id)
        warnings = ", ".join(preset.warning_codes) or "none"
        threshold = (
            f"{preset.frozen_score_threshold:.6f}"
            if preset.frozen_score_threshold is not None
            else "unresolved"
        )
        self.preset_summary.set(
            f"{h2_pipeline_role(preset_id)} · {preset.display_name} · raw-score "
            f"threshold {threshold} · warnings: {warnings}"
        )
        if self._pending_enrollment is None:
            count = required_enrollment_take_count(self.catalog, preset_id)
            self.import_enrollment_button.configure(
                text=f"Analyze exactly {count} labelled WAVs"
            )

    def _on_product_mode_selected(self, _event: object | None = None) -> None:
        try:
            mode = h2_product_mode(self._required_product_mode_id())
        except ValueError as exc:
            self._show_error("Speaker-label mode", exc)
            return
        self.product_mode_summary.set(mode.summary)
        self.status_message.set(
            f"Selected {mode.mode_id}; it will be frozen for the next session"
        )

    def _required_product_mode_id(self) -> str:
        return h2_mode_id_from_display(self.selected_product_mode.get())

    def _on_mode_changed(self, _event: object | None = None) -> None:
        enrollment = self._mode() == "enrollment"
        self.start_button.configure(state="disabled" if enrollment else "normal")

    def _mode(self) -> str:
        selected = self.mode_notebook.select()
        if selected == str(self.file_tab):
            return "file"
        if selected == str(self.enrollment_tab):
            return "enrollment"
        return "live"

    def manage_enrolled_speakers(self) -> None:
        self.mode_notebook.select(self.enrollment_tab)
        self.view_notebook.select(0)
        self.status_message.set("Enrollment profiles are local and backend-bound")

    def select_inspector_sample(self) -> None:
        value = filedialog.askopenfilename(
            parent=self.root,
            title="Select a sample for the H2 embedding inspector",
            filetypes=(
                ("Audio", "*.wav *.flac *.ogg *.aiff *.aif"),
                ("All files", "*.*"),
            ),
        )
        if not value:
            return
        self.file_path.set(value)
        self.file_pace.set("1.0")
        self.mode_notebook.select(self.file_tab)
        self.view_notebook.select(1)
        self.status_message.set(
            "Inspector sample selected. Press Start to process it through the "
            "same H2 streaming runtime."
        )

    def record_inspector_sample(self) -> None:
        self.live_duration.set("10")
        self.mode_notebook.select(self.live_tab)
        self.view_notebook.select(1)
        self.status_message.set(
            "Inspector recording prepared for 10 seconds. Press Start and speak "
            "through the selected microphone."
        )

    def preserve_transcript(self) -> None:
        self.transcript_reset_policy.set("preserve")
        self.status_message.set(
            "Reset Session will preserve visible transcript text while clearing "
            "volatile identity state."
        )

    def reset_session(self) -> None:
        preserve = self.transcript_reset_policy.get() == "preserve"
        if self._active_session_id is None:
            self.view_state = reset_session_projection(
                self.view_state, preserve_transcript=preserve
            )
            self._last_user_transcript = ""
            self._render_state()
            self.status_message.set("Local empty-session view reset")
            return
        if not messagebox.askyesno(
            "Reset session",
            (
                "Clear all session-local anonymous profiles and identity mappings? "
                "Permanent enrolled speakers will not be deleted. "
                + (
                    "The transcript will be preserved."
                    if preserve
                    else "The transcript will be deleted."
                )
            ),
            parent=self.root,
        ):
            return
        session_id = self._active_session_id
        self.status_message.set("Requesting verified runtime session reset…")
        self.tasks.submit(
            "session-privacy-control",
            lambda: self.session_manager.reset_session(
                session_id, preserve_transcript=preserve
            ),
            lambda value: self._session_reset_complete(
                value, preserve_transcript=preserve
            ),
            lambda exc: self._show_error("Reset Session", exc),
        )

    def _session_reset_complete(
        self,
        value: object,
        *,
        preserve_transcript: bool,
    ) -> None:
        self.view_state = reset_session_projection(
            self.view_state, preserve_transcript=preserve_transcript
        )
        self._last_user_transcript = ""
        if not preserve_transcript:
            self._clear_event_log()
            self._research_line_count = 0
            self._last_logged_sequence = self.view_state.last_event_sequence
        if isinstance(value, Mapping):
            self._consume_status(value)
        self._render_state()
        self.status_message.set(
            "Session-local memory reset; permanent enrolled profiles preserved"
        )

    def clear_anonymous_memory(self) -> None:
        if self._active_session_id is None:
            self.view_state = clear_anonymous_memory_projection(self.view_state)
            self._render_state()
            self.status_message.set("No active runtime; local anonymous view cleared")
            return
        session_id = self._active_session_id
        self.status_message.set("Requesting verified anonymous-memory clear…")
        self.tasks.submit(
            "session-privacy-control",
            lambda: self.session_manager.clear_anonymous_memory(
                session_id, preserve_transcript=True
            ),
            self._anonymous_memory_cleared,
            lambda exc: self._show_error("Clear Anonymous Memory", exc),
        )

    def _anonymous_memory_cleared(self, value: object) -> None:
        self.view_state = clear_anonymous_memory_projection(self.view_state)
        if isinstance(value, Mapping):
            self._consume_status(value)
        self._last_user_transcript = ""
        self._render_state()
        self.status_message.set(
            "Anonymous session memory cleared; enrolled profiles preserved"
        )

    def delete_transcript(self) -> None:
        self.transcript_reset_policy.set("delete")
        if self._active_session_id is None:
            self.view_state = reset_session_projection(
                self.view_state, preserve_transcript=False
            )
            self._last_user_transcript = ""
            self._clear_event_log()
            self._research_line_count = 0
            self._render_state()
            self.status_message.set("Visible transcript deleted")
            return
        self.reset_session()

    def refresh_devices(self) -> None:
        self.status_message.set("Discovering local input devices…")
        self.tasks.submit(
            "devices",
            lambda: tuple(self.device_enumerator()),
            self._devices_loaded,
            lambda exc: self._show_error("Device discovery", exc),
        )

    def _devices_loaded(self, value: object) -> None:
        devices = tuple(value) if isinstance(value, Sequence) else ()
        self._devices = tuple(
            row for row in devices if isinstance(row, AudioInputDevice)
        )
        self._device_by_display = {row.display_name: row for row in self._devices}
        names = tuple(self._device_by_display)
        self.live_device_combo.configure(values=names)
        self.enrollment_device_combo.configure(values=names)
        if names:
            if self.device_name.get() not in self._device_by_display:
                self.device_name.set(names[0])
            self._on_device_selected()
            self.status_message.set(f"Found {len(names)} input device(s)")
        else:
            self.device_name.set("")
            self.status_message.set("No local input device is available")

    def _on_device_selected(self, _event: object | None = None) -> None:
        device = self._device_by_display.get(self.device_name.get())
        if device is not None:
            self.source_rate.set(str(device.sample_rate_hz))
            self.source_channels.set(str(min(2, device.maximum_input_channels)))

    def _selected_device(self) -> AudioInputDevice | None:
        return self._device_by_display.get(self.device_name.get())

    def _browse_file(self) -> None:
        value = filedialog.askopenfilename(
            parent=self.root,
            title="Select source audio",
            filetypes=(
                ("Audio", "*.wav *.flac *.ogg *.aiff *.aif"),
                ("All files", "*.*"),
            ),
        )
        if value:
            self.file_path.set(value)

    def _browse_export(self) -> None:
        value = filedialog.askdirectory(parent=self.root, title="Select export folder")
        if value:
            self.export_root.set(value)

    def start(self) -> None:
        try:
            preset_id = self._required_preset_id()
            product_mode = self._required_product_mode_id()
            if self._mode() == "file":
                path = Path(self.file_path.get().strip()).resolve()
                pace = parse_pace(self.file_pace.get())
                duration = parse_optional_duration(self.file_duration.get())
                play_audio = self.play_file_audio.get()

                def action() -> object:
                    method = (
                        self.session_manager.switch_file
                        if self.session_manager.active
                        else self.session_manager.start_file
                    )
                    return method(
                        pipeline_id=preset_id,
                        input_path=path,
                        pace=pace,
                        play_audio=play_audio,
                        duration_sec=duration,
                        product_mode=product_mode,
                    )

            else:
                duration = parse_optional_duration(self.live_duration.get())
                if duration is None:
                    raise ValueError("live duration is required")
                device = self._selected_device()
                rate = int(self.source_rate.get())
                channels = int(self.source_channels.get())
                if rate <= 0 or channels <= 0:
                    raise ValueError("microphone rate and channels must be positive")
                if device is not None and channels > device.maximum_input_channels:
                    raise ValueError("channels exceed the selected device capability")
                record_input_audio = self.record_live_audio.get()

                def action() -> object:
                    method = (
                        self.session_manager.switch_microphone
                        if self.session_manager.active
                        else self.session_manager.start_microphone
                    )
                    return method(
                        pipeline_id=preset_id,
                        duration_sec=duration,
                        device=device.index if device is not None else None,
                        source_sample_rate_hz=rate,
                        source_channels=channels,
                        record_input_audio=record_input_audio,
                        product_mode=product_mode,
                    )

            self.status_message.set("Starting immutable runtime session…")
            self.tasks.submit(
                "session-control", action, self._session_started, self._session_error
            )
        except (OSError, TypeError, ValueError) as exc:
            self._show_error("Start session", exc)

    def _session_started(self, value: object) -> None:
        if not isinstance(value, Mapping):
            self._show_error("Start session", RuntimeError("invalid session response"))
            return
        self._active_session_id = str(value.get("session_id") or "") or None
        self.view_state = DemoViewState(
            session_id=self._active_session_id,
            pipeline_id=str(value.get("pipeline_id") or "") or None,
            product_mode=(str(value.get("product_mode") or "") or None),
            processing_state=str(value.get("state") or "queued"),
        )
        self._last_logged_sequence = 0
        self._research_line_count = 0
        self._clear_event_log()
        self._last_user_transcript = ""
        self._session_started_monotonic = time.monotonic()
        self.status_message.set(f"Session {self._active_session_id} started")
        self._render_state()

    def pause(self) -> None:
        self._session_control("pause", self.session_manager.pause)

    def resume(self) -> None:
        self._session_control("resume", self.session_manager.resume)

    def stop(self) -> None:
        self._session_control("stop", self.session_manager.stop)

    def _session_control(
        self, label: str, operation: Callable[[str | None], object]
    ) -> None:
        if self._active_session_id is None:
            self.status_message.set("No active session")
            return
        session_id = self._active_session_id
        self.status_message.set(f"Requesting {label}…")
        self.tasks.submit(
            "session-control",
            lambda: operation(session_id),
            lambda value: self._consume_status(value)
            if isinstance(value, Mapping)
            else None,
            self._session_error,
        )

    def _poll_session(self) -> None:
        session_id = self._active_session_id
        if session_id is None or self.tasks.pending("session-poll"):
            return
        after_sequence = self.view_state.last_event_sequence

        def action() -> object:
            payload = self.session_manager.poll_updates(session_id)
            if payload.get("requires_event_resync"):
                cursor = self.session_manager.open_event_cursor(
                    session_id, after_sequence=after_sequence
                )
                payload["resync_events"] = cursor.read_available(limit=4096)
            return payload

        self.tasks.submit(
            "session-poll", action, self._consume_update_batch, self._session_error
        )

    def _consume_update_batch(self, value: object) -> None:
        if not isinstance(value, Mapping):
            return
        resync = value.get("resync_events")
        if isinstance(resync, Sequence) and not isinstance(resync, (str, bytes)):
            for event in resync:
                if isinstance(event, Mapping):
                    self._consume_event(event)
        updates = value.get("updates")
        if isinstance(updates, Sequence) and not isinstance(updates, (str, bytes)):
            for update in updates:
                if not isinstance(update, Mapping):
                    continue
                if update.get("kind") == "event" and isinstance(
                    update.get("event"), Mapping
                ):
                    self._consume_event(update["event"])  # type: ignore[arg-type]
                elif update.get("kind") == "status" and isinstance(
                    update.get("status"), Mapping
                ):
                    self._consume_status(update["status"])  # type: ignore[arg-type]
        self._render_state()

    def _consume_event(self, event: Mapping[str, object]) -> None:
        sequence = int(event.get("event_sequence") or 0)
        self.view_state = apply_event(self.view_state, event)
        capture = event.get("capture_timestamps")
        if isinstance(capture, Mapping) and capture.get("audio_end_sec") is not None:
            audio_end = float(capture["audio_end_sec"])
            self.view_state = replace(
                self.view_state,
                audio_processed_sec=max(self.view_state.audio_processed_sec, audio_end),
            )
        if sequence > self._last_logged_sequence:
            self._append_event_log(event)
            self._last_logged_sequence = sequence

    def _consume_status(self, status: Mapping[str, object]) -> None:
        runtime = status.get("runtime_status")
        merged = dict(runtime) if isinstance(runtime, Mapping) else {}
        merged["session_id"] = status.get("session_id") or merged.get("session_id")
        merged["pipeline_id"] = status.get("pipeline_id") or merged.get("pipeline_id")
        merged["product_mode"] = status.get("product_mode") or merged.get(
            "product_mode"
        )
        for key in (
            "scientific_runtime_configuration",
            "scientific_config_status",
            "scientific_config_path",
            "scientific_config_sha256",
            "runtime_tuning_identity_sha256",
            "final_scientific_validation",
        ):
            if key in status:
                merged[key] = status[key]
        control = str(status.get("control_state") or "")
        manager_state = str(status.get("state") or "")
        if control and control != "running":
            merged["state"] = control
        elif not merged.get("state"):
            merged["state"] = manager_state
        warnings = [str(row) for row in status.get("warnings", []) or []]
        warnings.extend(str(row) for row in merged.get("warnings", []) or [])
        failures = status.get("failures")
        errors = [str(row) for row in merged.get("errors", []) or []]
        if isinstance(failures, Sequence) and not isinstance(failures, (str, bytes)):
            for row in failures:
                if isinstance(row, Mapping):
                    errors.append(str(row.get("message") or row))
                else:
                    errors.append(str(row))
        merged["warnings"] = list(dict.fromkeys(warnings))
        merged["errors"] = list(dict.fromkeys(errors))
        merged.setdefault("elapsed_session_sec", self.view_state.elapsed_session_sec)
        merged.setdefault("audio_processed_sec", self.view_state.audio_processed_sec)
        merged.setdefault("realtime_factor", self.view_state.realtime_factor)
        self.view_state = apply_status(self.view_state, merged)
        if manager_state in TERMINAL_STATES:
            self.status_message.set(f"Session {manager_state}; results are ready")
        self._render_state()

    def _session_error(self, exc: BaseException) -> None:
        self._show_error("Runtime session", exc)
        self.view_state = replace(
            self.view_state,
            processing_state="failed",
            errors=(*self.view_state.errors, f"{type(exc).__name__}: {exc}"),
        )
        self._render_state()

    def export(self) -> None:
        if self._active_session_id is None:
            self._show_error("Export", RuntimeError("no session is selected"))
            return
        destination = self.export_root.get().strip()
        if not destination:
            self._browse_export()
            destination = self.export_root.get().strip()
        if not destination:
            return
        session_id = self._active_session_id
        include_audio = self.include_input_audio.get()
        self.status_message.set("Exporting completed session…")
        self.tasks.submit(
            "export",
            lambda: self.session_manager.export(
                Path(destination),
                session_id=session_id,
                include_input_audio=include_audio,
            ),
            lambda value: self.status_message.set(f"Export complete: {destination}"),
            lambda exc: self._show_error("Export", exc),
        )

    def _labelled_wavs(
        self,
        paths: Sequence[str],
        *,
        prompt_ids: Sequence[str] | None = None,
    ) -> tuple[LabelledWav, ...]:
        values: list[LabelledWav] = []
        for index, path in enumerate(paths, start=1):
            prompt_id = (
                str(prompt_ids[index - 1])
                if prompt_ids is not None
                else f"prompt_{index}"
            )
            prompt = next(
                (
                    row
                    for row in DEFAULT_ENROLLMENT_PROMPTS
                    if row.prompt_id == prompt_id
                ),
                None,
            )
            values.append(
                LabelledWav(
                    prompt_id=prompt_id,
                    prompt_text=prompt.text if prompt else "Imported labelled take",
                    path=Path(path),
                )
            )
        return tuple(values)

    def import_enrollment(self) -> None:
        try:
            pending = self._pending_enrollment
            pipeline_id = (
                pending.pipeline_id
                if pending is not None
                else self._required_preset_id()
            )
            required_count = required_enrollment_take_count(self.catalog, pipeline_id)
            prompt_ids = (
                pending.repeat_prompt_ids
                if pending is not None
                else tuple(f"prompt_{index}" for index in range(1, required_count + 1))
            )
        except (KeyError, TypeError, ValueError) as exc:
            self._show_error("Enrollment import", exc)
            return
        paths = filedialog.askopenfilenames(
            parent=self.root,
            title=(
                f"Select exactly {len(prompt_ids)} replacement WAV(s) for "
                + ", ".join(prompt_ids)
                if pending is not None
                else f"Select exactly {required_count} labelled WAVs in prompt order"
            ),
            filetypes=(("WAV audio", "*.wav"),),
        )
        if not paths:
            return
        try:
            if len(paths) != len(prompt_ids):
                raise ValueError(
                    f"this enrollment step requires exactly {len(prompt_ids)} WAV(s); "
                    f"selected {len(paths)}"
                )
            replacements = self._labelled_wavs(paths, prompt_ids=prompt_ids)
            if pending is None:
                label = self._required_enrollment_label()
                speaker = self.enrollment_speaker_id.get().strip() or None
                labelled = replacements
            else:
                label = pending.display_label
                speaker = pending.speaker_id
                labelled = merge_selective_replacements(pending, replacements)
        except (TypeError, ValueError) as exc:
            self._show_error("Enrollment import", exc)
            return
        self.enrollment_message.set(
            "Analyzing local WAVs before any embedding/profile creation…"
        )
        self.tasks.submit(
            "enrollment",
            lambda: self.enrollment_service.analyze(
                pipeline_id=pipeline_id,
                labelled_wavs=labelled,
                speaker_id=speaker,
            ),
            lambda draft: self._enrollment_analyzed(draft, label),
            lambda exc: self._show_error("Enrollment analysis", exc),
        )

    def record_enrollment(self) -> None:
        try:
            label = self._required_enrollment_label()
            pipeline_id = self._required_preset_id()
            device = self._selected_device()
            rate = int(self.source_rate.get())
            channels = int(self.source_channels.get())
            speaker = self.enrollment_speaker_id.get().strip() or None
        except (TypeError, ValueError) as exc:
            self._show_error("Enrollment recording", exc)
            return
        self._run_enrollment_action(
            "Recording prompted local takes; speak each displayed prompt…",
            lambda: self.enrollment_service.record(
                pipeline_id=pipeline_id,
                display_label=label,
                speaker_id=speaker,
                device=device.index if device is not None else None,
                source_sample_rate_hz=rate,
                source_channels=channels,
            ),
        )

    def rebuild_enrollment(self) -> None:
        profile_id = self._selected_profile_id()
        if profile_id is None:
            self.status_message.set("Select an active profile to rebuild")
            return
        paths = filedialog.askopenfilenames(
            parent=self.root,
            title="Select replacement labelled WAVs in prompt order",
            filetypes=(("WAV audio", "*.wav"),),
        )
        if not paths:
            return
        labelled = self._labelled_wavs(paths)
        pipeline_id = self._required_preset_id()
        self._run_enrollment_action(
            "Rebuilding local profile as a new immutable version…",
            lambda: self.enrollment_service.rebuild(
                profile_id=profile_id,
                pipeline_id=pipeline_id,
                labelled_wavs=labelled,
            ),
        )

    def remove_enrollment(self) -> None:
        profile_id = self._selected_profile_id()
        if profile_id is None:
            self.status_message.set("Select an active profile to remove")
            return
        if not messagebox.askyesno(
            "Archive enrollment profile",
            "Remove this profile from active matching? The protected store keeps an "
            "auditable local archive.",
            parent=self.root,
        ):
            return
        self._run_enrollment_action(
            "Archiving local profile…",
            lambda: self.enrollment_service.remove(profile_id),
        )

    def _run_enrollment_action(
        self, message: str, action: Callable[[], object]
    ) -> None:
        self.enrollment_message.set(message)
        self.tasks.submit(
            "enrollment",
            action,
            self._enrollment_complete,
            lambda exc: self._show_error("Enrollment", exc),
        )

    def _enrollment_analyzed(self, value: object, display_label: str) -> None:
        if not hasattr(value, "to_dict"):
            self._show_error(
                "Enrollment analysis", RuntimeError("invalid enrollment draft")
            )
            return
        payload = value.to_dict()
        if not isinstance(payload, Mapping):
            self._show_error(
                "Enrollment analysis", RuntimeError("invalid enrollment draft payload")
            )
            return
        failed = tuple(
            row.prompt_id
            for row in enrollment_display(payload).takes
            if row.status != "accepted"
        )
        analyzed_payload = {**dict(payload), "state": "technical_qc_analyzed"}
        if failed:
            analyzed_payload["repeat_prompt_ids"] = list(failed)
        self._render_enrollment_payload(analyzed_payload)
        if failed:
            self._set_pending_repeat(
                analyzed_payload,
                display_label=display_label,
                repeat_prompt_ids=failed,
            )
            self.enrollment_message.set(
                "No profile was created. Replace only: " + ", ".join(failed)
            )
            return
        self._clear_pending_repeat()
        self.enrollment_message.set(
            "Technical QC passed; creating the local backend-bound profile…"
        )
        self.tasks.submit(
            "enrollment",
            lambda: self.enrollment_service.create(
                draft=value, display_label=display_label
            ),
            self._enrollment_complete,
            lambda exc: self._show_error("Enrollment profile creation", exc),
        )

    def _enrollment_complete(self, value: object) -> None:
        payload = value.to_dict() if hasattr(value, "to_dict") else str(value)
        state = payload.get("state") if isinstance(payload, Mapping) else "complete"
        self.enrollment_message.set(f"Local enrollment operation: {state}")
        if isinstance(payload, Mapping):
            self._render_enrollment_payload(payload)
            repeat = enrollment_display(payload).repeat_prompt_ids
            if repeat:
                self._set_pending_repeat(
                    payload,
                    display_label=str(payload.get("display_label") or "Speaker"),
                    repeat_prompt_ids=repeat,
                )
                self.enrollment_message.set(
                    "Profile not created; selectively replace: " + ", ".join(repeat)
                )
            else:
                self._clear_pending_repeat()
        self.status_message.set(json.dumps(payload, sort_keys=True, default=str)[:500])
        self.refresh_profiles()

    def _render_enrollment_payload(self, payload: Mapping[str, object]) -> None:
        display = enrollment_display(payload)
        for item in self.enrollment_take_tree.get_children():
            self.enrollment_take_tree.delete(item)
        for index, take in enumerate(display.takes):
            self.enrollment_take_tree.insert(
                "",
                "end",
                iid=f"take_{index:04d}",
                values=(
                    take.prompt_id,
                    f"{take.duration_sec:.2f} s",
                    f"{take.rms_dbfs:.1f}",
                    f"{take.peak_dbfs:.1f}",
                    f"{take.clipped_fraction:.3%}",
                    take.status,
                    ", ".join(take.reason_codes) or "none",
                ),
            )
        details = [
            f"state {display.state}",
            (
                f"consistency {_format_float(display.consistency)}"
                if display.consistency is not None
                else "consistency —"
            ),
            f"outlier {display.outlier_take_id or 'none'}",
            (
                "repeat prompts " + ", ".join(display.repeat_prompt_ids)
                if display.repeat_prompt_ids
                else "repeat prompts none"
            ),
            (
                "recommendations " + ", ".join(display.recommendation_codes)
                if display.recommendation_codes
                else "recommendations none"
            ),
            display.identity_summary,
        ]
        self.enrollment_details.set(" | ".join(details))

    def _set_pending_repeat(
        self,
        payload: Mapping[str, object],
        *,
        display_label: str,
        repeat_prompt_ids: Sequence[str],
    ) -> None:
        self._pending_enrollment = selective_repeat_plan(
            payload,
            display_label=display_label,
            repeat_prompt_ids=repeat_prompt_ids,
            fallback_pipeline_id=self._required_preset_id(),
        )
        repeat = self._pending_enrollment.repeat_prompt_ids
        self.import_enrollment_button.configure(
            text=f"Replace {len(repeat)} failed take(s)"
        )
        self.cancel_repeat_button.configure(state="normal")

    def cancel_enrollment_repeat(self) -> None:
        self._clear_pending_repeat()
        self.enrollment_message.set(
            "Selective repeat cancelled; no profile was created"
        )

    def _clear_pending_repeat(self) -> None:
        self._pending_enrollment = None
        count = required_enrollment_take_count(self.catalog, self._required_preset_id())
        self.import_enrollment_button.configure(
            text=f"Analyze exactly {count} labelled WAVs"
        )
        self.cancel_repeat_button.configure(state="disabled")

    def refresh_profiles(self) -> None:
        self.tasks.submit(
            "profiles",
            lambda: tuple(self.enrollment_service.list()),
            self._profiles_loaded,
            lambda exc: self._show_error("Enrollment profiles", exc),
        )

    def _profiles_loaded(self, value: object) -> None:
        for item in self.profile_tree.get_children():
            self.profile_tree.delete(item)
        self._profile_id_by_item.clear()
        self._profile_state_by_item.clear()
        rows = value if isinstance(value, Sequence) else ()
        for index, row in enumerate(rows):
            profile_id = str(getattr(row, "profile_id", ""))
            if not profile_id:
                continue
            state = str(getattr(row, "state", "—"))
            item_id = f"profile_{index:04d}"
            self._profile_id_by_item[item_id] = profile_id
            self._profile_state_by_item[item_id] = state
            self.profile_tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    getattr(row, "display_label", None) or "—",
                    getattr(row, "backend_id", "—"),
                    state,
                    getattr(row, "profile_version", None) or "—",
                    (
                        f"{getattr(row, 'model_id', None) or '—'} / "
                        f"{str(getattr(row, 'model_sha256', None) or '—')[:12]} / "
                        f"{str(getattr(row, 'backend_config_sha256', None) or '—')[:12]}"
                    ),
                    profile_id,
                ),
            )
        self.enrollment_message.set(
            f"{len(self.profile_tree.get_children())} local profile record(s)"
        )

    def _selected_profile_id(self) -> str | None:
        selection = self.profile_tree.selection()
        if not selection:
            return None
        item = str(selection[0])
        if self._profile_state_by_item.get(item) != "active":
            return None
        return self._profile_id_by_item.get(item)

    def _required_preset_id(self) -> str:
        value = self.selected_preset_id.get().strip()
        if not value:
            raise ValueError("select a pipeline preset")
        self.catalog.get(value)
        return require_h2_pipeline_id(value)

    def _required_enrollment_label(self) -> str:
        value = self.enrollment_label.get().strip()
        if not value:
            raise ValueError("enter a display name for enrollment")
        return value

    def _render_state(self) -> None:
        state = self.view_state
        self.processing_state.set(state.processing_state)
        self.session_identity.set(
            f"Session: {state.session_id or '—'} · Preset: "
            f"{state.pipeline_id or '—'} · Mode: {state.product_mode or '—'} · "
            f"Config: {state.scientific_config_status or '—'} · Tuning: "
            f"{(state.runtime_tuning_identity_sha256 or '—')[:12]}"
        )
        self.metric_audio.set(f"{state.audio_processed_sec:.2f} s")
        self.metric_elapsed.set(f"{state.elapsed_session_sec:.2f} s")
        self.metric_rtf.set(
            f"{state.realtime_factor:.3f}" if state.realtime_factor is not None else "—"
        )
        self.metric_queue.set(
            f"{state.queue_depth} frame(s), max wait {state.queue_latency_sec:.3f} s"
        )
        self.metric_drops.set(str(state.dropped_frames))
        self.metric_asr.set(state.asr_state)
        self.metric_segmentation.set(state.segmentation_state)
        self.metric_identity.set(
            "raw {score_type} score {score} (not probability) · Top-1/Top-2 "
            "margin {margin} · evidence {evidence} · thresholds "
            "{score_threshold}/{margin_threshold}".format(
                score_type=state.score_type or "unspecified",
                score=_format_float(state.top1_raw_score),
                margin=_format_float(state.top1_top2_margin),
                evidence=_format_float(state.evidence_duration_sec),
                score_threshold=_format_float(state.score_threshold),
                margin_threshold=_format_float(state.margin_threshold),
            )
        )
        rss = (
            f"{state.process_rss_bytes / (1024**2):.1f} MiB"
            if state.process_rss_bytes is not None
            else "—"
        )
        self.metric_resources.set(
            f"CPU {_format_float(state.cpu_percent)}% · RAM "
            f"{_format_float(state.ram_percent)}% · process {rss}"
        )
        self.metric_last_event.set(
            f"#{state.last_event_sequence} {state.last_event_type or '—'}"
        )
        inspector = embedding_inspector_display(state)
        self.inspector_closest.set(inspector.closest_identity)
        self.inspector_top1.set(inspector.top1_raw_score)
        self.inspector_top2.set(inspector.top2_raw_score)
        self.inspector_margin.set(inspector.margin)
        self.inspector_evidence.set(inspector.evidence_duration)
        self.inspector_quality.set(inspector.quality)
        self.inspector_backend.set(inspector.backend_identity)
        self.inspector_checkpoint.set(inspector.checkpoint_identity)
        self.inspector_cluster.set(inspector.cluster_id)
        self.inspector_decision.set(inspector.decision)
        self.inspector_warnings.set(inspector.warnings)
        problems = [*state.warnings, *state.errors]
        self.warning_message.set(" · ".join(problems[-4:]))
        self._render_transcript()
        self._render_roster()
        active = state.processing_state not in TERMINAL_STATES and bool(
            self._active_session_id
        )
        paused = "pause" in state.processing_state
        self.pause_button.configure(
            state="normal" if active and not paused else "disabled"
        )
        self.resume_button.configure(
            state="normal" if active and paused else "disabled"
        )
        self.stop_button.configure(state="normal" if active else "disabled")
        self.export_button.configure(
            state="normal" if state.processing_state in TERMINAL_STATES else "disabled"
        )
        if self._mode() != "enrollment":
            self.start_button.configure(state="normal")

    def _render_transcript(self) -> None:
        rendered = self.view_state.user_transcript()
        if rendered == self._last_user_transcript:
            return
        self._last_user_transcript = rendered
        self.transcript_text.configure(state="normal")
        self.transcript_text.delete("1.0", "end")
        if self.view_state.transcript_spans:
            for span in self.view_state.transcript_spans:
                text = span.text.strip()
                if not text:
                    continue
                label = self.view_state.display_label_for(span)
                identity_state = self.view_state.identity_states.get(
                    span.anonymous_speaker_id or "", "unknown"
                )
                if identity_state == "tentative":
                    label = f"{label} (tentative)"
                elif identity_state == "confirmed":
                    label = f"{label} (confirmed)"
                tag = "known" if identity_state == "confirmed" else identity_state
                if tag not in {"known", "tentative", "unknown"}:
                    tag = "unknown"
                self.transcript_text.insert("end", f"{label}: ", tag)
                self.transcript_text.insert("end", text + "\n")
        else:
            self.transcript_text.insert("end", rendered)
        self.transcript_text.see("end")
        self.transcript_text.configure(state="disabled")

    def _render_roster(self) -> None:
        rows = roster_display_rows(self.view_state)
        expected = tuple(
            (
                row.participant_id,
                row.display_label,
                row.identity_state,
                row.cluster_id,
                row.last_seen,
            )
            for row in rows
        )
        observed = tuple(
            (
                str(item),
                *tuple(str(value) for value in self.roster_tree.item(item, "values")),
            )
            for item in self.roster_tree.get_children()
        )
        if expected == observed:
            return
        for item in self.roster_tree.get_children():
            self.roster_tree.delete(item)
        for row in rows:
            self.roster_tree.insert(
                "",
                "end",
                iid=row.participant_id,
                values=(
                    row.display_label,
                    row.identity_state,
                    row.cluster_id,
                    row.last_seen,
                ),
            )

    def _append_event_log(self, event: Mapping[str, object]) -> None:
        self.event_log.configure(state="normal")
        self.event_log.insert(
            "end", json.dumps(dict(event), sort_keys=True, default=str) + "\n"
        )
        self._research_line_count += 1
        while self._research_line_count > MAX_RESEARCH_EVENT_LINES:
            self.event_log.delete("1.0", "2.0")
            self._research_line_count -= 1
        self.event_log.see("end")
        self.event_log.configure(state="disabled")

    def _clear_event_log(self) -> None:
        self.event_log.configure(state="normal")
        self.event_log.delete("1.0", "end")
        self.event_log.configure(state="disabled")

    def _show_error(self, title: str, exc: BaseException) -> None:
        message = f"{type(exc).__name__}: {exc}"
        self.status_message.set(message)
        if not self._closing:
            messagebox.showerror(title, message, parent=self.root)

    def _tick(self) -> None:
        if self._closing and not self.tasks.pending("shutdown"):
            return
        try:
            self.tasks.drain()
            if not self._closing:
                if (
                    self._session_started_monotonic is not None
                    and self.view_state.processing_state not in TERMINAL_STATES
                ):
                    elapsed = max(
                        self.view_state.elapsed_session_sec,
                        time.monotonic() - self._session_started_monotonic,
                    )
                    rtf = (
                        elapsed / self.view_state.audio_processed_sec
                        if self.view_state.audio_processed_sec > 0
                        else self.view_state.realtime_factor
                    )
                    self.view_state = replace(
                        self.view_state,
                        elapsed_session_sec=elapsed,
                        realtime_factor=rtf,
                    )
                    self._render_state()
                self._poll_session()
        finally:
            if not self._closing or self.tasks.pending("shutdown"):
                self.root.after(POLL_INTERVAL_MS, self._tick)

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.status_message.set("Stopping local sessions…")
        self.tasks.submit(
            "shutdown",
            lambda: self.session_manager.shutdown(timeout_per_session=3.0),
            lambda _value: self._finish_close(),
            lambda _exc: self._finish_close(),
        )

    def _finish_close(self) -> None:
        self.tasks.close()
        self.root.destroy()


def _format_float(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "—"


def create_default_app(
    root: tk.Misc,
    *,
    runtime_config_path: Path | None = None,
    runtime_config_expected_sha256: str | None = None,
) -> FullPipelineDemoApp:
    """Build local services lazily without loading a model implementation."""

    from app.full_pipeline.factory import (
        DEFAULT_ENROLLMENT_ROOT,
        MATRIX_PATH,
        RUNTIME_CONFIG_PATH,
    )
    from app.full_pipeline.matrix import FullPipelineMatrix

    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    catalog = PresetCatalog(matrix)
    manager = DemoSessionManager(
        enrollment_root=DEFAULT_ENROLLMENT_ROOT,
        runtime_config_path=runtime_config_path,
        runtime_config_expected_sha256=runtime_config_expected_sha256,
    )
    enrollment = EnrollmentService(
        matrix=matrix,
        enrollment_root=DEFAULT_ENROLLMENT_ROOT,
    )
    return FullPipelineDemoApp(
        root,
        catalog=catalog,
        session_manager=manager,
        enrollment_service=enrollment,
    )


def launch_demo(
    *,
    runtime_config_path: Path | None = None,
    runtime_config_expected_sha256: str | None = None,
) -> None:
    """Open the local Tk application and enter its event loop."""

    root = tk.Tk()
    create_default_app(
        root,
        runtime_config_path=runtime_config_path,
        runtime_config_expected_sha256=runtime_config_expected_sha256,
    )
    root.mainloop()


DemoApplication = FullPipelineDemoApp


__all__ = [
    "BackgroundTaskRunner",
    "DemoApplication",
    "EmbeddingInspectorDisplay",
    "EnrollmentDisplay",
    "EnrollmentTakeDisplay",
    "FullPipelineDemoApp",
    "PresetTableRow",
    "RosterDisplayRow",
    "SelectiveRepeatPlan",
    "create_default_app",
    "enrollment_display",
    "embedding_inspector_display",
    "h2_preset_table_rows",
    "launch_demo",
    "merge_selective_replacements",
    "parse_optional_duration",
    "parse_pace",
    "preset_table_rows",
    "required_enrollment_take_count",
    "roster_display_rows",
    "selective_repeat_plan",
]
