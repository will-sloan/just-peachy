"""One-run live output specification. Read README_FIELD_LIVE_LAYOUT_V1.md."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import PurePosixPath

KIB = 1024
MIB = KIB*KIB
PRODUCERS = ('entry', 'source', 'transport', 'presentation', 'worker', 'gate',
             'stage', 'archive', 'native', 'launcher')
SOURCE_NAMES = ('PRE_ROUTE_SNAPSHOT.json', 'POST_ROUTE_SNAPSHOT.json',
                'SOURCE_START.json', 'SOURCE_START_FAILURE.json', 'ROUTE_STOP.json',
                'BRIDGE_STOP.json', 'BRIDGE_CLOSE.json', 'CHILD_OWNER.json',
                'CHILD_READY.json', 'CHILD_RESULT.json')
CONTROL_NAMES = ('ADMISSION.json', 'OWNER.json', 'DISPATCH_OWNER.json',
                 'LIVE_ENVELOPE.json', 'REGISTERED_OWNER.json', 'REQUEST.json',
                 'ACK.json', 'MANIFEST.json', 'LAYOUT.json')
RECEIPT_NAMES = ('RESULT.json', 'DISPATCH_RESULT.json', 'APPLICATION_CLOSURE.json',
                 'START_REQUEST.json', 'MODEL_CLOSURE.json', 'GUI_STOP.json',
                 'SAVE_REOPEN.json', 'DEPENDENCY_BINDING.json')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def finite_json(raw):
    def number(token):
        value = float(token)
        if not math.isfinite(value):
            raise ValueError('Nonfinite decoded JSON number')
        return value
    def constant(token):
        raise ValueError('Nonfinite JSON constant: '+token)
    return json.loads(raw.decode('utf-8'), parse_float=number, parse_constant=constant)


def slot(producer, size, write, mode='once', count=1):
    return dict(producer=producer, maximum_bytes=size, maximum_write_bytes=write,
                mode=mode, maximum_files=count)


def specification():
    """Fixed one-process/run, one conversation/epoch/session; no history deletion.

    Values are independent writer maxima, not measured simultaneous usage.
    Replace slots reserve both old and pending copies. Directory reserve is
    counted once; the host mirror includes that reserve conservatively.
    """
    groups = {
        'source': {n: slot('source' if not n.startswith('CHILD_') else 'transport',
                           64*KIB, 64*KIB) for n in SOURCE_NAMES},
        'config': {n: slot('entry', 64*KIB, 64*KIB) for n in
                   ('CONFIG.json', 'live_config.json', 'settings.json', 'DATA_SCHEMA.json',
                    'last_application.json', 'field_contract.json', 'archive_policy.json',
                    'n2_runtime.json')},
        'control': {n: slot('stage' if n in ('ADMISSION.json', 'MANIFEST.json', 'LAYOUT.json')
                            else 'launcher', 64*KIB, 64*KIB) for n in CONTROL_NAMES},
        'receipts': {n: slot('worker', 64*KIB, 64*KIB) for n in RECEIPT_NAMES},
        'trace': {'TRACE.jsonl': slot('transport', 12*MIB, 8*KIB, 'append')},
        'telemetry': {p+'.jsonl': slot(p, 256*KIB, 8*KIB, 'append')
                      for p in ('presentation', 'gate')},
        'logs': {'service.log': slot('gate', MIB, 16*KIB, 'append'),
                 'child.log': slot('launcher', 128*KIB, 16*KIB, 'append')},
        'failure': {}, 'closure': {},
        # Exact flat names must be filled by the reviewed capsule manifest.
        'code': {'<manifest-code>': slot('stage', 2*MIB, 128*KIB, 'manifest', 64)},
    }
    for producer in PRODUCERS:
        groups['failure'][producer+'.bin'] = slot(producer, 64*KIB, 64*KIB)
        groups['failure'][producer+'.json'] = slot(producer, 8*KIB, 8*KIB)
        groups['closure'][producer+'.json'] = slot(producer, 32*KIB, 32*KIB)
    # These use the retained native/archive sinks, not the flat sidecar writer.
    # Artifact paths are bound to fresh concrete identifiers before Start.
    artifacts = {
        'native_events': dict(path='data/sessions/<session>/events.jsonl',
                              **slot('native', 16*MIB, MIB, 'native')),
        'labelled_transcript': dict(path='data/sessions/<session>/labelled_transcript.jsonl',
                                   **slot('native', 2*MIB, 64*KIB, 'append')),
        'readable_transcript': dict(path='data/sessions/<session>/transcript.md',
                                   **slot('native', 2*MIB, 64*KIB, 'append')),
        'latest_transcript': dict(path='data/sessions/<session>/latest_labelled_transcript.jsonl',
                                 **slot('native', 2*MIB, 64*KIB, 'append')),
        'native_clock_trace': dict(path='data/sessions/<session>/s7_clocks.jsonl',
                                  **slot('native', 4*MIB, 64*KIB, 'append')),
        'conversation_events': dict(path='data/conversations/<conversation>/epochs/<epoch>/events.jsonl',
                                    **slot('archive', 16*MIB, MIB, 'native')),
        'float_audio': dict(path='data/conversations/<conversation>/epochs/<epoch>/model_input.f32le',
                           **slot('archive', 4*2080000, 131072, 'native')),
        'pcm_audio': dict(path='data/conversations/<conversation>/epochs/<epoch>/model_input.wav',
                         **slot('archive', 44+2*2080000, 65536, 'native')),
        # windows/resources share this enforced aggregate; each can use it all.
        'archive_auxiliary': dict(paths=['windows.jsonl', 'resources.jsonl'],
                                 **slot('archive', MIB, MIB, 'aggregate', 2)),
        'epoch_control': dict(path='epoch.json', **slot('archive', 2*64*KIB, 64*KIB, 'replace', 2)),
        'conversation_control': dict(path='conversation.json', **slot('archive', 2*64*KIB, 64*KIB, 'replace', 2)),
        'checkpoint_detail': dict(path='checkpoint-detail.json', **slot('archive', 2*256*KIB, 256*KIB, 'replace', 2)),
        'archive_failure': dict(path='failure.txt', **slot('archive', 256*KIB, 256*KIB)),
        # Native pipeline configuration / terminal metadata need a new mapped adapter.
        'native_controls': dict(paths=['session_summary.json', 'session_finalization_v3.json',
                                       's6d_consumer_closure.json'],
                                **slot('native', 6*64*KIB, 64*KIB, 'replace', 6)),
    }
    artifacts['application_lock'] = dict(path='data/runtime.lock', **slot('entry', KIB, KIB))
    directories = ['', *groups, 'data', 'data/people', 'data/sessions', 'data/sessions/<session>',
                   'data/conversations', 'data/conversations/<conversation>',
                   'data/conversations/<conversation>/epochs',
                   'data/conversations/<conversation>/epochs/<epoch>']
    sidecar_bytes = sum(v['maximum_bytes'] for g in groups.values() for v in g.values())
    artifact_bytes = sum(v['maximum_bytes'] for v in artifacts.values())
    directory_bytes = len(directories)*64*KIB
    target = sidecar_bytes+artifact_bytes+directory_bytes
    return dict(schema='just-peachy.live-layout.v1', groups=groups, artifacts=artifacts,
                directories=directories, directory_reserve_bytes=directory_bytes,
                sidecar_maximum_bytes=sidecar_bytes, artifact_maximum_bytes=artifact_bytes,
                target_maximum_bytes=target, host_target_copy_maximum_bytes=target,
                host_metadata_maximum_bytes=4*MIB, host_maximum_bytes=target+4*MIB,
                combined_request_bytes=2*target+4*MIB,
                frame_limit=2080000, planned_stop_samples=1920000,
                minimum_pi_free_bytes=5*1024**3, maximum_runs_per_process=1,
                maximum_epochs=1, maximum_sessions=1, maximum_conversations=1,
                status='SELECTED_LIVE_OUTPUT_MAP_PREPARED_BINDING_GATES_OPEN',
                capture_admitted=False, runtime_accepted=False)


REQUIRED_BINDINGS = (
    'stage_code_control', 'entry_config', 'source_start_stop_restore',
    'transport_owner_terminal', 'trace', 'presentation', 'outer_log_resources',
    'producer_failure_closure', 'archive_pcm_events_aux_controls',
    'native_journal_controls', 'native_text_trace', 'controller_failure_stop', 'field_restrictions',
    'host_streamed_backup', 'one_epoch_one_process')


def reservation(value):
    if type(value) is not dict or encoded(value) != encoded(specification()):
        raise ValueError('Live layout must match exact reviewed maxima and names')
    return value['combined_request_bytes']


def start_gate(value, bindings, admission):
    """No native dispatch until every actual writer binding is pinned.

    A binding registry is a preparation control, never evidence of execution.
    The actual entry must verify each source digest and install each binding.
    """
    reservation(value)
    if type(bindings) is not dict or set(bindings) != set(REQUIRED_BINDINGS):
        raise ValueError('Incomplete live writer binding registry')
    for name, row in bindings.items():
        if type(row) is not dict or set(row) != {'source_sha256', 'installed'}:
            raise ValueError('Binding fields: '+name)
        sha = row['source_sha256']
        if type(sha) is not str or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Binding digest: '+name)
        if row['installed'] is not True:
            raise ValueError('Uninstalled live writer binding: '+name)
    expected = {'layout_sha256': hashlib.sha256(encoded(value)).hexdigest(),
                'target_maximum_bytes': value['target_maximum_bytes'],
                'host_maximum_bytes': value['host_maximum_bytes'],
                'combined_request_bytes': value['combined_request_bytes']}
    if type(admission) is not dict or any(type(admission.get(k)) is not type(v) or admission.get(k) != v
                                         for k, v in expected.items()):
        raise ValueError('Whole layout is not covered by admission')
    return deepcopy(expected)


def lookup(group, name):
    if type(name) is not str or PurePosixPath(name).name != name or name.endswith('.pending'):
        raise ValueError('Exact flat output name required')
    spec = specification()
    if group not in spec['groups'] or name not in spec['groups'][group] or group == 'code':
        raise ValueError('Unmapped live output')
    return deepcopy(spec['groups'][group][name])


def preflight(group, name, raw, current_bytes=0, append=False):
    row = lookup(group, name)
    if type(raw) is not bytes or type(current_bytes) is not int or current_bytes < 0:
        raise ValueError('Exact bytes and nonnegative current count required')
    if type(append) is not bool or append != (row['mode'] == 'append'):
        raise ValueError('Output publication mode mismatch')
    if len(raw) > row['maximum_write_bytes'] or current_bytes+len(raw) > row['maximum_bytes']:
        raise ValueError('Mapped live output slot exhausted')
    if name.endswith('.json'):
        finite_json(raw)
    if name.endswith('.jsonl'):
        if not raw.endswith(b'\n'):
            raise ValueError('Complete JSON lines required')
        for line in raw.splitlines():
            finite_json(line)
    return row
