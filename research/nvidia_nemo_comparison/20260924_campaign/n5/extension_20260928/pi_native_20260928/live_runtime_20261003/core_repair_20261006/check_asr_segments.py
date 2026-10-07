"""Synthetic native-segment contract checks; see README_ASR_SEGMENTS.md."""
import json
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from asr_segment_contract import NativeSegmentContract, boundary_kind, bpe_text, join_raw_parts
from asr_segment_runtime import SegmentLedger, SegmentedAsrMixin, _SherpaSegments, _words, _windows, _map_case_and_punctuation


class FakeSherpa:
    """Synthetic recognizer supplies actual-result tokens, never audio inference."""
    sample_rate = 10
    decode_ms = 0.
    def __init__(self):
        self.utterance_index = 0
        self.stream = object()
        self.text, self.tokens_result, self.endpoint = '', [], False
        self.recognizer = SimpleNamespace(tokens=lambda stream:list(self.tokens_result),
                                         get_result=lambda stream:self.text)
        self.reset_count = 0
        self.punctuation_inputs = []
    def accept(self, audio):
        return self.text,self.endpoint
    def reset_endpoint(self):
        text = self.text
        self.text,self.tokens_result,self.endpoint = '',[],False
        self.utterance_index += 1
        self.reset_count += 1
        return text
    def finish(self):
        return self.text
    def punctuate(self, text):
        self.punctuation_inputs.append(text)
        display = text.lower().capitalize()+'.'
        return dict(text=display,status='synthetic',compute_ms=0.,terminal_fallback=None)


class RuntimeFixture(SegmentedAsrMixin):
    def __init__(self, path):
        self._segment_contract = NativeSegmentContract()
        self._segment_ledger = SegmentLedger(path,policy=SimpleNamespace(reserve=lambda total:0))
        self.events,self.finals,self.jobs = [],[],[]
        self._s6d_punctuation = SimpleNamespace(submit=self.jobs.append)
    def _emit(self, kind, source, payload):
        self.events.append((kind,source,payload))
    def _transcript_event(self, text, source, **fields):
        self.finals.append(dict(text=text,source=source,**fields))
    def _record_punctuation(self, result):
        pass


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.engine = RuntimeFixture(Path(self.directory.name)/'segments.sqlite3')
        self.asr = FakeSherpa()
        self.proxy = _SherpaSegments(self.engine,self.asr)
    def accept(self, text, tokens, samples, endpoint=False):
        self.asr.text,self.asr.tokens_result,self.asr.endpoint = text,tokens,endpoint
        return self.proxy.accept(SimpleNamespace(size=samples))
    def reset(self):
        text = self.proxy.reset_endpoint()
        if text:
            self.engine._publish_final(self.proxy,text,self.proxy.samples/10,
                                       self.asr.utterance_index-1,0.)
    def test_production_facade_preserves_reset_and_defers_timer_punctuation(self):
        self.accept('IN PARTICUL',['▁IN','▁PARTICUL'],203,True)
        self.reset()
        self.assertEqual(self.asr.reset_count,1)
        self.assertEqual(len(self.engine.finals),1)
        self.assertEqual(self.engine.jobs,[])
        row = self.engine.asr_segment_row(dict(utterance_id='utterance:000000'))
        self.assertTrue(row['recognition_segment_final'])
        self.assertFalse(row['utterance_final'])
        self.assertEqual(row['endpoint_kind'],'resource')
        with patch('storage_support.shutil.disk_usage',return_value=SimpleNamespace(total=1000,free=1)):
            blocked = Path(self.directory.name)/'low-space.sqlite3'
            with self.assertRaises(OSError):
                SegmentLedger(blocked)
            self.assertFalse(blocked.exists())
    def test_pause_formats_assembled_word_once_and_maps_exact_native_parents(self):
        self.accept('IN PARTICUL',['▁IN','▁PARTICUL'],203,True)
        self.reset()
        self.accept('AR',['AR'],20,True)
        self.reset()
        self.assertEqual(len(self.engine.jobs),1)
        self.engine._s6d_punctuate(self.engine.jobs[0])
        self.assertEqual(self.asr.punctuation_inputs,['IN PARTICULAR'])
        a,b = (self.engine._segment_ledger.get('utterance:'+str(i).zfill(6)) for i in range(2))
        self.assertEqual(a['raw_text'],'IN PARTICUL')
        self.assertEqual(b['raw_text'],'AR')
        self.assertEqual(a['text']+b['text'],'In particular.')
        revisions = [e for e in self.engine.events if e[0]=='s6d_punctuation_revision']
        self.assertEqual([e[1] for e in revisions],[20.3,22.3])
        self.assertTrue(self.engine.asr_segment_row(dict(utterance_id='utterance:000000'))['spoken_punctuation_ready'])
    def test_real_repeated_word_survives_resource_reset(self):
        self.accept('VERY',['▁VERY'],203,True)
        self.reset()
        self.accept('VERY GOOD',['▁VERY','▁GOOD'],10)
        text = self.proxy.finish()
        self.engine._publish_final(self.proxy,text,21.3,1,0.)
        self.engine._s6d_punctuate(self.engine.jobs[0])
        self.assertEqual(self.asr.punctuation_inputs,['VERY VERY GOOD'])
    def test_empty_pause_closes_previous_resource_piece_without_fake_source_time(self):
        self.accept('WORD',['▁WORD'],203,True)
        self.reset()
        self.accept('',[],24,True)
        self.reset()
        self.assertEqual(len(self.engine.jobs),1)
        row = self.engine._segment_ledger.metadata('utterance:000000')
        self.assertTrue(row['utterance_final'])
        self.assertEqual(row['source_end_sec'],20.3)
        self.assertEqual(row['utterance_boundary_kind'],'native_pause')
        self.assertEqual(self.engine.events[-1][1],22.7)
    def test_duplicate_final_and_group_close_are_idempotent(self):
        self.accept('WORD',['▁WORD'],30,True)
        self.reset()
        self.engine._publish_final(self.proxy,'WORD',3,0,0.)
        self.assertEqual(len(self.engine.finals),1)
        self.assertEqual(len(self.engine.jobs),1)
    def test_giant_word_falls_back_raw_in_bounded_windows(self):
        raw = 'X'*1200
        piece = dict(parent='one',raw=raw,metadata=dict(leading_text_joiner=' '))
        windows = list(_windows(_words(iter([piece]))))
        self.assertEqual(''.join(w['text'] for window in windows for w in window),raw)
        self.assertTrue(all(w['unsafe'] for window in windows for w in window))
        self.assertTrue(all(len(window)==1 and len(window[0]['text'].encode())<=180 for window in windows))
    def test_long_group_is_paged_and_keeps_every_word(self):
        def pieces():
            for index in range(1000):
                yield dict(parent=str(index),raw='WORD '*100,metadata=dict(leading_text_joiner=' '))
        count = 0
        for window in _windows(_words(pieces())):
            self.assertLessEqual(len(window),96)
            self.assertLessEqual(len(' '.join(w['text'] for w in window).encode()),4096)
            count += len(window)
        self.assertEqual(count,100000)
    def test_punctuation_lexical_rewrite_is_rejected(self):
        words = list(_words(iter([dict(parent='one',raw='VERY VERY',metadata=dict(leading_text_joiner=' '))])))
        with self.assertRaises(ValueError):
            _map_case_and_punctuation(words,'Very good.')
        patches = _map_case_and_punctuation(words,'Very very.')
        self.assertEqual([p[3] for p in patches],['Very','very.'])
        number = list(_words(iter([dict(parent='two',raw='3.14',metadata=dict(leading_text_joiner=' '))])))
        self.assertEqual(_map_case_and_punctuation(number,'3.14.')[0][3],'3.14.')
        self.assertEqual(_map_case_and_punctuation(number,'3.14')[0][3],'3.14')
    def test_advisory_endpoint_does_not_masquerade_as_native_rule(self):
        self.accept('WORD',['▁WORD'],203,False)
        self.reset()  # inherited advisor requested reset, native boolean false
        row = self.engine._segment_ledger.metadata('utterance:000000')
        self.assertEqual(row['endpoint_kind'],'advisory')
        self.assertTrue(row['utterance_final'])
        self.accept('WORD',['▁WORD'],1)
        self.assertNotEqual(self.engine._segment_ledger.metadata('utterance:000001')['utterance_group_id'],row['utterance_group_id'])


