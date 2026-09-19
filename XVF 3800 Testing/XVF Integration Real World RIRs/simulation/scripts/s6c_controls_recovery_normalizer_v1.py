"""Exact controls recovery join; README_S6C_CONTROLS_RECOVERY_NORMALIZER_V1.md."""
from __future__ import annotations
import argparse,importlib,json,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
NORMALIZER_SHA='d94507a8f7f4246b8f6a377b22fd50b9c2487761a3638e32bd650d49ac953b0b'
ANALYSIS_SHA='a47a208de821f485fee01c8ae433f70673c241c587fca357bbcfd7c31d469a2a'
OVERLAY_SHA='e2f6dece6c9062e35f8cdeece73376a670e4ba3d390059a8b04de85548afadf8'

def require(v,m):
 if not v:raise ValueError(m)

def load(name,sha):
 import hashlib
 path=HERE/(name+'.py');raw=path.read_bytes();require(len(raw)<=2**20 and hashlib.sha256(raw).hexdigest()==sha,'Held source differs: '+name)
 module=importlib.import_module(name);require(Path(module.__file__).resolve()==path,'Import origin');return module

def build_context(N,base_A,analysis,inventory,recovery):
 """Identical old run code, private module/source callbacks only."""
 A=types.SimpleNamespace(**vars(base_A));A.sources=analysis.sources;A.make_adapter=analysis.make_adapter
 ns=dict(N.run.__globals__)
 def modules(name):
  if name=='s6c_fast_observer_analysis_v1':return A
  if name=='s6c_execution_inventory_v7':return inventory
  return N.module(name)
 def sources():
  return base_A.unique_bindings(N.sources()+analysis.sources()+[N.exact(__file__)[1],N.exact(HERE/'README_S6C_CONTROLS_RECOVERY_NORMALIZER_V1.md')[1],recovery])
 ns.update(module=modules,sources=sources)
 run=base_A.private_function(N.run,ns)
 require(run.__code__ is N.run.__code__ and run.__globals__ is not N.run.__globals__,'Original normalizer run/private identity')
 for name in ('historical_rows','analysis_chain','runtime_row','historical_tail','historical_condition','owners_closed','require_distinct_runtime_sessions'):
  require(ns[name] is N.run.__globals__[name],'Original normalization formula changed')
 return types.SimpleNamespace(run=run,sources=sources,namespace=ns)

def context(pair):
 N=load('s6c_runtime_metadata_normalizer_v1',NORMALIZER_SHA)
 C=load('s6c_controls_recovery_analysis_v1',ANALYSIS_SHA);R=load('s6c_controls_recovery_inventory_v1',OVERLAY_SHA)
 base,analysis,recovery=C.context(pair);inventory=R.make_inventory(recovery)
 return N,build_context(N,base,analysis,inventory,recovery),recovery

def finite_spec(spec,recovery,manifest_sha):
 require(spec.get('external_recovery')==recovery,'Explicit exact recovery binding in normalization spec')
 require(not spec.get('physical_inventories'),'This finite join does not rewrite whole-study physical inventory')
 rows=spec['requests'];require(len(rows)==2 and {r['generation'] for r in rows}=={'baseline','research'},'Both original controls generations required separately')
 require(all(r['kind']=='historical' and r['manifest']['sha256']==manifest_sha for r in rows),'Only recovered controls manifest')
 require(rows[0]['manifest']==rows[1]['manifest'],'Same actual controls manifest')

def run(args):
 N,adapter,recovery=context(args.recovery);raw,sb=N.exact(args.spec);require(sb['sha256']==args.spec_sha256,'Explicit spec hash')
 finite_spec(N.parse(raw),recovery,'8fb281fe4788e549cfb294bdcfb6adf326144cfeefbb1d09c76cf22f7b26c044')
 return adapter.run(args)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=['run']);p.add_argument('--recovery',nargs=2,required=True);p.add_argument('--spec',type=Path,required=True);p.add_argument('--spec-sha256',required=True);p.add_argument('--namespace',required=True)
 print(json.dumps(run(p.parse_args()),indent=2))
