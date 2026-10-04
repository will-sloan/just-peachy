"""Synthetic pinned-route derivation/protocol checks; README_RAW_CAPTURE.md."""
import hashlib
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

import numpy as np
import installed_source as source
from raw_capture import RawSink, admission, derive_factory, derive_stop_base, storage_raw_spec, validate_block, transport_accounting
from storage import SessionStore, StoragePolicy


class FakeLiveSource:
    """Only the exact source-replacement boundaries; no hardware implementation."""
    def __init__(self, config):
        self.config = config
        self._model_samples = self._native_frames = 0
        self._capture_epoch = 1
        self._stream_start_perf_ns = 10
        self._accepted_origin_frame = 0
        self._read_seq = self._write_seq = 0
        self._capacity = 2
        self._frames = np.zeros(2, dtype=np.int32)
        self._native_start = np.zeros(2, dtype=np.int64)
        self._stopped = True
        self._route_ready = False

    def _start_owned(self):
        first = dict(dtype="float32")
        second = dict(dtype="float32")
        self._ring = np.empty((2,480,2),dtype=np.float32)
        if True:
            self._converter = StreamingDecimator()

    def read(self):
        slot = self._read_seq % self._capacity
        n = int(self._frames[slot])
        mono = self._ring[slot, :n, 0 if self.config.tap == "O0" else 1].copy()
        native_start = int(self._native_start[slot])
        self._read_seq += 1
        audio = self._converter.convert(mono)
        block = types.SimpleNamespace(audio=audio, model_start_sample=self._model_samples,
                                      native_start_frame=native_start, native_frames=n)
        self._model_samples += len(audio)
        return block


