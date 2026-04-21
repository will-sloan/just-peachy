"""Small reusable tkinter widgets for the Evaluation Tool GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


MULTISELECT_DROPDOWN_HEIGHT = 8


class VerticalScrolledFrame(ttk.Frame):
    """A simple vertically scrollable container for tkinter forms."""

    def __init__(self, master: tk.Misc, *, padding: int = 0) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.content = ttk.Frame(self.canvas, padding=padding)
        self._window_id = self.canvas.create_window((0, 0), window=self.content, anchor=tk.NW)
        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.content.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _on_content_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox(tk.ALL))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window_id, width=event.width)

    def _bind_mousewheel(self, _event: tk.Event) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: tk.Event) -> None:
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        if self._event_target_has_own_scroll(event):
            return None
        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            direction = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(direction, "units")
        return "break"

    def _event_target_has_own_scroll(self, event: tk.Event) -> bool:
        target = self.winfo_containing(event.x_root, event.y_root)
        while target is not None:
            if str(target) == str(self):
                return False
            try:
                if target.winfo_class() in {"Listbox", "Text", "TCombobox"}:
                    return True
            except tk.TclError:
                return False
            target = target.master
        return False


class MultiSelectDropdown(ttk.Frame):
    """Compact dropdown-style multi-select control.

    Tkinter does not provide a native multi-select combobox. This widget keeps a
    button-sized summary in the main window and opens a fixed-height scrollable
    listbox only while the user is choosing values.
    """

    def __init__(
        self,
        master: tk.Misc,
        values: list[str] | tuple[str, ...],
        *,
        selected: list[str] | tuple[str, ...] = (),
        width: int = 36,
    ) -> None:
        super().__init__(master)
        self.values = tuple(values)
        self.selected_values = tuple(value for value in selected if value in self.values)
        self.summary_var = tk.StringVar(value=self._summary_text())
        self._popup: tk.Toplevel | None = None
        self._listbox: tk.Listbox | None = None
        self.button = ttk.Button(
            self,
            textvariable=self.summary_var,
            command=self.toggle_popup,
            width=width,
        )
        self.button.pack(fill=tk.X, expand=True)

    def get_selected(self) -> tuple[str, ...]:
        """Return selected values without depending on a live popup widget."""

        self._sync_from_listbox()
        return self.selected_values

    def set_selected(self, values: list[str] | tuple[str, ...]) -> None:
        """Set selected values programmatically."""

        allowed = set(self.values)
        self.selected_values = tuple(value for value in values if value in allowed)
        self._sync_to_listbox()
        self._refresh_summary()

    def toggle_popup(self) -> None:
        """Open or close the dropdown popup."""

        if self._live_popup() is not None:
            self.close_popup()
        else:
            self.open_popup()

    def open_popup(self) -> None:
        """Open the fixed-height scrollable selection list."""

        if self._live_popup() is not None:
            return
        self._popup = None
        self._listbox = None

        popup = tk.Toplevel(self)
        popup.transient(self.winfo_toplevel())
        popup.resizable(False, False)
        popup.title("Select values")
        popup.bind("<Escape>", lambda _event: self.close_popup())
        popup.bind("<FocusOut>", self._schedule_close_if_unfocused)
        self._popup = popup

        frame = ttk.Frame(popup, padding=6)
        frame.pack(fill=tk.BOTH, expand=True)
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self._listbox = tk.Listbox(
            list_frame,
            selectmode=tk.MULTIPLE,
            height=MULTISELECT_DROPDOWN_HEIGHT,
            width=42,
            exportselection=False,
        )
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scrollbar.set)
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for value in self.values:
            self._listbox.insert(tk.END, value)
        self._sync_to_listbox()
        self._listbox.bind("<<ListboxSelect>>", lambda _event: self._on_select())
        self._listbox.bind("<Return>", lambda _event: self.close_popup())

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(buttons, text="Clear", command=self.clear_selection).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Done", command=self.close_popup).pack(side=tk.RIGHT)

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        popup.geometry(f"+{x}+{y}")
        popup.lift()
        self._listbox.focus_set()

    def close_popup(self) -> None:
        """Close the dropdown popup and keep the selected values."""

        self._sync_from_listbox()
        popup = self._live_popup()
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass
        self._popup = None
        self._listbox = None
        self._refresh_summary()

    def clear_selection(self) -> None:
        """Clear all selected values."""

        self.selected_values = ()
        listbox = self._live_listbox()
        if listbox is not None:
            try:
                listbox.selection_clear(0, tk.END)
            except tk.TclError:
                self._listbox = None
        self._refresh_summary()

    def _on_select(self) -> None:
        self._sync_from_listbox()
        self._refresh_summary()

    def _sync_from_listbox(self) -> None:
        listbox = self._live_listbox()
        if listbox is None:
            return
        try:
            self.selected_values = tuple(self.values[index] for index in listbox.curselection())
        except tk.TclError:
            self._listbox = None

    def _sync_to_listbox(self) -> None:
        listbox = self._live_listbox()
        if listbox is None:
            return
        selected = set(self.selected_values)
        try:
            listbox.selection_clear(0, tk.END)
            for index, value in enumerate(self.values):
                if value in selected:
                    listbox.selection_set(index)
        except tk.TclError:
            self._listbox = None

    def _refresh_summary(self) -> None:
        self.summary_var.set(self._summary_text())

    def _summary_text(self) -> str:
        if not self.selected_values:
            return "Any"
        if len(self.selected_values) <= 2:
            return ", ".join(self.selected_values)
        return f"{len(self.selected_values)} selected"

    def _schedule_close_if_unfocused(self, _event: tk.Event) -> None:
        self.after(120, self._close_if_unfocused)

    def _close_if_unfocused(self) -> None:
        popup = self._live_popup()
        if popup is None:
            return
        focus = popup.focus_get()
        if focus is None or not self._is_descendant(focus, popup):
            self.close_popup()

    def _live_popup(self) -> tk.Toplevel | None:
        if self._popup is None:
            return None
        try:
            if self._popup.winfo_exists():
                return self._popup
        except tk.TclError:
            pass
        self._popup = None
        return None

    def _live_listbox(self) -> tk.Listbox | None:
        if self._listbox is None:
            return None
        try:
            if self._listbox.winfo_exists():
                return self._listbox
        except tk.TclError:
            pass
        self._listbox = None
        return None

    @staticmethod
    def _is_descendant(widget: tk.Misc, parent: tk.Misc) -> bool:
        current: tk.Misc | None = widget
        while current is not None:
            if current == parent:
                return True
            current = current.master
        return False
