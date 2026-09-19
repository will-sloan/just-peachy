"""Workbook trial identity, metadata and explicitly sequential microphone passes.

Reservation runs under the server's inter-process device lease. Existing folders
are never adopted, modified or reused, even after an incomplete reservation.
"""
import copy
import json
import math
import re
import shutil
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .core import now, write_json, freeze, sha


def validate_setup(setup,required=True):
    if not isinstance(setup,dict):raise ValueError('Setup must be an object')
    s=json.loads(json.dumps(setup,allow_nan=False))
    for key,label in [('room_name','Room name'),('position_name','Position name')]:
        value=s.get(key)
        if value is not None and not isinstance(value,str):raise ValueError(label+' must be text')
        value=' '.join((value or '').split())
        if required and not value:raise ValueError(label+' is required')
        if len(value)>120:raise ValueError(label+' must be at most 120 characters')
        s[key]=value or None
    for key in ['source','device','obstruction']:
        if key not in s:s[key]={}
        if not isinstance(s[key],dict):raise ValueError(key+' must be an object')
    for key,label,valid in [('distance_to_array_m','Distance in metres',lambda x:x>0),
                            ('azimuth_lab_deg','Angle in degrees',lambda x:-180<=x<=180)]:
        value=s['source'].get(key)
        if value is None:
            if required:raise ValueError(label+' is required')
        elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not valid(value):
            raise ValueError(label+' must be positive' if key=='distance_to_array_m' else label+' must be between -180 and 180')
        s['source'][key]=value
    pose=s['device'].get('orientation')
    if pose not in (['FLAT','UPRIGHT'] if required else [None,'UNKNOWN','FLAT','UPRIGHT']):
        raise ValueError('Select Flat or Upright')
    obstructed=s['obstruction'].get('present')
    if (required or obstructed is not None) and not isinstance(obstructed,bool):
        raise ValueError('Obstruction must be true or false, independent of pose')
    clutter=s.get('clutter_state','unknown')
    if clutter not in ['unknown','clear','normal']:raise ValueError('Clutter must be unknown, clear or normal')
    s['clutter_state']=clutter
    for key,default,pattern in [('table_id','T01',r'T\d{2,3}'),('device_placement_id','D01',r'D\d{2,3}'),
                               ('pilot_phase','P1',r'P[0-3]'),('source_facing','NAT',r'NAT|TOW')]:
        value=s.get(key) or default
        if not isinstance(value,str) or not re.fullmatch(pattern,value):raise ValueError('Invalid '+key.replace('_',' '))
        s[key]=value
    s['schema_version']=2
    s['physical_array']={'kind':'default_onboard_linear','microphone_order_seated_left_to_right':['MIC0','MIC1','MIC2','MIC3'],
        'order_provenance':'user_reported','external_connections_removed_user_reported':True}
    s['angle_convention']={'origin':'array acoustic centre','units':'degrees',
        'zero':'protocol forward arrow away from seated user; photograph and confirm before pilot',
        'positive':'counterclockwise toward seated user left','range':[-180,180],
        'native_xvf_transform_verified':False,'native_linear_front_rear_ambiguity':True,
        'distance_interpretation':'operator-entered distance from array acoustic centre to source reference point; record point in notes'}
    s['imu']={'recorded':False,'pose_provenance':'operator_reported'}
    return s


def _metadata(runs):
    for path in runs.glob('*/00_admin/trial_metadata.json'):
        if not path.resolve().is_relative_to(runs.resolve()):continue
        try:
            if path.stat().st_size>2097152:raise ValueError('oversized metadata')
            yield json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError) as error:
            # Do not silently reuse a human-label ID when its registry evidence
            # is unreadable. This is deliberately an actionable preflight error.
            raise RuntimeError('Cannot read trial identity metadata: '+str(path)) from error


