"""Real Tk frontend with explicit fake backend; no audio/model/device access.

Run from repository root; see prototype/docs/UI_ITERATION.md. Screenshots made
by --screenshots are clearly identified synthetic UI evidence, never live tests.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tkinter as tk
import unittest

from prototype.app.ui import MODES, PrototypeUI, prepare_dpi_awareness


class StubController:
    def __init__(self):
        self.calls = []
        self.data = dict(state="IDLE", status="STUB UI CHECK · microphone unavailable", rows=[],
            people=[dict(id="uuid-alex-1", name="Alex"), dict(id="uuid-alex-2", name="Alex")],
            mode="caption_only", recipe="fast", tap="O0", strict=False, selected_ids=[], settings={},
            metrics={"evidence_kind": "explicit UI stub; no model or audio"}, enrollment={}, error=None,
            recipes=[dict(id="fast", name="Fast · B36", available=True, taps=["O0", "O1"],
                          evidence_status="STUB metadata only", compatible_modes=list(MODES)),
                     dict(id="spatial", name="Spatial", available=False, reason="No verified beam evidence", taps=[])])

    def snapshot(self): return deepcopy(self.data)
    def _record(self, method, *args, **kwargs): self.calls.append((method, args, kwargs))
    def start_live(self, **kwargs): self._record("start_live", **kwargs); self.data["state"] = "RUNNING"
    def start_file(self, path): self._record("start_file", path); self.data["state"] = "RUNNING"
    def stop(self): self._record("stop"); self.data["state"] = "STOPPED"
    def switch(self, **kwargs): self._record("switch", **kwargs); self.data.update(kwargs)
    def settings_update(self, values): self._record("settings_update", values); self.data["settings"].update(values)
    def enrollment_start(self, name, target, **kwargs):
        self._record("enrollment_start", name, target, **kwargs)
        self.data["state"] = "ENROLLING"
        self.data["enrollment"] = dict(state="RECORDING", usable_s=0, elapsed_s=0, target_sec=target, can_save=False)
    def enrollment_stop(self): self._record("enrollment_stop")
    def enrollment_save(self): self._record("enrollment_save")
    def enrollment_cancel(self): self._record("enrollment_cancel")
    def rename_person(self, *args): self._record("rename_person", *args)
    def delete_person(self, *args): self._record("delete_person", *args)
    def export_people(self, *args, **kwargs): self._record("export_people", *args, **kwargs)
    def import_people(self, *args, **kwargs): self._record("import_people", *args, **kwargs)
    def mark_problem(self, **kwargs): self._record("mark_problem", **kwargs)
    def close(self): self._record("close"); self.data["state"] = "CLOSED"


def sample_rows(count=30):
    return [dict(id=f"row-{i}", raw_asr_text=f"ROW {i} PLEASE SIT WITH ME BY THE WINDOW", label="Alex" if i % 2 else "Unknown",
                 final=False, selected=bool(i % 2)) for i in range(count)]


def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)


class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): prepare_dpi_awareness()

    def setUp(self):
        self.root = tk.Tk(); self.controller = StubController(); self.ui = PrototypeUI(self.root, self.controller)
        self.root.geometry("+30+30"); self.root.update()

    def tearDown(self):
        if not self.ui._closed:
            self.ui.close(); self.ui.poll()

    def refresh(self):
        self.ui.snapshot = self.controller.snapshot(); self.ui._show_status()
        self.ui._render_rows(self.ui.snapshot["rows"]); self.root.update_idletasks()

    def test_physical_client_touch_targets_idle_and_consent(self):
        metrics = self.ui.measure_client()
        self.assertEqual((metrics["physical_width"], metrics["physical_height"]), (480, 800))
        for name in ("start_stop", "mode", "people", "settings", "rescue", "back_live"):
            self.assertGreaterEqual(self.ui.actions[name].winfo_height(), 48)
            self.assertGreaterEqual(self.ui.actions[name].winfo_width(), 48)
        self.assertEqual(self.controller.calls, [])
        self.ui.toggle_listening(); self.assertEqual(self.ui.page, "consent")
        self.assertEqual(self.controller.calls, [])
        self.ui.actions["cancel"].invoke(); self.assertEqual(self.controller.calls, [])
        self.ui.toggle_listening(); self.ui.actions["confirm"].invoke()
        self.assertEqual(self.controller.calls[-1], ("start_live", (), {"consent": True}))
        self.refresh(); self.ui.toggle_listening(); self.assertEqual(self.controller.calls[-1][0], "stop")

    def test_stable_rows_late_labels_final_text_and_raw(self):
        self.controller.data.update(mode="open_with_names", rows=sample_rows(3)); self.refresh()
        original_marks = dict(self.ui._marks)
        self.controller.data["rows"][0].update(raw_asr_text="I AGREE", label="Alex", final=True,
            final_punctuated_display_text="I agree.")
        self.controller.data["rows"][1]["raw_asr_text"] = "A RETRACTION"
        self.refresh()
        output = self.ui.caption_text.get("1.0", "end-1c")
        self.assertEqual(self.ui._marks, original_marks)
        self.assertEqual(output, "Alex\nI agree.\n\nAlex\nA retraction\n\nUnknown\nRow 2 please sit with me by the window\n\n")
        self.assertEqual(self.controller.data["rows"][0]["raw_asr_text"], "I AGREE")
        self.controller.data["rows"].append(dict(id="emoji", raw_asr_text="HELLO 🙂", label="Alex"))
        self.refresh(); self.controller.data["rows"][-1]["raw_asr_text"] = "HELLO 🙂 AGAIN"; self.refresh()
        self.assertTrue(self.ui.caption_text.get("1.0", "end-1c").endswith("Alex\nHello 🙂 again\n\n"))

    def test_scroll_anchor_survives_revisions_and_append(self):
        self.controller.data["rows"] = sample_rows(40); self.refresh()
        self.ui._follow_live = False
        self.ui.caption_text.yview(self.ui._marks["row-12"][0]); self.root.update_idletasks()
        before = self.ui.caption_text.get("@0,0", "@0,0 lineend")
        self.controller.data["rows"][0]["raw_asr_text"] = "LONG REVISION " * 30
        self.controller.data["rows"].append(dict(id="new", raw_asr_text="NEWEST", label="Unknown"))
        self.refresh()
        self.assertEqual(self.ui.caption_text.get("@0,0", "@0,0 lineend"), before)
        self.assertFalse(self.ui._follow_live)
        self.ui.back_to_live(); self.root.update_idletasks()
        self.assertTrue(self.ui._follow_live); self.assertGreater(self.ui.caption_text.yview()[1], .99)

    def test_five_modes_strict_warning_and_rescue(self):
        self.controller.data["rows"] = sample_rows(2); self.refresh()
        for _ in range(4):
            for mode in MODES:
                self.ui.show_modes(); self.ui.actions[f"mode_{mode}"].invoke(); self.refresh()
        self.assertEqual(len([call for call in self.controller.calls if call[0] == "switch"]), 20)
        self.controller.data["selected_ids"] = ["uuid-alex-1"]; self.refresh()
        self.ui.request_strict(); self.assertFalse(self.controller.data["strict"])
        self.ui.actions["cancel"].invoke(); self.assertFalse(self.controller.data["strict"])
        self.ui.request_strict(); self.ui.actions["confirm"].invoke(); self.refresh()
        self.assertEqual(self.ui._render_order, ["row-1"])
        self.ui.actions["rescue"].invoke(); self.refresh()
        self.assertEqual(self.ui._render_order, ["row-0", "row-1"])
        self.assertEqual(len(self.controller.data["rows"]), 2)
        self.assertEqual(self.controller.data["mode"], "caption_only")

    def test_touch_keyboard_enrollment_goals_and_quality_gate(self):
        self.ui.add_person(); self.root.update_idletasks()
        def key(label):
            next(w for w in widgets(self.root) if isinstance(w, tk.Button) and w.cget("text") == label).invoke()
        key("A"); key("l"); key("e"); key("x")
        self.ui.actions["keyboard_done"].invoke()
        self.assertEqual(self.ui._enroll_name, "Alex")
        self.assertEqual(self.ui.actions["enrollment_start"].cget("state"), "disabled")
        self.ui.actions["enroll_target_60"].invoke(); self.ui.actions["enrollment_consent"].invoke()
        self.ui.actions["enrollment_start"].invoke(); self.refresh(); self.ui._update_enrollment()
        self.assertEqual(self.controller.calls[-1], ("enrollment_start", ("Alex", 60), {"consent": True, "person_id": None}))
        self.assertEqual(self.ui.actions["enrollment_save"].cget("state"), "disabled")
        self.controller.data["enrollment"].update(state="RECORDING", usable_s=10, elapsed_s=25, level=.25)
        self.refresh(); self.ui._update_enrollment()
        self.assertIn("10.0 / 60s", self.ui.enroll_progress_label.cget("text"))
        calls_before = len(self.controller.calls); self.ui._read_more(); self.ui._save_enrollment()
        self.assertEqual(len(self.controller.calls), calls_before)
        self.controller.data["enrollment"].update(state="READY", can_save=True)
        self.refresh(); self.ui._update_enrollment(); self.ui.actions["enrollment_save"].invoke()
        self.assertEqual(self.controller.calls[-1][0], "enrollment_save")

    def test_people_uuid_privacy_and_unavailable_recipe(self):
        self.ui._rename("uuid-alex-2", "Alex II")
        self.assertEqual(self.controller.calls[-1], ("rename_person", ("uuid-alex-2", "Alex II"), {}))
        self.ui.show_person(self.controller.data["people"][1]); self.ui.actions["delete_person"].invoke()
        self.assertNotEqual(self.controller.calls[-1][0], "delete_person")
        self.ui.actions["confirm"].invoke(); self.assertEqual(self.controller.calls[-1][1], ("uuid-alex-2",))
        for purpose in ("import", "export"):
            count = len(self.controller.calls)
            self.ui._path_chosen(purpose, Path("stub-only-profile.zip"))
            self.assertEqual(len(self.controller.calls), count)
            self.ui.actions["confirm"].invoke()
            self.assertEqual(self.controller.calls[-1][0], purpose + "_people")
            self.assertEqual(self.controller.calls[-1][2], {"consent": True})
        self.ui.show_recipes()
        self.assertEqual(self.ui.actions["recipe_spatial"].cget("state"), "disabled")

    def test_caption_size_theme_zoom_and_close_waits(self):
        self.ui._preference("caption_size", "Extra large"); self.ui._preference("theme", "High contrast")
        self.assertIn("-37", str(self.ui.caption_text.cget("font")))
        self.assertEqual(self.ui.measure_client()["physical_width"], 480)
        self.ui._preference("preview_zoom", 1.25)
        self.assertEqual(self.ui.measure_client()["physical_width"], 600)
        self.assertEqual(self.ui.measure_client()["physical_height"], 1000)
        def delayed_close(): self.controller._record("close")
        self.controller.close = delayed_close
        self.ui.close(); self.assertTrue(self.root.winfo_exists()); self.assertTrue(self.ui._closing)
        self.controller.data["state"] = "CLOSED"; self.ui.poll(); self.assertTrue(self.ui._closed)

    def test_problem_excerpt_explicit_audio_consent_and_text_retention(self):
        self.ui.show_problem(); self.assertEqual(self.controller.calls, [])
        self.ui.actions["problem_cancel"].invoke(); self.assertEqual(self.controller.calls, [])
        self.ui.show_problem(); self.ui.actions["problem_without_audio"].invoke()
        self.assertEqual(self.controller.calls[-1], ("mark_problem", (), {"save_audio": False}))
        self.ui.show_problem(); self.ui.actions["problem_with_audio"].invoke()
        self.assertEqual(self.controller.calls[-1], ("mark_problem", (), {"save_audio": True}))
        self.controller.data["settings"]["save_session_text"] = True; self.refresh(); self.ui.show_settings()
        self.ui.actions["session_text"].invoke()
        self.assertEqual(self.controller.calls[-1], ("settings_update", ({"save_session_text": False},), {}))
        self.controller.data["settings"].update(completed_session_limit=10, session_quota_mib=256, ram_horizon_sec=120)
        self.refresh(); self.ui.show_settings()
        for setting, value in (("completed_session_limit", 20), ("session_quota_mib", 64), ("ram_horizon_sec", 60)):
            self.ui.actions[f"retention_{setting}_{value}"].invoke()
            self.assertEqual(self.controller.calls[-1], ("settings_update", ({setting: value},), {}))


def screenshots(directory):
    """Optional evidence generation; all captions/people/metrics are a fake stub."""
    from PIL import ImageGrab
    prepare_dpi_awareness(); root = tk.Tk(); controller = StubController(); ui = PrototypeUI(root, controller)
    root.geometry("+25+25"); root.lift(); root.attributes("-topmost", True); root.update()
    directory.mkdir(parents=True, exist_ok=True)
    captured = []
    def capture(name):
        root.update(); root.after(100); root.update()
        x, y = root.winfo_rootx(), root.winfo_rooty()
        image = ImageGrab.grab(bbox=(x, y, x+root.winfo_width(), y+root.winfo_height()))
        path = directory/(name+".png"); image.save(path); captured.append(str(path))
    capture("01_idle_stub")
    controller.data.update(mode="open_with_names", rows=[dict(id="one", raw_asr_text="PLEASE SIT WITH ME BY THE WINDOW", label="Alex"),
        dict(id="two", raw_asr_text="WOULD YOU LIKE SOME TEA", label="Unknown", final=True, final_punctuated_display_text="Would you like some tea?"),
        dict(id="three", raw_asr_text="I USUALLY CHOOSE TEA", label="Alex")])
    ui.snapshot = controller.snapshot(); ui._show_status(); ui._render_rows(ui.snapshot["rows"]); capture("02_captions_stub")
    ui.show_modes(); capture("03_modes_stub")
    ui.add_person(); capture("04_keyboard_stub")
    ui.enrollment_form("Alex"); ui.show_enrollment_progress()
    controller.data["enrollment"] = dict(state="RECORDING (STUB)", usable_s=10, elapsed_s=24, target_sec=30, level="-24 dBFS", can_save=False)
    ui.snapshot = controller.snapshot(); ui._update_enrollment(); capture("05_enrollment_stub")
    ui._preference("theme", "High contrast"); ui._preference("caption_size", "Extra large"); ui.home(); capture("06_large_contrast_stub")
    (directory/"UI_STUB_EVIDENCE.json").write_text(json.dumps(dict(kind="STUB FRONTEND ONLY; no live/model/enrollment verification",
        client=ui.measure_client(), screenshots=captured, human_checks="pending"), indent=2), encoding="utf-8")
    ui.close(); ui.poll()


if __name__ == "__main__":
    if "--screenshots" in sys.argv:
        screenshots(Path(sys.argv[sys.argv.index("--screenshots") + 1]))
    else: unittest.main()
