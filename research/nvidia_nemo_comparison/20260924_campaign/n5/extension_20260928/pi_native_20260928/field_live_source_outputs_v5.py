"""Operator source composition binding; README_FIELD_OPERATOR_V1.md."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import resource
import shutil
import threading

import field_child_deadline_v1 as deadlines
from field_operator_layout_v1 import specification, validate, finite_json, encoded
from field_run_outputs_v1 import SlotGroup
from field_transport_outputs_v1 import OutputFailure
from field_source_receipt_routes_v1 import ReceiptFailure

DEADLINE = datetime.fromisoformat('2026-10-01T17:42:44+00:00')
PRODUCERS = ('entry','source','transport','transport_child','presentation','worker',
             'gate','stage','archive','native','launcher')
SOURCE_NAMES = set(specification()['groups']['source'])
CHILD_NAMES = {n for n in SOURCE_NAMES if n.startswith('CHILD_')}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bounded_json(path, maximum=65536):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('Bounded real JSON file required')
    with path.open('rb') as stream:
        raw = stream.read(maximum+1)
    if len(raw) > maximum:
        raise ValueError('JSON grew beyond its reserved slot')
    return finite_json(raw)


class Outputs:
    """Attach existing admitted flat sidecar groups; no layout creation here.

    Source/transport adapters use these actual writers. Artifact and host-mirror
    binding remain the responsibility of the complete admitted entry.
    """
    def __init__(self, root, role):
        if role not in ('parent','child','source'):
            raise ValueError('Source writer role')
        self.root = Path(root)
        self.role = role
        self.producer = {'parent':'transport','child':'transport_child','source':'source'}[role]
        self.failures = {}
        self.closures = set()
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.request_stop = self.stop_event.set
        self.groups = {}
        for group in ('source','control','config','trace','failure','closure','telemetry'):
            entries = specification()['groups'][group]
            mapping = {name:(row['maximum_bytes'],row['maximum_write_bytes'],row['mode']=='append')
                       for name,row in entries.items()}
            budget = dict(maximum_bytes=sum(row[0] for row in mapping.values()),
                maximum_file_bytes=max(row[0] for row in mapping.values()),
                maximum_write_bytes=max(row[1] for row in mapping.values()),
                maximum_files=len(mapping),minimum_free_bytes=5*1024**3)
            self.groups[group] = SlotGroup(self.root/group, budget, mapping)
        self.layout()

    def layout(self):
        directories = [self.root]+[self.root/name for name in self.groups]
        for path in directories:
            if path.is_symlink() or not path.is_dir():
                raise ValueError('Existing real admitted output directories required')
            stat = path.stat()
            if max(stat.st_size,stat.st_blocks*512) > 65536:
                raise ValueError('Output directory exceeded its reserved extent')

    def publish(self, producer, kind, raw):
        if producer not in PRODUCERS or kind not in ('raw','failure','closure','telemetry'):
            raise ValueError('Unmapped producer/channel')
        group = {'raw':'failure','failure':'failure','closure':'closure','telemetry':'telemetry'}[kind]
        name = producer+('.bin' if kind=='raw' else '.jsonl' if kind=='telemetry' else '.json')
        self.layout()
        return self.groups[group].write(name,raw,append=kind=='telemetry')

    def fail(self, producer, reason, request_stop, raw=None):
        if producer not in PRODUCERS:
            raise ValueError('Unmapped failure producer')
        with self.lock:
            if producer in self.failures:
                return deepcopy(self.failures[producer])
            row = dict(error=type(reason).__name__+': '+str(reason)[:512],stop_requested=False,
                raw_bytes=None if raw is None else len(raw),
                raw_sha256=None if raw is None else hashlib.sha256(raw).hexdigest(),
                raw_retained=False,receipt_retained=False)
            self.failures[producer] = row
            # Must be nonblocking. Never restore/join/archive-close in this callback.
            try:
                request_stop()
                row['stop_requested'] = True
            except Exception as exc:
                row['stop_error'] = repr(exc)[:256]
            if raw is not None:
                if len(raw) <= 65536:
                    try:
                        self.publish(producer,'raw',raw)
                        row['raw_retained'] = True
                    except Exception as exc:
                        row['raw_retention_error'] = repr(exc)[:256]
                else:
                    row['raw_retention_error'] = 'RAW_EXCEEDS_RESERVED_SLOT'
            try:
                self.publish(producer,'failure',encoded(dict(row,receipt_retained=True)))
                row['receipt_retained'] = True
            except Exception as exc:
                row['receipt_error'] = repr(exc)[:256]
            return deepcopy(row)

    def finish(self, producer, value):
        with self.lock:
            if producer in self.closures:
                raise RuntimeError('Closure already attempted; preserve outcome')
            self.closures.add(producer)
            self.publish(producer,'closure',encoded(value))

    def source(self, name, value):
        allowed = CHILD_NAMES if self.role=='child' else SOURCE_NAMES-CHILD_NAMES
        if name not in allowed:
            raise ValueError('Source name belongs to another producer')
        raw = None
        try:
            raw = encoded(value)
            finite_json(raw)
            self.layout()
            return self.groups['source'].write(name,raw)
        except Exception as exc:
            receipt = self.fail(self.producer,exc,self.request_stop,raw)
            receipt['name'] = name
            error = ReceiptFailure if self.role=='source' else OutputFailure
            raise error(receipt) from exc

    def trace(self, value):
        raw = None
        try:
            raw = encoded(value)+b'\n'
            finite_json(raw)
            self.layout()
            return self.groups['trace'].write('TRACE.jsonl',raw,append=True)
        except Exception as exc:
            receipt = self.fail('transport',exc,self.request_stop,raw)
            receipt['name'] = 'TRACE.jsonl'
            raise OutputFailure(receipt) from exc

    def closure(self, value):
        return self.finish('source',value)


def load(path, expected=None, *, role='parent'):
    path = Path(path)
    if expected is not None and sha(path) != expected:
        raise ValueError('Source configuration changed')
    cfg = bounded_json(path)
    fields = {'schema','capture','quiet_only','output_root','prototype','authority','alsa_config',
              'live_config','case_directory','admission_path','admission_sha256','layout_path',
              'layout_sha256','deadline','source_module','source_factory','backpressure_seconds'}
    if type(cfg) is not dict or set(cfg) != fields or cfg['schema'] != 'just-peachy.live-source.v1':
        raise ValueError('Exact actual-source config required')
    if cfg['capture'] is not True or cfg['quiet_only'] is not True:
        raise ValueError('Only authorized quiet capture is admitted')
    root = Path(cfg['output_root'])
    if not root.is_absolute() or root.is_symlink() or path != root/'config/CONFIG.json':
        raise ValueError('Admitted source root/config identity')
    if Path(cfg['case_directory']) != root/'source' or Path(cfg['live_config']) != root/'data/live_config.json':
        raise ValueError('Fixed source/private configuration paths')
    if Path(cfg['admission_path']) != root/'control/ADMISSION.json' or Path(cfg['layout_path']) != root/'control/LAYOUT.json':
        raise ValueError('Fixed admission/layout paths')
    if sha(cfg['admission_path']) != cfg['admission_sha256'] or sha(cfg['layout_path']) != cfg['layout_sha256']:
        raise ValueError('Admission/layout digest')
    admission = bounded_json(cfg['admission_path'])
    layout = validate(bounded_json(cfg['layout_path']))
    now = datetime.now(timezone.utc)
    expiry = datetime.fromisoformat(admission['expires_utc'])
    if not now < expiry <= DEADLINE or (expiry-now).total_seconds() > 600:
        raise ValueError('Source admission expiry/deadline')
    if admission['capture'] is not True or type(admission['maximum_active_children']) is not int or admission['maximum_active_children'] != 1:
        raise ValueError('One admitted capture child required')
    if admission['scope'] != 'OPERATOR_LIVE_DATA_COMPOSITION' or admission['output_root'] != str(root):
        raise ValueError('Actual integration admission/root required')
    for key in ('target_maximum_bytes','host_maximum_bytes','combined_request_bytes'):
        if type(admission[key]) is not int or admission[key] != layout[key]:
            raise ValueError('Whole selected output reservation missing: '+key)
    if admission['layout_sha256'] != cfg['layout_sha256']:
        raise ValueError('Admission selected another layout')
    pins = {row['path']:row for row in admission['files']}
    if len(pins) != len(admission['files']):
        raise ValueError('Duplicate admitted file identity')
    for name,row in pins.items():
        if set(row) != {'path','bytes','sha256'} or type(row['bytes']) is not int or row['bytes'] <= 0:
            raise ValueError('Exact admitted file row required')
        file = Path(name)
        if file.is_symlink() or not file.is_file() or file.stat().st_size != row['bytes'] or sha(file) != row['sha256']:
            raise ValueError('Admitted source/config file changed')
    prototype = Path(cfg['prototype'])
    if not prototype.is_absolute() or str(prototype) != admission['installed_release']:
        raise ValueError('Installed source release identity')
    required = [cfg['authority'],cfg['alsa_config'],cfg['live_config'],
                str(prototype/'RELEASE_MANIFEST.json'),str(prototype/'app/live_audio.py')]
    required += [str(Path(__file__).parent/name) for name in
        ('field_live_source_outputs_v5.py','field_operator_files_v1.py','field_transfer_files_v2.py','field_transfer_paths_v2.py','field_live_files_v2.py','field_live_paths_v1.py','field_live_source_factory_v5.py',
         'field_live_source_bridge_v5.py','isolated_live_transport_v5.py',
         'isolated_live_facade_v8.py','isolated_pipeline_source_v10.py',
         'field_operator_layout_v1.py','field_transfer_layout_v1.py','field_transfer_v2.py','field_live_layout_v3.py','field_child_deadline_v1.py')]
    for file in required:
        if file not in pins:
            raise ValueError('Required source identity omitted: '+file)
    if (cfg['source_module'],cfg['source_factory']) != ('field_live_source_factory_v5','create'):
        raise ValueError('Only the reviewed actual source factory is admitted')
    if type(cfg['backpressure_seconds']) is not int or cfg['backpressure_seconds'] != 1:
        raise ValueError('Fixed source backpressure bound')
    authority = bounded_json(cfg['authority'])
    if authority['scheduled_quiet_capture_authorized'] is not True or authority['quiet_audio_retention_authorized'] is not True:
        raise ValueError('Quiet source authority missing')
    if cfg['alsa_config'] != str(prototype/'config/alsa_hw_only_v1.conf') or os.environ.get('ALSA_CONFIG_PATH') != cfg['alsa_config']:
        raise ValueError('Process-local ALSA path binding')
    if sorted(os.sched_getaffinity(0)) != [2,3] or resource.getrlimit(resource.RLIMIT_STACK) != (1024**2,)*2:
        raise ValueError('Actual source CPU/stack limits')
    expected_as = (256 if role in ('child','source') else 768)*1024**2
    if resource.getrlimit(resource.RLIMIT_AS) != (expected_as,)*2 or shutil.disk_usage(root).free < 5*1024**3:
        raise ValueError('Actual source address-space/free-space limits')
    value = deadlines.validate(cfg['deadline'],admission)
    if type(admission.get('cleanup_reserve_seconds')) is not int or admission['cleanup_reserve_seconds'] != 60:
        raise ValueError('Explicit sixty-second outer cleanup reserve required')
    if deadlines.remaining(value,hard=True)+60 > (expiry-datetime.now(timezone.utc)).total_seconds():
        raise ValueError('Child lifetime and cleanup exceed admission or hard completion boundary')
    from field_operator_files_v1 import attach
    return cfg,admission,attach(root,admission,Outputs(root,role))
