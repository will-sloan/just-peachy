"""Tkinter GUI for configuring and launching Evaluation Tool runs."""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app.dataset_registry.loader import load_filter_option_values
from app.dataset_registry.registry import get_dataset, list_datasets
from app.gui.launcher import BatchLauncher, BatchLaunchResult
from app.gui.preview import PreviewOnlyResult, generate_preview_only
from app.gui.state import (
    GuiRunConfig,
    RIR_LISTBOX_HEIGHT,
    all_selected_datasets_support_augmentation,
    augmentation_visibility,
    list_available_rirs,
    parse_max_recordings,
    parse_snr_values,
    validate_gui_config,
)
from app.gui.widgets import MultiSelectDropdown, VerticalScrolledFrame
from app.utils.paths import find_project_root, tool_root


class EvaluationToolGui(tk.Tk):
    """Small local GUI over the existing command-line pipeline."""

    def __init__(self, project_root: Path | None = None) -> None:
        super().__init__()
        self.title("Evaluation Tool")
        self.geometry("1120x780")
        self.project_root = find_project_root(project_root)
        self.tool_root = tool_root(self.project_root)
        self.launcher = BatchLauncher(self.tool_root, sys.executable)
        self.events: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.dataset_vars: dict[str, tk.BooleanVar] = {}
        self.filter_widgets: dict[str, dict[str, MultiSelectDropdown]] = {}
        self.filter_selections: dict[str, dict[str, tuple[str, ...]]] = {}
        self.filter_option_cache: dict[str, dict[str, list[str]]] = {}
        self.available_rirs: list[str] = []
        self.selected_preview_source_file: Path | None = None
        self._build_variables()
        self._build_layout()
        self._refresh_filter_controls()
        self._refresh_augmentation_controls()
        self.after(100, self._poll_events)

    def _build_variables(self) -> None:
        self.command_var = tk.StringVar(value="full")
        self.runner_var = tk.StringVar(value="simulation")
        self.simulation_mode_var = tk.StringVar(value="perfect")
        self.augmentation_var = tk.StringVar(value="none")
        self.noise_white_var = tk.BooleanVar(value=True)
        self.noise_pink_var = tk.BooleanVar(value=False)
        self.snr_var = tk.StringVar(value="20")
        self.max_recordings_var = tk.StringVar(value="10")
        self.run_name_var = tk.StringVar(value="gui_run")
        self.preview_var = tk.BooleanVar(value=False)
        self.preview_recording_var = tk.StringVar(value="")
        self.preview_source_file_var = tk.StringVar(value="No preview source file selected")
        for definition in list_datasets():
            self.dataset_vars[definition.key] = tk.BooleanVar(value=False)

    def _build_layout(self) -> None:
        scrolled = VerticalScrolledFrame(self, padding=12)
        scrolled.pack(fill=tk.BOTH, expand=True)
        main = scrolled.content
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self._build_dataset_box(left)
        self._build_runner_box(left)
        self._build_augmentation_box(left)
        self._build_run_options_box(left)
        self._build_filter_box(right)
        self._build_status_box(right)

    def _build_dataset_box(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Datasets", padding=10)
        box.pack(fill=tk.X, pady=(0, 10))
        for definition in list_datasets():
            ttk.Checkbutton(
                box,
                text=f"{definition.display_name} ({definition.key})",
                variable=self.dataset_vars[definition.key],
                command=self._on_dataset_selection_changed,
            ).pack(anchor=tk.W)

    def _build_runner_box(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Runner", padding=10)
        box.pack(fill=tk.X, pady=(0, 10))
        ttk.Radiobutton(
            box,
            text="Simulation",
            value="simulation",
            variable=self.runner_var,
            command=self._refresh_runner_controls,
        ).pack(anchor=tk.W)
        ttk.Radiobutton(
            box,
            text="External stub / real runner hook",
            value="external-stub",
            variable=self.runner_var,
            command=self._refresh_runner_controls,
        ).pack(anchor=tk.W)
        self.simulation_mode_frame = ttk.Frame(box)
        self.simulation_mode_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(self.simulation_mode_frame, text="Simulation mode").pack(anchor=tk.W)
        self.simulation_mode_combo = ttk.Combobox(
            self.simulation_mode_frame,
            textvariable=self.simulation_mode_var,
            values=("perfect", "noisy", "drop_some"),
            state="readonly",
        )
        self.simulation_mode_combo.pack(fill=tk.X)

    def _build_augmentation_box(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Augmentation", padding=10)
        box.pack(fill=tk.BOTH, pady=(0, 10))
        ttk.Label(box, text="Mode").pack(anchor=tk.W)
        self.augmentation_combo = ttk.Combobox(
            box,
            textvariable=self.augmentation_var,
            values=("none", "reverb", "noise", "reverb_noise"),
            state="readonly",
        )
        self.augmentation_combo.pack(fill=tk.X)
        self.augmentation_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_augmentation_controls())
        self.augmentation_note_var = tk.StringVar(value="")
        self.augmentation_note = ttk.Label(box, textvariable=self.augmentation_note_var, wraplength=300)
        self.augmentation_note.pack(anchor=tk.W, pady=(6, 0))

        self.rir_frame = ttk.LabelFrame(box, text="RIRs", padding=8)
        self.rir_frame.pack(fill=tk.BOTH, expand=False, pady=(8, 0))
        ttk.Label(
            self.rir_frame,
            text="Select one or more RIRs. The list is fixed-height and scrollable.",
        ).pack(anchor=tk.W)
        rir_list_frame = ttk.Frame(self.rir_frame)
        rir_list_frame.pack(fill=tk.X, pady=(4, 0))
        self.available_rirs = list_available_rirs(self.project_root)
        self.rir_listbox = tk.Listbox(
            rir_list_frame,
            selectmode=tk.EXTENDED,
            height=RIR_LISTBOX_HEIGHT,
            exportselection=False,
        )
        rir_scrollbar = ttk.Scrollbar(
            rir_list_frame,
            orient=tk.VERTICAL,
            command=self.rir_listbox.yview,
        )
        self.rir_listbox.configure(yscrollcommand=rir_scrollbar.set)
        self.rir_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        rir_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        for rir_name in self.available_rirs:
            self.rir_listbox.insert(tk.END, rir_name)
        self.rir_selected_var = tk.StringVar(value="0 RIRs selected")
        ttk.Label(self.rir_frame, textvariable=self.rir_selected_var).pack(anchor=tk.W, pady=(4, 0))
        self.rir_listbox.bind("<<ListboxSelect>>", lambda _event: self._refresh_rir_selection_label())
        if not self.available_rirs:
            ttk.Label(self.rir_frame, text="No RIR WAV files found.").pack(anchor=tk.W)

        self.noise_frame = ttk.LabelFrame(box, text="Noise", padding=8)
        self.noise_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Checkbutton(self.noise_frame, text="White", variable=self.noise_white_var).pack(anchor=tk.W)
        ttk.Checkbutton(self.noise_frame, text="Pink", variable=self.noise_pink_var).pack(anchor=tk.W)
        ttk.Label(self.noise_frame, text="SNR dB values, e.g. 5, 10, 20").pack(anchor=tk.W, pady=(6, 0))
        ttk.Entry(self.noise_frame, textvariable=self.snr_var).pack(fill=tk.X)

        self.preview_frame = ttk.LabelFrame(box, text="Preview", padding=8)
        self.preview_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Checkbutton(
            self.preview_frame,
            text="Also save preview audio during a full run",
            variable=self.preview_var,
            command=self._refresh_augmentation_controls,
        ).pack(anchor=tk.W)
        ttk.Button(
            self.preview_frame,
            text="Choose Preview Source Audio File...",
            command=self._choose_preview_source_file,
        ).pack(fill=tk.X, pady=(4, 0))
        ttk.Label(
            self.preview_frame,
            textvariable=self.preview_source_file_var,
            wraplength=300,
        ).pack(anchor=tk.W, pady=(4, 0))
        self.preview_recording_entry = ttk.Entry(
            self.preview_frame,
            textvariable=self.preview_recording_var,
        )
        ttk.Label(self.preview_frame, text="Optional preview recording_id").pack(anchor=tk.W)
        self.preview_recording_entry.pack(fill=tk.X)
        ttk.Button(
            self.preview_frame,
            text="Generate Preview Audio",
            command=self._generate_preview_audio,
        ).pack(fill=tk.X, pady=(6, 0))

    def _build_run_options_box(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Run Options", padding=10)
        box.pack(fill=tk.X)
        ttk.Label(box, text="Command").pack(anchor=tk.W)
        ttk.Combobox(
            box,
            textvariable=self.command_var,
            values=("full", "run"),
            state="readonly",
        ).pack(fill=tk.X)
        ttk.Label(box, text="Max recordings").pack(anchor=tk.W, pady=(8, 0))
        ttk.Entry(box, textvariable=self.max_recordings_var).pack(fill=tk.X)
        ttk.Label(box, text="Run name").pack(anchor=tk.W, pady=(8, 0))
        ttk.Entry(box, textvariable=self.run_name_var).pack(fill=tk.X)
        ttk.Button(box, text="Validate", command=self._validate_dialog).pack(fill=tk.X, pady=(10, 0))
        ttk.Button(box, text="Launch Run", command=self._launch).pack(fill=tk.X, pady=(6, 0))

    def _build_filter_box(self, parent: ttk.Frame) -> None:
        self.filter_outer = ttk.LabelFrame(parent, text="Subset Filters", padding=10)
        self.filter_outer.grid(row=0, column=0, sticky="ew")

    def _build_status_box(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Progress and Output", padding=10)
        box.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        box.rowconfigure(2, weight=1)
        box.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(box, textvariable=self.status_var).grid(row=0, column=0, sticky="ew")
        self.progress = ttk.Progressbar(box, mode="determinate")
        self.progress.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        self.log_text = tk.Text(box, height=22, wrap="word")
        self.log_text.grid(row=2, column=0, sticky="nsew")

    def _refresh_filter_controls(self) -> None:
        self._sync_filter_selections_from_widgets()
        self._close_filter_popups()
        for child in self.filter_outer.winfo_children():
            child.destroy()
        self.filter_widgets = {}
        selected = self._selected_dataset_keys()
        if not selected:
            ttk.Label(self.filter_outer, text="Select a dataset to show relevant filters.").pack(anchor=tk.W)
            return
        ttk.Label(
            self.filter_outer,
            text="Leave filters as Any to run the full dataset and save all grouped metrics.",
            wraplength=760,
        ).pack(anchor=tk.W, pady=(0, 8))
        for dataset_key in selected:
            definition = get_dataset(dataset_key)
            frame = ttk.LabelFrame(
                self.filter_outer,
                text=f"{definition.display_name} filters",
                padding=8,
            )
            frame.pack(fill=tk.X, pady=(0, 8))
            self.filter_widgets[definition.key] = {}
            try:
                option_values = self._filter_options_for(definition.key)
            except Exception as exc:
                ttk.Label(
                    frame,
                    text=f"Could not load filter values from normalized metadata: {exc}",
                    wraplength=720,
                ).pack(anchor=tk.W)
                continue
            for filter_name in definition.supported_subset_filters:
                row = ttk.Frame(frame)
                row.pack(fill=tk.X, pady=2)
                ttk.Label(row, text=filter_name, width=24).pack(side=tk.LEFT)
                values = option_values.get(filter_name, [])
                selected_values = self.filter_selections.get(definition.key, {}).get(filter_name, ())
                if values:
                    widget = MultiSelectDropdown(row, values, selected=selected_values)
                    widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    self.filter_widgets[definition.key][filter_name] = widget
                else:
                    ttk.Label(row, text="No values found in metadata").pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _refresh_runner_controls(self) -> None:
        if self.runner_var.get() == "simulation":
            self.simulation_mode_frame.pack(fill=tk.X, pady=(8, 0))
        else:
            self.simulation_mode_frame.forget()

    def _refresh_augmentation_controls(self) -> None:
        supports_augmentation = all_selected_datasets_support_augmentation(self._selected_dataset_keys())
        if not supports_augmentation:
            self.augmentation_var.set("none")
            self.preview_var.set(False)
            self.augmentation_combo.configure(state="disabled")
            self.augmentation_note_var.set(
                "Augmentation is available only for clean single-speaker datasets. "
                "AMI, VOiCES, and CHiME-6 runs use their original recorded audio."
            )
            self.rir_frame.forget()
            self.noise_frame.forget()
            self.preview_frame.forget()
            return

        self.augmentation_combo.configure(state="readonly")
        self.augmentation_note_var.set("")
        visibility = augmentation_visibility(self.augmentation_var.get(), self.preview_var.get())
        if visibility.show_rir_controls:
            self.rir_frame.pack(fill=tk.BOTH, expand=False, pady=(8, 0))
        else:
            self.rir_frame.forget()
        if visibility.show_noise_controls:
            self.noise_frame.pack(fill=tk.X, pady=(8, 0))
        else:
            self.noise_frame.forget()
        if visibility.show_preview_recording:
            self.preview_recording_entry.configure(state="normal")
        else:
            self.preview_recording_entry.configure(state="disabled")
        self.preview_frame.pack(fill=tk.X, pady=(8, 0))

    def _selected_dataset_keys(self) -> list[str]:
        return [key for key, var in self.dataset_vars.items() if var.get()]

    def _on_dataset_selection_changed(self) -> None:
        self._refresh_filter_controls()
        self._refresh_augmentation_controls()

    def _collect_config(self) -> GuiRunConfig:
        snr_values = parse_snr_values(self.snr_var.get())
        max_recordings = parse_max_recordings(self.max_recordings_var.get())
        self._sync_filter_selections_from_widgets()
        filters_by_dataset: dict[str, dict[str, tuple[str, ...]]] = {}
        for dataset_key in self._selected_dataset_keys():
            values: dict[str, tuple[str, ...]] = {}
            for filter_name, selected_values in self.filter_selections.get(dataset_key, {}).items():
                if selected_values:
                    values[filter_name] = selected_values
            filters_by_dataset[dataset_key] = values
        noise_types: list[str] = []
        if self.noise_white_var.get():
            noise_types.append("white")
        if self.noise_pink_var.get():
            noise_types.append("pink")
        rir_paths = self._selected_rir_paths()
        return GuiRunConfig(
            dataset_keys=tuple(self._selected_dataset_keys()),
            command=self.command_var.get(),
            runner=self.runner_var.get(),
            simulation_mode=self.simulation_mode_var.get(),
            augmentation=self.augmentation_var.get(),
            rir_paths=tuple(rir_paths),
            noise_types=tuple(noise_types),
            snr_db=snr_values,
            max_recordings=max_recordings,
            run_name=self.run_name_var.get().strip() or None,
            preview=self.preview_var.get(),
            preview_recording_id=self.preview_recording_var.get().strip() or None,
            filters_by_dataset=filters_by_dataset,
            project_root=self.project_root,
        )

    def _selected_rir_paths(self) -> list[str]:
        return [self.available_rirs[index] for index in self.rir_listbox.curselection()]

    def _refresh_rir_selection_label(self) -> None:
        selected = self._selected_rir_paths()
        if not selected:
            self.rir_selected_var.set("0 RIRs selected")
        elif len(selected) <= 2:
            self.rir_selected_var.set(f"{len(selected)} selected: {', '.join(selected)}")
        else:
            self.rir_selected_var.set(f"{len(selected)} selected: {', '.join(selected[:2])}, ...")

    def _filter_options_for(self, dataset_key: str) -> dict[str, list[str]]:
        if dataset_key not in self.filter_option_cache:
            self.filter_option_cache[dataset_key] = load_filter_option_values(
                self.project_root,
                get_dataset(dataset_key),
            )
        return self.filter_option_cache[dataset_key]

    def _sync_filter_selections_from_widgets(self) -> None:
        for dataset_key, widgets in self.filter_widgets.items():
            dataset_values = self.filter_selections.setdefault(dataset_key, {})
            for filter_name, widget in widgets.items():
                dataset_values[filter_name] = widget.get_selected()

    def _close_filter_popups(self) -> None:
        for widgets in self.filter_widgets.values():
            for widget in widgets.values():
                widget.close_popup()

    def _choose_preview_source_file(self) -> None:
        initial = self.project_root / "Raw Datasets (Not formatted)"
        path = filedialog.askopenfilename(
            title="Choose preview source audio",
            initialdir=str(initial if initial.exists() else self.project_root),
            filetypes=[
                ("Audio files", "*.wav *.flac"),
                ("WAV files", "*.wav"),
                ("FLAC files", "*.flac"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.selected_preview_source_file = Path(path)
            self.preview_source_file_var.set(str(self.selected_preview_source_file))

    def _generate_preview_audio(self) -> None:
        try:
            config = self._collect_config()
            errors = validate_gui_config(config)
            if errors:
                raise ValueError("\n".join(errors))
        except ValueError as exc:
            messagebox.showerror("Invalid preview configuration", str(exc))
            return

        self.status_var.set("Generating preview audio...")
        self.progress.configure(maximum=1, value=0)

        def worker() -> None:
            try:
                result = generate_preview_only(
                    config=config,
                    project_root=self.project_root,
                    selected_source_file=self.selected_preview_source_file,
                    on_line=lambda line: self.events.put(("line", line)),
                )
            except Exception as exc:  # pragma: no cover - GUI boundary
                self.events.put(("preview_done", (False, str(exc))))
            else:
                self.events.put(("preview_done", (True, result)))

        threading.Thread(target=worker, daemon=True).start()

    def _validate_dialog(self) -> bool:
        try:
            config = self._collect_config()
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return False
        errors = validate_gui_config(config)
        if errors:
            messagebox.showerror("Invalid run configuration", "\n".join(errors))
            return False
        commands = self.launcher.build_commands(config)
        messagebox.showinfo(
            "Configuration looks good",
            f"Ready to launch {len(commands)} run(s).\n\n"
            + "\n\n".join(" ".join(command) for command in commands[:3]),
        )
        return True

    def _launch(self) -> None:
        try:
            config = self._collect_config()
            errors = validate_gui_config(config)
            if errors:
                raise ValueError("\n".join(errors))
        except ValueError as exc:
            messagebox.showerror("Invalid run configuration", str(exc))
            return
        self.log_text.delete("1.0", tk.END)
        commands = self.launcher.build_commands(config)
        self.progress.configure(maximum=max(1, len(commands)), value=0)
        self.status_var.set(f"Launching {len(commands)} run(s)...")
        self.launcher.run_batch_async(config, self.events)

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "line":
                    self._append_log(str(payload))
                elif kind == "progress":
                    done, total, message = payload  # type: ignore[misc]
                    self.progress.configure(maximum=max(1, int(total)), value=int(done))
                    self.status_var.set(str(message))
                elif kind == "done":
                    result = payload
                    if isinstance(result, BatchLaunchResult):
                        self.status_var.set(result.message)
                        self.progress.configure(value=self.progress["maximum"] if result.success else self.progress["value"])
                        self._append_log(result.message)
                elif kind == "preview_done":
                    success, result = payload  # type: ignore[misc]
                    if success and isinstance(result, PreviewOnlyResult):
                        self.progress.configure(value=1)
                        self.status_var.set(f"Preview saved: {result.run_dir}")
                        self._append_log(f"Preview saved: {result.run_dir}")
                    else:
                        self.status_var.set("Preview generation failed")
                        self._append_log(f"Preview generation failed: {result}")
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _append_log(self, line: str) -> None:
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)


def launch_gui(project_root: Path | None = None) -> None:
    """Launch the tkinter GUI."""

    app = EvaluationToolGui(project_root=project_root)
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