def reserve_trial(req,runs_root):
    """Atomically own a new directory and snapshot user metadata before capture."""
    request=copy.deepcopy(req)
    request['setup']=validate_setup(request.get('setup',{}),required=request.get('mode')=='measure')
    runs=Path(runs_root);runs.mkdir(parents=True,exist_ok=True)
    rows=list(_metadata(runs));s=request['setup'];recorded=now();retake=request.get('retake_of')
    if request.get('mode')=='record' and not (s['room_name'] and s['position_name']):
        if retake:raise ValueError('Retake requires a named measurement')
        measurement='TAKE_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'_'+uuid.uuid4().hex[:6]
        condition=None;repeat=None;take=1;room_id=None;position_id=None
    else:
        def label(v):return str(v or '').casefold()
        room_map={label(r.get('setup',{}).get('room_name')):r['room_id'] for r in rows if r.get('room_id')}
        room_id=room_map.get(label(s['room_name']))
        if room_id is None:room_id='R'+str(max([int(v[1:]) for v in room_map.values()]+[0])+1).zfill(2)
        position_map={label(r.get('setup',{}).get('position_name')):r['position_id'] for r in rows if r.get('room_id')==room_id and r.get('position_id')}
        position_id=position_map.get(label(s['position_name']))
        if position_id is None:position_id='S'+str(max([int(v[1:]) for v in position_map.values()]+[0])+1).zfill(2)
        pose='F00' if s['device'].get('orientation')=='FLAT' else 'UPR' if s['device'].get('orientation')=='UPRIGHT' else 'UNK'
        clutter='C2' if s['obstruction'].get('present') else {'unknown':'CU','clear':'C0','normal':'C1'}[s['clutter_state']]
        condition='_'.join(['JPXVF',s['pilot_phase'],room_id,s['table_id'],s['device_placement_id'],position_id,pose,s['source_facing'],clutter])
        siblings=[r for r in rows if r.get('condition_id')==condition]
        repeat=max([r.get('repeat_number',0) or 0 for r in siblings]+[0])+1;take=1
        if retake:
            old=next((r for r in rows if r.get('run_id')==retake),None)
            if old is None or old.get('condition_id')!=condition:raise ValueError('Retake ID must name an existing trial with the same room, position and condition')
            repeat=old['repeat_number']
            take=max([r.get('take_number',1) for r in siblings if r.get('repeat_number')==repeat]+[1])+1
        measurement=condition+'_R'+str(repeat).zfill(2)
    while True:
        runid=measurement+('__TAKE'+str(take).zfill(2) if take>1 else '')
        folder=runs/runid
        try:folder.mkdir(exist_ok=False);break
        except FileExistsError:take+=1
    # From this point only this caller owns folder. All writes are exclusive.
    for name in ['00_admin','01_photos','02_raw','03_derived','04_hil_exports','05_analysis']:(folder/name).mkdir()
    s.update(room_id=room_id,position_id=position_id,placement_id=position_id,repeat_number=repeat)
    request['schema_version']=request.get('schema_version',2)
    metadata={'storage_schema_version':2,'run_id':runid,'measurement_id':measurement,'condition_id':condition,
        'recorded_utc':recorded,'room_id':room_id,'position_id':position_id,'repeat_number':repeat,'take_number':take,
        'retake_of':retake,'setup':s,'domain':request.get('domain','raw'),'mode':request['mode'],
        'capture_relationship':'sequential different acoustic realizations' if request.get('domain')=='both' else 'single pass',
        'planned_domains':['raw','amplified'] if request.get('domain')=='both' else [request.get('domain','raw')],
        'coordinate_values_in_filename':False,'id_defaults_are_protocol_labels_not_measured_geometry':True}
    write_json(folder/'request.json',request);write_json(folder/'00_admin/trial_metadata.json',metadata)
    (folder/'00_admin/notes.md').write_text(str(s.get('notes') or 'No additional operator notes.')+'\n',encoding='utf-8')
    for name,text in [('01_photos','Photo references are in trial metadata. Add later photos in a NEW supplement folder outside this frozen trial.'),
                      ('04_hil_exports','Reserved for the workbook workflow. No HIL stimulus exported by this recorder.'),
                      ('05_analysis','Reserved for the workbook workflow. No final RIR or scientific acceptance produced by this recorder.')]:
        (folder/name/'README.txt').write_text(text+'\n',encoding='utf-8')
    return folder


