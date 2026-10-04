"""Focused host regression for empty D1 acknowledgements. See README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import os
import json
import uuid
from pathlib import Path

PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
OUTPUT = PRIVATE / ('presets-preparation-empty-activity-check-' + uuid.uuid4().hex)
OUTPUT.mkdir()
with (OUTPUT / 'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(pid=os.getpid(), create_time=psutil.Process().create_time(), affinity=[14]), stream)
    stream.flush(); os.fsync(stream.fileno())

# Project access begins only after the host owner is recorded.
import argparse
import base64
from collections import deque
import hashlib
import importlib.util
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise(subject, label, *, count=100, real_batches=False, corrupt=None):
    """Run the real supervisor loop with injected child/RPC messages, no process."""
    owner = dict(pid=123, parent_pid=os.getpid(), start_ticks=456,
                 boot_id='synthetic-host-contract', affinity=[2, 3])
    raw = b'\0' * (count * 320 * 4)
    total = len(raw) // 4
    frame = 0
    messages = deque([dict(kind='owner', owner=owner),
                      dict(kind='ready', initialization_seconds=.01)])
    for index in range(count):
        messages.append(dict(kind='read', start_sample=index*320,
                             maximum_samples=subject.BLOCK_SAMPLES))
        masks = bytes([1, 2]) if real_batches else b''
        event = dict(kind='activity', frame_start=frame, frame_end=frame+len(masks),
                     received_samples=(index+1)*320,
                     masks=base64.b64encode(masks).decode(), final=False)
        if index == 9 and corrupt:
            event[corrupt] += 1
        messages.append(event)
        frame += len(masks)
    tail = bytes([4]) * (total//160+1-frame)
    messages.extend([
        dict(kind='activity', frame_start=frame, frame_end=total//160+1,
             received_samples=total, masks=base64.b64encode(tail).decode(), final=True),
        dict(kind='closed', owner=owner, delivered_samples=total,
             output_frames=total//160+1, delivered_f32_sha256=hashlib.sha256(raw).hexdigest(),
             complete_eof=True, model_closed=True, failure=None)])

    class FakeChannel:
        def __init__(self, sock): self.sock = sock
        def send(self, value): pass
        def receive(self): return messages.popleft()
        def close(self): self.sock.close()

    class FakeProcess:
        pid = 123
        returncode = None
        def poll(self): return self.returncode
        def wait(self, timeout): self.returncode = 0; return 0

    class Journal:
        max_read_samples = 320
        committed_samples = total
        def __init__(self): self.spool = self
        def snapshot(self): return dict(committed_samples=total, finished=True, fatal_error=None)
        def read_processed(self, start, count): return raw[start*4:(start+count)*4]

    worker = subject.OptionalD1Refiner.__new__(subject.OptionalD1Refiner)
    worker.output = OUTPUT/label; worker.output.mkdir()
    worker.admission = dict(limits=dict(child_as_bytes=768*1024**2, maximum_lag_seconds=30))
    worker.policy = SimpleNamespace(total_deadline_seconds=300, model_load_seconds=120, max_drain_seconds=60)
    worker.unit = 'synthetic.service'; worker.config = {}
    worker.resource_guard = SimpleNamespace(exceeded=lambda: False, last=None)
    worker.journal = Journal(); worker.rpc = subject.JournalRPC(worker.journal, 4800000)
    worker.started = time.monotonic(); worker.stop_event = threading.Event(); worker.lock = threading.Lock()
    worker.ready = worker.done = False
    worker.failure = worker.child_owner = worker.child_result = None
    worker.frames = worker.received = worker.diagnostic_drops = 0
    worker.activity = deque(maxlen=8); worker.messages = deque(maxlen=32)
    with patch.object(subject, 'Channel', FakeChannel), patch.object(subject.subprocess, 'Popen', return_value=FakeProcess()) as spawned:
        worker._run()
    assert spawned.call_count == 1
    assert not spawned.call_args.kwargs['start_new_session']
    assert len(spawned.call_args.kwargs['pass_fds']) == 1
    assert worker.closed_receipt['child_dead']
    assert worker.closed_receipt['primary_audio_dropped'] is False
    return worker, tail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-package', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.base_package))
    old = load(args.base_package/'optional_refiner.py', 'frozen10_optional_handoff')
    revised = load(Path(__file__).with_name('optional_refiner.py'), 'proposed_optional_handoff')
    checks = []
    worker, _ = exercise(old, 'baseline')
    assert worker.failure == 'RuntimeError: Optional activity consumer capacity reached'
    assert (worker.received, worker.frames) == (2880, 0)
    checks.append('Exact frozen10 loop reproduces actual failure at 2880 samples and zero frames')
    worker, tail = exercise(revised, 'warmup')
    assert worker.failure is None and worker.closed_receipt['complete_eof']
    assert worker.received == 32000 and worker.frames == 201
    assert list(worker.activity) == [(0, tail, 32000)]
    assert worker.child_result['delivered_f32_sha256'] == worker.rpc.digest.hexdigest()
    checks.append('100 empty acknowledgements preserve exact source/hash/EOF and all 201 final masks')
    for field in ('frame_start', 'received_samples'):
        worker, _ = exercise(revised, 'invalid-'+field, corrupt=field)
        assert worker.failure == 'RuntimeError: Optional native frame/source delivery mismatch'
        assert worker.closed_receipt['complete_eof'] is False
        checks.append('Malformed empty acknowledgement still rejects '+field)
    worker, _ = exercise(revised, 'real-capacity', count=10, real_batches=True)
    assert worker.failure == 'RuntimeError: Optional activity consumer capacity reached'
    assert len(worker.activity) == 8
    assert b''.join(batch[1] for batch in worker.activity) == bytes([1, 2])*8
    checks.append('Eight real batches retain exact masks; ninth still triggers bounded fallback')
    result = dict(status='HOST_CONTRACT_PASS', native_execution=False, checks=checks,
                  original_sha256=hashlib.sha256((args.base_package/'optional_refiner.py').read_bytes()).hexdigest(),
                  replacement_sha256=hashlib.sha256(Path(__file__).with_name('optional_refiner.py').read_bytes()).hexdigest())
    (OUTPUT/'RESULT.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(OUTPUT), **result), indent=2))


if __name__ == '__main__':
    main()
