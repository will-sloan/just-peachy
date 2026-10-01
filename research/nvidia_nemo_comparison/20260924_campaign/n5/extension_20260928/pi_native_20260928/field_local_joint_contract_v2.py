"""Bind one broker to a finite manager; README_FIELD_LOCAL_JOINT_V2.md."""
import base64
import hashlib
from datetime import datetime
from field_local_release_plan_v2 import encoded, validate_release, validate_research_operation
from field_operator_session_plan_v3 import validate_policy
from field_owner_binding_v1 import pack


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def capsule(value, schema, maximum, prefix):
    if type(value) is not dict or set(value) != {'manifest', 'files'}:
        raise ValueError('Exact capsule envelope')
    manifest = value['manifest']
    if type(manifest) is not dict or set(manifest) != {'schema', 'files'} or manifest['schema'] != schema:
        raise ValueError('Exact capsule manifest')
    if type(value['files']) is not dict or type(manifest['files']) is not list:
        raise ValueError('Exact capsule containers')
    files = {}
    aliases = set()
    import re
    for name, body in value['files'].items():
        if type(name) is not str or not re.fullmatch(r'(code/[A-Za-z0-9_]+\.py|broker/(CONFIG|TEMPLATE)\.json)', name):
            raise ValueError('Exact portable capsule member')
        if prefix == 'code/' and not name.startswith(prefix):
            raise ValueError('Manager code only')
        if type(body) is not str or len(body)>174764:
            raise ValueError('Base64 source string')
        if name.casefold() in aliases:
            raise ValueError('Case alias member')
        aliases.add(name.casefold())
        raw = base64.b64decode(body, validate=True)
        if not 0 < len(raw) <= 131072:
            raise ValueError('Original member ceiling')
        files[name] = raw
    codes = [raw for name, raw in files.items() if name.startswith('code/')]
    if not 1 <= len(codes) <= maximum or sum(map(len, codes)) > 2097152:
        raise ValueError('Original code cardinality/aggregate')
    expected = [dict(path=n, bytes=len(raw), sha256=digest(raw)) for n, raw in sorted(files.items())]
    if encoded(manifest['files']) != encoded(expected):
        raise ValueError('Exact complete capsule bytes')
    if prefix != 'code/' and set(files)-{n for n in files if n.startswith('code/')} != {'broker/CONFIG.json', 'broker/TEMPLATE.json'}:
        raise ValueError('Required broker controls')
    return files


def bind(broker, manager, release, operation, prior_pi, *, now):
    """Pure construction, not admission. Caller verifies fresh actual evidence."""
    import json
    validate_release(release)
    validate_research_operation(operation, now=now)
    if release['allocation']['recordings'] != 1 or release['allocation']['launches'] != 3:
        raise ValueError('This qualification allocates one recording and three launches')
    files = capsule(broker, 'just-peachy.broker-capsule.v1', 64, 'broker')
    capsule(manager, 'just-peachy.local-release-manifest.v1', 16, 'code/')
    manager_sha = digest(encoded(manager['manifest']))
    if release['release_manifest_sha256'] != manager_sha:
        raise ValueError('Manager release/capsule digest')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:raise ValueError('Duplicate control key')
            result[key] = value
        return result
    config = json.loads(files['broker/CONFIG.json'], object_pairs_hook=unique)
    template = json.loads(files['broker/TEMPLATE.json'], object_pairs_hook=unique)
    encoded(config); encoded(template)
    if config.get('manager_manifest_sha256') != manager_sha or 'local_manager' in config:
        raise ValueError('Unconsumed prepared manager binding')
    if config['installed_manifest_sha256'] != release['installed_manifest_sha256']:
        raise ValueError('Installed manifest drift')
    if template['admission']['operator_parent']['manifest_sha256'] != release['mode_registry_sha256']:
        raise ValueError('Mode registry drift')
    if encoded(config['qualification']) != encoded(dict(schema='just-peachy.one-session-visible-qualification.v1', count=1, stop_after_samples=80000)):
        raise ValueError('One changed qualification, no hidden second recording')
    if not prior_pi:
        raise ValueError('Fresh exact prior owner census required')
    binding = dict(schema='just-peachy.local-gate-binding.v1', root=release['root'],
        release_sha256=digest(encoded(release)), manifest_sha256=manager_sha,
        recording_slot='recording-01', launch_slot='launch-02', operation=operation)
    config['local_manager'] = binding
    config['preflight_pi_owners'] = pack(prior_pi)
    template['admission'].update(preflight_pi_owners=config['preflight_pi_owners'],
        host_window_bytes=release['measured_host_before_bytes'],
        payload_before_bytes=release['measured_payload_before_bytes'],
        target_before_bytes=release['measured_target_before_bytes'])
    files['broker/CONFIG.json'] = encoded(config)
    files['broker/TEMPLATE.json'] = encoded(template)
    if len(files['broker/CONFIG.json']) > 65536 or len(files['broker/TEMPLATE.json']) > 131072:
        raise ValueError('Original control allocation')
    manifest = dict(schema='just-peachy.broker-capsule.v1', files=[
        dict(path=n, bytes=len(raw), sha256=digest(raw)) for n, raw in sorted(files.items())])
    policy = dict(schema='just-peachy.operator-broker-policy.v1',
        root=release['recording_roots'][0], issued_utc=operation['issued_utc'],
        expires_utc=operation['expires_utc'], allocation=release['allocation']['broker_allocation'],
        combined_output_cap_bytes=release['combined_output_cap_bytes'],
        total_payload_cap_bytes=release['total_payload_cap_bytes'], mode='delayed',
        release_manifest_sha256=digest(encoded(manifest)), boot_id=config['baseline']['boot_id'],
        host_window_bytes=release['measured_host_before_bytes'],
        target_before_bytes=release['measured_target_before_bytes'],
        payload_before_bytes=release['measured_payload_before_bytes'])
    validate_policy(policy, now=now)
    request = dict(policy=policy, manifest=manifest,
        files={n:base64.b64encode(raw).decode() for n, raw in sorted(files.items())})
    if len(encoded(request)) > 4*1048576:
        raise ValueError('Original initializer request ceiling')
    return dict(broker_request=request, gate_binding=binding,
        reserve_binding=dict(binding, launch_slot='launch-01'),
        finish_binding=dict(binding, launch_slot='launch-03'),
        full_joint_reservation=release['allocation'], admission_issued=False)
