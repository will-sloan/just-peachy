"""N3 state/trace/firewall tests without neural or hardware calls."""
import ctypes as C
from pathlib import Path
from types import SimpleNamespace
import unittest
import sys
from unittest.mock import patch
import numpy as np

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'vendor')]

from prototype.app.n3_text import TextLayers
from prototype.app.n3_pipeline import StreamingASRLane
from edge_speech_pipeline.n3_asr_native import NativeRecognizer,NativeStream,Options,Config,validate_binding


class NativeProtocolTests(unittest.TestCase):
    def test_recognizer_passes_valid_geometry_for_each_rnnt_context(self):
        def create(config_pointer, handle_pointer):
            stream = config_pointer._obj.streaming.contents
            # This mirrors the real native pre-model validation that rejected
            # all A2/A3 smoke jobs when the ctypes fields defaulted to zero.
            self.assertGreater(stream.chunk_size, 0)
            self.assertGreaterEqual(stream.ctc_left_padding, 0)
            self.assertGreaterEqual(stream.ctc_right_padding, 0)
            self.assertEqual(stream.rnnt_right_context, right)
            return 0
        library = SimpleNamespace(nemo_speech_asr_create=create)
        for right in (0, 1, 6, 13):
            with patch('edge_speech_pipeline.n3_asr_native.validate_binding', return_value=Path(__file__)), \
                 patch('edge_speech_pipeline.n3_asr_native.C.CDLL', return_value=library), \
                 patch.object(NativeRecognizer, '_bind'):
                owner = NativeRecognizer(dict(gpu=-1, model_path='not-loaded.gguf', variant='A2', right_context=right))
                owner.close()

    def test_c_abi_sizes_on_64_bit_host(self):
        self.assertEqual(C.sizeof(C.c_void_p),8)
        self.assertEqual(C.sizeof(Config),80)
        self.assertEqual(C.sizeof(Options),72)
        self.assertEqual(Options().size,C.sizeof(Options))

    def test_native_rejects_a1_before_loading_files(self):
        with self.assertRaisesRegex(ValueError,'separate architecture'):
            validate_binding(dict(schema='just-peachy.n3.native-asr.v1',variant='A1'))

    def test_native_preserves_all_results_and_empty_final(self):
        pending=[('first',False),('first',True),('second',True),('',True)]
        current={}
        def take(handle,pointer):
            if pending:
                current['text'],current['final']=pending.pop(0);pointer._obj.value=1
            return 0
        destroyed=[]
        lib=SimpleNamespace(nemo_speech_asr_stream_next=take,
            nemo_speech_asr_result_transcript=lambda *x:current['text'].encode(),
            nemo_speech_asr_result_audio_processed=lambda *x:.16,
            nemo_speech_asr_result_word_count=lambda *x:0,
            nemo_speech_asr_result_is_final=lambda *x:current['final'],
            nemo_speech_asr_result_destroy=lambda *x:destroyed.append(1))
        stream=object.__new__(NativeStream);stream.owner=SimpleNamespace(lib=lib,check=lambda status:None)
        stream.handle=C.c_void_p(1);stream.input_samples=2560;stream.utterance_index=0
        rows=stream._read()
        self.assertEqual([r['raw_text'] for r in rows],['first','first','second',''])
        self.assertEqual([r['utterance'] for r in rows],[0,0,1,2])
        self.assertEqual(len(destroyed),4)


