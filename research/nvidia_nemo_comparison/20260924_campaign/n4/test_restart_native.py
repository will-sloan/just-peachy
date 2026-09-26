"""Explicit-prefix native census, corruption and historical parity checks."""
from copy import deepcopy
import json
import unittest

from common import fingerprint, freeze, load, verify
import restart_native_journal as subject
import test_native_journal_review as original_tests
import review_native_journal as original

OUTPUT = None
CASES = []
EXTRA_FIELDS = {'schema','job_fingerprint','planned_audio_frames','delivered_audio_frames','intent',
                'delivered_length_independently_joined','same_controller_restart_qualified'}


def comparable(value):
    result={k:v for k,v in value.items() if k not in EXTRA_FIELDS}
    result['status']=result['status'].replace('COMPLETE_RELEASED_NATIVE','COMPLETE_NATIVE').replace('INCOMPLETE_RELEASED_NATIVE','INCOMPLETE_NATIVE')
    return result


class RestartNativeTests(original_tests.NativeJournalTests):
    """Reuse all original adversarial records, now against a true prefix reader."""
    def setUp(self):
        self.folder=OUTPUT/self._testMethodName; self.folder.mkdir()
        self.job=dict(job_id='SYNTHETIC_PREFIX_O0',audio_path=str(self.folder/'never_opened.wav'),
            audio_sha256='1'*64,frames=32000,sample_rate_hz=16000,gain=1.,reset_between_scenes=True,tap='O0')

    def review(self, session, **kwargs):
        return subject.inspect(session,job=self.job,delivered_frames=16000,intent='mid_file_stop',**kwargs)

    def test_complete_rotated_journal_preserves_scope_and_source_overhang(self):
        session,events=self.fixture(); events[2]['source_time_sec']=-.01; events[4]['source_time_sec']=1.08
        self.write(session,events,split=3); before=deepcopy(self.job)
        result=subject.require_complete(self.review(session))
        self.assertEqual(self.job,before); self.assertEqual(result['job_fingerprint'],fingerprint(before))
        self.assertEqual(result['planned_audio_frames'],32000); self.assertEqual(result['delivered_audio_frames'],16000)
        self.assertEqual(result['source_audio_seconds'],1.); self.assertEqual(result['retained_events'],6)
        self.assertEqual(result['event_source_seconds_range'],[-.01,1.08]); self.assertEqual(result['event_source_outside_audio_count'],2)
        self.assertFalse(result['delivered_length_independently_joined']); self.assertFalse(result['same_controller_restart_qualified'])
        self.assertFalse(result['accuracy_qualified']); self.assertFalse(result['N4_accepted'])
        freeze(self.folder/'SYNTHETIC_PREFIX_CENSUS.json',result)

    def test_nine_saved_native_journals_are_classified_without_transcript_output(self):
        self.assertEqual(len(CASES),9); results=[]
        for case in CASES:
            for name in ('consumer','finalization'):verify(case[name])
            before=deepcopy(case['audio'])
            original_result=original.inspect(case['session'],job=case['audio'])
            result=subject.inspect(case['session'],job=case['audio'],delivered_frames=case['audio']['frames'],intent='completed_release')
            self.assertEqual(case['audio'],before); self.assertEqual(comparable(result),original_result)
            self.assertEqual(result['status'],'INCOMPLETE_RELEASED_NATIVE_EVENT_JOURNAL')
            self.assertGreater(result['missing_prefix_events'],0); self.assertEqual(result['missing_suffix_events'],0)
            with self.assertRaisesRegex(ValueError,'retained tail'):subject.require_complete(result)
            results.append(dict(cell_id=case['cell_id'],review=result,identical_full_file_classification=True))
        freeze(self.folder/'HISTORICAL_PREFIX_PARITY.json',dict(status='NINE_HISTORICAL_PREFIXES_STILL_UNAVAILABLE',cases=results,
            new_audio_or_model_run=False,actual_restart_qualified=False))

    def test_original_full_file_reader_still_rejects_prefix(self):
        session,events=self.fixture(); self.write(session,events)
        with self.assertRaisesRegex(ValueError,'finalization'):original.inspect(session,job=self.job)
        result=subject.require_complete(self.review(session))
        with self.assertRaises(ValueError):original.require_complete(result)

    def test_explicit_intent_and_length_cannot_relabel_partial_as_full(self):
        session,events=self.fixture(); self.write(session,events)
        for sent,intent in ((16000,'completed_release'),(32000,'mid_file_stop'),(16001,'mid_file_stop'),
                (0,'mid_file_stop'),(-1,'mid_file_stop'),(True,'mid_file_stop'),(16000.,'mid_file_stop'),
                (32001,'completed_release'),(16000,'unknown')):
            with self.subTest(sent=sent,intent=intent),self.assertRaises(ValueError):
                subject.inspect(session,job=self.job,delivered_frames=sent,intent=intent)

    def test_valid_full_file_classification_matches_original(self):
        session,events=self.fixture(); self.write(session,events,split=2)
        self.job['frames']=16000  # This independent synthetic job is full, not a production-job rewrite.
        expected=original.require_complete(original.inspect(session,job=self.job))
        actual=subject.require_complete(subject.inspect(session,job=self.job,delivered_frames=16000,intent='completed_release'))
        self.assertEqual(comparable(actual),expected); self.assertEqual(actual['intent'],'completed_release')
        self.assertEqual(actual['planned_audio_frames'],actual['delivered_audio_frames'])

    def test_declared_delivered_span_must_match_terminal_and_last_cursor(self):
        for name,frames in (('wrong_terminal',16320),('wrong_cursor',16320)):
            session,events=self.fixture(name); self.write(session,events)
            if name=='wrong_cursor':
                path=session/'session_finalization_v3.json'; value=load(path)
                value.update(source_samples=frames,identity_samples=frames); path.write_text(json.dumps(value),encoding='utf-8')
            with self.subTest(name=name),self.assertRaises(ValueError):
                subject.inspect(session,job=self.job,delivered_frames=frames,intent='mid_file_stop')

    def test_new_complete_gate_rejects_tails_and_false_acceptance(self):
        session,events=self.fixture(); self.write(session,events[3:]); result=self.review(session)
        with self.assertRaisesRegex(ValueError,'retained tail'):subject.require_complete(result)
        session,events=self.fixture('full'); self.write(session,events); result=subject.require_complete(self.review(session))
        for key in ('delivered_length_independently_joined','same_controller_restart_qualified','N4_accepted','integrated_N4_cells'):
            changed=deepcopy(result); changed[key]=1 if key=='integrated_N4_cells' else True
            with self.subTest(key=key),self.assertRaises(ValueError):subject.require_complete(changed)

    def test_planned_job_firewall_and_source_identity_remain_required(self):
        session,events=self.fixture(); self.write(session,events)
        for key,value in (('gain',2),('speaker','hidden evaluator label'),('audio_path','X:/foreign.wav')):
            job=deepcopy(self.job); job[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                subject.inspect(session,job=job,delivered_frames=16000,intent='mid_file_stop')

    def test_terminal_count_types_do_not_accept_boolean_or_float(self):
        for number,value in enumerate((True,16000.)):
            session,events=self.fixture(str(number)); self.write(session,events)
            path=session/'session_finalization_v3.json'; final=load(path); final['source_samples']=value
            path.write_text(json.dumps(final),encoding='utf-8')
            with self.subTest(value=value),self.assertRaises(ValueError):self.review(session)
