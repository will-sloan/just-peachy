"""Model-free parser rejection checks; README_NATIVE_STREAM_MODELS_V1.md."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from native_stream_review_v1 import review


def fixture():
    rows = [dict(kind='start', schema='n5-native-stream-smoke-v1', frames=1600, push_frames=1280,
        sample_rate=16000, gpu=-1, ctc_chunk=.16, ctc_left=1.92, ctc_right=1.92, rnnt_right=1, stop_ms=800)]
    for name, length in [('empty',0),('one_sample',1),('short_tail',1281),('saved_source',1600),
                         ('saved_source_repeat',1600),('saved_source_forced',1600)]:
        rows.append(dict(kind='case_start',case=name,frames=length))
        full = name.startswith('saved_source')
        if full: rows.append(dict(kind='event',case=name,phase='finish',sent_frames=length,is_final=True,
            audio_processed_seconds_raw=.1,confidence_raw=0.,channel_raw=0,
            hypothesis=dict(text='fixture',words=[dict(text='fixture',start_ms=0,end_ms=1)])))
        rows.append(dict(kind='case_closed',case=name,sent_frames=length,events=int(full),finals=int(full),
                         forced_endpoint=name=='saved_source_forced',stream_closed=True))
    rows.append(dict(kind='result',status='PASS_NATIVE_STREAM_CONFORMANCE_ONLY',cases=6,
        resident_state_parity=True,recognizer_closed=True,N4_accepted=False,N5_complete=False,CM5_tested=False))
    return rows


class ReviewTests(unittest.TestCase):
    def check(self, rows):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'synthetic-parser-only.jsonl'
            p.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
            return review(p,1600)

    def test_valid_complete_fixture(self):
        self.assertEqual(len(self.check(fixture())['cases']),6)

    def test_failure_and_missing_or_extra_output_rejected(self):
        for rows in [fixture()[:-1], fixture()+[dict(kind='failure')], [dict(kind='failure')]]:
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError): self.check(rows)

    def test_configuration_rejected(self):
        for key,value in [('gpu',0),('frames',1599),('ctc_left',0),('push_frames',2560)]:
            rows=fixture();rows[0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(rows)

    def test_closure_accounting_and_order_rejected(self):
        for key,value in [('sent_frames',3),('events',1),('stream_closed',False),('case','unexpected')]:
            rows=fixture();rows[2][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(rows)

    def test_changed_repeat_text_or_words_rejected(self):
        for change in ('text','words'):
            rows=fixture();event=next(r for r in rows if r.get('kind')=='event' and r['case']=='saved_source_repeat')
            if change=='text':event['hypothesis']['text']='different'
            else:event['hypothesis']['words'][0]['end_ms']=2
            with self.subTest(change=change),self.assertRaises(ValueError):self.check(rows)

    def test_invalid_event_numbers_and_phase_rejected(self):
        for key,value in [('confidence_raw',float('nan')),('sent_frames',1601),('phase','after_close'),('is_final',1)]:
            rows=fixture();event=next(r for r in rows if r.get('kind')=='event');event[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(rows)

    def test_recognizer_closure_and_acceptance_rejected(self):
        for key in ('recognizer_closed','resident_state_parity','CM5_tested','N5_complete'):
            rows=fixture();rows[-1][key]=not rows[-1][key]
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(rows)


if __name__=='__main__':unittest.main(verbosity=2)
