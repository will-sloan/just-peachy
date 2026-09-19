"""Read-only bank-delta review; see README_S6D_BANK_REMAINING_REVIEW_V1.md."""
import argparse
import ast
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
TARGET=SIM/'scripts/s6d_bank_remaining_admit_v2.py'

def bind(p):
    p=Path(p).resolve();data=p.read_bytes()
    return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def need(v,m):
    if not v:raise ValueError(m)
def charge(rows):return sum((Fraction(str(x['duration_sec']))+4+Fraction(16383,48000) for x in rows),Fraction())

def review():
    target=bind(TARGET);tree=ast.parse(TARGET.read_text(encoding='utf-8'))
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('path_map','snapshot_sources','execution_sources_from_freeze')]
    namespace=dict(Path=Path,A=SimpleNamespace(require=need))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(TARGET),'exec'),namespace)
    snap=namespace['snapshot_sources'];mapping=namespace['path_map']
    first=dict(path='C:/old/source.py',bytes=2,sha256='a'*64)
    identical=dict(path='C:/review/source.py',bytes=2,sha256='a'*64)
    conflict=dict(path='C:/review/source.py',bytes=2,sha256='b'*64)
    checks=dict(identical_basename_selects_original=snap([first],[identical])==[first])
    try:snap([first],[conflict]);checks['conflicting_basename_rejected']=False
    except ValueError:checks['conflicting_basename_rejected']=True
    case_identical={**identical,'path':'C:/review/SOURCE.py'}
    case_conflict={**conflict,'path':'C:/review/SOURCE.py'}
    checks['case_insensitive_identical_uses_original']=snap([first],[case_identical])==[first]
    try:snap([first],[case_conflict]);checks['case_insensitive_conflict_rejected']=False
    except ValueError:checks['case_insensitive_conflict_rejected']=True
    checks['path_mapping_exact_components']=mapping('C:/root/old_batch/case/old_attempt/case_result.json',{'old_batch':'new_batch','old_attempt':'new_attempt'})==str(Path('C:/root/new_batch/case/new_attempt/case_result.json'))
    checks['path_mapping_keeps_source_substrings']=mapping('C:/root/source_old_attempt/input.wav',{'old_attempt':'new_attempt'})==str(Path('C:/root/source_old_attempt/input.wav'))
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    calls=[n for n in ast.walk(main) if isinstance(n,ast.Call)]
    saves=[n.lineno for n in calls if isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='A' and n.func.attr=='save']
    closures=[n.lineno for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='prior_closure']
    checks['prior_closure_before_first_save']=len(closures)==1 and closures[0]<min(saves)
    checks['auth_charge_recomputed_from_remaining_rows']=any(k.arg=='charged_playback_seconds' and ast.unparse(k.value)=='float(A.charge(rows))' for n in calls for k in n.keywords)
    # Exercise only the extracted metadata gate, with no owner/import/output path.
    fixture_root=Path('G:/bank_remaining_tiny_fixture')
    freeze=dict(path=str(fixture_root/'runner/SOURCE_FREEZE.json'),bytes=17,sha256='f'*64)
    canonical=[dict(path=f'G:/canonical/source_{i}.py',bytes=i+1,sha256=f'{i+1:064x}') for i in range(24)]
    source_doc={'owner_execution_dependency_bindings':canonical}
    reviewed={'owner_execution_source_freeze':freeze,'source_bindings':[dict(path='G:/historical/SOURCE_0.py',bytes=991,sha256='b'*64)]}
    rejected_binding=[None]
    def fixture_verify(b):
        need(b!=rejected_binding[0],'Synthetic source changed')
        return b
    namespace['A']=SimpleNamespace(require=need,R=fixture_root,read=lambda p:source_doc,verify=fixture_verify)
    select=namespace['execution_sources_from_freeze']
    def selection_rejected(review_doc=reviewed,freeze_doc=freeze,sha='f'*64,members=None):
        try:select(review_doc,freeze_doc,sha,canonical[:3] if members is None else members);return False
        except (ValueError,KeyError):return True
    checks['execution_24_canonical_only_historical_ignored']=select(reviewed,freeze,'f'*64,canonical[:3])==canonical
    checks['execution_freeze_literal_hash_required']=selection_rejected(sha='0'*64)
    checks['execution_freeze_root_review_binding_required']=selection_rejected(review_doc={'owner_execution_source_freeze':{**freeze,'sha256':'0'*64}})
    outside={**freeze,'path':str(fixture_root/'outside/SOURCE_FREEZE.json')}
    checks['execution_freeze_runner_root_required']=selection_rejected(review_doc={'owner_execution_source_freeze':outside},freeze_doc=outside)
    checks['execution_exact_canonical_members_required']=selection_rejected(members=[{**canonical[0],'path':'G:/historical/source_0.py'}])
    source_doc['owner_execution_dependency_bindings']=canonical[:-1]+[{**canonical[0],'path':'G:/alias/SOURCE_0.py'}]
    checks['execution_same_byte_case_collision_rejected']=selection_rejected()
    source_doc['owner_execution_dependency_bindings']=canonical[:-1]+[{**canonical[0],'path':'G:/alias/SOURCE_0.py','sha256':'e'*64}]
    checks['execution_conflicting_case_collision_rejected']=selection_rejected()
    source_doc['owner_execution_dependency_bindings']=canonical;rejected_binding[0]=canonical[-1]
    checks['execution_every_dependency_verified']=selection_rejected()
    rejected_binding[0]=None
    oldref=bind(R/'runner/bank_queue_v3/ROOT_QUEUE_REVIEW.json')
    need(oldref['sha256']=='1e9db5d482ceff2d6e15a55eff68a81434ad0d823bbcb4f269e49085b28281ff','Original admission differs')
    old=read(oldref['path'])
    authorities=[oldref,bind(R/'physical_ledger.json'),bind(R/'partial_bank_review_v1/MAIN_FIRST16_TRANSPORT.json')]
    need(authorities[-1]['sha256']=='b52a327fe534061bf9415ced4c5d3a68ee7f5971760a216b8812081c576fa50d','Retained16 review differs')
    for key in ('queue','approval','runner','qualification','source_review','recovery'):
        need(bind(old[key]['path'])==old[key],'Old bound '+key+' differs');authorities.append(old[key])
    ledger=read(authorities[1]['path']);passes=ledger['passes']
    need(len(passes)==52 and sum(r['status']=='PASS' for r in passes)==51 and sum(r['status']=='FAIL' for r in passes)==1,'Exact52-entry history required')
    need(next(r for r in passes if r['status']=='FAIL')['attempt_id']=='P_MAIN6_S45_01_17','Expected telemetry failure')
    done={f'P_MAIN6_S45_01_{i:02d}' for i in range(1,17)}
    renames={'QA_P_MAIN6_B1_PRE_R2':'QA_P_MAIN6_B1_PRE_R3','P_MAIN6_S45_01_17':'P_MAIN6_S45_01_17_R2'}
    rows=[];groups=[];group_rows={};inherited=None
    for group in old['groups']:
        for key in ('plan','authorization'):
            need(bind(group[key]['path'])==group[key],'Old group binding differs');authorities.append(group[key])
        plan=read(group['plan']['path']);auth=read(group['authorization']['path'])
        if inherited is None:inherited=auth['reviewed_recoveries']
        need(auth['reviewed_recoveries']==inherited,'Recovery context mismatch')
        kept=[]
        for oldrow in plan['attempts']:
            if oldrow['attempt_id'] in done:continue
            row=deepcopy(oldrow);row['attempt_id']=renames.get(row['attempt_id'],row['attempt_id']);kept.append(row)
        rows.extend(kept);group_rows[group['group_id']]=kept
        groups.append(dict(group_id=group['group_id'],old_attempts=len(plan['attempts']),future_attempts=len(kept),
                           old_declared_charge=auth['charged_playback_seconds'],future_charge=float(charge(kept))))
    need(len(inherited)==1 and inherited[0]['sha256']=='1e56f8169aa1f019ee78e2035f82bca48b5f94f871cc015536dc281c4ad04938','Exact inherited gain recovery required')
    need(bind(inherited[0]['path'])==inherited[0],'Inherited actual recovery changed')
    q=read(old['queue']['path']);stages=[];all_stage_ids=[];previous=None
    mutable={'job_id','predecessor_job_id','argv','heartbeat_path','completion_path','stop_request_path','restoration_path','expected_artifacts','source_bindings'}
    for j in q['jobs']:
        ids=[renames.get(x,x) for x in j['argv'][j['argv'].index('--attempt-ids')+1:] if x not in done]
        new_id='bank_v3_'+j['job_id'][len('bank_v2_'):]
        need(j['job_id'].startswith('bank_v2_') and ids,'Expected nonempty60-stage epoch')
        artifacts=[a for a in j['expected_artifacts'] if not done.intersection(Path(a['path']).parts)]
        completion=next(a for a in artifacts if 'semantic_checks.attempt_count' in a.get('expected_fields',{}))
        stages.append(dict(old_job_id=j['job_id'],new_job_id=new_id,predecessor=previous,stage=j['bank_stage'],group=j['bank_group_id'],
                           attempts=len(ids),attempt_ids=ids,retained_artifacts=len(artifacts),completion_attempt_count_after_rebind=len(ids),
                           immutable_job_policy={k:v for k,v in j.items() if k not in mutable}))
        previous=new_id;all_stage_ids.extend(ids)
        need(j['kind']=='hardware' and j['allow_owned_termination'] is False,'Hardware termination policy changed')
        need(len(ids)==len(set(ids)),'Duplicate stage attempts')
        for artifact in artifacts:
            mapped=mapping(artifact['path'],{**renames,j['job_id']:new_id})
            need(not done.intersection(Path(mapped).parts),'Retained old PASS artifact leaked')
    ids=[r['attempt_id'] for r in rows];existing={r['attempt_id'] for r in passes}
    need(len(ids)==len(set(ids))==378 and ids==all_stage_ids and not(existing&set(ids)),'Exact378 future coverage differs')
    need(len(stages)==60 and [x['attempts'] for x in stages[:3]]==[1,14,1],'First stage progression differs')
    need(sum(x['attempts'] for x in stages if x['stage']!='body')==40,'Every pre/post QA required')
    already=sum((Fraction(str(r['charged_playback_s'])) for r in passes),Fraction());future=charge(rows)
    need(already+future==Fraction('19744.058') and len(passes)+len(ids)==430,'Exact total changed')
    for b in authorities:need(bind(b['path'])==b,'Authority changed during review')
    need(bind(TARGET)==target,'Helper changed during source review')
    return dict(status='SOURCE_METADATA_PASS_PENDING_ACTUAL_V7_RECOVERY' if all(checks.values()) else 'SOURCE_METADATA_CHANGES_REQUESTED',
                source=target,readme=bind(TARGET.with_name('README_S6D_BANK_REMAINING_ADMIT_V2.md')),checks=checks,
                source_gate_lines=dict(prior_closure=closures[0],first_save=min(saves)),authorities=authorities,inherited_recovery=inherited,
                groups=groups,stages=stages,ledger_attempts=52,ledger_PASS=51,ledger_FAIL=1,retained_PASS=16,future_attempts=378,total_attempts=430,
                already_charged_seconds=float(already),future_charged_seconds=float(future),total_charged_seconds=float(already+future),
                prior_finding=dict(issue='P_MAIN6_B1 authorization retained1504.922s after removing16 rows',fix='Recompute charged_playback_seconds=float(A.charge(rows)); new715.461s',actual_caps_never_weakened=True),
                limitations=['Actual root V7 source review/recovery.v2 were not executed or semantically accepted by this review','Exact helper main was not invoked; only three pure AST functions and independent saved-metadata transformations were evaluated','Old16-case transport review has no completed old postQA; later catalog/scientific admission must preserve that limitation','New source and recovery still require actual V7 prior_closure before first output and root literal admission review'],
                actual_plan_outputs_created=False,approvals_created=False,owner_imported=False,hardware_calls=0,model_calls=0,check_plan_subprocesses=0)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    need(a.output.drive.upper()=='G:' and not a.output.exists(),'Fresh G review output required')
    result=review();a.output.mkdir(parents=True)
    result['review_helper']=bind(__file__);result['review_readme']=bind(Path(__file__).with_name('README_S6D_BANK_REMAINING_REVIEW_V1.md'))
    path=a.output/'REVIEW.json';path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],review=bind(path),checks=result['checks'])))
