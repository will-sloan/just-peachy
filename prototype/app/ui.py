"""Portrait touch frontend; no model/audio/device ownership. See docs/UI_ITERATION.md."""
from __future__ import annotations

import ctypes
import json
import math
import os
from pathlib import Path
import re
import time
import tkinter as tk
from tkinter import font as tkfont, ttk
from typing import Any, Callable

from .casing import provisional_case
from .beam_diagnostics import BEAMS, arrow_tip
from .caption_display import IdentityLabels, continues, active_caption_rows, ActiveCaptionPane
from .backends import BASELINE_BACKEND_ID, backend_catalog, backend_status
from .enrollment_progress import VerifiedAnimation, reference_text
from .session_ui import SessionUI
from .roster_ui import RosterUI
from .seat_ui import SeatUI
from .text_assistance_ui import TextAssistanceUI
from .script_evidence_ui import ScriptEvidenceUI
from .noise_ui import NoiseUI
from .adaptation_ui import AdaptationUI
from .transcript_review_ui import TranscriptReviewUI
from .mode_policy import MODE_METADATA, SELECTED_MODES, NAMED_MODES, NUMBERED_MODES, SEAT_MODES

CONFIG = Path(__file__).resolve().parents[1] / "config" / "ui.json"
MODES = {key:(row['label'],row['description']) for key,row in MODE_METADATA.items()}
MODE_LEGEND = "✓ simulation-supported · ◇ experimental / real-world validation needed"


def prepare_dpi_awareness() -> dict[str, Any]:
    """Call before Tk() on Windows; changes this process, never global scaling."""
    result: dict[str, Any] = {"platform": os.name, "requested": False}
    if os.name == "nt":
        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
            result["requested"] = bool(user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)))
        except (AttributeError, OSError) as exc:
            result["error"] = str(exc)
    return result


