"""Publish existing motion evidence, source and handoff; see README_PUBLICATION.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast,base64,hashlib,io,json,os,shutil,time,zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path

H=Path(__file__).parent
W=Path('G:/Just_Peachy_N1/20260924_campaign/worktree')
P=W/'research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
C=P.parents[1]/'completion_20261001'
B=W.parent/'local/n5/research-extension-20260928/pi-native-20260928'
I=B/'imu-integration-20261002'
O=I/'publication-v1'
O.mkdir()
now=datetime.now(timezone.utc);deadline=time.monotonic()+600;budget=16*1024**2;charged=0
sha=lambda r:hashlib.sha256(r).hexdigest()
enc=lambda v:(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def put(p,r,existing=False):
    global charged
    if time.monotonic()>deadline or charged+len(r)>budget:raise RuntimeError('Publication time/aggregate budget')
    if len(r)>2*1024**2:raise ValueError('Publication member ceiling')
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('wb' if existing else 'xb') as f:
        if f.write(r)!=len(r):raise OSError('Short publication write')
        f.flush();os.fsync(f.fileno())
    if p.read_bytes()!=r:raise IOError('Publication readback')
    charged+=len(r)
def save(n,v):put(O/n,enc(v))
me=psutil.Process()
save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
save('SCOPE.json',dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),maximum_bytes=budget,purpose='CURRENT_MOTION_SOURCE_GUIDES_AND_HANDOFF_ONLY'))
for drive,floor in [('C:/',50),('G:/',75)]:
    if shutil.disk_usage(drive).free<floor*1024**3+budget:raise RuntimeError('Host floor')
report=json.loads((I/'delivery-review-v1/RESULT.json').read_bytes())
assert report['status']=='PASS_MOUNTED_MOTION_SHARED_RUNTIME_RECORDING_AND_PRIVATE_COPIES'
assert report['remaining_recording_slots']==3 and len(report['profiles'])==10
dest=P/'mounted_imu_20261002'
if dest.exists():raise ValueError('Source publication directory already exists')

# Independently preserve old editable guides before changing any of them.
names=('START_HERE.md','MODE_GUIDE.md','INSTALL_HEALTH_AND_RECOVERY.md','PATHS_AND_BACKUPS.md',
       'CHATGPT_HANDOFF.md','CURRENT_RUNTIME_PROGRESS.md','FINAL_OPERATOR_GUIDE.md','BACKEND_COMBINATIONS.md')
old={n:(C/n).read_bytes() for n in names}
old['DELIVERY_START_HERE.md']=(W/'DELIVERY_START_HERE.md').read_bytes()
old['source-README.md']=(H/'README.md').read_bytes()
for n,r in old.items():
    put(O/'before-backup'/n,r);put(O/'before-restore'/n,r)
save('BEFORE_CLOSED.json',{n:dict(bytes=len(r),sha256=sha(r)) for n,r in old.items()})

header='''# Mounted BMI270: current code and commands

Current deployed release is **field-runtime-v27**, using `bind_runtime_motion_v3.py`
and `prepare_runtime_motion_v3.py`. Three recording slots remain. Read
[MOTION_GUIDE.md](MOTION_GUIDE.md) first for operation, geometry, measured CPU cost
and limits. Ten profiles share one sensor worker; plain saved WAVs never borrow
the current live pose.

For future completed-batch renewal, use `renew_motion_runtime.py` and the
"Renew batches without losing motion integration" section below. Operator helper
sources are already prepared in `operator-tools-v1`; do not rerun their generators.
The combined renewal wrapper is prepared/compiled/planned, not itself executed.
Its preservation/inspection/provision components retain their actual scoped evidence.

PowerShell, from this directory:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./renew_motion_runtime.py --previous-version 27 --version 28 --last-receipt 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/shortcuts-v27-v2' --plan
```
CMD or Anaconda Prompt uses the same arguments after `python -B renew_motion_runtime.py`
in the existing project environment. `--plan` makes no Pi contact. Use the actual
latest native receipt and fresh version/output paths for a later renewal. Remove
`--plan` only when intentionally renewing a completed batch. For recording offload,
use `operator-tools-v1/export_runtime_recording_v4.py` with the current installation
and a new private destination; see the completion MODE_GUIDE and the existing
README_RUNTIME_RECORDING_OFFLOAD_V4.md. Copies retain every original.

Purpose: share one mounted motion stream across existing live source/display and
position consumers. Inputs: pinned installed application, fixed mount config,
BMI270 library and original runtime/model manifests. Outputs: bounded causal
beam/pose metadata, relative rotation correction, explicit invalidation during
motion/gaps, optional diagnostic graphic, and private recording/closure receipts.
These are prepared-workstation tools, not a generic fresh-device installer.

The following preparation/execution history is retained for reproducibility.
Old version-bound checks, recovery, recording and copy commands are **consumed**;
they are not instructions to rerun them. Earlier "current" statements below apply
only to their historical stage. Saved-WAV pose-sidecar replay is not implemented.

'''
put(H/'README.md',(header+old['source-README.md'].decode()).encode(),existing=True)

docs={}
docs['START_HERE.md']='''# Just Peachy: start here

**The prepared CM5 now runs field-runtime-v27 with mounted BMI270 integration.**
It was left idle, capture off, display 270, with **three recording slots remaining**
and ten backend shortcuts plus rollback. No recording starts by opening a profile.

Read [MODE_GUIDE.md](MODE_GUIDE.md) for the ten diarizer/embedding combinations,
recording controls and PC commands. Read [MOTION_GUIDE.md](MOTION_GUIDE.md) for
automatic calibration, array-centered geometry, the optional orientation graphic,
and what the six-axis sensor can and cannot infer. Sherpa ASR, ReDimNet/TitaNet
and the existing Pyannote/Nemotron choices are retained.

The changed shared integration passed one native 5.25-second processed recording,
normal Stop/Save/Return/closure, local backup and two complete independent PC
copies. It measured about 1.21% of one core for the IMU thread at 50.29 samples/s.
All ten profiles bind the same code; the unchanged model combinations were not
all rerun. Earlier all-profile and raw-recording evidence remains separately scoped.

The sensor handles relative rotation and tilt, with the microphone-array center
as origin. Detected translation suspends location assumptions; reliable absolute
room position is unavailable. Relative yaw can drift. Live beam arrows stay
device-relative, and plain saved WAVs never borrow current tablet motion.

[INSTALL_HEALTH_AND_RECOVERY.md](INSTALL_HEALTH_AND_RECOVERY.md) and
[PATHS_AND_BACKUPS.md](PATHS_AND_BACKUPS.md) cover renewal, rollback and storage.
Use the new motion renewal command; the historical Refresh-JustPeachy wrapper
and 91,554,957-byte v23 kit omit the new integration. The current code is installed
and independently backed up. The new small handoff includes guides and readable
motion source, not models, recordings or a standalone OS image.

Current receipts: MOTION_RELEASE_INDEX.json, MOTION_CHECKLIST.json and
MOTION_HANDOFF_RECEIPT.json. Older FINAL_* receipts remain immutable v23 history.
Physical touch, cable-disconnected coldboot, battery endurance, long-term drift
and noisy-world recognition remain real-world validation, not completed claims.
Use FIELD_VALIDATION.md/FIELD_RUN_TEMPLATE.json. FINAL_COVERAGE retains the
N1-N5/34-method denominator and incomplete full 240-cell N4 comparison.
'''
mode=old['MODE_GUIDE.md'].decode().replace('field-runtime-v23','field-runtime-v27')
mode=mode.replace('The fresh release has four recording slots.','The release reserves four recording slots; three remain after the motion integration recording.')
mode=mode.replace('Use `export_runtime_recording_v4.py` in the native source directory;',
    'Use `operator-tools-v1/export_runtime_recording_v4.py` under `C:/Users/amiri/Documents/GitHub/just-peachy/Resumes/imu_integration_20261002`;')
mode=mode.replace('-B export_runtime_recording_v4.py','-B "C:/Users/amiri/Documents/GitHub/just-peachy/Resumes/imu_integration_20261002/operator-tools-v1/export_runtime_recording_v4.py"')
mode=mode.replace('deployable-runtime-resume-v1/PREINSTALL_PRIOR_BINDING_V6.json','NATIVE_CLOSURE_V315.json')
left=mode.index('For a fresh batch, after Stop/Save/Return/broker Close and local backup:')
right=mode.index('## Validation scope',left)
mode=mode[:left]+'''For a fresh batch, after Stop/Save/Return/broker Close and local backup, use
the new motion-preserving wrapper. The old Refresh-JustPeachy reconstructs v23
and omits this integration. From the host motion directory:

~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./renew_motion_runtime.py --previous-version 27 --version 28 --last-receipt 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/shortcuts-v27-v2' --plan
~~~

CMD/Anaconda uses the same arguments after `python -B renew_motion_runtime.py`.
Replace the receipt with the latest actual utility receipt after any later native
operation. Remove `--plan` to perform intentional renewal; use higher unused
versions thereafter. This wrapper is prepared/compiled/planned only. Its component
preservation, inspection and provision paths have actual execution evidence.
Every phase retains full independent storage reservations and a 600-second limit;
failed sources require their specific recovery, never counter or pending-file deletion.

## Mounted motion

All profiles share the integration described in [MOTION_GUIDE.md](MOTION_GUIDE.md).
Live beams stay microphone-relative; existing location logic uses trusted relative
rotation correction. Acceleration/gaps invalidate spatial trust. Voice-only rules
and plain saved WAVs do not gain invented location evidence. Settings -> Orientation
graphic toggles an upper-right diagnostic; tap it to zero the visual only.
It is hidden by default. Automatic quiet reference acquisition needs no manual zero.

'''+mode[right:]
mode=mode.replace('All ten routes have scoped native functional evidence,','Before the motion change, all ten routes had scoped native functional evidence,')
mode+='\nThe changed shared motion path passed one new D1/ReDimNet live recording; all ten profile pins were checked. Other unchanged model/raw routes were not rerun. Three slots remain.\n'
docs['MODE_GUIDE.md']=mode
health=old['INSTALL_HEALTH_AND_RECOVERY.md'].decode().replace('field-runtime-v23','field-runtime-v27').replace('version23','version27')
health=health.replace('The final private prepared-device kit includes code, TitaNet assets, operator sources and exact manifests.',
    'The historical v23 prepared-device kit includes its old code, TitaNet assets, operator sources and exact manifests; it does not include mounted motion. The v27 install backups and motion source/capsule are the current restore basis.')
a=health.index('Use the PC `Refresh-JustPeachy.ps1`');b=health.index('The rollback shortcut',a)
health=health[:a]+'''Use `renew_motion_runtime.py` in the host motion directory, with the exact
PowerShell/CMD/Anaconda commands in MODE_GUIDE.md and the source README. The old
Refresh-JustPeachy wrapper would omit motion. The new wrapper preserves completed
recordings, independently reads back the PC copy, restores the idle baseline,
inspects actual current ownership/resources and installs a fresh motion version.
Its combined CLI is prepared/compiled/planned only; component paths have execution
evidence. Failed recordings need their specific preserved-failure recovery first.

'''+health[b:]
health=health.replace('The1024prior-owner and other finite bounds remain explicit;',
    'A measured metadata-only continuation allows at most1088 prior identities under the unchanged256KiB request ceiling; all old identities and other finite bounds remain explicit;')
health+='''
Mounted sensor configuration is `/home/peachyprototype/JustPeachy/data/imu_config.json`.
Its fixed geometry and library hash are pinned. Stale/unavailable sensor data
suspends location trust; do not fabricate a corrected direction. Source25's graphic
failure and26's AEC255 firmware fault were preserved. One conditional maintenance
send followed that actual fault; matching firmware readback and the v27 recording
succeeded. No periodic reset is configured or authorized. See MOTION_GUIDE.
'''
docs['INSTALL_HEALTH_AND_RECOVERY.md']=health
paths=old['PATHS_AND_BACKUPS.md'].decode()
end=paths.index('\n\n| Purpose')
paths='# Paths and verified backups\n\nCurrent native release: `/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v27`. Last observed manager2626/start362288 on bootfddfa8ec-8af2-4e41-ae56-f2ac5dcc73d4 was idle, capture off, with three slots left. These are recorded observations, not reusable future process authority.'+paths[end:]
paths=paths.replace('field-runtime-v23-install','field-runtime-v27-install').replace('field-runtime-v23-profiles','field-runtime-v27-profiles')
paths=paths.replace('| Prepared-device runtime kit |','| Historical v23 prepared-device kit (without mounted motion) |')
paths=paths.replace('| Independent expanded kit restore |','| Historical v23 expanded kit restore |')
paths=paths.replace('The current prepared-device kit supplements existing pinned baseline/Nemotron dependencies; it is not an OS image. The small final ChatGPT ZIP is documentation only. FINAL_ARTIFACT_INDEX and FINAL_HANDOFF_RECEIPT record final immutable paths/hashes after packaging.',
    'The old prepared-device kit and FINAL_* artifact receipts remain immutable v23 history. Use MOTION_RELEASE_INDEX and MOTION_HANDOFF_RECEIPT for this addition. The new small ChatGPT ZIP includes documentation and selected readable motion source; it excludes private data/models and is not an OS image.')
paths+='''
## Mounted motion addition

| Purpose | Path |
|---|---|
| Host code/current README | C:/Users/amiri/Documents/GitHub/just-peachy/Resumes/imu_integration_20261002 |
| Reviewed repository source | mounted_imu_20261002 under the native tools directory |
| Motion private base I | B/imu-integration-20261002 |
| Current common capsule + independent restore | I/runtime-capsule-v3 |
| Current compact result | I/delivery-review-v1/RESULT.json |
| New processed recording original PC copy | I/offload-v27-original/tree/field-operator-sessions-v10108 |
| Independent Pi-local recording PC copy | I/offload-v27-local/tree/recording-01 |
| Fixed mount backup/restore | I/mount-save-v1 |
| Physical turn evidence | I/physical-v1 |
| Current shortcut/idle receipt | I/shortcuts-v27-v2 |
| New source/docs backup + independent restore/handoff | I/publication-v1 |
| Failed25/26 source and manager preservation | B/field-runtime-v25-preservation-mounted-v1 and B/field-runtime-v26-preservation-mounted-v1 |

The two new recording copies each contain201files/3641161bytes/27directories,
manifestSHA92cc5105498b7997fbcddf4e42ae807f63c1fe6f9d6bd6744aa7178bce4ac598.
They are private and are never included in the source/handoff ZIP.
'''
docs['PATHS_AND_BACKUPS.md']=paths
handoff=old['CHATGPT_HANDOFF.md'].decode()
handoff=handoff.replace('# ChatGPT handoff — prepared CM5 runtime','# ChatGPT handoff — current mounted-motion runtime\n\nRead START_HERE, MODE_GUIDE and MOTION_GUIDE first. Current release is v27; the following v23 completion account is retained history. The new shared mounted motion path was deployed, checked with one5.25s live recording and two independent complete PC copies, and left idle with three slots remaining. All ten profile pins share the same common code. IMU thread cost was1.21% of one core at50.29samples/s; not total pipeline or battery cost.\n\nUse microphone-array-centered geometry and distinguish raw device-relative beam arrows from trusted relative-anchor location logic. BMI270 has no absolute heading/position reference: yaw can drift; detected translation/gaps suspend location assumptions. Current live pose is excluded from plain saved WAVs. Source in mounted-source/runtime is exact deployed code for reading, not a bare standalone launcher. The prior prepared-device kit and refresh wrapper omit this addition. See the new motion renewal command and MOTION_* receipts. No noisy-world accuracy, battery or physical-touch claim is added.\n\n## Earlier runtime/model completion (v23 history)')
docs['CHATGPT_HANDOFF.md']=handoff
docs['CURRENT_RUNTIME_PROGRESS.md']='''# Current runtime progress

field-runtime-v27 is installed, idle and capture off, display270, with three
recording slots remaining and ten profile shortcuts plus rollback. The shared
mounted BMI270 implementation and array-centered transform are deployed.

Actual changed integration:5.25s/84000samples/525blocks;79causal beam records with
no queue drops;44pose records, including8explicit invalid startup poses and36valid
poses after automatic stationary recovery. Source/model/archive/command closure,
local backup and two complete independent PC copies passed. IMU thread50.29Hz,
1.21% of one core. The same final code's optional graphic show/tap/hide passed.

All ten profiles bind the exact common capsule. Earlier model/raw/control passes
remain separately scoped; unchanged profiles were not exhaustively rerun. Old
v25/v26 failures remain preserved. Current receipts are MOTION_RELEASE_INDEX,
MOTION_CHECKLIST and MOTION_HANDOFF_RECEIPT. Old FINAL_* receipts describe v23.

No additional native job is required for this handoff. Physical touch, cable-
disconnected coldboot, long-term yaw drift, battery endurance and noisy-human
recognition remain operator validation. Reliable inertial room position is not
available; acceleration suspends location priors without inventing translation.
'''
docs['FINAL_OPERATOR_GUIDE.md']='''# Operator entry

The current field-runtime-v27 has mounted motion and three recording slots left.
It opens idle/capture off. Read MODE_GUIDE.md for all ten combinations, controls,
duration limits, recording formats and PC offload. Read MOTION_GUIDE.md for the
automatic reference, optional graphic and inertial-position limitations.

INSTALL_HEALTH_AND_RECOVERY.md contains the current motion-preserving renewal
path. Old Refresh-JustPeachy and the v23 kit omit motion. The new handoff has
guides and readable source, not models/private data or a fresh-device OS image.
Use FIELD_VALIDATION.md/FIELD_RUN_TEMPLATE.json for real-world comparison; keep
TitaNet/ReDimNet galleries separate and retain every recording/failure receipt.
'''
docs['BACKEND_COMBINATIONS.md']=old['BACKEND_COMBINATIONS.md'].decode()+'''
Mounted motion is shared across all ten profile pins in v27. Existing live spatial
consumers receive trusted rotation-aware cues; voice-only/native anonymous rules
are unchanged, and current pose is excluded from plain saved WAVs. MOTION_GUIDE
describes geometry, efficient sampling and limits. Three recording slots remain.
'''
docs['MOTION_GUIDE.md']=(H/'MOTION_GUIDE.md').read_text(encoding='utf-8')
for n,t in docs.items():put(C/n,t.replace('\r\n','\n').encode(),existing=n in old)
entry='''# Just Peachy delivery

The prepared CM5 runs **field-runtime-v27**, including all ten backend profiles
and the mounted BMI270 integration. It was left idle, capture off, with **three
recording slots remaining**. Start with [the operator entry](research/nvidia_nemo_comparison/20260924_campaign/n5/completion_20261001/START_HERE.md),
then the mode and motion guides linked there. The current motion handoff receipt
is MOTION_HANDOFF_RECEIPT.json; older FINAL_* receipts and the v23 kit are history.

Relative rotation/tilt are integrated; reliable absolute room translation is not
available from this six-axis sensor. Real-world recognition, battery and physical
interaction validation remain separate from the completed functional check.
'''
put(W/'DELIVERY_START_HERE.md',entry.encode(),existing=True)

index=dict(schema='just-peachy.mounted-motion-release.v1',observed_utc=now.isoformat(),
    result=report,host_code=str(H),repository_source=str(dest),private_evidence=str(I),
    native_root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v27',
    renewal='renew_motion_runtime.py; combined wrapper prepared/compiled/planned only',
    historical_kit='runtime-delivery-v23; excludes mounted motion',
    fixed_mount_sha256='e17ea820ca7a960d71a6c82b649b7901293574e7771d49fc82c90bb3a3a5eaab')
put(C/'MOTION_RELEASE_INDEX.json',enc(index))
checklist=dict(schema='just-peachy.mounted-motion-checklist.v1',items=[
    dict(id='M01',task='Confirm mounted axes and actual microphone-array center',status='DONE',evidence='mount-save-v1; integrated-v27-v1 geometry'),
    dict(id='M02',task='Save fixed mount and exercise approximate90degree physical turn',status='DONE_FUNCTIONAL_NOT_ACCURACY',evidence='physical-v1; mount-save-v1'),
    dict(id='M03',task='Share efficient causal pose/beam path across all10profile pins',status='DONE',evidence='runtime-capsule-v3; delivery-review-v1'),
    dict(id='M04',task='Correct existing location/display frames and invalidate unreliable motion',status='DONE',evidence='changed-check-v1; actualstartupgapandrecovery'),
    dict(id='M05',task='Optional hidden-by-default graphic with visual-onlyzero',status='DONE',evidence='integrated-v26-v1; samefinalcommoncode'),
    dict(id='M06',task='One changed live recording, Stop/Save/closure and two independentPCcopies',status='DONE',evidence='integrated-v27-v1; offload-v27-original/local'),
    dict(id='M07',task='Measure workerCPU, retain bounded queues and sampling',status='DONE_SCOPED',evidence='1.21%onecore50.29Hz; excludesbeamgettersandbattery'),
    dict(id='M08',task='Currentshortcuts, guides, sourcebackup and updatedhandoff',status='DONE',evidence='shortcuts-v27-v2; publication-v1'),
    dict(id='V01',task='Physicaltouch, noisyspeakercomparison, longdrift, battery and coldboot',status='REAL_WORLD_VALIDATION_OPEN'),
    dict(id='L01',task='Absoluteheading, reliableroomtranslation and plainWAVmotionreplay',status='NOT_IMPLEMENTED_OR_OBSERVABLE',reason='Noexternalheading/position/range; no synchronizedsidecarreplay')])
put(C/'MOTION_CHECKLIST.json',enc(checklist))

# Exact source copies; never publish private media, profile vectors or raw traces.
selected=('mounted_spatial.py','derive_mounted_imu.py','bind_runtime_motion_v3.py','prepare_runtime_motion_v3.py',
          'check_mounted_spatial.py','prepare_motion_operator.py','renew_motion_runtime.py',
          'review_motion_delivery.py','copy_motion_recording.py','run_motion_recording.py',
          'README.md','MOTION_GUIDE.md','README_PUBLICATION.md','publish_motion_delivery.py')
published={}
def source(n,r):
    if n.endswith('.py'):ast.parse(r);compile(r,n,'exec')
    put(dest/n,r);published[n]=r
for n in selected:source(n,(H/n).read_bytes())
for folder in ('operator-tools-v1','deployment-tools-v5'):
    for p in sorted((H/folder).glob('*.py')):source(folder+'/'+p.name,p.read_bytes())
    for p in sorted((H/folder).glob('*.py.restore')):source(folder+'/'+p.name,p.read_bytes())
    for n in ('DERIVATION.json','HISTORY_BOUND.json'):
        p=H/folder/n
        if p.exists():source(folder+'/'+n,p.read_bytes())
source('deployment-tools-v3/install_mounted_native.py',(H/'deployment-tools-v3/install_mounted_native.py').read_bytes())
for n in ('imu.py','live_spatial.py'):source('runtime/'+n,(I/'changed-check-v1'/(n+'.prepared')).read_bytes())
common=json.loads((I/'runtime-capsule-v3/COMMON_BUNDLE.restore.json').read_bytes())
for n in ('field_live_source_bridge_v6.py','field_live_source_factory_v6.py','field_operator_controller_v6.py',
          'field_operator_ui_v1.py','isolated_live_facade_v9.py','isolated_pipeline_source_v11.py'):
    source('runtime/'+n,base64.b64decode(common['files'][n],validate=True))
source('runtime/README.md',b'''# Exact motion runtime source

These are the selected deployed common-capsule members and the mounted imu.py /
live_spatial.py injected into the pinned installed app. Read them for architecture
and math. Do not run these modules as bare scripts: the versioned manager supplies
their policy, leases, paths, model pins and hardware lifecycle. Normal Pi operation
uses the current desktop profile shortcuts (see completion MODE_GUIDE.md).

For PowerShell/CMD/Anaconda preparation, input/output definitions and exact host
commands, read ../README.md. The deployable environment and existing local assets
remain required. This source directory contains no model weights or recordings.
''')
source('SOURCE_MANIFEST.json',enc({n:dict(bytes=len(r),sha256=sha(r)) for n,r in published.items()}))

# Whitelist and independently restore every changed/current published byte.
paths=[W/'DELIVERY_START_HERE.md']+[C/n for n in docs]+[C/'MOTION_RELEASE_INDEX.json',C/'MOTION_CHECKLIST.json']+[dest/n for n in published]
manifest={}
for p in paths:
    r=p.read_bytes();n=p.relative_to(W).as_posix();manifest[n]=dict(bytes=len(r),sha256=sha(r))
    put(O/'published-backup'/n,r);put(O/'published-restore'/n,r)
save('PUBLICATION.json',dict(files=manifest,source_bytes=sum(x['bytes'] for x in manifest.values()),native_action=False))

# Keep the prior handoff's context, replacing only current guides and adding source.
oldreceipt=json.loads((C/'FINAL_HANDOFF_RECEIPT.json').read_bytes())
save('PREVIOUS_HANDOFF_REFERENCE.json',oldreceipt)
builder=ast.parse((C/'build_handoff_v5.py').read_bytes())
docnames=ast.literal_eval(next(n.value for n in builder.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DOCS' for t in n.targets)))
payload={n:(C/n).read_bytes() for n in docnames}
for n in ('MOTION_GUIDE.md','MOTION_RELEASE_INDEX.json','MOTION_CHECKLIST.json'):payload[n]=(C/n).read_bytes()
campaign=C.parent.parent
for name,relative in {
    'historical/N1_HANDOFF.md':'N1_HANDOFF.md','historical/N2_HANDOFF.md':'n2/N2_HANDOFF.md',
    'historical/N3_HANDOFF.md':'n3/N3_HANDOFF.md','historical/N4_PARTIAL_REPORT_20260927.md':'n4/N4_PARTIAL_REPORT_20260927.md',
    'historical/RELEASE_MAPPING_20260927.md':'n5/RELEASE_MAPPING_20260927.md','reference/LICENSE_LEDGER.md':'n5/LICENSE_LEDGER.md',
    'reference/ENROLLMENT_COMPATIBILITY.md':'n5/ENROLLMENT_COMPATIBILITY.md','reference/EXPERIMENTS.json':'n5/realtime_validation_v1/EXPERIMENTS.json',
    'reference/REAL_WORLD_HOLDOUT_V1.md':'n5/realtime_validation_v1/REAL_WORLD_HOLDOUT_V1.md'}.items():payload[name]=(campaign/relative).read_bytes()
for n in ('D1_METHOD_APPLICATION_FINDINGS_V1.md','FIELD_LOCAL_JOINT_ACTUAL_FINDINGS_V1.md'):payload['evidence/'+n]=(P/n).read_bytes()
for n,r in published.items():
    if n.startswith('runtime/') or n in ('mounted_spatial.py','derive_mounted_imu.py','bind_runtime_motion_v3.py','README.md'):
        payload['mounted-source/'+n]=r
assert sum(map(len,payload.values()))<2*1024**2
payload['BUNDLE_MANIFEST.json']=enc(dict(schema='just-peachy.motion-handoff.v1',release='field-runtime-v27',
    created_utc=now.isoformat(),private_payloads_included=False,models_included=False,standalone_deployment=False,
    files={n:dict(bytes=len(r),sha256=sha(r)) for n,r in payload.items()}))
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
    for n,r in sorted(payload.items()):z.writestr(n,r)
zr=buf.getvalue();assert len(zr)<2*1024**2
zipname='JustPeachy-motion-v27-ChatGPT-handoff.zip'
put(O/zipname,zr);put(O/'handoff-independent-backup'/zipname,zr)
with zipfile.ZipFile(O/'handoff-independent-backup'/zipname) as z:
    assert set(z.namelist())==set(payload)
    for n,r in payload.items():
        assert z.read(n)==r
        put(O/'handoff-independent-restore'/n,r)
receipt=dict(schema='just-peachy.motion-handoff-receipt.v1',path=str(O/zipname),bytes=len(zr),sha256=sha(zr),
    members=len(payload),complete_member_readback=True,independent_zip_and_expanded_restore=True,
    private_audio_or_models=False,old_packs_unchanged=True)
put(C/'MOTION_HANDOFF_RECEIPT.json',enc(receipt))
n=(C/'MOTION_HANDOFF_RECEIPT.json').relative_to(W).as_posix();r=enc(receipt)
put(O/'published-backup'/n,r);put(O/'published-restore'/n,r)
manifest[n]=dict(bytes=len(r),sha256=sha(r))
save('FINAL_WHITELIST.json',manifest)
save('CLOSED.json',dict(closed_utc=datetime.now(timezone.utc).isoformat(),charged_before_receipt=charged,
    maximum_bytes=budget,within_deadline=time.monotonic()<deadline,files=len(manifest),
    all_backups_restored=True,code_compiled_without_execution=True,native_action=False))
print(json.dumps(dict(files=len(manifest),charged_bytes=charged,handoff=receipt)))
