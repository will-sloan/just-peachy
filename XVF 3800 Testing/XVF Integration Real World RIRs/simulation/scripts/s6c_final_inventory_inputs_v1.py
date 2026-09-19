"""Resolve original observer metadata only; README_S6C_FINAL_INVENTORY_INPUTS_V1.md."""
from __future__ import annotations
import argparse,hashlib,importlib,json,types
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
PIN='2677136bfb6c9f3cfbeb5da989d9829bcc8b2e57b75863c59898c2666d034574'
p=HERE/'s6c_final_inventory_refresh_v1.py'
if hashlib.sha256(p.read_bytes()).hexdigest()!=PIN:raise ValueError('Held final integration source differs')
R=importlib.import_module('s6c_final_inventory_refresh_v1')
R.require(Path(R.__file__).resolve()==p,'Import origin')

def original_paths(F,assembly):
 """No suffix-wide recursive walk. Only original observer output families."""
 roots=[(F.REPORT/'observer_fast_v1/attempts','*.json'),(F.REPORT/'observer_fast_v2/attempts','*.json')]
 for b in assembly['fast_manifests']:
  p=Path(b['path'])
  if p.parent.parent.name=='paced_controls':root=F.REPORT/'paced_controls'/p.parent.name/'observer_invocations'
  elif p.parent.parent.name=='long_b36':root=F.REPORT/'long_b36'/p.parent.name/'observer_invocations'
  else:continue
  roots.append((root,'*/SCANNER_OUTCOME.json'))
 paths=[]
 for root,pattern in roots:
  for p in sorted(root.glob(pattern)):
   R.require(p.resolve()==p.absolute(),'Observer path resolution differs');paths.append(p)
 R.require(len(paths)<=20000 and len(paths)==len(set(paths)),'Bounded unique original observers')
 return roots,paths

def prepare(args):
 F,ctx,api,recovery=R.make_context();F.quiet()
 assembly,ab=R.read_input(args.assembly);R.validate_assembly(F,ctx,api,recovery,assembly)
 out=Path(args.output).resolve();R.require(out.parent==F.REPORT/'execution_inventory' and not out.exists(),'Fresh exact inventory input namespace');out.mkdir()
 reader=F.B.MetadataReader(out);before=ctx.sources()+[R.bind(__file__),R.bind(HERE/'README_S6C_FINAL_INVENTORY_INPUTS_V1.md')]
 roots,paths=original_paths(F,assembly);bindings=[];rows=[]
 declared={F.B.canonical(b['path']):b for b in assembly['fast_manifests']}
 for p in paths:
  F.quiet();d,b=reader.read(p)
  R.require(d['schema'] in ('s6c.fast_resource_observer_exit.v1','s6c-historical-fast-observer-outcome.v1'),'Unexpected observer metadata schema')
  F.V.v4.owner(d['owner']);mb=d.get('manifest');matched=bool(mb and declared.get(F.B.canonical(mb['path']))==mb)
  bindings.append(b);rows.append(dict(binding=b,schema=d['schema'],entry=d.get('entry'),status=d.get('status'),error=d.get('error'),owner=d['owner'],manifest=mb,job_id=d.get('job_id'),wrapper=d.get('wrapper'),manifest_in_finite_fast_assembly=matched,scope='Observer metadata observation only; does not add a native session or prove owner closure.'))
 index=F.B.write_new(out/'OBSERVER_INDEX.json',dict(schema='s6c-fast-observer-index.v1',status='COMPLETE_METADATA_ENUMERATION',assembly=ab,receipts=bindings,discovery=[dict(root=str(r),pattern=g) for r,g in roots],scope='All original receipts at the explicit observer paths, including failed, preparation and unmatched metadata. No outcome filtering; index membership is not native completion or current owner closure.'))
 # Base V7 verifies original exit schema/finite owners, without invoking the
 # controls recovery facade's full80-cell/current-owner admission here.
 F.V.admit_observer_index(reader,index)
 spec=R.resolve_spec(types.SimpleNamespace(assembly=args.assembly,observer_index=[index['path'],index['sha256']],output=str(out/'REGISTERED_SPEC.json')))
 after_roots,after_paths=original_paths(F,assembly)
 R.require((roots,paths)==(after_roots,after_paths),'Observer set changed during preparation')
 R.require(all(R.bind(b['path'])==b for b in bindings),'Original observer bytes changed during preparation')
 R.require(ctx.sources()+[R.bind(__file__),R.bind(HERE/'README_S6C_FINAL_INVENTORY_INPUTS_V1.md')]==before,'Preparation source changed');F.quiet()
 inventory=F.B.write_new(out/'OBSERVER_METADATA_ROWS.json',rows)
 # Deliberately not an executable authority: actual closure/diagnostic proofs
 # and root declarations must be supplied later by root, in a new document.
 template=F.B.write_new(out/'ROOT_AUTHORITY_DRAFT.json',dict(schema='s6c-inventory-refresh-authority.v1',status='DRAFT_NOT_AUTHORIZED',spec=spec,helper=R.bind(F.__file__),integration_helper=R.bind(R.__file__),integration_readme=R.bind(HERE/'README_S6C_FINAL_INVENTORY_REFRESH_V1.md'),integration_sources=assembly['sources'],recovery=recovery,all_model_paced_long_work_closed=False,no_concurrent_research_writers=False,completed_continuous_manifests=assembly['required_continuous_manifests'],original_continuous_closure=None,admitted_continuous_diagnostics=None,scope='Required exact schema/input fields only. completed_continuous_manifests lists required targets here; DRAFT status/false declarations do not assert their closure. Root must issue a new authorized document after independent closure/diagnostics admission.'))
 counts=dict(total=len(rows),by_entry=dict(Counter(str(x['entry']) for x in rows)),by_status=dict(Counter(str(x['status']) for x in rows)),with_error=sum(x['error'] is not None for x in rows),unmatched_manifest=sum(not x['manifest_in_finite_fast_assembly'] for x in rows))
 return F.B.write_new(out/'PREPARATION_RECEIPT.json',dict(schema='s6c-final-inventory-inputs.v1',status='RESOLVED_INPUTS_NO_CENSUS_NO_AUTHORIZATION',assembly=ab,observer_index=index,registered_spec=spec,observer_rows=inventory,authority_draft=template,counts=counts,sources=before,metadata_sources=reader.sources,models=0,actual_inventory=False,current_owner_checks=False,scope='Original observer metadata and unchanged49-manifest assembly only. Failure/unknown exit/native-source reuse accounting remains the held future census responsibility; no interpretation of prepared cells as executed.'))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--assembly',nargs=2,required=True);p.add_argument('--output',required=True);print(json.dumps(prepare(p.parse_args()),indent=2))
