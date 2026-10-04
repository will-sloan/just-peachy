"""Host-only closed GUI mirror/recording audit. README_GUI_RECORDING_REVIEW.md."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
import time
import wave


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(path):
    info=path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
        raise ValueError('Single-link regular private mirror member required')
    result=hashlib.sha256()
    with path.open('rb') as stream:
        while raw:=stream.read(1024**2):result.update(raw)
    if path.stat().st_size!=info.st_size:raise ValueError('Mirror member changed during independent readback')
    return info.st_size,result.hexdigest()


def read_json(path,maximum=262144):
    if path.stat().st_size>maximum:raise ValueError('Bounded metadata receipt required')
    return json.loads(path.read_bytes())


def review(mirror,selected):
    result=read_json(mirror/'RESULT.json');done=read_json(mirror/'MIRROR_COMPLETE.json')
    rows=read_json(mirror/'MIRROR_MANIFEST.json',2*1024**2);job=result['job'];closed=done['closure']
    if (result.get('status')!='FULL_CLOSED_OUTPUT_MIRRORED' or result.get('functional_success') is not True or
        done.get('kind')!='COMPLETE' or done.get('mirror_scope')!='all_regular_output_files' or
        not all(closed.get(key) is True for key in ('closed','exact_owner_gone','cgroup_empty')) or
        any(closed.get(key)!=job[key] for key in ('owner','unit','invocation_id','control_group')) or
        closed['job_exit'].get('natural_returncode')!=0 or closed['job_exit'].get('error') or
        closed['job_exit'].get('leases_released') is not True):
        raise ValueError('Actual successful whole-unit and full-mirror closure required')
    if hashlib.sha256(canonical(rows)).hexdigest()!=done['manifest_sha256']:
        raise ValueError('Canonical full mirror manifest pin differs')
    root=mirror/'closed-output';expected={};total=0
    for row in rows:
        name=row['path'];relative=PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or relative.as_posix()!=name or name in expected:
            raise ValueError('Exact safe unique mirror member required')
        path=root.joinpath(*relative.parts)
        if path.resolve(strict=True)!=path:raise ValueError('Mirror path redirects outside closed root')
        size,sha=digest(path)
        if (size,sha)!=(row['identity']['bytes'],row['sha256']):raise ValueError('Independent mirror file/hash differs: '+name)
        expected[name]=row;total+=size
    actual=set()
    for directory,children,files in os.walk(root,followlinks=False):
        if any((Path(directory)/name).is_symlink() for name in children):raise ValueError('Mirror directory symlink')
        for name in files:actual.add((Path(directory)/name).relative_to(root).as_posix())
    if actual!=set(expected) or total!=done['bytes'] or len(rows)!=done['files']:
        raise ValueError('Complete mirror membership/extent differs')
    gui=read_json(root/'gui/GUI_RESULT.json');unit=read_json(root/'UNIT_OWNERSHIP.json')
    if (gui.get('status')!='GUI_PROGRAMMATIC_CHECK_PASSED' or gui.get('failure') is not None or
        gui.get('owner')!=job['owner'] or unit['owner']!=job['owner'] or gui['unit']!=unit or
        not all(gui.get(k) is True for k in ('actual_tk','desktop_orientation_preserved','exit_to_desktop_invoked',
            'policy_boundary_observed','replay_waited_for_natural_eof','save_raw_requested')) or
        gui.get('stop_button_invocations')!=0 or gui.get('native_model_sessions')!=2 or selected!=gui['sessions'][0]):
        raise ValueError('Exact actual live policy-Stop/SaveRaw/replay/Exit receipt required')
    geometry=read_json(root/'gui/001-stable-geometry.json')
    if len(geometry['samples'])!=10 or any(row['extent']!=[480,800,0,0] or row['fullscreen'] is not True for row in geometry['samples']):
        raise ValueError('Ten actual stable fullscreen480x800+0+0 samples required')
    workers={};owner_rows=[dict(role='gui',owner=job['owner'],closed=True)]
    for launch in (root/'data/launches').iterdir():
        closure=read_json(launch/'HOST_CLOSURE.json');owner=read_json(launch/'worker/REGISTERED_OWNER.json')
        value=closure['result'];session=value['session_id']
        if (closure.get('registered_owner')!=owner or closure.get('direct_child_reaped') is not True or
            closure.get('stdout_reader_joined') is not True or closure.get('returncode')!=0 or
            closure.get('output_error') or closure.get('receipt_errors') or value.get('failure') is not None or
            value['result'].get('status')!='FUNCTIONAL_SESSION_COMPLETED'):
            raise ValueError('Exact successful directly reaped worker closure required')
        workers[session]=closure;owner_rows.append(dict(role='worker',session_id=session,owner=owner,closed=True))
    if set(workers)!=set(gui['sessions']):raise ValueError('Actual GUI/worker session membership differs')
    source=read_json(root/f'data/recordings/sessions/{selected}/work/source/SOURCE_CLOSE.json')
    source_owner=read_json(root/f'data/recordings/sessions/{selected}/work/source/REGISTERED_OWNER.json')['owner']
    nested=workers[selected]['nested_source'];raw_capture=source['raw_capture']
    if (source['owner']!=source_owner or nested['owner']!=source_owner or nested.get('closed') is not True or
        nested.get('state')!='ABSENT' or source.get('kind')!='CLOSED' or source.get('error') is not None or
        not all(source.get(k) is True for k in ('stream_closed','lease_released')) or
        source['integrity'].get('restoration_ok') is not True or source['status'].get('dropped_frames')!=0 or
        source['status'].get('fault') is not None or source['status'].get('callback_fault_detail') is not None or
        raw_capture.get('transport_partition_checked') is not True or raw_capture.get('parent_durable_spool_ack') is not True):
        raise ValueError('Exact physical source closure/restoration/clock receipt required')
    owner_rows.append(dict(role='physical_source',owner=source_owner,closed=True))
    dbpath=root/'data/recordings/history.sqlite3'
    db=sqlite3.connect(dbpath.as_uri()+'?mode=ro&immutable=1',uri=True);db.row_factory=sqlite3.Row
    try:
        sessions={row['id']:dict(row) for row in db.execute('SELECT * FROM sessions ORDER BY seq')}
        replay=gui['sessions'][1]
        if set(sessions)!=set(gui['sessions']) or sessions[selected]['status']!='kept' or sessions[replay]['status']!='discarded':
            raise ValueError('Selected original kept / replay discarded isolation differs')
        metadata=read_json(root/f'data/recordings/sessions/{selected}/session.json')
        expected_samples=4800000
        if metadata.get('include_raw') is not True or metadata['processed_samples']!=expected_samples or metadata['raw_samples']!=expected_samples:
            raise ValueError('Exact300second kept raw+processed recording required')
        for session in gui['sessions']:
            if workers[session]['result']['result']['source_samples']!=expected_samples:
                raise ValueError('Original/replay complete source clocks differ')
        if source['sent_samples']!=expected_samples or raw_capture['samples']!=expected_samples or raw_capture['bytes']!=expected_samples*16:
            raise ValueError('Physical source count/byte boundary differs')
        segments=list(db.execute('SELECT * FROM segments WHERE session_id=? ORDER BY kind,idx',(selected,)))
        timelines={};audio_bytes=0;entries=5;raw_sha=hashlib.sha256()
        for kind,width in (('processed',4),('raw',16)):
            cursor=0;count=0
            for item in segments:
                row=dict(item)
                if row['kind']!=kind:continue
                if row['start_sample']!=cursor:raise ValueError('Gap or overlap in authoritative saved timeline')
                path=root/f'data/recordings/sessions/{selected}'/row['data_name']
                if path.stat().st_size!=row['samples']*width:raise ValueError('Audio segment sample/byte extent differs')
                if kind=='raw':
                    with path.open('rb') as stream:
                        while block:=stream.read(1024**2):raw_sha.update(block)
                audio_bytes+=path.stat().st_size;entries+=1
                if row['replay_name']:
                    path=root/f'data/recordings/sessions/{selected}'/row['replay_name']
                    with wave.open(str(path),'rb') as wav:
                        if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())!=(1,2,16000,row['samples']):
                            raise ValueError('Replay WAV header/sample count differs')
                    audio_bytes+=path.stat().st_size;entries+=1
                cursor+=row['samples'];count+=1
            if cursor!=expected_samples:raise ValueError('Segmented complete source duration differs')
            timelines[kind]=dict(segments=count,samples=cursor,bytes=cursor*width)
        if raw_sha.hexdigest()!=raw_capture['sha256']:raise ValueError('Independent all-raw-segment hash differs from physical source')
        if db.execute('SELECT COUNT(*) FROM segments WHERE session_id=?',(replay,)).fetchone()[0]!=0:
            raise ValueError('Discarded replay still has audio segment references')
        if any(name.startswith(f'data/recordings/sessions/{replay}/') and name.endswith(('.f32','.wav','.bin')) for name in expected):
            raise ValueError('Discarded replay retained audio files')
        aggregates={};required=65536+len(json.dumps(metadata,sort_keys=True).encode())+4096
        for session in gui['sessions']:
            row=dict(db.execute('SELECT used_bytes,limit_bytes FROM metadata_usage WHERE session_id=?',(session,)).fetchone())
            row['captions']=db.execute('SELECT COUNT(*) FROM captions WHERE session_id=?',(session,)).fetchone()[0]
            row['events']=db.execute('SELECT COUNT(*) FROM events WHERE session_id=?',(session,)).fetchone()[0]
            row['artifacts']=db.execute('SELECT COUNT(*) FROM artifacts WHERE session_id=?',(session,)).fetchone()[0]
            aggregates[session]=row
        required+=sum(row['bytes']+1024 for row in db.execute('SELECT bytes FROM artifacts WHERE session_id=?',(selected,)))
        required+=db.execute('SELECT COALESCE(SUM(LENGTH(text)*6+LENGTH(provenance)+4096),0) FROM captions WHERE session_id=?',(selected,)).fetchone()[0]
        required+=db.execute('SELECT COALESCE(SUM(CASE WHEN payload_bytes>0 THEN payload_bytes ELSE LENGTH(CAST(payload AS BLOB)) END+4096),0) FROM events WHERE session_id=?',(selected,)).fetchone()[0]
        required+=audio_bytes+(entries-5)*1024
        entries+=aggregates[selected]['artifacts']
    finally:db.close()
    # Mirrors already retain every utility owner and its exact natural SSH reap.
    phases=0
    for phase in mirror.glob('probe-*'):
        if not phase.is_dir():continue
        closure=read_json(phase/'SSH_CLOSURE.json')
        if closure.get('utility_pid_absent_after_ssh') is not True:raise ValueError('Monitor utility closure incomplete')
        phases+=1
    maximum=math.ceil((required+16*1024**2)/(1024**2))*1024**2
    if maximum>256*1024**2:raise ValueError('Selected export exceeds exact existing finite action capacity')
    admission=read_json(root/'ADMISSION.json')
    payload=dict(package=admission['payload']['package'],package_manifest_sha256=job['package_manifest_sha256'],
        boot_id=job['boot_id'],expires_unix=time.time()+600,label='recording-export-01',session_id=selected,
        recordings_root=job['output_root']+'/data/recordings',source_job=job,maximum_output_bytes=maximum)
    report=dict(schema='just-peachy.gui-recording-host-review.v1',status='INDEPENDENT_METADATA_AND_AUDIO_HASH_REVIEW_PASSED',
        mirror=str(mirror),mirror_manifest_sha256=done['manifest_sha256'],files=len(rows),bytes=total,
        package_manifest_sha256=job['package_manifest_sha256'],owners=owner_rows,monitor_phases_closed=phases,
        selected_session=selected,replay_session=replay,timelines=timelines,raw_concat_sha256=raw_sha.hexdigest(),
        sqlite_bytes=dbpath.stat().st_size,session_metadata=aggregates,export_estimated_upper_bytes=required,
        export_maximum_output_bytes=maximum,export_entries=entries,selected_original_preserved=True,
        replay_discarded=True,raw_source_lag_max_seconds=source['status']['maximum_source_lag_seconds'],
        raw_dropped_frames=0,raw_markers_errors=raw_capture['packing_marker_errors'],
        physical_source_closed=True,route_restored=True,policy_stop_observed=True,whole_replay_natural_eof=True,
        actual_fullscreen_checks=10,desktop_orientation_preserved=True,exit_to_desktop_invoked=True,
        transcript_or_media_displayed=False,physical_touch_qualified=False,visual_quality_qualified=False,
        speech_quality_qualified=False,sustained_hour_qualified=False,native_action_performed=False)
    return report,payload


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mirror',type=Path,required=True);ap.add_argument('--session-id',required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    import psutil
    me=psutil.Process();me.cpu_affinity([14]);args.output.mkdir()
    def save(name,value):
        raw=canonical(value)
        with (args.output/name).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        if (args.output/name).read_bytes()!=raw:raise OSError('Review receipt readback differs')
    save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    report,payload=review(args.mirror.absolute(),args.session_id)
    save('REVIEW.json',report);save('EXPORT_PAYLOAD.json',payload)
    print(json.dumps(dict(status=report['status'],files=report['files'],bytes=report['bytes'],
        export_maximum_output_bytes=report['export_maximum_output_bytes'],output=str(args.output))))


if __name__=='__main__':main()