class TouchScroll(tk.Frame):
    """Scrollable in-window page with large explicit scroll controls and dragging."""
    def __init__(self, parent: tk.Misc, ui: "PrototypeUI"):
        super().__init__(parent, bg=ui.color("background"))
        self.ui = ui
        self.canvas = tk.Canvas(self, bg=ui.color("background"), highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=ui.color("background"))
        self.window = self.canvas.create_window(0, 0, anchor="nw", window=self.inner)
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        rail = tk.Frame(self, bg=ui.color("background"), width=ui.px(48))
        rail.pack(side="right", fill="y"); rail.pack_propagate(False)
        ui.button(rail, "↑", lambda: self.canvas.yview_scroll(-3, "units")).pack(fill="x")
        scrollbar = ttk.Scrollbar(rail, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(fill="y", expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        ui.button(rail, "↓", lambda: self.canvas.yview_scroll(3, "units")).pack(fill="x")
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda _e: self.canvas.yview_scroll(-2, "units"))
        self.canvas.bind("<Button-5>", lambda _e: self.canvas.yview_scroll(2, "units"))
        self.canvas.bind("<ButtonPress-1>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B1-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))

    def _wheel(self, event: tk.Event) -> str:
        self.canvas.yview_scroll(-int(event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1), "units")
        return "break"


class PrototypeUI(TranscriptReviewUI,AdaptationUI,NoiseUI,ScriptEvidenceUI,TextAssistanceUI,SeatUI,RosterUI,SessionUI):
    """Thin controller-driven frontend. Construct on Tk's owning/main thread."""
    def __init__(self, root: tk.Tk, controller: Any, *, allow_auto_start: bool = True):
        self.root, self.controller = root, controller
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.preferences = dict(self.config["defaults"])
        # Display preferences do not start capture; the separate saved microphone
        # permission and auto-start choice must both be explicitly enabled.
        initial = controller.snapshot()
        settings = initial.get("settings", {}) if isinstance(initial, dict) else {}
        for key, choices in (("caption_size", self.config["caption_sizes_px"]),
                             ("theme", self.config["themes"]), ("preview_zoom", self.config["preview_zooms"]),
                             ("display_smoothing_ms", self.config["display_smoothing_ms"])):
            if settings.get(key) in choices:
                self.preferences[key] = settings[key]
        if isinstance(settings.get("spatial_visualization"), bool):
            self.preferences["spatial_visualization"] = settings["spatial_visualization"]
        if isinstance(settings.get("numbered_unknowns"), bool):
            self.preferences["numbered_unknowns"] = settings["numbered_unknowns"]
        self.zoom = float(self.preferences["preview_zoom"])
        self.snapshot: dict[str, Any] = {}
        self.page = "captions"
        self._closed = False
        self._closing = False
        self._poll_handle: str | None = None
        self._mic_consented = settings.get("microphone_preapproved") is True
        self._auto_start_pending = (allow_auto_start and self._mic_consented
                                    and settings.get("auto_start_listening") is True)
        self._row_cache: dict[str, tuple[str, str, bool]] = {}
        self._marks: dict[str, tuple[str, str]] = {}
        self._render_order: list[str] = []
        self._history_order: list[str] = []
        self._mark_number = 0
        self._follow_live = True
        self._identity_labels = IdentityLabels()
        self._display_handle = None
        self._pending_rows = None
        self._display_received = 0.0
        self.presentation_delays_ms = []  # Last 64 GUI batches; not model latency.
        self.presentation_receipts = []  # Bounded Tk application receipts, never scanout evidence.
        self._presentation_spans = {}
        self._presentation_values = {}
        self._nav_context = None
        self._people_signature = ""
        self._enroll_name = ""
        self._enroll_person_id: str | None = None
        self._enroll_target = 30
        self._enroll_consent = False
        self._enroll_started = False
        self._paragraph = self.config["enrollment_paragraph"]
        self._notice = ""
        self._spatial_signature = None
        self._spatial_rendered_at = 0.0
        self._page_update: Callable[[], None] | None = None
        self.client_metrics: dict[str, Any] = {}
        self.actions: dict[str, tk.Widget] = {}
        self.root.title("Just Peachy · portrait prototype")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.resizable(False, False)
        self._build()
        self._set_geometry()
        self.poll()
        self._auto_start_handle = None
        if self._auto_start_pending:
            self._auto_start_handle = self.root.after(250, self._auto_start_listening)

    def _cancel_auto_start_timer(self) -> None:
        if self._auto_start_handle is not None:
            self.root.after_cancel(self._auto_start_handle)
            self._auto_start_handle = None

    def _auto_start_listening(self) -> None:
        self._cancel_auto_start_timer()
        pending, self._auto_start_pending = self._auto_start_pending, False
        if (pending and not self._closed and not self._closing
                and self._mic_consented and self.page == "captions"
                and self.snapshot.get("state") in ("IDLE", "STOPPED")
                and not self.snapshot.get("error")):
            self.toggle_listening()

    def px(self, value: float) -> int:
        return max(1, round(value * self.zoom))

    def color(self, key: str) -> str:
        return self.config["themes"][self.preferences.get("theme", "Dark")][key]

    def font(self, size: int | str = "body_font_px", bold: bool = False) -> tuple:
        pixels = self.config[size] if isinstance(size, str) else size
        return (self.config["font_family"], -self.px(pixels), "bold" if bold else "normal")

    def button(self, parent: tk.Misc, text: str, command: Callable, *, accent: bool = False,
               key: str | None = None, height: int = 48, wrap: int | None = None) -> tk.Frame:
        frame = tk.Frame(parent, bg=self.color("background"), height=self.px(height))
        frame.pack_propagate(False); frame.grid_propagate(False)
        button = tk.Button(frame, text=text, command=command, font=self.font(),
            bg=self.color("accent" if accent else "raised"), fg=self.color("accent_text" if accent else "text"),
            activebackground=self.color("selected"), activeforeground=self.color("text"),
            relief="flat", borderwidth=0, highlightthickness=1, highlightbackground=self.color("border"),
            takefocus=True, wraplength=self.px(wrap or 390), cursor="hand2", overrelief="raised")
        button.pack(fill="both", expand=True)
        self._bind_page_scroll(button)
        frame.button = button  # type: ignore[attr-defined]
        if key:
            self.actions[key] = button
        return frame

    def label(self, parent: tk.Misc, text: str = "", *, muted: bool = False,
              size: int | str = "body_font_px", bold: bool = False, **kwargs: Any) -> tk.Label:
        label = tk.Label(parent, text=text, font=self.font(size, bold), bg=self.color("background"),
            fg=self.color("muted" if muted else "text"), anchor="w", justify="left", wraplength=self.px(390), **kwargs)
        self._bind_page_scroll(label, drag=True)
        return label

    @staticmethod
    def _bind_page_scroll(widget: tk.Widget, drag: bool = False) -> None:
        parent = widget.master
        while parent is not None and not isinstance(parent, TouchScroll):
            parent = parent.master
        if isinstance(parent, TouchScroll):
            canvas = parent.canvas
            widget.bind("<MouseWheel>", parent._wheel)
            widget.bind("<Button-4>", lambda _e: canvas.yview_scroll(-2, "units"))
            widget.bind("<Button-5>", lambda _e: canvas.yview_scroll(2, "units"))
            if drag:
                widget.bind("<ButtonPress-1>", lambda e: canvas.scan_mark(e.x_root-canvas.winfo_rootx(), e.y_root-canvas.winfo_rooty()))
                widget.bind("<B1-Motion>", lambda e: canvas.scan_dragto(e.x_root-canvas.winfo_rootx(), e.y_root-canvas.winfo_rooty(), gain=1))

    def _build(self) -> None:
        self.root.configure(bg=self.color("background"))
        self.shell = tk.Frame(self.root, bg=self.color("background"))
        self.shell.pack(fill="both", expand=True)
        header = tk.Frame(self.shell, bg=self.color("background"))
        header.pack(fill="x", padx=self.px(12), pady=(self.px(8), self.px(4)))
        heading = tk.Frame(header, bg=self.color("background")); heading.pack(fill="x")
        self.label(heading, "Just Peachy", size=22, bold=True).pack(side="left")
        self.preview_label = self.label(heading, "480 × 800", size="small_font_px", muted=True)
        self.preview_label.pack(side="right")
        mode_bar = tk.Frame(header, bg=self.color("background")); mode_bar.pack(fill="x")
        self.mode_label = self.label(mode_bar, "Just Transcription", size="small_font_px", bold=True)
        self.mode_label.pack(side="left", fill="x", expand=True)
        self.rescue = self.button(mode_bar, "Show all", self.show_all_captions, key="rescue", height=48, wrap=92)
        self.rescue.configure(width=self.px(104))
        self.status_label = self.label(header, "Ready · microphone off", size="small_font_px", muted=True)
        self.status_label.configure(wraplength=self.px(456)); self.status_label.pack(fill="x", pady=(self.px(3), 0))
        self.error_label = self.label(header, "", size="small_font_px")
        self.error_label.configure(fg=self.color("error"), wraplength=self.px(456))
        self.backend_control = self.button(header, "BACKEND · Baseline", self.show_backends,
                                           key="backend", height=48, wrap=442)
        self.backend_control.pack(fill="x", pady=(self.px(3), 0))
        self.actions["backend"].configure(font=self.font("small_font_px", True), anchor="w", padx=self.px(8))
        footer = tk.Frame(self.shell, bg=self.color("background"))
        footer.pack(side="bottom", fill="x")
        nav = tk.Frame(footer, bg=self.color("background")); nav.pack(fill="x")
        for index, (text, command, key) in enumerate((
            ("Start", self.toggle_listening, "start_stop"), ("Mode", self.show_modes, "mode"),
            ("People", self.show_people, "people"), ("Settings", self.show_settings, "settings"))):
            nav.columnconfigure(index, weight=1, uniform="navigation")
            self.button(nav, text, command, accent=index == 0, key=key, height=60, wrap=112).grid(row=0, column=index, sticky="nsew", padx=self.px(1))
        self.body = tk.Frame(self.shell, bg=self.color("background")); self.body.pack(fill="both", expand=True)
        self.caption_page = tk.Frame(self.body, bg=self.color("background"))
        self.caption_page.pack(fill="both", expand=True)
        self.spatial_canvas = tk.Canvas(self.caption_page, height=self.px(145),
            bg=self.color("surface"), highlightthickness=0)
        self._spatial_font = tkfont.Font(root=self.root, font=self.font(11))
        if self.preferences.get("spatial_visualization", False):
            self.spatial_canvas.pack(fill="x", padx=self.px(8), pady=(self.px(4), 0))
        self.spatial_canvas.bind("<Configure>", lambda _e: self._update_spatial_visualization(force=True))
        self.spatial_canvas.bind("<Button-1>", lambda _e: self._hide_spatial())
        self._spatial_signature = None
        # This pane has a fixed height. Long/partial captions scroll inside it;
        # reviewing transcript history never moves the current speech offscreen.
        self.active_region = tk.Frame(self.caption_page, bg=self.color("surface"), height=self.px(184))
        self.active_region.pack(side="bottom", fill="x", padx=self.px(6), pady=(0, self.px(4)))
        self.active_region.pack_propagate(False)
        active_heading = tk.Frame(self.active_region, bg=self.color("surface")); active_heading.pack(fill="x")
        self.active_title = self.label(active_heading, "LIVE CAPTION · waiting", size="small_font_px", bold=True)
        self.active_title.configure(bg=self.color("surface")); self.active_title.pack(side="left", padx=self.px(6))
        self.active_text = tk.Text(self.active_region, wrap="word", state="disabled",
            font=self.font(self.config["caption_sizes_px"][self.preferences["caption_size"]]),
            bg=self.color("surface"), fg=self.color("text"), relief="flat", borderwidth=0,
            padx=self.px(6), pady=self.px(3), cursor="arrow", takefocus=False, highlightthickness=0)
        active_scroll = ttk.Scrollbar(self.active_region, orient="vertical", command=self._scroll_active_to)
        active_scroll.pack(side="right", fill="y")
        self.active_text.configure(yscrollcommand=active_scroll.set)
        self.active_text.pack(fill="both", expand=True)
        self._active_pane = ActiveCaptionPane(self.active_text)
        self.active_text.tag_configure("speaker", font=self.font("small_font_px", True), foreground=self.color("muted"))
        self.active_text.tag_configure("selected", background=self.color("selected"))
        self.active_text.tag_configure("pending", foreground=self.color("muted"))
        self.active_text.tag_configure("placeholder", foreground=self.color("muted"))
        self.active_text.bind("<MouseWheel>", self._active_wheel)
        self.active_text.bind("<Button-4>", lambda _e: self._scroll_active(-2))
        self.active_text.bind("<Button-5>", lambda _e: self._scroll_active(2))
        self.active_text.bind("<ButtonPress-1>", lambda e: self.active_text.scan_mark(e.x, e.y))
        self.active_text.bind("<B1-Motion>", self._drag_active)
        self.history_title = self.label(self.caption_page, "TRANSCRIPT HISTORY", size="small_font_px", muted=True)
        self.history_title.pack(fill="x", padx=self.px(12))
        self.caption_text = tk.Text(self.caption_page, wrap="word", state="disabled", font=self.font(self.config["caption_sizes_px"][self.preferences["caption_size"]]),
            bg=self.color("background"), fg=self.color("text"), relief="flat", borderwidth=0,
            padx=self.px(12), pady=self.px(6), cursor="arrow", takefocus=False,
            selectbackground=self.color("selected"), highlightthickness=0, spacing1=0, spacing2=0, spacing3=self.px(1))
        self.caption_text.pack(fill="both", expand=True)
        self.caption_text.tag_configure("speaker", font=self.font("small_font_px", True), foreground=self.color("muted"))
        self.caption_text.tag_configure("selected", background=self.color("selected"))
        self.caption_text.tag_configure("partial", foreground=self.color("text"))
        self.caption_text.tag_configure("placeholder", foreground=self.color("muted"))
        self.caption_text.tag_configure("gap", font=self.font(6), spacing1=0, spacing3=0)
        self.caption_text.tag_configure("pending", foreground=self.color("muted"))
        self.caption_text.tag_configure("active_row", elide=True)
        self.caption_text.bind("<MouseWheel>", self._caption_wheel)
        self.caption_text.bind("<Button-4>", lambda _e: self._scroll_caption(-3))
        self.caption_text.bind("<Button-5>", lambda _e: self._scroll_caption(3))
        self.caption_text.bind("<ButtonPress-1>", self._drag_start)
        self.caption_text.bind("<B1-Motion>", self._drag_caption)
        controls = tk.Frame(self.caption_page, bg=self.color("background"))
        controls.pack(side="bottom", before=self.caption_text, fill="x", padx=self.px(4), pady=self.px(4))
        self.button(controls, "↑", lambda: self._scroll_caption(-5), key="scroll_up").pack(side="left", fill="x", expand=True)
        self.button(controls, "Back to live", self.back_to_live, key="back_live").pack(side="left", fill="x", expand=True, padx=self.px(4))
        self.button(controls, "↓", lambda: self._scroll_caption(5), key="scroll_down").pack(side="left", fill="x", expand=True)
        self.dialog_page = tk.Frame(self.body, bg=self.color("background"))
        self._render_rows(self.snapshot.get("rows", []), force=True)

    def _set_geometry(self) -> None:
        self.root.geometry(f"{self.px(480)}x{self.px(800)}")
        self.root.update_idletasks()
        self.client_metrics = self.measure_client()
        exact = self.client_metrics.get("physical_width") == 480 and self.client_metrics.get("physical_height") == 800
        suffix = "pixel-check" if self.zoom == 1 and exact and self.client_metrics.get("dpi_awareness") != 0 else "client check pending" if self.zoom == 1 else f"{round(self.zoom * 100)}% comfort zoom"
        self.preview_label.configure(text=suffix)

    def measure_client(self) -> dict[str, Any]:
        self.root.update_idletasks()
        result: dict[str, Any] = dict(design_width=480, design_height=800, zoom=self.zoom,
            toolkit_width=self.root.winfo_width(), toolkit_height=self.root.winfo_height(),
            tk_scaling=float(self.root.tk.call("tk", "scaling")), screen_ppi=self.root.winfo_fpixels("1i"))
        if os.name == "nt":
            try:
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]; user32.GetAncestor.restype = wintypes.HWND
                hwnd = user32.GetAncestor(self.root.winfo_id(), 2)
                rect = wintypes.RECT()
                user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
                user32.GetClientRect.restype = wintypes.BOOL
                if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
                    raise OSError("GetClientRect failed")
                user32.GetDpiForWindow.argtypes = [wintypes.HWND]; user32.GetDpiForWindow.restype = wintypes.UINT
                user32.GetWindowDpiAwarenessContext.argtypes = [wintypes.HWND]; user32.GetWindowDpiAwarenessContext.restype = ctypes.c_void_p
                user32.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]
                awareness = user32.GetAwarenessFromDpiAwarenessContext(user32.GetWindowDpiAwarenessContext(hwnd))
                result.update(native_client_width=rect.right - rect.left, native_client_height=rect.bottom - rect.top,
                              dpi=user32.GetDpiForWindow(hwnd), dpi_awareness=awareness)
                if awareness in (1, 2):
                    result.update(physical_width=rect.right - rect.left, physical_height=rect.bottom - rect.top)
            except (AttributeError, OSError) as exc:
                result["native_measurement_error"] = str(exc)
        else:
            result.update(physical_width=self.root.winfo_width(), physical_height=self.root.winfo_height(),
                          dpi_awareness="toolkit; target display hardware pending")
        return result

    def _call(self, method: str, *args: Any, **kwargs: Any) -> bool:
        try:
            getattr(self.controller, method)(*args, **kwargs)
            self._notice = ""
            return True
        except Exception as exc:
            self._notice = str(exc)
            self._show_status()
            return False

    def poll(self) -> None:
        if self._closed:
            return
        if self._poll_handle:
            self.root.after_cancel(self._poll_handle)
            self._poll_handle = None
        try:
            snapshot = self.controller.snapshot()
            if not isinstance(snapshot, dict):
                raise TypeError("Controller snapshot must be a dictionary")
            self.snapshot = snapshot
            if self._closing and str(snapshot.get("state", "")).casefold() == "closed":
                self._closed = True
                self.root.destroy()
                return
            if self._closing and snapshot.get("error") and str(snapshot.get("state", "")).casefold() == "error":
                self._closing = False
                self._notice = "Close did not finish: " + str(snapshot["error"])
                for key in ("start_stop", "mode", "people", "settings", "rescue", "backend"):
                    self.actions[key].configure(state="normal")
            self._show_status()
            self._queue_rows(snapshot.get("rows", []))
            # GUI-only three-dot pulse; no callback, inference or event/log frame.
            self.caption_text.tag_configure("pending", foreground=self.color("muted" if int(time.perf_counter()*2)%2 else "text"))
            self.active_text.tag_configure("pending", foreground=self.color("muted" if int(time.perf_counter()*2)%2 else "text"))
            self._update_spatial_visualization()
            if self._page_update:
                self._page_update()
        except Exception as exc:
            self._notice = f"Display update: {exc}"
            self._show_status()
        self._poll_handle = self.root.after(self.config["poll_ms"], self.poll)

    def _running(self) -> bool:
        return str(self.snapshot.get("state", "idle")).casefold() not in {"idle", "ready", "stopped", "error", "blocked", "closed"}

    def _show_status(self) -> None:
        mode = self.snapshot.get("mode", "caption_only")
        state = str(self.snapshot.get("state", "idle"))
        status = str(self.snapshot.get("status") or ("Microphone off · choose Start" if not self._running() else state))
        profile = f"{self.snapshot.get('recipe', 'pending')} / {self.snapshot.get('tap', 'pending')}"
        self.mode_label.configure(text=MODES.get(mode, (mode,))[0])
        status = status.split(" · "+mode)[0]
        self.status_label.configure(text=f"{profile} · {status}"[:200])
        backend = self.snapshot.get("backend") or backend_status(self.snapshot.get("backend_id", BASELINE_BACKEND_ID), mode, self.snapshot.get("tap", "O0"))
        name = str(backend.get("label", "Unknown composition"))
        self.actions["backend"].configure(text="BACKEND · " + name + (" · unavailable" if not backend.get("available") else ""),
            bg=self.color("selected" if self.page == "backends" else "raised"),
            fg=self.color("text" if backend.get("available") else "warning"))
        sessions=self.snapshot.get('sessions') or {}
        archive=sessions.get('archive') or {}
        recording=archive.get('audio_recording')
        if recording:self.status_label.configure(text='● SAVING EXACT AUDIO · '+str(status)[:110],fg=self.color('warning'))
        else:self.status_label.configure(fg=self.color('muted'))
        archive_error=archive.get('archive_error') if archive else (sessions.get('last_archive') or {}).get('archive_error')
        error = self._notice or self.snapshot.get("error") or ('Recording/archive loss: '+archive_error if archive_error else '')
        playback=sessions.get('playback') or {}
        if playback.get('error'):error=error or ('Listening: '+playback['error'])
        if playback.get('active'):
            self.status_label.configure(text='▶ Listening · microphone off · '+str((playback.get('device') or {}).get('name',''))[:90])
        elif playback and not playback.get('error'):
            self.status_label.configure(text='Listening finished · microphone off')
        if error:
            self.error_label.configure(text=str(error)[:240]); self.error_label.pack(fill="x", pady=(self.px(4), 0))
        else:
            self.error_label.pack_forget()
        self.actions["start_stop"].configure(text="Stop" if self._running() else "Start")
        strict = bool(self.snapshot.get("strict"))
        if strict:
            self.rescue.pack(side="right")
            self.mode_label.configure(text=MODES.get(mode,(mode,))[0]+" · filtered")
        else:
            self.rescue.pack_forget()
        self._highlight_navigation()

    def _highlight_navigation(self) -> None:
        if self.page == "backends": self._nav_context = None
        elif self.page in {"modes", "roster", "recipes", "help", "display_features"}: self._nav_context = "mode"
        elif self.page in {"people", "person", "enrollment", "enrollment_progress"}: self._nav_context = "people"
        elif self.page in {"settings", "diagnostics", "beam_diagnostics", "problem", "advanced", "identity_scores", "identity_parameters", "sessions", "session_detail", "session_outputs"}: self._nav_context = "settings"
        elif self.page == "captions": self._nav_context = None
        for key in ("mode", "people", "settings"):
            chosen = key == self._nav_context
            self.actions[key].configure(bg=self.color("selected" if chosen else "raised"),
                text=("● " if chosen else "") + key.title(), relief="sunken" if chosen else "flat")

    def _queue_rows(self, rows) -> None:
        delay = self.preferences["display_smoothing_ms"]
        if not delay:
            if self._display_handle:
                self.root.after_cancel(self._display_handle); self._display_handle = None
            self._pending_rows = None
            self._render_rows(rows)
            return
        # Throttle from the first change, never debounce indefinitely under speech.
        if rows == self._pending_rows:
            return
        if self._display_handle is None and rows == getattr(self, "_applied_rows", None):
            self._render_rows(rows)  # Identity deadlines still advance without text.
            return
        self._pending_rows = rows
        if self._display_handle is None:
            self._display_received = time.perf_counter()
            self._display_handle = self.root.after(delay, self._flush_rows)

    def _flush_rows(self) -> None:
        self._display_handle = None
        if self._closed or self._closing: return
        rows = self._pending_rows
        self._pending_rows = None
        if rows is None: return
        self._render_rows(rows)
        self._applied_rows = rows
        self.presentation_delays_ms.append((time.perf_counter()-self._display_received)*1000)
        del self.presentation_delays_ms[:-64]

    def _display_row(self, row: dict[str, Any]) -> tuple[str, str, bool]:
        names = [str(p.get("name", "")) for p in self.snapshot.get("people", [])]
        if row.get("final") and row.get("final_punctuated_display_text"):
            text = str(row["final_punctuated_display_text"])
        elif row.get("provisional_display_text") is not None:
            text = str(row["provisional_display_text"])
        else:
            text = provisional_case(str(row.get("raw_asr_text", "")), names, self.config["acronyms"])
        if row.get('final') and row.get('show_corrected_text') and row.get('optional_corrected_text'):
            text='✎ '+str(row['optional_corrected_text'])
        mode = self.snapshot.get("mode", "caption_only")
        label = self._identity_labels.label(row, mode, time.perf_counter(), mode in NUMBERED_MODES)
        return label, text, bool(row.get("selected")) and bool(self.snapshot.get('settings',{}).get('highlight_selected'))

    def _render_rows(self, rows: list[dict[str, Any]], force: bool = False) -> None:
        strict = bool(self.snapshot.get("strict"))
        visible = [row for row in rows if not strict or row.get("selected")]
        ids = [str(row["id"]) for row in visible]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate caption row IDs")
        self._identity_labels.prune(rows)
        current = {str(row["id"]): self._display_row(row) for row in visible}
        previous = None
        for row in visible:
            rid = str(row["id"])
            label, caption, selected = current[rid]
            if previous and continues(previous, row, self._display_row(previous)[0], label):
                current[rid] = ("", caption, selected)
            previous = row
        active_rows = active_caption_rows(visible)
        active_ids = {str(row['id']) for row in active_rows}
        history_order = [rid for rid in ids if rid not in active_ids]
        history_added = history_order != self._history_order
        self._active_pane.render(active_rows, current,
            "No selected speech. Use Show all." if strict and rows else "Choose Start when you are ready.")
        self.active_title.configure(text="LIVE CAPTION" + (" · scroll for full paragraph" if active_rows else " · waiting"))
        if not force and ids == self._render_order and current == self._row_cache and not history_added:
            return
        text = self.caption_text
        follow = self._follow_live
        anchor = text.index("@0,0")
        text.mark_set("view_anchor", anchor); text.mark_gravity("view_anchor", "left")
        anchor_row = next((rid for rid in self._render_order if text.compare(self._marks[rid][0], "<=", anchor)
                           and text.compare(anchor, "<", self._marks[rid][1])), None)
        anchor_offset = (text.count(self._marks[anchor_row][0], anchor, "chars") or (0,))[0] if anchor_row else 0
        text.configure(state="normal")
        if force:
            text.delete("1.0", "end")
            for start, end in self._marks.values():
                text.mark_unset(start, end)
            self._marks.clear(); self._row_cache.clear(); self._render_order = []
        # Native S7 may retire/replace one segment when ownership arrives. Keep
        # every surviving row/widget mark instead of rebuilding the transcript.
        for rid in list(self._render_order):
            if rid not in current:
                start, end = self._marks.pop(rid)
                text.delete(start, end); text.mark_unset(start, end)
                self._row_cache.pop(rid, None); self._render_order.remove(rid)
        if not ids:
            text.delete("1.0", "end")
            placeholder = "No selected speech is visible.\nUse Show all captions to recover the full view." if strict and rows else "Completed turns appear here.\nCurrent speech stays in the panel below."
            text.insert("1.0", placeholder, "placeholder")
        else:
            if not self._render_order:
                text.delete("1.0", "end")
            for index, rid in enumerate(ids):
                value = current[rid]
                if rid in self._marks and self._render_order.index(rid) != index:
                    start, end = self._marks.pop(rid)
                    text.delete(start, end); text.mark_unset(start, end)
                    self._row_cache.pop(rid, None); self._render_order.remove(rid)
                next_id = self._render_order[index] if rid not in self._marks and index < len(self._render_order) else (
                    self._render_order[index+1] if rid in self._marks and index+1 < len(self._render_order) else None)
                next_start = self._marks[next_id][0] if next_id else None
                if rid in self._marks and self._row_cache.get(rid) == value: continue
                if rid not in self._marks:
                    self._mark_number += 1
                    start, end = f"row_{self._mark_number}_start", f"row_{self._mark_number}_end"
                    text.mark_set(start, next_start or "end-1c"); text.mark_gravity(start, "left")
                    text.mark_set(end, start); text.mark_gravity(end, "right")
                    self._marks[rid] = start, end
                    self._render_order.insert(index, rid)
                else:
                    start, end = self._marks[rid]
                if next_start: text.mark_gravity(next_start, "right")
                label, caption, selected = value
                replacement = (label+"\n" if label else "") + caption + "\n\n"
                before = text.get(start, end)
                prefix = 0
                while prefix < min(len(before), len(replacement)) and before[prefix] == replacement[prefix]: prefix += 1
                suffix = 0
                while suffix < min(len(before), len(replacement))-prefix and before[-suffix-1] == replacement[-suffix-1]: suffix += 1
                chars = lambda s: int(self.root.tk.call("string", "length", s))
                edit_start = f"{start}+{chars(before[:prefix])}c"
                edit_end = f"{end}-{chars(before[len(before)-suffix:]) if suffix else 0}c"
                text.mark_gravity(end, "right")
                text.delete(edit_start, edit_end)
                text.insert(edit_start, replacement[prefix:len(replacement)-suffix if suffix else None])
                text.mark_gravity(end, "left")
                for tag in ("speaker", "selected", "gap", "pending"): text.tag_remove(tag, start, end)
                if label: text.tag_add("speaker", start, f"{start}+{chars(label)}c")
                if label.startswith("•••"): text.tag_add("pending", start, f"{start}+3c")
                text.tag_add("gap", f"{end}-1c", end)
                if selected:
                    text.tag_add("selected", start, end)
                if next_start: text.mark_gravity(next_start, "left")
            self._render_order = ids
            self._row_cache = current
        text.tag_remove("active_row", "1.0", "end")
        for rid in active_ids:
            if rid in self._marks:
                text.tag_add("active_row", *self._marks[rid])
        self._history_order = history_order
        text.configure(state="disabled")
        if follow and history_added:
            text.update_idletasks(); text.yview_moveto(1.0)
        elif anchor_row in self._marks:
            text.yview(f"{self._marks[anchor_row][0]}+{anchor_offset}c")
        else:
            text.yview("view_anchor")
        self._record_presentations(visible, current, active_ids)

    def _record_presentations(self, rows, current, active_ids) -> None:
        """Capture applied GUI labels separately from model/core proposals."""
        now = time.perf_counter()
        for row in rows:
            rid = str(row['id'])
            shown = current[rid]
            spans = tuple(str(value) for value in row.get('span_ids') or [rid])
            signature = (shown, spans, row.get('speaker_revision'), rid in active_ids)
            if self._presentation_values.get(rid) == signature:
                continue
            self._presentation_values[rid] = signature
            # A grouped row has no repeated header, but still carries the
            # inherited label explicitly in the receipt for span auditing.
            label = shown[0] or self._display_row(row)[0]
            first = {}
            revisions = {}
            for span in spans:
                state = self._presentation_spans.setdefault(span, dict(first=label, last=label, revision=0))
                if state['last'] != label:
                    state['last'] = label; state['revision'] += 1
                first[span] = state['first']; revisions[span] = state['revision']
            receipt = dict(schema='just-peachy.gui-presentation.v1', kind='prototype_gui_presentation',
                row_id=rid, caption_key=row.get('caption_key'), span_ids=list(spans),
                backend_id=self.snapshot.get('backend_id', BASELINE_BACKEND_ID),
                applied_monotonic_sec=now, label=label, heading_suppressed=not bool(shown[0]),
                first_gui_labels=first, gui_label_revisions=revisions,
                speaker_revision=row.get('speaker_revision'), pane='active' if rid in active_ids else 'history',
                scope='Tk text applied; viewport visibility and physical scanout not measured',
                root_state=self.root.state())
            self.presentation_receipts.append(receipt)
            callback = getattr(self.controller, 'record_presentation', None)
            if callable(callback):
                callback(receipt)
        del self.presentation_receipts[:-256]
        live_ids = {str(row['id']) for row in rows}
        self._presentation_values = {key:value for key,value in self._presentation_values.items() if key in live_ids}
        # The core journal remains the durable record; UI audit memory is bounded.
        while len(self._presentation_spans) > 8192:
            self._presentation_spans.pop(next(iter(self._presentation_spans)))

    def _caption_wheel(self, event: tk.Event) -> str:
        return self._scroll_caption(-int(event.delta / 120) * 3 if abs(event.delta) >= 120 else (-2 if event.delta > 0 else 2))

    def _scroll_caption(self, units: int) -> str:
        self._follow_live = False
        self.caption_text.yview_scroll(units, "units")
        return "break"

    def _drag_start(self, event: tk.Event) -> str:
        self.caption_text.scan_mark(event.x, event.y)
        return "break"

    def _drag_caption(self, event: tk.Event) -> str:
        self._follow_live = False
        self.caption_text.scan_dragto(event.x, event.y)
        return "break"

    def back_to_live(self) -> None:
        self._follow_live = True
        self.caption_text.update_idletasks(); self.caption_text.yview_moveto(1.0)
        self._active_pane.follow = True
        self.active_text.see("end-1c")

    def _scroll_active_to(self, *args) -> None:
        self._active_pane.follow = False
        self.active_text.yview(*args)

    def _scroll_active(self, units: int) -> str:
        self._active_pane.follow = False
        self.active_text.yview_scroll(units, "units")
        return "break"

    def _active_wheel(self, event: tk.Event) -> str:
        return self._scroll_active(-int(event.delta / 120) * 2 if abs(event.delta) >= 120 else (-2 if event.delta > 0 else 2))

    def _drag_active(self, event: tk.Event) -> str:
        self._active_pane.follow = False
        self.active_text.scan_dragto(event.x, event.y, gain=1)
        return "break"

    def home(self) -> None:
        self.page = "captions"; self._page_update = None
        self.dialog_page.pack_forget(); self.caption_page.pack(fill="both", expand=True)
        self._highlight_navigation()

    def _page(self, title: str, *, scroll: bool = True, back: Callable | None = None) -> tk.Frame:
        self._page_update = None
        self._highlight_navigation()
        self.caption_page.pack_forget()
        for child in self.dialog_page.winfo_children():
            child.destroy()
        self.dialog_page.pack(fill="both", expand=True)
        top = tk.Frame(self.dialog_page, bg=self.color("background")); top.pack(fill="x")
        back_control = self.button(top, "‹ Transcript" if back is None else "‹ Back", back or self.home, height=48, key="back")
        back_control.configure(width=self.px(124)); back_control.pack(side="left")
        self.label(top, title, size="heading_font_px", bold=True).pack(side="left", fill="x", expand=True, padx=self.px(8))
        if scroll:
            area = TouchScroll(self.dialog_page, self); area.pack(fill="both", expand=True)
            return area.inner
        frame = tk.Frame(self.dialog_page, bg=self.color("background")); frame.pack(fill="both", expand=True)
        return frame

    def _paragraph_label(self, parent: tk.Misc, value: str, muted: bool = False) -> tk.Label:
        label = self.label(parent, value, muted=muted)
        label.pack(fill="x", padx=self.px(12), pady=self.px(4))
        return label

    def confirm(self, title: str, message: str, action: str, callback: Callable, *, cancel: Callable | None = None) -> None:
        self.page = "consent"
        frame = self._page(title, back=cancel)
        self._paragraph_label(frame, message)
        self.button(frame, action, callback, accent=True, key="confirm").pack(fill="x", padx=self.px(12), pady=self.px(8))
        self.button(frame, "Cancel", cancel or self.home, key="cancel").pack(fill="x", padx=self.px(12), pady=self.px(4))

    def toggle_listening(self) -> None:
        self._cancel_auto_start_timer()
        self._auto_start_pending = False
        if self._running():
            self._call("stop")
            return
        backend = self.snapshot.get("backend") or backend_status(
            self.snapshot.get("backend_id", BASELINE_BACKEND_ID), self.snapshot.get("mode", "caption_only"), self.snapshot.get("tap", "O0"))
        if not backend.get("available"):
            self._notice = str(backend.get("reason", "Backend unavailable."))
            self.show_backends(); self._show_status()
            return
        def start() -> None:
            if self._call("start_live", consent=True):
                self._mic_consented = True; self.home()
        if not self._mic_consented:
            self.confirm("Microphone consent", "Start listening through the selected XVF microphone array? Speech is processed locally. Session text and diagnostic retention follow Settings. Enrollment is separate. Stop releases capture. The app does not change your default speakers.", "I consent · Start listening", start)
        else:
            start()

    def show_all_captions(self) -> None:
        if self._call("switch", strict=False):
            self.snapshot = dict(self.snapshot, strict=False)
            self._render_rows(self.snapshot.get("rows", []), force=True)
            self.home()

    def _choose_mode(self, mode: str) -> None:
        if mode in SEAT_MODES:
            self.show_seats(mode);return
        if mode in SELECTED_MODES:
            self.show_roster(mode);return
        if self._call("switch", mode=mode, strict=False):
            self.home()

    def show_modes(self) -> None:
        self.page = "modes"; frame = self._page("Mode")
        self._paragraph_label(frame, "Modes change naming and emphasis. Backend, recipe and audio tap are independent controls.", True)
        self._paragraph_label(frame, MODE_LEGEND, True)
        self._paragraph_label(frame, "✓ marks a supported simulation configuration, not verified field accuracy. Experimental modes remain selectable.", True)
        for mode, (name, description) in MODES.items():
            if MODE_METADATA[mode]['advanced']:continue
            metadata = self._mode_metadata(mode)
            selected = mode == self.snapshot.get("mode", "caption_only")
            self.button(frame, metadata["symbol"] + " " + metadata["label"] + (" · active" if selected else ""), lambda m=mode: self._choose_mode(m),
                        accent=selected, key=f"mode_{mode}").pack(fill="x", padx=self.px(12), pady=(self.px(6), 0))
            self._paragraph_label(frame, MODE_METADATA[mode]['full_name']+'\n'+metadata["description"], True)
            availability = backend_status(self.snapshot.get("backend_id", BASELINE_BACKEND_ID), mode, self.snapshot.get("tap", "O0"),
                recorded_spatial=bool(self.snapshot.get("recorded_spatial_available")))
            if not availability['available']:
                self._paragraph_label(frame, availability['reason'], True)
        self.button(frame, "Separate display features…", self.show_display_features, key="roster").pack(fill="x", padx=self.px(12), pady=self.px(6))
        self.button(frame, "Advanced · numbered modes / scores", self.show_advanced).pack(fill='x',padx=self.px(12),pady=self.px(6))
        self.button(frame, "Engine recipe & audio tap", self.show_recipes, key="recipes").pack(fill="x", padx=self.px(12), pady=self.px(6))
        self.button(frame, "Mode guide", self.show_help).pack(fill="x", padx=self.px(12), pady=self.px(6))

    def _mode_metadata(self, mode: str) -> dict[str, str]:
        """Missing evidence is experimental; the GUI never invents support."""
        name, description = MODES[mode]
        item = (self.snapshot.get("mode_metadata") or {}).get(mode) or {}
        return {"label": str(item.get("label") or name),
                "description": str(item.get("description") or description),
                "symbol": "✓" if item.get("symbol") == "✓" else "◇",
                "status": str(item.get("status") or "experimental"),
                "parent": str(item.get("parent") or "")}

    def request_strict(self) -> None:
        if self.snapshot.get('mode') not in NAMED_MODES:
            self._notice='Choose an identification mode first. A display filter does not enable identification.'
            self.show_modes();self._show_status();return
        if not self.snapshot.get("display_ids"):
            self._notice = "Choose at least one person in the separate display roster before hiding."
            self.show_roster(); self._show_status(); return
        self.confirm("Experimental filter", "Selected-only may hide intended speech when identity is unknown or wrong. It hides text; it does not acoustically remove other voices. The full internal transcript is retained. Show all captions is always one tap away.", "Enable selected-only view", self._enable_strict, cancel=self.show_modes)

    def _enable_strict(self) -> None:
        if self._call("switch", strict=True):
            self.home()

    def show_display_features(self) -> None:
        self.page='display_features';frame=self._page('Display features',back=self.show_modes)
        self._paragraph_label(frame,'Highlighting or hiding changes the view only. Matching is controlled by the selected mode and its gallery. All text remains in the archive.',True)
        self.button(frame,'Choose display roster',self.show_roster).pack(fill='x',padx=self.px(12),pady=self.px(4))
        highlight=self.snapshot.get('settings',{}).get('highlight_selected',False)
        self.button(frame,'Highlight selected: '+('ON' if highlight else 'OFF'),
            lambda:self._call('settings_update',{'highlight_selected':not highlight}),key='highlight_selected').pack(fill='x',padx=self.px(12),pady=self.px(4))
        self.button(frame,'Experimental · hide other/Unknown captions',self.request_strict,key='strict').pack(fill='x',padx=self.px(12),pady=self.px(4))
        self.button(frame,'Show all captions · keep identity mode',self.show_all_captions).pack(fill='x',padx=self.px(12),pady=self.px(4))
        def update():
            if self.snapshot.get('settings',{}).get('highlight_selected',False)!=highlight:self.show_display_features()
        self._page_update=update

    def _recipes(self) -> list[dict[str, Any]]:
        recipes = self.snapshot.get("recipes", [])
        if isinstance(recipes, dict):
            return [dict(value, id=key) if isinstance(value, dict) else dict(id=key, name=str(value)) for key, value in recipes.items()]
        return [r if isinstance(r, dict) else dict(id=str(r), name=str(r)) for r in recipes]

    def show_backends(self) -> None:
        self.page = "backends"; frame = self._page("Backend")
        self._show_status()
        self._paragraph_label(frame, "Select the model composition. Mode, roster, recipe and O0/O1 remain separate. Switching stops the current session; Start remains explicit.", True)
        for backend in self.snapshot.get("backends") or backend_catalog():
            bid = backend['manifest_id']
            selected = bid == self.snapshot.get("backend_id", BASELINE_BACKEND_ID)
            title = ("✓ " if selected else "") + backend['label']
            title += " · implemented" if backend.get('implemented') else " · unavailable"
            self.button(frame, title, lambda value=bid: self._select_backend(value), accent=selected,
                        key="backend_" + backend['key'], height=64).pack(fill="x", padx=self.px(12), pady=(self.px(5), 0))
            capacity = backend.get('capacity') or {}
            details = ["Manifest " + bid, str(backend.get('reason') or "Existing baseline adapter; local asset checks still apply at Start."),
                "Capacity: " + str(capacity.get('speaker_channels_status', 'Not established')),
                "2 GB target: " + str(capacity.get('system_ram_2gb', 'NOT_TESTED')),
                "One active model stack. All logical modes remain visible."]
            self._paragraph_label(frame, "\n".join(details), True)
        self._paragraph_label(frame, "Voice profiles are model-specific. ReDimNet vectors cannot be compared with TitaNet; compatible permitted reference audio or re-enrollment is required.", True)

    def _select_backend(self, backend_id: str) -> None:
        if self._call('select_backend', backend_id):
            # Controller owns the command and its completion; the next poll
            # supplies the authoritative ID instead of an optimistic UI state.
            self._notice = "Backend selection queued. Start is explicit."
            self._page_update = self._backend_selection_update

    def _backend_selection_update(self) -> None:
        identifier = self.snapshot.get('backend_id', BASELINE_BACKEND_ID)
        if identifier != getattr(self, '_backend_page_id', None):
            self._backend_page_id = identifier
            self.show_backends()
            self._page_update = self._backend_selection_update

    def show_recipes(self) -> None:
        self.page = "recipes"; frame = self._page("Recipe & tap", back=self.show_modes)
        self._paragraph_label(frame, "Changes may pause listening while the backend starts a new profile/audio epoch. Finished captions and people remain.", True)
        recipes = self._recipes()
        for recipe in recipes:
            rid = str(recipe.get("id", recipe.get("key", "")))
            modes = recipe.get("compatible_modes", recipe.get("modes", []))
            available = recipe.get("available", True) and (not modes or self.snapshot.get("mode", "caption_only") in modes)
            chosen = rid == self.snapshot.get("recipe")
            control = self.button(frame, ("✓ " if chosen else "") + str(recipe.get("name", rid)),
                                  lambda value=rid: self._select_recipe(value), accent=chosen, key=f"recipe_{rid}")
            control.pack(fill="x", padx=self.px(12), pady=(self.px(8), 0))
            control.button.configure(state="normal" if available else "disabled")  # type: ignore[attr-defined]
            details = recipe.get("description", recipe.get("why", ""))
            reason = recipe.get("reason", recipe.get("unavailable_reason", ""))
            evidence = recipe.get("evidence_status", "Native evidence: see mode guide")
            if not available and not reason:
                reason = "Unavailable for the current mode."
            self._paragraph_label(frame, "\n".join(str(x) for x in (details, reason, evidence) if x), True)
        if not recipes:
            self._paragraph_label(frame, "The backend has not supplied compatible recipes yet. No unverified substitute is offered.")
        current = next((r for r in recipes if str(r.get("id", r.get("key", ""))) == self.snapshot.get("recipe")), {})
        taps = current.get("taps", current.get("compatible_taps", []))
        self._paragraph_label(frame, "Audio tap · the backend verifies routing and applies gain once.")
        row = tk.Frame(frame, bg=self.color("background")); row.pack(fill="x", padx=self.px(12), pady=self.px(8))
        for tap in ("O0", "O1"):
            choice = self.button(row, tap + (" ✓" if tap == self.snapshot.get("tap", "O0") else ""),
                                 lambda value=tap: self._select_tap(value), key=f"tap_{tap}")
            choice.pack(side="left", expand=True, fill="x", padx=self.px(2))
            choice.button.configure(state="normal" if tap in taps else "disabled")  # type: ignore[attr-defined]

    def _select_recipe(self, recipe: str) -> None:
        if self._call("switch", recipe=recipe):
            self.snapshot["recipe"] = recipe; self.show_recipes()

    def _select_tap(self, tap: str) -> None:
        if self._call("switch", tap=tap):
            self.snapshot["tap"] = tap; self.show_recipes()

    def show_people(self) -> None:
        self.page = "people"; frame = self._page("People")
        self._paragraph_label(frame, "Personal profiles stay local. Nothing is preloaded from a research gallery.", True)
        self.button(frame, "＋ Add person", self.add_person, accent=True, key="add_person").pack(fill="x", padx=self.px(12), pady=self.px(6))
        people = self.snapshot.get("people", [])
        self._people_signature = json.dumps(people, sort_keys=True)
        for person in people:
            display_name = str(person["name"]).replace("\n", " ")
            name_font = tkfont.Font(root=self.root, font=self.font())
            while len(display_name)>2 and name_font.measure(display_name)>self.px(360):
                display_name = display_name[:-2] + "…"
            self.button(frame, display_name + f"\nProfile {str(person['id'])[:6]}", lambda p=dict(person): self.show_person(p),
                        height=56).pack(fill="x", padx=self.px(12), pady=self.px(4))
        if not people:
            self._paragraph_label(frame, "No enrolled people. Recording needs explicit consent and real speech from the named person.")
        self.button(frame, "Import profiles…", lambda: self.browse_file("import"), key="import_people").pack(fill="x", padx=self.px(12), pady=self.px(5))
        self.button(frame, "Export profiles…", lambda: self.browse_file("export"), key="export_people").pack(fill="x", padx=self.px(12), pady=self.px(5))
        def refresh() -> None:
            if json.dumps(self.snapshot.get("people", []), sort_keys=True) != self._people_signature:
                self.show_people()
        self._page_update = refresh

    def show_person(self, person: dict[str, Any]) -> None:
        self.page = "person"; frame = self._page("Person", back=self.show_people)
        self._paragraph_label(frame, str(person["name"]))
        self._paragraph_label(frame, "Profile " + str(person["id"]), True)
        self.button(frame,'Review latest paragraph evidence',lambda:self.show_script_review(person['id']),key='person_script_review',height=60).pack(fill='x',padx=self.px(12),pady=self.px(5))
        self.button(frame, "Rename", lambda: self.keyboard("Rename person", str(person["name"]),
            lambda value: self._rename(person["id"], value), cancel=lambda: self.show_person(person)), key="rename_person").pack(fill="x", padx=self.px(12), pady=self.px(6))
        self.button(frame, "Add a reference session", lambda: self.enrollment_form(str(person["name"]), str(person["id"])),
                    key="add_reference").pack(fill="x", padx=self.px(12), pady=self.px(6))
        self.button(frame, "Delete profile…", lambda: self.confirm("Delete profile?", f"Delete {person['name']} and its local voice references? This cannot be undone by closing the dialog. Other people are preserved.",
            "Delete this profile", lambda: self._delete(person["id"]), cancel=lambda: self.show_person(person)), key="delete_person").pack(fill="x", padx=self.px(12), pady=self.px(6))

    def _rename(self, person_id: str, name: str) -> None:
        if self._call("rename_person", person_id, name):
            self.show_people()

    def _delete(self, person_id: str) -> None:
        if self._call("delete_person", person_id):
            self.show_people()

    def add_person(self) -> None:
        self.keyboard("Person's name", "", lambda value: self.enrollment_form(value), cancel=self.show_people)

    def keyboard(self, title: str, value: str, done: Callable[[str], None], *, multiline: bool = False,
                 cancel: Callable | None = None) -> None:
        self.page = "keyboard"; frame = self._page(title, scroll=False, back=cancel)
        self.keyboard_value = tk.Text(frame, height=4 if multiline else 2, wrap="word", font=self.font(22),
            bg=self.color("surface"), fg=self.color("text"), insertbackground=self.color("accent"),
            padx=self.px(8), pady=self.px(8), relief="flat")
        self.keyboard_value.pack(fill="x", pady=self.px(8)); self.keyboard_value.insert("1.0", value)
        self.keyboard_value.mark_set("insert", "end-1c"); self.keyboard_value.focus_set()
        message = self.label(frame, "Touch the text to move its cursor. No physical keyboard needed.", muted=True, size="small_font_px")
        message.pack(fill="x", padx=self.px(8), pady=self.px(4))
        keys = tk.Frame(frame, bg=self.color("background")); keys.pack(fill="x")
        keyboard_state = {"shift": not bool(value), "symbols": False}
        def insert(character: str) -> None:
            try:
                self.keyboard_value.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            self.keyboard_value.insert("insert", character)
            if keyboard_state["shift"] and character.isalpha():
                keyboard_state["shift"] = False; draw()
        def erase() -> None:
            try:
                self.keyboard_value.delete("sel.first", "sel.last")
            except tk.TclError:
                if self.keyboard_value.compare("insert", ">", "1.0"):
                    self.keyboard_value.delete("insert-1c", "insert")
        def finish() -> None:
            text = self.keyboard_value.get("1.0", "end-1c").strip()
            if not text:
                message.configure(text="Enter a value first.", fg=self.color("error")); return
            if not multiline and len(text) > 240:
                message.configure(text="Use at most 240 characters.", fg=self.color("error")); return
            done(text)
        def draw() -> None:
            for child in keys.winfo_children(): child.destroy()
            rows = ("1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm") if not keyboard_state["symbols"] else ("1234567890", "/\\:._-@!?", "'\"()+,;=&", "[]{}#%+*")
            for letters in rows:
                row = tk.Frame(keys, bg=self.color("background")); row.pack(fill="x")
                for index, letter in enumerate(letters):
                    row.columnconfigure(index, weight=1, uniform="key")
                    char = letter.upper() if keyboard_state["shift"] else letter
                    self.button(row, char, lambda c=char: insert(c), height=48, wrap=48).grid(row=0, column=index, sticky="nsew")
            row = tk.Frame(keys, bg=self.color("background")); row.pack(fill="x")
            def toggle(key: str) -> None:
                keyboard_state[key] = not keyboard_state[key]; draw()
            for index, (label, callback) in enumerate((("Shift", lambda: toggle("shift")), ("ABC" if keyboard_state["symbols"] else "Symbols", lambda: toggle("symbols")), ("Space", lambda: insert(" ")), ("⌫", erase))):
                row.columnconfigure(index, weight=1, uniform="bottomkey")
                self.button(row, label, callback, height=48, wrap=120).grid(row=0, column=index, sticky="nsew")
        draw()
        self.button(frame, "Done", finish, accent=True, key="keyboard_done").pack(fill="x", pady=self.px(4))

    def enrollment_form(self, name: str, person_id: str | None = None) -> None:
        self._enroll_name, self._enroll_person_id = name, person_id
        self._enroll_consent = False; self._enroll_started = False
        self._draw_enrollment()

    def _draw_enrollment(self) -> None:
        self.page = "enrollment"; frame = self._page("Voice reference", back=self.show_people)
        self._paragraph_label(frame, self._enroll_name)
        self._paragraph_label(frame, "Read at a comfortable level. Background voices, overlap, weak or clipped speech can reduce usefulness. The paragraph is a guide, never an expected transcript.", True)
        self.button(frame, "Read / edit paragraph", lambda: self.keyboard("Recording guide", self._paragraph,
            self._set_paragraph, multiline=True, cancel=self._draw_enrollment), key="edit_paragraph").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self._paragraph_label(frame, 'Target: unique usable speech', True)
        targets = tk.Frame(frame, bg=self.color("background")); targets.pack(fill="x", padx=self.px(12), pady=self.px(6))
        for target in (15, 30, 60):
            def choose(value: int = target) -> None:
                self._enroll_target = value; self._draw_enrollment()
            self.button(targets, f"{target}s" + (" ✓" if self._enroll_target == target else ""), choose,
                        accent=self._enroll_target == target, key=f"enroll_target_{target}", wrap=120).pack(side="left", fill="x", expand=True, padx=self.px(2))
        def paragraph_done() -> None:
            self._enroll_target = None; self._draw_enrollment()
        self.button(frame, 'Read paragraph → Done' + (' ✓' if self._enroll_target is None else ''), paragraph_done,
                    accent=self._enroll_target is None, key='enroll_target_done').pack(fill='x', padx=self.px(12), pady=self.px(4))
        self._paragraph_label(frame, 'Timed: the paragraph may not meet the target; continue with different natural speech. Done: no timed quota or verbatim requirement. Short references have limited evidence.', True)
        def consent() -> None:
            self._enroll_consent = not self._enroll_consent; self._draw_enrollment()
        self.button(frame, ("✓ " if self._enroll_consent else "○ ") + "I consent to record and store my voice locally", consent,
                    key="enrollment_consent", height=60).pack(fill="x", padx=self.px(12), pady=self.px(4))
        start = self.button(frame, "Start recording", self._start_enrollment, accent=True, key="enrollment_start")
        start.pack(fill="x", padx=self.px(12), pady=self.px(8)); start.button.configure(state="normal" if self._enroll_consent else "disabled")  # type: ignore[attr-defined]

    def _set_paragraph(self, text: str) -> None:
        try: reference_text(text)
        except ValueError as exc:
            self._notice = str(exc); self._show_status(); return
        self._paragraph = text; self._draw_enrollment()

    def _start_enrollment(self) -> None:
        if not self._enroll_consent: return
        extra = {'paragraph': self._paragraph} if self._enroll_target is None else {}
        if self._call("enrollment_start", self._enroll_name, self._enroll_target, consent=True, person_id=self._enroll_person_id, **extra):
            self._enroll_started = True; self.show_enrollment_progress()

    def show_enrollment_progress(self) -> None:
        self.page = "enrollment_progress"; frame = self._page("Recording reference", back=self.show_people)
        self._paragraph_label(frame, self._enroll_name)
        self.enroll_progress_label = self._paragraph_label(frame, "Waiting for microphone / quality status…")
        self._enroll_animation = VerifiedAnimation()
        self.enroll_progress = ttk.Progressbar(frame, orient="horizontal", mode="determinate", maximum=self._enroll_target or 1)
        self.enroll_progress.pack(fill="x", padx=self.px(12), pady=self.px(8))
        if self._enroll_target is None:
            self._paragraph_label(frame, 'Bar: verified portion of captured audio; no quota.', True)
        self.enroll_script_label = self._paragraph_label(frame, '', True)
        self.button(frame, 'Done · check reference' if self._enroll_target is None else 'Stop recording', lambda: self._call("enrollment_stop"), key="enrollment_stop").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "Save reference", self._save_enrollment, accent=True, key="enrollment_save").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame,'Review paragraph coverage',self.show_script_review,key='script_review').pack(fill='x',padx=self.px(12),pady=self.px(4))
        self.button(frame, "Discard this recording", self._cancel_enrollment, key="enrollment_cancel").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self._paragraph_label(frame, self._paragraph)
        self.button(frame, "Read more / continue naturally", self._read_more, key="enrollment_more").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self._page_update = self._update_enrollment; self._update_enrollment()

    def _update_enrollment(self) -> None:
        enrollment = self.snapshot.get("enrollment") or {}
        usable = self._number(enrollment.get("usable_s", enrollment.get("unique_usable_s", 0)))
        elapsed = self._number(enrollment.get("elapsed_s", 0))
        target = self._number(enrollment.get("target_sec", enrollment.get("target_s", self._enroll_target)))
        state = str(enrollment.get("state", enrollment.get("status", "starting")))
        level = enrollment.get("level", "not available")
        quality = enrollment.get("quality", enrollment.get("message", ""))
        paragraph = enrollment.get('target_sec', self._enroll_target) is None
        analyzed = self._number(enrollment.get('analyzed_s', 0))
        pending = max(0., elapsed - analyzed)
        value = self._enroll_animation.update(usable, time.monotonic())
        maximum = max(1., elapsed) if paragraph else max(1., target)
        self.enroll_progress.configure(maximum=maximum, value=min(value, maximum))
        support = f'{usable:.1f}s · no timed target' if paragraph else f'{usable:.1f} / {target:g}s'
        evidence = '\nLimited evidence: short reference' if enrollment.get('evidence_status') == 'limited_short_reference' else ''
        self.enroll_progress_label.configure(text=f'{state}\nVerified unique usable: {support}\nCaptured: {elapsed:.1f}s · pending quality: {pending:.1f}s\nLevel activity: {self._number(enrollment.get("activity_s")):.1f}s (not verified speech)\nClipped samples: {self._number(enrollment.get("clipping"))*100:.2f}%'+evidence+('\n'+str(enrollment['error']) if enrollment.get('error') else ''))
        estimate = enrollment.get('script_estimate') or {}
        coverage, match = estimate.get('estimated_coverage'), estimate.get('estimated_agreement')
        if paragraph:
            text = ('Estimated script coverage: '+f'{coverage:.0%}' if coverage is not None else 'Script estimate pending / unavailable')
            if match is not None:text += f' · agreement: {match:.0%}'
            text += f'\nASR analyzed: {self._number(estimate.get("analyzed_audio_s")):.1f}s. Skips and paraphrases are OK.'
        else:text = 'Bar follows verified speech only. Continue naturally if needed.'
        self.enroll_script_label.configure(text=text)
        self.actions["enrollment_save"].configure(state="normal" if state=='READY' and enrollment.get("can_save") else "disabled")
        self.actions['enrollment_stop'].configure(state='normal' if state=='RECORDING' else 'disabled')
        self.actions['script_review'].configure(state='normal' if state=='READY' and enrollment.get('script_evidence') else 'disabled')
        if state.casefold() == "saved": self.show_people()

    @staticmethod
    def _number(value: Any) -> float:
        try:
            result = float(value)
            return result if math.isfinite(result) and result >= 0 else 0.0
        except (TypeError, ValueError): return 0.0

    def _read_more(self) -> None:
        self._notice = "Continue with different natural speech, then tap Stop. Targets are goals; the backend limits a recording to 180 seconds."
        self._show_status()

    def _save_enrollment(self) -> None:
        if (self.snapshot.get("enrollment") or {}).get("state")=='READY' and (self.snapshot.get("enrollment") or {}).get("can_save"):
            self._call("enrollment_save")

    def _cancel_enrollment(self) -> None:
        self.confirm("Discard recording?", "Discard this unfinished reference? Existing saved people and reference sessions are retained.",
                     "Discard recording", lambda: self._finish_cancel(), cancel=self.show_enrollment_progress)

    def _finish_cancel(self) -> None:
        if self._call("enrollment_cancel"): self.show_people()

    def browse_file(self, purpose: str, directory: Path | None = None) -> None:
        self.page = "files"; current = (directory or Path.home()).expanduser().resolve()
        frame = self._page("Export location" if purpose == "export" else "Choose file", back=self.show_people if purpose != "replay" else self.show_settings)
        self._paragraph_label(frame, str(current), True)
        self.button(frame, "Enter a path with touch keyboard", lambda: self.keyboard("File path", str(current) + os.sep,
            lambda text: self._path_chosen(purpose, Path(text)), cancel=lambda: self.browse_file(purpose, current))).pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "↑ Parent folder", lambda: self.browse_file(purpose, current.parent)).pack(fill="x", padx=self.px(12), pady=self.px(4))
        if purpose == "export":
            self.button(frame, "Export here as people-export.zip", lambda: self._path_chosen(purpose, current / "people-export.zip"), accent=True).pack(fill="x", padx=self.px(12), pady=self.px(4))
        try:
            with os.scandir(current) as iterator:
                entries = []
                for entry in iterator:
                    if len(entries) >= 240: break
                    if not entry.name.startswith("."):
                        entries.append((entry.is_dir(follow_symlinks=False), entry.name, Path(entry.path)))
            entries.sort(key=lambda row: (not row[0], row[1].casefold()))
            for is_dir, name, path in entries:
                if purpose == "export" and not is_dir: continue
                action = (lambda p=path: self.browse_file(purpose, p)) if is_dir else (lambda p=path: self._path_chosen(purpose, p))
                self.button(frame, ("▸ " if is_dir else "") + name, action, height=56).pack(fill="x", padx=self.px(12), pady=self.px(3))
            if len(entries) >= 240:
                self._paragraph_label(frame, "Showing the first 240 entries. Enter the exact path to reach other files.", True)
        except OSError as exc:
            self._paragraph_label(frame, f"Cannot browse this folder: {exc}")

    def _path_chosen(self, purpose: str, path: Path) -> None:
        path = path.expanduser()
        if path.is_dir(): self.browse_file(purpose, path); return
        if purpose == "replay":
            if self._call("start_file", str(path)): self.home()
            return
        verb = "Export" if purpose == "export" else "Import"
        warning = f"{verb} personal voice profiles at:\n{path}\n\nProfiles contain sensitive voice data. Share only with consent. Ordinary files are not claimed to be encrypted. Imported files must pass the backend's integrity and compatibility checks."
        if purpose == "export" and path.exists(): warning += "\nAn existing export is at this path; the backend may refuse replacement."
        def commit() -> None:
            if self._call("export_people" if purpose == "export" else "import_people", str(path), consent=True):
                self.show_people()
        self.confirm(f"{verb} privacy", warning, f"I consent · {verb}", commit, cancel=self.show_people)

    def _preference(self, key: str, value: Any) -> None:
        if not self._call("settings_update", {key: value}): return
        self.preferences[key] = value
        if key == "caption_size":
            self.caption_text.configure(font=self.font(self.config["caption_sizes_px"][value]))
            self.active_text.configure(font=self.font(self.config["caption_sizes_px"][value]))
            self.show_settings()
        elif key == "spatial_visualization":
            if value:
                self.spatial_canvas.pack(fill="x", before=self.caption_text, padx=self.px(8), pady=(self.px(4), 0))
                self._update_spatial_visualization(force=True)
            else:
                self.spatial_canvas.pack_forget()
            self.show_settings()
        elif key in ("theme", "preview_zoom"):
            self.zoom = float(self.preferences.get("preview_zoom", 1))
            self.shell.destroy(); self._row_cache.clear(); self._marks.clear(); self._render_order.clear(); self._history_order.clear()
            self._build(); self._set_geometry(); self._show_status(); self.show_settings()
        else: self.show_settings()

    def _hide_spatial(self) -> None:
        if self._call("settings_update", {"spatial_visualization": False}):
            self.preferences["spatial_visualization"] = False
            self.spatial_canvas.pack_forget()

    def _choices(self, frame, key, choices) -> None:
        row = tk.Frame(frame, bg=self.color("background")); row.pack(fill="x", padx=self.px(12), pady=self.px(3))
        for value, title in choices:
            selected = self.preferences[key] == value
            self.button(row, title + (" ✓" if selected else ""),
                lambda k=key, v=value: self._preference(k, v), accent=selected, height=52,
                wrap=max(70, 380//len(choices)), key=f"{key}_{value}").pack(side="left", fill="x", expand=True, padx=self.px(1))

    def show_advanced(self) -> None:
        self.page = "advanced"; frame = self._page("Advanced comparison", back=self.show_settings)
        self.button(frame,'◇ Audio transcript review',self.show_audio_review,key='audio_review',height=60).pack(fill='x',padx=self.px(12),pady=self.px(5))
        self.button(frame,'◇ Session references / Undo',self.show_adaptation,key='adaptation',height=60).pack(fill='x',padx=self.px(12),pady=self.px(5))
        self.button(frame,'◇ Noise / model routing',self.show_noise,key='noise',height=60).pack(fill='x',padx=self.px(12),pady=self.px(5))
        self.button(frame,'Text-aware reference selection: '+('On' if self.snapshot.get('settings',{}).get('text_aware_references',False) else 'Off'),self._toggle_script_evidence,key='text_aware_references',height=60).pack(fill='x',padx=self.px(12),pady=self.px(5))
        self._paragraph_label(frame,'Optional post-recording paragraph contexts and advisory voice comparison. Original references still decide names. No phonetic model; applies at next enrollment / Start.',True)
        self.button(frame,'Compare base / alternate voice scores',self.show_reference_comparison,key='reference_comparison',height=60).pack(fill='x',padx=self.px(12),pady=self.px(5))
        self._paragraph_label(frame,'Ordinary name modes use one Unknown. Internal tracks, UUIDs and voice segmentation remain intact. Numbered modes are explicit comparisons.',True)
        for mode in MODES:
            if not MODE_METADATA[mode]['advanced']:continue
            row=MODE_METADATA[mode]
            self.button(frame,row['symbol']+' '+row['label'],lambda m=mode:self._choose_mode(m),height=65,key='mode_'+mode).pack(fill='x',padx=self.px(12),pady=self.px(5))
            self._paragraph_label(frame,row['full_name']+'\n'+row['description'],True)
        self.button(frame,'Live identity scores',self.show_identity_scores,key='identity_scores').pack(fill='x',padx=self.px(12),pady=self.px(5))
        self.button(frame,'Sensitivity / spatial weight',self.show_identity_parameters).pack(fill='x',padx=self.px(12),pady=self.px(5))
        self.button(frame,'Separate display features',self.show_display_features).pack(fill='x',padx=self.px(12),pady=self.px(5))

    def _advanced_numbered(self, value) -> None:
        if self._call("settings_update", {"numbered_unknowns": value}):
            self.preferences["numbered_unknowns"] = value
            self.show_advanced()

    def _microphone_preference(self, approved: bool, automatic: bool = False) -> None:
        values = {"microphone_preapproved": approved, "auto_start_listening": approved and automatic}
        if self._call("settings_update", values):
            self._mic_consented = approved
            self._cancel_auto_start_timer()
            self._auto_start_pending = False
            self.snapshot = dict(self.snapshot, settings={**self.snapshot.get("settings", {}), **values})
            self.show_settings()

    def show_settings(self) -> None:
        self.page = "settings"; frame = self._page("Settings")
        access = self.snapshot.get("settings", {})
        approved = access.get("microphone_preapproved") is True
        automatic = access.get("auto_start_listening") is True
        self.button(frame, "Microphone: " + ("Always allowed" if approved else "Ask on opening"),
                    lambda: self._microphone_preference(not approved), key="microphone_permission").pack(fill="x", padx=self.px(12), pady=self.px(3))
        if approved:
            self.button(frame, "Listen when app opens: " + ("On" if automatic else "Off"),
                        lambda: self._microphone_preference(True, not automatic), key="auto_listening").pack(fill="x", padx=self.px(12), pady=self.px(3))
        self.button(frame,'Developer Sessions · audio & transcripts',self.show_sessions,key='sessions').pack(fill='x',padx=self.px(12),pady=self.px(3))
        if self.snapshot.get('motion', {}).get('enabled'):
            self.button(frame, 'Motion sensor · relative direction', self.show_motion, key='motion').pack(fill='x',padx=self.px(12),pady=self.px(3))
        recipe = next((r for r in self._recipes() if r.get("id") == self.snapshot.get("recipe")), {})
        self._paragraph_label(frame, f"{recipe.get('name', self.snapshot.get('recipe', 'Recipe'))} · {self.snapshot.get('tap', 'O0')}\n" + recipe.get("description", "See Engine recipe & audio tap for the current backend policy."), True)
        self._paragraph_label(frame, "O0: XVF ASR output, live +3 dB once. O1: processed auto-selected output, unity gain. Prepared files already include their declared gain.", True)
        self.button(frame, "Engine recipe & audio tap", self.show_recipes).pack(fill="x", padx=self.px(12), pady=self.px(3))
        self._paragraph_label(frame, "Caption size · display only")
        self._choices(frame, "caption_size", [(name, name) for name in self.config["caption_sizes_px"]])
        self._paragraph_label(frame, "Text smoothing · optional added display delay")
        self._choices(frame, "display_smoothing_ms", [(0, "Immediate"), (150, "150 ms"), (300, "300 ms")])
        self._paragraph_label(frame, "Words never wait for identity. Dots resolve after 1.2s at the next display update; names need 0.2s of stability. Smoothing also affects that update. Inference is unchanged.", True)
        self.button(frame, "Advanced · modes and scores", self.show_advanced, key="advanced").pack(fill="x", padx=self.px(12), pady=self.px(3))
        enabled = bool(self.preferences.get("spatial_visualization", False))
        self.button(frame, "Live spatial display: " + ("ON · tap to hide" if enabled else "OFF · tap to show"),
                    lambda value=not enabled: self._preference("spatial_visualization", value),
                    key="spatial_visualization").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "Reset positions · tablet moved", self._reset_spatial,
                    key="reset_spatial").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "Beam angles · live diagnostics", self.show_beam_diagnostics,
                    key="beam_diagnostics").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self._paragraph_label(frame, "Contrast")
        self._choices(frame, "theme", [(theme, theme) for theme in self.config["themes"]])
        self._paragraph_label(frame, "Preview size · comfort zoom is not exact-pixel evidence")
        self._choices(frame, "preview_zoom", [(zoom, f"{round(zoom*100)}%") for zoom in self.config["preview_zooms"]])
        self._paragraph_label(frame, "Spatial modes can use fresh directions as association evidence. Colors identify hardware beams; names appear only when supplied by the pipeline. An angle alone does not prove identity. Reset positions clears location memory and preserves saved people.", True)
        self.button(frame, "Open a saved file…", lambda: self.browse_file("replay"), key="file_replay").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "Diagnostics / raw text", self.show_diagnostics, key="diagnostics").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, 'Text assistance / vocabulary', self.show_text_assistance, key='text_assistance').pack(fill='x',padx=self.px(12),pady=self.px(4))
        self.button(frame, "Mark a problem / save excerpt…", self.show_problem, key="mark_problem").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "Mode guide & human checks", self.show_help, key="help").pack(fill="x", padx=self.px(12), pady=self.px(4))
        settings = self.snapshot.get("settings") or {}
        self._paragraph_label(frame, "Session retention · saved people and pinned problems are preserved. RAM changes apply to the next session.", True)
        for setting, title, choices, unit in (
            ("completed_session_limit", "Completed sessions", (3, 10, 20), ""),
            ("session_quota_mib", "Session disk quota", (64, 128, 256), " MiB"),
            ("ram_horizon_sec", "Audio history in RAM", (60, 120), "s")):
            if setting not in settings:
                continue
            current = self.preferences.get(setting, settings[setting])
            self._paragraph_label(frame, title)
            row = tk.Frame(frame, bg=self.color("background")); row.pack(fill="x", padx=self.px(12), pady=self.px(4))
            for choice in choices:
                self.button(row, f"{choice}{unit}" + (" ✓" if current == choice else ""),
                    lambda key=setting, value=choice: self._preference(key, value), accent=current == choice,
                    key=f"retention_{setting}_{choice}", wrap=126).pack(side="left", fill="x", expand=True, padx=self.px(2))
        if "save_session_text" in settings:
            enabled = bool(self.preferences.get("save_session_text", settings["save_session_text"]))
            self.button(frame, "Session text journals: " + ("ON · tap to turn off" if enabled else "OFF · tap to turn on"),
                lambda value=not enabled: self._preference("save_session_text", value), key="session_text").pack(fill="x", padx=self.px(12), pady=self.px(4))
        retention = {key: value for key, value in settings.items() if any(word in key for word in ("retention", "quota", "horizon", "audio", "diagnostic"))}
        self._paragraph_label(frame, "Retention / disk: " + (json.dumps(retention, ensure_ascii=False) if retention else "Backend policy is not yet reported; no audio recording is enabled by this UI."), True)
        free_disk = self.snapshot.get("metrics", {}).get("free_disk_gib")
        self._paragraph_label(frame, f"Free data disk: {self._number(free_disk):.1f} GiB" if free_disk is not None else "Free data disk: awaiting backend measurement", True)

    def _reset_spatial(self) -> None:
        if self._call("reset_spatial"):
            self._notice = "Seat anchor invalidated; open the seat mode and Apply here again." if self.snapshot.get('mode') in SEAT_MODES else "Position memory cleared; saved people are unchanged."
            self._show_status()

    @staticmethod
    def _spatial_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    def _update_spatial_visualization(self, force: bool = False) -> None:
        """Render bounded controller telemetry, at most four times/second; no inference."""
        if not self.preferences.get("spatial_visualization", False):
            return
        now = time.monotonic()
        if not force and (self.page != "captions" or now - self._spatial_rendered_at < .25):
            return
        self._spatial_rendered_at = now
        view = self.snapshot.get("spatial_view") or self.snapshot.get("beam_diagnostics") or {}
        state = str(view.get("state", "OFF"))
        active = state.upper() == "RUNNING"
        stale_after = view.get("stale_after_seconds", .75)
        stale_after = float(stale_after) if self._spatial_number(stale_after) and stale_after >= 0 else .75
        beams = {beam["id"]: beam for beam in BEAMS}
        arrows = []
        for row in view.get("arrows", [])[:len(BEAMS)]:
            if not isinstance(row, dict) or row.get("id") not in beams:
                continue
            angle, age = row.get("angle_deg"), row.get("age_sec")
            if not (self._spatial_number(angle) and 0 <= angle <= 180 and self._spatial_number(age) and 0 <= age <= 12):
                continue
            fresh = active and age <= stale_after and row.get("fresh", True) is not False
            arrows.append({**beams[row["id"]], **row, "fresh": fresh})
        associations = []
        for row in view.get("associations", [])[:8]:
            if not isinstance(row, dict):
                continue
            angle, age = row.get("angle_deg"), row.get("age_sec")
            if not (self._spatial_number(angle) and 0 <= angle <= 180 and self._spatial_number(age) and 0 <= age <= 12):
                continue
            fresh = active and age <= stale_after and row.get("fresh") is True and row.get("speaking") is True
            associations.append({**row, "fresh": fresh})
        associations.sort(key=lambda row: (not row["fresh"], row["age_sec"]))
        associations = associations[:2]
        # Repainting depends on visible state, not raw high-frequency receipt times.
        signature = (state, str(view.get("message", "")), self.spatial_canvas.winfo_width(),
                     tuple((a["id"], round(a["angle_deg"], 1), a["fresh"], bool(a.get("selected")), bool(a.get("speech"))) for a in arrows),
                     tuple((str(a.get("label", "Unknown")), round(a["angle_deg"], 1), a["fresh"], int(a["age_sec"])) for a in associations),
                     bool(view.get("speech")), str(view.get("energy")), str(view.get('seating',{}).get('valid')))
        if signature == self._spatial_signature and not force:
            return
        self._spatial_signature = signature
        canvas = self.spatial_canvas
        canvas.delete("all")
        width = max(self.px(360), canvas.winfo_width())
        cx, cy, radius = self.px(107), self.px(97), self.px(61)
        canvas.create_text(self.px(10), self.px(12), anchor="w", text="XVF board · tap to hide", font=self.font(12, True), fill=self.color("text"))
        canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius, start=0, extent=180,
                          style="arc", outline=self.color("border"))
        canvas.create_line(cx-radius, cy, cx+radius, cy, fill=self.color("border"))
        for angle, text in ((180, "180°"), (90, "90° front/rear"), (0, "0°")):
            x, y = arrow_tip(angle, cx, cy, radius+self.px(16))
            if angle == 90: y = self.px(27)
            canvas.create_text(x, y, text=text, fill=self.color("muted"), font=self.font(11))
        for row in arrows:
            x, y = arrow_tip(row["angle_deg"], cx, cy, radius*row["radius"])
            canvas.create_line(cx, cy, x, y, arrow="last", arrowshape=(self.px(7), self.px(9), self.px(3)),
                fill=row["color"] if row["fresh"] else self.color("muted"),
                width=self.px(4 if row.get("selected") and row["fresh"] else 2),
                dash=() if row["fresh"] else (self.px(3), self.px(3)),
                tags=("spatial_beam", row["id"], "fresh" if row["fresh"] else "stale"))
            marker = "▲" if row['id'].startswith('focused') else "◆" if row['id']=='free_running' else "■"
            if not row['fresh']: marker = {'▲':'△','◆':'◇','■':'□'}[marker]
            canvas.create_text(x, y, text=marker, font=self.font(11), fill=row['color'] if row['fresh'] else self.color('muted'), tags=("beam_shape",))
            if row.get('selected') and row['fresh']:
                canvas.create_oval(x-self.px(7), y-self.px(7), x+self.px(7), y+self.px(7), outline=self.color('text'), width=2, tags=("selected_ring",))
        for row in associations:
            x, y = arrow_tip(row["angle_deg"], cx, cy, radius+self.px(4))
            color = self.color("text" if row["fresh"] else "muted")
            if not row["fresh"]:
                canvas.create_line(cx, cy, x, y, fill=color, dash=(self.px(2), self.px(4)), tags=("spatial_position", "stale"))
            canvas.create_oval(x-self.px(4), y-self.px(4), x+self.px(4), y+self.px(4),
                fill=color if row["fresh"] else self.color("surface"), outline=color, tags=("spatial_association",))
        canvas.create_rectangle(cx-self.px(11), cy-self.px(3), cx+self.px(11), cy+self.px(5),
                                fill=self.color("raised"), outline=self.color("text"))
        tx = self.px(207)
        text_width = max(self.px(140), width-tx-self.px(8))
        selected = next((row for row in arrows if row.get("selected") and row["fresh"]), None)
        speaking = bool(active and selected and (view.get("speech") or selected.get("speech")))
        badge = "● Fresh speaking direction" if speaking else "Fresh beam · speech unconfirmed" if any(a["fresh"] for a in arrows) else "No fresh direction"
        canvas.create_text(tx, self.px(13), anchor="w", text=badge, font=self.font(12, True),
                           fill=self.color("accent" if speaking else "muted"), width=text_width, tags=("spatial_badge",))
        selection = f"{selected['label']} · {selected['angle_deg']:.0f}°" if selected else "Selected direction: —"
        canvas.create_text(tx, self.px(36), anchor="w", text=selection, font=self.font(12),
                           fill=selected["color"] if selected else self.color("muted"), width=text_width, tags=("spatial_selected",))
        energy = view.get("energy")
        energy_text = f"Energy {energy:.3g} · device units" if active and self._spatial_number(energy) else "Energy unavailable"
        canvas.create_text(tx, self.px(53), anchor="w", text=energy_text, font=self.font(11), fill=self.color("muted"), tags=("spatial_energy",))
        for index, row in enumerate(associations):
            label = "≈ " + str(row.get("label") or "Unknown").replace("\n", " ")[:20]
            suffix = "speaking" if row["fresh"] else f"last known {row['age_sec']:.0f}s"
            tail = f" · {row['angle_deg']:.0f}° · {suffix}"
            while len(label) > 2 and self._spatial_font.measure(label+tail) > text_width:
                label = label[:-2] + "…"
            canvas.create_text(tx, self.px(73+index*17), anchor="w", text=label+tail,
                font=self.font(11), fill=self.color("text" if row["fresh"] else "muted"),
                tags=("spatial_name", "fresh" if row["fresh"] else "stale"))
        if not associations:
            canvas.create_text(tx, self.px(75), anchor="w", text="No speaker association", font=self.font(11),
                               fill=self.color("muted"), width=text_width, tags=("spatial_name",))
        for x, title, color in ((10,"▲ F1",BEAMS[0]['color']), (51,"▲ F2",BEAMS[1]['color']), (96,"◆ scan",BEAMS[2]['color']),
                                (161,"■ outputs",self.color('muted')), (249,"○ selected",self.color('text')), (341,"● ≈ match",self.color('text'))):
            canvas.create_text(self.px(x), self.px(114), anchor="w", text=title, font=self.font(11), fill=color, tags=("beam_key",))
        legend="Solid: fresh · dashed: last known · ≈ estimated, not verified"
        if self.snapshot.get('mode') in SEAT_MODES:legend='Seats: '+('manual anchor active · labels may be assumptions' if self.snapshot.get('seating',{}).get('valid') else 'RE-ANCHOR REQUIRED · keep captions')
        motion = view.get('motion')
        if motion:
            legend = ('Startup frame · turn %.1f° · drift possible' % motion.get('yaw_deg', 0)) if motion.get('valid') and motion.get('compensation') else str(motion.get('reason', 'Motion reference unavailable'))[:68]
        canvas.create_text(self.px(10), self.px(134), anchor="w", text=legend,
                           font=self.font(11), fill=self.color("muted"), tags=("spatial_legend",))

    def show_motion(self) -> None:
        self.page = 'motion'; frame = self._page('Motion & relative direction')
        status = self._paragraph_label(frame, '', True)
        def update():
            row = self.snapshot.get('motion', {})
            status.configure(text=f"BMI270 · {row.get('state', 'unavailable')}\nHorizontal turn {row.get('yaw_deg', 0):.1f}° · frame {row.get('frame_generation', 0)}\n"+
                str(row.get('error') or row.get('reason') or 'Waiting for sensor'))
        self._page_update = update; update()
        mounted = self.snapshot.get('motion', {}).get('fixed_mount', False)
        if not mounted:
            self._paragraph_label(frame, 'Not assembled: sensor data is diagnostic only. Mount as described before enabling: sensor +X down, +Y right, +Z toward the front; MIC3 at screen right. All directions are viewed from the display front.', True)
        def mounting():
            if self._call('motion_mount_configure', not mounted): self.home()
        self.button(frame, 'Mark sensor unmounted' if mounted else 'Confirm mounted as described', mounting,
                    key='motion_mount').pack(fill='x',padx=self.px(12),pady=self.px(4))
        self._paragraph_label(frame, 'A fresh relative reference starts automatically after two quiet seconds at startup. Normal tilt and turns keep that reference; no repeated manual calibration is needed. The sensor must stay fixed to the array.')
        self._paragraph_label(frame, 'Experimental horizontal bearings assume speakers at array height, in the initial 0–180° half-plane. Gyro drift and front/back ambiguity remain. Moving the tablet to another position can change the actual speaker bearing.')
        enabled = self.snapshot.get('motion', {}).get('compensation', False)
        def toggle():
            if self._call('motion_configure', not enabled): self.home()
        self.button(frame, 'Rotation assistance: '+('On' if enabled else 'Off'), toggle,
                    key='motion_compensation').pack(fill='x',padx=self.px(12),pady=self.px(4))
        self.button(frame, 'Start a new direction reference', self._reset_spatial,
                    key='motion_reset').pack(fill='x',padx=self.px(12),pady=self.px(4))
        self._paragraph_label(frame, 'A sensor interruption automatically starts a NEW reference once still; old locations are discarded. Acceleration clears old locations but retains heading. Assigned seats require Apply after relocation. Raw angles remain in Beam diagnostics. This is not a compass or position tracker.', True)

    def show_beam_diagnostics(self) -> None:
        self.page = "beam_diagnostics"; frame = self._page("Beam angles", back=self.show_settings)
        self._paragraph_label(frame, "Hardware beams · colors identify outputs, not people. Music and other sounds can move these arrows.", True)
        self.beam_status_label = self.label(frame, "Waiting for live input", size="small_font_px")
        self.beam_status_label.pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.beam_canvas = tk.Canvas(frame, width=self.px(390), height=self.px(225),
                                    bg=self.color("background"), highlightthickness=0)
        self.beam_canvas.pack(fill="x", padx=self.px(8), pady=self.px(4))
        self.beam_legend = {}
        for beam in BEAMS:
            row = self.label(frame, beam["label"] + " · unavailable", size="small_font_px")
            row.configure(fg=beam["color"])
            row.pack(fill="x", padx=self.px(12), pady=self.px(2))
            self.beam_legend[beam["id"]] = row
        self._paragraph_label(frame, "0° = MIC3 end; 180° = MIC0 end. The 90° axis folds front and rear together; it does not determine which side of the board a sound is on.", True)
        self._paragraph_label(frame, "Ages measure host receipt, not the age of the DSP estimate. Stale or invalid arrows disappear. Several arrows do not prove several speakers. This display does not steer beams or change recognition.", True)
        self._page_update = self._update_beam_diagnostics
        self.beam_canvas.bind("<Configure>", lambda _e: self._update_beam_diagnostics())
        self._update_beam_diagnostics()

    def _update_beam_diagnostics(self) -> None:
        if self.page != "beam_diagnostics":
            return
        diagnostic = self.snapshot.get("beam_diagnostics") or {}
        state = str(diagnostic.get("state", "OFF"))
        status = state + " · " + str(diagnostic.get("error") or diagnostic.get("reason") or
                 ("Recent host readbacks; source age unverified" if state == "RUNNING" else "Start live input to observe the XVF"))
        self.beam_status_label.configure(text=status[:350])
        canvas = self.beam_canvas
        width = max(self.px(320), canvas.winfo_width())
        center_x, center_y = width / 2, self.px(188)
        radius = min(width / 2 - self.px(30), self.px(156))
        canvas.delete("all")
        canvas.create_arc(center_x-radius, center_y-radius, center_x+radius, center_y+radius,
                          start=0, extent=180, style="arc", outline=self.color("border"), width=2)
        canvas.create_line(center_x-radius, center_y, center_x+radius, center_y,
                           fill=self.color("border"), width=2)
        for angle, label in ((180, "180°\nMIC0"), (90, "90°"), (0, "0°\nMIC3")):
            x, y = arrow_tip(angle, center_x, center_y, radius + self.px(16))
            canvas.create_text(x, y + (self.px(13) if angle != 90 else 0), text=label,
                               fill=self.color("muted"), font=self.font(12))
        arrows = {row.get("id"): row for row in diagnostic.get("arrows", [])
                  if isinstance(row, dict)} if state == "RUNNING" else {}
        for beam in BEAMS:
            row = arrows.get(beam["id"], {})
            angle, age = row.get("angle_deg"), row.get("age_sec")
            valid = all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                        for value in (angle, age))
            valid = valid and 0 <= angle <= 180 and 0 <= age <= self._number(diagnostic.get("stale_after_seconds", 2.5))
            if valid:
                x, y = arrow_tip(angle, center_x, center_y, radius * beam["radius"])
                canvas.create_line(center_x, center_y, x, y, arrow="last", arrowshape=(self.px(10), self.px(13), self.px(5)),
                                   fill=beam["color"], width=self.px(3),
                                   dash=(self.px(6), self.px(3)) if beam["field"] == "AUDIO_MGR_SELECTED_AZIMUTHS" else (),
                                   tags=("beam_arrow", beam["id"]))
                self.beam_legend[beam["id"]].configure(text=f"{beam['label']} · {angle:.1f}° · received {age:.1f}s ago")
            else:
                self.beam_legend[beam["id"]].configure(text=beam["label"] + " · unavailable / stale")
        canvas.create_oval(center_x-self.px(4), center_y-self.px(4), center_x+self.px(4), center_y+self.px(4),
                           fill=self.color("text"), outline="")

    def show_diagnostics(self) -> None:
        self.page = "diagnostics"; frame = self._page("Diagnostics", back=self.show_settings)
        self._paragraph_label(frame, "Raw text is diagnostic evidence; provisional casing never replaces it.", True)
        self.button(frame, "Beam angles · live diagnostics", self.show_beam_diagnostics,
                    key="beam_diagnostics").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "Mark a problem / save excerpt…", lambda: self.show_problem(back=self.show_diagnostics),
                    key="mark_problem").pack(fill="x", padx=self.px(12), pady=self.px(4))
        display = tk.Text(frame, wrap="word", font=self.font(14), height=23, bg=self.color("surface"), fg=self.color("text"), relief="flat")
        display.pack(fill="both", expand=True, padx=self.px(8), pady=self.px(8))
        def update() -> None:
            doc = dict(state=self.snapshot.get("state"), status=self.snapshot.get("status"),
                       mode=self.snapshot.get("mode"), recipe=self.snapshot.get("recipe"), tap=self.snapshot.get("tap"),
                       raw_identity_decisions=self.snapshot.get("metrics", {}).get("recent_identity_decisions", [])[-3:],
                       raw_caption_identity=[r.get('raw_identity') for r in self.snapshot.get('rows', [])[-6:]],
                       client=self.measure_client(), metrics=self.snapshot.get("metrics", {}), error=self.snapshot.get("error"),
                       beam_diagnostics=self.snapshot.get("beam_diagnostics", {}),
                       presentation=dict(smoothing_ms=self.preferences['display_smoothing_ms'],
                           batch_delay_ms=self.presentation_delays_ms, pending_limit_ms=1200, name_stability_ms=200),
                       recent_rows=self.snapshot.get("rows", [])[-6:])
            value = json.dumps(doc, indent=2, ensure_ascii=False, default=str)[:16000]
            if getattr(display, "_last_value", None) != value:
                view = display.yview(); display.configure(state="normal"); display.delete("1.0", "end"); display.insert("1.0", value)
                display.configure(state="disabled"); display.yview_moveto(view[0]); display._last_value = value
        self._page_update = update; update()

    def show_problem(self, back: Callable | None = None) -> None:
        self.page = "problem"; return_to = back or self.show_settings
        frame = self._page("Save a problem", back=return_to)
        self._paragraph_label(frame, "Mark the current issue to retain local diagnostic evidence outside rolling session cleanup. The saved location appears in status/Diagnostics.")
        self._paragraph_label(frame, "Audio is optional. Saving recent audio copies up to 30 seconds already in the current RAM buffer into your private data folder. It can contain other people's voices. Save only with their consent. This action never starts a microphone or plays audio.", True)
        def mark(audio: bool) -> None:
            if self._call("mark_problem", save_audio=audio):
                return_to()
        self.button(frame, "Mark without audio", lambda: mark(False), accent=True,
                    key="problem_without_audio").pack(fill="x", padx=self.px(12), pady=self.px(5))
        self.button(frame, "I consent · Save recent 30s audio", lambda: mark(True),
                    key="problem_with_audio", height=60).pack(fill="x", padx=self.px(12), pady=self.px(5))
        self.button(frame, "Cancel", return_to, key="problem_cancel").pack(fill="x", padx=self.px(12), pady=self.px(5))

    def show_help(self) -> None:
        self.page = "help"; frame = self._page("Mode guide")
        self._paragraph_label(frame,'Text assistance is separate from identity. Settings → Text assistance offers spelling review and explicitly approved contextual rules. ✎ marks assisted text; Off restores original formatting. Raw/final/manual layers and undo stay in Sessions. Enrolled-name acoustic bias is unavailable because the matching ASR BPE vocabulary is not bound. Greedy decoding is unchanged.',True)
        self._paragraph_label(frame, MODE_LEGEND)
        self._paragraph_label(frame, "Simulation support belongs to the configuration and its tested conditions; all personal live use still needs real-world validation. An experimental marker never blocks selecting a mode.", True)
        for mode in MODES:
            metadata = self._mode_metadata(mode)
            self._paragraph_label(frame, metadata["symbol"] + " " + metadata["label"])
            self._paragraph_label(frame, metadata["description"], True)
            if metadata["parent"]:
                self._paragraph_label(frame, "Existing method: " + metadata["parent"], True)
        self._paragraph_label(frame, "Spatial-assisted supports voice and anonymous continuity with recent positions. Strongly spatial-assisted favors seat continuity more heavily; it can misassociate people who swap seats or overlap. Strong voice disagreement and expiring location evidence allow recovery. Neither mode turns an angle into proof of identity.")
        self._paragraph_label(frame, "Settings → Live spatial display adds a compact semicircle above captions. Solid arrows are fresh beam readbacks; the speaking badge requires fresh speech evidence. Dashed arrows and hollow dots are stale/last-known positions, not current speakers. Names come from the pipeline, never from the drawing. Colors identify hardware outputs. The folded 0–180° frame cannot resolve front from rear.")
        self._paragraph_label(frame, "On the configured CM5, BMI270 tracks three-dimensional turns and tilt in an automatic startup reference. Acceleration discards uncertain old locations; voice matches can rebuild them. Assigned-seat modes require Apply after relocation. Settings → Motion sensor shows status and the optional new-reference control. Saved people are preserved. The drawing performs no inference.")
        self._paragraph_label(frame, "Recipes choose existing engine settings; O0/O1 choose compatible audio taps. The menu shows backend availability and evidence status. Personalization is a new application condition, not a research accuracy guarantee.")
        self._paragraph_label(frame, "Human checks still needed: consent and speak through the identified XVF; record and save your own voice reference; restart, then test different speech; try Unknown/wrong-person behavior. A stub or saved file does not verify live enrollment.")
        self._paragraph_label(frame, "Stop actually stops capture through the controller. If the separate hiding filter hides words, Show all captions restores full visibility while keeping the identity mode. The documented evaluation firmware has an eight-hour limit; stop between sessions and follow the device recovery guide rather than resetting during speech.")
        self._paragraph_label(frame, "CM5 I2S capture, portrait touch and BMI270 sensing have bounded bring-up checks. Physical rotation accuracy and sustained real-world recognition still need field testing. Optional camera and unassigned GPIO remain disabled.", True)

    def close(self) -> None:
        self._cancel_auto_start_timer()
        if self._closed or self._closing: return
        if self._call("close"):
            self._closing = True
            if self._display_handle:
                self.root.after_cancel(self._display_handle); self._display_handle = None
            self._pending_rows = None
            self._notice = "Closing · waiting for capture and workers to release safely…"
            self._show_status()
            for key in ("start_stop", "mode", "people", "settings", "rescue", "backend"):
                self.actions[key].configure(state="disabled")