class RawCaptureTests(unittest.TestCase):
    def setUp(self):
        parent = os.environ.get('LIVE_RAW_TEST_ROOT')
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='raw-capture-test-', dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.factory = Path(os.environ['LIVE_RAW_FACTORY'])
        self.digest = hashlib.sha256(self.factory.read_bytes()).hexdigest()
        self.constructor, self.route, self.proof = derive_factory(self.factory, self.digest)

    def make_source(self, maximum=16000, emit=None):
        sink = RawSink(maximum, emit or (lambda start, raw: dict(kind='ACK_RAW', accepted_samples=start+len(raw)//16)), self.proof)
        live = types.SimpleNamespace(XVFLiveSource=FakeLiveSource)
        cls = self.constructor(FakeLiveSource, live, sink)
        instance = cls(types.SimpleNamespace(tap='O0'))
        instance._start_owned()
        return instance, sink

    @staticmethod
    def packed():
        return np.asarray([[100, -200], [301, -399], [501, -599]], dtype=np.int32)

    def test_exact_pinned_ast_and_hash_rejection(self):
        self.assertTrue(self.proof['unchanged_outside_sink_bounds_and_read_fence'])
        self.assertFalse(self.proof['native_execution'])
        self.assertEqual(len(self.proof['route_ast_sha256']), 64)
        with self.assertRaises(ValueError):
            derive_factory(self.factory, '0'*64)

    def test_packed_slots_markers_and_source_clock_to_durable_spool(self):
        store = SessionStore(self.base/'store', StoragePolicy(reserve_bytes=0, reserve_fraction=0, segment_samples=1))
        self.addCleanup(store.close)
        spec = dict(duration_seconds=1, mode='raw_processed', raw_qualification=True,
            raw=dict(sample_rate=16000, channels=4, sample_width_bytes=4, encoding='PCM_S32LE',
                     qualification=dict(qualified=False, qualification_run=True, evidence='synthetic admission')))
        spool = store.begin(spec)
        def emit(start, raw):
            spool.append_raw(start, raw)
            return dict(kind='ACK_RAW', accepted_samples=spool.raw_samples)
        instance, sink = self.make_source(emit=emit)
        processed = instance._converter.convert(np.tile(self.packed(), (2, 1)))
        self.assertEqual(processed.tolist(), [100/2147483648, 100/2147483648])
        spool.append_processed(0, processed.astype('<f4').tobytes())
        instance._model_samples = 2; instance._native_frames = 6; instance._packed_prefix = 0
        instance._packed_read_transport_frames = 6
        row = instance.raw_capture_finish()
        expected = struct.pack('<iiii', 300, -400, 500, -600)*2
        receipt = spool.raw_receipt()
        self.assertEqual(receipt['sha256'], hashlib.sha256(expected).hexdigest())
        self.assertEqual(receipt['sha256'], row['sha256'])
        self.assertTrue(receipt['complete_source_readback'])
        self.assertFalse(row['complete_source_readback'])
        self.assertEqual(row['sample_rate'], 16000)
        self.assertEqual(row['channels'], 4)
        self.assertEqual(row['model_host_gain_db'], 3.0)
        self.assertFalse(row['identical_acoustic_latency_claim'])
        spool.stop(2)
        self.assertTrue(spool.keep(include_raw=True)['include_raw'])
        self.assertFalse(spool.spec['raw']['qualification']['qualified'])

    def test_exact_final_sample_is_fenced_before_raw_conversion_and_backlog_is_counted(self):
        # Reproduce native trial02: prefix alignment gives159, then499*160=79999.
        # The last slot contributes exactly one chosen sample and195 slots remain.
        digest = hashlib.sha256()
        def emit(start, raw):
            digest.update(raw)
            return dict(kind='ACK_RAW', accepted_samples=start + len(raw)//16)
        instance, sink = self.make_source(maximum=80000, emit=emit)
        instance._capacity = 256
        instance._ring = np.empty((256, 480, 2), dtype=np.int32)
        instance._frames = np.zeros(256, dtype=np.int32)
        instance._native_start = np.zeros(256, dtype=np.int64)
        instance._packed_prefix = 2
        instance._packed_tail_count = 1
        total = 0
        for index in range(501):
            n = 477 if index == 0 else 480
            slot = instance._write_seq % instance._capacity
            instance._ring[slot, :n] = np.tile(self.packed(), (n//3, 1))
            instance._frames[slot] = n
            instance._native_start[slot] = instance._native_frames
            instance._native_frames += n
            instance._write_seq += 1
            block = instance.read()
            self.assertEqual(block.model_start_sample, total)
            self.assertEqual(block.native_start_frame, total*3)
            self.assertEqual(block.native_frames, len(block.audio)*3)
            self.assertTrue(np.all(block.audio == np.float32(100/2147483648)))
            total += len(block.audio)
        self.assertEqual(len(block.audio), 1)
        self.assertEqual(total, 80000)
        for _ in range(195):
            instance._frames[instance._write_seq % instance._capacity] = 480
            instance._write_seq += 1
            instance._native_frames += 480
        row = instance.raw_capture_finish()
        self.assertEqual(sink.accepted_samples, 80000)
        expected = hashlib.sha256()
        sample = struct.pack('<iiii', 300, -400, 500, -600)
        for _ in range(800):
            expected.update(sample*100)
        self.assertEqual(digest.hexdigest(), expected.hexdigest())
        self.assertEqual(row['sha256'], expected.hexdigest())
        self.assertEqual(row['accepted_transport_frames'], 240000)
        self.assertEqual(row['callback_complete_transport_frames'], 334077)
        self.assertEqual(row['final_read_suffix_transport_frames'], 477)
        self.assertEqual(row['unconverted_queued_transport_frames'], 93600)
        self.assertEqual(row['terminal_incomplete_transport_frames'], 1)
        self.assertEqual(row['capture_boundary_reason'], 'allocated_duration')
        self.assertTrue(row['transport_partition_checked'])
        self.assertEqual(instance._converter.samples, 80000)

    def test_transport_partition_refuses_unaccounted_frames_or_pre_stop_receipt(self):
        instance, _ = self.make_source()
        instance._converter.convert(self.packed())
        instance._model_samples = 1
        instance._native_frames = instance._packed_read_transport_frames = 3
        instance._packed_prefix = 0
        self.assertEqual(transport_accounting(instance, 16000)['capture_boundary_reason'], 'explicit_stop')
        instance._native_frames += 3
        with self.assertRaisesRegex(ValueError, 'accounting'):
            transport_accounting(instance, 16000)
        instance._native_frames -= 3
        instance._route_ready = True
        with self.assertRaisesRegex(ValueError, 'physical Stop'):
            transport_accounting(instance, 16000)

    def test_marker_errors_and_allocated_duration_stop_conversion(self):
        instance, _ = self.make_source(maximum=2080001)
        instance._converter.samples = 2080000
        instance._converter.convert(self.packed())
        self.assertEqual(instance._converter.samples, 2080001)
        with self.assertRaisesRegex(ValueError, 'reservation'):
            instance._converter.convert(self.packed())
        other, _ = self.make_source()
        broken = self.packed(); broken[1, 0] &= np.int32(-2)
        with self.assertRaisesRegex(ValueError, 'marker'):
            other._converter.convert(broken)

    def test_normal_qualification_and_experimental_admission_are_distinct(self):
        with self.assertRaises(ValueError):
            admission(dict(raw_adapter_enabled=True))
        experimental = dict(raw_qualification=True, raw_qualification_evidence=dict(
            qualified=False, qualification_run=True, evidence='fresh explicit admission'))
        self.assertFalse(admission(experimental, qualification_run=True)['qualified'])
        with self.assertRaises(ValueError):
            admission(experimental)
        self.assertIsNone(storage_raw_spec(experimental, 'live'))
        normal = dict(raw_adapter_enabled=True, raw_qualification_evidence=dict(
            qualified=True, adapter_native_qualified=True, evidence='passed receipt'))
        with self.assertRaises(ValueError):
            storage_raw_spec(normal, 'live')
        self.assertIsNone(storage_raw_spec(normal, 'saved'))

    def test_exact_pinned_stop_and_actual_start_are_preserved(self):
        references = {}
        for name in ('field_live_stop_overlay_v1.py', 'field_source_receipt_routes_v1.py'):
            references[name] = dict(sha256=hashlib.sha256((self.factory.parent/name).read_bytes()).hexdigest())
        config = dict(raw_factory_path=str(self.factory), raw_factory_sha256=self.digest, reference_files=references)
        base, proof = derive_stop_base(config, types.SimpleNamespace(XVFLiveSource=FakeLiveSource))
        self.assertTrue(hasattr(base, '_stop_owned'))
        self.assertEqual(len(proof['stop_ast_sha256']), 64)
        references['field_live_stop_overlay_v1.py']['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            derive_stop_base(config, types.SimpleNamespace(XVFLiveSource=FakeLiveSource))

    def test_raw_ack_requires_durable_correct_cursor(self):
        sink = RawSink(10, lambda *args: dict(kind='ACK_RAW', accepted_samples=0), {})
        with self.assertRaises(ValueError):
            sink.write(0, bytes(16))
        self.assertEqual(sink.accepted_samples, 0)
        for start, data in ((1, bytes(16)), (0, bytes(15)), (0, bytes(65552))):
            with self.assertRaises(ValueError):
                validate_block(start, data, 0, 10000)

    def test_parent_raw_packet_ack_occurs_after_append(self):
        adapter = source._IsolatedSource.__new__(source._IsolatedSource)
        adapter.config = dict(raw_capture=True)
        adapter.policy = dict(duration_seconds=1)
        adapter.raw_sent = 0
        adapter.raw_digest = hashlib.sha256()
        adapter.stop_event = threading.Event()
        calls = []
        adapter.spool = types.SimpleNamespace(append_raw=lambda start, raw: calls.append(('append', start, raw)))
        adapter._control = lambda value: calls.append(('ack', value))
        adapter._accept_raw(dict(start_sample=0, samples=1), bytes(16))
        self.assertEqual([row[0] for row in calls], ['append', 'ack'])
        self.assertEqual(calls[1][1]['accepted_samples'], 1)
        adapter.spool.append_raw = mock.Mock(side_effect=OSError('spool fault'))
        with self.assertRaises(OSError):
            adapter._accept_raw(dict(start_sample=1, samples=1), bytes(16))
        self.assertEqual(adapter.raw_sent, 1)
        self.assertEqual(len(calls), 2)

    def test_raw_payload_has_64k_bound_without_raising_processed_bound(self):
        wire = bytearray()
        def write(fd, data):
            wire.extend(data)
            return len(data)
        def read(fd, count):
            result = bytes(wire[:count]); del wire[:count]
            return result
        with mock.patch.object(source.select, 'select', side_effect=lambda reads,writes,errors,timeout: (reads,writes,[])), mock.patch.object(source.os, 'write', side_effect=write), mock.patch.object(source.os, 'read', side_effect=read):
            source._send(1, dict(kind='RAW', start_sample=0), bytes(65536))
            metadata, payload = source._receive(1, 1)
            self.assertEqual(metadata['kind'], 'RAW')
            self.assertEqual(len(payload), 65536)
            with self.assertRaises(ValueError):
                source._send(1, dict(kind='AUDIO'), bytes(source.BLOCK_BYTES+1))

    def test_source_only_import_path_is_verified_without_loading_pipeline(self):
        release=self.base/'release';(release/'app').mkdir(parents=True)
        module=release/'app'/'pipeline.py'
        module.write_text("raise RuntimeError('pipeline must not load in source-only qualification')\n")
        import json
        raw=json.dumps(dict(files=[dict(path='app/pipeline.py',sha256=hashlib.sha256(module.read_bytes()).hexdigest())])).encode()
        (release/'RELEASE_MANIFEST.json').write_bytes(raw)
        pin=hashlib.sha256(raw).hexdigest()
        config=dict(installed_release=str(release),installed_manifest_sha256=pin)
        spool=types.SimpleNamespace(spec=dict(raw_qualification=True))
        before=set(sys.modules)
        with mock.patch.object(source,'BASE_MANIFEST',pin), mock.patch.object(source.sys,'platform','linux'), mock.patch.object(source.sys,'path',list(sys.path)), mock.patch.object(source,'_IsolatedSource',return_value='prepared-only') as constructor:
            result=source.create_source(None,config,None,None,None,spool)
            self.assertEqual(result,'prepared-only')
            self.assertEqual(source.sys.path[0],str(release))
            self.assertEqual(set(sys.modules)-before,set())
            constructor.assert_called_once()
            module.write_text('# changed after pin\n')
            with self.assertRaisesRegex(ValueError,'source pin changed'):
                source.prepare_source_imports(config)


if __name__ == '__main__':
    unittest.main()
