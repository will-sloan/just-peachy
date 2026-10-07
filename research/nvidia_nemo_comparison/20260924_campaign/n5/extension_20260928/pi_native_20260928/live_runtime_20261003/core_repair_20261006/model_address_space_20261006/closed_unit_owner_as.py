"""Host-only extended closed supervisor receipt; README_CLOSED_UNIT_OWNER_AS.md.

The legacy callback is left intact. No runtime imports, native action, process
inspection, filesystem mutation or receipt creation occurs in this module.
"""
import hashlib
import json
import re


BASE_KEYS = frozenset(('control_group', 'deadline_monotonic', 'idle_timeout_seconds',
                      'invocation_id', 'main_pid', 'owner', 'runtime_max_seconds', 'unit'))
EXTRA_KEYS = frozenset(('address_space', 'stack', 'qualification_kind', 'recording_model_scope'))
ROOT = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/'
MODERN_HELPERS = frozenset((
    '5c6eab13e00076aabf3f022f69410e1f330dc16a4cbad69b49b8fe016109e37e',
    '01fc4288e8496a99eb318875e1aaebac51af8b2fca80b232798693d93cc27237'))
LABELS = dict(raw=r'raw-qualification-\d{2}', pipeline=r'pipeline-qualification-\d{2}',
              storage=r'storage-check-\d{2}', backup=r'production-backup-\d{2}',
              gui=r'gui-qualification-\d{2}', full_app_hour=r'full-app-hour-\d{2}')


