"""Additive execution-lineage inventory; README_S6C_EXECUTION_INVENTORY_V3.md."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib
import json
import math
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch
import psutil

BASE_SHA='655476f9ca94df06ed9df30c38191bef63e02d9323b9474ad26a79171d51b8ac'
BASE_README_SHA='9fa2a50d9604b87b5f3d5c21ec1fea3f8de08abfdb6b9c4abe993e8197d0ecb2'
LONG_SHA='9c15795253b17722af6b56e8bc3eb524ce68665bfa2d5de2d95ef940f690ea9b'
LONG_README_SHA='259285ffc0eef5ae3b3459cb98cc64d7c6241a29958cc5bc4cb09c3bc50909f3'
EPOCH4_SHA='720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945'
COMPOSITION_SHA='bfa18ae06bb224faaad2d4f5096f2e6a0d1aebff5c7c16192d608739d3533bf3'
SCHEMA='s6c-execution-inventory-adapter.v3'


def load_base():
    p=Path(__file__).with_name('s6c_execution_inventory.py')
    if hashlib.sha256(p.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Reviewed base collector changed')
    readme=p.with_name('README_S6C_EXECUTION_INVENTORY.md')
    if hashlib.sha256(readme.read_bytes()).hexdigest()!=BASE_README_SHA:raise ValueError('Reviewed base README changed')
    module=importlib.import_module('s6c_execution_inventory')
    if Path(module.__file__).resolve()!=p.resolve():raise ValueError('Base collector import path differs')
    return module


base=load_base()
REPORT=base.REPORT
EXPECTED_COMPOSITION=REPORT/'long_session/v1/COMPOSITION.json'
EXPECTED_EPOCH=REPORT/'EPOCH4_EXECUTION_MANIFEST.json'


def finite_owner(pid,created):
    return type(pid) is int and pid>0 and type(created) in (int,float) and math.isfinite(created) and created>0


def process_state(pid,created):
    if not finite_owner(pid,created):return dict(state='INVALID_OR_UNAVAILABLE_OWNER_IDENTITY',alive=None,error='Finite positive nonboolean PID/creation identity required')
    try:
        actual=psutil.Process(pid).create_time()
        if not math.isfinite(actual) or actual<=0:return dict(state='INSPECTION_UNAVAILABLE',alive=None)
        alive=abs(actual-created)<.001
        return dict(state='ALIVE_SAME_IDENTITY' if alive else 'CLOSED_PID_REUSED',alive=alive)
    except psutil.NoSuchProcess:return dict(state='CLOSED_NO_SUCH_PROCESS',alive=False)
    except psutil.Error as exc:return dict(state='INSPECTION_UNAVAILABLE',alive=None,error=type(exc).__name__)


def same_owner(a,b):
    if not finite_owner(a.get('pid'),a.get('creation_time')) or not finite_owner(b.get('pid'),b.get('creation_time')):raise ValueError('Invalid native/outer owner identity')
    if (a['pid'],a['creation_time'])!=(b['pid'],b['creation_time']):raise ValueError('Outer/native owner identity differs')


def expected_binding(actual,path,sha):
    if base.canonical(actual['path'])!=base.canonical(path) or actual['sha256']!=sha:raise ValueError('Pinned lineage authority differs')


def source_bindings():
    return [base.binding(p,p.read_bytes()) for p in (Path(__file__),Path(__file__).with_name('README_S6C_EXECUTION_INVENTORY_V3.md'))]


def validate_outer(reader,path):
    admission,ab=reader.read(path)
    if admission.get('status')!='ADMITTED_NOT_YET_COMPLETED':raise ValueError('Unexpected outer admission status')
    owner=admission['owner'];same_owner(owner,owner)
    plan,pb=reader.read(admission['manifest']['path'],admission['manifest'])
    copied=dict(plan);key=copied.pop('plan_key')
    if base.digest(copied)!=key or plan['schema']!='s6c-epoch4-long-native-admission.v1':raise ValueError('Outer manifest schema/digest differs')
    namespace=plan['namespace']
    if not re.fullmatch(r'epoch4_[A-Za-z0-9_-]{1,64}',namespace):raise ValueError('Unadmitted long namespace')
    expected_plan=REPORT/'long_native_epoch4'/namespace/'MANIFEST.json'
    if base.canonical(pb['path'])!=base.canonical(expected_plan) or path.parent.parent.parent!=expected_plan.parent:raise ValueError('Outer manifest/admission path differs')
    if plan['actual_execution_epoch']!='epoch4' or plan['source_composition_epoch']!='epoch2':raise ValueError('Outer execution/composition epochs differ')
    expected_binding(plan['composition'],EXPECTED_COMPOSITION,COMPOSITION_SHA)
    expected_binding(plan['execution_manifest'],EXPECTED_EPOCH,EPOCH4_SHA)
    spec,eb=reader.read(plan['execution_manifest']['path'],plan['execution_manifest'])
    composition,cb=reader.read(plan['composition']['path'],plan['composition'])
    if spec['epoch']!='epoch4' or spec['execution_digest']!=base.digest({k:spec[k] for k in ('execution_files','assets','versions','state_policy')}):raise ValueError('Actual native epoch digest differs')
    if Path(composition['epoch']['path']).name!='EPOCH2_EXECUTION_MANIFEST.json':raise ValueError('Source composition is not epoch2')
    row=plan['profile_row']
    if sum(r==row for r in spec['profiles'])!=1 or base.digest(row)!=plan['profile_sha256']:raise ValueError('Exact registered long candidate/route differs')
    if row['gallery_condition'] not in ('NONE','FIXED_ROTATION_A','FIXED_ROTATION_B') or row['cue_condition'] not in ('CUES_OFF','REAL_ALIGNED_CUES'):raise ValueError('Unsupported long cue/gallery condition')
    if plan['report_root']!=str(REPORT/'long_session'/namespace) or plan['payload_root']!=str(base.PAYLOAD/'long_session'/namespace):raise ValueError('Native namespace differs')
    for key in ('audio','pcm_sha256','telemetry','duration_sec','duration_samples'):
        if plan[key]!=composition[key]:raise ValueError('Long source differs: '+key)
    for key,pin in (('s6c_long_native_epoch4.py',LONG_SHA),('README_S6C_LONG_NATIVE_EPOCH4.md',LONG_README_SHA)):
        deps=[b for b in plan['dependencies'] if Path(b['path']).name==key]
        if len(deps)!=1 or deps[0]['sha256']!=pin:raise ValueError('Unreviewed wrapper authority')
    for a,p in (('source_composition','composition'),('actual_execution_manifest','execution_manifest'),('profile_row','profile_row'),('gallery','gallery'),('imports','imports')):
        if admission[a]!=plan[p]:raise ValueError('Outer admission/manifest differs: '+a)
    if admission['actual_execution_epoch']!='epoch4' or admission['source_composition_epoch']!='epoch2':raise ValueError('Admission epoch labels differ')
    if plan['gallery'] is None:
        if row['gallery_condition']!='NONE' or row['profile']['identity']['mode']!='none':raise ValueError('No-gallery identity route differs')
    else:
        index,ib=reader.read(plan['gallery_index']['path'],plan['gallery_index'])
        if plan['gallery_index']!=spec['gallery_index']:raise ValueError('Wrong valid gallery index')
        matched=[r for r in index['rows'] if r['case_id'] is None and r['gallery_condition']==row['gallery_condition'] and r['enrollment_tier']==row['enrollment_tier']]
        if len(matched)!=1 or matched[0]!=plan['gallery_row'] or matched[0]['manifest']!=plan['gallery']:raise ValueError('Exact fixed roster/tier mapping differs')
    record=dict(admission=ab,manifest=pb,actual_execution_manifest=eb,source_composition=cb,actual_execution_epoch='epoch4',source_composition_epoch='epoch2',owner=owner,plan=plan,closure=None,native_outcome=None,original_native_result=None,wrapper_status='ADMITTED_NO_CLOSURE_OBSERVED')
    closure_path=path.parent/'CLOSURE.json'
    if closure_path.exists():
        closure,kb=reader.read(closure_path);same_owner(owner,closure['owner'])
        for key,wanted in (('admission',ab),('manifest',pb),('actual_execution_manifest',eb),('source_composition',cb),('profile_row',row),('gallery',plan['gallery'])):
            if closure[key]!=wanted:raise ValueError('Outer closure authority differs: '+key)
        if closure['actual_execution_epoch']!='epoch4' or closure['source_composition_epoch']!='epoch2' or closure.get('original_result_not_rewritten') is not True or closure.get('protected_functions_restored') is not True:raise ValueError('Wrapper closure source/protection statement differs')
        outcome,nb=reader.read(closure['pre_release_outcome']['path'],closure['pre_release_outcome'])
        for key in ('manifest','owner','original_native_result','actual_execution_manifest','profile_row','gallery'):
            if outcome[key]!=closure[key]:raise ValueError('Pre-release/closure result identity differs')
        if closure['original_native_result'] is not None:
            native,rb=reader.read(closure['original_native_result']['path'],closure['original_native_result']);same_owner(owner,native['owner'])
            if native['profile']!=row or native['composition']!=cb or Path(plan['report_root']) not in Path(rb['path']).parents:raise ValueError('Outer result points to a different native execution')
            if native.get('schema')!='s6c_continuous_paced_native.v1' or native.get('status')!='COMPLETE':raise ValueError('Outer result is not an actual completed native schema')
            if native.get('source_duration_sec')!=plan['duration_sec'] or native.get('long_session_gallery_condition')!=plan.get('gallery_row') or native.get('gallery_index')!=plan.get('gallery_index'):raise ValueError('Native source duration/gallery mapping differs from admitted plan')
            record['original_native_result']=rb
        release=closure['lease_release']
        if closure['status']=='NATIVE_COMPLETE_QUIET_LEASE_RELEASED':
            if outcome['status']!='NATIVE_COMPLETE_RELEASE_PENDING':raise ValueError('Successful closure lacks a completed pending-release native outcome')
            if release['status']!='RELEASED' or release['released'] is not True or record['original_native_result'] is None:raise ValueError('False complete/released wrapper claim')
            archived,lb=reader.read(release['archived_binding']['path'],release['archived_binding']);same_owner(owner,archived)
            if archived['manifest']!=pb or archived['admission']!=ab:raise ValueError('Released lease belongs to another admission')
        record.update(closure=kb,native_outcome=nb,wrapper_status=closure['status'])
    return record


def enrich_long_row(row,records,reader):
    source=row['receipt_bindings'][0];start,sb=reader.read(source['path'],source)
    candidates=[r for r in records if Path(r['plan']['report_root']) in Path(sb['path']).parents]
    is_wrapped=any(part.startswith('epoch4_') for part in Path(sb['path']).parts)
    if not candidates:
        if is_wrapped:raise ValueError('Epoch4 native row lacks verified unique outer admission')
        row['source_composition_epoch']=row['epoch'];row['lineage_status']='ORIGINAL_UNWRAPPED_NATIVE_SOURCE';return
    matching=[]
    for r in candidates:
        try:same_owner(start['owner'],r['owner'])
        except ValueError:continue
        if start['profile']==r['plan']['profile_row'] and start['composition']==r['source_composition']:matching.append(r)
    if len(matching)!=1:raise ValueError('Missing/ambiguous exact native owner/profile/source admission')
    r=matching[0]
    if row['status']=='COMPLETE':
        native=next((b for b in row['receipt_bindings'] if Path(b['path']).name=='RESULT.json'),None)
        if native!=r['original_native_result'] or r['closure'] is None:raise ValueError('Completed native row lacks matching outer final result binding')
    row.update(epoch='epoch4',source_composition_epoch='epoch2',epoch_manifest=r['actual_execution_manifest'],source_composition=r['source_composition'],
        lineage_status='VERIFIED_OUTER_EXECUTION_ADMISSION',wrapper_status=r['wrapper_status'],wrapper_admission=r['admission'],wrapper_manifest=r['manifest'],wrapper_closure=r['closure'])
    row['receipt_bindings']+=[b for b in (r['admission'],r['manifest'],r['closure'],r['native_outcome']) if b]


def auxiliary_adapter(original,reader,declared,issues,rows,bysession,paced_manifests):
    sources=source_bindings();records=[];failed=[]
    for path in sorted((REPORT/'long_native_epoch4').glob('*/invocations/*/ADMISSION.json')):
        try:records.append(validate_outer(reader,path))
        except (KeyError,ValueError,OSError,RuntimeError) as exc:failed.append(dict(path=str(path),error=repr(exc)))
    result=original(reader,declared,issues,rows,bysession,paced_manifests)
    for row in rows:
        if row['branch']!='CONTINUOUS_HOST_PACED_NATIVE':continue
        try:enrich_long_row(row,records,reader)
        except (KeyError,ValueError,OSError,RuntimeError) as exc:
            row.update(epoch='UNVERIFIED_LONG_EXECUTION',lineage_status='CLOSURE_UNVERIFIED',lineage_error=repr(exc))
            failed.append(dict(physical_id=row['physical_id'],error=repr(exc)))
        if row.get('wrapper_status') not in (None,'NATIVE_COMPLETE_QUIET_LEASE_RELEASED','ADMITTED_NO_CLOSURE_OBSERVED'):
            failed.append(dict(physical_id=row['physical_id'],error='Wrapper outcome not successful: '+row['wrapper_status']))
    for r in records:
        owner=r['owner'];result['owner_observations'].append(dict(branch='LONG_WRAPPER_OWNER',pid=owner['pid'],creation_time=owner['creation_time'],process_state=process_state(owner['pid'],owner['creation_time']),source=r['admission']))
        declared.add([r['manifest'],r['actual_execution_manifest'],r['source_composition'],r['closure'],r['original_native_result']],r['admission'],'LONG_NATIVE_OUTER_EXECUTION_LINEAGE')
    if failed:
        issues.extend(failed)
        result['owner_observations'].append(dict(branch='UNVERIFIED_LONG_LINEAGE',pid=None,creation_time=None,process_state=dict(state='CLOSURE_UNVERIFIED_LINEAGE',alive=None),issues=failed))
    snapshots=[]
    for b in sources:
        raw=Path(b['path']).read_bytes();target=reader.output/'source_snapshots'/Path(b['path']).name;target.write_bytes(raw)
        snapshots.append(dict(source=b,snapshot=base.binding(target,raw)))
        declared.add(b,b,'INVENTORY_ADAPTER_CODE_OR_README')
    result['execution_inventory_adapter']=dict(schema=SCHEMA,sources=sources,source_snapshots=snapshots,
        long_lineage_records=[{k:v for k,v in r.items() if k!='plan'} for r in records],unverified_lineage=failed,
        interpretation='Outer admission is owner/execution lineage, not another model session. Source composition epoch2 remains separate from actual epoch4. Native result bytes are never rewritten. All evidence is metadata-bound, not a payload rehash.')
    return result


@contextmanager
def patched_base():
    original_aux=base.collect_auxiliary;original_state=base.process_state;original_validate=base.validate_native
    def validated(row,specs):
        if not finite_owner(row.get('pid'),row.get('creation_time')):raise ValueError('Invalid native physical owner identity')
        return original_validate(row,specs)
    base.collect_auxiliary=lambda *a:auxiliary_adapter(original_aux,*a);base.process_state=process_state;base.validate_native=validated
    try:yield
    finally:base.collect_auxiliary=original_aux;base.process_state=original_state;base.validate_native=original_validate


def collect(args):
    before=source_bindings()
    with patched_base():result=base.collect(args)
    if source_bindings()!=before:raise ValueError('Inventory adapter changed during snapshot')
    receipt=dict(schema=SCHEMA,status='COMPLETE_ADAPTER_SNAPSHOT',created_utc=base.utc(),sources=before,base_source=base.binding(base.__file__,Path(base.__file__).read_bytes()),
        inventory=result['snapshot'],result=result,model_calls=0,scope='Preserved original collector with explicit finite-owner and outer-long-lineage adapters. The underlying snapshot retains its active/unverified flags; this receipt does not certify whole-study completion.')
    return base.write_new(Path(result['snapshot']['path']).parent/'INVENTORY_ADAPTER_RECEIPT.json',receipt)


def checks():
    from types import SimpleNamespace
    count=0
    for pid,created in ((None,1),(1,None),(True,1),(1,True),(0,1),(1,0),(1,float('nan')),(1,float('inf'))):
        assert process_state(pid,created)['alive'] is None;count+=1
    with patch.object(psutil,'Process',side_effect=psutil.AccessDenied(1)):assert process_state(1,1)['alive'] is None;count+=1
    with patch.object(psutil,'Process',side_effect=psutil.NoSuchProcess(1)):assert process_state(1,1)['alive'] is False;count+=1
    with patch.object(psutil,'Process',return_value=SimpleNamespace(create_time=lambda:2.)):
        assert process_state(1,1)['alive'] is False and process_state(1,2)['alive'] is True;count+=1
    for b in ({'pid':2,'creation_time':1.},{'pid':1,'creation_time':2.},{'pid':True,'creation_time':1.}):
        try:same_owner(dict(pid=1,creation_time=1.),b)
        except ValueError:count+=1
        else:raise AssertionError('Wrong outer/native owner admitted')
    with tempfile.TemporaryDirectory(prefix='s6c_inventory_lineage_') as temporary:
        root=Path(temporary);out=root/'snap';out.mkdir();reader=base.MetadataReader(out);path=root/'authority.json'
        path.write_text('{"value":1}',encoding='utf-8');value,b=reader.read(path);assert value=={'value':1};count+=1
        path.write_text('{"value":2}',encoding='utf-8');again,same=reader.read(path,b)
        assert again==value and same==b and json.loads(Path(reader.sources[0]['preserved']['path']).read_text())==value;count+=1
        fresh=base.MetadataReader(out)
        try:fresh.read(path,b)
        except ValueError:count+=1
        else:raise AssertionError('Changed authority admitted')
        native_root=root/'epoch4_fixture';start_path=native_root/'native/C001/O0_O0/NONE/STARTED.json';start_path.parent.mkdir(parents=True)
        owner=dict(pid=1,creation_time=1.);profile=dict(candidate_id='C001');composition=dict(path='source',sha256='1'*64,bytes=1)
        sb=base.write_new(start_path,dict(owner=owner,profile=profile,composition=composition))
        admission=dict(path='admission',sha256='2'*64,bytes=1);manifest=dict(path='manifest',sha256='3'*64,bytes=1)
        record=dict(plan=dict(report_root=str(native_root),profile_row=profile),owner=owner,source_composition=composition,actual_execution_manifest=dict(path='epoch4',sha256='4'*64,bytes=1),admission=admission,manifest=manifest,closure=None,native_outcome=None,wrapper_status='ADMITTED_NO_CLOSURE_OBSERVED',original_native_result=None)
        row=dict(receipt_bindings=[sb],status='STARTED',epoch='EPOCH2_EXECUTION_MANIFEST')
        enrich_long_row(row,[record],reader);assert row['epoch']=='epoch4' and row['source_composition_epoch']=='epoch2';count+=1
        for records,status in (([], 'STARTED'),([record,record],'STARTED'),([record],'COMPLETE')):
            row=dict(receipt_bindings=[sb],status=status,epoch='EPOCH2_EXECUTION_MANIFEST')
            try:enrich_long_row(row,records,reader)
            except ValueError:count+=1
            else:raise AssertionError('Missing/duplicate/final-unbound lineage admitted')
        final=dict(path=str(start_path.with_name('RESULT.json')),sha256='5'*64,bytes=1)
        complete={**record,'closure':dict(path='closure',sha256='6'*64,bytes=1),'original_native_result':final,'wrapper_status':'NATIVE_COMPLETE_QUIET_LEASE_RELEASED'}
        row=dict(receipt_bindings=[sb,final],status='COMPLETE',epoch='EPOCH2_EXECUTION_MANIFEST')
        enrich_long_row(row,[complete],reader);assert row['epoch']=='epoch4' and row['wrapper_closure']==complete['closure'];count+=1
        wrong=deepcopy(complete);wrong['original_native_result']['sha256']='7'*64
        try:enrich_long_row(dict(receipt_bindings=[sb,final],status='COMPLETE',epoch='EPOCH2_EXECUTION_MANIFEST'),[wrong],reader)
        except ValueError:count+=1
        else:raise AssertionError('Wrong completed result accepted')
    funcs=(base.collect_auxiliary,base.process_state,base.validate_native)
    with patched_base():assert base.process_state is process_state;count+=1
    assert funcs==(base.collect_auxiliary,base.process_state,base.validate_native);count+=1
    assert base.closure_scope([dict(process_state=dict(alive=None))])['status']=='CLOSURE_UNVERIFIED';count+=1
    count+=outer_chain_checks()
    return dict(status='PASS_MODEL_FREE_ADAPTER_CHECKS',checks=count,model_calls=0,full_inventory_scans=0,scope='Constructed metadata and process inspection failures; not actual long completion evidence.')


def outer_chain_checks():
    """Exercise the actual metadata validator using complete temporary chains."""
    count=0
    cases=(None,'wrong_profile','wrong_epoch','wrong_source_epoch','wrong_wrapper','wrong_owner','wrong_admission_profile','wrong_result','false_release','wrong_lease_owner','wrong_native_owner','wrong_plan_digest',
        'wrong_native_schema','wrong_native_status','wrong_native_duration','wrong_native_gallery_row','wrong_native_gallery_index','wrong_outcome_status')
    for change in cases:
        with tempfile.TemporaryDirectory(prefix='s6c_inventory_outer_') as temporary:
            root=Path(temporary);report=root/'report';payload=root/'payload';namespace='epoch4_fixture';report.mkdir();payload.mkdir()
            composition=dict(epoch=dict(path=str(report/'EPOCH2_EXECUTION_MANIFEST.json'),sha256='1'*64,bytes=1),audio={},pcm_sha256={},telemetry={},duration_sec=1.,duration_samples=16000)
            cb=base.write_new(report/'long_session/v1/COMPOSITION.json',composition)
            row=dict(candidate_id='C001',asr_tap='O0',identity_tap='O0',gallery_condition='NONE',enrollment_tier=None,cue_condition='CUES_OFF',profile=dict(identity=dict(mode='none')))
            spec=dict(epoch='epoch4',profiles=[row],execution_files=[],assets=[],versions={},state_policy={});spec['execution_digest']=base.digest({k:spec[k] for k in ('execution_files','assets','versions','state_policy')})
            eb=base.write_new(report/'EPOCH4_EXECUTION_MANIFEST.json',spec)
            plan=dict(schema='s6c-epoch4-long-native-admission.v1',namespace=namespace,actual_execution_epoch='epoch4',source_composition_epoch='epoch2',composition=cb,execution_manifest=eb,
                profile_row=deepcopy(row),profile_sha256=base.digest(row),report_root=str(report/'long_session'/namespace),payload_root=str(payload/'long_session'/namespace),
                gallery=None,gallery_row=None,gallery_index=None,imports={},dependencies=[dict(path=n,sha256=h,bytes=1) for n,h in (('s6c_long_native_epoch4.py',LONG_SHA),('README_S6C_LONG_NATIVE_EPOCH4.md',LONG_README_SHA))],
                **{k:composition[k] for k in ('audio','pcm_sha256','telemetry','duration_sec','duration_samples')})
            if change=='wrong_profile':plan['profile_row']['candidate_id']='C999';plan['profile_sha256']=base.digest(plan['profile_row'])
            if change=='wrong_epoch':plan['actual_execution_epoch']='epoch2'
            if change=='wrong_source_epoch':plan['source_composition_epoch']='epoch4'
            if change=='wrong_wrapper':plan['dependencies'][0]['sha256']='0'*64
            plan['plan_key']=base.digest(plan)
            if change=='wrong_plan_digest':plan['plan_key']='0'*64
            pb=base.write_new(report/'long_native_epoch4'/namespace/'MANIFEST.json',plan)
            folder=Path(pb['path']).parent/'invocations/id';owner=dict(pid=1,creation_time=1.)
            admission=dict(status='ADMITTED_NOT_YET_COMPLETED',owner=owner,manifest=pb,source_composition=cb,actual_execution_manifest=eb,profile_row=deepcopy(plan['profile_row']),gallery=None,imports={},actual_execution_epoch='epoch4',source_composition_epoch='epoch2')
            if change=='wrong_owner':admission['owner']=dict(pid=True,creation_time=1.)
            if change=='wrong_admission_profile':admission['profile_row']['candidate_id']='C999'
            ab=base.write_new(folder/'ADMISSION.json',admission)
            native=dict(schema='s6c_continuous_paced_native.v1',status='COMPLETE',owner=dict(pid=2,creation_time=1.) if change=='wrong_native_owner' else owner,profile=row,composition=cb,
                source_duration_sec=plan['duration_sec'],long_session_gallery_condition=None,gallery_index=None)
            for bad,key,value in (('wrong_native_schema','schema','other'),('wrong_native_status','status','STARTED'),('wrong_native_duration','source_duration_sec',2.),('wrong_native_gallery_row','long_session_gallery_condition',{}),('wrong_native_gallery_index','gallery_index',{})):
                if change==bad:native[key]=value
            rb=base.write_new(Path(plan['report_root'])/'native/C001/O0_O0/NONE/RESULT.json',native)
            if change=='wrong_result':rb={**rb,'sha256':'0'*64}
            lease=dict(owner='unused',pid=2 if change=='wrong_lease_owner' else 1,creation_time=1.,manifest=pb,admission=ab)
            lb=base.write_new(folder/'QUIET_LEASE_RELEASED.json',lease)
            outcome=dict(status='FAILED' if change=='wrong_outcome_status' else 'NATIVE_COMPLETE_RELEASE_PENDING',owner=owner,manifest=pb,admission=ab,actual_execution_manifest=eb,source_composition=cb,profile_row=row,gallery=None,original_native_result=rb)
            nb=base.write_new(folder/'NATIVE_OUTCOME.json',outcome)
            closure=dict(**{k:v for k,v in outcome.items() if k!='status'},status='NATIVE_COMPLETE_QUIET_LEASE_RELEASED',actual_execution_epoch='epoch4',source_composition_epoch='epoch2',
                original_result_not_rewritten=True,protected_functions_restored=True,pre_release_outcome=nb,lease_release=dict(status='RELEASE_FAILED' if change=='false_release' else 'RELEASED',released=change!='false_release',archived_binding=lb))
            base.write_new(folder/'CLOSURE.json',closure);out=root/'snap';out.mkdir();reader=base.MetadataReader(out)
            with patch.multiple(sys.modules[__name__],REPORT=report,EXPECTED_COMPOSITION=Path(cb['path']),COMPOSITION_SHA=cb['sha256'],EXPECTED_EPOCH=Path(eb['path']),EPOCH4_SHA=eb['sha256']),patch.object(base,'PAYLOAD',payload):
                if change is None:
                    actual=validate_outer(reader,Path(ab['path']));assert actual['actual_execution_epoch']=='epoch4' and actual['original_native_result']==rb;count+=1
                else:
                    try:validate_outer(reader,Path(ab['path']))
                    except (ValueError,KeyError):count+=1
                    else:raise AssertionError('Invalid complete outer chain admitted: '+change)
    return count


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('checks','collect'));p.add_argument('--version');a=p.parse_args()
    if a.action=='collect' and not a.version:p.error('collect requires a fresh --version')
    print(json.dumps(checks() if a.action=='checks' else collect(a),indent=2))
