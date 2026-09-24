"""Verify difficult/empty denominators; see README_SCORING.md."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


HERE=Path(__file__).resolve().parent
score=module('n3_score',HERE/'score_asr.py')
scoring=module('n2_score',HERE.parent/'n2/evaluation/scoring.py')


class ScoringTests(unittest.TestCase):
    def test_missed_words_overlap_and_empty_controls_keep_denominators(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);truth={};records=[]
            cases=[('complete_nonoverlap',[('s1','one two three')],''),
                   ('complete_overlap',[('s1','one two'),('s2','three four')],'one two'),
                   ('empty_control',[],'false words'),('incomplete_ambient_reference',[('s1','target words')],'target')]
            for i,(category,turns,hyp) in enumerate(cases):
                cell=root/str(i);cell.mkdir();events=cell/'events.jsonl';events.write_text('')
                job='N3_fixture'+str(i);path=cell/'RESULT.json'
                value=dict(status='COMPLETE',job_id=job,input_samples=16000,events_sha256=score.sha(events),
                    raw_final_text=hyp,source_seconds=1,compute_ms=10,elapsed_seconds=.1,cpu_seconds=.1,
                    peak_process_rss_bytes=1000,word_revision_removals=0,first_text_elapsed_sec=None,finalization_after_source_sec=None)
                path.write_text(json.dumps(value));records.append(dict(path=str(path),sha256=score.sha(path)))
                truth[job.replace('N3_','N2_')]=dict(reference_class=category,tap='O0',frames=16000,
                    complete_reference=category!='incomplete_ambient_reference',
                    turns=[dict(identity=s,transcript_normalized=t) for s,t in turns])
            (root/'RESULT.json').write_text(json.dumps(dict(variant='A2',runtime='fixture',status='COMPLETE',completed=4,total=4,cells=records,contract_sha256='fixture')))
            (root/'RUN_LOCK.json').write_text(json.dumps(dict(delivery='accelerated_causal_not_live_latency')))
            result=score.score_run(root,truth,scoring);rows={r['reference_class']:r for r in result['table']}
            self.assertEqual(rows['complete_nonoverlap']['WER'],1.)
            self.assertEqual(rows['complete_nonoverlap']['reference_words'],3)
            self.assertEqual(rows['complete_overlap']['cp_reference_words'],4)
            self.assertEqual(rows['complete_overlap']['single_output_cpWER'],.5)
            self.assertIsNone(rows['complete_overlap']['WER'])
            self.assertEqual(rows['empty_control']['false_words_per_minute'],120)
            self.assertIsNone(rows['incomplete_ambient_reference']['WER'])


if __name__=='__main__':unittest.main()
