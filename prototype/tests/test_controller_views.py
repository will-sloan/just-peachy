"""Actual projection/retention methods with explicit model-free synthetic fixtures.

No Controller constructor, worker, model, endpoint inventory or capture is
started. See tests/README.md for inputs, outputs and run commands.
"""
from collections import OrderedDict, namedtuple
from copy import deepcopy
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "vendor")]
from app.controller import Controller
from app.buffers import MemoryJournal

PERSON_A = "11111111-1111-4111-8111-111111111111"
PERSON_B = "22222222-2222-4222-8222-222222222222"
Disk = namedtuple("Disk", "total used free")


class ExplicitStubStore:
    """View-only metadata; no vectors, gallery or persistence claim."""
    def __init__(self):
        self.people = [{"id": PERSON_A, "name": "Alex", "references": 1},
                       {"id": PERSON_B, "name": "Alex", "references": 1}]

    def summaries(self): return deepcopy(self.people)
    def list(self): return deepcopy(self.people)
    def rename(self, identifier, name):
        next(person for person in self.people if person["id"] == identifier)["name"] = name
    def delete(self, identifier):
        self.people = [person for person in self.people if person["id"] != identifier]


def s7_fixture():
    """Synthetic supported-token ownership row in the S7 projection schema."""
    key = "synthetic-view-session/utterance:000042"
    return {"caption_key": key, "utterance_id": 42, "text": "HELLO ALEX I AM READY THANK YOU",
        "text_revision_id": "text:2", "punctuation_for_text_revision": "text:2",
        "display_text": "Hello Alex, I am ready. Thank you.", "final": True,
        "identity_version": 4, "anonymous_label": "Speaker_9", "segments": [
            {"segment_id": key + "/segment:9", "token_ids": ["token:1", "token:2", "token:3"],
             "token_range": [0, 3], "raw_text": "HELLO ALEX I", "known_profile_id": PERSON_A,
             "naming_state": "confirmed", "anonymous_label": "Speaker_2"},
            {"segment_id": key + "/segment:14", "token_ids": ["token:4", "token:5", "token:6", "token:7"],
             "token_range": [3, 7], "raw_text": "AM READY THANK YOU", "known_profile_id": None,
             "naming_state": "unknown", "anonymous_label": "Speaker_9"}]}


