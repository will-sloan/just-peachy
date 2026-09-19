"""Model-free endpoint dependency/grid guards; README_S6C_ENDPOINT_DEPENDENCY_V1.md."""
from __future__ import annotations
import ast
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import sys
import s6c_orchestrator_scan_v5 as overlay


def main():
    sb,spec,common,execution=overlay.load_native('epoch6')
    report=common.REPORT
    registry=common.verified(spec['effective_profile_registry'])
    old=common.verified(registry['parent_registry'])
    amendment=common.verified(registry['endpoint_registration'])
    manifest_path=report/'jobs/epoch6/endpoint_advice_v1.json'
    manifest=common.read(manifest_path)
    rows=manifest['jobs'];checks=[]
    assert registry['profiles'][:384]==old['profiles'] and len(registry['profiles'])==388
    checks.append('384 prior route objects preserved, four additive routes, 240 total labels')
    cases=sorted(common.verified(spec['panel'])['case_ids'])
    expected={(cid,case,tap,tap) for cid in ('C195','C196') for case in cases for tap in ('O0','O1')}
    actual={(j['candidate_id'],j['case_id'],j['asr_tap'],j['identity_tap']) for j in rows}
    assert len(rows)==len(actual)==len(expected)==224 and actual==expected
    assert len(amendment['empty_music_case_ids'])==11 and set(amendment['empty_music_case_ids'])<=set(cases)
    checks.append('Exact 224 unique jobs, fixed 56 cases, both routes and all 11 empty/music cases')
    inputs={(r['case_id'],r['stream']):r for r in common.verified(spec['input_index'])['rows']}
    profiles={(p['candidate_id'],p['asr_tap'],p['identity_tap']):p for p in spec['profiles']}
    for job in rows:
        p=profiles[job['candidate_id'],job['asr_tap'],job['identity_tap']]
        parent=profiles[p['parent'],p['asr_tap'],p['identity_tap']]
        restored=deepcopy(p['profile'])
        restored['profile_id']=parent['profile']['profile_id'];restored['xvf']['mode']=parent['profile']['xvf']['mode']
        assert restored==parent['profile']
        assert p['neural_dependency']=='FULL_PROFILE_AND_CUES' and p['cue_condition']=='REAL_ALIGNED_CUES'
        assert job['identity']==execution.job_identity(spec,p,job['asr_audio'],job['identity_audio'],job['telemetry'],job['gallery'],False)
        assert job['job_key']==common.digest(job['identity']) and job['telemetry']==inputs[job['case_id'],job['asr_tap']]['telemetry']
        assert job['gallery'] is None and job['identity']['gain']['adapter']==1. and job['identity']['inner_threads']==1
        assert not Path(job['folder']).exists()
    checks.append('All 224 full native identities, exact parent numeric settings, real tap cues, gain, empty gallery and unstarted folders')
    matrix_binding=next(b for b in spec['execution_files'] if Path(b['path']).name=='s6c_policy_matrix_v4.py')
    common.bind(matrix_binding['path'],matrix_binding['sha256'])
    module_spec=importlib.util.spec_from_file_location('endpoint_bound_matrix',matrix_binding['path'])
    matrix=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(matrix)
    for cid in ('C195','C196'):
        for tap in ('O0','O1'):
            p=profiles[cid,tap,tap];parent=profiles[p['parent'],tap,tap]
            assert matrix.exogenous_key(p['profile'])==common.digest(dict(full=p['profile']))
            assert matrix.exogenous_key(p['profile'])!=matrix.exogenous_key(parent['profile'])
    checks.append('Frozen actual matrix exogenous key binds full endpoint profile and rejects original N01 parent key')
    # Execute exact guard statements from the frozen policy-matrix run, without
    # its filesystem/output/replay loop or neural imports.
    run=next(n for n in ast.parse(Path(matrix_binding['path']).read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='run')
    loop=next(n for n in run.body if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple) and any(isinstance(x,ast.Name) and x.id=='gal_binding' for x in n.target.elts))
    guard=next(n for n in loop.body if isinstance(n,ast.If) and isinstance(n.test,ast.BoolOp) and isinstance(n.test.values[0],ast.Name) and n.test.values[0].id=='full_dependent')
    code=compile(ast.Module(body=[guard],type_ignores=[]),matrix_binding['path'],'exec')
    p=profiles['C195','O0','O0'];job=next(j for j in rows if j['candidate_id']=='C195' and j['asr_tap']=='O0')
    base=dict(full_dependent=True,p=p,evidence=dict(identity=deepcopy(job['identity'])),cue_binding=job['telemetry'],gal_binding=None)
    exec(code,deepcopy(base));checks.append('Exact frozen matrix full-dependency guard accepts matching profile/cue/gallery')
    for field in ('profile','telemetry','gallery'):
        bad=deepcopy(base);bad['evidence']['identity'][field]=None
        if field=='gallery':bad['evidence']['identity'][field]={'fixture':'wrong'}
        try:exec(code,bad)
        except ValueError:checks.append('Exact frozen matrix guard rejects changed native '+field)
        else:raise AssertionError('Full guard admitted '+field)
    execution.validate_job(spec,job,inputs,check_assets=False);checks.append('Actual native admission accepts unchanged job')
    mutations=[]
    bad=deepcopy(job);bad['identity']['profile']['xvf']['mode']='none';mutations.append(('unchanged key changed profile',bad))
    bad=deepcopy(job);bad['identity']['cue_condition']='CUES_OFF';bad['job_key']=common.digest(bad['identity']);mutations.append(('rekeyed wrong cue condition',bad))
    bad=deepcopy(job);bad['profile']['asr']['decoding_method']='modified_beam_search';bad['identity']['profile']=deepcopy(bad['profile']);bad['job_key']=common.digest(bad['identity']);mutations.append(('rekeyed unregistered decoder',bad))
    bad=deepcopy(job);bad['telemetry']=None;bad['identity']['telemetry']=None;bad['job_key']=common.digest(bad['identity']);mutations.append(('rekeyed absent real telemetry',bad))
    bad=deepcopy(job);bad['candidate_id']='C065';mutations.append(('parent ID with endpoint profile',bad))
    for title,bad in mutations:
        try:execution.validate_job(spec,bad,inputs,check_assets=False)
        except ValueError:checks.append('Actual native admission rejects '+title)
        else:raise AssertionError(title)
    receipt=dict(status='PASS_MODEL_FREE_DEPENDENCY_AND_GRID',checks=checks,check_count=len(checks),native_jobs_checked=224,neural_invocations=0,
        source=common.bind(__file__),readme=common.bind(Path(__file__).with_name('README_S6C_ENDPOINT_DEPENDENCY_V1.md')),
        execution_manifest=sb,registry=spec['effective_profile_registry'],amendment=registry['endpoint_registration'],jobs=common.bind(manifest_path),
        frozen_matrix=matrix_binding,frozen_execution=next(b for b in spec['execution_files'] if Path(b['path']).name=='s6c_execution.py'),
        scope='Actual native validate_job/job_identity and matrix exogenous_key; exact matrix guard AST executed in isolation. No native run, model construction, replay or alternative transcript inference. Changed on-disk dependencies remain subject to unchanged native hash admission.')
    print(json.dumps(common.save(report/'endpoint_factorial_v1/DEPENDENCY_CHECKS.json',receipt,immutable=True)))


if __name__=='__main__':
    sys.dont_write_bytecode=True
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    main()
