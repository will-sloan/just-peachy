"""Immutable production acceptance and per-session gates. See README_RELEASE_AUTHORIZATION.md."""
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import time

KEYS=('diarizer','embedding','input_source','nemotron_profile','allow_experimental',
      'provisional_correction','refinement_profile','revision_window_seconds','refinement_period_seconds',
      'embedding_schedule','embedding_refresh_seconds','speaker_attribution','optional_d1_refiner')
HOME='/home/peachyprototype/JustPeachy/'


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def sha(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{64}',value):
        raise ValueError('Explicit SHA256 required')
    return value


def bounded_bytes(path,maximum=262144):
    path=Path(path)
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size>maximum: raise ValueError('Bounded regular authorization receipt')
    with path.open('rb') as stream:raw=stream.read(maximum+1)
    after=path.lstat()
    if len(raw)>maximum or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('Authorization receipt changed')
    return raw


def bounded_json(path,maximum=262144):
    return strict(bounded_bytes(path,maximum))


def selection_key(selection):
    value=selection.validate() if hasattr(selection,'validate') else selection
    if set(value)!=set(KEYS):raise ValueError('Complete explicit algorithm selection required')
    return {key:value[key] for key in KEYS}


def validate_acceptance(value,binding):
    if (value.get('schema')!='just-peachy.v29.production-acceptance.v1' or value.get('accepted') is not True
        or not isinstance(value.get('reviewer'),str) or not value['reviewer'].strip()
        or type(value.get('accepted_unix')) not in (int,float) or not math.isfinite(value['accepted_unix'])
        or value['accepted_unix']<=0 or value.get('target')!=binding['target']
        or value.get('candidate_content_sha256')!=binding['candidate_content_sha256']
        or value.get('installed_manifest_sha256')!=binding['installed_manifest_sha256']):
        raise ValueError('Explicit exact-content production acceptance required')
    sha(value['candidate_content_sha256']);sha(value['installed_manifest_sha256'])
    sha(value['previous_desktop_sha256'])
    selections=value.get('allowed_selections')
    if not isinstance(selections,list) or not 1<=len(selections)<=256:
        raise ValueError('Explicit accepted selections required')
    from profiles import RuntimeSelection
    for row in selections:
        if (set(row)!=set(KEYS) or row['diarizer'] not in ('pyannote','nemotron')
            or row['embedding'] not in ('redimnet','titanet','anonymous')
            or row['input_source'] not in ('live','saved') or type(row['provisional_correction']) is not bool):
            raise ValueError('Exact production selection shape')
        RuntimeSelection(**row).validate()
        if row['provisional_correction']:
            raise ValueError('Production dual diarizer is not implemented/accepted by this release')
        if row['optional_d1_refiner']:
            from optional_refiner_dispatch import reference
            reference(value,RuntimeSelection(**row))
        if row['diarizer']=='pyannote' and row['nemotron_profile'] is not None:
            raise ValueError('Pyannote cannot name a Nemotron preset')
        if row['diarizer']=='nemotron' and not isinstance(row['nemotron_profile'],str):
            raise ValueError('Explicit accepted Nemotron preset')
    limits=value['limits']
    if 'manual_stop_storage_policy' in limits and limits['manual_stop_storage_policy'] is not True:
        raise ValueError('Explicit reviewed manual-stop storage policy required')
    for key,minimum,maximum in (('maximum_session_seconds',1,300),('maximum_developer_seconds',3600,86400),
        ('max_drain_seconds',1,86400),('max_backlog_seconds',1,86400)):
        if type(limits.get(key)) is not int or not minimum<=limits[key]<=maximum:
            raise ValueError('Finite explicit production policy ceiling: '+key)
    from optional_refiner_dispatch import validate_references
    validate_references(value.get('optional_refiner_admissions',[]))
    assets=value.get('assets')
    if not isinstance(assets,list) or not 1<=len(assets)<=512: raise ValueError('Explicit native asset inventory')
    paths=set()
    for row in assets:
        path=row['path'];resolved=row['resolved']
        for name in (path,resolved):
            if (not isinstance(name,str) or '..' in PurePosixPath(name).parts
                or PurePosixPath(name).as_posix()!=name): raise ValueError('Pinned native asset path')
        if not path.startswith(HOME):raise ValueError('Pinned native asset alias')
        # Actual selected-assets-01 verified the installed Python symlink. Its
        # one external resolution is content/extent pinned, not a root grant.
        interpreter=(path==binding['python'] and resolved=='/usr/bin/python3.11'
            and row['bytes']==6616896
            and row['sha256']=='304aa87a76ebb13fd22d253ac157f14980ff2cdb23e6274f3b045571405e07dc')
        if not resolved.startswith(HOME) and not interpreter:
            raise ValueError('Pinned native asset resolution')
        if path in paths or type(row['bytes']) is not int or not 0<row['bytes']<=8*1024**3:
            raise ValueError('Unique bounded native asset entry')
        paths.add(path);sha(row['sha256'])
    backup=value.get('full_backup')
    if not isinstance(backup,dict) or backup.get('scope')!='selected-release-and-user-data':
        raise ValueError('Explicit reviewed full release/data backup scope required')
    for key in ('manifest_sha256','completion_sha256'):sha(backup[key])
    for key in ('root','manifest_path','completion_path'):
        if not isinstance(backup.get(key),str) or not backup[key]: raise ValueError('Full backup location required')
    return value


def authorization(binding):
    if binding.get('native_launch_enabled') is not True: raise PermissionError('Native launch is not enabled')
    root=Path(binding['target'])
    kind=binding.get('authorization_kind','qualification')
    if kind=='production':
        path=root/'PRODUCTION_ACCEPTANCE.json'
        raw=bounded_bytes(path)
        if len(raw)>262144 or hashlib.sha256(raw).hexdigest()!=binding.get('production_acceptance_sha256'):
            raise ValueError('Immutable production acceptance pin changed')
        return kind,validate_acceptance(strict(raw),binding)
    if kind!='qualification': raise ValueError('Unknown release authorization kind')
    raw=bounded_bytes(root/'NATIVE_ADMISSION.json',65536)
    value=strict(raw)
    if (len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=binding.get('admission_sha256')
        or value.get('schema')!='just-peachy.v29-reviewed-native-admission.v1'
        or value.get('reviewed') is not True or value.get('native_launch_enabled') is not True
        or value.get('candidate_content_sha256')!=binding['candidate_content_sha256']
        or value.get('target')!=str(root) or value.get('expires_unix',0)<=time.time()
        or value.get('boot_id')!=Path('/proc/sys/kernel/random/boot_id').read_text().strip()):
        raise PermissionError('Qualification admission expired, changed, or belongs to another boot')
    return kind,value


def variant_asset_document(binding,selection,document):
    """Match the engine's selected native fields while retaining embedding data."""
    if selection_key(selection)['nemotron_profile']!='chunk52_threads2':return document,{}
    pin=binding.get('native_variants',{}).get('chunk52_threads2')
    if type(pin) is not dict or set(pin)!={'path','sha256'}:
        raise ValueError('Exact accepted thread2 descriptor binding required')
    from native_variant import verify_native_variant, SOURCE_SHA256, COMPONENT_REVIEW
    verified=verify_native_variant(pin['path'],sha(pin['sha256']),selection)
    native=verified.document()
    merged=dict(document)
    for key in ('nemotron_model','nemotron_model_sha256','nemotron_library','nemotron_library_sha256',
                'native_runtime_files','streaming_profile','native_device'):
        merged[key]=native[key]
    parent=Path(pin['path']).parent
    required={pin['path']:pin['sha256'],str(parent/'BUILD_RESULT.json'):verified.build_result_sha256,
        str(parent/'SOURCE_VARIANT.json'):verified.source_variant_sha256,
        str(parent/'session.cpp'):SOURCE_SHA256,str(parent/'build/libnemo_speech_asr.so'):verified.core_sha256,
        str(COMPONENT_REVIEW):verified.component_review_sha256,
        str(parent/'OWNER.json'):None,str(parent/'JOB_EXIT.json'):None}
    return merged,required


def required_assets(binding,selection):
    selected=selection_key(selection)
    if selected['diarizer']=='pyannote': key='baseline-titanet' if selected['embedding']=='titanet' else 'baseline'
    else:
        mode='delayed' if selected['nemotron_profile']=='current_delayed' else 'streaming'
        key='d1-'+mode+('-titanet' if selected['embedding']=='titanet' else '')+('-saved' if mode=='streaming' else '')
    pin=binding['profiles'][key];raw=Path(pin['path']).read_bytes()
    if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Accepted descriptor changed')
    descriptor=strict(raw);document,variant_assets=variant_asset_document(binding,selection,descriptor['runtime_document'])
    root=Path(binding['installed_release'])
    raw=(root/'RELEASE_MANIFEST.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=binding['installed_manifest_sha256']:raise ValueError('Installed manifest changed')
    manifest=strict(raw)
    contract_pin=next(row for row in manifest['files'] if row['path']=='config/field_contract.json')
    raw=(root/'config/field_contract.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=contract_pin['sha256']:raise ValueError('Pinned installed asset contract changed')
    contract=strict(raw)
    catalog_pin=next(row for row in manifest['files'] if row['path']=='config/assets.json')
    raw=bounded_bytes(root/'config/assets.json')
    if hashlib.sha256(raw).hexdigest()!=catalog_pin['sha256']:
        raise ValueError('Pinned installed asset catalog changed')
    catalog={}
    for row in strict(raw):
        relative=row['deployment_relative_path']
        filename=row['filename']
        if (not relative.startswith('models/') or '..' in PurePosixPath(relative).parts
            or relative in catalog or not filename or PurePosixPath(filename).name!=filename
            or '\\' in filename):
            raise ValueError('Unsupported installed asset catalog mapping')
        catalog[relative]=(sha(row['sha256']),filename)
    required={str(root/'RELEASE_MANIFEST.json'):binding['installed_manifest_sha256']}
    required.update(variant_assets)
    for component in descriptor['runtime_profile']['definition']['composition']['components'].values():
        for asset in component.get('assets',[]):
            relative=asset['deployment_relative_path']
            row=catalog.get(relative)
            if row is None or row[0]!=asset['sha256']:
                raise ValueError('Selected asset differs from pinned installed catalog')
            # app.paths.pipeline_config resolves the shared content-addressed
            # store from assets.json, not its deployment-relative label.
            required[str(Path(contract['models_root'])/row[0]/row[1])]=row[0]
    for row in document.get('native_runtime_files',[]):required[row['path']]=row['sha256']
    if selected['diarizer']=='nemotron':
        model=document['nemotron_model']
        # Streaming descriptors intentionally select an independent geometry
        # model path; its artifact bytes match the installed D1 model pin.
        digest=sha(descriptor['runtime_profile']['definition']['composition']['components']['diarization']['artifact_sha256'])
        if not any(row.get('sha256')==digest for row in contract['extra_assets']):
            raise ValueError('Selected native diarizer artifact lacks immutable installed pin')
        required[model]=digest
    extra_hashes=set()
    if selected['embedding']=='titanet':
        required[document['titanet_manifest']]=document['titanet_manifest_sha256']
        namespace=document['embedding_namespace']
        extra_hashes={namespace['onnx_sha256'],namespace['frontend_sha256']}
    # These binaries are selected by the accepted release but not model assets.
    required.setdefault(binding['python'],None)
    if selected['input_source']=='live':required.setdefault(binding['live_config']['host_executable'],None)
    if selected['optional_d1_refiner']:
        from profiles import RuntimeSelection
        child=RuntimeSelection('nemotron','anonymous',selected['input_source'],'current_delayed')
        child_required,child_extra=required_assets(binding,child)
        for name,digest in child_required.items():
            if name in required and required[name] is not None and digest is not None and required[name]!=digest:
                raise ValueError('Primary and optional native assets conflict')
            required.setdefault(name,digest)
        extra_hashes.update(child_extra)
    return required,extra_hashes


def selected_inventory_sha256(binding,selection,assets):
    """Canonical exact selected primary + optional inventory, never arbitrary receipt metadata."""
    required,extras=required_assets(binding,selection)
    available={row['path']:row for row in assets}
    if len(available)!=len(assets):raise ValueError('Duplicate native inventory path')
    for digest in extras:
        matches=[row for row in assets if row['sha256']==digest]
        if not matches:raise ValueError('Selected embedding assets missing')
        for row in matches:required[row['path']]=digest
    chosen=[]
    for name,expected in sorted(required.items()):
        row=available.get(name)
        if row is None or expected is not None and row['sha256']!=expected:
            raise ValueError('Selected primary/refiner inventory mismatch: '+name)
        chosen.append({key:row[key] for key in ('path','resolved','bytes','sha256')})
    return hashlib.sha256(json.dumps(chosen,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _verify_assets(binding,selection,acceptance):
    required,extra_hashes=required_assets(binding,selection)
    available={row['path']:row for row in acceptance['assets']}
    for digest in extra_hashes:
        matches=[row for row in acceptance['assets'] if row['sha256']==digest]
        if not matches:raise ValueError('TitaNet frontend/model absent from accepted asset inventory')
        for row in matches:required[row['path']]=digest
    for name,expected in required.items():
        row=available.get(name)
        if row is None or expected is not None and row['sha256']!=expected:
            raise ValueError('Selected asset not covered by production acceptance: '+name)
        path=Path(name);resolved=path.resolve(strict=True)
        if str(resolved)!=row['resolved']:raise ValueError('Accepted asset resolution changed')
        before=resolved.stat()
        if before.st_size!=row['bytes']:raise ValueError('Accepted asset extent changed')
        with resolved.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        after=resolved.stat()
        if digest!=row['sha256'] or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('Accepted native asset bytes changed')
    return len(required)


def authorize_session(binding,selection,policy,*,verify_assets=False):
    chosen=selection.validate();values=policy.validate()
    kind,receipt=authorization(binding)
    verified=0
    if kind=='production':
        if selection_key(chosen) not in receipt['allowed_selections']:
            raise PermissionError('This profile/source/embedding was not selected for production acceptance')
        ceiling=receipt['limits']['maximum_developer_seconds' if values['developer_soak'] else 'maximum_session_seconds']
        if values.get('manual_stop') and receipt['limits'].get('manual_stop_storage_policy') is not True:
            raise PermissionError('Manual-stop storage admission has not been reviewed for this release')
        if ((not values.get('manual_stop') and values['maximum_session_seconds']>ceiling) or values['max_drain_seconds']>receipt['limits']['max_drain_seconds']
            or values['max_backlog_seconds']>receipt['limits']['max_backlog_seconds']):
            raise PermissionError('Session exceeds the accepted finite policy ceiling')
        if verify_assets:verified=_verify_assets(binding,selection,receipt)
    return dict(authorization_kind=kind,candidate_content_sha256=binding['candidate_content_sha256'],
                selection=chosen,policy=values,verified_asset_files=verified,native_qualified=False)


def require_service_room(unit_ownership_path,policy,*,now=None):
    receipt=bounded_json(unit_ownership_path,65536)
    if policy.manual_stop and receipt.get('lifetime_policy') == 'manual_stop_storage_guarded':
        if receipt.get('runtime_max_seconds') is not None or receipt.get('deadline_monotonic') is not None:
            raise PermissionError('Manual service lifetime receipt is inconsistent')
        return None
    deadline=receipt.get('deadline_monotonic')
    if type(deadline) not in (int,float) or not math.isfinite(deadline):
        raise PermissionError('Exact finite supervisor deadline is missing')
    remaining=deadline-(time.monotonic() if now is None else now)
    if remaining<policy.total_deadline_seconds+150:
        raise PermissionError('Reopen the launcher before Start; its remaining lifetime cannot cover this complete session')
    return remaining
