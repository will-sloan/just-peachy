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
from unittest.mock import patch

from prototype.app.ui import MODES, PrototypeUI, prepare_dpi_awareness


class StubController:
    def __init__(self):
        self.calls = []
        self.data = dict(state="IDLE", status="STUB UI CHECK · microphone unavailable", rows=[],
            people=[dict(id="uuid-alex-1", name="Alex"), dict(id="uuid-alex-2", name="Alex")],
            mode="caption_only", recipe="fast", tap="O0", strict=False, selected_ids=[], display_ids=[],settings={},
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
    def display_roster(self, ids):self._record('display_roster',ids);self.data['display_ids']=ids
    def seats_apply(self,rows,mode,strength,acknowledged):self._record('seats_apply',rows,mode,strength,acknowledged);self.data['mode']=mode
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
    def reset_spatial(self): self._record("reset_spatial")
    def motion_configure(self, enabled): self._record('motion_configure', enabled)
    def motion_mount_configure(self, enabled): self._record('motion_mount_configure', enabled)
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

    def reopen_with_access(self, settings, *, allow_auto_start=True):
        self.ui.close(); self.ui.poll()
        self.root = tk.Tk(); self.controller = StubController()
        self.controller.data['settings'].update(settings)
        self.ui = PrototypeUI(self.root, self.controller, allow_auto_start=allow_auto_start)
        self.root.update_idletasks()

    def test_saved_microphone_permission_skips_repeated_dialog(self):
        self.reopen_with_access({'microphone_preapproved': True})
        self.ui.toggle_listening()
        self.assertEqual(self.ui.page, 'captions')
        self.assertEqual(self.controller.calls[-1], ('start_live', (), {'consent': True}))
        self.assertNotIn('requires your consent', self.ui.caption_text.get('1.0', 'end'))

    def test_motion_page_exposes_live_state_reset_and_experimental_switch(self):
        self.controller.data['motion'] = dict(enabled=True, state='STATIONARY', yaw_deg=12.,
            compensation=True, valid=True, reason='Relative front-side frame')
        self.ui.snapshot = self.controller.snapshot()
        self.ui.show_settings(); self.ui.actions['motion'].invoke()
        self.assertEqual(self.ui.page, 'motion')
        self.ui._page_update()
        self.ui.actions['motion_reset'].invoke()
        self.assertEqual(self.controller.calls[-1][0], 'reset_spatial')
        self.ui.actions['motion_compensation'].invoke()
        self.assertEqual(self.controller.calls[-1], ('motion_configure', (False,), {}))
        self.ui.show_motion();self.ui.actions['motion_mount'].invoke()
        self.assertEqual(self.controller.calls[-1], ('motion_mount_configure', (True,), {}))

    def test_automatic_listening_is_once_and_requires_saved_permission(self):
        self.reopen_with_access({'microphone_preapproved': True, 'auto_start_listening': True})
        self.ui._auto_start_listening(); self.ui._auto_start_listening()
        self.assertEqual([c[0] for c in self.controller.calls], ['start_live'])
        self.ui.snapshot = self.controller.snapshot()
        self.ui.toggle_listening(); self.ui._auto_start_listening()
        self.assertEqual([c[0] for c in self.controller.calls], ['start_live', 'stop'])
        self.reopen_with_access({'auto_start_listening': True})
        self.ui._auto_start_listening()
        self.assertEqual(self.controller.calls, [])

    def test_file_gui_and_manual_start_suppress_pending_automatic_start(self):
        access = {'microphone_preapproved': True, 'auto_start_listening': True}
        self.reopen_with_access(access, allow_auto_start=False)
        self.ui._auto_start_listening(); self.assertEqual(self.controller.calls, [])
        self.reopen_with_access(access)
        self.ui.toggle_listening(); self.ui._auto_start_listening()
        self.assertEqual([c[0] for c in self.controller.calls], ['start_live'])

    def test_permission_can_be_revoked_and_disables_automatic_listening(self):
        self.reopen_with_access({'microphone_preapproved': True, 'auto_start_listening': True})
        self.ui._microphone_preference(False)
        self.assertEqual(self.controller.data['settings'],
                         {'microphone_preapproved': False, 'auto_start_listening': False})
        self.ui._auto_start_listening()
        self.assertFalse(any(c[0] == 'start_live' for c in self.controller.calls))
        self.ui.home(); self.ui.toggle_listening()
        self.assertEqual(self.ui.page, 'consent')

    def test_physical_client_touch_targets_idle_and_consent(self):
        metrics = self.ui.measure_client()
        self.assertEqual((metrics["physical_width"], metrics["physical_height"]), (480, 800))
        self.assertFalse(self.ui.rescue.winfo_manager())
        for name in ("start_stop", "mode", "people", "settings", "back_live"):
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
        clock = patch("prototype.app.ui.time.perf_counter", return_value=10.0).start()
        self.addCleanup(patch.stopall)
        self.controller.data.update(mode="open_with_names", rows=sample_rows(3)); self.refresh()
        original_marks = dict(self.ui._marks)
        self.controller.data["rows"][0].update(raw_asr_text="I AGREE", label="Alex", final=True,
            final_punctuated_display_text="I agree.")
        self.controller.data["rows"][1]["raw_asr_text"] = "A RETRACTION"
        self.refresh()
        clock.return_value = 11.3; self.refresh()
        output = self.ui.caption_text.get("1.0", "end-1c")
        self.assertEqual(self.ui._marks, original_marks)
        self.assertEqual(output, "Alex\nI agree.\n\nAlex\nA retraction\n\nUnknown\nRow 2 please sit with me by the window\n\n")
        self.assertEqual(self.controller.data["rows"][0]["raw_asr_text"], "I AGREE")
        self.controller.data["rows"].append(dict(id="emoji", raw_asr_text="HELLO 🙂", label="Alex"))
        self.refresh(); self.controller.data["rows"][-1]["raw_asr_text"] = "HELLO 🙂 AGAIN"; self.refresh()
        clock.return_value = 11.6; self.refresh()
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
        self.assertTrue(self.ui._follow_live)
        # Tk's fraction uses estimated heights for mixed-font offscreen lines.
        # Assert the actual last caption/end is in the viewport instead.
        self.assertIsNotNone(self.ui.caption_text.bbox("end-1c"))

    def test_all_modes_strict_warning_and_rescue(self):
        from prototype.app.mode_policy import MODE_METADATA,SELECTED_MODES,SEAT_MODES
        self.controller.data["rows"] = sample_rows(2); self.refresh()
        for mode in MODES:
            self.ui.show_advanced() if MODE_METADATA[mode]['advanced'] else self.ui.show_modes()
            self.ui.actions[f"mode_{mode}"].invoke()
            if mode in SEAT_MODES:
                self.ui._seat_draft=[dict(person_id='uuid-alex-1',angle_deg=30.,tolerance_deg=25.)]
                self.ui._paint_seats();self.ui.actions['seat_apply'].invoke()
            elif mode in SELECTED_MODES:
                if not self.ui._roster_draft:self.ui.actions['roster_uuid-alex-1'].invoke()
                self.ui.actions['roster_apply'].invoke()
            self.refresh()
        self.assertEqual(len([call for call in self.controller.calls if call[0] in ("switch","seats_apply")]), len(MODES))
        self.controller.data["display_ids"] = ["uuid-alex-1"]; self.refresh()
        self.ui.request_strict(); self.assertFalse(self.controller.data["strict"])
        self.ui.actions["cancel"].invoke(); self.assertFalse(self.controller.data["strict"])
        self.ui.request_strict(); self.ui.actions["confirm"].invoke(); self.refresh()
        self.assertTrue(self.ui.rescue.winfo_manager())
        self.assertGreaterEqual(self.ui.actions["rescue"].winfo_height(), 48)
        self.assertEqual(self.ui._render_order, ["row-1"])
        identity_mode=self.controller.data['mode'];self.ui.actions["rescue"].invoke(); self.refresh()
        self.assertEqual(self.ui._render_order, ["row-0", "row-1"])
        self.assertEqual(len(self.controller.data["rows"]), 2)
        self.assertEqual(self.controller.data["mode"], identity_mode)

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

    def test_beam_diagnostics_remain_accessible_live_and_hide_stale_arrows(self):
        self.controller.data.update(state="RUNNING", beam_diagnostics={"state": "RUNNING", "stale_after_seconds": 2.5,
            "arrows": [{"id": "focused_1", "angle_deg": 0, "age_sec": .1},
                       {"id": "focused_2", "angle_deg": 180, "age_sec": .2},
                       {"id": "free_running", "angle_deg": 90, "age_sec": 3},
                       {"id": "processed_output", "angle_deg": 90, "age_sec": .3}]})
        self.refresh(); self.ui.show_settings(); self.root.update_idletasks()
        self.assertEqual(self.ui.actions["beam_diagnostics"].cget("state"), "normal")
        self.ui.actions["beam_diagnostics"].invoke(); self.root.update_idletasks()
        self.assertEqual(self.controller.calls, [])
        self.assertEqual(len(self.ui.beam_canvas.find_withtag("beam_arrow")), 3)
        right = self.ui.beam_canvas.coords(self.ui.beam_canvas.find_withtag("focused_1")[0])
        left = self.ui.beam_canvas.coords(self.ui.beam_canvas.find_withtag("focused_2")[0])
        self.assertGreater(right[2], right[0]); self.assertLess(left[2], left[0])
        self.assertIn("180.0°", self.ui.beam_legend["focused_2"].cget("text"))
        self.controller.data["beam_diagnostics"] = {"state": "OFF", "arrows": []}
        self.ui.snapshot = self.controller.snapshot(); self.ui._update_beam_diagnostics()
        self.assertEqual(len(self.ui.beam_canvas.find_withtag("beam_arrow")), 0)
        self.assertEqual(self.controller.calls, [])

    def test_spatial_modes_are_selectable_with_explicit_evidence_symbols(self):
        self.controller.data["mode_metadata"] = {
            "caption_only": {"symbol": "✓", "status": "simulation-supported", "label": "Captions", "description": "Configuration evidence"},
            "spatial_assisted": {"symbol": "◇", "status": "experimental", "available": False, "parent": "C079", "description": "Experimental spatial support"}}
        self.refresh(); self.ui.show_modes()
        self.assertTrue(self.ui.actions["mode_caption_only"].cget("text").startswith("✓"))
        for mode in ("spatial_assisted", "strongly_spatial_assisted"):
            self.ui.show_modes()
            button = self.ui.actions["mode_" + mode]
            self.assertEqual(button.cget("state"), "normal")
            self.assertTrue(button.cget("text").startswith("◇"))
            button.invoke()
            self.assertEqual(self.controller.calls[-1], ("switch", (), {"mode": mode, "strict": False}))
        self.ui.show_help()
        text = " ".join(str(w.cget("text")) for w in widgets(self.root) if isinstance(w, tk.Label))
        self.assertIn("C079", text)
        self.assertIn("not current speakers", text)

    def test_compact_spatial_display_fresh_stale_names_and_reset(self):
        self.controller.data.update(state="RUNNING", spatial_view={"state": "RUNNING", "stale_after_seconds": .75,
            "speech": True, "energy": .013, "arrows": [
                {"id": "focused_1", "angle_deg": 35, "age_sec": .1, "fresh": True},
                {"id": "processed_output", "angle_deg": 35, "age_sec": .2, "fresh": True, "selected": True, "speech": True},
                {"id": "focused_2", "angle_deg": 140, "age_sec": 3, "fresh": True}],
            "associations": [
                {"label": "Alex", "angle_deg": 35, "age_sec": .2, "fresh": True, "speaking": True},
                {"label": "Speaker 2", "angle_deg": 140, "age_sec": 4, "fresh": True, "speaking": True}]})
        self.refresh(); self.ui.show_settings()
        self.assertFalse(self.ui.spatial_canvas.winfo_manager())
        self.ui.actions["spatial_visualization"].invoke(); self.ui.home(); self.root.update_idletasks()
        self.ui._update_spatial_visualization(force=True)
        self.assertEqual(self.controller.calls[-1], ("settings_update", ({"spatial_visualization": True},), {}))
        self.assertEqual(self.ui.spatial_canvas.winfo_height(), 145)
        self.assertGreaterEqual(self.ui.caption_text.winfo_height() + self.ui.active_region.winfo_height(), 350)
        canvas = self.ui.spatial_canvas
        self.assertEqual(len(canvas.find_withtag("spatial_beam")), 3)
        self.assertTrue(canvas.itemcget(canvas.find_withtag("focused_2")[0], "dash"))
        names = [canvas.itemcget(item, "text") for item in canvas.find_withtag("spatial_name")]
        self.assertIn("≈ Alex · 35° · speaking", names)
        self.assertIn("≈ Speaker 2 · 140° · last known 4s", names)
        self.assertIn("Fresh speaking", canvas.itemcget(canvas.find_withtag("spatial_badge")[0], "text"))
        self.controller.data["spatial_view"]["state"] = "STOPPED"
        self.ui.snapshot = self.controller.snapshot(); self.ui._update_spatial_visualization(force=True)
        self.assertFalse(canvas.find_withtag("fresh"))
        self.assertEqual(canvas.itemcget(canvas.find_withtag("spatial_badge")[0], "text"), "No fresh direction")
        self.ui.show_settings(); self.ui.actions["reset_spatial"].invoke()
        self.assertEqual(self.controller.calls[-1], ("reset_spatial", (), {}))
        self.assertEqual(len(self.controller.data["people"]), 2)
        self.ui.actions["spatial_visualization"].invoke(); self.ui.home(); self.root.update_idletasks()
        self.assertFalse(self.ui.spatial_canvas.winfo_manager())

    def test_spatial_display_does_not_infer_names_from_beam_labels(self):
        self.controller.data["spatial_view"] = {"state": "RUNNING", "arrows": [
            {"id": "processed_output", "label": "Misleading person name", "angle_deg": 90, "age_sec": .1,
             "selected": True, "fresh": True}], "associations": [
            {"label": "Expired", "angle_deg": 40, "age_sec": 20, "speaking": True, "fresh": True}]}
        self.refresh(); self.ui._preference("spatial_visualization", True); self.ui.home()
        self.ui._update_spatial_visualization(force=True)
        names = [self.ui.spatial_canvas.itemcget(item, "text") for item in self.ui.spatial_canvas.find_withtag("spatial_name")]
        self.assertEqual(names, ["No speaker association"])
        badge = self.ui.spatial_canvas.itemcget(self.ui.spatial_canvas.find_withtag("spatial_badge")[0], "text")
        self.assertIn("speech unconfirmed", badge)

    def test_spatial_toggle_preference_is_loaded_at_start(self):
        self.ui.close(); self.ui.poll()
        self.controller = StubController(); self.controller.data["settings"]["spatial_visualization"] = True
        self.root = tk.Tk(); self.ui = PrototypeUI(self.root, self.controller); self.root.update()
        self.assertTrue(self.ui.preferences["spatial_visualization"])
        self.assertEqual(self.ui.spatial_canvas.winfo_height(), 145)
        self.assertEqual(self.controller.calls, [])

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
    ui._preference("theme", "Dark"); ui._preference("caption_size", "Normal")
    controller.data.update(mode="spatial_assisted", spatial_view={"state": "RUNNING", "speech": True, "energy": .012,
        "stale_after_seconds": .75, "arrows": [
            {"id": "focused_1", "angle_deg": 38, "age_sec": .1, "fresh": True},
            {"id": "processed_output", "angle_deg": 38, "age_sec": .1, "fresh": True, "selected": True, "speech": True},
            {"id": "focused_2", "angle_deg": 145, "age_sec": .2, "fresh": True}],
        "associations": [{"label": "Alex", "angle_deg": 38, "age_sec": .1, "fresh": True, "speaking": True},
                         {"label": "Speaker 2", "angle_deg": 145, "age_sec": 4, "fresh": False, "speaking": False}]})
    ui.snapshot = controller.snapshot(); ui._preference("spatial_visualization", True); ui.home()
    ui._show_status(); ui._update_spatial_visualization(force=True); capture("07_spatial_fresh_and_last_known_stub")
    controller.data["spatial_view"]["state"] = "STOPPED"; ui.snapshot = controller.snapshot()
    ui._update_spatial_visualization(force=True); capture("08_spatial_stale_stub")
    (directory/"UI_STUB_EVIDENCE.json").write_text(json.dumps(dict(kind="STUB FRONTEND ONLY; no live/model/enrollment verification",
        client=ui.measure_client(), screenshots=captured, human_checks="pending"), indent=2), encoding="utf-8")
    ui.close(); ui.poll()


if __name__ == "__main__":
    if "--screenshots" in sys.argv:
        screenshots(Path(sys.argv[sys.argv.index("--screenshots") + 1]))
    else: unittest.main()
