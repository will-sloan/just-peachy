"""Actual shared presentation/name-map fixture, with no model/hardware calls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parents[4] / "prototype"
sys.path[:0]=[str(SOURCE),str(SOURCE / "vendor")]
from runtime_observer import RuntimeGalleryObserver

INDEX=Path("G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/component/E0/RUNTIME_GALLERY_INDEX_SAFE.json")


@unittest.skipUnless(INDEX.exists(),"Actual E0 component preparation required")
class ObserverTests(unittest.TestCase):
    def test_out_of_order_match_closed_assumption_and_span_invariance(self):
        index=json.loads(INDEX.read_text())
        entry=next(e for e in index["conditions"] if e["mode"]=="closed" and e["domain"]=="clean_source" and not e["matched_duration_diagnostic"])
        gallery=json.loads(Path(entry["gallery"]["path"]).read_text())
        vector=gallery["profiles"][0]["vector"]
        with tempfile.TemporaryDirectory() as output:
            observer=RuntimeGalleryObserver("E0",INDEX,output,"test-session")
            # Simulate asynchronous callback delivery without deriving a track
            # from the waveform or from evaluator truth.
            observer.event("speaker_decision",1,{"event_id":"scheduler:1","input_event_id":"embedding:1","tracker_id":"track-1","anonymous_label":"Speaker 1","state":"committed","committed":True})
            observer.event("research_embedding",1,{"evidence_event_id":"embedding:1","normalized_embedding":vector,"source_start_sec":0.,"source_end_sec":1.,"speech":True,"overlap":False,"clean_intervals":[[0.,1.]]})
            common={"utterance_id":"u","session_id":"test-session","text":"hello world","display_text":"Hello world.","source_start_sec":0.,"source_end_sec":1.2,"available_at_sec":1.3}
            observer.event("s6d_text_ready",1.2,dict(common,event_id="asr:1",text_revision_id="asr:1"))
            observer.event("transcript_final",1.2,dict(common,event_id="asr:2",text_revision_id="asr:2",tracker_id="track-1",latest_label="Speaker 1",latest_label_time=1.3,identity_version=2))
            observer.event("transcript_label_revision",1.2,{"session_id":"test-session","utterance_id":"u","event_id":"scheduler:3","source_start_sec":0.,"source_end_sec":1.,"target_source_start_sec":0.,"target_source_end_sec":1.2,"target_text_revision_id":"asr:2","target_span_ids":["test-session/u/token:1"],"replacement_tracker_id":"track-1","latest_label":"Speaker 1","latest_label_time":1.4,"identity_version":3})
            observer.queue.join()
            report=observer.finish([{"utterance_id":"u","raw_asr_text":"hello ","provisional_display_text":"Hello ","final_punctuated_display_text":"Hello ","token_range":[0,1]},
                                    {"utterance_id":"u","raw_asr_text":"world","provisional_display_text":"world.","final_punctuated_display_text":"world.","token_range":[1,2]}])
            self.assertEqual(report["embedding_matches"]["matched_actual_embedding_decisions"],1)
            self.assertEqual(len(report["conditions"]),15)
            self.assertTrue(all(c["raw_words_equal_observer_base"] for c in report["conditions"]))
            self.assertTrue(all(c["formatted_words_equal_observer_base"] for c in report["conditions"]))
            self.assertTrue(report["actual_rows_equal_observer_base_raw"])
            self.assertTrue(report["actual_rows_equal_observer_base_formatted"])
            closed=next(c for c in report["conditions"] if c["gallery_id"]==entry["gallery_id"])
            self.assertEqual(closed["naming_states"]["closed_assumption"],1)
            rows=json.loads(Path(closed["rows_path"]).read_text())
            self.assertEqual(rows[0]["text"],"hello world")
            self.assertTrue(all(s["first_shown_label"]=="Pending identity" for s in rows[0]["word_spans"]))
            self.assertEqual(report["embeddings_without_actual_decision"],0)
            self.assertEqual(report["decisions_without_actual_embedding"],0)


if __name__=="__main__":unittest.main()
