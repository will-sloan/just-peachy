"""Acceptance-denominator and evidence/timing refusal tests; README_REVIEW.md."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from review_completed import binding, complete_cells, primary_tables, require_hash, resource_summary, validate_paced_manifest


class ReviewTests(unittest.TestCase):
    def fixture(self):
        cells=[dict(job_id='cell_'+str(i),all_samples=True) for i in range(96)]
        rows=[dict(reference_class='complete_nonoverlap',tap='O0',cells=32,word_errors=10,reference_words=100),
              dict(reference_class='complete_nonoverlap',tap='O1',cells=32,word_errors=9,reference_words=10),
              dict(reference_class='complete_overlap',tap='O0',cells=9,word_errors=999,reference_words=999)]
        return dict(status='COMPLETE',runs=[dict(variant=a,runtime='fixture',completed=96,total=96,
                    cells=copy.deepcopy(cells),table=copy.deepcopy(rows)) for a in ['A0','A1','A2','A3']])

    def test_ratio_of_sums_and_overlap_exclusion(self):
        for row in primary_tables(self.fixture()):
            self.assertEqual(row['word_errors'],19)
            self.assertAlmostEqual(row['combined_lexical_WER'],19/110)
            self.assertEqual(row['other_reference_classes'][0]['word_errors'],999)

    def test_missing_duplicate_unmatched_and_incomplete_audio_fail(self):
        for kind in ['missing','duplicate','unmatched','samples']:
            fixture=self.fixture();run=fixture['runs'][0]
            if kind=='missing':run['cells'].pop()
            elif kind=='duplicate':run['cells'][1]=copy.deepcopy(run['cells'][0])
            elif kind=='unmatched':run['cells'][0]['job_id']='another'
            else:run['cells'][0]['all_samples']=False
            with self.assertRaises(ValueError):primary_tables(fixture)

    def test_negative_endpoint_is_separate_from_completion(self):
        cell=dict(source_seconds=45.,compute_ms=100.,peak_process_rss_bytes=1000,
            first_text_elapsed_sec=None,elapsed_seconds=45.8,finalization_after_source_sec=-20.)
        lock=dict(cpu_affinity=[4],numerical_threads=1,delivery='source_paced_independent_producer',model_binding=dict(gpu=False))
        summary=resource_summary(dict(variant='A1',runtime='onnx'),[cell],lock)
        self.assertAlmostEqual(summary['completion_after_audio_duration_sec']['max'],.8)
        self.assertEqual(summary['last_speech_final_vs_audio_end_sec']['min'],-20.)
        self.assertEqual(summary['first_text_elapsed_sec']['n'],0)
        self.assertFalse(summary['gpu'])
        lock['model_binding']=None
        self.assertFalse(resource_summary(dict(variant='A0',runtime='sherpa'),[cell],lock)['gpu'])
        lock['model_binding']=dict(gpu=True)
        self.assertTrue(resource_summary(dict(variant='A2',runtime='native'),[cell],lock)['gpu'])

    def test_changed_evidence_hash_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'result.json';path.write_text('{}',encoding='utf-8')
            row=binding(path);path.write_text('{"changed":true}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'binding changed'):require_hash(row)

    def test_queue_count_cannot_replace_actual_cell_count(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name)
            (folder/'RESULT.json').write_text(json.dumps(dict(status='COMPLETE',total=96,completed=96,cells=[])),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'census'):complete_cells(folder,96,[])

    def test_eight_file_census_requires_exact_predeclared_waveforms(self):
        jobs=[dict(job_id='N2_'+str(i),frames=16,audio_sha256=str(i),gain=1,
                   sample_rate_hz=16000,reset_between_scenes=True) for i in range(8)]
        cells=[dict(job_id='N3_'+str(i),input_samples=16,audio_sha256=str(i),status='COMPLETE',
                    delivery='source_paced_independent_producer') for i in range(8)]
        validate_paced_manifest(jobs,cells)
        for key,value in [('job_id','unexpected'),('input_samples',15),('audio_sha256','changed'),('delivery','accelerated')]:
            wrong=copy.deepcopy(cells);wrong[0][key]=value
            with self.assertRaises(ValueError):validate_paced_manifest(jobs,wrong)
        with self.assertRaises(ValueError):validate_paced_manifest(jobs,cells[:4])


if __name__=='__main__':unittest.main()
