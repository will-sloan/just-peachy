"""Reconcile current guides after the approved source push; README_FINALIZE_DOCS.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast,hashlib,io,json,os,shutil,time,zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path

H=Path(__file__).parent
W=Path('G:/Just_Peachy_N1/20260924_campaign/worktree')
P=W/'research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
C=P.parents[1]/'completion_20261001'
I=W.parent/'local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002'
O=I/'approved-final-docs-v1';O.mkdir()
now=datetime.now(timezone.utc);end=time.monotonic()+600;used=0;maximum=16*1024**2
sha=lambda r:hashlib.sha256(r).hexdigest()
enc=lambda d:(json.dumps(d,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def put(p,r,replace=False):
    global used
    if time.monotonic()>end or used+len(r)>maximum or len(r)>2*1024**2:raise RuntimeError('Publication bound')
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('wb' if replace else 'xb') as f:
        if f.write(r)!=len(r):raise OSError('Short write')
        f.flush();os.fsync(f.fileno())
    if p.read_bytes()!=r:raise IOError('Readback')
    used+=len(r)
def save(n,d):put(O/n,enc(d))
me=psutil.Process();save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
save('SCOPE.json',dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),maximum_bytes=maximum,purpose='USER_APPROVED_FINAL_DOCUMENTATION_AND_HANDOFF'))
for drive,floor in [('C:/',50),('G:/',75)]:
    assert shutil.disk_usage(drive).free>=floor*1024**3+maximum
remote=dict(source_commit='ed27d04b6131106c400bda828a64d00274095c56',
    repository='https://github.com/will-sloan/just-peachy',branch='codex/n1-foundation-20260924',
    source_push_verified=True,verification='git push succeeded; git ls-remote matched exact source commit in this turn',
    user_authority='You can push it and I approve everything. Please update all of the documentation and the hand off.',
    recorded_utc=now.isoformat(),previous_rejection_preserved='publication-v2/COMPLETION_AND_REMOTE_HOLD.json',
    private_media_or_model_payload_uploaded=False,documentation_followup_commit='Recorded separately after this immutable handoff to avoid a self-referential hash')
save('APPROVED_SOURCE_REMOTE.json',remote)
names=['START_HERE.md','MODE_GUIDE.md','MOTION_GUIDE.md','CHATGPT_HANDOFF.md','CURRENT_RUNTIME_PROGRESS.md',
       'FINAL_OPERATOR_GUIDE.md','PATHS_AND_BACKUPS.md','INSTALL_HEALTH_AND_RECOVERY.md','BACKEND_COMBINATIONS.md',
       'ACCEPTANCE.json','FINISH_CHECKLIST.json','FINISH_CHECKLIST.md','HARDWARE_CAPABILITIES.json',
       'FIELD_RUN_TEMPLATE.json','FIELD_VALIDATION.md','OFFLINE_ACCEPTANCE.md','COMPLETION_PLAN.md',
       'MOTION_RELEASE_INDEX.json','MOTION_CHECKLIST.json','MOTION_HANDOFF_RECEIPT.json']
targets=[C/n for n in names]+[W/'DELIVERY_START_HERE.md',P/'MASTER_BACKEND_MODE_GUIDE.md',P/'STATUS.md',P.parent/'STATUS.md',P.parent/'NEXT.md']
before={}
for p in targets:
    r=p.read_bytes();n=p.relative_to(W).as_posix();before[n]=r
    put(O/'before-backup'/n,r);put(O/'before-restore'/n,r)
save('BEFORE_CLOSED.json',{n:dict(bytes=len(r),sha256=sha(r)) for n,r in before.items()})
changes={}
def text(n):return (C/n).read_text(encoding='utf-8')
def change(n,t):changes[C/n]=t.encode() if isinstance(t,str) else enc(t)

change('MOTION_REMOTE.json',remote)
change('START_HERE.md',text('START_HERE.md')+'''
The approved motion source is remotely backed up at commit
`ed27d04b6131106c400bda828a64d00274095c56`; see MOTION_REMOTE.json.
Use the current MOTION_HANDOFF_RECEIPT.json for the latest verified archive.
The previous upload approval hold is resolved. No new native test was needed
for this documentation refresh; hardware observations remain the recorded v27 check.
''')
change('CURRENT_RUNTIME_PROGRESS.md',text('CURRENT_RUNTIME_PROGRESS.md')+'''
Source publication ed27d04b6131106c400bda828a64d00274095c56 is verified on the
existing GitHub delivery branch after explicit user approval. Current acceptance,
hardware/checklist declarations and the field-run template now include motion.
MOTION_HANDOFF_RECEIPT points to the refreshed immutable handoff. No native action
or quality/battery test occurred during this documentation update.
''')
change('CHATGPT_HANDOFF.md',text('CHATGPT_HANDOFF.md').replace('## Earlier runtime/model completion (v23 history)',
    'The mounted-motion source commit ed27d04b6131106c400bda828a64d00274095c56 is now verified on the existing GitHub branch. MOTION_REMOTE.json supersedes the earlier approval hold. Current acceptance, hardware capability and checklist files incorporate this addition; historical deadline and FINAL_* receipts remain history.\n\n## Earlier runtime/model completion (v23 history)'))
change('PATHS_AND_BACKUPS.md',text('PATHS_AND_BACKUPS.md')+'''
Latest approved documentation/handoff: `I/approved-final-docs-v1`, with original
and independent ZIP/expanded readback. MOTION_HANDOFF_RECEIPT.json is the current
archive pointer; publication-v2's earlier ZIP stays immutable. MOTION_REMOTE.json
records the approved, verified source push; final documentation commit verification
is retained privately in approved-final-docs-v1/REMOTE.json.
''')
changes[W/'DELIVERY_START_HERE.md']=(W/'DELIVERY_START_HERE.md').read_bytes()+b'\nThe source push is approved and remotely verified; the current motion handoff receipt links the final refreshed archive.\n'
offline=text('OFFLINE_ACCEPTANCE.md').replace('Current candidate23 reuses the same reviewed runtime/model bytes.',
    'Current candidate27 retains the reviewed network restrictions and model assets, with new mounted-motion source integration. Its separate5.25s processed recording and full closure/copies passed; unchanged model combinations/raw paths were not all rerun.')
change('OFFLINE_ACCEPTANCE.md',offline+'''
Mounted BMI270 orientation, gravity/gyro fusion and array-centered correction are
local and require no network. Relative yaw can drift and reliable room translation
is unavailable. Confirm movement/rotation behavior during operator validation;
the live sensor never supplies retrospective pose to a plain saved WAV.
Three recording slots remained at the last v27 observation. See MOTION_GUIDE
and MOTION_RELEASE_INDEX for the exact functional/resource scope.
''')
plan=text('COMPLETION_PLAN.md');cut=plan.index('## Historical plan and milestones')
change('COMPLETION_PLAN.md','''# Current completion outcome

The prepared-CM5 runtime is deployed for bounded real-world validation as v27,
with ten profiles, TitaNet/ReDimNet, optional raw/processed recording and shared
mounted BMI270 integration. The changed recording, closure, independent backups,
efficient-worker measurement and source push are complete. Three recording slots
remained at the last observation; capture was off. Guides and handoff are refreshed.

Physical/noisy-world recognition, longer yaw drift, touch, coldboot and battery
validation remain user measurements. Reliable absolute room translation cannot be
inferred from this six-axis IMU. The new renewal wrapper is prepared/compiled/planned;
its component paths have execution evidence. Do not treat it as an additional native pass.

The deadlines below governed the historical delivery. The later mounted-motion
task and this final documentation/push were separately requested by the user;
none of the old admissions or deadline receipts was extended or rewritten.

'''+plan[cut:])
field=text('FIELD_VALIDATION.md').replace('the current four-slot allocation','the finite four-slot allocation (three slots remain in v27)')
change('FIELD_VALIDATION.md',field+'''
## Mounted-motion validation addition

Use MOTION_GUIDE and record results in the template's `motion` fields. These are
future physical observations, not extra checks already performed or automatic jobs.

1. Leave the device quiet briefly and observe automatic reference acquisition.
2. With a stationary consented speaker, rotate and tilt the tablet. Raw beam arrows
   must follow microphone-relative direction; trusted location association should
   use the relative reference without changing the voice embedding itself.
3. Move the tablet sideways. Observe motion/trust invalidation; do not expect a
   reliable room trajectory or speaker range from accelerometer integration.
4. Toggle the optional orientation graphic and tap it. Only the graphic zero should
   change. After gaps/movement, observe reacquisition rather than guessed angles.
5. Compare ReDimNet/TitaNet with separately compatible galleries and matched input.
   A plain saved WAV must not react to present-day tablet rotation. Record drift,
   false movement indications and battery/temperature over separately admitted runs.

Keep normal duration/slot/storage limits. Long-term drift/endurance needs its own
bounded plan; this protocol does not enlarge the current runtime allowance.
''')
template=json.loads(text('FIELD_RUN_TEMPLATE.json'))
template['motion']=dict(sensor_model=None,mount_config_sha256=None,automatic_reference_acquired=None,
    reference_epoch=None,rotation_direction_and_degrees=None,tilt_observation=None,translation_observation=None,
    sensor_gap_or_stale_pose=None,location_trust_invalidation=None,reference_reacquisition=None,
    raw_beam_device_relative=None,identity_continuity=None,visual_zero_only=None,saved_wav_excludes_live_pose=None,
    imu_thread_cpu_seconds=None,imu_elapsed_seconds=None,sample_rate_hz=None,heading_drift_observation=None,
    battery_energy_measured=False,battery_measurement=None,absolute_room_position_claimed=False)
change('FIELD_RUN_TEMPLATE.json',template)
hardware=json.loads(text('HARDWARE_CAPABILITIES.json'));hardware['as_of_utc']=now.isoformat()
hardware['status']='ACTUAL_AUDIO_DISPLAY_MOUNTED_IMU_FUNCTIONAL_OTHER_CAPABILITIES_DECLARED'
hardware['imu']=dict(status='MOUNTED_SHARED_RUNTIME_FUNCTIONAL_PASS_REAL_WORLD_VALIDATION_OPEN',
    model='SparkFun Bosch BMI270 6DoF',accelerometer_axes=3,gyroscope_axes=3,magnetometer=False,
    mount_axes_confirmed=True,sensor_to_device=[[0,1,0],[-1,0,0],[0,0,1]],
    sensor_from_array_center_m=[-.045,-.160,-.015],mount_position_is_approximate=True,
    array_geometry_m=[[-.04995,0,0],[-.01665,0,0],[.01665,0,0],[.04995,0,0]],
    array_geometry_basis='actual AEC_MIC_ARRAY_TYPE1 and AEC_MIC_ARRAY_GEO readback',
    configured_rate_hz=50,measured_rate_hz=50.28760165745563,measured_thread_one_core_percent=1.2097841523466566,
    measurement_scope='5.150374873s thread observation; excludes external beam-getter CPU, GUI/models and battery energy',
    drift_free_position_or_absolute_yaw=False,plain_wav_live_pose_excluded=True,
    evidence=['imu-integration-20261002/physical-v1','imu-integration-20261002/mount-save-v1',
              'imu-integration-20261002/delivery-review-v1/RESULT.json'])
change('HARDWARE_CAPABILITIES.json',hardware)

check=json.loads(text('FINISH_CHECKLIST.json'));check['as_of_utc']=now.isoformat()
check['current_release']='field-runtime-v27';check['current_item']='IMPLEMENTATION_COMPLETE_BOUNDED_REAL_WORLD_VALIDATION_NEXT'
check['motion_addendum']='MOTION_CHECKLIST.json; separately user-requested mounted-motion task, not a historical deadline extension'
specific={
 'F04':'Current v27 manager2626/start362288 was left idle, captureoff, three slots remaining. Actual v27 install/one changed recording/localbackup/full PCcopies passed. Motion renewal wrapper is prepared/compiled/planned only; component preserve/inspect/provision evidence is retained separately.',
 'F05':'Same finite4recordings/16launchslots/24h idlelaunch;120s microphone/Chunk52 and30s savedStreaming. Three slots remain. Full3307886087B installation reservation retained. Metadata-only continuation1088owners within original256KiB request, no removed bounds.',
 'F07':'shortcuts-v27-v2 retained ten exact current profile shortcuts plusrollback;33obsoletegeneratedicons independently backed up and retired. All10profiles pin motion commonSHA3383fa869e7357cfa7f9ef410be6dcb40972feb40cea7aebee9d71dd526e4d80.',
 'F17':'field-runtime-v27-install stage-backup/stage-restore and active backups retain actualinstalled motionrelease. Prior91554957B v23prepared-devicekit remains intact but omits motion; not a current-v27 OS image.',
 'F19':'Historical actualbroker/childInternet socketdenial andstartup-commandrestart retained. Newv27 processedrecording/closure passed with retainedofflineguards, display270/captureoff. Physical cable-disconnectedcoldboot/touch remain validation; not rerun.',
 'F21':'HARDWARE_CAPABILITIES now records actualBMI270 axes/mount/arraygeometry/physicalturn and50Hz sharedruntime. No absoluteheading/reliableroomtranslation. Camera and unknownGPIO remain unqualified/disabled.',
 'F23':'Current MODE_GUIDE/MOTION_GUIDE/START_HERE, renewal/offload, hardware/acceptance and fieldtemplate updated; legacy v23kit/commands explicitly historical.',
 'F24':'FIELD_VALIDATION and FIELD_RUN_TEMPLATE include rotation/tilt/translation-trust/visualzero/drift/battery observations; protocolonly, no invented noisyhuman results.',
 'F25':'Motion source commit ed27d04b6131106c400bda828a64d00274095c56 remotelyverified afterexplicituserapproval. Currentinstall/source and two independentcompletePCrecordingcopies are retained. Updateddoc/handoff backups in approved-final-docs-v1; oldkit/packsimmutable.',
 'F26':'MOTION_HANDOFF_RECEIPT identifies refreshedverifiedZIP with guides/readablemotioncode, no privateaudio/models. Lastv27observation idle/captureoff/three slots. No newnativeaction for this finaldocumentation.'}
for item in check['items']:
    if item['id'] in specific:
        item['historical_evidence_before_motion']=item['evidence'];item['evidence']=specific[item['id']]
    if item['id']=='F21':item['status']='DONE_ACTUAL_MOUNTED_IMU_AND_CAPABILITY_DECLARATIONS'
change('FINISH_CHECKLIST.json',check)
lines=['# Concrete finish checklist — current v27 status','',
 'Implementation is complete for bounded real-world validation. Three recording slots remained at the last observation; physical/noisy-world tests remain open. The 26 original requirements and their exit criteria stay below. The separately requested mounted-motion work is recorded in MOTION_CHECKLIST.json. Old deadlines/admissions are historical and unchanged.','']
for item in check['items']:
    lines+=['## '+item['id']+' — '+item['title'],'','Status: **'+item['status']+'**','',
       'Exit criterion: '+item['done_means'],'','Evidence: '+item.get('evidence',''),'']
    if item.get('historical_evidence_before_motion'):lines+=['Earlier evidence (historical): '+item['historical_evidence_before_motion'],'']
change('FINISH_CHECKLIST.md','\n'.join(lines))
accept=json.loads(text('ACCEPTANCE.json'));accept['as_of_utc']=now.isoformat();accept['current_release']='field-runtime-v27'
accept['latest_motion_review']='MOTION_RELEASE_INDEX.json';accept['source_backup']='MOTION_REMOTE.json'
for gate in accept['gates']:
    if 'remaining' in gate:gate['remaining']=gate['remaining'].replace('finalartifactreceipts pending.','current receipts are MOTION_RELEASE_INDEX/MOTION_HANDOFF_RECEIPT; physical/noisy-world validation remains open.')
    for key in ('entry_preparation','milestone'):
        if key in gate:gate['historical_'+key]=gate.pop(key)
    if gate['id']=='MODE_LAUNCHER_AND_ERROR_RECOVERY':gate['evidence']=specific['F04']
    if gate['id']=='OFFLINE_STARTUP_AND_OPERATION':gate['evidence']=specific['F19']
    for key,value in list(gate.items()):
        if isinstance(value,str) and 'Current23' in value:gate[key]=value.replace('Current23','Historical candidate23')
accept['gates'].append(dict(id='MOUNTED_IMU_ALL_SUPPORTED_PROFILES',required=True,
    status='SHARED_CODE_DEPLOYED_SCOPED_LIVE_FUNCTIONAL_PASS',
    evidence='MOTION_RELEASE_INDEX; actual5.25s processedrecording, source/model/Stop/Saveclosure and2independentcompletePCcopies; all10commonprofilepins; physicalturn; graphicshow/tap/hide;1.21%onecore50.29Hz',
    remaining='No all-profile rerun, noisyhumanaccuracy, longdrift/battery/physicaltouch or reliable absolute roomtranslation claim. PlainWAVliveposeexcluded; pose-sidecar replay unimplemented.'))
change('ACCEPTANCE.json',accept)
release=json.loads(text('MOTION_RELEASE_INDEX.json'));release['source_backup']=remote;release['documentation_updated_utc']=now.isoformat()
change('MOTION_RELEASE_INDEX.json',release)
motioncheck=json.loads(text('MOTION_CHECKLIST.json'))
for item in motioncheck['items']:
    if item['id']=='M08':item['evidence']='shortcuts-v27-v2; publication-v2; approved-final-docs-v1; sourcepush ed27d04b remotelyverified'
change('MOTION_CHECKLIST.json',motioncheck)

master=(P/'MASTER_BACKEND_MODE_GUIDE.md').read_text(encoding='utf-8').replace('Currentreleasefield-runtime-v23','Currentreleasefield-runtime-v27')
master+='\nThe shared mounted BMI270 integration is deployed across all ten profile pins. Read [MOTION_GUIDE](../../completion_20261001/MOTION_GUIDE.md) for automatic reference, array-centered geometry,50Hz/1.21%one-core observation and limits. Three recording slots remained at last observation. The approved source push is recorded in MOTION_REMOTE.json. Current handoff/source history is distinct from immutable v23 FINAL_* receipts.\n'
changes[P/'MASTER_BACKEND_MODE_GUIDE.md']=master.encode()
for p in (P/'STATUS.md',P.parent/'STATUS.md',P.parent/'NEXT.md'):
    prefix='''# Current mounted-motion delivery — October 2

field-runtime-v27 is deployed for bounded real-world validation across all ten
profile pins, with BMI270 motion integration,3recording slots remaining and the
last manager observation idle/captureoff/display270. Source commit
ed27d04b6131106c400bda828a64d00274095c56 is remotely verified after user approval.
Current operator instructions and refreshed handoff are in completion_20261001:
START_HERE, MODE_GUIDE, MOTION_GUIDE, MOTION_RELEASE_INDEX, MOTION_REMOTE and
MOTION_HANDOFF_RECEIPT. No additional native/model campaign is pending.

Changed functional evidence:5.25s/84000samples, full Stop/Save/closure and two
independentPCcopies; IMU thread1.21%ofonecore at50.29Hz. Translation invalidates
location assumptions; no reliable absoluteposition/heading or noisyworld/battery
claim. Future physicalvalidation follows FIELD_VALIDATION within actual limits.

## Retained previous status and research history

'''
    changes[p]=(prefix+p.read_text(encoding='utf-8')).encode()
for n in ('finalize_motion_docs.py','README_FINALIZE_DOCS.md'):
    changes[P/'mounted_imu_20261002'/n]=(H/n).read_bytes()
manifest={}
for p,r in changes.items():
    if p.suffix=='.py':ast.parse(r);compile(r,p.name,'exec')
    put(p,r,replace=p.exists());n=p.relative_to(W).as_posix()
    put(O/'published-backup'/n,r);put(O/'published-restore'/n,r)
    manifest[n]=dict(bytes=len(r),sha256=sha(r))

# Read the verified prior handoff and refresh only the current documents.
prior=json.loads((C/'MOTION_HANDOFF_RECEIPT.json').read_bytes());oldzip=Path(prior['path']).read_bytes()
assert sha(oldzip)==prior['sha256'] and len(oldzip)==prior['bytes']
with zipfile.ZipFile(io.BytesIO(oldzip)) as z:payload={n:z.read(n) for n in z.namelist() if n!='BUNDLE_MANIFEST.json'}
for n in list(payload):
    if '/' not in n and (C/n).is_file():payload[n]=(C/n).read_bytes()
payload['MOTION_REMOTE.json']=(C/'MOTION_REMOTE.json').read_bytes()
assert sum(map(len,payload.values()))<2*1024**2
payload['BUNDLE_MANIFEST.json']=enc(dict(schema='just-peachy.motion-handoff.v2',release='field-runtime-v27',
    source_commit=remote['source_commit'],source_remote_verified=True,created_utc=now.isoformat(),
    private_payloads_included=False,models_included=False,standalone_deployment=False,
    files={n:dict(bytes=len(r),sha256=sha(r)) for n,r in payload.items()}))
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
    for n,r in sorted(payload.items()):z.writestr(n,r)
zr=buf.getvalue();assert len(zr)<2*1024**2
zipname='JustPeachy-motion-v27-final-ChatGPT-handoff.zip'
put(O/zipname,zr);put(O/'independent-zip-backup'/zipname,zr)
with zipfile.ZipFile(O/'independent-zip-backup'/zipname) as z:
    assert set(z.namelist())==set(payload)
    for n,r in payload.items():
        assert z.read(n)==r;put(O/'independent-expanded-restore'/n,r)
receipt=dict(schema='just-peachy.motion-handoff-receipt.v2',path=str(O/zipname),bytes=len(zr),sha256=sha(zr),
    members=len(payload),complete_member_readback=True,independent_zip_and_expanded_restore=True,
    private_audio_or_models=False,old_packs_unchanged=True,source_commit=remote['source_commit'],source_remote_verified=True,
    earlier_receipt=prior)
r=enc(receipt);p=C/'MOTION_HANDOFF_RECEIPT.json';put(p,r,replace=True);n=p.relative_to(W).as_posix()
put(O/'published-backup'/n,r);put(O/'published-restore'/n,r);manifest[n]=dict(bytes=len(r),sha256=sha(r))
save('FINAL_WHITELIST.json',manifest)
save('CLOSED.json',dict(files=len(manifest),charged_before_receipt=used,maximum_bytes=maximum,
    closed_utc=datetime.now(timezone.utc).isoformat(),within_scope=time.monotonic()<end,
    handoff=receipt,source_remote_verified=True,no_native_action=True))
print(json.dumps(dict(files=len(manifest),charged_bytes=used,handoff_bytes=len(zr),handoff_sha256=sha(zr),handoff=str(O/zipname))))
