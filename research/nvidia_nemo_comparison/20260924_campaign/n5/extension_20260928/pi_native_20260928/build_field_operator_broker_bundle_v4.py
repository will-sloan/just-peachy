"""Build a pinned qualification capsule without issuing policy; README_FIELD_OPERATOR_BROKER_QUALIFICATION_V6.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,base64,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('plan','projection','owners','output'):p.add_argument('--'+n,required=True,type=Path)
 args=p.parse_args();args.output.mkdir()
 me=psutil.Process()
 (args.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
 from field_owner_binding_v1 import pack
 from field_operator_session_plan_v3 import encoded
 here=Path(__file__).resolve().parent
 def checked(path,size=None,digest=None):
  raw=Path(path).read_bytes()
  if size is not None and (len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest):raise ValueError('Source pin drift')
  return raw
 old=json.loads(checked(args.plan));projection=json.loads(checked(args.projection));owners=json.loads(checked(args.owners))
 if any(r['exact_alive'] is not False for r in owners['pi']) or owners['utility_pid_absent_after_ssh'] is not True:raise ValueError('Closed owner review')
 allowners=[r['owner'] for r in owners['pi']]+[owners['utility_owner']]
 changes={'field_operator_controller_v4.py':'field_operator_controller_v5.py','field_operator_entry_v7.py':'field_operator_entry_v9.py','field_operator_parent_v8.py':'field_operator_parent_v11.py',
  'field_operator_broker_entry_v1.py':'field_operator_broker_entry_v4.py','field_operator_broker_gate_v2.py':'field_operator_broker_gate_v6.py',
  'field_operator_broker_stage_v1.py':'field_operator_broker_stage_v3.py','field_operator_broker_v2.py':'field_operator_broker_v5.py',
  'field_operator_chooser_v2.py':'field_operator_chooser_v3.py'}
 files={};source_pins=[]
 for row in projection['rows']:
  checked(row['path'],row['bytes'],row['sha256'])
  name=changes.get(row['name'],row['name']);path=here/name if name!=row['name'] else Path(row['path'])
  raw=checked(path);files['code/'+name]=raw
  source_pins.append(dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
 for name in ('field_operator_qualification_v3.py','field_operator_broker_qualification_v1.py'):
  raw=checked(here/name);files['code/'+name]=raw;source_pins.append(dict(path=str(here/name),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
 if len(files)!=64 or sum(map(len,files.values()))>2097152 or any(len(raw)>131072 for raw in files.values()):raise ValueError('Original capsule guard')
 selected={name.split('/')[1] for name in files}
 missing={}
 for name,raw in files.items():
  if name.endswith('.py'):
   compile(raw,name,'exec')
   for n in ast.walk(ast.parse(raw)):
    modules=[n.module] if isinstance(n,ast.ImportFrom) else [a.name for a in n.names] if isinstance(n,ast.Import) else []
    for module in modules:
     dependency=(module or '').split('.')[0]+'.py'
     if (here/dependency).is_file() and dependency not in selected:missing.setdefault(name,set()).add(dependency)
 expected={'code/archive_stop_sessions_v1.py':{'app_bounded_artifacts_v1.py'},'code/field_operator_controller_v5.py':{'field_archive_v3.py'},
  'code/d1_process_entry_v1.py':{'d1_recovery_process_v1.py'}}
 if missing!=expected:raise ValueError('New unresolved local imports: '+repr(missing))
 child=[]
 drop={'field_operator_gate_v7.py','OPERATOR_RESOURCE_POLICY_V4.json'}
 childchanges={'field_operator_controller_v4.py':'field_operator_controller_v5.py','field_operator_entry_v6.py':'field_operator_entry_v9.py','field_operator_parent_v6.py':'field_operator_parent_v11.py',
  'field_operator_qualification_v2.py':'field_operator_qualification_v3.py'}
 data={}
 for row in old['stage_files']:
  raw=checked(row['local'],row['bytes'],row['sha256']);name=Path(row['relative']).name
  if row['relative'].startswith('data/'):data[name]=json.loads(raw)
  elif name not in drop:
   name=childchanges.get(name,name)
   if 'code/'+name not in files:raise ValueError('Child code outside outer capsule')
   child.append(name)
 if len(child)!=51 or len(set(child))!=len(child) or set(data)!={'live_config.json','settings.json','n2_runtime.json','DATA_SCHEMA.json'}:raise ValueError('Exact child code/data')
 a=old['admission'];a['preflight_pi_owners']=pack(allowners)
 a.pop('qualification',None)
 # The local stager writes fresh policy/time/root/session bindings; this is an unadmitted historical template.
 template=dict(schema='just-peachy.broker-child-template.v1',source_root=a['output_root'],admission=a,code_names=child,data_files=data)
 baseline=dict(boot_id=a['boot_id'],install_sha256=a['install_sha256'],live_config_sha256=a['live_config_sha256'],
  display_sha256='c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b')
 config=dict(baseline=baseline,preflight_pi_owners=pack(allowners),installed_release=a['installed_release'],
  python=a['python'],alsa_config=a['installed_release']+'/config/alsa_hw_only_v1.conf',
  installed_manifest_sha256='274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0',
  qualification=dict(schema='just-peachy.two-session-visible-qualification.v1',count=2,stop_after_samples=80000))
 files['broker/CONFIG.json']=encoded(config);files['broker/TEMPLATE.json']=encoded(template)
 if len(files['broker/CONFIG.json'])>65536 or len(files['broker/TEMPLATE.json'])>131072:raise ValueError('Control slots')
 manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for n,raw in sorted(files.items())])
 bundle=dict(manifest=manifest,files={n:base64.b64encode(raw).decode() for n,raw in sorted(files.items())})
 raw=encoded(bundle)
 if len(raw)>1048576:raise ValueError('Host prepared bundle ceiling')
 (args.output/'BUNDLE.json').open('xb').write(raw);assert (args.output/'BUNDLE.json').read_bytes()==raw
 review=dict(status='PREPARED_EXACT_CAPSULE_NOT_ADMITTED',outer_files=64,outer_bytes=sum(len(v) for k,v in files.items() if k.startswith('code/')),
  child_code_files=len(child),child_data_files=len(data),template_bytes=len(files['broker/TEMPLATE.json']),config_bytes=len(files['broker/CONFIG.json']),
  source_pins=source_pins,manifest_sha256=hashlib.sha256(encoded(manifest)).hexdigest(),bundle_sha256=hashlib.sha256(raw).hexdigest(),
  owner_count=len(allowners),external_imports={k:sorted(v) for k,v in missing.items()},
  native_executed=False,policy_issued=False,requires_fresh_owners_and_census_before_dispatch=True)
 (args.output/'REVIEW.json').open('x').write(json.dumps(review))
 print(json.dumps({k:v for k,v in review.items() if k not in ('source_pins','external_imports')}))
if __name__=='__main__':raise SystemExit(main())
