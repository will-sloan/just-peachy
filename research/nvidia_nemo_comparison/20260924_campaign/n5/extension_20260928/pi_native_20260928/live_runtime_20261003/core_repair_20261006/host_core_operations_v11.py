"""Reviewed build33/34 host dispatch; README_CORE_OPERATIONS_V11.md.

This is a host dispatcher, not a native qualification or product runtime.
The original V10 prefix and closure adapter remain immutable source inputs.
"""
import psutil
psutil.Process().cpu_affinity([14])
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import uuid

PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BOOT = 'e60e67c2-f3f5-4b8b-8eab-2613df2de37e'
PIN33 = '2889a2bddc9b6cb65c150510e87db978eb5fb24e4ffa22809b1623d45234b61e'
PIN34 = 'fb9ca63814906629ec9e93935f4d28e77d1c60e1f6202f212223116195a0e802'
V10_SHA = '639b3a02ad51aae9155f8d4bf71f1424e4ef58523f2014cf34294733fc5c5c80'
ADAPTER_SHA = '4e038792bc074db74184e9bb29f4f51c2d2e738bcf87bb40349cecd29e6402f9'
ADAPTER_README_SHA = '07a4342ce0e193809466ca1c4850a01cb3d8bca35e440de864d696c0cee58f47'
ACTION_SHA = '4f5876f32a634db420baf78583a7a0ebac7d27b17bab52aace867d78df0d1c74'
INSTALLER_SHA = 'b4cbc107259556f901da1e47462b9ba238b766e56b7910c3c5982ea3fee68ad6'
BACKUP_PINS = {
    'COMPLETE.json': '9aa11fd4932bb64accda5a8155e735110c20bfb29189c4dc07563c7a171ee80e',
    'RESULT.json': '1154c795a07e35941d21f99fc81617f0534dd3de51771c070d031ce526d2f879',
    'CENSUS.json': '509432c01072df2d33b12cdf7de17f1fe450fede5f3521df051744107f68a263',
}
STAGE34 = dict(
    schema='just-peachy.core-stage34-root-admission.v1', label='core-stage34-01',
    manifest_sha256=PIN34, parent_manifest_sha256=PIN33,
    target='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-34',
    expected_boot_id=BOOT,
    payload_sha256='e150e52129c395bf83897b6821574a685c56fdd21503dc4e9071ce9fa6b65996',
    payload_bytes=2291501, action_sha256=ACTION_SHA, installer_source_sha256=INSTALLER_SHA,
    archive_sha256='5a4e83bf7b9bbe3874b363e7af842b706ddecc8150f7676874c7c7d003a36ce1',
    archive_bytes=1703894,
    source_review_sha256='53275087e72069b6d3012f505616079ab8debaa90a290848f1830e159e9c6096',
    members=447, expanded_bytes=7492370, directories=8, target_reservation_bytes=9851624,
    accepted_backup_metadata_sha256=BACKUP_PINS)

# Exact host ownership precedes the first project-source read.
initial = PRIVATE/'audit-preparation'/('core-operations-v11-source-'+uuid.uuid4().hex)
initial.mkdir(exist_ok=False)
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
stamps = [ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(kernel.GetCurrentProcess(), *(ctypes.byref(item) for item in stamps)):
    raise ctypes.WinError(ctypes.get_last_error())
with (initial/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
        affinity_mask=16384, creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000), stream)
    stream.flush(); os.fsync(stream.fileno())


def original_read(path, maximum=131072):
    path = Path(path)
    before = path.lstat()
    if (path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or before.st_size > maximum or path.resolve(strict=True) != path
            or any(parent.is_symlink() for parent in path.parents)):
        raise ValueError('Canonical bounded single-link project input required')
    raw = path.read_bytes(); after = path.stat()
    identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    if len(raw) != before.st_size or identity(before) != identity(after):
        raise ValueError('Project input changed during read')
    return raw


def independent_copy(root, path, raw):
    for suffix in ('.backup', '.restore'):
        destination = root/(path.name+suffix)
        with destination.open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise OSError('Short dispatcher source backup')
            stream.flush(); os.fsync(stream.fileno())
        if original_read(destination, max(131072, len(raw))) != raw:
            raise OSError('Independent dispatcher source readback differs')


