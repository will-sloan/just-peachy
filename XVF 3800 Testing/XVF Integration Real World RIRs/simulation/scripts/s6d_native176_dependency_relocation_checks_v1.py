"""Tiny path-relocation negatives; README_S6D_NATIVE176_DEPENDENCY_RELOCATION_V1.md."""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import traceback


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();assert out.drive.casefold()=='g:' and 'review_fixtures' in out.parts and not out.exists();out.mkdir(parents=True)
    path=a.source_root/'s6d_native176_dependency_relocation_v1.py';s=importlib.util.spec_from_file_location('relocation_checks',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    parent=m.read(m.PARENT);diagnosis=m.read(m.DIAGNOSIS);original=deepcopy(parent);rows=diagnosis['dependency_rows'];new=m.relocation_pairs(parent,rows);provenance=dict(fixture_only=True);proposal=deepcopy(parent);proposal.update(status=m.PROPOSED,dependencies=new,dependency_path_correction=provenance);results=[]
    def check(name,fn):
        try:fn();results.append(dict(name=name,status='PASS'))
        except BaseException:results.append(dict(name=name,status='FAIL',error=traceback.format_exc()))
    def reject(fn):
        try:fn()
        except (ValueError,KeyError,TypeError):return
        raise AssertionError('Expected fail-closed rejection')
    check('exact_six_content_identical_relocations_allowed',lambda:m.assert_only_relocation(parent,proposal,new,provenance))
    for mode in ('reordered','omitted','foreign_path','changed_hash','changed_bytes','boolean_bytes','claimed_extra_change'):
        def adverse(mode=mode):
            changed=deepcopy(rows)
            if mode=='reordered':changed[0],changed[1]=changed[1],changed[0]
            elif mode=='omitted':changed.pop()
            elif mode=='foreign_path':changed[0]['actual_from_unchanged_dependencies_path_logic']['path']='G:/foreign/s4_h2_analysis.py'
            elif mode=='changed_hash':changed[0]['actual_from_unchanged_dependencies_path_logic']['sha256']='0'*64
            elif mode=='changed_bytes':changed[0]['actual_from_unchanged_dependencies_path_logic']['bytes']+=1
            elif mode=='boolean_bytes':changed[0]['actual_from_unchanged_dependencies_path_logic']['bytes']=True
            else:changed[0]['differing_fields']=['path','sha256']
            reject(lambda:m.relocation_pairs(parent,changed))
        check(mode+'_dependency_rejected',adverse)
    for mode in ('runnable','job','comparison','validation','output','provenance','extra_field'):
        def adverse(mode=mode):
            changed=deepcopy(proposal)
            if mode=='runnable':changed['status']='APPROVED_CLOSED_NATIVE_INPUTS'
            elif mode=='job':changed['jobs'][0]['job_id']='FOREIGN'
            elif mode=='comparison':changed['comparison_pairs'].pop()
            elif mode=='validation':changed['closed_input_validation']['sha256']='0'*64
            elif mode=='output':changed['output_root']='G:/foreign/scores'
            elif mode=='provenance':changed['dependency_path_correction']={}
            else:changed['invented_permission']=True
            reject(lambda:m.assert_only_relocation(parent,changed,new,provenance))
        check(mode+'_spec_change_rejected',adverse)
    assert parent==original
    receipt=dict(status='PASS' if all(x['status']=='PASS' for x in results) else 'FAIL',tests=results,passed=sum(x['status']=='PASS' for x in results),total=len(results),source=m.binding(path),fixture=m.binding(__file__),parent_metadata=m.binding(m.PARENT),diagnosis=m.binding(m.DIAGNOSIS),native_audio_journals_opened=0,metric_calls=0,model_calls=0,process_queries=0,approvals=0,scorer_retries=0)
    m.save(out/'RECEIPT.json',receipt);print(json.dumps(dict(status=receipt['status'],passed=receipt['passed'],total=receipt['total'],receipt=m.binding(out/'RECEIPT.json'))));return 0 if receipt['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
