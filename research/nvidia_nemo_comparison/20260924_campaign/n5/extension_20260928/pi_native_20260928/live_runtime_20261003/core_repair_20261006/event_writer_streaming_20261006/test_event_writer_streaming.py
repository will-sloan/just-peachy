"""Focused synthetic checks. Run with run_host_event_writer_checks.py; see README."""
import copy
import gc
import hashlib
import importlib.util
import os
from pathlib import Path
import queue
import tempfile
import threading
import time
import tracemalloc
import unittest
from unittest import mock

import event_compaction as candidate
import runtime_support as support

REFERENCE_SHA='4ad7255459b7aadbbee1c1bd498a6f1402e3ba60e83db0386a6a9bf10f28e206'
reference_path=Path(os.environ['JP_EVENT_REFERENCE'])
if support.digest(reference_path)!=REFERENCE_SHA:raise ValueError('Exact frozen31 codec required')
spec=importlib.util.spec_from_file_location('reference_event_compaction',reference_path)
reference=importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
ALLOCATION_RESULT={}


def display(payload=None,**meta):
    return dict(event_type='s6d_display',payload=dict(session_id='synthetic-session',**(payload or {})),**meta)


def structured_display():
    """Synthetic public-field shape: observed 59 spans/45 segments; no real text/IDs."""
    history=dict(label='speaker',speaker_revision=1,identity_event_id='e'*19,
        source_start_sec=1.0,source_end_sec=2.0,publication_monotonic_sec=3.0,
        accepted_identity_snapshot=dict(label='speaker',source_span=[1.0,2.0],evidence_ids=['e'*65]))
    spans=[dict(committed_label='speaker',exact_word_end_sec=None,exact_word_start_sec=None,
        first_seen_monotonic_sec=1.0,first_shown_label='s'*16,first_shown_label_scope='s'*57,
        id='w'*63+('%02d'%number),source_end_sec=float(number+1),source_start_sec=float(number),
        speaker_history=[copy.deepcopy(history)],speaker_revision=1,text='word!',timing_kind='s'*42)
        for number in range(59)]
    none_fields=('application_scope','current_source_permission','historical_eligibility_clock',
        'historical_only','identity_input_event_id','input_available_at_sec','known_name','known_profile_id',
        'legacy_first_times_clock','live_evidence_age_at_policy_ready_sec','live_evidence_age_at_publication_sec',
        'live_evidence_age_sec','live_evidence_fresh','live_evidence_fresh_at_policy_ready',
        'live_evidence_fresh_at_publication','live_evidence_id','live_evidence_source_end_sec',
        'modeled_available_at_sec','observed_first_display_ready_at_sec','observed_first_final_ready_at_sec',
        'observed_first_known_name_ready_at_sec','observed_policy_decision_ready_at_sec',
        'observed_publication_at_sec','policy_decision_finish_monotonic_sec','policy_worker_receipt_monotonic_sec',
        'queue_admission_monotonic_sec','source_epoch_monotonic_sec','source_evidence_expiry_at_sec',
        'source_origin_monotonic_sec')
    segments=[]
    for number in range(45):
        segment=dict.fromkeys(none_fields)
        segment.update(accepted_raw_text='word! '*55,accepted_text_revision_id='r'*12,
            accepted_token_ids=['t'*65],anonymous_label='s'*9,caption_application_scope='s'*34,
            caption_key='c'*57,column='s'*4,committed_label='speaker',display_text='word! ',emphasized=False,
            evidence_ids=['e'*65],first_shown_label='s'*16,identity_event_id='e'*19,
            identity_source_span=[1.0,2.0],identity_target_span=[1.0,2.0],identity_version=[1,1],
            label='speaker',naming_state='pending',ownership_state='s'*17,prototype_closed_group=False,
            publication_monotonic_sec=3.0,raw_character_range=[0,6],raw_text='word! ',segment_id='s'*67,
            session_id='synthetic-session',source_end_sec=float(number+1),source_start_sec=float(number),
            span_ids=['w'*65],speaker_history=[copy.deepcopy(history)],speaker_revision=1,
            support_is_historical_only=False,target_revision_authority='s'*21,text_revision_id='r'*12,
            timing_kind='s'*42,token_ids=['t'*65],token_range=[number,number+1],token_time_alignment='s'*11,
            track_id='t'*56,visible=True,voice_or_direction_permission=True,word_spans=[copy.deepcopy(spans[number])])
        segments.append(segment)
    snapshot=dict(word_spans=copy.deepcopy(spans),segments=copy.deepcopy(segments),label='speaker')
    return display(dict(word_spans=spans,segments=segments,token_ids=['t'*65]*59,
        upstream_token_ids=['t'*65]*59,text='word! '*59,display_text='word! '*59,
        accepted_identity_snapshot=snapshot,first_supported_identity=copy.deepcopy(snapshot),view_revision=1))