source_root = Path(__file__).resolve().parent
v10_path = source_root/'host_core_operations_v10.py'
v10_raw = original_read(v10_path)
if hashlib.sha256(v10_raw).hexdigest() != V10_SHA:
    raise ValueError('Exact frozen V10 source required')
own_sources = {}
for path in (Path(__file__).resolve(), source_root/'README_CORE_OPERATIONS_V11.md',
             v10_path, source_root/'README_CORE_OPERATIONS_V10.md'):
    raw = original_read(path)
    if path == v10_path and raw != v10_raw:
        raise ValueError('Frozen V10 changed between pin and independent backup')
    independent_copy(initial, path, raw)
    own_sources[path] = raw
boundary = '\nbind_extended_closed_owner()\n'
v10_text = v10_raw.decode('utf-8')
if v10_text.count(boundary) != 1:
    raise ValueError('One exact frozen V10 pre-binding boundary required')
prefix = v10_text.split(boundary)[0]
v10 = dict(__name__='core_v11_exact_v10_prefix', __file__=str(v10_path))
exec(compile(prefix, str(v10_path), 'exec'), v10)
space, early = v10['space'], v10['early']


def reviewed_stage34_admission():
    """Consume only explicit paired root-reviewed certificate options."""
    options = ('--stage34-admission', '--stage34-admission-sha256')
    original = list(sys.argv)
    present = [original.count(option) for option in options]
    if present == [0, 0]:
        return None
    if present != [1, 1]:
        raise ValueError('One paired explicit stage34 admission path and SHA required')
    supplied = {}
    for option in options:
        index = original.index(option)
        if index+1 == len(original) or original[index+1].startswith('--'):
            raise ValueError('Stage34 certificate option value required')
        supplied[option] = original[index+1]
    expected = supplied[options[1]]
    if re.fullmatch('[0-9a-f]{64}', expected) is None:
        raise ValueError('Explicit reviewed certificate SHA required')
    path = Path(supplied[options[0]])
    if not path.is_absolute():
        raise ValueError('Absolute reviewed certificate path required')
    raw = original_read(path, 16384)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Reviewed stage34 certificate bytes differ')
    data = space['strict'](raw)
    required = {'schema', 'label', 'manifest_sha256', 'parent_manifest_sha256', 'target',
        'expected_boot_id', 'payload_sha256', 'payload_bytes', 'action_sha256',
        'installer_source_sha256', 'archive_sha256', 'archive_bytes', 'source_review_sha256',
        'members', 'expanded_bytes', 'directories', 'target_reservation_bytes',
        'accepted_backup_metadata_sha256'}
    if (type(data) is not dict or set(data) != required
            or data['schema'] != 'just-peachy.core-stage34-root-admission.v1'
            or data['label'] != 'core-stage34-01'
            or data['target'] != space['NATIVE_PREFIX']+'field-runtime-v29-build-34'
            or data['expected_boot_id'] != BOOT or data['parent_manifest_sha256'] != PIN33
            or data['manifest_sha256'] == PIN33 or data['action_sha256'] != ACTION_SHA
            or data['installer_source_sha256'] != INSTALLER_SHA
            or data['accepted_backup_metadata_sha256'] != BACKUP_PINS):
        raise ValueError('Exact reviewed build34/B14 certificate required')
    for name in ('manifest_sha256', 'payload_sha256', 'action_sha256',
                 'installer_source_sha256', 'archive_sha256', 'source_review_sha256'):
        if type(data[name]) is not str or re.fullmatch('[0-9a-f]{64}', data[name]) is None:
            raise ValueError('Exact certificate SHA field required: '+name)
    for name in ('payload_bytes', 'archive_bytes', 'members', 'expanded_bytes',
                 'directories', 'target_reservation_bytes'):
        if type(data[name]) is not int or data[name] <= 0:
            raise ValueError('Positive actual certificate integer required: '+name)
    if data != STAGE34:
        raise ValueError('Only the root-reviewed actual stage34-01 constants are admitted')
    if not 2*1024**2 < data['payload_bytes'] <= 3*1024**2 or data['archive_bytes'] > 2*1024**2:
        raise ValueError('Retained bounded stage-only encoding scope required')
    for root in (initial, early):
        independent_copy(root, path, raw)
    if original_read(path, 16384) != raw:
        raise ValueError('Root-reviewed certificate changed during admission')
    # Remove only these host-adapter options; the original argparse authority
    # continues to parse every native-operation option without modification.
    removed = {original.index(option)+offset for option in options for offset in (0, 1)}
    sys.argv[:] = [item for index, item in enumerate(original) if index not in removed]
    return dict(data=data, path=str(path), sha256=expected, bytes=len(raw))


