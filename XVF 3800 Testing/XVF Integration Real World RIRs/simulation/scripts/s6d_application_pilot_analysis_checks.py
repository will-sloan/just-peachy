"""Model-free analyzer clock/absence fixtures. See README_S6D_APPLICATION_PILOT_ANALYSIS.md."""
from pathlib import Path
import json
import tempfile
import unittest
import s6d_application_pilot_analysis as analysis


class AnalysisChecks(unittest.TestCase):
    def test_actual_nested_event_schema_source_origin_and_missing_cell(self):
        with tempfile.TemporaryDirectory(prefix='s6d-analysis-fixture-') as temp:
            output=Path(temp)/'job';output.mkdir();session=Path(temp)/'session';session.mkdir()
            job={'job_id':'fixture','candidate':'fixture','scene_id':'fixture','variant':'original','audio_duration_sec':3.,'settings':None,'output':str(output)}
            manifest={'helper':{'path':'fixture_only','sha256':'fixture_only'}};manifest_binding={'path':'fixture_only_manifest'}
            row,data=analysis.analyze_cell(job,manifest_binding,manifest)
            self.assertEqual(row['status'],'UNAVAILABLE');self.assertIsNone(data)
            def save(path,value):path.write_text(json.dumps(value)+'\n')
            def lines(path,rows):path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            receipt={'job':job,'manifest':manifest_binding,'helper':manifest['helper'],'status':'COMPLETE','failure':None,
                'native_tested':True,'resource_observer_closed':True,'event_consumer_drained':True,'observer_errors':[],
                'completion_errors':[],'telemetry':{'state':'COMPLETED'},'session_dir':str(session)}
            save(output/'RESULT.json',receipt)
            events=[{'event_type':'session_created','payload':{'pilot_publication_monotonic_sec':100.}},
                {'event_type':'source_started','payload':{'pilot_publication_monotonic_sec':102.}},
                {'event_type':'transcript_final','payload':{'utterance_id':'u','text':'HELLO','source_start_sec':0.,
                    'source_end_sec':1.9,'pilot_publication_monotonic_sec':104.},'actual_consumed_monotonic_sec':104.05}]
            lines(output/'consumer_events.jsonl',events);lines(session/'events.jsonl',events)
            lines(output/'resources.jsonl',[{'rss':123,'sampling_gap_sec':.25,'telemetry':{}}])
            lines(session/'latest_labelled_transcript.jsonl',[{'utterance_id':'u','text':'HELLO','latest_known_profile_id':None}])
            save(session/'session_finalization_v3.json',{'state':'COMPLETED','event_and_transcript_handles_closed':True,'live_lanes_at_finalization':[],'finalization_error':None})
            row,data=analysis.analyze_cell(job,manifest_binding,manifest)
            self.assertEqual(row['status'],'ANALYZED');self.assertEqual(row['first_text'][0]['publication_from_source_start_sec'],2.)
            self.assertAlmostEqual(row['first_text'][0]['consumer_from_source_start_sec'],2.05)
            self.assertAlmostEqual(row['first_text'][0]['publication_minus_source_end_sec'],.1)
            self.assertEqual(row['startup']['session_created'][0]['publication_before_source_start_sec'],2.)
            receipt['event_consumer_drained']=False;save(output/'RESULT.json',receipt)
            row,data=analysis.analyze_cell(job,manifest_binding,manifest)
            self.assertEqual(row['status'],'FAILED_OR_UNADMITTED');self.assertIsNone(data)

    def test_pairs_keep_missing_words_and_incompatible_source_support(self):
        def cell(text,start,pub):return {'first':{'u':{'text':text,'source_start_sec':start,'publication_from_source_start_sec':pub,'consumer_from_source_start_sec':pub+.01}},'finals':{'u':{'text':text}}}
        result=analysis.pair('a','b',{'a':cell('hello',0.,2.),'b':cell('different',1.,3.)},'fixture')
        self.assertFalse(result['all_raw_final_rows_equal'])
        self.assertEqual(result['additional_publication_delay']['count'],0)
        self.assertEqual(analysis.pair('a','missing',{},'fixture')['status'],'UNAVAILABLE')
        result=analysis.pair('a','b',{'a':cell('hello',0.,2.),'b':cell('hello',0.,2.1)},'fixture')
        self.assertAlmostEqual(result['additional_publication_delay']['p50'],.1)


if __name__=='__main__':unittest.main(verbosity=2)