class Budget:
    maximum=1
    def __init__(self):self.used=0
    def claim(self,size):self.used+=size
    def unclaim(self,size):self.used-=size


def dormant_sink(*,items=512,queue_bytes=4*1024**2,segment_bytes=8*1024**2):
    sink=support.SegmentedText.__new__(support.SegmentedText)
    sink.lock=threading.RLock();sink.queue=queue.Queue(items);sink.budget=Budget()
    sink.pending=sink.accepted=sink.completed=0;sink.closed=False;sink.error=None
    sink.refusal=None;sink.fail=lambda error:None;sink.maximum=1
    sink.queue_bytes=queue_bytes;sink.segment_bytes=segment_bytes
    return sink


class EventWriterStreamingChecks(unittest.TestCase):
    def compare(self,events):
        old=reference.Codec();new=candidate.Codec();decoder=candidate.Codec()
        rows=[]
        for event in events:
            text=support.encoded(event).decode('utf-8')
            left,old_state=old.prepare(text.encode('utf-8'))
            right,new_state=new.prepare_text(text)
            self.assertEqual(right,left)
            old.commit(old_state);new.commit(new_state)
            self.assertEqual(new.metrics(),old.metrics())
            self.assertEqual(support.encoded(decoder.decode(support.strict(right))),support.encoded(event))
            rows.append(right)
        return rows

    def test_canonical_chunks_and_digest_match_exact_encoder(self):
        value={'unicode':'🙂é漢字'*(candidate.UTF8_CHARS+1),'escape':'\n\t\\"',
               'numbers':[-0.0,0.0,1e-7,1e20,1.7976931348623157e308,2**80],
               'nested':{'z':None,'a':[False,True,{},[]]}}
        raw=support.encoded(value)
        parts=list(candidate._canonical_parts(value))
        self.assertEqual(b''.join(parts),raw)
        self.assertTrue(all(len(part)<=4*candidate.UTF8_CHARS for part in parts))
        size,sha,logical=candidate._canonical_info(value,hashlib.sha256(b'prior\n'))
        self.assertEqual((size,sha),(len(raw),hashlib.sha256(raw).hexdigest()))
        self.assertEqual(logical.hexdigest(),hashlib.sha256(b'prior\n'+raw+b'\n').hexdigest())

    def test_text_bytes_bom_and_whitespace_match(self):
        for text in (' {"z":2,"a":"é🙂"} \n','\ufeff{"a":1}', '{"v":-0.0}'):
            old=reference.Codec();new=candidate.Codec();byte_codec=candidate.Codec()
            expected,state=old.prepare(text.encode('utf-8'));old.commit(state)
            actual,state=new.prepare_text(text);new.commit(state)
            byte_actual,state=byte_codec.prepare(text.encode('utf-8'));byte_codec.commit(state)
            self.assertEqual(actual,expected);self.assertEqual(byte_actual,expected)
            self.assertEqual(new.metrics(),old.metrics());self.assertEqual(byte_codec.metrics(),old.metrics())

    def test_lossless_revisions_sessions_and_complexity_fallback(self):
        payload={'text':'word '*100,'words':[{'word':'a','n':-0.0},{'word':'b'}],
                 'nested':{'retire':True,'keep':[1,2,3]}}
        events=[display(copy.deepcopy(payload))]
        payload['words'][0]['n']=0.0;payload['nested'].pop('retire')
        events.append(display(copy.deepcopy(payload),revision=2))
        payload['words'].append({'word':'é'});payload['nested']['keep']=[1]
        events.extend([display(copy.deepcopy(payload),revision=3),display(copy.deepcopy(payload),revision=3),
                       {'kind':'ordinary','payload':{'observed':True}},
                       dict(event_type='s6d_display',payload=dict(payload,session_id='other-session'))])
        deep_old=deep_new={}
        for _ in range(candidate.MAX_DEPTH+2):deep_old={'child':deep_old};deep_new={'child':deep_new}
        deep_new['extra']='changed'
        events.extend([display({'deep':deep_old}),display({'deep':deep_new}),
                       display({'many':list(range(candidate.MAX_OPS+20))}),
                       display({'many':[-1]*(candidate.MAX_OPS+20)})])
        rows=self.compare(events)
        self.assertTrue(any(support.strict(row)['encoding']=='display_patch' for row in rows))
        self.assertEqual(support.strict(rows[-1])['encoding'],'full')

    def test_patch_is_selected_before_full_wrapper_encoding(self):
        codec=candidate.Codec();event=display({'text':'x'*300000,'revision':1})
        _,state=codec.prepare_text(support.encoded(event).decode());codec.commit(state)
        event['payload']['revision']=2;encodings=[];actual_record=candidate._record
        def record(value):
            encodings.append(value['encoding'])
            if value['encoding']=='full':raise AssertionError('Unselected full wrapper was encoded')
            return actual_record(value)
        with mock.patch.object(candidate,'_record',side_effect=record):
            row,_=codec.prepare_text(support.encoded(event).decode())
        self.assertEqual(encodings,['display_patch']);self.assertEqual(support.strict(row)['encoding'],'display_patch')

    def test_full_fallback_after_larger_patch_matches_exact_bytes(self):
        codec=candidate.Codec();old=reference.Codec()
        for event in (display({'n':1}),display({'n':2})):
            expected,state=old.prepare(support.encoded(event));old.commit(state)
            encodings=[];actual_record=candidate._record
            with mock.patch.object(candidate,'_record',side_effect=lambda row:(encodings.append(row['encoding']),actual_record(row))[1]):
                actual,state=codec.prepare_text(support.encoded(event).decode())
            codec.commit(state);self.assertEqual(actual,expected)
        self.assertEqual(encodings,['display_patch','full'])

    def test_invalid_inputs_leave_staged_state_uncommitted(self):
        codec=candidate.Codec();before=codec.metrics()
        for raw in (b'',b'[]',b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}',
                    b'{"event_type":"s6d_display","payload":{}}',b' '* (candidate.LOGICAL_MAX+1)):
            with self.assertRaises((ValueError,TypeError)):codec.prepare(raw)
            self.assertEqual(codec.metrics(),before)
        for value in ('', '"\ud800"', '🙂'*(candidate.LOGICAL_MAX//4+1)):
            with self.assertRaises((ValueError,UnicodeError)):codec.prepare_text(value)
            self.assertEqual(codec.metrics(),before)
        with self.assertRaises(TypeError):codec.prepare_text(b'{}')
        with self.assertRaises(ValueError):codec.prepare(bytearray(b'{}'))

    def test_exact_wrapper_record_limit_is_retained(self):
        header=len(reference.Codec().prepare(b'{"v":""}')[0])
        raw=support.encoded({'v':'x'*(candidate.LOGICAL_MAX-header)})
        left,_=reference.Codec().prepare(raw);right,_=candidate.Codec().prepare(raw)
        self.assertEqual(len(right),candidate.LOGICAL_MAX);self.assertEqual(right,left)
        for codec in (reference.Codec(),candidate.Codec()):
            with self.assertRaises(ValueError):codec.prepare(support.encoded({'v':'x'*(candidate.LOGICAL_MAX-header+1)}))

    def test_reader_payload_cache_stays_private(self):
        events=[display({'text':'word '*100,'words':['first']}),display({'text':'word '*100,'words':['first','next']})]
        rows=self.compare(events);decoder=candidate.Codec()
        first=decoder.decode(support.strict(rows[0]));first['payload']['words'][0]='consumer annotation'
        self.assertEqual(decoder.decode(support.strict(rows[1])),events[1])

    def test_byte_submit_is_one_immutable_fifo_item(self):
        sink=dormant_sink();raw=b'complete record\n'
        self.assertEqual(sink.write_bytes(raw),len(raw));self.assertIs(sink.queue.get_nowait(),raw)
        self.assertEqual(sink.write('é🙂'),2);self.assertEqual(sink.queue.get_nowait(),'é🙂'.encode())
        self.assertEqual((sink.pending,sink.accepted,sink.budget.used),(len(raw)+6,)*3)
        for value in (bytearray(raw),memoryview(raw),'text'):
            with self.assertRaises(TypeError):sink.write_bytes(value)

    def test_queue_failure_restores_admission_and_preserves_fault(self):
        sink=dormant_sink(items=1);sink.queue.put_nowait(b'occupied')
        with self.assertRaises(queue.Full):sink.write_bytes(b'new')
        self.assertEqual((sink.pending,sink.accepted,sink.budget.used),(0,0,0))
        self.assertIn('item queue exhausted',sink.error)
        with self.assertRaises(RuntimeError):sink.write_bytes(b'retry')
        for sink,raw,boundary in ((dormant_sink(queue_bytes=2),b'abc','pending_queue_bytes'),
                                  (dormant_sink(),b'x'*(candidate.LOGICAL_MAX+1),'logical_record')):
            with self.assertRaises(BufferError):sink.write_bytes(raw)
            self.assertEqual(sink.refusal['boundary'],boundary)
            self.assertEqual((sink.pending,sink.accepted,sink.budget.used),(0,0,0))

    def test_sink_failure_does_not_commit_and_receipts_stay_failed(self):
        with tempfile.TemporaryDirectory(prefix='event-failure-') as folder:
            path=Path(folder)/'events.jsonl'
            writer=candidate.CompactEventText(path,maximum_bytes=1,reserve_bytes=0)
            with mock.patch.object(writer.sink,'write_bytes',side_effect=MemoryError('injected admission')):
                with self.assertRaises(MemoryError):writer.write('{"event_type":"ordinary"}')
            self.assertEqual(writer.codec.sequence,0)
            with self.assertRaises(RuntimeError):writer.close()
            self.assertFalse(writer.thread.is_alive())
            self.assertFalse(support.strict(path.with_name(path.name+'.index.json').read_bytes())['complete'])
            receipt=support.strict(path.with_name(path.name+'.compaction.json').read_bytes())
            self.assertFalse(receipt['complete']);self.assertIn('MemoryError',receipt['error'])

    def test_full_producer_fifo_closure_and_reader_roundtrip(self):
        events=[display({'text':'word '*300,'revision':number,'words':list(range(number))}) for number in range(30)]
        expected=self.compare(events)
        with tempfile.TemporaryDirectory(prefix='event-roundtrip-') as folder:
            path=Path(folder)/'events.jsonl';writer=candidate.CompactEventText(path,maximum_bytes=1,reserve_bytes=0,segment_bytes=4096)
            with mock.patch.object(writer.sink,'write',side_effect=AssertionError('Byte record was decoded and re-encoded')):
                for event in events:
                    text=support.encoded(event).decode();self.assertEqual(writer.write(text),len(text))
            writer.close();self.assertFalse(writer.thread.is_alive())
            actual=b''.join(path.with_name(path.name+'.%06d'%index).read_bytes() for index in range(writer.sink.segment_count))
            self.assertEqual(actual,b''.join(expected))
            self.assertEqual(list(candidate.iter_events(path,maximum_bytes=1024**2,maximum_records=100)),events)
            self.assertEqual((writer.sink.pending,writer.sink.accepted),(0,writer.sink.completed))
            self.assertTrue(support.strict(path.with_name(path.name+'.compaction.json').read_bytes())['complete'])

    def test_uncommitted_prepare_preserves_sequence_and_digest(self):
        codec=candidate.Codec();before=codec.metrics()
        first,state=codec.prepare_text(support.encoded(display({'text':'x'*10000})).decode())
        self.assertEqual(codec.metrics(),before)
        second,retry_state=codec.prepare_text(support.encoded(display({'text':'x'*10000})).decode())
        self.assertEqual(first,second);codec.commit(retry_state)
        self.assertEqual(codec.sequence,1);self.assertEqual(codec.metrics()['logical_bytes'],retry_state.logical_size+1)

    def test_large_repeated_display_has_lower_traced_prepare_peak(self):
        global ALLOCATION_RESULT
        event=display({'text':'x'*300000,'revision':1,'words':[{'text':'word','n':number} for number in range(100)]})
        old=reference.Codec();new=candidate.Codec();text=support.encoded(event).decode()
        _,state=old.prepare(text.encode());old.commit(state)
        _,state=new.prepare_text(text);new.commit(state)
        event['payload']['revision']=2;text=support.encoded(event).decode()
        def peak(call):
            gc.collect();tracemalloc.start()
            try:
                output,state=call();_,maximum=tracemalloc.get_traced_memory()
                return maximum,output
            finally:tracemalloc.stop()
        old_peak,old_output=peak(lambda:old.prepare(text.encode('utf-8')))
        new_peak,new_output=peak(lambda:new.prepare_text(text))
        self.assertEqual(new_output,old_output)
        ALLOCATION_RESULT=dict(reference_peak_bytes=old_peak,draft_peak_bytes=new_peak,
            synthetic_display_bytes=len(text.encode()),selected_record_bytes=len(new_output))
        self.assertLess(new_peak,old_peak*0.9)
        timings=[]
        for name,workload in (('large_text',event),('59_spans_45_segments',structured_display())):
            inputs=[]
            for revision in range(21):
                workload['payload']['view_revision']=revision
                inputs.append(support.encoded(workload).decode())
            def timed(codec,is_new):
                prepare=codec.prepare_text if is_new else lambda value:codec.prepare(value.encode('utf-8'))
                _,state=prepare(inputs[0]);codec.commit(state)
                wall=time.perf_counter();cpu=time.thread_time();rows=[]
                for value in inputs[1:]:
                    output,state=prepare(value);codec.commit(state);rows.append(output)
                return time.perf_counter()-wall,time.thread_time()-cpu,rows,codec.metrics()
            old_wall,old_cpu,left,old_metrics=timed(reference.Codec(),False)
            new_wall,new_cpu,right,new_metrics=timed(candidate.Codec(),True)
            self.assertEqual(right,left);self.assertEqual(new_metrics,old_metrics)
            timings.append(dict(shape=name,events=20,logical_event_bytes=len(inputs[0].encode()),
                reference_wall_seconds=old_wall,draft_wall_seconds=new_wall,
                reference_thread_cpu_seconds=old_cpu,draft_thread_cpu_seconds=new_cpu))
            self.assertLessEqual(new_cpu,old_cpu*1.2+0.005)
        ALLOCATION_RESULT['codec_timing']=timings


if __name__=='__main__':
    raise SystemExit('Use the registered runner; see README_EVENT_WRITER_STREAMING.md')
