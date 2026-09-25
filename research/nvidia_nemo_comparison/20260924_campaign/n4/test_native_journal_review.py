"""Synthetic corruption tests plus a private, read-only historical census."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from common import freeze, load, verify
import review_native_journal as journal

OUTPUT = None
CASES = []


class NativeJournalTests(unittest.TestCase):
    def setUp(self):
        self.folder = OUTPUT/self._testMethodName
        self.folder.mkdir()
        self.job = dict(job_id='synthetic_O0', audio_path=str(self.folder/'never_opened.wav'),
            audio_sha256='1'*64, frames=16000, sample_rate_hz=16000, gain=1., reset_between_scenes=True, tap='O0')

    def fixture(self, name='session'):
        session = self.folder/name; session.mkdir()
        events = []
        for index, kind in enumerate(('session_started','source_started','research_asr_observation',
                                     'transcript_partial','transcript_final','session_completed')):
            payload = dict(publication_sequence=index+1, publication_monotonic_sec=100.+index*.25,
                session_id=name, publication_source_cursor_sec=max(0,index-1)/4)
            if kind == 'source_started':
                payload.update(mode='file', path=self.job['audio_path'], start_sample=0, gain=1.,
                    pacing='absolute', source_epoch_monotonic_sec=100.1)
            events.append(dict(schema_version='edge-speech-event.v1', event_type=kind,
                source_time_sec=payload['publication_source_cursor_sec'], wall_time_utc='2026-09-25T17:00:00+00:00',
                payload=payload, journal_write_monotonic_sec=payload['publication_monotonic_sec']+.02))
        consumer=dict(state='COMPLETED', full_event_consumer_drained=True, monotonic_sec=102., queues=dict(
            journal=dict(accepted=6,completed=6,depth=0,error=None,thread_alive=False,closed=True),
            event_consumer=dict(consumed=5,coalesced_obsolete_ui_partials=1,depth=0)))
        final=dict(schema_version='edge-session-finalization.v3',state='COMPLETED',live_lanes_at_finalization=[],
            finalization_error=None,resident_bundle_lease_retained=False,resident_bundle_reuse_allowed=True,
            event_and_transcript_handles_closed=True,source_samples=16000,identity_samples=16000,
            handle_close_results={k:dict(closed=True,error=None,was_opened=True)
                for k in ('_event_handle','_transcript_handle','_readable_transcript_handle')})
        freeze(session/'s6d_consumer_closure.json',consumer);freeze(session/'session_finalization_v3.json',final)
        return session, events

    def write(self, session, events, *, split=None):
        def save(path, values):
            path.write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in values),encoding='utf-8',newline='\n')
        if split: save(session/'events.jsonl.1',events[:split]);events=events[split:]
        save(session/'events.jsonl',events)

    def review(self, session, **kwargs):
        return journal.inspect(session,job=self.job,**kwargs)

    def test_complete_rotated_journal_preserves_scope_and_source_overhang(self):
        session,events=self.fixture();events[2]['source_time_sec']=-.01;events[4]['source_time_sec']=1.08
        self.write(session,events,split=3);result=journal.require_complete(self.review(session))
        self.assertEqual(result['retained_events'],6);self.assertEqual(result['event_source_seconds_range'],[-.01,1.08])
        self.assertEqual(result['event_source_outside_audio_count'],2)
        self.assertEqual(result['missing_prefix_events'],0)
        self.assertFalse(result['native_payload_semantics_reviewed']);self.assertFalse(result['N4_accepted'])
        freeze(self.folder/'SYNTHETIC_COMPLETE_ENVELOPE.json',result)

    def test_discarded_prefix_is_incomplete_even_with_exact_terminal_census(self):
        session,events=self.fixture();self.write(session,events[3:]);result=self.review(session)
        self.assertEqual(result['missing_prefix_events'],3);self.assertEqual(result['missing_suffix_events'],0)
        self.assertIn('SOURCE_START_UNAVAILABLE',result['reasons'])
        with self.assertRaisesRegex(ValueError,'retained tail'):journal.require_complete(result)

    def test_missing_suffix_and_missing_start_are_not_complete(self):
        for index in range(2):
            session,events=self.fixture(str(index))
            if index==0:events=events[:-1]
            else:events[1]['event_type']='other_event'
            self.write(session,events);result=self.review(session)
            self.assertFalse(result['complete_envelope'])
            with self.assertRaises(ValueError):journal.require_complete(result)

    def test_sequence_duplicates_gaps_reversal_and_boolean_are_rejected(self):
        for name,change in (
            ('duplicate',lambda e:e[3]['payload'].update(publication_sequence=3)),
            ('gap',lambda e:e.pop(3)),
            ('reverse',lambda e:e.reverse()),
            ('boolean',lambda e:e[0]['payload'].update(publication_sequence=True))):
            session,events=self.fixture(name);change(events);self.write(session,events)
            with self.subTest(name=name),self.assertRaises(ValueError):self.review(session)

    def test_wrong_session_clock_cursor_and_wall_timezone_are_rejected(self):
        changes=[('foreign',lambda e:e[3]['payload'].update(session_id='different_session')),
            ('write_early',lambda e:e[3].update(journal_write_monotonic_sec=90)),
            ('publication_back',lambda e:e[3]['payload'].update(publication_monotonic_sec=100.1)),
            ('negative_cursor',lambda e:e[0]['payload'].update(publication_source_cursor_sec=-.1)),
            ('cursor_overrun',lambda e:e[3]['payload'].update(publication_source_cursor_sec=1.1)),
            ('cursor_back',lambda e:e[3]['payload'].update(publication_source_cursor_sec=0)),
            ('wall',lambda e:e[3].update(wall_time_utc='2026-09-25T17:00:00'))]
        for name,change in changes:
            session,events=self.fixture(name);change(events);self.write(session,events)
            with self.subTest(name=name),self.assertRaises(ValueError):self.review(session)

    def test_source_start_mismatch_and_duplicate_completion_are_rejected(self):
        changes=[dict(mode='live'),dict(path='C:/foreign.wav'),dict(start_sample=320),dict(gain=2.),
            dict(pacing='relative'),dict(source_epoch_monotonic_sec=200)]
        for index,change in enumerate(changes):
            session,events=self.fixture(str(index));events[1]['payload'].update(change);self.write(session,events)
            with self.subTest(change=change),self.assertRaises(ValueError):self.review(session)
        session,events=self.fixture('completion');events[4]['event_type']='session_completed';self.write(session,events)
        with self.assertRaises(ValueError):self.review(session)

    def test_terminal_queue_or_source_failure_is_rejected(self):
        for name in ('journal','inbox','source','handle'):
            session,events=self.fixture(name);self.write(session,events)
            path=session/('s6d_consumer_closure.json' if name in ('journal','inbox') else 'session_finalization_v3.json')
            value=load(path)
            if name=='journal':value['queues']['journal']['completed']=5
            elif name=='inbox':value['queues']['event_consumer']['consumed']=6
            elif name=='source':value['source_samples']=15999
            else:value['handle_close_results']['_event_handle']['closed']=False
            path.write_text(json.dumps(value),encoding='utf-8')
            with self.subTest(name=name),self.assertRaises(ValueError):self.review(session)

    def test_duplicate_keys_nonfinite_nested_overflow_and_partial_lines_are_rejected(self):
        for name in ('duplicate','nan','overflow','partial'):
            session,events=self.fixture(name);self.write(session,events);path=session/'events.jsonl'
            text=path.read_text(encoding='utf-8')
            if name=='duplicate':text=text.replace('"publication_sequence": 1','"publication_sequence": 1, "publication_sequence": 1',1)
            elif name=='nan':text=text.replace('"payload": {','"payload": {"nested": [NaN],',1)
            elif name=='overflow':text=text.replace('"payload": {','"payload": {"nested": [1e999],',1)
            else:text=text[:-1]
            path.write_text(text,encoding='utf-8')
            with self.subTest(name=name),self.assertRaises(ValueError):self.review(session)

    def test_rotations_must_be_contiguous_and_unambiguous(self):
        for name in ('missing','ambiguous','directory'):
            session,events=self.fixture(name);self.write(session,events)
            if name=='missing':(session/'events.jsonl.2').write_text('{}\n',encoding='utf-8')
            elif name=='ambiguous':(session/'events.jsonl.01').write_text('{}\n',encoding='utf-8')
            else:(session/'events.jsonl.1').mkdir()
            with self.subTest(name=name),self.assertRaises(ValueError):self.review(session)

    def test_byte_record_line_and_segment_limits_are_enforced(self):
        for name,limit in (('MAX_BYTES',10),('MAX_LINE',20),('MAX_RECORDS',3),('MAX_SEGMENTS',1)):
            session,events=self.fixture(name);self.write(session,events,split=3)
            with self.subTest(name=name),patch.object(journal,name,limit),self.assertRaises(ValueError):self.review(session)

    def test_mutation_during_review_is_rejected(self):
        session,events=self.fixture();self.write(session,events,split=3);calls=[]
        def mutate():
            calls.append(True)
            if len(calls)==2:
                with (session/'events.jsonl.1').open('ab') as stream:stream.write(b'{}\n')
        with self.assertRaises(ValueError):self.review(session,checkpoint=mutate)

    def test_nine_saved_native_journals_are_classified_without_transcript_output(self):
        self.assertEqual(len(CASES),9);results=[]
        for case in CASES:
            for name in ('consumer','finalization'):verify(case[name])
            result=journal.inspect(case['session'],job=case['audio'])
            self.assertEqual(result['status'],'INCOMPLETE_NATIVE_EVENT_JOURNAL')
            self.assertGreater(result['missing_prefix_events'],0)
            self.assertEqual(result['missing_suffix_events'],0)
            self.assertEqual(result['last_sequence'],result['expected_events'])
            self.assertIsNone(result['source_start'])
            with self.assertRaises(ValueError):journal.require_complete(result)
            results.append(dict(cell_id=case['cell_id'],review=result))
        freeze(self.folder/'HISTORICAL_JOURNAL_CENSUS.json',dict(
            status='NINE_HISTORICAL_PREFIXES_UNAVAILABLE',cases=results,new_audio_or_model_run=False,
            interpretation='Does not change narrower accepted N3 terminal/GUI evidence; cannot supply complete native N4 event histories'))
