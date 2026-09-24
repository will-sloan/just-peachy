"""Receipt, redaction and ASR invariance regressions; no audio/model calls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from prepare import bind,fingerprint,load
from summarize_screen import COMBINATIONS,asr_signatures,canonical_rows,save,summarize


def rows():
    return [{"utterance_id":"utterance:1","token_range":[1,2],"raw_asr_text":"transcript", "final_punctuated_display_text":"transcript."},
            {"utterance_id":"utterance:1","token_range":[0,1],"raw_asr_text":"private-fixture ","final_punctuated_display_text":"Private-fixture "}]


def events():
    return [{"event_type":"research_asr_dispatch","source_sec":0.1,"payload":{"source_start_sec":0.,"source_end_sec":0.1,"receptive_start_sec":0.,"available_source_cursor_sec":0.1,"native_endpoint":False,"advisory_endpoint":False,"reset_requested":False,"compute_ms":3.}},
            {"event_type":"s6d_text_ready","source_sec":1.,"payload":{"event_id":"asr:1","utterance_id":"utterance:1","source_start_sec":0.,"source_end_sec":1.,"text":"private-fixture transcript","final":True,"available_at_sec":4.5,"session_id":"private-session"}},
            {"event_type":"research_asr_reset","source_sec":1.,"payload":{"native_endpoint":True,"advisory_endpoint":False,"compute_ms":2.}}]


def fixture(root):
    jobs=[{"job_id":"N2_fixture_"+tap,"audio_path":"private-waveform-"+tap+".wav","audio_sha256":tap*32,"frames":16000,"sample_rate_hz":16000,"gain":1,"reset_between_scenes":True,"tap":tap} for tap in ["O0","O1"]]
    truth=root/"EVALUATOR_TRUTH.json";manifest=root/"AUDIO_ONLY.json"
    save(truth,{"cells":[{"job_id":j["job_id"],"frames":j["frames"],"screen48":False,"turns":[],"complete_reference":True,"reference_class":"empty_control"} for j in jobs]})
    save(manifest,{"jobs":jobs});save(root/"ROSTERS.json",{"primary":[]})
    save(root/"MANIFEST_RECEIPT.json",{"outputs":[bind(truth),bind(manifest),bind(root/"ROSTERS.json")]})
    indexes=[]
    for combo in COMBINATIONS:
        folder=root/combo
        contract={"combination":combo,"manifest":bind(manifest),"profile":"fixture","threads":{"asr":1},"source_bindings":{}}
        checksum=fingerprint(contract)
        save(folder/"ADMISSION.json",{"contract":contract,"contract_sha256":checksum})
        completed={}
        for job in jobs:
            attempt=folder/"cells"/job["job_id"]/"attempt_fixture"
            save(attempt/"FINAL_SNAPSHOT.json",{"rows":rows()})
            (attempt/"RUNTIME_EVENTS.jsonl").write_text("\n".join(json.dumps(r) for r in events())+"\n",encoding="utf-8")
            result=attempt/"RESULT.json"
            save(result,{"status":"COMPLETE","job_id":job["job_id"],"combination":combo,"audio":job,"elapsed_seconds":1.4,"evidence":[bind(attempt/"FINAL_SNAPSHOT.json"),bind(attempt/"RUNTIME_EVENTS.jsonl")]})
            save(attempt.parent/"CHECKPOINT.json",{"status":"COMPLETE","result":bind(result)})
            completed[job["job_id"]]=str(result)
        index=folder/"RESULT_INDEX.json"
        save(index,{"status":"COMPLETE","completed":completed,"failed":{},"total":2,"contract_sha256":checksum})
        indexes.append(index)
    return indexes,truth,manifest


class ScreenSummaryTests(unittest.TestCase):
    def test_exact_text_source_reset_invariance_excludes_clocks_and_labels(self):
        reference=asr_signatures(events(),rows())
        changed=deepcopy(events());changed[1]["payload"].update(available_at_sec=99,session_id="another",speaker="any label",publication_sequence=1000)
        changed[0]["payload"]["compute_ms"]=40
        self.assertEqual(reference,asr_signatures(changed,rows()))
        changed[1]["payload"]["source_end_sec"]=1.01
        self.assertNotEqual(reference["raw_observations"],asr_signatures(changed,rows())["raw_observations"])
        changed=deepcopy(events());changed[2]["payload"]["native_endpoint"]=False
        self.assertNotEqual(reference["dispatch_reset_source_sequence"],asr_signatures(changed,rows())["dispatch_reset_source_sequence"])
        self.assertEqual(canonical_rows(rows())[0]["text"],"private-fixture transcript")
        self.assertEqual(canonical_rows(rows(),True)[0]["text"],"Private-fixture transcript.")

    def test_complete_regression_population_redaction_and_empty_control_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);indexes,truth,manifest=fixture(root)
            result=summarize(indexes,truth,root/"private",root/"public",manifest,"regression")
            self.assertEqual(result["status"],"COMPLETE")
            self.assertEqual((result["scored_total_cells"],result["expected_total_cells"],result["matched_four_way_cells"]),(8,8,2))
            public=(root/"public/SCREEN_SUMMARY.json").read_text()
            for secret in ["private-fixture transcript","private-waveform","private-session",str(root)]:self.assertNotIn(secret,public)
            for group in result["groups"]:
                self.assertEqual(group["primary_actual_latest_words"]["empty_control_inserted_words"],2)
                self.assertIsNone(group["resources"]["cpu_seconds"])
                self.assertIsNone(group["resources"]["maximum_sampled_process_rss_bytes"])
                self.assertIsNone(group["activity_primary_collar0"]["micro_approximate_activity_DER"])

    def test_missing_factorial_and_corrupt_evidence_never_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);indexes,truth,manifest=fixture(root)
            result=summarize(indexes[:3],truth,root/"private",root/"public",manifest,"regression")
            self.assertEqual(result["status"],"PARTIAL")
            self.assertEqual(result["matched_four_way_cells"],0)
            result_path=Path(next(iter(load(indexes[0])["completed"].values())))
            (result_path.parent/"FINAL_SNAPSHOT.json").write_text("{}")
            result=summarize(indexes,truth,root/"private2",root/"public2",manifest,"regression")
            self.assertEqual(result["status"],"FAILED")
            self.assertEqual(result["scored_total_cells"],7)
            self.assertEqual(result["failure_counts"]["SCORING_OR_INTEGRITY_FAILED"],1)

    def test_valid_receipts_with_asr_change_are_failed_invariance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);indexes,truth,manifest=fixture(root)
            result_path=Path(next(iter(load(indexes[-1])["completed"].values())))
            changed=events();changed[1]["payload"]["source_end_sec"]=0.99
            event_path=result_path.parent/"RUNTIME_EVENTS.jsonl"
            event_path.write_text("\n".join(json.dumps(r) for r in changed)+"\n")
            result=load(result_path);result["evidence"]=[bind(e["path"]) for e in result["evidence"]];save(result_path,result)
            save(result_path.parent.parent/"CHECKPOINT.json",{"status":"COMPLETE","result":bind(result_path)})
            result=summarize(indexes,truth,root/"private",root/"public",manifest,"regression")
            self.assertEqual(result["collection_status"],"COMPLETE")
            self.assertEqual(result["status"],"FAILED_ASR_INVARIANCE")
            self.assertEqual(result["ASR_invariance_status"],"FAILED")


if __name__=="__main__":unittest.main()
