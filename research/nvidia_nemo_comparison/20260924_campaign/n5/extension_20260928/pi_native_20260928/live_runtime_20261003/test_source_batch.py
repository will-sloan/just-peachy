"""Changed batching boundaries only; no native models. README_SOURCE_BATCH.md."""
import dataclasses
import hashlib
import os
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest import mock

import numpy as np
import installed_source as isolated
import source_batch as batching
from raw_capture import RawSink, derive_factory
from test_raw_capture import FakeLiveSource


@dataclasses.dataclass
class Block:
    audio: object
    model_start_sample: int
    native_start_frame: int
    native_frames: int
    callback_perf_counter_ns: int


def block(start, count):
    return Block(np.arange(start,start+count,dtype=np.float32),start,start*3,count*3,1000000000+start*62500)


class BatchTests(unittest.TestCase):
    def adapter(self, log, raw=True, append_fault=False):
        adapter=isolated._IsolatedSource.__new__(isolated._IsolatedSource)
        adapter.config=dict(raw_capture=raw,source_batch_ms=100)
        adapter.policy=dict(duration_seconds=5)
        adapter.sent=adapter.raw_sent=0
        adapter.raw_digest=hashlib.sha256()
        adapter.stop_event=threading.Event()
        adapter.spatial_provider=types.SimpleNamespace(advance_audio=lambda item:log.append(('spatial',item.model_start_sample)))
        adapter._beam=types.SimpleNamespace(accept=lambda beam,clock:log.append(('beam',beam['source_sample'],clock)))
        adapter.timing=types.SimpleNamespace(origin=0,accept=lambda item,clock:log.append(('clock',item.model_start_sample)))
        def append(array):
            log.append(('processed',array.copy()))
            if append_fault:raise OSError('injected processed fsync failure')
        adapter.journal=types.SimpleNamespace(append=append,fatal_error=None)
        adapter.spool=types.SimpleNamespace(append_raw=lambda start,payload:log.append(('raw',start,len(payload))))
        adapter._record=lambda kind,row:log.append(('event',kind,row))
        adapter._control=lambda message:log.append(('ack',message))
        return adapter

    def modules(self):
        return mock.patch.dict(sys.modules,{'app.live_audio':types.SimpleNamespace(LiveBlock=Block),
            'app.live_timing':types.SimpleNamespace(CaptureTimeline=object)})

    def test_ten_block_split_final_single_sample_and_raw_ack_precedes_processed(self):
        log=[];adapter=self.adapter(log)
        factory=Path(os.environ['LIVE_RAW_FACTORY'])
        constructor,_,proof=derive_factory(factory,hashlib.sha256(factory.read_bytes()).hexdigest())
        def raw_emit(start,payload):
            adapter._accept_raw(dict(start_sample=start,samples=len(payload)//16),payload)
            return log[-1][1]
        sink=RawSink(80000,raw_emit,proof)
        cls=constructor(FakeLiveSource,types.SimpleNamespace(XVFLiveSource=FakeLiveSource),sink)
        source=cls(types.SimpleNamespace(tap='O0'));source._start_owned()
        emitted=[]
        def read(timeout):
            count=min(159 if source._model_samples==0 else 160,80000-source._model_samples)
            start=source._model_samples
            frames=np.tile(np.asarray([[100,200],[301,401],[501,601]],dtype=np.int32),(count,1))
            audio=source._converter.convert(frames)
            source._model_samples+=count
            return Block(audio,start,start*3,count*3,1000000000+start*62500)
        source.read=read;source.status=lambda:dict(converted_samples=source._model_samples)
        def send(fd,message,audio):
            emitted.append((len(message['blocks']),message['samples'],len(audio)))
            adapter._accept_audio_batch(message,audio)
        progress=dict(sent=0,sequence=0)
        with self.modules(),mock.patch.object(batching.time,'monotonic',return_value=0):
            batching.capture(source,types.SimpleNamespace(drain=lambda clock:dict(source_sample=int((clock-1)*16000))),80000,sink,
                             send,lambda *args:(log[-1][1],b''),lambda:False,progress)
        self.assertEqual(progress,dict(sent=80000,sequence=51))
        self.assertEqual(emitted[0],(10,1599,6396))
        self.assertEqual(emitted[-1],(1,1,4))
        self.assertEqual(adapter.sent,adapter.raw_sent)
        raw_entries=[row for row in log if row[0]=='raw']
        processed=[row for row in log if row[0]=='processed']
        self.assertEqual(len(raw_entries),51)
        self.assertEqual(len(processed),51)
        self.assertEqual(sum(row[2] for row in raw_entries),80000*16)
        self.assertTrue(all(row[2]<=25600 for row in raw_entries))
        self.assertEqual(len([row for row in log if row[0]=='clock']),501)
        self.assertEqual(len([row for row in log if row[0]=='beam']),501)
        self.assertEqual(len([row for row in log if row[0]=='spatial']),501)
        order=[row[1]['kind'] for row in log if row[0]=='ack']
        self.assertEqual(order,['ACK_RAW','ACK_AUDIO']*51)
        self.assertEqual(source._converter.pending,bytearray())
        import struct
        expected_raw=hashlib.sha256()
        for _ in range(800):expected_raw.update(struct.pack('<iiii',300,400,500,600)*100)
        self.assertEqual(adapter.raw_digest.hexdigest(),expected_raw.hexdigest())
        self.assertTrue(all(np.all(row[1]==np.float32(100/2147483648)) for row in processed))

    def test_explicit_stop_flushes_every_already_read_partial_block(self):
        reads=iter([block(0,160),block(160,160),block(320,160)])
        readiness=iter([False,False,False,True])
        sent=[];reply=[]
        source=types.SimpleNamespace(read=lambda timeout:next(reads),status=lambda:{})
        def send(fd,message,audio):
            sent.append((message,bytes(audio)))
            reply.append((dict(kind='ACK_AUDIO',sequence=0,accepted_samples=480),b''))
        progress=dict(sent=0,sequence=0)
        def receive(fd,timeout):
            return reply.pop(0) if reply else (dict(kind='STOP'),b'')
        with mock.patch.object(batching.time,'monotonic',return_value=0):
            batching.capture(source,types.SimpleNamespace(drain=lambda clock:{}),1600,None,send,receive,
                             lambda:next(readiness),progress)
        self.assertEqual(progress,dict(sent=480,sequence=1))
        np.testing.assert_array_equal(np.frombuffer(sent[0][1],dtype='<f4'),np.arange(480,dtype=np.float32))

    def test_ack_failure_never_advances_child_cursor_or_publishes_processed_ack(self):
        batch=batching.Batch(0);batch.add(block(0,160),dict(source_sample=0))
        source=types.SimpleNamespace(status=lambda:{})
        for ack in (dict(kind='ACK_AUDIO',sequence=0,accepted_samples=159),dict(kind='ACK_RAW',accepted_samples=160)):
            with self.assertRaisesRegex(ValueError,'acknowledgement'):
                batching.deliver(batch,0,source,None,lambda *args:None,lambda *args:(ack,b''))
        log=[];adapter=self.adapter(log,raw=False,append_fault=True)
        with self.modules():
            with self.assertRaisesRegex(OSError,'fsync'):
                adapter._accept_audio_batch(batch.message(0,{}),batch.audio)
        self.assertEqual(adapter.sent,0)
        self.assertFalse(any(row[0]=='ack' for row in log))
        source=types.SimpleNamespace(status=lambda:{},_converter=types.SimpleNamespace(
            flush=mock.Mock(side_effect=OSError('injected raw fsync failure'))))
        sent=mock.Mock()
        with self.assertRaisesRegex(OSError,'raw fsync'):
            batching.deliver(batch,0,source,types.SimpleNamespace(accepted_samples=0),sent,lambda *args:None)
        sent.assert_not_called()
        progress=dict(sent=0,sequence=0)
        with mock.patch.object(batching.time,'monotonic',return_value=0):
            with self.assertRaisesRegex(ValueError,'acknowledgement'):
                batching.capture(types.SimpleNamespace(read=lambda timeout:block(0,160),status=lambda:{}),
                    types.SimpleNamespace(drain=lambda clock:{}),160,None,lambda *args:None,
                    lambda *args:(dict(kind='ACK_AUDIO',sequence=0,accepted_samples=159),b''),lambda:False,progress)
        self.assertEqual(progress,dict(sent=0,sequence=0))

    def test_raw_batch_cannot_arrive_twice_or_be_skipped_before_processed_commit(self):
        log=[];adapter=self.adapter(log)
        batch=batching.Batch(0);batch.add(block(0,160),dict(source_sample=0))
        with self.modules():
            with self.assertRaisesRegex(ValueError,'raw must be durable'):
                adapter._accept_audio_batch(batch.message(0,{}),batch.audio)
        adapter._accept_raw(dict(start_sample=0,samples=160),bytes(160*16))
        with self.assertRaisesRegex(ValueError,'one bounded packet'):
            adapter._accept_raw(dict(start_sample=160,samples=160),bytes(160*16))
        self.assertEqual(adapter.raw_sent,160)

    def test_scatter_wire_partial_writes_preserve_batch_and_configuration_is_explicit(self):
        self.assertEqual(batching.batch_milliseconds({}),0)
        for config in (dict(source_batch_ms=True),dict(source_batch_ms=100,live_config=dict(block_frames=160))):
            with self.assertRaises(ValueError):batching.batch_milliseconds(config)
        batch=batching.Batch(0);batch.add(block(0,160),{})
        wire=bytearray()
        def write(fd,value):
            count=min(7,len(value));wire.extend(value[:count]);return count
        def read(fd,count):
            count=min(3,count);result=bytes(wire[:count]);del wire[:count];return result
        with mock.patch.object(isolated.select,'select',side_effect=lambda reads,writes,errors,timeout:(reads,writes,[])),mock.patch.object(isolated.os,'write',side_effect=write),mock.patch.object(isolated.os,'read',side_effect=read):
            isolated._send(1,batch.message(0,{}),batch.audio)
            message,audio=isolated._receive(1,1)
        self.assertEqual(batching.validate_message(message,audio,0),160)
        self.assertEqual(audio,batch.audio)


if __name__=='__main__':unittest.main()
