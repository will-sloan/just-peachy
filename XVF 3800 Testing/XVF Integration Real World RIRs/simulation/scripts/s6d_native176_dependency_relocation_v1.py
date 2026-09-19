"""Proposal-only six-path relocation; README_S6D_NATIVE176_DEPENDENCY_RELOCATION_V1.md."""
from copy import deepcopy
import argparse
import difflib
import hashlib
import json
from pathlib import Path

SIM=Path('C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation')
REPO=SIM.parents[2]
R=SIM/'reports/S6D/20260913T195357Z'
G=Path('G:/Just_Peachy_S6D/20260913T195357Z')
PARENT=G/'application/native176_composite_closed_inputs_v2/SCORING_INPUTS.json'
DIAGNOSIS=R/'application/native176_scoring_execution_v2/DEPENDENCY_PATH_DIAGNOSIS.json'
FAILURE=R/'application/native176_scoring_execution_v2/EXECUTION.json'
PINS={
 'parent':'bfaecace727accad3e63b9cd9d86aecab2533862c0b41b255e26e0a18947c373',
 'diagnosis':'f92bca26babecc49c9c9f40145ea25f6f3110cf0472ee1845dbd0ba25b6af7d5',
 'failure':'92d189156378df0ba9f258952be06fc422acc31a8ea0291ee40253c083f6772d',
 'validation':'885634c7ec270c8f177d8241cf73b57a108282785ff878a445b0844692fc36c9',
 'scorer':'31408ef3b089a2319230ff49cd83f388d52498b8fd2d774430ce046b4d1770a2'}
FILES=[
 ('s4_h2_analysis.py',18581,'0b5d8a227ca87c4dcee48db8118de35444fb32217291bf022feb458f0982d1a0'),
 ('s5_text_metrics.py',15191,'4bf822fe40227acf74a17a24666fcb1ddce9f76cbe93adf4ec6b10e6d2b47969'),
 ('s6c_name_analysis_v3.py',28859,'79c58dd9f67ebbaa9d1f5ca2b9ef53ec788b8762e348eda5d6add44d5dac3017'),
 ('s6a_support_metrics.py',32761,'4ecc9240d897598005719b00b803ea5f1f137bba4b66f1e970b1d098a47a68b5'),
 ('wer.py',2418,'fd493e6952b5b4ab7cf2652338511dac99667591b94af84ad1efba8d438adf34'),
 ('s6d_native_evidence_v1.py',15877,'bb1b5ff846f8edad386b573dea203df7b08e9c31b8126e7c3aa14a8cccb226d2')]
PROPOSED='PROPOSED_DEPENDENCY_RELOCATION_NOT_AUTHORIZED'


def need(value,message):
    if not value:raise ValueError(message)
