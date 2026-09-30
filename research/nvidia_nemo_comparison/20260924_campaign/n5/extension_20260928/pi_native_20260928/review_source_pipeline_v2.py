"""Independent application source/shutdown boundary review; README_REVIEW_SOURCE_PIPELINE_V2.md."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path,PurePosixPath
import psutil
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE
from dispatch_b01_stack_v2 import SSH


def main():
    psutil.Process().cpu_affinity([14])
    x=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import ast,fcntl,hashlib,json,math,os,resource,signal,struct,subprocess,wave
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2);signal.alarm(110)
root=Path(ROOT)/'source-pipeline-v2'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
a=read(root/'ADMISSION.json');r=read(root/'RESULT.json');e=read(root/'LIVE_ENVELOPE.json');di=read(root/'DISPATCH_RESULT.json')
assert r['status']=='COLLECTED_NATIVE_ISOLATED_PIPELINE_CONTROLLER_BOUNDARY_CASES_ONLY' and di['exit_code']==0 and not di['log_overflow'] and not di['memory_guard']
assert not r['capture'] and not r['models_loaded'] and not r['gui_tested'] and not r['whole_controller_startup_qualified'] and r['unready_child_blocks_release']
assert e['properties']['LoadState']=='loaded' and e['properties']['ActiveState']=='active' and e['properties']['MainPID']==str(e['owner']['pid'])
assert e['properties']['RuntimeMaxUSec']=='5min' and e['properties']['TimeoutStopUSec']=='10s' and e['properties']['TasksMax']=='64'
assert e['address_space']==[768*1024**2]*2 and e['stack']==[1024**2]*2 and e['affinity']==[2,3]
assert int(e['properties']['LimitAS'])==768*1024**2 and int(e['properties']['LimitSTACK'])==1024**2 and int(e['properties']['LimitFSIZE'])==8*1024**2
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
assert a['child_address_space_bytes']==256*1024**2 and a['child_deadline_seconds']==90 and not a['capture']
for row in a['files']:assert sha(row['path'])==row['sha256']
assert r['source_modules']==dict(pipeline=str(Path(a['prototype'])/'app/pipeline.py'),controller=str(Path(a['prototype'])/'app/controller.py'))
with wave.open(a['source_wav'],'rb') as wav:pcm=[x[0]/32768 for x in struct.iter_unpack('<h',wav.readframes(15360))]
tree=ast.parse((Path(a['prototype'])/'app/_fir97_v1.py').read_text());taps=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TAPS' for t in n.targets));assert len(taps)==97
gain=f32(10**(3/20));reference=[f32(f32(math.fsum(pcm[(n-k)//3]*taps[k] for k in range(min(97,n+1))))*gain) for n in range(0,46080,3)]
reference_bytes=b''.join(struct.pack('<f',v) for v in reference)
names=['stop_tail','restart','empty_stop','callback_fault','restore_failure','start_failure','timing_failure']
assert [z['case'] for z in r['cases']]==names
metrics=[];child_peaks=[]
for name in names:
 d=root/name;row=read(d/'CASE_RESULT.json');c=read(d/'CHILD_RESULT.json');owner=read(d/'CHILD_OWNER.json')
 child_fault=name in ('callback_fault','restore_failure','start_failure');failed=child_fault or name=='timing_failure'
 source_samples=0 if name in ('empty_stop','start_failure') else (960 if name=='callback_fault' else 15360)
 journal_samples=0 if name=='timing_failure' else source_samples
 assert c.pop('terminal_sent') and c.pop('terminal_acknowledged') and c==row['terminal']['terminal']
 assert c['owner']==owner and c['address_space']==[256*1024**2]*2 and c['stack']==[1024**2]*2 and c['affinity']==[2,3]
 assert c['sent_samples']==source_samples and c['sent_blocks']==source_samples//160 and c['high_blocks']<=64 and c['high_bytes']<=65536
 assert c['audio_sha256']==hashlib.sha256(reference_bytes[:source_samples*4]).hexdigest()
 assert row['child_exit']==int(child_fault) and not row['terminal']['forced_close'] and row['terminal']['delivered_samples']==source_samples
 assert row['journal_samples']==journal_samples and row['expected_journal_samples']==journal_samples
 data=(d/'JOURNAL.f32').read_bytes();assert len(data)==journal_samples*4
 values=[v[0] for v in struct.iter_unpack('<f',data)];error=max((abs(v-reference[i]) for i,v in enumerate(values)),default=0.)
 assert error<=1e-7 and all(math.isfinite(v) for v in values)
 assert bool(row['source_error'])==failed and bool(row['journal_fatal'])==failed and bool(row['controller_error'])==failed
 assert row['integrity']['ok']==(not failed) and row['integrity']['child_closed'] and row['integrity']['source_samples']==source_samples
 assert row['integrity']['journal_samples']==journal_samples and row['integrity']['discarded_after_failure_samples']==(15360 if name=='timing_failure' else 0)
 assert row['controller_engine_released'] and row['negative_calls']==3 and row['controller_metrics']['last_worker_cleanup']['owned_threads_joined']
 assert all(not v for v in [row['controller_metrics']['last_worker_cleanup']['live_after']])
 events=row['events'];assert sum(v['kind']=='source_stopped' for v in events)==1 and sum(v['kind']=='fatal' for v in events)==int(failed)
 if name in ('stop_tail','restart','restore_failure'):
  assert row['held_during_stop']==dict(controller_state='STOPPING',engine_retained=True,journal_samples=480,source_finished=False)
 if name=='start_failure':
  assert row['startup_error'] and len(row['partial_cleanup'])==2 and not (d/'SOURCE_START.json').exists()
  failure=read(d/'SOURCE_START_FAILURE.json');assert failure['status']['finished'] and not failure['errors']
  pending=0
 else:
  m=read(d/'SOURCE_START.json');close=read(d/'BRIDGE_CLOSE.json');s=close['final_status']
  assert m['endpoint']['name']=='XMOS_FAKE_ONLY (hw:7,1)' and m['actual_stream_rate']==48000 and not m['timestamps_calibrated_to_acoustic_arrival']
  assert close['stream_closed'] and close['lease_released'] and not close['errors'] and s['finished'] and s['pending_raw_blocks']==0
  assert s['converted_samples']==source_samples and s['raw_frames']==source_samples*3 and s['priming_frames_discarded_before_route_verified']==480
  assert close['route_restoration']=={'AEC_ASROUTONOFF':'MISMATCH' if name=='restore_failure' else 'RESTORED'}
  pending=close['original_stop_status']['pending_raw_blocks']
  if name in ('stop_tail','restart','restore_failure'):assert pending>0
  if name=='callback_fault':assert s['callback_fault_detail']['raw_status_bits']==2 and s['callback_fault_detail']['upstream_lost_frames'] is None
 if journal_samples:
  t=row['timing'];assert t['model_samples_accepted']==journal_samples and t['native_frames_accepted']==journal_samples*3 and t['blocks']==journal_samples//160
  assert t['max_native_lead_ns']<=0 and len(t['recent_blocks'])<=64 and len(row['recent_ipc'])<=64
 if name=='timing_failure':
  assert row['timing']['blocks']==0 and 'callback/consumer host clock mismatch' in row['source_error']
  assert sum(v['kind']=='source_timing' for v in events)==1 and 'JOURNAL_SOURCE_COVERAGE' in row['integrity']['reasons']
 with (d/'fake-device.lock').open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 metrics.append(dict(case=name,journal_samples=journal_samples,source_samples=source_samples,independent_fir_maxabs=error,pending_raw_at_stop=pending,failed_as_expected=failed,child_exit=row['child_exit'],controller_released_after_close=True))
 child_peaks.append(c['peak_rss_bytes'])
assert (root/'stop_tail/JOURNAL.f32').read_bytes()==(root/'restart/JOURNAL.f32').read_bytes()
owners=list(root.rglob('*OWNER.json'));assert len(owners)==9
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==a['boot_id']
for path in owners:
 o=read(path);assert o['boot_id']==boot and ticks(o['pid'])!=o['start_ticks']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
for path in [root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
files={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in root.rglob('*') if p.is_file()};size=sum(z['bytes'] for z in files.values());assert size<a['target_output_max_bytes']==16*1024**2
review=dict(status='PASS_NATIVE_ISOLATED_PIPELINE_AND_CONTROLLER_STOP_BOUNDARIES_ONLY',cases=metrics,elapsed_seconds=r['elapsed_seconds'],main_peak_rss_bytes=r['peak_rss_bytes'],maximum_child_peak_rss_bytes=max(child_peaks),sampled_aggregate_peak_bytes=max(z.get('aggregate_rss_bytes',0) for z in di['samples']),unready_child_owner_view_checked=True,output_bytes=size,owners_closed=len(owners),capture=False,models_loaded=False,whole_controller_startup_qualified=False,gui_qualified=False,live_B01_qualified=False,baseline_unchanged=True,leases_free=True)
print(json.dumps(dict(review=review,files=files)))
''')
    out=PRIVATE/'source-pipeline-v2-evidence';assert not (out/'target').exists() and not (out/'REVIEW.json').exists()
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    data=subprocess.check_output(SSH+['tar -C '+REMOTE+'/source-pipeline-v2 -cf - .'],timeout=90)
    backup=out/'target';backup.mkdir();seen=set()
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as tar:
        for member in tar:
            if member.isdir():continue
            assert member.isfile() and member.name.startswith('./')
            name=member.name[2:];path=PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts and name in x['files'] and name not in seen
            raw=tar.extractfile(member).read();assert len(raw)==x['files'][name]['bytes'] and hashlib.sha256(raw).hexdigest()==x['files'][name]['sha256']
            dest=backup.joinpath(*path.parts);dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as f:f.write(raw)
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==x['files'][name]['sha256'];seen.add(name)
    assert seen==set(x['files'])
    combined=x['review']['output_bytes']+sum(p.stat().st_size for p in out.rglob('*') if p.is_file());assert combined+128*1024<32*1024**2
    x['review'].update(backup_verified=True,backup_files=len(seen),combined_with_backup_bytes=combined)
    for name,value in [('REVIEW.json',x['review']),('BACKUP.json',x['files'])]:
        with (out/name).open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps(x['review']))


if __name__=='__main__':main()
