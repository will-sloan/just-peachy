"""Source/tiny metadata review; README_S6C_FAST_ANALYSIS_COMPONENT_REVIEW.md."""
import argparse,hashlib,json,tempfile,types
from pathlib import Path
import s6c_fast_observer_analysis_v1 as A

def run(output):
 output.mkdir(parents=True,exist_ok=False);done=[]
 def ck(n,v=True):assert v,n;done.append(n)
 def reject(n,f):
  try:f()
  except (ValueError,KeyError,TypeError):ck(n);return
  raise AssertionError(n)
 ck('exact held adapter',A.bind(A.HERE/'s6c_fast_observer_analysis_v1.py')['sha256']=='e5497ec28daa6c5f823fde53e7f1253cf655427cd30f8eab067de5e9a4c0f530')
 before=A.sources();owner=A.checks();ck('all38 held owner checks reproduced',owner['check_count']==38)
 v=A.load_module('s6c_execution_inventory_v7',A.V7_SHA)
 with tempfile.TemporaryDirectory(prefix='s6c_fast_analysis_review_') as tmp:
  root=Path(tmp);out=root/'reader';out.mkdir()
  index=A.write_new(root/'index.json',dict(schema='s6c-fast-observer-index.v1',status='COMPLETE_METADATA_ENUMERATION',receipts=[]))
  request=A.write_new(root/'request.json',{})
  factory=A.reader_factory(v,index);reader=factory(out)
  ck('real V7 attaches exact synthetic index',reader.fast_observer_index==index and reader.fast_observer_receipts==[])
  Path(index['path']).write_text('{}',encoding='utf-8');reject('changed observer buffer rejected before reader use',lambda:factory(out))
  Path(index['path']).unlink();A.write_new(root/'index.json',dict(schema='s6c-fast-observer-index.v1',status='COMPLETE_METADATA_ENUMERATION',receipts=[]))
  for kind in A.MODES:
   plan=dict(kind=A.MODES[kind][2][0]);binding=dict(path=str(root/'manifest.json'),bytes=2,sha256='0'*64)
   fake=types.SimpleNamespace(**vars(v));fake.kind_of=lambda p:p['kind'];fake.source_bindings=lambda:[]
   fake.admit_plan=lambda r,b:(plan,b,'spec');fake.admit_long=lambda r,b:(plan,b,'a','g');fake.validate_outer=lambda r,p,**kw:dict(plan=plan,kwargs=kw)
   adapter,_=A.make_adapter(kind,index,request,[],fake)
   ck(kind+' admitted metadata API preserves tuple',adapter.inventory.admit_plan(None,binding)==(plan,binding,'spec'))
   ck(kind+' long tuple and keyword APIs preserved',adapter.inventory.admit_long(None,binding)==(plan,binding,'a','g') and adapter.inventory.validate_outer(None,None,observer_receipts=[])['kwargs']=={'observer_receipts':[]})
   plan['kind']='nonmatching';reject(kind+' admitted callback rejects wrong family',lambda:adapter.inventory.admit_plan(None,binding))
  actual=root/'buffer.json';actual.write_bytes(b'{"x":1}');b=A.bind(actual);wrapped=A.bound_wrapper(lambda p:A.bind(p),[b]);ck('explicit same buffer binding accepted',wrapped(actual)==b)
  actual.write_bytes(b'{"x":2}');reject('same length replacement rejected',lambda:wrapped(actual))
  reject('conflicting duplicate authority rejected',lambda:A.unique_bindings([b,dict(b,sha256='f'*64)]))
 ck('EDGE path exact',A.EDGE.resolve()==Path('C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe').resolve())
 ck('held sources unchanged',before==A.sources())
 result=dict(schema='s6c-fast-analysis-independent-review.v1',status='PASS_SOURCE_AND_TINY_CONTEXT',independent_checks=len(done),checks=done,reproduced_owner_checks=owner['check_count'],owner_reproduction=A.write_new(output/'REPRODUCED_CHECKS.json',owner),sources=before+[A.bind(__file__),A.bind(A.HERE/'README_S6C_FAST_ANALYSIS_COMPONENT_REVIEW.md')],review_scope='Read held source and maintained README plus exact original API call sites for all six modes. Original metadata orchestration uses private globals; scientific functions/classes retain exact object/code authority. Real V7 reader tested only against synthetic index; no actual preparation/conversion/runtime source consumed.',findings=[],limitations='marshal signatures are diagnostic only; exact code-object identity/source bindings enforce reuse. Source review is not proof of actual runtime closure or successful scientific conversion.',model_calls=0,actual_native_reads=0,actual_preparations=0)
 return A.write_new(output/'REVIEW_RECEIPT.json',result)

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',required=True,type=Path);print(json.dumps(run(p.parse_args().output),indent=2))
if __name__=='__main__':main()