class BindingTests(unittest.TestCase):
    def test_production_mixin_delegates_verified_loop_through_actual_facade(self):
        installed = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12/vendor/edge_speech_pipeline')
        class Parent:
            def _asr_loop(self, asr):
                self.received_facade = asr
                return 'delegated'
            def _emit(self,*args):
                pass
        Parent._asr_loop.__code__ = Parent._asr_loop.__code__.replace(co_filename=str(installed/'runtime.py'))
        class Engine(SegmentedAsrMixin,Parent):
            def _fail(self,reason):
                raise AssertionError(reason)
        with tempfile.TemporaryDirectory() as directory:
            engine = Engine()
            engine.config = SimpleNamespace(endpoint_rule3_utterance_sec=20.)
            engine._session_dir = Path(directory)
            engine._segment_storage_policy = SimpleNamespace(reserve=lambda total:0)
            with patch('asr_segment_runtime.inspect.getfile',return_value=str(installed/'models.py')):
                self.assertEqual(engine._asr_loop(FakeSherpa()),'delegated')
            self.assertIsInstance(engine.received_facade,_SherpaSegments)
            self.assertIsInstance(engine._s6d_punctuated,SegmentLedger)


class SegmentTests(unittest.TestCase):
    def test_length_boundary_does_not_claim_spoken_finality(self):
        self.assertEqual(boundary_kind(source_start_sec=0, source_end_sec=20.3, native_endpoint=True), 'resource')
        self.assertEqual(boundary_kind(source_start_sec=20.3, source_end_sec=25.4, native_endpoint=True), 'native_pause')
        self.assertEqual(boundary_kind(source_start_sec=0, source_end_sec=60.4, native_endpoint=False, stop=True), 'stop')

    def test_subword_continues_without_spelling_guess(self):
        state = NativeSegmentContract()
        a = state.observe(segment_id='one', raw_text='IN PARTICUL', tokens=['\u2581IN', '\u2581PARTICUL'],
                          source_start_sec=0, source_end_sec=20.3, native_endpoint=True)
        b = state.begin_after_reset(segment_id='two', raw_text='AR', tokens=['AR'],
                                    source_start_sec=20.3, source_end_sec=20.4)
        self.assertFalse(a['utterance_final'])
        self.assertEqual(a['utterance_group_id'], b['utterance_group_id'])
        self.assertEqual(b['leading_text_joiner'], '')
        self.assertEqual(join_raw_parts([dict(a,raw_asr_text='IN PARTICUL'),dict(b,raw_asr_text='AR')]), 'IN PARTICULAR')

    def test_actual_repeated_words_are_kept(self):
        state = NativeSegmentContract()
        a = state.observe(segment_id='one', raw_text='VERY', tokens=['\u2581VERY'],
                          source_start_sec=0, source_end_sec=20.3, native_endpoint=True)
        b = state.begin_after_reset(segment_id='two', raw_text='VERY GOOD', tokens=['\u2581VERY','\u2581GOOD'],
                                    source_start_sec=20.3, source_end_sec=22)
        self.assertEqual(b['leading_text_joiner'], ' ')
        self.assertEqual(join_raw_parts([dict(a,raw_asr_text='VERY'),dict(b,raw_asr_text='VERY GOOD')]), 'VERY VERY GOOD')

    def test_same_segment_revision_replaces_its_suffix(self):
        state = NativeSegmentContract()
        state.observe(segment_id='one', raw_text='PARTICUL', tokens=['\u2581PARTICUL'], source_start_sec=0, source_end_sec=.8)
        final = state.observe(segment_id='one', raw_text='PARTICULAR', tokens=['\u2581PARTICUL','AR'], source_start_sec=0, source_end_sec=1)
        self.assertEqual(final['native_segment_id'], 'one')
        self.assertEqual(bpe_text(['\u2581PARTICUL','AR']), 'PARTICULAR')

    def test_pause_starts_a_separate_group_even_if_next_token_matches(self):
        state = NativeSegmentContract()
        a = state.observe(segment_id='one', raw_text='VERY', tokens=['\u2581VERY'], source_start_sec=0, source_end_sec=5, native_endpoint=True)
        b = state.begin_after_reset(segment_id='two', raw_text='VERY', tokens=['\u2581VERY'], source_start_sec=5, source_end_sec=6)
        self.assertNotEqual(a['utterance_group_id'], b['utterance_group_id'])
        self.assertEqual(b['leading_text_joiner'], ' ')

    def test_empty_reset_result_waits_for_first_token(self):
        state = NativeSegmentContract()
        state.observe(segment_id='one', raw_text='PARTICUL', tokens=['\u2581PARTICUL'], source_start_sec=0, source_end_sec=20.3, native_endpoint=True)
        state.begin_after_reset(segment_id='two', raw_text='', tokens=[], source_start_sec=20.3, source_end_sec=20.4)
        row = state.observe(segment_id='two', raw_text='AR', tokens=['AR'], source_start_sec=20.3, source_end_sec=20.5)
        self.assertEqual(row['leading_text_joiner'], '')

    def test_token_text_mismatch_rejects_contract_inference(self):
        with self.assertRaises(ValueError):
            NativeSegmentContract().observe(segment_id='one',raw_text='DIFFERENT',tokens=['\u2581WORD'],source_start_sec=0,source_end_sec=.1)

    def test_repeated_final_is_idempotent_but_conflict_is_rejected(self):
        state = NativeSegmentContract()
        kwargs = dict(segment_id='one',raw_text='WORD',tokens=['\u2581WORD'],source_start_sec=0,source_end_sec=20.3,native_endpoint=True)
        self.assertEqual(state.observe(**kwargs), state.observe(**kwargs))
        with self.assertRaises(ValueError):
            state.observe(**dict(kwargs,raw_text='OTHER',tokens=['\u2581OTHER']))

    def test_metadata_state_does_not_accumulate_transcript(self):
        state = NativeSegmentContract()
        for index in range(1000):
            kwargs = dict(segment_id=str(index),raw_text='WORD',tokens=['\u2581WORD'],source_start_sec=index*20.3,source_end_sec=(index+1)*20.3,native_endpoint=True)
            state.observe(**kwargs) if index == 0 else state.begin_after_reset(**kwargs)
        self.assertLessEqual(len(state.__dict__), 6)
        self.assertNotIn('raw_text', state.current_contract)
        self.assertNotIn('tokens', state.current_contract)


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(test)
                               for test in (SegmentTests,RuntimeTests,BindingTests))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print(json.dumps(dict(schema='just-peachy.asr-segment-contract-check.v1',tests_run=result.testsRun,
                          passed=result.wasSuccessful(),native_inference_tested=False),sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
