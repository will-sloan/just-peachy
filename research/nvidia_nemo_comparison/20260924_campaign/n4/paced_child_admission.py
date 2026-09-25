"""Child-side ownership and renewable permit gate. README_PACED_CHILD_ADMISSION.md."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import time

import psutil
from common import audio_only, fingerprint, load, verify
from metric_process import exact_process, identity
from paced_panel_plan import EXECUTION_POLICY
from paced_slot import key, observe_owner, validate_policy, validate_supervision

SCHEMA = 'n4-application-child-permit-v1'
LEASE_SCHEMA = 'n4-application-child-lease-v1'
MAX_PERMIT_BYTES = 256*1024
MAX_LEASE_BYTES = 4096
MAX_LEASE_AGE_SECONDS = 5
INPUT_FIELDS = {'schema', 'cell_id', 'job', 'contract', 'execution', 'source_receipt', 'catalog',
    'runtimes', 'gallery_preparation', 'models_root', 'assets', 'source_execution_authorized', 'remaining_gate'}
PERMIT_FIELDS = {'schema', 'status', 'nonce', 'coordinator', 'application', 'supervisor', 'supervised_run',
    'coordinator_argv_sha256', 'application_argv_sha256', 'desktop', 'plan_sha256', 'input', 'output', 'state', 'code'}
LEASE_FIELDS = {'schema', 'status', 'nonce', 'permit_sha256', 'coordinator', 'application',
    'supervised_run', 'sequence', 'issued_monotonic'}


def require(condition, message):
    if not condition: raise ValueError(message)


def digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def bounded_json(path, maximum):
    # Bound the actual bytes read, including a file that grows between stat/read.
    with Path(path).open('rb') as stream: data = stream.read(maximum+1)
    require(len(data) <= maximum, 'Admission record exceeds byte bound')
    return json.loads(data.decode('utf-8-sig'))


def validate_input(value):
    require(set(value) == INPUT_FIELDS and value['schema'] == 'n4-paced-cell-input-v1', 'Child input allowlist differs')
    require(value['execution'] == EXECUTION_POLICY and value['source_execution_authorized'] is False,
        'Child input is preparation only; exact separate permit is required')
    audio_only(value['job'])
    require(isinstance(value['cell_id'], str) and re.fullmatch('[A-Za-z0-9_]{1,160}', value['cell_id']), 'Invalid cell identity')
    require(isinstance(value['assets'], list) and 0 < len(value['assets']) <= 256, 'Bounded actual model asset bindings required')
    require(isinstance(value['runtimes'], list) and len(value['runtimes']) == 2 and
        {Path(b['path']).name for b in value['runtimes']} == {'n2_runtime.json', 'n3_runtime.json'}, 'Both runtime metadata files required')
    require(type(value['contract']) is dict and value['contract'].get('mode') == 'open_with_names', 'Primary panel mode differs')
    return value


def validate_permit(value, *, nonce, application, parent, desktop):
    """Pure schema/identity checks; passing this function alone authorizes nothing."""
    require(set(value) == PERMIT_FIELDS and value['schema'] == SCHEMA and
        value['status'] == 'ADMITTED_SINGLE_APPLICATION_CHILD', 'Exact application permit required')
    require(digest(nonce) and value['nonce'] == nonce, 'Launch nonce differs')
    for field in ('application', 'coordinator', 'supervisor'): key(value[field])
    require(value['application'] == application and value['coordinator'] == parent, 'Permit process identity differs or PID reused')
    require(len({key(value[name]) for name in ('application', 'coordinator', 'supervisor')}) == 3, 'Ownership roles must be distinct')
    require(value['desktop'] == desktop and re.fullmatch('codex-n1-n4-[0-9a-f]{32}', desktop), 'Exact private desktop differs')
    require(isinstance(value['supervised_run'], str) and 1 <= len(value['supervised_run']) <= 128, 'Supervised run missing')
    for name in ('plan_sha256', 'coordinator_argv_sha256', 'application_argv_sha256'): require(digest(value[name]), 'Binding digest invalid')
    require(isinstance(value['code'], list) and 1 <= len(value['code']) <= 128, 'Bounded fixed worker code required')


def validate_lease(value, permit, permit_sha256, *, now_monotonic, previous_sequence):
    require(set(value) == LEASE_FIELDS and value['schema'] == LEASE_SCHEMA and value['status'] == 'ADMITTED', 'Missing or revoked application lease')
    for name in ('nonce', 'coordinator', 'application', 'supervised_run'):
        require(value[name] == permit[name], 'Lease ownership/nonce/run differs')
    require(value['permit_sha256'] == permit_sha256 and digest(permit_sha256), 'Lease does not bind this immutable permit')
    require(type(value['sequence']) is int and value['sequence'] >= previous_sequence and value['sequence'] >= 0, 'Lease sequence rolled back')
    issued = value['issued_monotonic']
    require(type(issued) in (float, int) and math.isfinite(issued) and math.isfinite(now_monotonic)
        and 0 <= now_monotonic-issued <= MAX_LEASE_AGE_SECONDS, 'Parent lease is future-dated or expired')
    return value['sequence']


def write_lease(path, permit, permit_sha256, sequence):
    """Parent-only renewal after its successful live slot.check(); no ledger mutation.

    A future coordinator must bind/validate the production plan before issuing
    the immutable permit. This API cannot establish that prerequisite itself.
    """
    process = psutil.Process()
    require(identity(process) == permit['coordinator'] and process.cpu_affinity() == [14], 'Only exact CPU14 coordinator may renew')
    require(digest(permit_sha256) and permit_sha256 == fingerprint(permit) and type(sequence) is int and sequence >= 0,
        'Invalid lease identity/sequence')
    path = Path(path)
    require(path.name == 'LEASE.json' and path.parent == Path(permit['output']).parent/'transport', 'Lease escaped owned transport directory')
    if path.exists():
        previous = bounded_json(path, MAX_LEASE_BYTES)
        require(previous.get('permit_sha256') == permit_sha256 and previous.get('status') == 'ADMITTED' and
            type(previous.get('sequence')) is int and sequence > previous['sequence'], 'Renewal must advance this same admitted permit')
    value = dict(schema=LEASE_SCHEMA, status='ADMITTED', nonce=permit['nonce'], permit_sha256=permit_sha256,
        coordinator=permit['coordinator'], application=permit['application'], supervised_run=permit['supervised_run'],
        sequence=sequence, issued_monotonic=time.monotonic())
    temporary = path.with_name('LEASE.pending')
    with temporary.open('x', encoding='utf-8') as stream: json.dump(value, stream, allow_nan=False)
    os.replace(temporary, path)
    return value


def assert_plain_path(path, root):
    path = Path(os.path.abspath(path)); root = Path(root).resolve()
    require(path.is_relative_to(root), 'Child evidence escaped private campaign root')
    for current in (path, *path.parents):
        if current.exists():
            require(not current.is_symlink() and not getattr(current.lstat(), 'st_file_attributes', 0) & 1024, 'Reparse evidence path rejected')
        if current == root: break
    require(path.resolve().is_relative_to(root), 'Resolved evidence path escaped private root')
    return path.resolve()


class ChildAdmission:
    """Pre-model check and cheap repeat checks; no model/UI/source construction.

    The actual fixed worker must pass its observed private desktop, not a user
    supplied desktop label, and call prime() before importing application code.
    """
    def __init__(self, permit_path, *, nonce, desktop, expected_code):
        self.process = psutil.Process(); self.application = identity(self.process)
        self.permit_path = Path(permit_path).resolve(strict=True)
        self.permit = bounded_json(self.permit_path, MAX_PERMIT_BYTES)
        parent = self.process.parent(); require(parent is not None, 'Exact application parent missing')
        validate_permit(self.permit, nonce=nonce, application=self.application, parent=identity(parent), desktop=desktop)
        require(self.process.cpu_affinity() == [4], 'Application must already be pinned to CPU4')
        self.local = Path('G:/Just_Peachy_N1/20260924_campaign/local').resolve()
        self.state = self.local/'supervision'
        require(Path(self.permit['state']).resolve() == self.state, 'Campaign supervision differs')
        self.output = assert_plain_path(self.permit['output'], self.local/'n4')
        self.transport = self.output.parent/'transport'
        require(self.output.name == 'application' and self.permit_path == self.transport/'PERMIT.json', 'Fixed child evidence layout required')
        assert_plain_path(self.transport, self.local/'n4')
        require(not self.output.exists(), 'Application output is not fresh')
        require(self.permit['code'] == expected_code, 'Fixed worker dependency set differs')
        for binding in expected_code: verify(binding)
        self.permit_sha256 = fingerprint(self.permit)
        self.sequence = -1; self.primed = False
        require(Path(self.permit['input']['path']).resolve() == self.transport/'INPUT.json', 'Child input escaped transport')
        verify(self.permit['input'])
        self.payload = validate_input(bounded_json(self.permit['input']['path'], MAX_PERMIT_BYTES))
        self.check()

    def check(self, job=None, contract=None):
        require(bounded_json(self.permit_path, MAX_PERMIT_BYTES) == self.permit, 'Immutable permit changed')
        require(not (self.transport/'CANCEL').exists(), 'Application cancelled by its owner')
        if job is not None: require(job == self.payload['job'] and contract == self.payload['contract'], 'Source job/contract changed')
        record = load(self.state/'worker.json')
        observations = {p['pid']: observe_owner(p) for p in (self.permit['supervisor'], self.permit['coordinator'], self.application)}
        observed_supervisor = validate_supervision(record, self.permit['coordinator'], observations, time.time())
        require(observed_supervisor == self.permit['supervisor'] and record['run_id'] == self.permit['supervised_run'], 'Supervisor owner/run changed')
        require(observations[self.application['pid']]['affinity'] == [4] and
            observations[self.application['pid']]['parent_pid'] == self.permit['coordinator']['pid'], 'Application ownership/CPU changed')
        for role in ('application', 'coordinator'):
            process = exact_process(self.permit[role]); require(process is not None, 'Exact process exited')
            require(fingerprint(process.cmdline()) == self.permit[role+'_argv_sha256'], 'Owned command changed')
        lease = bounded_json(self.transport/'LEASE.json', MAX_LEASE_BYTES)
        self.sequence = validate_lease(lease, self.permit, self.permit_sha256, now_monotonic=time.monotonic(), previous_sequence=self.sequence)
        import shutil
        free = {drive: shutil.disk_usage(drive+'/').free for drive in ('C:', 'G:')}
        validate_policy(load(self.state/'campaign.json'), free, datetime.now(timezone.utc))
        return dict(status='LIVE_CHILD_OWNERSHIP_CHECK_PASSED', lease_sequence=self.sequence, source_execution_started=False)

    def prime(self):
        require(not self.primed, 'Child already primed')
        self.check(); payload = self.payload
        for binding in [payload['source_receipt'], payload['catalog'], payload['gallery_preparation'], *payload['runtimes'], *payload['assets']]:
            verify(binding)
        source = load(payload['source_receipt']['path']); root = Path(source['prototype']).resolve()
        require(root.is_relative_to(self.local/'releases') and root.name == 'prototype', 'Frozen release source required')
        require(type(source['files']) is dict and 0 < len(source['files']) <= 4096, 'Bounded source manifest required')
        for relative, row in source['files'].items():
            path = (root/relative).resolve(); require(path.is_relative_to(root), 'Source manifest escaped release')
            verify(dict(path=str(path), **row))
        require(Path(payload['catalog']['path']).resolve() == root/'config/backends.json', 'Source catalog differs')
        from mode_galleries import backend_contract
        gallery = load(payload['gallery_preparation']['path'])
        require(gallery['catalog'] == payload['catalog'], 'Research gallery uses a different catalog')
        require(backend_contract(load(payload['catalog']['path']), payload['contract']['backend_key'], payload['contract']['mode']) == payload['contract'],
            'Actual catalog backend contract differs')
        from common import bind
        require(bind(payload['job']['audio_path'])['sha256'] == payload['job']['audio_sha256'], 'Saved audio binding changed')
        self.check(); self.primed = True
        return dict(source=str(root), input=self.permit['input'], source_execution_started=False)
