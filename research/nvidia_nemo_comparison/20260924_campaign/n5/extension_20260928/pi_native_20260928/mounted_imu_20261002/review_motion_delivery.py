"""Review retained motion/copy evidence without rerunning hardware or models; README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import hashlib,json,math,os
from pathlib import Path
B=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928');I=B/'imu-integration-20261002'
out=I/'delivery-review-v1';out.mkdir();me=psutil.Process()
def save(n,v):
 raw=json.dumps(v,sort_keys=True,indent=2,allow_nan=False).encode()
 with (out/n).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 assert (out/n).read_bytes()==raw
save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
read=lambda p:json.loads(Path(p).read_bytes())
copies=[read(I/('offload-v27-'+kind)/'BACKUP.json') for kind in ('original','local')]
for copy in copies:assert copy['status']=='COMPLETE_SINGLE_RUNTIME_TREE_PC_OFFLOAD'
rows=[next(iter(c['copies'].values())) for c in copies];assert rows[0]==rows[1]
root=I/'offload-v27-original/tree/field-operator-sessions-v10108';child=root/'recordings/slot-01'
gate=read(root/'broker/GATE_RESULT.json');app=read(child/'receipts/APPLICATION_CLOSURE.json');model=read(child/'receipts/MODEL_CLOSURE.json');result=read(child/'receipts/RESULT.json')
assert gate['logical_success'] and gate['capture_closed'] and gate['worker_exact_dead'] and gate['pipe_closed']
assert app['controller_closed'] and app['worker_joined'] and app['capture_closed'] and app['pending_commands']==0 and app['physical']['open_writable_descriptors']==0
assert result['source_samples']==84000 and not result['cleanup_errors'] and model['closed']
trace_raw=(child/'trace/TRACE.jsonl').read_bytes();trace=[json.loads(r) for r in trace_raw.splitlines()]
assert len(trace)==525 and sum(r['samples'] for r in trace)==84000
poses=[];beam_samples=[];ages=[];lastseq=0
for index,row in enumerate(trace):
 assert row['metadata']['model_start_sample']==160*index and row['samples']==160
 t=row['metadata']['callback_perf_counter_ns']/1e9
 packet=row['ipc']['spatial_telemetry'];assert packet['generation']==packet['dropped']==0
 for sample in packet['samples']:
  sequence,name,values,start,end=sample
  assert sequence==lastseq+1 and start<=end<=t and all(v is None or math.isfinite(v) for v in values)
  lastseq=sequence;beam_samples.append(sample)
 pose=row['ipc'].get('orientation')
 if pose:
  assert 0<=t-pose['at']<=.15 and pose['absolute_position_available'] is False
  poses.append(pose);ages.append(t-pose['at'])
assert len(beam_samples)==79 and len(poses)==44 and sum(p['valid'] for p in poses)==36
assert poses[-1]['valid'] and poses[-1]['state']=='STATIONARY'
duration=poses[-1]['imu_elapsed_sec']-poses[0]['imu_elapsed_sec'];cpu=poses[-1]['imu_cpu_seconds']-poses[0]['imu_cpu_seconds']
rate=(poses[-1]['imu_samples']-poses[0]['imu_samples'])/duration
assert 45<=rate<=55 and 0<=cpu<duration*.05
install=B/'field-runtime-v27-install';common=(install/'stage-backup/field-runtime-v27-profiles/COMMON_BUNDLE.json').read_bytes();ch=hashlib.sha256(common).hexdigest()
assert ch=='3383fa869e7357cfa7f9ef410be6dcb40972feb40cea7aebee9d71dd526e4d80'
assert common==(I/'runtime-capsule-v3/COMMON_BUNDLE.restore.json').read_bytes()
profiles={}
for p in (install/'stage-backup/field-runtime-v27-profiles').glob('*.json'):
 if p.name=='COMMON_BUNDLE.json':continue
 d=read(p);assert d['template_sha256']==ch
 profiles[p.stem]=d['runtime_profile']['definition']['selection']
assert len(profiles)==10
shortcut=read(I/'shortcuts-v27-v2/RESULT.json');inspection=read(I/'shortcuts-v27-v2/INSPECTION.json')
assert shortcut['retained_count']==11 and shortcut['retired_count']==33
assert inspection['active_recorded_owners']==[] and all(v=='closed' for v in inspection['capture'].values())
workflow=read(I/'integrated-v27-v1/RESULT.json');geometry=workflow['array_geometry_readback']
assert geometry['AEC_MIC_ARRAY_TYPE']['stdout'].split()==['AEC_MIC_ARRAY_TYPE','1']
actual=list(map(float,geometry['AEC_MIC_ARRAY_GEO']['stdout'].split()[1:]));assert actual==[-.04995,0,0,-.01665,0,0,.01665,0,0,.04995,0,0]
report=dict(status='PASS_MOUNTED_MOTION_SHARED_RUNTIME_RECORDING_AND_PRIVATE_COPIES',release='field-runtime-v27',common_sha256=ch,
 profiles=profiles,samples=84000,audio_seconds=5.25,blocks=525,beam_samples=len(beam_samples),beam_drops=0,pose_records=len(poses),valid_pose_records=36,
 initial_sensor_gap_invalidated=True,automatic_stationary_recovery_observed=True,maximum_causal_pose_age_sec=max(ages),
 imu_thread_measurement=dict(elapsed_seconds=duration,cpu_seconds=cpu,one_core_percent=100*cpu/duration,samples_per_second=rate,includes_GUI_or_models=False,battery_energy_measured=False,external_beam_getter_CPU_measured=False),
 whole_frontend_idle=read(I/'integrated-v26-v1/RESULT.json')['idle_frontend_cpu'],debug_graphic=read(I/'integrated-v26-v1/RESULT.json')['debug_graphic'],
 copy=rows[0],independent_pc_copies=2,physical_array_geometry_m=actual,array_center_m=[0,0,0],mounted_sensor_from_center_m=[-.045,-.16,-.015],
 current_manager=shortcut['manager'],capture_off=True,remaining_recording_slots=3,retained_shortcuts=11,
 model_accuracy_tested=False,all_model_profiles_rerun=False,physical_rotation_evidence='physical-v1; approximate 90-degree clockwise and return, not accuracy calibration',
 limitations=['Relative yaw may drift; no magnetometer/absolute heading','Linear array retains front/back ambiguity','No reliable inertial room-position/range estimate; acceleration invalidates location priors','Initial model loading caused one sensor gap; affected spatial trust was withheld until automatic stationary recovery','No new noisy-human recognition or battery-endurance result'])
save('RESULT.json',report)
save('INPUT_PINS.json',{str(p.relative_to(B)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [child/'trace/TRACE.jsonl',child/'receipts/RESULT.json',I/'offload-v27-original/BACKUP.json',I/'offload-v27-local/BACKUP.json',I/'shortcuts-v27-v2/RESULT.json']})
print(json.dumps({k:report[k] for k in ('status','audio_seconds','beam_samples','imu_thread_measurement','remaining_recording_slots')}))
