"""Integrity tests using real frozen loops and stub events. README_REVIEW_ASR.md."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from common import bind
from review_asr_components import scan_events
import test_asr_lane_components as fixtures


class TestASRReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.TestRealASRLoops.setUpClass()
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def fixture(self,variant='A0'):
        t=fixtures.TestRealASRLoops();capture=t.capture()
        (t.base._asr_loop if variant=='A0' else t.native._asr_loop)(capture,fixtures.BaselineStub() if variant=='A0' else fixtures.NativeStub())
        cell=dict(variant=variant,job=dict(frames=3205),summary=capture.finish_capture(),events={'path':str(self.root/'events.gz')})
        events=t.events();self.write(cell,events);return cell,events
    def write(self,cell,events):
        data=''.join(json.dumps(row,separators=(',',':'))+'\n' for row in events).encode('utf-8')
        path=Path(cell['events']['path'])
        with gzip.open(path,'wb') as stream:stream.write(data)
        cell['events']=bind(path)
        cell['events_expanded']=dict(uncompressed_sha256=hashlib.sha256(data).hexdigest(),uncompressed_bytes=len(data))
    def test_actual_baseline_loop_and_native_multiple_finals_pass(self):
        for variant in ('A0','A1','A2','A3'):
            cell,_=self.fixture(variant);row=scan_events(cell,1600)
            self.assertEqual(row['source_samples'],3205)
            self.assertEqual(row['final_utterances'],2 if variant=='A0' else 3)
    def test_tail_cannot_be_dropped(self):
        cell,events=self.fixture();events=[r for r in events if r['event_type']!='research_asr_tail_dispatch'];self.write(cell,events)
        with self.assertRaisesRegex(ValueError,'dispatch'):scan_events(cell,1600)
    def test_raw_final_cannot_be_replaced_by_formatted_text(self):
        cell,events=self.fixture();next(r for r in events if r['event_type']=='component_final_punctuation')['payload']['raw_text']='different'
        self.write(cell,events)
        with self.assertRaisesRegex(ValueError,'Formatting'):scan_events(cell,1600)
    def test_native_final_omission_cannot_be_hidden(self):
        cell,events=self.fixture('A2')
        events=[r for r in events if not (r['event_type']=='research_asr_observation' and r['payload']['text']=='second')]
        self.write(cell,events)
        with self.assertRaises(ValueError):scan_events(cell,1600)
    def test_original_native_punctuation_must_remain(self):
        cell,events=self.fixture('A3');next(r for r in events if r['event_type']=='component_final_punctuation')['payload']['punctuation']['text']='changed'
        self.write(cell,events)
        with self.assertRaisesRegex(ValueError,'punctuation'):scan_events(cell,1600)
    def test_truncated_gzip_rejected_even_if_compressed_hash_updated(self):
        cell,_=self.fixture();path=Path(cell['events']['path']);path.write_bytes(path.read_bytes()[:-3]);cell['events']=bind(path)
        with self.assertRaises(EOFError):scan_events(cell,1600)
    def test_fake_completion_summary_rejected(self):
        cell,_=self.fixture();cell['summary']['input_samples']=3204
        with self.assertRaisesRegex(ValueError,'summary'):scan_events(cell,1600)
    def test_clock_before_source_or_formatted_fifo_rejected(self):
        cell,original=self.fixture()
        for kind,key in [('research_asr_observation','available_at_sec'),('component_final_punctuation','modeled_available_at_sec')]:
            events=deepcopy(original);next(r for r in events if r['event_type']==kind)['payload'][key]=0.
            self.write(cell,events)
            with self.assertRaises(ValueError):scan_events(cell,1600)


if __name__=='__main__':unittest.main()
