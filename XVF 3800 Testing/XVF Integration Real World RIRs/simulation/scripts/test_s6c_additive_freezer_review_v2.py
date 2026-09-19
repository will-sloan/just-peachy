"""Model-free additive-freezer review. See README_S6C_ADDITIVE_FREEZER_REVIEW_V2.md."""
from __future__ import annotations
import argparse
import ast
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch

import s6c_common as c
import s6c_freeze_v2 as freezer
import s6c_policy_matrix_v4 as matrix


def run(output):
    checks=[]
    def yes(name, predicate):
        if not predicate: raise AssertionError(name)
        checks.append(dict(name=name,status='PASS'))
    def rejects(name, callback):
        try: callback()
        except (ValueError,RuntimeError,KeyError,FileNotFoundError) as exc:
            checks.append(dict(name=name,status='PASS',rejected_with=type(exc).__name__,reason=str(exc)))
        else: raise AssertionError('Accepted forbidden case: '+name)
    def redigest(spec):
        spec['execution_digest']=c.digest({k:spec[k] for k in ('execution_files','assets','versions','state_policy')})
        return spec
    source_paths=[Path(freezer.__file__),Path(matrix.__file__)]
    trees=[ast.parse(p.read_text(encoding='utf-8')) for p in source_paths]
    yes('both_reviewed_modules_parse',len(trees)==2)
    source=trees[0]
    fn=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='freeze')
    early=ast.FunctionDef(name='early_guard',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='epoch'),ast.arg(arg='extra_scripts')],
        kwonlyargs=[],kw_defaults=[],defaults=[]),body=deepcopy(fn.body[:2]),decorator_list=[])
    early_namespace=dict(vars(freezer));exec(compile(ast.fix_missing_locations(ast.Module(body=[early],type_ignores=[])),
        str(source_paths[0])+':early_guard','exec'),early_namespace)
    early_namespace['early_guard']('fixture',('one.py','two.py'));yes('early_extra_guard_accepts_plain_names',True)
    for name in ('../bad.py','sub/bad.py','C:/bad.py','wrong.md'):
        rejects('early_extra_guard_rejects_'+name,lambda n=name:early_namespace['early_guard']('fixture',(n,)))
    branch=next(n for n in fn.body if isinstance(n,ast.If) and ast.unparse(n.test)=='target.exists()')
    # Execute only the existing-input guard body copied directly from the parsed
    # reviewed source. Never invoke freeze(), save(), admit_work() or copytree().
    guard=ast.FunctionDef(name='existing_guard',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg=x) for x in
        ('epoch','registry_binding','gallery_binding','previous','target','extra_scripts')],kwonlyargs=[],kw_defaults=[],defaults=[]),
        body=deepcopy(branch.body),decorator_list=[])
    guard_tree=ast.fix_missing_locations(ast.Module(body=[guard],type_ignores=[]))
    namespace=dict(vars(freezer));exec(compile(guard_tree,str(source_paths[0])+':existing_guard','exec'),namespace)
    existing=namespace['existing_guard']
    yes('extracted_existing_branch_has_no_publication_calls',not any(isinstance(n,ast.Call) and
        ast.unparse(n.func) in ('save','admit_work','shutil.copytree','shutil.copy2') for n in ast.walk(guard_tree)))
    original=c.verified(c.bind(c.REPORT/'EPOCH2_EXECUTION_MANIFEST.json',
        '1f7f0e10186eb1187d05d9be258372d6dfbe39ec3741c2ce2976a2ca3d005cdb'))
    freezer.check_environment(original);yes('actual_original_interpreter_packages_asset_bytes',True)
    matrix.assert_compatible_epochs(original,original);yes('actual_epoch2_self_compatibility',True)
    epoch3=c.REPORT/'EPOCH3_EXECUTION_MANIFEST.json'
    if epoch3.exists():rejects('actual_epoch3_worker_drift_rejected',lambda:matrix.assert_compatible_epochs(original,c.read(epoch3)))
    registry5=c.read(c.REPORT/'EFFECTIVE_PROFILE_REGISTRY_V5.json')
    registry4=c.read(c.REPORT/'EFFECTIVE_PROFILE_REGISTRY_V4.json')
    key=lambda r:(r['candidate_id'],r['asr_tap'],r['identity_tap'])
    old={key(r):r for r in registry4['profiles']};new={key(r):r for r in registry5['profiles']}
    yes('V5_unique_route_keys',len(new)==len(registry5['profiles']))
    yes('V5_preserves_every_V4_route_exactly',all(new.get(k)==v for k,v in old.items()))
    yes('V5_declares_190_executable_candidates',registry5['candidate_count']==190 and len({r['candidate_id'] for r in new.values()})==190)
    yes('V5_376_effective_routes',len(new)==376)
    yes('V5_profile_bindings_match_payload',all(c.verified(r['profile_binding'])==r['profile'] for r in registry5['profiles']))
    fixture_parent=c.STAGING/'component_review_fixtures';fixture_parent.mkdir(parents=True,exist_ok=True)
    # Temporary tiny fixture trees only. These are not executable epochs, and
    # contain no actual model, user gallery, production audio or native jobs.
    with tempfile.TemporaryDirectory(prefix='freezer_v2_',dir=fixture_parent) as temp:
        root=Path(temp);namespace['STAGING']=root
        def build_tree(folder):
            app=folder/'app/edge_speech_pipeline';scripts=folder/'scripts';app.mkdir(parents=True);scripts.mkdir()
            (app/'fixture.py').write_text('FIXTURE = 1\n',encoding='utf-8')
            (scripts/'s6c_execution.py').write_text('def extract(value):\n    return value\n',encoding='utf-8')
            (scripts/'s6c_common.py').write_text('FIXTURE_COMMON = 1\n',encoding='utf-8')
            (scripts/'requested_extra.py').write_text('FIXTURE_EXTRA = 1\n',encoding='utf-8')
            return [c.bind(p) for p in sorted(folder.rglob('*.py'))]
        previous_root=root/'previous_fixture';target_root=root/'fixture'
        previous=dict(root=str(previous_root),execution_files=build_tree(previous_root),assets=[],versions={},python='fixture',
            state_policy={'fixture':True},input_index={'fixture':'input'},scene_manifest={'fixture':'scene'})
        previous=redigest(previous)
        registry_path=root/'registry.json';c.save(registry_path,{'status':'VALIDATED_REAL_V3_API','profiles':[{'fixture':1}]})
        gallery_path=root/'gallery.json';c.save(gallery_path,{'rows':[]})
        rb=c.bind(registry_path);gb=c.bind(gallery_path)
        previous.update(profiles=[{'fixture':1}],effective_profile_registry=rb)
        target=redigest(dict(previous,root=str(target_root),epoch='fixture',execution_files=build_tree(target_root),
            documentation_files=[],profiles=[{'fixture':1}],effective_profile_registry=rb,gallery_index=gb))
        target_path=root/'guard_input.json'
        def guard_call(spec,extras=()):
            c.save(target_path,spec);return existing('fixture',rb,gb,previous,target_path,extras)
        guard_call(target,('requested_extra.py',));yes('actual_extracted_existing_guard_accepts_exact_input',True)
        for field,value in [('epoch','wrong'),('root',str(root/'wrong')),('execution_digest','0'*64),
            ('profiles',[]),('assets',[{'changed':1}]),('python','changed'),('versions',{'changed':'1'}),
            ('state_policy',{}),('input_index',{}),('scene_manifest',{}),('effective_profile_registry',{}),('gallery_index',{})]:
            changed=deepcopy(target);changed[field]=value
            if field in ('assets','versions','state_policy'):redigest(changed)
            rejects('existing_guard_rejects_'+field,lambda s=changed:guard_call(s))
        rejects('existing_guard_missing_requested_extra',lambda:guard_call(target,('absent.py',)))
        extra=target_root/'app/edge_speech_pipeline/unbound.py';extra.write_text('EXTRA=1\n',encoding='utf-8')
        rejects('existing_guard_unbound_app_inventory',lambda:guard_call(target));extra.unlink()
        app=target_root/'app/edge_speech_pipeline/fixture.py';saved=app.read_bytes();app.write_bytes(b'FIXTURE=2\n')
        rejects('existing_guard_changed_app_bytes',lambda:guard_call(target));app.write_bytes(saved)
        matrix.assert_compatible_epochs(target,previous);yes('compatible_separate_fixture_roots',True)
        for field,value in [('execution_digest','0'*64),('assets',[{'changed':1}]),('versions',{'changed':'1'}),
            ('python','different'),('input_index',{}),('scene_manifest',{}),('state_policy',{}),('profiles',[])]:
            changed=deepcopy(target);changed[field]=value
            if field!='execution_digest':redigest(changed)
            rejects('compatible_rejects_'+field,lambda s=changed:matrix.assert_compatible_epochs(s,previous))
        for name in ('s6c_execution.py','s6c_common.py'):
            path=target_root/'scripts'/name;saved=path.read_bytes()
            path.write_bytes(saved+b'\nTOP_LEVEL_CHANGED=1\n')
            changed=deepcopy(target)
            changed['execution_files']=[c.bind(path) if Path(b['path'])==path else b for b in changed['execution_files']];redigest(changed)
            rejects('compatible_rejects_whole_module_'+name,lambda s=changed:matrix.assert_compatible_epochs(s,previous))
            path.write_bytes(saved)
        changed=deepcopy(previous);changed['execution_files'][0]['sha256']='0'*64;redigest(changed)
        rejects('compatible_rehashes_source_bytes',lambda:matrix.assert_compatible_epochs(target,changed))
        with patch.object(freezer,'EDGE',root/'not_python.exe'):
            rejects('environment_exact_interpreter_path',lambda:freezer.check_environment(original))
        changed=deepcopy(original);changed['python']='different'
        rejects('environment_python_string_drift',lambda:freezer.check_environment(changed))
        changed=deepcopy(original);changed['versions']['numpy']='different'
        rejects('environment_package_drift',lambda:freezer.check_environment(changed))
    output=Path(output)
    result=dict(schema='s6c_additive_freezer_component_review.v2',status='PASS',utc=c.utc(),checks=checks,
        check_count=len(checks),sources=[c.bind(p) for p in source_paths],test_source=c.bind(__file__),
        test_readme=c.bind(Path(__file__).with_name('README_S6C_ADDITIVE_FREEZER_REVIEW_V2.md')),
        reviewed_documentation=[c.bind(c.SIM/'scripts'/n) for n in ('README_S6C_FREEZE_V2.md','README_S6C_POLICY_MATRIX_V4.md')],
        original_epoch=c.bind(c.REPORT/'EPOCH2_EXECUTION_MANIFEST.json'),registry=c.bind(c.REPORT/'EFFECTIVE_PROFILE_REGISTRY_V5.json'),
        registry_counts=dict(candidates=registry5['candidate_count'],route_rows=len(new),preserved_V4_route_rows=len(old)),
        fixture_development_note='Initial assertion incorrectly expected all 234 historical+current scorer definitions in the executable registry. Corrected to 190 executable candidates / 376 routes; no reviewed implementation change or model execution.',
        scope='Actual environment/source/hash checks; synthetic separate-root compatibility and exact AST-extracted existing-target guards. No freeze invocation, execution epoch creation, model import/inference, source mutation or native job launch.',
        limits=['Fresh copy/publication path reviewed statically, not executed here.','Invocation-boundary hashes do not provide an atomic global snapshot against later external mutation.',
            'Gallery ownership/eligibility remains independently reviewed by the source owner; this check verifies profile byte bindings and additive route preservation.'])
    return c.save(output,result,immutable=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    print(c.json.dumps(run(p.parse_args().output),indent=2))
