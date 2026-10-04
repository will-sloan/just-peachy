"""Two explicit admission paths over the same frozen runtime. README_OPTIONAL_REFINER.md."""
from pathlib import Path
from dataclasses import replace
import hashlib
import json
from optional_refiner_admission import SCHEMA,operational_binding_sha256,validate_admission


def _raw(path,sha):
    file=Path(path)
    if file.is_symlink() or not file.is_file() or file.stat().st_size>65536:raise ValueError('Bounded regular measured-refiner receipt required')
    raw=file.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Reviewed-refiner receipt changed')
    return raw


def validate_references(rows):
    from profiles import RuntimeSelection,SessionPolicy
    from release_authorization import sha,HOME
    from pathlib import PurePosixPath
    if type(rows) is not list or len(rows)>64:raise ValueError('Bounded reviewed optional admission references required')
    seen=set()
    for value in rows:
        if type(value) is not dict or set(value)!={'selection','policy','path','sha256','asset_inventory_sha256'}:
            raise ValueError('Exact reviewed optional-refiner reference shape required')
        selection=RuntimeSelection(**value['selection']);selection.validate()
        policy=SessionPolicy(**value['policy']);policy.validate()
        if value['selection']!=selection.validate() or value['policy']!=policy.validate():
            raise ValueError('Proof reference must preserve every explicit selection and policy field')
        if not selection.optional_d1_refiner:raise ValueError('Optional proof reference must explicitly select the child')
        for key in ('sha256','asset_inventory_sha256'):sha(value[key])
        path=value['path']
        if type(path) is not str or not path.startswith(HOME) or '..' in PurePosixPath(path).parts or PurePosixPath(path).as_posix()!=path:
            raise ValueError('Exact reviewed native proof path required')
        key=json.dumps([selection.validate(),policy.validate()],sort_keys=True)
        if key in seen:raise ValueError('Duplicate optional selection/policy receipt')
        seen.add(key)
    return rows


def reference(receipt,selection,policy=None):
    matches=[item for item in validate_references(receipt.get('optional_refiner_admissions',[]))
             if item.get('selection')==selection.validate() and (policy is None or item.get('policy')==policy.validate())]
    if not matches or policy is not None and len(matches)!=1:
        raise ValueError('No unique exact-selection/policy reviewed optional-refiner admission')
    value=matches[0]
    if set(value)!={'selection','policy','path','sha256','asset_inventory_sha256'}:
        raise ValueError('Exact reviewed optional-refiner reference shape required')
    return value


def expected_pins(binding,ref):
    return dict(candidate_content_sha256=binding['candidate_content_sha256'],
        installed_manifest_sha256=binding['installed_manifest_sha256'],
        operational_binding_sha256=operational_binding_sha256(binding),
        selected_asset_inventory_sha256=ref['asset_inventory_sha256'])


def reviewed_options(binding,selection,policy):
    from release_authorization import authorization
    _,authorization_receipt=authorization(binding)
    ref=reference(authorization_receipt,selection,policy)
    from release_authorization import selected_inventory_sha256
    if selected_inventory_sha256(binding,selection,authorization_receipt.get('assets',[]))!=ref['asset_inventory_sha256']:
        raise ValueError('Reviewed receipt does not match exact selected native inventory')
    raw=_raw(ref['path'],ref['sha256'])
    from release_authorization import strict
    row=strict(raw)
    if row.get('schema')!=SCHEMA:raise ValueError('Normal GUI requires measured v2 admission, never a qualification permit')
    measured=row.get('measured',{})
    # Historical evidence validation uses the receipt's measured MemTotal only.
    # Current-machine RAM/phase admission is independently checked by the worker.
    validate_admission(raw,ref['sha256'],selection,policy,expected_pins(binding,ref),0,
        physical_ram_bytes=measured.get('total_ram_bytes'),phase='historical_evidence')
    return ref,raw


def ui_eligibility(binding,selection=None,policy=None):
    if selection is None:return False,'Choose an explicit selection; combined admission is pending'
    if selection.diarizer!='pyannote' or not selection.allow_experimental:
        return False,'Optional D1 requires experimental Pyannote primary'
    try:
        from profiles import SessionPolicy
        target=replace(selection,optional_d1_refiner=True)
        reviewed_options(binding,target,policy or SessionPolicy())
    except (ValueError,PermissionError,OSError,KeyError,TypeError) as error:
        return False,'Optional D1 unavailable: '+str(error)[:180]
    return True,'Reviewed combined admission available; current resources checked at Start'


def request_receipt(binding,selection,policy):
    if not selection.optional_d1_refiner:return None
    ref,_=reviewed_options(binding,selection,policy)
    return {key:ref[key] for key in ('path','sha256','asset_inventory_sha256')}


def worker_options(binding,request,selection,policy,owner_directory,identity,authorization):
    qualified=request.get('optional_refiner_qualification')
    measured=request.get('optional_refiner_admission')
    if not selection.optional_d1_refiner:
        if qualified is not None or measured is not None:raise ValueError('Optional settings provided without explicit mode')
        return None
    if qualified is not None:
        if measured is not None:raise ValueError('First qualification and measured reuse are distinct entry points')
        from optional_refiner_qualification import initialize
        return initialize(request,binding,owner_directory,identity,authorization)
    ref,raw=reviewed_options(binding,selection,policy)
    expected={key:ref[key] for key in ('path','sha256','asset_inventory_sha256')}
    if measured!=expected:raise ValueError('Worker request differs from exact reviewed optional admission')
    return dict(binding_path=request['binding'],binding_sha256=request['binding_sha256'],
        admission_raw=raw,admission_sha256=ref['sha256'],expected_pins=expected_pins(binding,ref),
        unit=request['unit'],reserved_output_bytes=4*1024**2)
