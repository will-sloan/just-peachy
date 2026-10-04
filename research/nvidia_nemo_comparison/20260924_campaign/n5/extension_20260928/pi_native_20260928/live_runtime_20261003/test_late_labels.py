"""Synthetic presentation contracts; no native evidence. See README_LATE_LABELS.md."""
from copy import deepcopy
from dataclasses import replace
import unittest

from late_labels import SingleD1LateLabels
from profiles import RuntimeSelection


def selection():
    return RuntimeSelection("nemotron", "redimnet", "saved", "current_delayed",
        allow_experimental=True, revision_window_seconds=5,
        speaker_attribution="single_d1_late_labels")


def caption(identifier="u1", start=0., end=1., observed=0.):
    key = "s/"+identifier
    return dict(session_id="s", utterance_id=identifier, caption_key=key,
        text="exact ASR words", display_text="Exact ASR words.", text_revision_id="text:1",
        source_start_sec=start, source_end_sec=end,
        word_spans=[dict(id=key+"/token:1", source_start_sec=start,
            source_end_sec=end, first_seen_monotonic_sec=observed, speaker_history=[])])


def label(row, name, version, support=None):
    result = deepcopy(row)
    result["word_spans"][0]["speaker_history"].append(dict(label=name,
        track_id=None if name == "Unknown" else "s:nemotron-slot-0",
        profile_id=None if name == "Unknown" else "enrolled-1",
        event_id="n2-caption:"+str(version), identity_version=[float(version), version],
        source_evidence_span=support or [row["source_start_sec"], row["source_end_sec"]]))
    return result


class LateLabelTests(unittest.TestCase):
    def helper(self, **kwargs):
        return SingleD1LateLabels(selection(), "s", "matched-source-sha", **kwargs)

    def test_immediate_text_without_model_or_direction_identity(self):
        helper = self.helper()
        row = caption()
        row.update(label="Alice", known_name="Alice", angle_deg=45, doa_valid=True)
        shown = helper.project(row, now=0.)
        self.assertEqual((shown["text"], shown["display_text"]), (row["text"], row["display_text"]))
        self.assertEqual(shown["speaker"], "Unknown")
        self.assertTrue(shown["provisional"])
        self.assertFalse(shown["speaker_supported"])
        self.assertIsNone(helper.project(row, now=1.))

    def test_existing_evidence_is_immediate_and_later_revision_keeps_id(self):
        helper, row = self.helper(), caption()
        shown = helper.project(label(row, "Alice", 1), now=1.)
        self.assertEqual(shown["speaker"], "Alice")
        self.assertFalse(shown["provisional"])
        changed = helper.project(label(row, "Bob", 2), now=2.)
        self.assertEqual((changed["caption_key"], changed["text"]), (shown["caption_key"], row["text"]))
        self.assertEqual(changed["speaker"], "Bob")
        changed["attribution_spans"][0]["evidence"]["identity_version"][0] = 999
        expired = helper.project(label(row, "Charlie", 3), now=6.)
        self.assertEqual(expired["speaker"], "Bob")
        self.assertEqual(expired["attribution_status"], "expired_supported")
        self.assertEqual(expired["attribution_spans"][0]["evidence"]["identity_version"], [2., 2])

    def test_unknown_retraction_and_disjoint_evidence(self):
        helper, row = self.helper(), caption()
        self.assertEqual(helper.project(label(row, "Alice", 1, [2., 3.]), now=1.)["speaker"], "Unknown")
        helper.project(label(row, "Alice", 2), now=2.)
        shown = helper.project(label(row, "Unknown", 3), now=3.)
        self.assertEqual(shown["speaker"], "Unknown")
        self.assertFalse(shown["speaker_supported"])

    def test_expiry_and_eviction_cannot_recreate_old_caption(self):
        helper, row = self.helper(maximum_rows=1), caption()
        helper.project(row, now=0.)
        patches = helper.expire(now=5.)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]["attribution_status"], "expired_unknown")
        self.assertFalse(patches[0]["provisional"])
        self.assertEqual(helper.expire(now=6.), [])
        helper.project(caption("u2", 1., 2., 6.), now=6.)
        self.assertIsNone(helper.project(row, now=7.))
        self.assertEqual(len(helper.rows), 1)

    def test_rewrite_new_span_does_not_reopen_old_span_window(self):
        helper, row = self.helper(), caption()
        helper.project(label(row, "Alice", 1), now=1.)
        row["text"] += " continued"
        row["display_text"] = row["text"]
        row["source_end_sec"] = 2.
        row["text_revision_id"] = "text:2"
        row["word_spans"].append(dict(id="s/u1/token:2", source_start_sec=1., source_end_sec=2.,
                                      first_seen_monotonic_sec=6., speaker_history=[]))
        changed = helper.project(label(row, "Bob", 2), now=6.)
        self.assertEqual(changed["attribution_spans"][0]["speaker"], "Alice")
        self.assertEqual(changed["attribution_spans"][1]["status"], "pending")
        self.assertTrue(changed["provisional"])

    def test_explicit_mode_foreign_session_and_bounds(self):
        with self.assertRaises(ValueError):
            replace(selection(), allow_experimental=False).validate()
        with self.assertRaises(ValueError):
            replace(selection(), diarizer="pyannote", nemotron_profile=None).validate()
        helper, row = self.helper(), caption()
        row["session_id"] = "other"
        with self.assertRaises(ValueError):
            helper.project(row, now=0.)
        row = caption()
        row["word_spans"][0]["source_end_sec"] = 2.
        with self.assertRaises(ValueError):
            helper.project(row, now=1.)


if __name__ == "__main__":
    unittest.main()