certificate = reviewed_stage34_admission()


def make_owner_family(legacy, adapter, pin34):
    """Select the immutable validator by the actual job pin, preserving old form."""
    validators = {PIN33: adapter['make_closed_unit_owner_validator'](legacy, PIN33)}
    if pin34 is not None:
        if type(pin34) is not str or pin34 == PIN33 or re.fullmatch('[0-9a-f]{64}', pin34) is None:
            raise ValueError('Distinct actual reviewed build34 manifest required')
        validators[pin34] = adapter['make_closed_unit_owner_validator'](legacy, pin34)

    def validate(job, raw, entry, closure):
        value = adapter['_strict'](raw)
        if type(value) is not dict:
            raise ValueError('Actual ownership object required')
        keys = set(value)
        if not keys.intersection(adapter['EXTRA_KEYS']):
            return legacy(job, raw, entry, closure)
        if keys not in (adapter['BASE_KEYS'] | adapter['EXTRA_KEYS'],
                       adapter['BASE_KEYS'] | adapter['EXTRA_KEYS'] | {'raw_admission_sha256'}):
            raise ValueError('Malformed extended ownership fields cannot use historical fallback')
        if type(job) is not dict:
            raise ValueError('Actual job object required')
        pin = job.get('package_manifest_sha256')
        if type(pin) is not str or pin not in validators:
            raise ValueError('Extended owner belongs to neither actual accepted build33 nor build34')
        return validators[pin](job, raw, entry, closure)

    return validate


def check_owner_family(adapter):
    """Six pure routing checks; do not repeat the healthy ten legacy/schema cases."""
    synthetic34 = PIN34  # Only the local routing objects are synthetic; no JOB is created.
    def legacy(*args):
        return ('legacy', args)
    def factory(callback, pin):
        def routed(*args):
            return ('family', pin, args)
        return routed
    probe_adapter = dict(adapter, make_closed_unit_owner_validator=factory)
    validate = make_owner_family(legacy, probe_adapter, synthetic34)
    entry, closure = {}, {}
    old_raw = b'{}'
    job = {'package_manifest_sha256': 'historical-unchanged-legacy-authority'}
    if validate(job, old_raw, entry, closure) != ('legacy', (job, old_raw, entry, closure)):
        raise AssertionError('Historical callback or exact four arguments changed')
    value = {name: None for name in adapter['BASE_KEYS'] | adapter['EXTRA_KEYS']}
    raw = space['encoded'](value)
    for pin in (PIN33, synthetic34):
        job = {'package_manifest_sha256': pin}
        if validate(job, raw, entry, closure) != ('family', pin, (job, raw, entry, closure)):
            raise AssertionError('Actual manifest family routing differs')
    rejected = 0
    malformed = dict(value); malformed.pop('stack')
    for job, bad_raw in (
        ({'package_manifest_sha256': '0'*64}, raw),
        ({'package_manifest_sha256': PIN33}, space['encoded'](malformed)),
        ({'package_manifest_sha256': PIN33}, b'{"address_space":[],"address_space":[]}')):
        try:
            validate(job, bad_raw, entry, closure)
        except ValueError:
            rejected += 1
        else:
            raise AssertionError('Unknown/malformed extended route was admitted')
    return dict(schema='just-peachy.core-owner-family-routing-check.v1', status='PASS',
        tests=6, positives=3, rejections=rejected, skipped=0, models=False,
        synthetic_routing_only=True, native_jobs_created=False,
        legacy_schema_selfcheck_repeated=False)


