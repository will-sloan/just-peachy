"""Responsive Tk desktop interface; all inference remains in PipelineEngine."""

from __future__ import annotations

import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .audio import input_devices
from .config import PipelineConfig
from .runtime import PipelineEngine
from .speakers import ProfileStore


class EdgeSpeechWindow:
    def __init__(self, root: tk.Tk, config: PipelineConfig) -> None:
        self.root = root
        self.config = config
        self.engine = PipelineEngine(config)
        self.devices: list[dict[str, object]] = []
        self.wav_path: Path | None = None
        self.ui_messages: queue.SimpleQueue[tuple[str, object]] = queue.SimpleQueue()
        self.last_partial = ""
        self.transcript_lines: list[str] = []
        self.overlap_active = False
        self.transcript_loading = False
        self.transcript_active = False
        self.transcript_mode = "transcription"
        self.transcript_elapsed_sec = 0.0
        self.enrollment_loading = False
        self.enrollment_active = False
        self.enrollment_finalizing = False
        self.enrollment_elapsed_sec = 0.0
        self._enrollment_error_seen: str | None = None

        root.title("Just Peachy Edge Speech — Sherpa Giga + H2")
        root.geometry("1120x760")
        root.minsize(920, 620)
        self._style()
        self._build()
        self._refresh_devices()
        self._refresh_profiles()
        self.root.after(75, self._poll)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Primary.TButton", padding=(14, 8))

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Edge Speech Pipeline", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Lossless audio journal • independent ASR and speaker lanes • local-only profiles").pack(anchor="w", pady=(2, 12))

        controls = ttk.Notebook(outer)
        controls.pack(fill="x")
        live = ttk.Frame(controls, padding=12)
        wav = ttk.Frame(controls, padding=12)
        enrollment = ttk.Frame(controls, padding=12)
        controls.add(live, text="Live microphone")
        controls.add(wav, text="WAV simulation")
        controls.add(enrollment, text="Speaker enrollment")

        ttk.Label(live, text="Input device").grid(row=0, column=0, sticky="w")
        self.device_var = tk.StringVar()
        self.device_box = ttk.Combobox(live, textvariable=self.device_var, state="readonly", width=66)
        self.device_box.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(3, 8))
        ttk.Button(live, text="Refresh", command=self._refresh_devices).grid(row=1, column=5, padx=(8, 0))
        ttk.Button(live, text="Start live", style="Primary.TButton", command=self._start_live).grid(row=2, column=0, sticky="w")
        ttk.Button(live, text="Pause", command=self.engine.pause).grid(row=2, column=1, padx=6)
        ttk.Button(live, text="Resume", command=self.engine.resume).grid(row=2, column=2)
        ttk.Button(live, text="Stop", command=self.engine.stop).grid(row=2, column=3, padx=6)
        live.columnconfigure(0, weight=1)

        self.wav_var = tk.StringVar(value="No WAV selected")
        ttk.Label(wav, textvariable=self.wav_var).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Button(wav, text="Choose WAV", command=self._choose_wav).grid(row=1, column=0, pady=(8, 0), sticky="w")
        self.realtime_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(wav, text="Real-time 1.0× playback", variable=self.realtime_var).grid(row=1, column=1, padx=10, pady=(8, 0))
        ttk.Button(wav, text="Process file", style="Primary.TButton", command=self._start_wav).grid(row=1, column=2, pady=(8, 0))
        ttk.Button(wav, text="Stop", command=self.engine.stop).grid(row=1, column=3, padx=6, pady=(8, 0))
        wav.columnconfigure(0, weight=1)

        ttk.Label(enrollment, text="Display name").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        ttk.Entry(enrollment, textvariable=self.name_var, width=30).grid(row=1, column=0, sticky="w", pady=(3, 8))
        self.enrollment_start_button = ttk.Button(
            enrollment,
            text="Start recording",
            style="Primary.TButton",
            command=self._start_enrollment_recording,
        )
        self.enrollment_start_button.grid(row=1, column=1, padx=8)
        self.enrollment_stop_button = ttk.Button(
            enrollment,
            text="Stop and create profile",
            command=self._stop_enrollment_recording,
            state="disabled",
        )
        self.enrollment_stop_button.grid(row=1, column=2, padx=(0, 8))
        ttk.Button(enrollment, text="Import WAV sample(s)", command=self._import_enrollment).grid(row=1, column=3)
        ttk.Label(enrollment, text="Profiles").grid(row=2, column=0, sticky="w", pady=(8, 2))
        self.profile_box = tk.Listbox(enrollment, height=4, width=90)
        self.profile_box.grid(row=3, column=0, columnspan=4, sticky="ew")
        ttk.Button(enrollment, text="Refresh profiles", command=self._refresh_profiles).grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Button(enrollment, text="Remove selected", command=self._remove_profile).grid(row=4, column=1, sticky="w", pady=(6, 0))
        enrollment.columnconfigure(0, weight=1)

        activity = ttk.Frame(outer, padding=(0, 10, 0, 2))
        activity.pack(fill="x")
        transcript_activity = ttk.Labelframe(
            activity, text="Transcription activity", padding=8
        )
        transcript_activity.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.transcript_activity_var = tk.StringVar(value="Ready")
        self.transcript_timer_var = tk.StringVar(value="00:00:00.0")
        ttk.Label(
            transcript_activity,
            textvariable=self.transcript_activity_var,
            style="Status.TLabel",
        ).pack(side="left")
        self.transcript_progress = ttk.Progressbar(
            transcript_activity, mode="indeterminate", length=90
        )
        self.transcript_progress.pack(side="left", padx=10)
        ttk.Label(
            transcript_activity,
            textvariable=self.transcript_timer_var,
            font=("Consolas", 12, "bold"),
        ).pack(side="right")

        enrollment_activity = ttk.Labelframe(
            activity, text="Enrollment activity", padding=8
        )
        enrollment_activity.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.enrollment_activity_var = tk.StringVar(value="Ready")
        self.enrollment_timer_var = tk.StringVar(value="00:00:00.0")
        ttk.Label(
            enrollment_activity,
            textvariable=self.enrollment_activity_var,
            style="Status.TLabel",
        ).pack(side="left")
        self.enrollment_progress = ttk.Progressbar(
            enrollment_activity, mode="indeterminate", length=90
        )
        self.enrollment_progress.pack(side="left", padx=10)
        ttk.Label(
            enrollment_activity,
            textvariable=self.enrollment_timer_var,
            font=("Consolas", 12, "bold"),
        ).pack(side="right")

        status_frame = ttk.Frame(outer, padding=(0, 12, 0, 8))
        status_frame.pack(fill="x")
        self.state_var = tk.StringVar(value="IDLE")
        self.speaker_var = tk.StringVar(value="Speaker: waiting")
        self.drop_var = tk.StringVar(value="Audio dropped: 0")
        self.queue_var = tk.StringVar(value="ASR lag 0.00 s • speaker lag 0.00 s")
        ttk.Label(status_frame, textvariable=self.state_var, style="Status.TLabel").pack(side="left")
        ttk.Separator(status_frame, orient="vertical").pack(side="left", fill="y", padx=12)
        ttk.Label(status_frame, textvariable=self.speaker_var).pack(side="left")
        ttk.Label(status_frame, textvariable=self.drop_var, foreground="#0a6b35").pack(side="right")
        ttk.Label(status_frame, textvariable=self.queue_var).pack(side="right", padx=14)

        panes = ttk.Panedwindow(outer, orient="horizontal")
        panes.pack(fill="both", expand=True)
        transcript_frame = ttk.Labelframe(panes, text="Transcript", padding=8)
        research_frame = ttk.Labelframe(panes, text="Research view", padding=8)
        panes.add(transcript_frame, weight=3)
        panes.add(research_frame, weight=2)
        self.transcript = tk.Text(transcript_frame, wrap="word", font=("Segoe UI", 12), state="disabled")
        self.transcript.pack(fill="both", expand=True)
        self.research = tk.Text(research_frame, wrap="word", font=("Consolas", 9), state="disabled")
        self.research.pack(fill="both", expand=True)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(8, 0))
        self.output_var = tk.StringVar(value="Session output will appear here")
        ttk.Label(footer, textvariable=self.output_var).pack(side="left")
        ttk.Button(footer, text="Clear display", command=self._clear_display).pack(side="right")

    def _selected_device(self) -> int | None:
        index = self.device_box.current()
        return int(self.devices[index]["index"]) if index >= 0 else None

    def _refresh_devices(self) -> None:
        try:
            self.devices = input_devices()
            labels = [f'{row["index"]}: {row["name"]} — {row["default_sample_rate"]} Hz, {row["channels"]} ch' for row in self.devices]
            self.device_box["values"] = labels
            if labels:
                self.device_box.current(0)
        except Exception as exc:
            messagebox.showerror("Microphone devices", str(exc))

    def _run_background(self, operation, *, success_kind: str = "ok") -> None:
        def run() -> None:
            try:
                result = operation()
                self.ui_messages.put((success_kind, result))
            except Exception as exc:
                self.ui_messages.put((f"{success_kind}_error", str(exc)))

        threading.Thread(target=run, daemon=True).start()

    def _start_live(self) -> None:
        if self.engine.state not in {"IDLE", "COMPLETED", "FAILED"}:
            messagebox.showinfo("Session running", "Stop the current session first.")
            return
        if self.enrollment_active or self.enrollment_loading or self.enrollment_finalizing:
            messagebox.showinfo("Enrollment active", "Finish enrollment first.")
            return
        self._begin_transcript_loading("live microphone")
        self._run_background(
            lambda: self.engine.start_live(self._selected_device()),
            success_kind="transcript_launched",
        )

    def _choose_wav(self) -> None:
        selected = filedialog.askopenfilename(filetypes=[("WAV audio", "*.wav"), ("Audio files", "*.wav *.flac")])
        if selected:
            self.wav_path = Path(selected)
            self.wav_var.set(selected)

    def _start_wav(self) -> None:
        if self.wav_path is None:
            messagebox.showinfo("Choose a file", "Choose a WAV file first.")
            return
        if self.engine.state not in {"IDLE", "COMPLETED", "FAILED"}:
            messagebox.showinfo("Session running", "Stop the current session first.")
            return
        if self.enrollment_active or self.enrollment_loading or self.enrollment_finalizing:
            messagebox.showinfo("Enrollment active", "Finish enrollment first.")
            return
        self._begin_transcript_loading("WAV transcription")
        self._run_background(
            lambda: self.engine.start_file(
                self.wav_path, realtime=self.realtime_var.get()
            ),
            success_kind="transcript_launched",
        )

    def _import_enrollment(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showinfo("Display name", "Enter the speaker's display name.")
            return
        if self.enrollment_active or self.enrollment_loading or self.enrollment_finalizing:
            messagebox.showinfo(
                "Enrollment active", "Stop the current enrollment recording first."
            )
            return
        selected = filedialog.askopenfilenames(filetypes=[("WAV audio", "*.wav")])
        if selected:
            self._begin_enrollment_loading("Loading WAV and building profile…")
            self._run_background(
                lambda: self.engine.enroll_files(
                    name, [Path(item) for item in selected]
                ),
                success_kind="enrollment_completed",
            )

    def _start_enrollment_recording(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showinfo("Display name", "Enter the speaker's display name.")
            return
        if self.engine.state not in {"IDLE", "COMPLETED", "FAILED"}:
            messagebox.showinfo("Stop live mode", "Stop the current speech session before recording enrollment.")
            return
        if self.enrollment_active or self.enrollment_loading or self.enrollment_finalizing:
            return
        self._begin_enrollment_loading("Opening microphone…")
        self.enrollment_start_button.configure(state="disabled")
        self._run_background(
            lambda: self.engine.start_enrollment_recording(
                name, device=self._selected_device()
            ),
            success_kind="enrollment_started",
        )

    def _stop_enrollment_recording(self) -> None:
        if not self.enrollment_active:
            return
        self.enrollment_active = False
        self.enrollment_finalizing = True
        self.enrollment_activity_var.set("Saving audio and building profile…")
        self.enrollment_progress.start(10)
        self.enrollment_stop_button.configure(state="disabled")
        self._run_background(
            self.engine.stop_enrollment_recording,
            success_kind="enrollment_completed",
        )

    def _begin_transcript_loading(self, mode: str) -> None:
        self.transcript_mode = mode
        self.transcript_loading = True
        self.transcript_active = False
        self.transcript_elapsed_sec = 0.0
        self.transcript_timer_var.set(self._format_duration(0.0))
        self.transcript_activity_var.set("Loading models and audio device…")
        self.transcript_progress.start(10)
        self.state_var.set("LOADING MODELS…")

    def _begin_enrollment_loading(self, label: str) -> None:
        self.enrollment_loading = True
        self.enrollment_finalizing = False
        self.enrollment_activity_var.set(label)
        self.enrollment_progress.start(10)

    @staticmethod
    def _format_duration(duration_sec: float) -> str:
        value = max(0.0, float(duration_sec))
        hours = int(value // 3600)
        minutes = int((value % 3600) // 60)
        seconds = value % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:04.1f}"

    def _refresh_profiles(self) -> None:
        self.profile_box.delete(0, "end")
        for row in ProfileStore(self.config.profile_root).list_metadata():
            self.profile_box.insert("end", f'{row.get("profile_id", "invalid")} | {row.get("display_name", "?")} | {row.get("quality_status", row.get("status", "?"))}')

    def _remove_profile(self) -> None:
        selection = self.profile_box.curselection()
        if not selection:
            return
        profile_id = self.profile_box.get(selection[0]).split("|", 1)[0].strip()
        ProfileStore(self.config.profile_root).remove(profile_id)
        self._refresh_profiles()

    def _poll(self) -> None:
        while not self.ui_messages.empty():
            kind, value = self.ui_messages.get()
            if kind.endswith("_error"):
                if kind.startswith("transcript_"):
                    self.transcript_loading = False
                    self.transcript_active = False
                    self.transcript_progress.stop()
                    self.transcript_activity_var.set("Failed to start")
                if kind.startswith("enrollment_"):
                    self.enrollment_loading = False
                    self.enrollment_active = False
                    self.enrollment_finalizing = False
                    self.enrollment_progress.stop()
                    self.enrollment_activity_var.set("Enrollment failed")
                    self.enrollment_start_button.configure(state="normal")
                    self.enrollment_stop_button.configure(state="disabled")
                messagebox.showerror("Operation failed", str(value))
            elif kind == "enrollment_started":
                self.enrollment_loading = False
                self.enrollment_active = True
                self.enrollment_finalizing = False
                self.enrollment_progress.stop()
                self.enrollment_activity_var.set("● Recording enrollment")
                self.enrollment_stop_button.configure(state="normal")
                self._enrollment_error_seen = None
            elif kind == "enrollment_completed" and isinstance(value, dict):
                self.enrollment_loading = False
                self.enrollment_active = False
                self.enrollment_finalizing = False
                self.enrollment_progress.stop()
                self.enrollment_activity_var.set("Enrollment complete")
                self.enrollment_start_button.configure(state="normal")
                self.enrollment_stop_button.configure(state="disabled")
                if "profile_id" in value:
                    messagebox.showinfo(
                        "Enrollment complete",
                        f'{value["display_name"]}: {value["quality_status"]}',
                    )
                    self._refresh_profiles()
            elif isinstance(value, Path):
                self.output_var.set(str(value))
        while not self.engine.events.empty():
            event = self.engine.events.get()
            data = event.to_jsonable()
            payload = data["payload"]
            if event.event_type == "source_started":
                self.transcript_loading = False
                self.transcript_active = True
                self.transcript_progress.stop()
                self.transcript_activity_var.set(
                    "● Live transcription"
                    if payload.get("mode") == "microphone"
                    else "● WAV transcription"
                )
            elif event.event_type == "session_completed":
                self.transcript_loading = False
                self.transcript_active = False
                self.transcript_progress.stop()
                self.transcript_activity_var.set("Transcription complete")
            elif event.event_type == "failure":
                self.transcript_loading = False
                self.transcript_active = False
                self.transcript_progress.stop()
                self.transcript_activity_var.set("Transcription failed")
            if event.event_type in {"transcript_partial", "transcript_final"}:
                text = str(payload.get("display_text", payload.get("text", "")))
                label = str(payload.get("speaker", "Speaker_?"))
                if event.event_type == "transcript_final":
                    self.transcript_lines.append(f"{label}: {text}")
                    self.last_partial = ""
                else:
                    self.last_partial = f"{label}: {text} …"
                self._render_transcript()
            if event.event_type == "segmentation":
                self.overlap_active = bool(payload.get("overlap", False))
                if self.overlap_active:
                    self.speaker_var.set(
                        "⚠ Overlap detected — attribution is uncertain"
                    )
                elif self.speaker_var.get().startswith("⚠"):
                    self.speaker_var.set("Speaker: waiting for next decision")
            if event.event_type == "speaker_decision" and not self.overlap_active:
                self.speaker_var.set(f'Speaker: {payload.get("display_label")} ({payload.get("state")})')
            self._append_research(json.dumps(data, ensure_ascii=False))
        telemetry = self.engine.telemetry()
        self.state_var.set(str(telemetry["state"]))
        if self.transcript_active:
            self.transcript_elapsed_sec = float(
                telemetry.get("source_duration_sec", 0.0)
            )
        self.transcript_timer_var.set(
            self._format_duration(self.transcript_elapsed_sec)
        )
        enrollment = self.engine.enrollment_recording_status()
        if self.enrollment_active:
            self.enrollment_elapsed_sec = float(
                enrollment.get("duration_sec", 0.0)
            )
            self.enrollment_timer_var.set(
                self._format_duration(self.enrollment_elapsed_sec)
            )
            error = enrollment.get("error")
            if error and str(error) != self._enrollment_error_seen:
                self._enrollment_error_seen = str(error)
                self.enrollment_active = False
                self.enrollment_progress.stop()
                self.enrollment_activity_var.set("Enrollment capture failed")
                self.enrollment_stop_button.configure(state="disabled")
                self.enrollment_start_button.configure(state="normal")
                self._run_background(
                    self.engine.cancel_enrollment_recording,
                    success_kind="enrollment_cancelled",
                )
                messagebox.showerror("Enrollment capture failed", str(error))
        dropped = int(telemetry.get("audio_frames_dropped", 0))
        overflows = int(telemetry.get("portaudio_input_overflows", 0)) + int(telemetry.get("raw_capture_reserve_failures", 0))
        self.drop_var.set(f"Audio dropped: {dropped} • capture faults: {overflows}")
        self.queue_var.set(f'ASR lag {float(telemetry.get("asr_lag_sec", 0)):.2f} s • speaker lag {float(telemetry.get("speaker_lag_sec", 0)):.2f} s')
        if telemetry.get("session_dir"):
            self.output_var.set(str(telemetry["session_dir"]))
        self.root.after(75, self._poll)

    def _render_transcript(self) -> None:
        content = "\n\n".join(self.transcript_lines + ([self.last_partial] if self.last_partial else []))
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.insert("1.0", content)
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def _append_research(self, line: str) -> None:
        self.research.configure(state="normal")
        self.research.insert("end", line + "\n")
        # Keep the GUI bounded even during long sessions; the full log stays on disk.
        if int(self.research.index("end-1c").split(".")[0]) > 1200:
            self.research.delete("1.0", "201.0")
        self.research.see("end")
        self.research.configure(state="disabled")

    def _clear_display(self) -> None:
        self.transcript_lines.clear()
        self.last_partial = ""
        self._render_transcript()
        self.research.configure(state="normal")
        self.research.delete("1.0", "end")
        self.research.configure(state="disabled")

    def _close(self) -> None:
        self.engine.stop()
        self.engine.cancel_enrollment_recording()
        self.root.destroy()


def run_gui(config: PipelineConfig | None = None) -> None:
    root = tk.Tk()
    EdgeSpeechWindow(root, config or PipelineConfig())
    root.mainloop()