def acquire_trial(req,folder,stop,update,capture=None):
    """Run one or two complete acquisitions inside an already owned trial."""
    if capture is None:
        from .acquisition import acquire
        capture=acquire
    folder=Path(folder)
    if (folder/'SHA256SUMS.txt').exists():raise FileExistsError('Trial already frozen')
    saved=json.loads((folder/'request.json').read_text(encoding='utf-8'))
    metadata=json.loads((folder/'00_admin/trial_metadata.json').read_text(encoding='utf-8'))
    domains=metadata['planned_domains'];passes=[];writer_active=False;failure=None
    for index,domain in enumerate(domains):
        if stop.is_set():break
        passid=f'pass_{index+1:02d}_{domain}';target=folder/'02_raw'/passid
        child=copy.deepcopy(saved);child['domain']=domain;child['trial_group_id']=folder.name;child['pass_id']=passid
        child['pass_index']=index+1;child['planned_passes']=len(domains)
        def report(**values):
            if 'progress' in values:values['progress']=(index+float(values['progress']))/len(domains)
            if 'message' in values:values['message']=f'Pass {index+1}/{len(domains)} · {domain}: '+values['message']
            update(**values)
        report(state='preflight',message='Preparing microphone routing and telemetry',progress=0)
        try:
            result=capture(child,target,stop,report)
            writer_active=bool(result.get('hardware_logger_still_active'))
            derived=folder/'03_derived'/passid;derived.mkdir()
            copied=[]
            for name in ['MIC0.wav','MIC1.wav','MIC2.wav','MIC3.wav','processed_auto.wav','quality.json']:
                if (target/name).is_file():
                    destination=derived/('qc_summary.json' if name=='quality.json' else name)
                    shutil.copy2(target/name,destination)
                    copied.append({'source':'02_raw/'+passid+'/'+name,'source_sha256':sha(target/name),
                                   'derived':destination.name,'derived_sha256':sha(destination)})
            write_json(derived/'provenance.json',{'source_pass':'02_raw/'+passid,
                'operation':'byte-identical copies of demultiplexed, unnormalized channels and QC; no RIR deconvolution',
                'domain':domain,'common_time_base_preserved':True,'files':copied,'processing_contract_version':2,
                'native_packed_sha256':sha(target/'native_packed.wav') if (target/'native_packed.wav').is_file() else None,
                'source_code_sha256':{name:sha(target/'source'/name) for name in ['core.py','acquisition.py','trial.py'] if (target/'source'/name).is_file()}})
        except BaseException as error:
            failure=repr(error)
            (folder/'00_admin'/f'{passid}_failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
            result={'status':'INVESTIGATE','capture_integrity_pass':False,'message':failure,'error':failure}
        passes.append({'domain':domain,'pass_id':passid,'run_id':result.get('run_id',passid),
            'status':result['status'],'capture_integrity_pass':result.get('capture_integrity_pass',False),
            'message':result.get('message'),'acoustic_marker_review':result.get('acoustic_marker_review'),
            'report_url':'/runs/'+folder.name+'/02_raw/'+passid+'/REPORT.txt',
            'json_url':'/runs/'+folder.name+'/02_raw/'+passid+'/result.json',
            'quality':result.get('quality',{}),'telemetry':result.get('telemetry'),
            'hardware_logger_still_active':writer_active,'reference':result.get('reference',{'enabled':False})})
        if writer_active or result['status'] not in ['PASS','REVIEW'] or not result.get('capture_integrity_pass'):break
    complete=len(passes)==len(domains) and all(p['status'] in ['PASS','REVIEW'] and p['capture_integrity_pass'] for p in passes) and not stop.is_set() and not writer_active
    if complete:
        status='REVIEW' if saved['mode']=='measure' else 'PASS'
        message=f'Recording saved successfully: {len(passes)} of {len(domains)} passes passed acquisition checks.'
        if saved['mode']=='measure':message+=' Acoustic review and later RIR analysis are still required.'
    else:
        status='INVESTIGATE' if failure or writer_active or any(p['status']=='INVESTIGATE' for p in passes) else 'RETAKE'
        message=f'Recording needs attention: {len(passes)} of {len(domains)} passes attempted. Evidence retained.'
        if passes:message+=' '+str(passes[-1].get('message') or '')
        if stop.is_set():message+=' Stopped by request; remaining passes were not started.'
    result={'run_id':folder.name,'status':status,'message':message,'recorded_utc':metadata['recorded_utc'],
        'capture_integrity_pass':complete,'scientific_measurement_qualified':False,'quality':{},
        'planned_passes':len(domains),'completed_passes':sum(p['status'] in ['PASS','REVIEW'] and p['capture_integrity_pass'] for p in passes),
        'passes':passes,'sequential':len(domains)>1,'simultaneous_raw_and_amplified':False,
        'hardware_logger_still_active':writer_active,'stopped':stop.is_set(),'error':failure,
        'checks':{'all_planned_passes_accepted':complete,'all_writers_stopped':not writer_active},
        'limits':['Four microphones per pass; raw and amplified are sequential when both selected',
                  'No final RIR deconvolution, absolute SPL, IMU or verified room-angle transform']}
    write_json(folder/'result.json',result)
    (folder/'REPORT.txt').write_text('XVF measurement '+folder.name+'\n\n'+message+'\nStatus: '+status+
        '\nScientific qualification: false\n\n'+''.join(p['domain']+': '+p['status']+' — 02_raw/'+p['pass_id']+'/REPORT.txt\n' for p in passes)+
        '\nMetadata: 00_admin/trial_metadata.json\nDerived channel copies: 03_derived/\nHash manifest: SHA256SUMS.txt\n',encoding='utf-8')
    if not writer_active:result['seal']=freeze(folder)
    return result
