"""Hardware-free source framing/pin checks; direct-run CPU14 bootstrap."""
import os
import sys


if __name__ != '__main__':
    raise RuntimeError('Run directly to establish CPU14 ownership first')
if os.name == 'nt':
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    process = kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(process, 1 << 14):
        raise ctypes.WinError(ctypes.get_last_error())
    process_times = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
    if not kernel.GetProcessTimes(process, *(ctypes.byref(value) for value in process_times)):
        raise ctypes.WinError(ctypes.get_last_error())
    creation = dict(creation_filetime=process_times[0].value)
else:
    os.sched_setaffinity(0, {14})
    creation = dict(start_ticks=int(open('/proc/self/stat').read().rsplit(')', 1)[1].split()[19]))
import json
import uuid
import time
import psutil
from pathlib import Path
if len(sys.argv) != 5 or sys.argv[1] != '--output-root' or sys.argv[3] != '--mounted-bundle':
    raise SystemExit('Usage: python test_installed_source.py --output-root PRIVATE_ROOT --mounted-bundle COMMON_BUNDLE.json')
root = Path(sys.argv[2]).absolute() / ('installed-source-checks-' + uuid.uuid4().hex)
bundle_path = Path(sys.argv[4])
root.mkdir(parents=True, exist_ok=False)
with (root/'REGISTERED_OWNER.json').open('x', encoding='utf-8') as stream:
    json.dump(dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(),
        create_time=psutil.Process().create_time(), affinity=psutil.Process().cpu_affinity(),
        purpose='SOURCE_PROTOCOL_AND_PIN_CHECKS', cpu=14, affinity_mask=1 << 14,
        registered_unix=time.time(), root=str(root), native_executed=False, **creation), stream)
    stream.flush()
    os.fsync(stream.fileno())
sys.dont_write_bytecode = True
sys.argv = [sys.argv[0]]
print('REGISTERED_OWNER:', root, flush=True)

import base64
import hashlib
import unittest
from unittest.mock import patch
import installed_source as source

bundle = json.loads(bundle_path.read_text(encoding='utf-8'))
bridge_raw = base64.b64decode(bundle['files']['code/field_live_source_bridge_v6.py'])
code_root = root/'reference-code'
code_root.mkdir()
(code_root/'field_live_source_bridge_v6.py').write_bytes(bridge_raw)
reference = dict(reference_code=str(code_root), reference_files={
    'field_live_source_bridge_v6.py': {'sha256':hashlib.sha256(bridge_raw).hexdigest()}})


class Channel:
    def __init__(self):
        self.buffer = bytearray()
        self.reads = 0
        self.stall_after = None
    def write(self, fd, data):
        count = min(len(data), 7)
        self.buffer.extend(data[:count])
        return count
    def read(self, fd, count):
        self.reads += 1
        count = min(count, 3)
        result = bytes(self.buffer[:count])
        del self.buffer[:count]
        return result
    def select(self, reads, writes, errors, timeout):
        if self.stall_after is not None and self.reads >= self.stall_after:
            return [], [], []
        return reads, writes, []


