"""Portrait touch frontend; no model/audio/device ownership. See docs/UI_ITERATION.md."""
from __future__ import annotations

import ctypes
import json
import math
import os
from pathlib import Path
import re
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from .casing import provisional_case

CONFIG = Path(__file__).resolve().parents[1] / "config" / "ui.json"
MODES = {
    "caption_only": ("Captions", "All words, neutral labels. Optional speaker inference is off."),
    "enrolled_names": ("Enrolled names", "Your people's names or Unknown. All words stay visible; internal association may still run."),
    "anonymous_conversation": ("Anonymous", "Speaker labels without looking up personal names. Labels can split or merge."),
    "open_with_names": ("Conversation + names", "Anonymous continuity with cautious matches to your personal profiles."),
    "selected_focus": ("Selected focus", "Emphasize selected people in the full transcript. Matching is experimental."),
}


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


class PrototypeUI:
    """Thin controller-driven frontend. Construct on Tk's owning/main thread."""
    def __init__(self, root: tk.Tk, controller: Any):
        self.root, self.controller = root, controller
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.preferences = dict(self.config["defaults"])
        # Saved display preferences are metadata, never a reason to start capture.
        initial = controller.snapshot()
        settings = initial.get("settings", {}) if isinstance(initial, dict) else {}
        for key, choices in (("caption_size", self.config["caption_sizes_px"]),
                             ("theme", self.config["themes"]), ("preview_zoom", self.config["preview_zooms"])):
            if settings.get(key) in choices:
                self.preferences[key] = settings[key]
        self.zoom = float(self.preferences["preview_zoom"])
        self.snapshot: dict[str, Any] = {}
        self.page = "captions"
        self._closed = False
        self._closing = False
        self._poll_handle: str | None = None
        self._mic_consented = False
        self._row_cache: dict[str, tuple[str, str, bool]] = {}
        self._marks: dict[str, tuple[str, str]] = {}
        self._render_order: list[str] = []
        self._mark_number = 0
        self._follow_live = True
        self._people_signature = ""
        self._enroll_name = ""
        self._enroll_person_id: str | None = None
        self._enroll_target = 30
        self._enroll_consent = False
        self._enroll_started = False
        self._paragraph = self.config["enrollment_paragraph"]
        self._notice = ""
        self._page_update: Callable[[], None] | None = None
        self.client_metrics: dict[str, Any] = {}
        self.actions: dict[str, tk.Widget] = {}
        self.root.title("Just Peachy · portrait prototype")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.resizable(False, False)
        self._build()
        self._set_geometry()
        self.poll()

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
            takefocus=True, wraplength=self.px(wrap or 390), cursor="hand2")
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
        self.status_label = self.label(header, "Ready · microphone off", size="small_font_px", muted=True)
        self.status_label.configure(wraplength=self.px(456)); self.status_label.pack(fill="x", pady=(self.px(3), 0))
        self.error_label = self.label(header, "", size="small_font_px")
        self.error_label.configure(fg=self.color("error"), wraplength=self.px(456))
        footer = tk.Frame(self.shell, bg=self.color("background"))
        footer.pack(side="bottom", fill="x")
        self.rescue = self.button(footer, "Show all captions · experimental identity", self.show_all_captions,
                                 key="rescue", height=48)
        self.rescue.pack(fill="x", padx=self.px(4), pady=(0, self.px(4)))
        nav = tk.Frame(footer, bg=self.color("background")); nav.pack(fill="x")
        for index, (text, command, key) in enumerate((
            ("Start", self.toggle_listening, "start_stop"), ("Mode", self.show_modes, "mode"),
            ("People", self.show_people, "people"), ("Settings", self.show_settings, "settings"))):
            nav.columnconfigure(index, weight=1, uniform="navigation")
            self.button(nav, text, command, accent=index == 0, key=key, height=60, wrap=112).grid(row=0, column=index, sticky="nsew", padx=self.px(1))
        self.body = tk.Frame(self.shell, bg=self.color("background")); self.body.pack(fill="both", expand=True)
        self.caption_page = tk.Frame(self.body, bg=self.color("background"))
        self.caption_page.pack(fill="both", expand=True)
        self.caption_text = tk.Text(self.caption_page, wrap="word", state="disabled", font=self.font(self.config["caption_sizes_px"][self.preferences["caption_size"]]),
            bg=self.color("background"), fg=self.color("text"), relief="flat", borderwidth=0,
            padx=self.px(16), pady=self.px(14), cursor="arrow", takefocus=False,
            selectbackground=self.color("selected"), highlightthickness=0, spacing1=self.px(4), spacing3=self.px(5))
        self.caption_text.pack(fill="both", expand=True)
        self.caption_text.tag_configure("speaker", font=self.font("small_font_px", True), foreground=self.color("muted"))
        self.caption_text.tag_configure("selected", background=self.color("selected"))
        self.caption_text.tag_configure("partial", foreground=self.color("text"))
        self.caption_text.tag_configure("placeholder", foreground=self.color("muted"))
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
        self._render_rows([], force=True)

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
                for key in ("start_stop", "mode", "people", "settings", "rescue"):
                    self.actions[key].configure(state="normal")
            self._show_status()
            self._render_rows(snapshot.get("rows", []))
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
        self.status_label.configure(text=f"{MODES.get(mode, (mode,))[0]} · {profile} · {status}"[:200])
        error = self._notice or self.snapshot.get("error") or ""
        if error:
            self.error_label.configure(text=str(error)[:240]); self.error_label.pack(fill="x", pady=(self.px(4), 0))
        else:
            self.error_label.pack_forget()
        self.actions["start_stop"].configure(text="Stop" if self._running() else "Start")
        strict = mode == "selected_focus" and bool(self.snapshot.get("strict"))
        self.actions["rescue"].configure(text="STRICT FILTER · Show all captions" if strict else "Show all captions · experimental identity")

    def _display_row(self, row: dict[str, Any]) -> tuple[str, str, bool]:
        names = [str(p.get("name", "")) for p in self.snapshot.get("people", [])]
        if row.get("final") and row.get("final_punctuated_display_text"):
            text = str(row["final_punctuated_display_text"])
        elif row.get("provisional_display_text") is not None:
            text = str(row["provisional_display_text"])
        else:
            text = provisional_case(str(row.get("raw_asr_text", "")), names, self.config["acronyms"])
        mode = self.snapshot.get("mode", "caption_only")
        label = str(row.get("label") or "Unknown")
        if mode == "caption_only":
            label = "Captions"
        elif mode == "enrolled_names" and re.fullmatch(r"speaker[ _-]*\d+", label, re.IGNORECASE):
            label = "Unknown"
        return label, text, bool(row.get("selected")) and mode == "selected_focus"

    def _render_rows(self, rows: list[dict[str, Any]], force: bool = False) -> None:
        strict = self.snapshot.get("mode") == "selected_focus" and bool(self.snapshot.get("strict"))
        visible = [row for row in rows if not strict or row.get("selected")]
        ids = [str(row["id"]) for row in visible]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate caption row IDs")
        current = {str(row["id"]): self._display_row(row) for row in visible}
        if not force and ids == self._render_order and current == self._row_cache:
            return
        text = self.caption_text
        follow = self._follow_live
        anchor = text.index("@0,0")
        text.mark_set("view_anchor", anchor); text.mark_gravity("view_anchor", "left")
        anchor_row = next((rid for rid in self._render_order if text.compare(self._marks[rid][0], "<=", anchor)
                           and text.compare(anchor, "<", self._marks[rid][1])), None)
        anchor_offset = (text.count(self._marks[anchor_row][0], anchor, "chars") or (0,))[0] if anchor_row else 0
        text.configure(state="normal")
        append_only = not force and ids[:len(self._render_order)] == self._render_order and bool(self._render_order)
        if (not append_only and ids != self._render_order) or force:
            text.delete("1.0", "end")
            for start, end in self._marks.values():
                text.mark_unset(start, end)
            self._marks.clear(); self._row_cache.clear(); self._render_order = []
        if not ids:
            text.delete("1.0", "end")
            placeholder = "No selected speech is visible.\n\nUse Show all captions to recover the full view." if strict and rows else "Your words will appear here.\n\nChoose Start when you are ready. Microphone access requires your consent."
            text.insert("1.0", placeholder, "placeholder")
        else:
            if not self._render_order:
                text.delete("1.0", "end")
            for rid in ids:
                value = current[rid]
                if rid in self._marks and self._row_cache.get(rid) == value:
                    continue
                if rid not in self._marks:
                    self._mark_number += 1
                    start, end = f"row_{self._mark_number}_start", f"row_{self._mark_number}_end"
                    text.mark_set(start, "end-1c"); text.mark_gravity(start, "left")
                    text.mark_set(end, start); text.mark_gravity(end, "right")
                    self._marks[rid] = start, end
                else:
                    start, end = self._marks[rid]
                    # Adjacent row starts must stay on their own side of this edit.
                    next_index = self._render_order.index(rid) + 1 if rid in self._render_order else 0
                    next_start = self._marks[self._render_order[next_index]][0] if next_index and next_index < len(self._render_order) else None
                    text.delete(start, end)
                    if next_start:
                        text.mark_gravity(next_start, "right")
                label, caption, selected = value
                text.mark_gravity(end, "right")
                text.insert(start, f"{label}\n{caption}\n\n")
                text.mark_gravity(end, "left")
                text.tag_remove("speaker", start, end)
                text.tag_remove("selected", start, end)
                text.tag_add("speaker", start, f"{start}+{len(label)}c")
                if selected:
                    text.tag_add("selected", start, end)
                if rid in self._render_order:
                    next_index = self._render_order.index(rid) + 1
                    if next_index < len(self._render_order):
                        text.mark_gravity(self._marks[self._render_order[next_index]][0], "left")
            self._render_order = ids
            self._row_cache = current
        text.configure(state="disabled")
        if follow:
            text.see("end")
        elif anchor_row in self._marks:
            text.yview(f"{self._marks[anchor_row][0]}+{anchor_offset}c")
        else:
            text.yview("view_anchor")

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
        self.caption_text.see("end")

    def home(self) -> None:
        self.page = "captions"; self._page_update = None
        self.dialog_page.pack_forget(); self.caption_page.pack(fill="both", expand=True)

    def _page(self, title: str, *, scroll: bool = True, back: Callable | None = None) -> tk.Frame:
        self._page_update = None
        self.caption_page.pack_forget()
        for child in self.dialog_page.winfo_children():
            child.destroy()
        self.dialog_page.pack(fill="both", expand=True)
        top = tk.Frame(self.dialog_page, bg=self.color("background")); top.pack(fill="x")
        self.button(top, "‹ Captions" if back is None else "‹ Back", back or self.home, height=48).pack(side="left", fill="x", expand=True)
        self.label(top, title, size="heading_font_px", bold=True).pack(side="left", fill="x", expand=True, padx=self.px(8))
        if scroll:
            area = TouchScroll(self.dialog_page, self); area.pack(fill="both", expand=True)
            return area.inner
        frame = tk.Frame(self.dialog_page, bg=self.color("background")); frame.pack(fill="both", expand=True)
        return frame

    def _paragraph_label(self, parent: tk.Misc, value: str, muted: bool = False) -> tk.Label:
        label = self.label(parent, value, muted=muted)
        label.pack(fill="x", padx=self.px(12), pady=self.px(8))
        return label

    def confirm(self, title: str, message: str, action: str, callback: Callable, *, cancel: Callable | None = None) -> None:
        self.page = "consent"
        frame = self._page(title, back=cancel)
        self._paragraph_label(frame, message)
        self.button(frame, action, callback, accent=True, key="confirm").pack(fill="x", padx=self.px(12), pady=self.px(8))
        self.button(frame, "Cancel", cancel or self.home, key="cancel").pack(fill="x", padx=self.px(12), pady=self.px(4))

    def toggle_listening(self) -> None:
        if self._running():
            self._call("stop")
            return
        def start() -> None:
            if self._call("start_live", consent=True):
                self._mic_consented = True; self.home()
        if not self._mic_consented:
            self.confirm("Microphone consent", "Start listening through the selected XVF microphone array? Speech is processed locally. Session text and diagnostic retention follow Settings. Enrollment is separate. Stop releases capture. The app does not change your default speakers.", "I consent · Start listening", start)
        else:
            start()

    def show_all_captions(self) -> None:
        if self._call("switch", mode="caption_only", strict=False):
            self.snapshot = dict(self.snapshot, mode="caption_only", strict=False)
            self._render_rows(self.snapshot.get("rows", []), force=True)
            self.home()

    def _choose_mode(self, mode: str) -> None:
        if self._call("switch", mode=mode, strict=False):
            self.home()

    def show_modes(self) -> None:
        self.page = "modes"; frame = self._page("Mode")
        self._paragraph_label(frame, "Modes change naming and emphasis. Recipes and audio taps are separate controls.", True)
        for mode, (name, description) in MODES.items():
            selected = mode == self.snapshot.get("mode", "caption_only")
            self.button(frame, ("✓ " if selected else "") + name, lambda m=mode: self._choose_mode(m),
                        accent=selected, key=f"mode_{mode}").pack(fill="x", padx=self.px(12), pady=(self.px(6), 0))
            self._paragraph_label(frame, description, True)
        self.button(frame, "Choose selected people", self.show_roster, key="roster").pack(fill="x", padx=self.px(12), pady=self.px(6))
        self.button(frame, "Experimental · show selected only", self.request_strict, key="strict").pack(fill="x", padx=self.px(12), pady=self.px(6))
        self.button(frame, "Engine recipe & audio tap", self.show_recipes, key="recipes").pack(fill="x", padx=self.px(12), pady=self.px(6))
        self.button(frame, "Mode guide", self.show_help).pack(fill="x", padx=self.px(12), pady=self.px(6))

    def request_strict(self) -> None:
        if not self.snapshot.get("selected_ids"):
            self._notice = "Choose at least one enrolled person before strict filtering."
            self.show_roster(); self._show_status(); return
        self.confirm("Experimental filter", "Selected-only may hide intended speech when identity is unknown or wrong. It hides text; it does not acoustically remove other voices. The full internal transcript is retained. Show all captions is always one tap away.", "Enable selected-only view", self._enable_strict, cancel=self.show_modes)

    def _enable_strict(self) -> None:
        if self._call("switch", mode="selected_focus", strict=True):
            self.home()

    def show_roster(self) -> None:
        self.page = "roster"; frame = self._page("Selected people", back=self.show_modes)
        self._paragraph_label(frame, "Select one or more profiles. Names may coincide; the app tracks their separate profile IDs.", True)
        selected = set(self.snapshot.get("selected_ids", []))
        for person in self.snapshot.get("people", []):
            pid = str(person["id"])
            def toggle(person_id: str = pid) -> None:
                values = set(self.snapshot.get("selected_ids", []))
                values.symmetric_difference_update({person_id})
                if self._call("switch", selected_ids=sorted(values), strict=False):
                    self.snapshot["selected_ids"] = sorted(values); self.show_roster()
            self.button(frame, ("✓ " if pid in selected else "○ ") + str(person["name"]) + f" · {pid[:6]}", toggle,
                        accent=pid in selected).pack(fill="x", padx=self.px(12), pady=self.px(4))
        if not self.snapshot.get("people"):
            self._paragraph_label(frame, "No personal profiles yet. Add a person when they are available to speak.")
        self.button(frame, "Use full-transcript focus", lambda: self._choose_mode("selected_focus"), accent=True).pack(fill="x", padx=self.px(12), pady=self.px(8))

    def _recipes(self) -> list[dict[str, Any]]:
        recipes = self.snapshot.get("recipes", [])
        if isinstance(recipes, dict):
            return [dict(value, id=key) if isinstance(value, dict) else dict(id=key, name=str(value)) for key, value in recipes.items()]
        return [r if isinstance(r, dict) else dict(id=str(r), name=str(r)) for r in recipes]

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
            self.button(frame, str(person["name"]) + f" · {str(person['id'])[:6]}", lambda p=dict(person): self.show_person(p),
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
        self._paragraph_label(frame, self._paragraph)
        targets = tk.Frame(frame, bg=self.color("background")); targets.pack(fill="x", padx=self.px(12), pady=self.px(6))
        for target in (15, 30, 60):
            def choose(value: int = target) -> None:
                self._enroll_target = value; self._draw_enrollment()
            self.button(targets, f"{target}s" + (" ✓" if self._enroll_target == target else ""), choose,
                        accent=self._enroll_target == target, key=f"enroll_target_{target}", wrap=120).pack(side="left", fill="x", expand=True, padx=self.px(2))
        self._paragraph_label(frame, "Target = unique usable speech, not elapsed time. 30s is the default; these tiers are interface choices, not guaranteed optimal lengths.", True)
        def consent() -> None:
            self._enroll_consent = not self._enroll_consent; self._draw_enrollment()
        self.button(frame, ("✓ " if self._enroll_consent else "○ ") + "I consent to record and store my voice locally", consent,
                    key="enrollment_consent", height=60).pack(fill="x", padx=self.px(12), pady=self.px(4))
        start = self.button(frame, "Start recording", self._start_enrollment, accent=True, key="enrollment_start")
        start.pack(fill="x", padx=self.px(12), pady=self.px(8)); start.button.configure(state="normal" if self._enroll_consent else "disabled")  # type: ignore[attr-defined]

    def _set_paragraph(self, text: str) -> None:
        self._paragraph = text; self._draw_enrollment()

    def _start_enrollment(self) -> None:
        if not self._enroll_consent: return
        if self._call("enrollment_start", self._enroll_name, self._enroll_target, consent=True, person_id=self._enroll_person_id):
            self._enroll_started = True; self.show_enrollment_progress()

    def show_enrollment_progress(self) -> None:
        self.page = "enrollment_progress"; frame = self._page("Recording reference", back=self.show_people)
        self._paragraph_label(frame, self._enroll_name)
        self.enroll_progress_label = self._paragraph_label(frame, "Waiting for microphone / quality status…")
        self.enroll_progress = ttk.Progressbar(frame, orient="horizontal", mode="determinate", maximum=self._enroll_target)
        self.enroll_progress.pack(fill="x", padx=self.px(12), pady=self.px(8))
        self._paragraph_label(frame, self._paragraph)
        self.button(frame, "Read more / continue naturally", self._read_more, key="enrollment_more").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "Stop recording", lambda: self._call("enrollment_stop"), key="enrollment_stop").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "Save reference", self._save_enrollment, accent=True, key="enrollment_save").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "Discard this recording", self._cancel_enrollment, key="enrollment_cancel").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self._page_update = self._update_enrollment; self._update_enrollment()

    def _update_enrollment(self) -> None:
        enrollment = self.snapshot.get("enrollment") or {}
        usable = self._number(enrollment.get("usable_s", enrollment.get("unique_usable_s", 0)))
        elapsed = self._number(enrollment.get("elapsed_s", 0))
        target = self._number(enrollment.get("target_sec", enrollment.get("target_s", self._enroll_target)))
        state = str(enrollment.get("state", enrollment.get("status", "starting")))
        level = enrollment.get("level", "not available")
        quality = enrollment.get("quality", enrollment.get("message", ""))
        self.enroll_progress.configure(maximum=max(1, target), value=min(usable, target))
        self.enroll_progress_label.configure(text=f"{state}\nUnique usable: {usable:.1f} / {target:g}s · elapsed: {elapsed:.1f}s\nLevel: {level} · {'CLIPPING' if enrollment.get('clipping') else 'no clipping reported'}\n{quality}" + ("\n" + str(enrollment["error"]) if enrollment.get("error") else ""))
        self.actions["enrollment_save"].configure(state="normal" if enrollment.get("can_save") else "disabled")
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
        if (self.snapshot.get("enrollment") or {}).get("can_save"):
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
            self.show_settings()
        elif key in ("theme", "preview_zoom"):
            self.zoom = float(self.preferences.get("preview_zoom", 1))
            self.shell.destroy(); self._row_cache.clear(); self._marks.clear(); self._render_order.clear()
            self._build(); self._set_geometry(); self._render_rows(self.snapshot.get("rows", []), force=True); self.show_settings()
        else: self.show_settings()

    def show_settings(self) -> None:
        self.page = "settings"; frame = self._page("Settings")
        self._paragraph_label(frame, "Display changes apply without reloading models.", True)
        self._paragraph_label(frame, "Caption size")
        for name in self.config["caption_sizes_px"]:
            self.button(frame, name + (" ✓" if name == self.preferences["caption_size"] else ""), lambda v=name: self._preference("caption_size", v)).pack(fill="x", padx=self.px(12), pady=self.px(3))
        self._paragraph_label(frame, "Contrast")
        for theme in self.config["themes"]:
            self.button(frame, theme + (" ✓" if theme == self.preferences["theme"] else ""), lambda v=theme: self._preference("theme", v)).pack(fill="x", padx=self.px(12), pady=self.px(3))
        self._paragraph_label(frame, "Preview size · comfort zoom is not exact-pixel evidence")
        for zoom in self.config["preview_zooms"]:
            self.button(frame, "480 × 800 pixel-check" if zoom == 1 else f"{round(zoom * 100)}% comfort zoom", lambda v=zoom: self._preference("preview_zoom", v)).pack(fill="x", padx=self.px(12), pady=self.px(3))
        self._paragraph_label(frame, "Direction display is off. Current named-person arrows are unavailable without verified fresh person-to-beam evidence.", True)
        self.button(frame, "Engine recipe & audio tap", self.show_recipes).pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "Open a saved file…", lambda: self.browse_file("replay"), key="file_replay").pack(fill="x", padx=self.px(12), pady=self.px(4))
        self.button(frame, "Diagnostics / raw text", self.show_diagnostics, key="diagnostics").pack(fill="x", padx=self.px(12), pady=self.px(4))
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

    def show_diagnostics(self) -> None:
        self.page = "diagnostics"; frame = self._page("Diagnostics", back=self.show_settings)
        self._paragraph_label(frame, "Raw text is diagnostic evidence; provisional casing never replaces it.", True)
        self.button(frame, "Mark a problem / save excerpt…", lambda: self.show_problem(back=self.show_diagnostics),
                    key="mark_problem").pack(fill="x", padx=self.px(12), pady=self.px(4))
        display = tk.Text(frame, wrap="word", font=self.font(14), height=23, bg=self.color("surface"), fg=self.color("text"), relief="flat")
        display.pack(fill="both", expand=True, padx=self.px(8), pady=self.px(8))
        def update() -> None:
            doc = dict(state=self.snapshot.get("state"), status=self.snapshot.get("status"),
                       mode=self.snapshot.get("mode"), recipe=self.snapshot.get("recipe"), tap=self.snapshot.get("tap"),
                       client=self.measure_client(), metrics=self.snapshot.get("metrics", {}), error=self.snapshot.get("error"),
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
        for title, description in MODES.values():
            self._paragraph_label(frame, title); self._paragraph_label(frame, description, True)
        self._paragraph_label(frame, "Recipes choose existing engine settings; O0/O1 choose compatible audio taps. The menu shows backend availability and evidence status. Personalization is a new application condition, not a research accuracy guarantee.")
        self._paragraph_label(frame, "Human checks still needed: consent and speak through the identified XVF; record and save your own voice reference; restart, then test different speech; try Unknown/wrong-person behavior. A stub or saved file does not verify live enrollment.")
        self._paragraph_label(frame, "Stop actually stops capture through the controller. If strict focus hides words, Show all captions returns to caption-only mode. The documented evaluation firmware has an eight-hour limit; stop between sessions and follow the device recovery guide rather than resetting during speech.")
        self._paragraph_label(frame, "CM5, physical touchscreen accuracy and unknown camera/IMU/GPIO assignments remain hardware-pending. Desktop client pixels do not emulate Pi performance.", True)

    def close(self) -> None:
        if self._closed or self._closing: return
        if self._call("close"):
            self._closing = True
            self._notice = "Closing · waiting for capture and workers to release safely…"
            self._show_status()
            for key in ("start_stop", "mode", "people", "settings", "rescue"):
                self.actions[key].configure(state="disabled")
