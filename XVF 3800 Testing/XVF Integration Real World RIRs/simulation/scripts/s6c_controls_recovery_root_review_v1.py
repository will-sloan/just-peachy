"""Independent actual-document review. See README_S6C_CONTROLS_RECOVERY_ROOT_REVIEW_V1.md."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
import argparse,json,hashlib
import s6c_controls_recovery_inventory_v1 as M
def main():
 p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);args=p.parse_args()
 M.require(__import__('re').fullmatch(r'[A-Za-z0-9_-]{1,64}',args.namespace),'Simple namespace')
 out=M.REPORT/'independent_review'/args.namespace;M.require(not out.exists(),'Fresh review');out.mkdir()
 M.require(M.binding(M.__file__)['sha256']=='e2f6dece6c9062e35f8cdeece73376a670e4ba3d390059a8b04de85548afadf8','Held overlay')
 v=M.load_v7();reader=v.base.MetadataReader(out)
 def read(b):return v.bound(reader,b)[0]
 rb=M.binding(M.REPORT/'runtime_failure_review/external_lease_recovery/controls_cross_volume_v1/RESULT.json')
 M.require(rb['sha256']=='c9a3a0394f19920bb886156d8f7d8ede2773ad509f6338c61c8882e51f0007a4','Actual root recovery')
 result=read(rb);admission=read(result['admission']);authority=read(result['authority']);audit=read(result['root_audit']);lease=read(result['lease_release']['archived_binding']);dispatch=read(audit['failed_dispatcher'])
 base=[result,rb,admission,result['admission'],authority,audit,result['root_audit'],lease,dispatch]
 def check(documents):return M.validate_result_documents(v,*documents)
 expected=check(base);M.require(len(expected)==162,'Actual exact original owner count')
 names=['actual_bound_recovery_document_chain']
 faults=[
 ('duplicate_owner_substitution',lambda d:d[0]['current_original_owner_observations'].__setitem__(1,deepcopy(d[0]['current_original_owner_observations'][0]))),
 ('naive_actual_admission_time',lambda d:d[2].__setitem__('created_utc','2026-09-12T05:00:00')),
 ('release_source_path_substitution',lambda d:d[2]['release_source'].__setitem__('path',str(M.HERE/'wrong_release.py'))),
 ('original_completion_substitution',lambda d:d[0]['original_completion'].__setitem__('sha256','0'*64)),
 ('archive_same_hash_wrong_namespace',lambda d:d[0]['lease_release']['archived_binding'].__setitem__('path',str(M.REPORT/'wrong/PRESERVED_ORIGINAL_QUIET_LEASE.json')))]
 for name,change in faults:
  d=deepcopy(base);change(d)
  try:check(d)
  except (ValueError,KeyError,TypeError):names.append(name)
  else:raise AssertionError('Accepted fault '+name)
 before=dict(vars(v));api=M.make_inventory(rb)
 M.require(api.collect.__code__ is v.collect.__code__ and api.collect.__globals__ is not v.collect.__globals__,'Unchanged collect/private namespace')
 M.require(vars(v).keys()==before.keys() and all(vars(v)[k] is x for k,x in before.items()),'No shared V7 mutation')
 M.require(api.kind_of is v.kind_of and api.admit_plan is v.admit_plan,'Unrelated admission unchanged')
 names+=['identical_collect_code_private_globals','original_v7_globals_unchanged','original_plan_and_kind_functions']
 value=dict(schema='s6c-independent-controls-recovery-root-review.v1',status='PASS_ACTUAL_DOCUMENT_AND_PRIVATE_SOURCE_REVIEW',created_utc=datetime.now(timezone.utc).isoformat(),checks=len(names),names=names,sources=[M.binding(__file__),M.binding(M.__file__),M.binding(M.HERE/'README_S6C_CONTROLS_RECOVERY_INVENTORY_V1.md')],recovery=rb,producer_checks=read(M.binding(M.REPORT/'runtime_failure_review/recovery_inventory_checks_v1/SOURCE_CHECKS.json')),metadata_sources=reader.sources,scope='Root read entire overlay and normalizer. Exact actual recovery documents and independent fault checks; no full80-cell admission, native payload/scoring/model/lease actions. Separately approved actual admission remains required.')
 print(json.dumps(v.base.write_new(out/'REVIEW_RECEIPT.json',value)))
if __name__=='__main__':main()

