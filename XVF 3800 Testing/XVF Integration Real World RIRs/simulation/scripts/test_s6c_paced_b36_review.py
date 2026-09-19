"""Independent model-free B36 admission review; see README_TEST_S6C_PACED_B36_REVIEW.md."""
from __future__ import annotations
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
PAYLOAD=Path('G:/Just_Peachy_S6C/20260910T123540Z')
EXPECTED='dd55f7fb64182e7c90eca2cbaf58fe41b1589937e14c96ad38f7b5dae2bee14f'
SOURCE='8d60474f0517b5f43dbdb64a5194829241ded8d5acdbd622ec3bef6851152abd'
bindings=[];checks=[]
def check(condition,label):
    if not condition:raise AssertionError(label)
    checks.append(label)
def read(path,expected=None):
    path=Path(path);raw=path.read_bytes()
    b=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    if expected:check(b['sha256']==expected,'exact bytes: '+path.name)
    bindings.append(b);return raw,b
def bound(b):
    raw,actual=read(b['path'],b['sha256'])
    check(actual['bytes']==b['bytes'],'exact length: '+Path(b['path']).name)
    return json.loads(raw)
def main():
    path=PAYLOAD/'paced_controls/b36_v1/MANIFEST.json';raw,manifest_binding=read(path,EXPECTED);plan=json.loads(raw)
    source_raw,source_binding=read(SIM/'scripts/s6c_paced_b36_v1.py',SOURCE)
    original_raw,original_binding=read(SIM/'scripts/s6c_paced_controls.py','abacc5db48137a808a9417c26e44b921be817dda4e6271efe7a9fb7dfd7bf6a9')
    read(SIM/'scripts/README_S6C_PACED_B36_V1.md','38d04677f9be2a6a7c603e229d2e90e73785f6a04bf8cd821a2e7f2ac4d2c23c')
    fixture=bound(dict(path=str(REPORT/'paced_controls/B36_ADAPTER_CHECKS_V1.json'),bytes=Path(REPORT/'paced_controls/B36_ADAPTER_CHECKS_V1.json').stat().st_size,sha256='2092d314d7dcd2c3ff6de398011727f7283528530b19c4eeda3cfe06c6bf2494'))
    check(fixture['status']=='PASS' and fixture['checks']==23 and fixture['native_calls']==0,'owner23 model-free checks')
    check(fixture['source']==source_binding,'owner checks exact current helper')
    base=bound(plan['source_controls_plan']);sealed=bound(plan['source_sealed_index']);epoch=bound(plan['historical_epoch'])
    check(plan['source_controls_plan']['sha256']=='22033c693b7009eec2c86e1c0b2235826984bbfb8cacc914730216204893de86','exact original80 plan')
    check(plan['source_sealed_index']['sha256']=='2ce021fccd0cff0d60d699c2a56e541949fd1348bf529b6f12ba8ca796336c8e','sealed S6B authority')
    check(any(all(a.get(k)==plan['historical_epoch'][k] for k in ('path','sha256','bytes')) for a in sealed['artifacts']),'epoch in sealed artifact index')
    registry=bound(epoch['effective_profile_registry']);entries=[e for e in registry['profiles'] if e['profile_id']=='B36']
    check(len(entries)==1,'one authoritative B36 entry');entry=entries[0];profile=bound(entry['file_binding'])
    check(profile==entry['profile']==plan['b36_registry_entry']['profile'],'exact complete B36 numeric profile')
    check(plan['b36_registry_entry']==entry,'exact registry entry')
    check(profile['tracker']['mode']=='original_common' and profile['tracker']['max_tracks']==256 and not profile['tracker']['cues_enabled'] and profile['xvf']['mode']=='none','old common tracker256 cue-off')
    check(profile['input']==dict(tap='mono',gain=1.0,already_gained=True),'once-gained native input')
    oldtree=ast.parse(original_raw);newtree=ast.parse(source_raw)
    old={n.name:n for n in oldtree.body if isinstance(n,ast.FunctionDef)}
    new={n.name:n for n in newtree.body if isinstance(n,ast.FunctionDef)}
    for name in fixture['original_functions']:
        check(ast.dump(old[name],include_attributes=False)==ast.dump(new[name],include_attributes=False),'unchanged function '+name)
    # Compile only the actual pure guards; do not import native driver, coordinator or models.
    ns=dict(json=json,hashlib=hashlib,datetime=datetime,timezone=timezone,Path=Path,re=re,
            CONTROLS=('B36',),SCHEMA='s6c-historical-paced-b36.v1',PAYLOAD=PAYLOAD,
            RESOURCE_LIMITS=dict(c_free_min_bytes=50*2**30,g_free_min_bytes=75*2**30,host_available_min_bytes=4*2**30,new_output_cap_bytes=120*2**30,pending_cell_reserve_bytes=512*2**20),
            GLOBAL_DEADLINE=datetime(2026,9,13,11,35,40,tzinfo=timezone.utc))
    for name in ('digest','dt','converted_jobs','validate_plan_structure','validate_b36_plan'):
        exec(compile(ast.Module(body=[new[name]],type_ignores=[]),str(source_binding['path']),'exec'),ns)
    ns['validate_b36_plan'](plan,base,entry);check(True,'actual pure B36 plan guards')
    clean=dict(plan);key=clean.pop('manifest_key');check(ns['digest'](clean)==key,'manifest key exact')
    originals=[j for j in base['jobs'] if j['profile_id']=='B01']
    check(len(plan['jobs'])==len(originals)==40 and len(plan['cases'])==16 and len(plan['repeat_case_sets'][1]['case_ids'])==4,'40 cells from16 plus4 both taps')
    changed={'profile_id','recipe_id','profile','epoch','mode','job_id','job_key'}
    for a,b in zip(originals,plan['jobs']):
        check({k:v for k,v in a.items() if k not in changed}=={k:v for k,v in b.items() if k not in changed},'unchanged input/app/assets/timing '+b['job_id'])
        check(b['profile']==profile and b['recipe_id']=='R0','native B36 profile '+b['job_id'])
        no_key=dict(b);key=no_key.pop('job_key');check(ns['digest'](no_key)==key,'exact job key '+b['job_id'])
    check(plan['total_audio_sec']==sum(j['duration_sec'] for j in originals),'matched total source duration')
    for field,value in [('profile',{}),('telemetry',{}),('input',{}),('app_path','bad'),('realtime',False),('duration_sec',0),('assets',[])]:
        bad=deepcopy(plan);bad['jobs'][0][field]=value
        try:ns['validate_b36_plan'](bad,base,entry)
        except (ValueError,KeyError):check(True,'actual guard rejects '+field)
        else:raise AssertionError('substitution accepted: '+field)
    driver_raw,driver_binding=read(SIM/'scripts/s6b_paced.py','e755867e703bc6f4dc457db8ad6e98b078af8cf3abcf15fce8adf58efd10fcd9')
    check(plan['driver']==driver_binding,'unchanged original worker binding')
    for b in fixture['dependencies']:read(b['path'],b['sha256'])
    # Verify code/profile/manifest metadata only; final runtime admission rehashes input/model dependencies.
    read(SIM/'scripts/test_s6c_paced_b36_review.py');read(SIM/'scripts/README_TEST_S6C_PACED_B36_REVIEW.md')
    result=dict(status='PASS',checks=len(checks),details=checks,source_bindings=bindings,
        original_control_jobs_unchanged=True,logical_cells=40,base_cases=16,repeat_cases=4,both_taps=True,source_minutes=plan['total_audio_sec']/60,
        native_calls=0,quiet_period_established=False,launch_authorized=False,
        scope='Independent exact metadata/AST/pure-guard admission. Model/audio payloads retain their prior bound chains and are not rehashed here. Run admission must recheck current bytes/resources/quiet owner. This review is not native completion or authorization to start models.',
        limitations=['Inherited global metadata scans can make sampling irregular; only observed trajectory peaks are measured.','Optional malformed LIVE becomes explicit missing status; authoritative output JSON remains strict.','No claim of complete OS process enumeration, DSP timestamps, hardware latency or CM5 qualification.'])
    out=REPORT/'independent_review/B36_PACED_ADAPTER_REVIEW_V1.json'
    if out.exists():raise RuntimeError('Preserve completed review')
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='PASS',checks=len(checks),path=str(out),sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
if __name__=='__main__':main()