def bind_owner_family():
    path = source_root/'model_address_space_20261006/closed_unit_owner_as.py'
    readme = path.with_name('README_CLOSED_UNIT_OWNER_AS.md')
    raws = {}
    for source, expected in ((path, ADAPTER_SHA), (readme, ADAPTER_README_SHA)):
        raw = original_read(source)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Exact previously reviewed/tested immutable owner adapter required')
        independent_copy(early, source, raw)
        raws[source] = raw
    adapter = dict(__name__='core_v11_exact_owner_adapter', __file__=str(path))
    exec(compile(raws[path], str(path), 'exec'), adapter)
    checks = check_owner_family(adapter)
    accepted34 = PIN34
    prior = space['driver'].closed_unit_owner
    family = make_owner_family(prior, adapter, accepted34)
    for source, raw in raws.items():
        if original_read(source) != raw:
            raise ValueError('Immutable owner adapter changed during routing checks')
    space['put']('OWNER_FAMILY_ROUTING_CHECK.json', dict(checks, adapter_sha256=ADAPTER_SHA,
        v10_sha256=V10_SHA, accepted_manifest_sha256=[PIN33]+([] if accepted34 is None else [accepted34]),
        reviewed_stage34_certificate_sha256=None if certificate is None else certificate['sha256'],
        original_legacy_validator_reused=True, exact_modern_two_helper_whitelist_unchanged=True,
        historical_nested_decoder_unchanged=True))
    space['driver'].closed_unit_owner = family


