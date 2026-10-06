"""Focused legacy-settings and failed-Start check; see README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import types
import uuid

HERE = Path(__file__).resolve().parent
PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
ROOT = PRIVATE/'audit-preparation'/('stabilization-fault-check-'+uuid.uuid4().hex)
ROOT.mkdir()
me = psutil.Process()
def save(name, value):
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    with (ROOT/name).open('xb') as stream:
        assert stream.write(raw) == len(raw)
        stream.flush(); os.fsync(stream.fileno())
save('REGISTERED_OWNER.json', dict(pid=me.pid, create_time=me.create_time(), affinity=[14]))

pins = {}
for name in ('check_stabilization_faults.py', 'application_controller.py', 'application_contract.py', 'installed_source.py', 'README.md'):
    raw = (HERE/name).read_bytes()
    for suffix in ('backup', 'restore'):
        path = ROOT/(name+'.'+suffix)
        path.write_bytes(raw)
        assert path.read_bytes() == raw
    pins[name] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
save('SOURCE_CLOSED.json', dict(files=pins, independent_restore=True))

BASE = PRIVATE/'audit-preparation/full-application-package-e366bb9496184252bc36bd4576fd8c04/package'
sys.dont_write_bytecode = True
sys.path[:0] = [str(HERE), str(BASE)]
from application_controller import controller_type
class Base:
    def _validate_settings(self, values):
        allowed = {'auto_start_listening','caption_size','display_smoothing_ms','microphone_preapproved',
                   'numbered_unknowns','preview_zoom','spatial_visualization','theme'}
        if set(values)-allowed:
            raise ValueError('Unsupported portrait setting')
Controller = controller_type(Base)
controller = object.__new__(Controller)
controller.config = dict(preview_zooms=[1.0])
diagnostic = json.loads((PRIVATE/'operation-stabilization-diagnostics02/dispatch/RESULT.json').read_bytes())
record = next(row for row in diagnostic['action_result']['records'] if row['path'].endswith('/PORTRAIT_SETTINGS.json'))
assert record['sha256'] == '539bc03a17a45bd7150ab819a8aad9d1feae24008999193507daf9148400c61b'
controller._validate_settings(json.loads(record['text']))
rejected = 0
for direction in ('on', True, 0, [], {}):
    try:
        controller._validate_settings(dict(direction=direction))
    except ValueError:
        rejected += 1
    else:
        raise AssertionError('Invalid legacy direction accepted')

tree = ast.parse((HERE/'installed_source.py').read_bytes())
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_raw_terminal')
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), '<actual-raw-terminal-helper>', 'exec'), namespace)
finish = namespace['_raw_terminal']
class Source:
    def __init__(self, *, started=False, samples=0, converter=None):
        self.started, self.samples, self.calls = started, samples, 0
        if converter is not None:
            self._converter = converter
    def status(self):
        return dict(started=self.started, converted_samples=self.samples)
    def raw_capture_finish(self):
        self.calls += 1
        raise ValueError('original nonempty/durable validation retained')
sink = types.SimpleNamespace(accepted_samples=0)
source = Source()
terminal = finish(source, sink, 'actual AEC failure', dict(route=None))
assert terminal['status'] == 'FAILED_BEFORE_CAPTURE' and not terminal['complete_recording'] and source.calls == 0
converter = types.SimpleNamespace(finished=False, samples=0, pending=bytearray(), written=0)
source = Source(converter=converter)
assert finish(source, sink, 'actual AEC failure', dict(route=None)) and converter.finished
for converter in (types.SimpleNamespace(finished=False, samples=1, pending=bytearray(), written=0),
                  types.SimpleNamespace(finished=False, samples=0, pending=bytearray(b'x'), written=0),
                  types.SimpleNamespace(finished=True, samples=0, pending=bytearray(), written=0)):
    try:
        finish(Source(converter=converter), sink, 'fault', dict(route=None))
    except ValueError:
        rejected += 1
    else:
        raise AssertionError('Partial raw data hidden')
for source, accepted, failure, route in ((Source(started=True, samples=1),1,'fault',None),
                                        (Source(),0,None,None),
                                        (Source(),0,'fault',{'verified':True})):
    try:
        finish(source, types.SimpleNamespace(accepted_samples=accepted), failure, dict(route=route))
    except ValueError as error:
        assert str(error) == 'original nonempty/durable validation retained' and source.calls == 1
    else:
        raise AssertionError('Original finish bypassed')
save('RESULT.json', dict(status='PASS', actual_legacy_settings_pin=record['sha256'],
    failed_start_positive_cases=2, rejects=rejected, unchanged_finish_paths=3,
    native_audio_test=False, models_loaded=False))
print(json.dumps(dict(output=str(ROOT), status='PASS', rejects=rejected)))