class LaneTests(unittest.TestCase):
    def test_tail_and_multiple_finals_keep_all_words_and_samples(self):
        published=[];events=[];samples=np.arange(1777,dtype=np.float32)/32768
        class Journal:
            finished=True;committed_samples=len(samples);duration_sec=len(samples)/16000
            def read(self,cursor,count):return samples[cursor:cursor+count]
        class Stream:
            input_samples=0;decode_ms=1.;padding_seconds=0.;closed=False
            def feed(self,x):self.input_samples+=len(x);return []
            def finish_events(self):
                return [dict(raw_text=t,final=True,utterance=i,input_end_sec=len(samples)/16000) for i,t in enumerate(('no missing','tail words'))]
            def close(self):self.closed=True
        lane=StreamingASRLane()
        lane.config=SimpleNamespace(sample_rate=16000,journal_read_ms=100,input_gain=1.,partial_display_min_interval_sec=0.)
        lane._journal=Journal();lane._research_profile=SimpleNamespace(xvf=SimpleNamespace(mode='none'))
        lane._state='RUNNING';lane._started_monotonic=0.;lane._research_asr_available_sec=0.;lane._telemetry={}
        lane._research_v2=False;lane.resident=SimpleNamespace(asr_document={'variant':'A2'})
        lane._emit=lambda kind,at,payload:events.append((kind,payload))
        lane._publish_final=lambda asr,text,at,index,ms:published.append(text)
        lane._fail=lambda message:self.fail(message)
        stream=Stream();lane._asr_loop(stream)
        self.assertEqual(stream.input_samples,1777);self.assertTrue(stream.closed)
        self.assertEqual(published,['no missing','tail words'])
        self.assertEqual(lane._telemetry['n3_input_samples'],1777)


class TextTests(unittest.TestCase):
    def grammar(self):
        layer=TextLayers();layer.grammar=dict(numbers={'one':'1','twenty':'20','twenty one':'21','forty':'40'},
            units={'centimeters':'cm'},standalone_minimum=13);layer.grammar_sha256='fixture-only'
        return layer

    def test_disabled_leaves_words_and_punctuation_untouched(self):
        text='Amir did not use twenty one centimeters.'
        self.assertEqual(self.grammar().transform(text)['text'],text)

    def test_negation_name_and_trace_preserved(self):
        text='Amir did not use twenty one centimeters.'
        result=self.grammar().transform(text,enabled=True)
        self.assertEqual(result['text'],'Amir did not use 21 cm.')
        self.assertEqual(result['original'],text)
        for edit in result['trace']:
            self.assertEqual(text[edit['source_start']:edit['source_end']],edit['original'])
            self.assertEqual(result['text'][edit['output_start']:edit['output_end']],edit['replacement'])

    def test_unsupported_large_number_is_not_partially_rewritten(self):
        text='one hundred twenty one centimeters'
        self.assertEqual(self.grammar().transform(text,enabled=True)['text'],text)

    def test_currency_initialisms_and_unsupported_prefixes_remain_original(self):
        for text in ('twenty one dollars','W D forty','point twenty one'):
            self.assertEqual(self.grammar().transform(text,enabled=True)['text'],text)

    def test_approved_mapping_is_independent_of_missing_itn(self):
        mapping=dict(alias='W D forty',preferred='WD-40',context='lubricant',approved=True)
        result=TextLayers().transform('Use lubricant W D forty',enabled=True,approved_mappings=[mapping])
        self.assertEqual(result['text'],'Use lubricant WD-40')
        self.assertEqual(result['itn_status'],'UNAVAILABLE_ITN_ARTIFACT')

    def test_wd40_requires_explicit_contextual_mapping(self):
        text='Use the lubricant W D forty; do not use water.'
        mapping=dict(alias='W D forty',preferred='WD-40',context='lubricant',approved=True)
        result=self.grammar().transform(text,enabled=True,approved_mappings=[mapping])
        self.assertEqual(result['text'],'Use the lubricant WD-40; do not use water.')
        self.assertEqual(result['trace'][0]['rule'],'explicit_contextual_mapping')

    def test_similar_name_not_replaced_without_approval_or_context(self):
        mapping=dict(alias='Ameer',preferred='Amir',context='colleague',approved=False)
        self.assertEqual(TextLayers().transform('My colleague Ameer',approved_mappings=[mapping])['text'],'My colleague Ameer')
        mapping['approved']=True
        self.assertEqual(TextLayers().transform('Ameer spoke',approved_mappings=[mapping])['text'],'Ameer spoke')


if __name__=='__main__':unittest.main()
