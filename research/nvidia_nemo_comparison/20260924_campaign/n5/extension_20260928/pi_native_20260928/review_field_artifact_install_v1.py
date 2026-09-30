"""Independent installed artifact review; README_REVIEW_FIELD_ARTIFACT_INSTALL_V1.md."""
import argparse
import hashlib
import json
from pathlib import Path
import psutil


def main():
    psutil.Process().cpu_affinity([14])
    p=argparse.ArgumentParser();p.add_argument('--run',choices=['field-artifact-install-v1','field-artifact-install-v2'],required=True);args=p.parse_args()
    from dispatch_geometry_v2 import remote, PRIVATE
    report=remote('RUN='+repr(args.run)+'\n'+r'''
import os,sys,resource
sys.dont_write_bytecode=True
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
import json,hashlib,subprocess,fcntl,zipfile,ast,wave
from pathlib import Path
r=Path.home()/'JustPeachy/research/nemotron-20260928'/RUN
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(r/'ADMISSION.json');result=read(r/'RESULT.json');d=read(r/'DISPATCH_RESULT.json');env=read(r/'LIVE_ENVELOPE.json')
for row in a['files']:assert sha(row['path'])==row['sha256']
prior=Path(a['installed_release']);assert {p.relative_to(prior).as_posix():sha(p) for p in prior.rglob('*') if p.is_file()}==a['installed_files']
assert not a['capture'] and not a['models_loaded']
assert env['address_space']==[768*1024**2]*2 and env['stack']==[1024**2]*2 and env['affinity']==[2,3]
assert env['properties']['TasksMax']=='64' and env['properties']['RuntimeMaxUSec']=='5min' and env['properties']['TimeoutStopUSec']=='1min'
assert int(env['properties']['LimitFSIZE'])==32*1024**2 and int(env['cpu_max'][0])/int(env['cpu_max'][1])==2
assert not d['log_overflow'] and not d['memory_guard']
owners=list(r.rglob('*OWNER.json'));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for p in owners:
 o=read(p);assert o['boot_id']==boot==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for path in [r.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
build=read(r/'CANDIDATE_BUILD.json');selected=Path(build['staged']['path']);manifest=read(selected/'RELEASE_MANIFEST.json')
assert sha(selected/'RELEASE_MANIFEST.json')==build['manifest_sha256']
assert not build['pointer_activated'] and not build['assets_copied']
expected={row['path']:row for row in manifest['files']}
assert set(expected)|{'RELEASE_MANIFEST.json'}=={p.relative_to(selected).as_posix() for p in selected.rglob('*') if p.is_file()}
for name,row in expected.items():assert (selected/name).stat().st_size==row['bytes'] and sha(selected/name)==row['sha256']
for original,target in build['mapping'].items():assert sha(r/original)==sha(selected/target)
with zipfile.ZipFile(build['built']['archive']) as z:
 assert set(z.namelist())==set(expected)|{'RELEASE_MANIFEST.json'}
 for name,row in expected.items():assert hashlib.sha256(z.read(name)).hexdigest()==row['sha256']
assert sha(build['built']['archive'])==build['built']['sha256']
contract=read(selected/'config/field_contract.json');limits=read(selected/'config/artifact_limits.json');binding=contract['artifact_limits']
canonical=hashlib.sha256(json.dumps(limits,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
assert canonical==binding['canonical_sha256']=='6b066469dc6baca11450d3710928a282416eadb5a17dcaa557a6c797191d89fd'
assert binding['sha256']==sha(selected/'config/artifact_limits.json') and binding['maximum_artifact_bytes']==46034476
oldcontract=read(prior/'config/field_contract.json');assert {k:v for k,v in contract.items() if k!='artifact_limits'}==oldcontract
assert not any((r/'deployment'/n).exists() for n in ['state.json','current.json','previous.json'])
for name,expected_sha in [('n2_runtime.json',a['n2_runtime_sha256']),('live_config.json',a['live_config_sha256'])]:assert sha(r/'data'/name)==expected_sha
closure=read(r/'OWNERSHIP_CLOSURE.json');assert closure['outer_released'] and not (r/'data/runtime.lock').exists()
with (r/'data/.runtime.guard').open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (r/'data/source_receipts').exists() and not (r/'data/sessions').exists()
health=read(r/'INSTALLED_HEALTH.json');assert health['artifact_limits']==limits and health['artifact_limits_binding']==binding
for label in ['missing-binding','missing-file','wrong-file-hash','wrong-canonical-hash','short-frame-bound','small-reservation','wrong-path']:
 assert read(r/(label+'.json'))['rejected'] and not (r/label/'must-not-create-data').exists()
summary=dict(status='REVIEWED_INSTALLED_ARTIFACT_FAILURE_ONLY',natural_exit=d['exit_code'],result=result,
 manifest_sha256=build['manifest_sha256'],version=manifest['version'],package=build['built'],
 owner_count=len(owners),baseline_unchanged=True,capture_closed=True,
 aggregate_sampled_rss_bytes=max((x.get('aggregate_rss_bytes',0) for x in d['samples']),default=None))
if result['status']=='FAILED_PRESERVED':
 assert d['exit_code']==1 and 'SyntaxError' in result['error'] and 'utf-8' in result['error']
 assert closure['borrowed']==dict(opened=0,closed=0) and not closure['controller_closed']
 summary.update(scope='Seven config preflights and health completed; controller import failed before construction/models/capture',
                preserved_invalid_utf8_controller=True,derivation_v1_hashes_are_intended_utf8_not_actual=True)
else:
 assert d['exit_code']==0 and result['status']=='PASS_INSTALLED_ARTIFACT_CONTRACT_AND_NATIVE_FACTORY_ONLY'
 assert len(result['rejections'])==8 and read(r/'conflicting-store-before-engine.json')['rejected']
 assert result['model_loads']==0 and not any(result[k] for k in ['capture','GUI','empty_wav_is_recording','pipeline_start_called','source_boundaries_executed','pointer_activated'])
 assert result['engine_type']=='N2Engine' and result['constructor_received_before_archive']
 assert result['artifact_limits']==result['store_policy']['artifact_limits']==limits
 writer=result['native_factory'];assert writer['clean'] and writer['physical_sink_closed'] and not writer['worker_alive'] and writer['accepted']==writer['completed']==1
 assert writer['sink']['byte_limit']==16*1024**2
 lines=[json.loads(x) for x in (r/'native-factory/events.jsonl').read_text().splitlines()]
 assert len(lines)==2 and lines[0]['seq']==0 and lines[0]['value']==dict(kind='installed_artifact_binding',synthetic_no_capture=True)
 assert lines[1]==dict(format='footer',count=1,status='COMPLETE')
 ep=Path(result['archive_path']);assert ep.parent.parent.parent==r/'data/conversations'
 meta=read(ep/'epoch.json');assert meta==result['archive_metadata'] and meta['state']=='CLOSED' and not meta['worker_alive'] and not meta['archive_error']
 assert meta['artifact_limits']==limits and meta['artifact_metrics']['events']['byte_limit']==16*1024**2
 assert meta['artifact_metrics']['audio']['max_frames']==2080000 and meta['recorded_samples']==meta['source_samples']==0
 assert (ep/'model_input.f32le').stat().st_size==0 and (ep/'model_input.wav').stat().st_size==44
 with wave.open(str(ep/'model_input.wav'),'rb') as wav:assert wav.getnframes()==0 and wav.getframerate()==16000 and wav.getnchannels()==1
 assert closure['borrowed']==dict(opened=1,closed=1) and closure['controller_closed'] and closure['worker_joined'] and closure['pending_commands']==0
 for name in ['app/controller.py','native/field_entry_v5.py','app/pipeline.py']:
  data=(selected/name).read_bytes();data.decode('utf-8');ast.parse(data)
 derivation=read(r/'ARTIFACT_INSTALL_DERIVATION_V2.json')
 for row in derivation['repairs'].values():assert row['new_sha256']==row['intended_utf8_sha256']
 summary.update(status='PASS_INSTALLED_ARTIFACT_BINDING_AND_ACTUAL_NATIVE_FACTORY_ONLY',scope='No live/source start, model, GUI, pointer activation or long-run acceptance')
summary['target_bytes']=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert summary['target_bytes']<a['target_output_max_bytes']==16*1024**2
print(json.dumps(summary))
''')
    report['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (PRIVATE/(args.run+'-evidence')/'REVIEW.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in ['result','package']}))


if __name__=='__main__':main()