class SourceProtocolTests(unittest.TestCase):
    def test_partial_reads_and_writes_preserve_metadata_and_audio(self):
        channel = Channel()
        with patch.object(source.os, 'write', channel.write), patch.object(source.os, 'read', channel.read), patch.object(source.select, 'select', channel.select):
            source._send(1, dict(kind='AUDIO', sequence=9), b'abcdefgh')
            metadata, audio = source._receive(1, 1)
        self.assertEqual(metadata, dict(kind='AUDIO', sequence=9))
        self.assertEqual(audio, b'abcdefgh')
        self.assertFalse(channel.buffer)

    def test_oversized_packet_rejects_before_any_write(self):
        with patch.object(source.os, 'write') as write:
            with self.assertRaises(ValueError):
                source._send(1, {'kind':'AUDIO'}, b'x'*(source.BLOCK_BYTES+1))
        write.assert_not_called()

    def test_timeout_after_partial_frame_is_terminal_not_retryable_poll(self):
        channel = Channel()
        with patch.object(source.os, 'write', channel.write), patch.object(source.os, 'read', channel.read), patch.object(source.select, 'select', channel.select):
            source._send(1, {'kind':'AUDIO'}, b'abcd')
            channel.stall_after = 1
            with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
                source._receive(1, 1)

    def test_exact_mounted_capsule_roundtrip_and_future_rejection(self):
        module = source._load_mounted(reference)
        delivered = []
        class Sink:
            def receive(self, *values):
                delivered.append(values)
            def invalidate_positions(self):
                raise AssertionError('No generation loss in this case')
        queue = module['BeamQueue']()
        receiver = module['BeamReceiver'](Sink())
        queue.receive('AEC_AZIMUTH_VALUES', [1,2,3,4], 1.0, 1.1)
        packet = queue.drain(1.2)
        self.assertEqual(receiver.accept(packet, 1.2), 1)
        self.assertEqual(len(delivered), 1)
        future = module['BeamQueue']()
        future.receive('AEC_AZIMUTH_VALUES', [1,2,3,4], 2.0, 2.1)
        with self.assertRaises(ValueError):
            module['BeamReceiver'](Sink()).accept(future.drain(2.2), 1.2)

    def test_changed_mounted_source_pin_rejects(self):
        bad = {**reference, 'reference_files':{'field_live_source_bridge_v6.py':{'sha256':'0'*64}}}
        with self.assertRaisesRegex(ValueError, 'pin changed'):
            source._load_mounted(bad)

    def test_manifest_row_list_resolves_exact_mounted_source(self):
        listed = {**reference, 'reference_files':[dict(path='field_live_source_bridge_v6.py',
            sha256=hashlib.sha256(bridge_raw).hexdigest(), bytes=len(bridge_raw))]}
        self.assertIn('BeamReceiver', source._load_mounted(listed))

    def test_runtime_session_policy_constructs_without_capture(self):
        from types import SimpleNamespace
        from profiles import SessionPolicy
        session_directory = root/'policy-adapter'
        (session_directory/'work').mkdir(parents=True)
        spool = SimpleNamespace(directory=session_directory,
            spec=dict(duration_seconds=300, sample_rate=16000, mode='processed'))
        config = dict(reference, installed_release='not-opened',
            installed_manifest_sha256=source.BASE_MANIFEST, consent=True,
            live_config=dict(lease_path=str(Path.home()/'JustPeachy/data/xvf-hardware.lock'),
                endpoint_name='explicit-fixture-only', hostapi='ALSA', evidence_dir=None))
        adapter = source._IsolatedSource(SimpleNamespace(), config, lambda *args: None,
            None, SessionPolicy(), spool)
        self.assertEqual(adapter.policy['duration_seconds'], 300)
        self.assertEqual(adapter.policy['sample_rate'], 16000)
        self.assertIsNone(adapter.process)
        self.assertFalse((session_directory/'work/source').exists())

    def test_unadmitted_raw_claim_is_explicitly_rejected(self):
        config = dict(installed_release='unused', installed_manifest_sha256=source.BASE_MANIFEST,
            live_config={}, owner_directory='unused')
        with self.assertRaisesRegex(ValueError, 'explicit spool/binding admission'):
            source._check_config(config, dict(raw_capture=True, duration_seconds=300, sample_rate=16000))

    def test_protocol_checks_do_not_import_installed_app(self):
        self.assertFalse(any(name == 'app' or name.startswith('app.') for name in sys.modules))


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SourceProtocolTests))
with (root/'RESULT.json').open('x', encoding='utf-8') as stream:
    json.dump(dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        successful=result.wasSuccessful(), native_executed=False, model_executed=False,
        scope='synthetic framing and exact pinned mounted transport only'), stream, indent=2)
with (root/'EXIT.json').open('x', encoding='utf-8') as stream:
    json.dump(dict(pid=os.getpid(), exit_code=0 if result.wasSuccessful() else 1), stream)
raise SystemExit(0 if result.wasSuccessful() else 1)
