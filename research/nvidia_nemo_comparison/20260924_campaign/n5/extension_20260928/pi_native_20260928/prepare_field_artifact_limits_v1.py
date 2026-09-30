"""One-shot immutable-source derivative builder; README_FIELD_ARTIFACT_LIMITS_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
B = Path(r'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928')
BASE = B/'field-sustained-v4-evidence/target/deployment/releases/b01-offline-20260930-v10'
OUT = P/'artifact_limits_v1/app'


def main():
    from field_artifact_limits_v1 import DEFAULT, MIB, digest, planned_bytes
    assert not OUT.exists()
    OUT.mkdir(parents=True)
    sources = {}
    for name in ['bounded_live_artifacts_v1.py', 'app_bounded_artifacts_v1.py', 'sessions.py', 'pipeline.py']:
        raw = (BASE/'app'/name).read_bytes()
        sources[name] = dict(source_sha256=hashlib.sha256(raw).hexdigest(), source_bytes=len(raw))
        code = raw.decode().replace('\r\n', '\n')

        def replace(old, new):
            nonlocal code
            assert code.count(old) == 1, (name, old, code.count(old))
            code = code.replace(old, new)

        if name == 'bounded_live_artifacts_v1.py':
            replace('from collections import OrderedDict', 'from collections import OrderedDict\nfrom field_artifact_limits_v1 import resolved')
            replace('def __init__(self, path, byte_limit, record_limit=1024**2):\n        if type(byte_limit) is not int or not 1024 <= byte_limit <= 8*1024**2:',
                    'def __init__(self, path, byte_limit, record_limit=1024**2, *, artifact_limits=None):\n        limits = resolved(artifact_limits)\n        ceiling = max(limits["native_journal_bytes"], limits["conversation_journal_bytes"])\n        if type(byte_limit) is not int or not 1024 <= byte_limit <= ceiling:')
            replace('def __init__(self, path, max_frames):\n        if type(max_frames) is not int or not 0 < max_frames <= 960000:\n            raise ValueError(\'PCM bound is at most60seconds\')',
                    'def __init__(self, path, max_frames, *, artifact_limits=None):\n        limits = resolved(artifact_limits)\n        if type(max_frames) is not int or not 0 < max_frames <= limits["pcm_max_frames"]:\n            raise ValueError("PCM frame bound exceeds explicit artifact contract")')
        elif name == 'app_bounded_artifacts_v1.py':
            replace('from pathlib import Path', 'from pathlib import Path\nfrom field_artifact_limits_v1 import resolved, digest')
            replace('def __init__(self, path, limit=8*MIB):\n        self.sink = CompactJournal(path, limit)',
                    'def __init__(self, path, limit=None, *, artifact_limits=None):\n        limits = resolved(artifact_limits)\n        limit = limits["conversation_journal_bytes"] if limit is None else limit\n        if type(limit) is not int or not 1024 <= limit <= limits["conversation_journal_bytes"]: raise ValueError("Conversation journal bound exceeds contract")\n        self.sink = CompactJournal(path, limit, artifact_limits=limits)')
            replace('def __init__(self, path, max_frames):', 'def __init__(self, path, max_frames, *, artifact_limits=None):')
            replace("PCM16Writer(Path(path).with_name('model_input.wav'), max_frames)", "PCM16Writer(Path(path).with_name('model_input.wav'), max_frames, artifact_limits=artifact_limits)")
            replace('def __init__(self, path, capacity=512, delay_once=0, sink_factory=None, byte_limit=8*MIB):\n        self.path',
                    'def __init__(self, path, capacity=512, delay_once=0, sink_factory=None, byte_limit=None, *, artifact_limits=None):\n        self.artifact_limits = resolved(artifact_limits)\n        byte_limit = self.artifact_limits["native_journal_bytes"] if byte_limit is None else byte_limit\n        if type(byte_limit) is not int or not 1024 <= byte_limit <= self.artifact_limits["native_journal_bytes"]: raise ValueError("Native journal bound exceeds contract")\n        if type(capacity) is not int or not 1 <= capacity <= 512: raise ValueError("Journal queue item bound invalid")\n        self.path')
            replace('CompactJournal(self.path, self.byte_limit)', 'CompactJournal(self.path, self.byte_limit, artifact_limits=self.artifact_limits)')
            replace('if self.closed: return\n            self.closed = True', 'if self.closed:\n                if self.thread.is_alive(): raise RuntimeError("Event journal closure still pending")\n                if self.error or self.completed != self.accepted: raise RuntimeError("Event journal failed: "+str(self.error))\n                return\n            self.closed = True')
            replace('\n\ndef compact_records(path, allow_partial=False):', '\n\n    def closure_receipt(self):\n        return dict(close_requested=self.closed, worker_alive=self.thread.is_alive(),\n            physical_sink_closed=bool(self.sink is not None and self.sink.closed and self.sink.file.closed),\n            error=self.error, accepted=self.accepted, completed=self.completed,\n            uncompleted=self.accepted-self.completed, pending_bytes=self.pending_bytes,\n            queue_items=self.queue.qsize(), clean=bool(self.closed and not self.thread.is_alive() and\n                not self.error and self.accepted==self.completed),\n            sink=self.sink.metrics() if self.sink is not None else None)\n\n\ndef compact_records(path, allow_partial=False, *, artifact_limits=None):')
            replace("if path.stat().st_size > 8*MIB: raise ValueError('Compact archive exceeds admitted bound')", "limits = resolved(artifact_limits)\n    if path.stat().st_size > max(limits['native_journal_bytes'], limits['conversation_journal_bytes']): raise ValueError('Compact archive exceeds admitted bound')")
            replace("rows, formats, sizes = OrderedDict(), {}, {}\n    for event in compact_records(folder/'events.jsonl', allow_partial=metadata.get('state') != 'CLOSED'):",
                    "limits = resolved(metadata.get('artifact_limits'))\n    if metadata.get('artifact_limits') is not None and digest(limits) != metadata.get('artifact_limits_sha256'): raise ValueError('Archive artifact contract hash mismatch')\n    rows, formats, sizes = OrderedDict(), {}, {}\n    for event in compact_records(folder/'events.jsonl', allow_partial=metadata.get('state') != 'CLOSED', artifact_limits=limits):")
        elif name == 'sessions.py':
            replace('from .paths import atomic_json, read_json, sha256', 'from .paths import atomic_json, read_json, sha256\nfrom field_artifact_limits_v1 import resolved, digest')
            replace('self.path=Path(path);self.path.mkdir(parents=True,exist_ok=False)', 'self.artifact_limits=resolved((policy or {}).get("artifact_limits"))\n        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=False)')
            replace("pcm_max_frames=960000)", "pcm_max_frames=self.artifact_limits['pcm_max_frames'],\n            artifact_limits=self.artifact_limits,artifact_limits_sha256=digest(self.artifact_limits))")
            replace("CompactBinary(self.path/'events.jsonl')", "CompactBinary(self.path/'events.jsonl',artifact_limits=self.artifact_limits)")
            replace("AudioWithPCM(self.path/'model_input.f32le',self.metadata['pcm_max_frames'])", "AudioWithPCM(self.path/'model_input.f32le',self.metadata['pcm_max_frames'],artifact_limits=self.artifact_limits)")
            replace("if self.thread.is_alive():raise TimeoutError('Archive writer still active; do not delete/reopen it')\n        return self.snapshot()", "if self.thread.is_alive():raise TimeoutError('Archive writer still active; do not delete/reopen it')\n        # Publish joined ownership without clearing failed writes or sample/count gaps.\n        self._checkpoint('PARTIAL' if self.error else 'CLOSED')\n        return self.snapshot()")
        else:
            replace('from .app_bounded_artifacts_v1 import ArtifactAsyncText', 'from .app_bounded_artifacts_v1 import ArtifactAsyncText\nfrom field_artifact_limits_v1 import resolved')
            replace("spatial_provider=None,archive=None,seats=None,seat_names=None,enhancement_route='bypass'):", "spatial_provider=None,archive=None,seats=None,seat_names=None,enhancement_route='bypass',artifact_limits=None):")
            replace('self.archive=archive\n        self.mode=', 'archive_limits=getattr(archive,"artifact_limits",None)\n        if artifact_limits is not None and archive_limits is not None and resolved(artifact_limits)!=archive_limits:\n            raise ValueError("Native/archive artifact contract mismatch")\n        self.artifact_limits=resolved(artifact_limits if artifact_limits is not None else archive_limits)\n        self.archive=archive\n        self.mode=')
            replace("writer=(ArtifactAsyncText if Path(path).name=='events.jsonl' else AsyncText)(path,delay_once=self.writer_delay if Path(path).name=='events.jsonl' else 0,sink_factory=CompleteText if Path(path).name=='events.jsonl' else None)",
                    "writer=(ArtifactAsyncText(path,delay_once=self.writer_delay,artifact_limits=self.artifact_limits)\n                if Path(path).name=='events.jsonl' else AsyncText(path,delay_once=0,sink_factory=None))")
        ast.parse(code)
        raw = code.encode()
        with (OUT/name).open('xb') as f: f.write(raw)
        sources[name].update(derivative_sha256=hashlib.sha256(raw).hexdigest(), derivative_bytes=len(raw))
    limits = dict(DEFAULT, native_journal_bytes=16*MIB, conversation_journal_bytes=16*MIB, pcm_max_frames=2080000)
    with (P/'ARTIFACT_LIMITS_V1.json').open('x') as f: json.dump(limits, f, indent=2)
    manifest = dict(schema='artifact-source-derivation.v1', source_release_manifest_sha256=hashlib.sha256((BASE/'RELEASE_MANIFEST.json').read_bytes()).hexdigest(),
                    files=sources, artifact_limits_sha256=digest(limits), planned_artifact_maximum_bytes=planned_bytes(limits),
                    scope='Native writer and actual archive no-capture boundary; pipeline wiring prepared only; no installed entry/GUI/capture acceptance')
    with (P/'ARTIFACT_DERIVATION_V1.json').open('x') as f: json.dump(manifest, f, indent=2)
    print(json.dumps(dict(files=len(sources), planned_artifact_maximum_bytes=planned_bytes(limits))))


if __name__ == '__main__': main()
