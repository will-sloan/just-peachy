"""Review actual installed entry derivation; README_FIELD_LIVE_CONTROLLER_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from field_live_controller_v1 import derive_field,derive_close,derive_presentation,BASE_MANIFEST


def code(value):
    if isinstance(value,list):return [code(n) for n in value]
    return ast.dump(value,include_attributes=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation',type=Path,required=True)
    parser.add_argument('--installed-mirror',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).parent
    admission=json.loads((args.preparation/'ADMISSION_REVIEW_V1.json').read_bytes())
    assert admission['native_dispatch'] is False
    assert datetime.now(timezone.utc)<datetime.fromisoformat(admission['expires_utc'])
    output=args.preparation/'COMPOSITION_SOURCE_REVIEW_V1.json'
    if output.exists():raise FileExistsError('Closed source review cannot be replayed')
    base=args.installed_mirror;raw=(base/'RELEASE_MANIFEST.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==BASE_MANIFEST
    manifest={r['path']:r for r in json.loads(raw)['files']}
    pins={}
    for relative in ('native/field_entry_v5.py','native/field_archive_v3.py','app/controller.py'):
        raw=(base/relative).read_bytes();digest=hashlib.sha256(raw).hexdigest()
        assert digest==manifest[relative]['sha256'];pins[relative]=digest
    old,new=derive_field((base/'native/field_entry_v5.py').read_bytes())
    a=next(n for n in old.body if isinstance(n,ast.ClassDef))
    b=next(n for n in new.body if isinstance(n,ast.ClassDef))
    original={n.name:n for n in a.body if isinstance(n,ast.FunctionDef)}
    changed={n.name:n for n in b.body if isinstance(n,ast.FunctionDef)}
    unchanged=[]
    for name,node in original.items():
        if name not in ('_sessions_initialize','_live_config'):
            assert code(node)==code(changed[name]);unchanged.append(name)
    assert code(original['_sessions_initialize'].body[1:])==code(changed['_sessions_initialize'].body[1:])
    assert {'_artifact_limits_for_epoch','_start_session','_do_switch','_do_select_backend','_do_enrollment_start'}<=set(unchanged)
    compile(ast.Module(body=[new],type_ignores=[]),'<actual-field-composition>','exec')
    old_close,new_close=derive_close((base/'app/controller.py').read_bytes())
    index=next(i for i,n in enumerate(new_close.body) if isinstance(n,ast.Try))
    assert code(old_close.body[:index])==code(new_close.body[:index])
    assert code(old_close.body[index+1:])==code(new_close.body[index+1:])
    assert code(old_close.body[index])==code(new_close.body[index].body[0])
    compile(ast.Module(body=[new_close],type_ignores=[]),'<actual-controller-close>','exec')
    old_presentation,new_presentation=derive_presentation((base/'app/controller.py').read_bytes())
    assert code(old_presentation.body[:-1])==code(new_presentation.body[:-1])
    assert code(old_presentation.body[-1].body[:-1])==code(new_presentation.body[-1].body[:-1])
    compile(ast.Module(body=[new_presentation],type_ignores=[]),'<actual-presentation>','exec')
    source=(root/'field_live_controller_v1.py').read_bytes()
    compile(source,'field_live_controller_v1.py','exec')
    tree=ast.parse(source)
    store=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='store_class')
    text=ast.unparse(store)
    assert "scope = dict(installed.__dict__, SessionStore=OneRunStore)" in text
    assert "ast.Module(body=[node], type_ignores=[])" in text
    receipt=dict(status='ACTUAL_FIELD_ENTRY_COMPOSITION_SOURCE_REVIEW_ONLY',as_of_utc=datetime.now(timezone.utc).isoformat(),
        host_affinity=[14],installed_source_pins=pins,unchanged_installed_field_methods=unchanged,
        installed_store_class_body_reused_without_edits=True,close_physical_cleanup_prefix_and_release_tail_exact=True,
        presentation_metadata_and_metrics_exact=True,constructors_executed=False,
        source_model_gui_capture=False,native_dispatch=False,
        source_sha256=hashlib.sha256(source).hexdigest(),
        remaining=['Whole physical output mapping and runtime path census','Bounded streamed complete host mirror',
                   'Fresh resource allowance/admission and actual integrated native passage',
                   'Review exact live D1 model/profile binding; no inference from saved-mode receipts'])
    raw=json.dumps(receipt,indent=2).encode();assert len(raw)<65536
    with output.open('xb') as handle:handle.write(raw)
    print(json.dumps(dict(status=receipt['status'],unchanged_field_methods=len(unchanged),native_dispatch=False)))


if __name__=='__main__':main()
