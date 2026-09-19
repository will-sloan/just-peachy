"""Independent pure V5 restoration review; see README_S6D_RESTORATION_REVIEW_V5.md."""
import argparse
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback

def binding(path):
    p=Path(path).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def need(value,message):
    if not value:raise AssertionError(message)
def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def definitions(path):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(Path(path).read_text(encoding='utf-8')).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}

def run(source_root,freeze_path,baseline,author_receipt,output):
    out=Path(output).resolve();need(out.drive.upper()=='G:' and not out.exists(),'Fresh G output required');out.mkdir(parents=True)
    freeze_ref=binding(freeze_path);need(freeze_ref['sha256']=='764893d418a691e7ee265d3ff6620dea4780fdff2c90434f3ac2b4d378998c4b','Exact frozen V5 required');f=read(freeze_path)
    refs=[r['copy'] for r in f['source_copies']]+f['unchanged_bound_dependencies']+[f['authority'],f['historical_failure'],f['historical_initial']]
    for b in refs:need(binding(b['path'])==b,'Source/authority/historical evidence changed')
    copied=[]
    for row in f['source_copies']:
        p=Path(source_root)/Path(row['copy']['path']).name;b=binding(p);need(b['sha256']==row['copy']['sha256'] and b['bytes']==row['copy']['bytes'],'Independent copy differs');copied.append(b)
    sys.dont_write_bytecode=True;sys.path.insert(0,str(source_root));P=module('s6d_restoration_policy_v1',Path(source_root)/'s6d_restoration_policy_v1.py')
    initial=read(Path(baseline)/'initial_state.json');restored=read(Path(baseline)/'restoration.json');rows=[]
    def check(name,fn):
        try:fn();rows.append(dict(name=name,status='PASS'))
        except BaseException as e:rows.append(dict(name=name,status='FAIL',error=repr(e),traceback=traceback.format_exc()))
    def decision(change):
        i,a,r=deepcopy((initial,restored['readback'],restored['reapply']));change(i,a,r);return P.restoration_decision(i,a,r)
    def disabled_exact():
        def change(i,a,r):
            for x in (i['settings'],a['settings'],r['observed']):x['PP_AGCONOFF']=[0]
            a['settings']['PP_AGCGAIN']=deepcopy(i['settings']['PP_AGCGAIN'])
        d=decision(change);need(d['accepted'] and d['exact_full_snapshot_match'] and not d['autonomous_gain']['exception_used'],'AGC disabled exact restoration must remain valid')
    check('AGC_disabled_exact_restoration_allowed_without_exception',disabled_exact)
    def static_boolean():
        d=decision(lambda i,a,r:a['settings'].update(I2S_INPUT_PACKED=[False]));need(not d['accepted'],'Boolean static value cannot equal original numeric zero')
    check('numeric_zero_static_cannot_be_replaced_by_boolean_false',static_boolean)
    def ancillary_boolean():
        def change(i,a,r):
            key=next(k for k,v in i['observe_only'].items() if isinstance(v,list) and any(x in (0,1) for x in v))
            a['observe_only'][key]=[bool(x) if x in (0,1) else x for x in a['observe_only'][key]]
        need(not decision(change)['accepted'],'Ancillary numeric values remain strict')
    check('ancillary_boolean_alias_rejected',ancillary_boolean)
    def record_mutation(key,value):
        d=P.restoration_decision(initial,restored['readback'],restored['reapply']);r=dict(schema_version=P.SCHEMA,status='PASS',**d,readback=restored['readback'],reapply=restored['reapply'],exact_recorded_configuration_match=d['exact_full_snapshot_match']);r[key]=value;need(not P.record_policy_valid(initial,r),'Forged derived policy field accepted')
    check('derived_accepted_integer_cannot_replace_true',lambda:record_mutation('accepted',1))
    check('derived_error_list_cannot_be_deleted',lambda:record_mutation('errors',None))
    def derived_delta():
        d=P.restoration_decision(initial,restored['readback'],restored['reapply']);x=deepcopy(d['autonomous_gain']);x['delta']=-x['delta'];record_mutation('autonomous_gain',x)
    check('derived_gain_delta_cannot_be_forged',derived_delta)
    def absent_initial_usb():need(not decision(lambda i,a,r:i.pop('usb_bits'))['accepted'],'Initial USB width proof absent')
    check('missing_initial_USB_width_rejected',absent_initial_usb)
    def pure_repeat():
        before=deepcopy((initial,restored));d1=P.restoration_decision(initial,restored['readback'],restored['reapply']);d2=P.restoration_decision(initial,restored['readback'],restored['reapply']);need(d1==d2 and before==(initial,restored),'Policy mutates original saved failure or depends on external state')
    check('repeated_policy_is_pure_and_saved_failure_stays_FAIL',pure_repeat)
    diffs=[]
    for d in f['semantic_diff']:
        a=definitions(d['original']['path']);b=definitions(d['candidate']['path']);changed=sorted(k for k in set(a)|set(b) if a.get(k)!=b.get(k));need(changed==sorted(d['changed_top_level_definitions']),'Unexpected source definition changes');diffs.append(dict(original=d['original'],candidate=d['candidate'],independently_changed_definitions=changed))
    author=read(author_receipt);need(author['passed']==58 and author['failed']==0 and author['status']=='PASS','Unchanged independent58 incomplete')
    for b in refs+copied:need(binding(b['path'])==b,'Source changed during review')
    result=dict(status='INDEPENDENT_SOURCE_FIXTURES_ACCEPTED' if all(x['status']=='PASS' for x in rows) else 'CHANGES_REQUESTED',freeze=freeze_ref,source_copies=copied,independent_definition_diffs=diffs,unchanged58=binding(author_receipt),additional_checks=rows,additional_passed=sum(x['status']=='PASS' for x in rows),additional_failed=sum(x['status']=='FAIL' for x in rows),reviewer_source=binding(__file__),readme=binding(Path(__file__).with_name('README_S6D_RESTORATION_REVIEW_V5.md')),historical_failure=f['historical_failure'],authority=f['authority'],hardware_calls=0,model_calls=0,scope='Accepted source/fixture semantics only: exact static/identity/ancillary/USB state, verified immediate gain and finite dynamic current gain only under enabled firmware3.2.1 AGC. Preserved V4 FAIL is not reclassified. This receipt demonstrates no current hardware recovery, command execution, physical QA or production queue admission.',remaining_root_gates=['Separately source-bound locked getter-only recovery and fresh physical state','Unchanged historical failure plus explicit authorized recovery binding','New QA IDs, literal V5/bridgeV2 queue predicates and root resource/nonoverlap admission'])
    save(out/'INDEPENDENT_REVIEW.json',result);print(json.dumps(binding(out/'INDEPENDENT_REVIEW.json')));need(result['additional_failed']==0,'Independent checks failed')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source-root','freeze','baseline','author-receipt','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(a.source_root,a.freeze,a.baseline,a.author_receipt,a.output)