def stage_payload_ceiling(args):
    """Retain default/stage33; only exact reviewed stage34 receives three MiB."""
    default = 2*1024**2
    size = args.payload.stat().st_size
    if args.label != 'core-stage34-01':
        return v10['stage33_payload_ceiling'](args)
    if size <= default or size > 3*1024**2:
        return default
    if args.writes is not True or certificate is None:
        raise ValueError('Oversized stage34 requires explicit reviewed exact certificate and writes flag')
    import base64
    data = certificate['data']
    action_raw = space['read'](args.action, 131072)
    payload_raw = space['read'](args.payload, 3*1024**2)
    if (len(payload_raw) != data['payload_bytes'] or space['sha'](payload_raw) != data['payload_sha256']
            or space['sha'](action_raw) != data['action_sha256']):
        raise ValueError('Exact reviewed stage34 action/payload bytes required')
    payload = space['strict'](payload_raw)
    if (type(payload) is not dict or set(payload) != {'archive_base64', 'archive_sha256',
            'expected_boot_id', 'installer_source_base64', 'installer_source_sha256',
            'manifest_sha256', 'production_backup_admission', 'source_review_sha256',
            'target_reservation_bytes'}
            or any(payload[key] != data[key] for key in ('archive_sha256', 'expected_boot_id',
                'installer_source_sha256', 'manifest_sha256', 'source_review_sha256',
                'target_reservation_bytes'))):
        raise ValueError('Stage34 certificate differs from exact sealed payload fields')
    backup = PRIVATE/'production-backup-14-reconcile-01'
    admission = payload['production_backup_admission']
    if (type(admission) is not dict or admission.get('schema') != 'just-peachy.core-stage-backup-admission.v1'
            or Path(admission['backup_root']) != backup or Path(admission['root']) != backup/'payload'
            or admission['boot_id'] != BOOT or admission['completion_sha256'] != BACKUP_PINS['COMPLETE.json']
            or admission['result_sha256'] != BACKUP_PINS['RESULT.json']
            or any(admission.get(key) is not True for key in ('source_before_after_verified',
                'external_asset_pins_verified', 'exact_owner_gone', 'cgroup_empty'))
            or type(admission.get('natural_returncode')) is not int or admission['natural_returncode'] != 0
            or admission.get('owner') != dict(boot_id=BOOT, pid=68815, start_ticks=1489488)):
        raise ValueError('Exact accepted closed backup14 admission required')
    for name, expected in BACKUP_PINS.items():
        raw = space['read'](backup/name, 2*1024**2)
        pin = admission['input_pins'][name]
        if pin['sha256'] != expected or type(pin['bytes']) is not int or pin['bytes'] != len(raw) or space['sha'](raw) != expected:
            raise ValueError('Accepted backup14 metadata changed: '+name)
    if (type(payload['archive_base64']) is not str or type(payload['installer_source_base64']) is not str
            or len(payload['archive_base64']) > 4*((default+2)//3)
            or len(payload['installer_source_base64']) > 4*((131072+2)//3)):
        raise ValueError('Retained finite archive/installer encoding required')
    archive = base64.b64decode(payload['archive_base64'], validate=True)
    installer = base64.b64decode(payload['installer_source_base64'], validate=True)
    if (len(archive) != data['archive_bytes'] or len(archive) > default
            or space['sha'](archive) != data['archive_sha256'] or len(installer) > 131072
            or space['sha'](installer) != INSTALLER_SHA):
        raise ValueError('Exact reviewed bounded stage34 archive/installer required')
    namespace = dict(__name__='core_v11_exact_stage34_installer_validator')
    exec(compile(installer, '<sealed-build34-installer-validator>', 'exec'), namespace)
    manifest, members = namespace['validate_payload'](archive, data['archive_sha256'], data['manifest_sha256'])
    expanded = sum(map(len, members.values()))
    directories = {str(parent) for name in members for parent in PurePosixPath(name).parents if str(parent) != '.'}
    reservation = expanded+len(archive)+(len(directories)+1)*65536+65536
    if (manifest.get('target') != data['target'] or len(members) != data['members']
            or expanded != data['expanded_bytes'] or len(directories) != data['directories']
            or type(payload['target_reservation_bytes']) is not int
            or payload['target_reservation_bytes'] != reservation or reservation != data['target_reservation_bytes']):
        raise ValueError('Exact canonical stage34 inventory/full reservation differs')
    if hashlib.sha256(original_read(Path(certificate['path']), 16384)).hexdigest() != certificate['sha256']:
        raise ValueError('Reviewed stage34 certificate changed before dispatch')
    space['put']('STAGE34_PAYLOAD_ADMISSION.json', dict(
        schema='just-peachy.core-stage34-payload-admission.v1', label=args.label,
        default_payload_bytes=default, admitted_payload_bytes=3*1024**2,
        actual_payload_bytes=len(payload_raw), payload_sha256=data['payload_sha256'],
        action_sha256=data['action_sha256'], archive_sha256=data['archive_sha256'], archive_bytes=len(archive),
        installer_sha256=INSTALLER_SHA, manifest_sha256=data['manifest_sha256'],
        source_review_sha256=data['source_review_sha256'], target=data['target'],
        expanded_bytes=expanded, members=len(members), directories=len(directories),
        target_reservation_bytes=reservation, accepted_backup_metadata_sha256=BACKUP_PINS,
        root_reviewed_certificate_sha256=certificate['sha256'], pure_host_validation=True))
    return 3*1024**2


bind_owner_family()
for path, raw in own_sources.items():
    if original_read(path) != raw:
        raise ValueError('Dispatcher source changed before original main')
space['put']('V11_SOURCE_BINDING.json', dict(
    schema='just-peachy.core-operations-v11-source-binding.v1',
    frozen_v10_sha256=V10_SHA, exact_prefix_before_original_binding=True,
    healthy_ten_owner_schema_checks_repeated=False, independent_backups_and_restores=True,
    initial_owner_root=str(initial), sources={str(path):dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        for path, raw in own_sources.items()}, native_action_claimed=False))
anchor = 'a.payload.stat().st_size > 2*1024**2'
replacement = 'a.payload.stat().st_size > stage_payload_ceiling(a)'
main = space['_main_source']
if main.count(anchor) != 1:
    raise ValueError('One exact retained local payload boundary required')
main = main.replace(anchor, replacement)
if main.replace(replacement, anchor) != space['_main_source']:
    raise ValueError('Only exact main payload boundary may change')
space['driver'].__dict__['stage_payload_ceiling'] = stage_payload_ceiling
exec(compile(main, '<core-v11-exact-stage-payload-main>', 'exec'), space['driver'].__dict__)
space['driver'].main()