class ControllerViewTests(unittest.TestCase):
    def test_closed_display_assumption_stays_separate_from_raw_identity_and_other_modes(self):
        c=self.controller;c.mode='selected_closed';part=c.rows['utterance:42']['segments'][1]
        part.update(prototype_closed_group=True,voice_available=False,
            closed_display_assignment=dict(profile_id=PERSON_A,name='outdated spelling',assignment='closed_assumed',basis='roster_default_no_voice_match'))
        shown=c.snapshot()['rows'][1]
        self.assertEqual(shown['label'],'Alex · assumed');self.assertEqual(shown['display_profile_id'],PERSON_A)
        self.assertIsNone(shown['profile_id']);self.assertIsNone(shown['raw_identity']['known_profile_id'])
        self.assertEqual(shown['identity_status'],'unavailable');self.assertTrue(shown['closed_group_display'])
        c.mode='selected_focus';shown=c.snapshot()['rows'][1]
        self.assertNotIn('assumed',shown['label']);self.assertFalse(shown['closed_group_display'])
        c.mode='selected_closed';c.selected_ids=[PERSON_B];self.assertFalse(c.snapshot()['rows'][1]['closed_group_display'])
    def test_people_mutation_invalidates_closed_display_assumptions(self):
        c=self.controller;c.mode='selected_closed';part=c.rows['utterance:42']['segments'][1]
        part.update(prototype_closed_group=True,closed_display_assignment=dict(profile_id=PERSON_A))
        c._do_person_mutation('delete',PERSON_A)
        self.assertNotIn('closed_display_assignment',part)
        self.assertFalse(c.snapshot()['rows'][1]['closed_group_display'])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="PROTO1 synthetic view contracts ")
        self.addCleanup(self.temporary.cleanup)
        self.data = Path(self.temporary.name)
        self.assertNotIn(ROOT, self.data.parents)
        # Constructor would start an owner thread and observe endpoints. Deliberately
        # supply only the state used by the actual methods under test instead.
        c = Controller.__new__(Controller)
        self.controller = c
        c.data_root = self.data; c.store = ExplicitStubStore(); c.lock = threading.RLock()
        c.rows = OrderedDict([("utterance:42", s7_fixture())]); c.engine = None
        c.mode = "open_with_names"; c.recipe = "balanced"; c.tap = "O0"
        c.selected_ids = [PERSON_A];c.display_ids=[PERSON_A]; c.strict = False; c.state = "IDLE"
        c.status = "EXPLICIT SYNTHETIC VIEW FIXTURE"; c.error = None; c.metrics = {}
        c.settings = {}; c.enrollment = {"state": "IDLE", "can_save": False}
        c._enroll_thread = None; c._quality_thread = None; c._enroll_live = None
        c.epoch = 7; c.commands = queue.Queue(32); c.closed = False; c.transitions = []
        c.source_kind = None
        c._stop_session = Mock(name="no session exists in synthetic fixture")
        c._observe_output = Mock(name="endpoint inventory forbidden in view tests")
        self.disk = patch("app.controller.shutil.disk_usage", return_value=Disk(20*1024**3, 10*1024**3, 10*1024**3))
        self.disk.start(); self.addCleanup(self.disk.stop)
        process = SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=64*1024**2),
            num_threads=lambda: 1, cpu_times=lambda: (0.0, 0.0))
        self.process = patch("psutil.Process", return_value=process)
        self.process.start(); self.addCleanup(self.process.stop)
        self.no_models = patch("app.pipeline.ResidentModels.acquire", side_effect=AssertionError("Neural execution forbidden"))
        self.no_models.start(); self.addCleanup(self.no_models.stop)

    def test_mixed_speaker_partition_is_complete_and_keeps_native_segment_ids(self):
        c = self.controller; before = deepcopy(c.rows)
        rows = c.snapshot()["rows"]
        self.assertEqual([row["id"] for row in rows], [part["segment_id"] for part in before["utterance:42"]["segments"]])
        self.assertEqual(" ".join(row["raw_asr_text"] for row in rows), before["utterance:42"]["text"])
        self.assertEqual("".join(row["provisional_display_text"] for row in rows), "Hello Alex I am ready thank you")
        self.assertEqual("".join(row["final_punctuated_display_text"] for row in rows), "Hello Alex, I am ready. Thank you.")
        self.assertEqual([row["label"] for row in rows], ["Alex", "Speaker_9"])
        self.assertEqual(c.rows, before)

    def test_late_identity_revision_and_rename_preserve_raw_tokens_and_ids(self):
        c = self.controller; old = c.snapshot()["rows"]; row = c.rows["utterance:42"]
        row["segments"][1].update(known_profile_id=PERSON_B, naming_state="confirmed")
        row["identity_version"] = 5
        revised = c.snapshot()["rows"]
        self.assertEqual([r["id"] for r in revised], [r["id"] for r in old])
        self.assertEqual([r["raw_asr_text"] for r in revised], [r["raw_asr_text"] for r in old])
        self.assertEqual([r["label"] for r in revised], ["Alex", "Alex"])
        c._do_person_mutation("rename", PERSON_B, "Sam")
        self.assertEqual(c.store.summaries()[1]["name"], "Sam")
        self.assertTrue(all(part["known_profile_id"] is None for part in row["segments"]))
        row["segments"][1].update(known_profile_id=PERSON_B, naming_state="confirmed")
        named = c.snapshot()["rows"]
        self.assertEqual(named[1]["label"], "Sam")
        self.assertEqual([r["raw_asr_text"] for r in named], [r["raw_asr_text"] for r in old])
        self.assertEqual([r["id"] for r in named], [r["id"] for r in old])

    def test_modes_keep_all_words_and_strict_hides_only_the_view(self):
        c = self.controller
        c.mode = "enrolled_names"
        self.assertEqual([r["label"] for r in c.snapshot()["rows"]], ["Alex", "Unknown"])
        c.mode = "anonymous_conversation"
        self.assertEqual([r["label"] for r in c.snapshot()["rows"]], ["Speaker_2", "Speaker_9"])
        c.mode = "selected_focus"; c.strict = True
        strict = c.snapshot()["rows"]
        self.assertEqual([r["visible"] for r in strict], [True, False])
        self.assertEqual([r["selected"] for r in strict], [True, False])
        self.assertEqual(len(strict), 2)  # Full internal transcript is still supplied.
        c.rows["utterance:42"]["segments"][0]["naming_state"] = "unknown"
        self.assertFalse(any(r["visible"] for r in c.snapshot()["rows"]))
        c._do_switch("caption_only", None, None, None, False)  # The real rescue command.
        rescued = c.snapshot()["rows"]
        self.assertTrue(all(r["visible"] for r in rescued))
        self.assertEqual([r["label"] for r in rescued], ["Transcription", "Transcription"])
        self.assertEqual([r["raw_asr_text"] for r in rescued], [r["raw_asr_text"] for r in strict])

    def test_deleting_the_last_selected_uuid_clears_strict_and_preserves_other_person(self):
        c = self.controller; c.mode = "selected_focus"; c.strict = True
        raw = [r["raw_asr_text"] for r in c.snapshot()["rows"]]
        c._do_person_mutation("delete", PERSON_A)
        self.assertEqual(c.selected_ids, []); self.assertFalse(c.strict)
        self.assertEqual([p["id"] for p in c.store.summaries()], [PERSON_B])
        rows = c.snapshot()["rows"]
        self.assertTrue(all(r["visible"] for r in rows))
        self.assertEqual([r["raw_asr_text"] for r in rows], raw)

    def test_misaligned_final_text_is_not_partitioned_onto_wrong_speakers(self):
        c = self.controller; row = c.rows["utterance:42"]
        row["display_text"] = "An incompatible final rewrite."
        rows = c.snapshot()["rows"]
        self.assertTrue(all(r["final_punctuated_display_text"] is None for r in rows))
        self.assertEqual(" ".join(r["raw_asr_text"] for r in rows), row["text"])
        self.assertEqual("".join(r["provisional_display_text"] for r in rows), "Hello Alex I am ready thank you")

    def test_assumed_marker_applies_to_named_history_not_neutral_or_anonymous_views(self):
        c=self.controller;c.rows['utterance:42']['segments'][0]['prototype_assignment']='forced'
        c.mode='selected_closed';self.assertEqual(c.snapshot()['rows'][0]['label'],'Alex · assumed')
        c.mode='anonymous_conversation';self.assertEqual(c.snapshot()['rows'][0]['label'],'Speaker_2')
        c.mode='caption_only';self.assertEqual(c.snapshot()['rows'][0]['label'],'Transcription')

    def test_snapshot_outputs_are_detached_and_report_retention_without_saving(self):
        c = self.controller; snapshot = c.snapshot()
        self.assertEqual(snapshot["settings"]["completed_session_limit"], 10)
        self.assertEqual(snapshot["settings"]["session_quota_mib"], 256)
        self.assertEqual(snapshot["settings"]["ram_horizon_sec"], 120)
        self.assertEqual(snapshot["metrics"]["free_disk_gib"], 10)
        self.assertEqual(snapshot["direction"], "unavailable")
        snapshot["rows"][0]["raw_asr_text"] = "MUTATED COPY"
        snapshot["people"][0]["name"] = "MUTATED COPY"
        snapshot["selected_ids"].clear(); snapshot["settings"]["ram_horizon_sec"] = 999
        snapshot["enrollment"]["state"] = "MUTATED COPY"
        current = c.snapshot()
        self.assertEqual(current["rows"][0]["raw_asr_text"], "HELLO ALEX I")
        self.assertEqual(current["people"][0]["name"], "Alex")
        self.assertEqual(current["selected_ids"], [PERSON_A])
        self.assertEqual(current["enrollment"]["state"], "IDLE")
        self.assertEqual(list(self.data.iterdir()), [])

    def test_settings_validate_all_changes_before_persisting(self):
        c = self.controller
        values = {"completed_session_limit": 3, "session_quota_mib": 64, "ram_horizon_sec": 60}
        c._do_settings(values)
        path = self.data / "settings.json"; original = path.read_bytes()
        self.assertEqual(json.loads(original), values)
        for invalid in ({"completed_session_limit": 4}, {"session_quota_mib": 1000},
                        {"ram_horizon_sec": 30}, {"save_session_text": False},
                        {"direction": "left"}, {"theme": "High contrast", "ram_horizon_sec": 0}):
            with self.subTest(values=invalid), self.assertRaises(ValueError): c._do_settings(invalid)
            self.assertEqual(c.settings, values); self.assertEqual(path.read_bytes(), original)
        self.assertEqual(c.snapshot()["settings"]["ram_horizon_sec"], 60)

    def test_saved_microphone_permission_and_automatic_start_validation(self):
        c = self.controller
        for invalid in ({'microphone_preapproved': 'yes'}, {'auto_start_listening': 1},
                        {'auto_start_listening': True}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                c._do_settings(invalid)
        c._do_settings({'microphone_preapproved': True, 'auto_start_listening': True})
        saved = json.loads((self.data/'settings.json').read_text())
        self.assertTrue(saved['microphone_preapproved'] and saved['auto_start_listening'])
        with self.assertRaises(ValueError): c._do_settings({'microphone_preapproved': False})
        c._do_settings({'microphone_preapproved': False, 'auto_start_listening': False})
        self.assertFalse(c.settings['auto_start_listening'])

    def test_mark_without_audio_writes_only_pinned_metadata_and_last_twenty_rows(self):
        c = self.controller
        c.rows = OrderedDict((str(i), {"caption_key": str(i), "text": f"SYNTHETIC ROW {i}"}) for i in range(25))
        with patch("soundfile.write", side_effect=AssertionError("Audio must not be written")):
            c._do_mark_problem(False)
        folder = Path(c.metrics["last_problem_path"])
        self.assertEqual(folder.parent, self.data / "problems")
        self.assertEqual({p.name for p in folder.iterdir()}, {"PROBLEM.json", "PINNED"})
        receipt = json.loads((folder / "PROBLEM.json").read_text(encoding="utf-8"))
        self.assertFalse(receipt["audio_saved"]); self.assertTrue(receipt["private"])
        self.assertEqual([r["caption_key"] for r in receipt["caption_rows"]], [str(i) for i in range(5,25)])
        self.assertIn(str(folder), c.status)
        c._retention(); self.assertTrue((folder / "PROBLEM.json").exists())

    def test_explicit_audio_excerpt_is_exact_recent_thirty_seconds_from_ram(self):
        c = self.controller; journal = MemoryJournal(reserve_sec=60)
        for second in range(70): journal.append(np.full(16000, second/280, dtype=np.float32))
        expected = journal.read(40*16000, 30*16000, wait_sec=0)
        c.engine = SimpleNamespace(_journal=journal, session_dir=self.data / "synthetic-session")
        c._do_mark_problem(True)
        folder = Path(c.metrics["last_problem_path"])
        audio, rate = sf.read(folder / "excerpt.wav", dtype="float32")
        self.assertEqual(rate, 16000); self.assertEqual(len(audio), 30*16000)
        np.testing.assert_allclose(audio, expected, rtol=0, atol=1/32768)
        receipt = json.loads((folder / "PROBLEM.json").read_text(encoding="utf-8"))
        self.assertTrue(receipt["audio_saved"])
        self.assertEqual((receipt["source_start_sec"], receipt["source_end_sec"]), (40,70))
        self.assertEqual(receipt["gain_policy"], "O0_host_plus3dB_once")
        self.assertTrue((folder / "PINNED").is_file())
        c._retention(); self.assertTrue((folder / "excerpt.wav").is_file())

    def test_public_mark_requires_true_audio_choice_and_does_not_execute_on_enqueue(self):
        c = self.controller
        for choice, expected in ((False, False), ("true", False), (1, False), (True, True)):
            c.mark_problem(save_audio=choice)
            action, args, kwargs = c.commands.get_nowait()
            self.assertEqual((action, args, kwargs), ("mark_problem", (expected,), {}))
        self.assertFalse((self.data / "problems").exists())

    def test_retention_removes_only_completed_unpinned_sessions_and_honors_free_floor(self):
        c = self.controller; c.settings = {"completed_session_limit": 3, "session_quota_mib": 64}
        sessions = self.data / "sessions"; sessions.mkdir()
        paths = []
        for index in range(7):
            path = sessions / f"edge_prototype_fixture_{index}"; path.mkdir(); paths.append(path)
            (path / "synthetic.txt").write_text("synthetic disposable session", encoding="utf-8")
            if index != 1: (path / "session_finalization_v3.json").write_text("{}", encoding="utf-8")
            if index == 0: (path / "PINNED").touch()
            os.utime(path, (1700000000+index, 1700000000+index))
        for protected in ("people", "problems", "historical"):
            folder = self.data / protected; folder.mkdir()
            (folder / "synthetic-protected.txt").write_text("preserve", encoding="utf-8")
        with patch("app.controller.shutil.disk_usage", return_value=Disk(10*1024**3, 9*1024**3, 1024**3)):
            with self.assertRaisesRegex(RuntimeError, "Less than2GiB"): c._retention()
        self.assertTrue(all(path.exists() for path in paths))
        c._retention()
        self.assertEqual([i for i,path in enumerate(paths) if path.exists()], [0,1,6])
        for protected in ("people", "problems", "historical"):
            self.assertEqual((self.data / protected / "synthetic-protected.txt").read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__": unittest.main()