def binding(path):
    p=Path(path).resolve();before=p.stat();need(before.st_size<=2**20,'This helper reads only bounded source/metadata, never native journals/audio')
    raw=p.read_bytes();after=p.stat();need((before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'File changed while hashing')
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'),parse_constant=lambda x:need(False,'Nonfinite JSON'))
def verified(ref):need(binding(ref['path'])==ref,'Bound source/metadata differs');return read(ref['path'])
def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def target(name):return REPO/'Software Validation from Datasets/Evaluation Tool/app/scoring/wer.py' if name=='wer.py' else SIM/'scripts'/name


def relocation_pairs(parent,rows):
    need(len(parent['dependencies'])==len(rows)==len(FILES)==6,'Exact six dependency rows required')
    result=[]
    for old,row,(name,size,sha) in zip(parent['dependencies'],rows,FILES):
        new=row['actual_from_unchanged_dependencies_path_logic']
        need(row['expected_from_original_frozen_tree']==old and row['name']==name,'Original dependency/order differs')
        need(set(old)==set(new)=={'path','bytes','sha256'},'Exact file bindings required')
        need(type(old['bytes']) is int and type(new['bytes']) is int and old['bytes']==new['bytes']==size and old['sha256']==new['sha256']==sha,'Dependency bytes/hash changed')
        need(new['path']==str(target(name).resolve()) and old['path']!=new['path'],'Exact loaded target path required')
        need(row['differing_fields']==['path'],'Relocation must change only path')
        result.append(deepcopy(new))
    need(sum(x['bytes'] for x in result)==113687,'Exact total dependency bytes required')
    return result


def assert_only_relocation(parent,proposal,new,provenance):
    need(parent.get('status')=='APPROVED_CLOSED_NATIVE_INPUTS' and 'dependency_path_correction' not in parent,'Exact original closed-input shape required')
    need(proposal.get('status')==PROPOSED and proposal.get('dependency_path_correction')==provenance and proposal.get('dependencies')==new,'Proposal status/provenance/targets differ')
    left=deepcopy(parent);right=deepcopy(proposal)
    for key in ('status','dependencies'):left.pop(key);right.pop(key)
    right.pop('dependency_path_correction')
    need(left==right,'Any other field change is forbidden, including output, validation, items, reference or comparisons')
    need(len(parent['jobs'])==176 and parent['unavailable_jobs']==[] and len(parent['comparison_pairs'])==176 and len(parent['execution_manifests'])==4,'Original exact176 population required')


def prepare(output):
    output=output.resolve();need(output.is_relative_to(R/'application') and not output.exists(),'Fresh compact application proposal directory required')
    refs={key:binding(path) for key,path in [('parent',PARENT),('diagnosis',DIAGNOSIS),('failure',FAILURE)]}
    for key,ref in refs.items():need(ref['sha256']==PINS[key],'Exact original input hash required: '+key)
    parent=read(PARENT);diagnosis=read(DIAGNOSIS);failure=read(FAILURE)
    need(diagnosis['status']=='EXACT_SIX_PATH_ONLY_MISMATCH_CONFIRMED' and diagnosis['spec']==refs['parent'] and diagnosis['execution']==refs['failure'] and diagnosis['identical_dependency_content'] is True,'Exact failed path diagnosis required')
    need(failure['status']=='SCORER_FAILED_NO_AUTOMATIC_RETRY' and failure['exit_code']==1 and failure['scoring_spec']==refs['parent'],'Original failed execution must remain explicit')
    validation=verified(parent['closed_input_validation']);need(parent['closed_input_validation']['sha256']==PINS['validation'] and validation['status']=='ALL176_COMPOSITE_CLOSED_INPUTS_VERIFIED' and validation['original_completed']==171 and validation['recovery_completed']==5,'Already-complete unchanged176 validation required')
    need(binding(parent['scorer']['path'])==parent['scorer'] and parent['scorer']['sha256']==PINS['scorer'],'Unchanged scorer required')
    new=relocation_pairs(parent,diagnosis['dependency_rows'])
    for old,actual in zip(parent['dependencies'],new):need(binding(old['path'])==old and binding(actual['path'])==actual,'Exact identical dependency source bytes required')
    need(not Path(parent['output_root']).exists(),'Original score output must still be uncreated; no cleanup or overwrite')
    provenance=dict(schema='s6d-native-dependency-path-correction-proposal.v1',status='PROPOSED_NOT_APPROVED',parent_spec=refs['parent'],failed_execution=refs['failure'],path_diagnosis=refs['diagnosis'],source_helper=binding(__file__),source_readme=binding(Path(__file__).with_name('README_S6D_NATIVE176_DEPENDENCY_RELOCATION_V1.md')),original_closed_status=parent['status'],closed_validation_reused_unchanged=parent['closed_input_validation'],changes='Six dependency paths only; same ordered source contents. Top-level status blocks scoring until root separately accepts a final exact hash.',native_jobs_unchanged=True,metrics_unchanged=True,root_execution_authorization_created=False,scorer_retry_performed=False)
    proposal=deepcopy(parent);proposal.update(status=PROPOSED,dependencies=new,dependency_path_correction=provenance);assert_only_relocation(parent,proposal,new,provenance)
    for key,ref in refs.items():need(binding(ref['path'])==ref,'Original metadata changed before proposal')
    output.mkdir(parents=True,exist_ok=False);save(output/'SCORING_INPUTS_PROPOSAL.json',proposal)
    before=json.dumps(dict(status=parent['status'],dependencies=parent['dependencies']),indent=2).splitlines(True);after=json.dumps(dict(status=proposal['status'],dependencies=proposal['dependencies'],dependency_path_correction=provenance),indent=2).splitlines(True)
    (output/'EXACT_ALLOWED_CHANGE.diff').write_text(''.join(difflib.unified_diff(before,after,fromfile='original_bound_spec_projection',tofile='proposal_allowed_changes')),encoding='utf-8')
    receipt=dict(status='DEPENDENCY_RELOCATION_PROPOSED_NOT_AUTHORIZED',parent=refs['parent'],failed_execution=refs['failure'],diagnosis=refs['diagnosis'],proposal=binding(output/'SCORING_INPUTS_PROPOSAL.json'),diff=binding(output/'EXACT_ALLOWED_CHANGE.diff'),unchanged_validation=parent['closed_input_validation'],source_helper=provenance['source_helper'],source_readme=provenance['source_readme'],dependencies_same_order_same_bytes_same_hash=True,dependency_count=6,dependency_total_bytes=113687,jobs=176,comparison_pairs=176,output_root_unchanged=parent['output_root'],original_stopped_attempt_uncredited=True,root_approval_created=False,scorer_retry=False,native_output_or_audio_files_opened=0,metrics_or_models_executed=0)
    save(output/'PREPARATION_RECEIPT.json',receipt);return binding(output/'PREPARATION_RECEIPT.json')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.output)))