def _strict(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate unit ownership field')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def make_closed_unit_owner_validator(legacy_validator, package_manifest_sha256):
    """Bind one accepted build33 manifest, returning the existing four-arg API.

    Original receipts go directly to the unchanged validator. Extended receipts
    first prove their actual immutable bytes, exact AS/stack policy and job
    scope, then reuse every legacy job/closure/identity/lifetime check on a
    projected old-form document. The returned pin always names ORIGINAL bytes.
    """
    if (not callable(legacy_validator) or type(package_manifest_sha256) is not str
            or re.fullmatch('[0-9a-f]{64}', package_manifest_sha256) is None):
        raise ValueError('Unchanged legacy validator and actual accepted build33 manifest required')

    def validate(job, raw, entry, closure):
        value = _strict(raw)
        if type(value) is not dict:
            raise ValueError('Unit ownership document must be an object')
        keys = set(value)
        if not keys.intersection(EXTRA_KEYS):
            return legacy_validator(job, raw, entry, closure)
        if keys not in (BASE_KEYS | EXTRA_KEYS, BASE_KEYS | EXTRA_KEYS | {'raw_admission_sha256'}):
            raise ValueError('Exact extended top-level supervisor fields required')
        if (entry.get('path') != 'UNIT_OWNERSHIP.json' or type(raw) is not bytes
                or len(raw) > 16384 or entry.get('identity', {}).get('bytes') != len(raw)
                or hashlib.sha256(raw).hexdigest() != entry.get('sha256')):
            raise ValueError('Complete original mirrored extended receipt pin differs')
        if (job.get('schema') != 'just-peachy.native-component-job.v1'
                or job.get('package_manifest_sha256') != package_manifest_sha256):
            raise ValueError('Exact accepted build33 actual job required')
        kind, scope = value['qualification_kind'], value['recording_model_scope']
        if type(kind) is not str or kind not in LABELS or type(scope) is not bool:
            raise ValueError('Exact supported qualification kind and boolean model scope required')
        for name in ('address_space', 'stack'):
            limits = value[name]
            if type(limits) is not list or len(limits) != 2 or any(type(item) is not int for item in limits):
                raise ValueError('Actual integer soft/hard resource pair required')
        if value['stack'] != [1024**2, 1024**2]:
            raise ValueError('Unchanged actual one-MiB stack required')
        root = job.get('output_root', '')
        if type(root) is not str or not root.startswith(ROOT):
            raise ValueError('Exact top-level qualification output root required')
        label = root[len(ROOT):]
        pattern = r'classic-ui-check-\d{2}' if kind == 'gui' and scope else LABELS[kind]
        if re.fullmatch(pattern, label) is None or job.get('unit') != 'jp-v29-'+label+'.service':
            raise ValueError('Qualification kind differs from actual named job')
        if scope != (kind == 'full_app_hour' or kind == 'gui' and label.startswith('classic-ui-check-')):
            raise ValueError('One-GiB scope is restricted to integrated hour or exact modern GUI')
        expected_as = 1024**3 if scope else 768*1024**2
        if value['address_space'] != [expected_as, expected_as]:
            raise ValueError('Actual finite model address allowance differs from reviewed scope')
        if 'raw_admission_sha256' in value and kind != 'raw':
            raise ValueError('Raw admission field belongs only to raw qualification')
        if kind == 'full_app_hour':
            if (value['runtime_max_seconds'] != 4680
                    or job.get('workflow') != 'continuous-full-application-repeated-wav'
                    or job.get('duration_seconds') != 3600 or job.get('repeat_input_seconds') != 3600):
                raise ValueError('Unchanged integrated one-hour job and owned lifetime required')
        if kind == 'gui' and scope:
            if (job.get('helper_source_sha256') not in MODERN_HELPERS
                    or job.get('native_check_path') != root+'/NATIVE_CHECK.json'):
                raise ValueError('Exact modern live/saved helper and actual GUI job required')
        old_value = {key: item for key, item in value.items() if key not in EXTRA_KEYS}
        old_raw = json.dumps(old_value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        old_entry = dict(entry, sha256=hashlib.sha256(old_raw).hexdigest(),
                         identity=dict(entry['identity'], bytes=len(old_raw)))
        old_pin = legacy_validator(job, old_raw, old_entry, closure)
        if type(old_pin) is not dict or old_pin.get('owner') != value['owner']:
            raise ValueError('Legacy closure validator returned a different actual owner')
        return dict(old_pin, sha256=entry['sha256'])

    return validate


def selfcheck_closed_unit_owner(legacy_validator, package_manifest_sha256, *,
                               legacy_case, hour_case, gui_case):
    """Ten pure admission checks over host-verified immutable old metadata.

    Cases contain job/raw/entry/closure. No reads or writes occur here. New-form
    receipt views and the new package field are SYNTHETIC LOCAL test values;
    they neither create jobs nor qualify actual model/resource enforcement.
    """
    validate = make_closed_unit_owner_validator(legacy_validator, package_manifest_sha256)
    required = {'job', 'raw', 'entry', 'closure'}
    sources = {}

    def admit_source(name, case):
        if type(case) is not dict or set(case) != required or type(case['raw']) is not bytes:
            raise ValueError('Exact host-verified legacy metadata case required')
        original = legacy_validator(case['job'], case['raw'], case['entry'], case['closure'])
        sources[name] = dict(receipt_sha256=hashlib.sha256(case['raw']).hexdigest(),
                            package_manifest_sha256=case['job'].get('package_manifest_sha256'),
                            owner=original['owner'])
        return original

    def copy_metadata(value):
        return _strict(json.dumps(value, sort_keys=True, allow_nan=False).encode())

    def pack(job, value, entry, closure):
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        entry = dict(entry, identity=dict(entry['identity'], bytes=len(raw)),
                     sha256=hashlib.sha256(raw).hexdigest())
        return dict(job=job, raw=raw, entry=entry, closure=closure)

    def extended(name, case, kind):
        admit_source(name, case)  # Actual old metadata must pass BEFORE local changes.
        job = copy_metadata(case['job'])
        job['package_manifest_sha256'] = package_manifest_sha256
        value = _strict(case['raw'])
        value.update(address_space=[1024**3, 1024**3], stack=[1024**2, 1024**2],
                     qualification_kind=kind, recording_model_scope=True)
        return pack(job, value, copy_metadata(case['entry']), copy_metadata(case['closure']))

    positives = []
    original = admit_source('legacy', legacy_case)
    if validate(**legacy_case) != original:
        raise AssertionError('Original receipt must pass through without changes')
    positives.append('original-form-preserved')
    hour = extended('hour', hour_case, 'full_app_hour')
    gui = extended('gui', gui_case, 'gui')
    for name, case in (('integrated-hour-extended', hour), ('modern-gui-extended', gui)):
        result = validate(**case)
        if result['sha256'] != case['entry']['sha256'] or result['owner'] != case['job']['owner']:
            raise AssertionError('Original synthetic new-form hash and exact old owner required')
        positives.append(name)
    rejections = []
    mutations = (
        ('missing-extra-field', lambda value: value.pop('stack')),
        ('boolean-as-integer', lambda value: value.update(address_space=[True, 1024**3])),
        ('integer-scope-boolean', lambda value: value.update(recording_model_scope=1)),
        ('wrong-kind-for-hour-label', lambda value: value.update(qualification_kind='gui')),
        ('changed-stack', lambda value: value.update(stack=[2*1024**2, 2*1024**2])),
    )
    bad_cases = []
    for name, mutate in mutations:
        value = _strict(hour['raw'])
        mutate(value)
        bad_cases.append((name, pack(copy_metadata(hour['job']), value,
                                    copy_metadata(hour['entry']), copy_metadata(hour['closure']))))
    bad_hash = dict(hour, entry=dict(hour['entry'], sha256='0'*64))
    bad_package = dict(hour, job=dict(hour['job'], package_manifest_sha256='0'*64))
    bad_cases.extend((('changed-original-member-hash', bad_hash), ('unaccepted-package-pin', bad_package)))
    for name, case in bad_cases:
        try:
            validate(**case)
        except ValueError:
            rejections.append(name)
        else:
            raise AssertionError('Malformed new-form admission was accepted: '+name)
    return dict(schema='just-peachy.closed-unit-owner-as-selfcheck.v1', status='PASS',
                tests=len(positives)+len(rejections), skipped=0, failures=0,
                positive_cases=positives, rejection_cases=rejections, source_cases=sources,
                synthetic_extended_metadata=True, actual_new_unit_enforcement_proven=False,
                original_inputs_modified=False, models=False, native_action=False, writes=False)
