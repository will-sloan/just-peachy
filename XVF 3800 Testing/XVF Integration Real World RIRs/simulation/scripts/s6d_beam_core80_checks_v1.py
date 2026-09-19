"""Affected future core80 source gates only; see README_S6D_BEAM_CORE80_V1.md."""
import argparse
import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import traceback


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);sys.modules[name]=result;spec.loader.exec_module(result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    assert out.drive.casefold()=='g:' and 'review_fixtures' in out.parts and not out.exists()
    out.mkdir(parents=True);sys.path.insert(0,str(args.source_root))
    native=load(args.source_root/'s6d_beam_native_run_core80_v1.py','s6d_beam_native_run_core80_v1')
    queue=load(args.source_root/'s6d_beam_queue_prepare_core80_v1.py','core80_queue_checks')
    report=queue.P.R
    plan_ref=native.bind(report/'application/beam_execution_predecl_v3/PROSPECTIVE_PLAN.json');plan=native.verified(plan_ref)
    accepted_ref=native.bind(report/'runner/source_epoch_payload_v5/ROOT_SOURCE_ACCEPTANCE.json');accepted=native.verified(accepted_ref)
    wrapper=native.verified(accepted['wrapper_source_freeze']);exception=native.verified(accepted['exception'])
    original_queue=native.verified(native.bind(report/'runner/native_pilot_proposed_v1/PROPOSED_QUEUE.json'))
    base=dict(schema='s6d-beam-execution.v1',stage='main_core',declaration=plan_ref,
              runner_helper=native.bind(native.__file__),support={**plan['support'],'protocol':wrapper['wrapper'],'runner':wrapper['runner']},
              payload_cap_exception=accepted['exception'],payload_source_acceptance=accepted_ref,
              limits={**plan['execution_limits'],'max_new_payload_gib':80},
              **{k:deepcopy(plan[k]) for k in ('run_id','source_root','source_files','assets')})
    base['jobs']=[dict(t,profile_binding=plan['profile_binding'],gallery=plan['gallery'],settings=plan['settings'])
                  for t in plan['tasks'] if t['stage']=='main_core']
    rows=[]

    def check(name,callback):
        try:callback();rows.append(dict(name=name,status='PASS'))
        except BaseException:rows.append(dict(name=name,status='FAIL',error=traceback.format_exc()))

    def reject(callback):
        try:callback()
        except (ValueError,KeyError,TypeError):return
        raise AssertionError('Expected rejection')

    def good():
        native.core_scope(base);authority=queue.payload_sources(base)
        assert authority['runner']==wrapper['runner'] and authority['wrapper']==wrapper['wrapper']
        assert authority['guards'][:4]==[accepted['exception']]+[exception[k] for k in ('contract','forecast','prior_runner')]
        assert len(authority['guards'])==7
    check('exact_original_core96_and_all_four_payload_authorities',good)

    def excluded_modes():
        for mode in ('calibration_collection','stream_diagnostic'):
            value=deepcopy(base);value['jobs'][0]['mode']=mode;reject(lambda:native.core_scope(value))
        for stage in ('C_collection','stream_diagnostics'):
            value=deepcopy(base);value['stage']=stage;reject(lambda:native.core_scope(value))
        value=deepcopy(base);value['jobs']=value['jobs'][:12];reject(lambda:native.core_scope(value))
    check('C12_diagnostics_and_partial_core_populations_reject',excluded_modes)

    def cell_membership():
        for field,value in (('mode','same_pass_auto_control'),('case_id','foreign_case'),('capture_profile','P_SCAN6'),('asr_raw_stream','focus0_asr_raw')):
            changed=deepcopy(base);changed['jobs'][1][field]=value;reject(lambda:native.core_scope(changed))
        changed=deepcopy(base);changed['jobs'][1]['job_id']=changed['jobs'][0]['job_id'];reject(lambda:native.core_scope(changed))
    check('matched_two_modes_MAIN_auto_input_and_unique96_required',cell_membership)

    def allocation():
        for key,value in (('serial_jobs',False),('maximum_resident_stacks',2),('maximum_identity_focus_states',3),('cpu_affinity',[0,1,2,3]),('cpu_threads_each',2),('max_new_payload_gib',40),('max_new_payload_gib',80.0),('max_new_payload_gib',True)):
            changed=deepcopy(base);changed['limits'][key]=value;reject(lambda:native.core_scope(changed))
    check('one_serial_stack_fixed_affinity_and_integer80_required',allocation)

    def missing_authorities():
        for field in ('payload_cap_exception','payload_source_acceptance'):
            changed=deepcopy(base);changed.pop(field);reject(lambda:queue.payload_sources(changed))
            changed=deepcopy(base);changed[field]['sha256']='f'*64;reject(lambda:queue.payload_sources(changed))
    check('missing_or_changed_manifest_authorities_reject',missing_authorities)

    def old_support():
        for field in ('runner','protocol'):
            changed=deepcopy(base);changed['support'][field]={'path':'foreign','sha256':'f'*64,'bytes':1}
            reject(lambda:queue.payload_sources(changed))
    check('old_or_foreign_runner_protocol_support_rejects',old_support)

    def plan_order():
        changed=deepcopy(base);changed['declaration']['sha256']='f'*64;reject(lambda:queue.payload_sources(changed))
        changed=deepcopy(base);changed['jobs'][0],changed['jobs'][1]=changed['jobs'][1],changed['jobs'][0]
        reject(lambda:queue.payload_sources(changed))
    check('exact_original_declaration_and_order_required',plan_order)

    def scientific_context():
        for field in ('profile_binding','gallery','settings'):
            changed=deepcopy(base);changed['jobs'][0][field]={};reject(lambda:queue.payload_sources(changed))
        for field in ('source_root','source_files','assets'):
            changed=deepcopy(base);changed[field]=[];reject(lambda:queue.payload_sources(changed))
        for field in ('evidence','native_loop'):
            changed=deepcopy(base);changed['support'][field]={};reject(lambda:queue.payload_sources(changed))
    check('original_profile_gallery_settings_native_and_application_sources_required',scientific_context)

    def unchanged_limits():
        for key,value in (('cell_timeout_sec',901),('source_paced',False),('no_overlap_with_active176',False)):
            changed=deepcopy(base);changed['limits'][key]=value;reject(lambda:queue.payload_sources(changed))
    check('no_timeout_pacing_or_nonoverlap_limit_relaxation',unchanged_limits)

    def policy():
        authority=queue.payload_sources(base);old=original_queue['payload_policy'];new=queue.payload_policy(old,authority)
        assert new=={**old,'max_new_payload_bytes':80*2**30,'cap_exception':accepted['exception']}
        assert old==original_queue['payload_policy'] and old['max_new_payload_bytes']==40*2**30
        for roots in (old['new_payload_roots'][:-1],list(reversed(old['new_payload_roots']))):
            reject(lambda:queue.payload_policy({**old,'new_payload_roots':roots},authority))
        reject(lambda:queue.payload_policy({**old,'max_new_payload_bytes':79*2**30},authority))
    check('payload_only_exact80_delta_and_all_shared_roots_preserved',policy)

    parent_runner=report/'application/beam_execution_predecl_v3/helpers/s6d_beam_native_run_v1.py'
    parent_queue=queue.P.SIM/'scripts/s6d_beam_queue_prepare_v1.py'
    def ast_preserved():
        assert native.bind(parent_runner)['sha256']=='6f7162900dbf19ff1876c5bbb09720a16081d1a330319ac8cc6e1f6ef61dfbb4'
        old=ast.parse(parent_runner.read_text());new=ast.parse(Path(native.__file__).read_text())
        def definitions(tree):return {n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        before,after=definitions(old),definitions(new)
        assert set(after)==set(before)|{'core_scope'}
        after['run'].body=[n for n in after['run'].body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='core_scope')]
        for name in before:assert ast.dump(before[name],include_attributes=False)==ast.dump(after[name],include_attributes=False),name
        prior=load(parent_runner,'core80_prior_ast_only')
        assert {k:v for k,v in native.PINS.items() if k!='protocol'}=={k:v for k,v in prior.PINS.items() if k!='protocol'}
    check('all_scientific_C_calibration_multistream_STOP_and_completion_AST_unchanged',ast_preserved)

    def queue_invariants():
        assert native.bind(parent_queue)['sha256']=='99ca383f170f43ed1904d164e27d9c87bebeb07dd346b1d9ec237b9f86bac701'
        old=ast.parse(parent_queue.read_text());new=ast.parse(Path(queue.__file__).read_text())
        def assignments(tree,name):
            return [ast.dump(n.value,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
        for name in ('fields','audit_fields','artifacts'):assert assignments(old,name)==assignments(new,name),name
        def jobs(tree):return [ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='append' and isinstance(n.func.value,ast.Subscript) and isinstance(n.func.value.value,ast.Name) and n.func.value.value.id=='q']
        assert jobs(old)==jobs(new)
        source_lists=[n.value for n in ast.walk(new) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='sources' for t in n.targets) and isinstance(n.value,ast.List)]
        assert any(isinstance(x,ast.Starred) and ast.unparse(x.value)=="authorities['guards']" for x in source_lists[0].elts)
        proposals=[n for n in ast.walk(new) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='dict' and any(k.arg=='approved_job_sha256' for k in n.keywords)]
        assert len(proposals)==1
        fields={k.arg:k.value for k in proposals[0].keywords}
        assert isinstance(fields['approved_job_sha256'],ast.List) and fields['approved_job_sha256'].elts==[]
        assert ast.unparse(fields['payload_cap_exception'])=="authorities['exception']"
    check('literal_job_artifact_timeouts_and_all_job_authority_guards_preserved',queue_invariants)
    result=dict(status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',tests=rows,passed=sum(r['status']=='PASS' for r in rows),total=len(rows),
                source_bindings=[native.bind(args.source_root/name) for name in ('s6d_beam_native_run_core80_v1.py','s6d_beam_queue_prepare_core80_v1.py','s6d_beam_core80_checks_v1.py','README_S6D_BEAM_CORE80_V1.md')],
                prior_sources=[native.bind(parent_runner),native.bind(parent_queue)],declaration=plan_ref,source_acceptance=accepted_ref,
                production_manifests_or_queues_created=0,actual_outputs_or_audio_read=0,models=0,process_queries=0,hardware_or_UI=0,
                source_scientific_change=False,existing_C12_or_core_sources_changed=False,original_broad_suites_rerun=False)
    native.save(out/'RECEIPT.json',result);print(json.dumps(result,indent=2));return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
