"""CPU14 missing-only native backup reconciliation. README_BACKUP_RECONCILER_V4.md."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time


PREPARATION_BYTES = 16 * 1024**2
PHASE_BYTES = 262144
SEGMENT_BYTES = 1024**2
FINAL_RECEIPT_RESERVE = 4 * 1024**2 + 262144


class PreparationBudget:
    """One total allocation; payload/guard mirror have separate reservations."""
    def __init__(self, root):
        self.root = root
        self.used = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
        self.held = FINAL_RECEIPT_RESERVE

    def require(self, count):
        if type(count) is not int or count < 0 or self.used + self.held + count > PREPARATION_BYTES:
            raise ValueError('Existing 16 MiB preparation allocation exhausted')

    def write(self, path, raw):
        if path.parent != self.root or path.exists() or len(raw) > 2 * 1024**2:
            raise ValueError('Fresh bounded top-level preparation receipt required')
        self.require(len(raw))
        with path.open('xb') as stream:
            if stream.write(raw) != len(raw): raise OSError('Short preparation write')
            stream.flush(); os.fsync(stream.fileno())
        if path.read_bytes() != raw: raise OSError('Preparation readback')
        self.used += len(raw)

    def charge_phase(self, directory):
        paths = list(directory.iterdir()) if directory.exists() else []
        if len(paths) > 8 or any(path.is_symlink() or not path.is_file() for path in paths):
            raise ValueError('Unexpected snapshot receipt membership')
        count = sum(path.stat().st_size for path in paths)
        if count > PHASE_BYTES: raise ValueError('Per-phase preparation allocation exhausted')
        self.require(count); self.used += count


def publish_phase(common,path,value):
    """Use the existing durable publisher within the pre-reserved phase cap."""
    raw=common.encoded(value);paths=list(path.parent.iterdir())
    if path.exists() or len(paths)>=8 or any(p.is_symlink() or not p.is_file() for p in paths):
        raise ValueError('Fresh bounded phase receipt required')
    if len(raw)+sum(p.stat().st_size for p in paths)>PHASE_BYTES:
        raise ValueError('Per-phase preparation allocation exhausted before write')
    common.write(path,raw)


def prior_attempt_usage(common,path,job_raw,output):
    """Charge preserved pre-transfer failure bytes; never reset snapshot time."""
    import psutil
    path=common.canonical(path)
    job=common.strict(job_raw);label=job['unit'][7:-8]
    if (path.parent!=output.parent or re.fullmatch(re.escape(label)+r'-reconcile-[0-9]{2}',path.name) is None
            or path==output or (path/'JOB.json').read_bytes()!=job_raw or not (path/'FAILURE.json').is_file()):
        raise ValueError('Exact same-JOB failed prior attempt required')
    owner=common.strict((path/'REGISTERED_OWNER.json').read_bytes())
    if psutil.pid_exists(owner['pid']):
        process=psutil.Process(owner['pid'])
        if process.create_time()==owner['create_time'] and process.is_running():
            raise ValueError('Prior host reconciler is still owned')
    entries=list(path.iterdir());total=0;phases=0
    if len(entries)>128:raise ValueError('Bounded pre-transfer prior attempt required')
    for entry in entries:
        if entry.is_symlink():raise ValueError('Prior preparation symlink')
        if entry.is_file():
            if entry.stat().st_nlink!=1 or entry.stat().st_size>2*1024**2:raise ValueError('Prior receipt cap')
            total+=entry.stat().st_size
        elif entry.is_dir() and re.fullmatch(r'snapshot-[0-9]{4}',entry.name):
            children=list(entry.iterdir());phases+=1
            if len(children)>8 or any(child.is_symlink() or not child.is_file() or child.stat().st_nlink!=1 for child in children):
                raise ValueError('Prior phase membership')
            count=sum(child.stat().st_size for child in children)
            if count>PHASE_BYTES:raise ValueError('Prior phase cap')
            total+=count
        else:raise ValueError('Resume accepts only pre-transfer failure, no payload/guard mirror')
    if total+FINAL_RECEIPT_RESERVE>=PREPARATION_BYTES:raise ValueError('Prior preparation allocation exhausted')
    return dict(path=str(path),bytes=total,phases=phases,job_sha256=hashlib.sha256(job_raw).hexdigest(),
        original_deadline_unix=job['deadline_unix'],old_output_preserved=True,
        utility_closure_gap_preserved=True,prior_utility_closure_reconstructed=False)


def transfer_plan(rows, plan):
    if len(rows) != len(plan): raise ValueError('Exact seed plan required')
    phases = 0; missing_bytes = 0
    for row, selected in zip(rows, plan):
        if row['path'] != selected['path']: raise ValueError('Seed plan ordering changed')
        if selected['seed']: continue
        size = row['identity']['bytes']
        if type(size) is not int or size < 0: raise ValueError('Source extent required')
        phases += max(1, (size + SEGMENT_BYTES - 1) // SEGMENT_BYTES)
        missing_bytes += size
    if phases + 3 > 8192: raise ValueError('Finite exact segment phase count exhausted')
    return dict(segment_bytes=SEGMENT_BYTES, transfer_phases=phases, missing_transfer_bytes=missing_bytes,
        preparation_bytes=PREPARATION_BYTES, maximum_phase_receipt_bytes=PHASE_BYTES,
        final_receipt_reserve_bytes=FINAL_RECEIPT_RESERVE)


def snapshot_matches(status, job, census_sha=None):
    return bool(status and status.get('snapshot_locked') is True and status.get('closed') is False
        and status.get('observed_owner') == job['owner']
        and all(status.get(key) == job[key] for key in ('owner','unit','invocation_id','control_group'))
        and (census_sha is None or status.get('census_sha256') == census_sha))


def receiver_types(monitor, common):
    class SnapshotSegment(monitor.SegmentReceiver):
        def __init__(self, *args, job, census_sha, **kwargs):
            super().__init__(*args, **kwargs); self.job=job; self.census_sha=census_sha
        def _permit_segment(self,status):
            return snapshot_matches(status,self.job,self.census_sha)
        def _permit_end(self,row):
            return snapshot_matches(row.get('snapshot'),self.job,self.census_sha)

    class CensusReceiver(monitor.Receiver):
        def __init__(self,*args,job,finalize=False,**kwargs):
            super().__init__(*args,**kwargs);self.job=job;self.census=None;self.finished=False;self.finalize=finalize;self.wire_bytes=0
        def feed(self,row):
            kind=row.get('kind')
            if kind in ('OWNER','UTILITY','STATUS'):return super().feed(row)
            if not snapshot_matches(self.status,self.job):raise ValueError('Exact active snapshot required')
            if kind=='CENSUS_BEGIN':
                if self.census is not None or self.finalize:raise ValueError('Unexpected census start')
                self.census=dict(schema=row['schema'],scope=row['scope'],bytes=row['bytes'],
                    files=[],directories=[],external_assets=[])
                common.validate_spec(self.census['scope'])
                self.wire_bytes=len(common.encoded(self.census))
            elif kind in ('CENSUS_FILE','CENSUS_DIRECTORY','CENSUS_ASSET'):
                if self.census is None or self.finished:raise ValueError('Census framing')
                key={'CENSUS_FILE':'files','CENSUS_DIRECTORY':'directories','CENSUS_ASSET':'external_assets'}[kind]
                if len(self.census[key]) >= (128 if key=='external_assets' else common.MAX_FILES):
                    raise ValueError('Census membership bound')
                self.census[key].append(row['value'])
                self.wire_bytes+=len(common.encoded(row['value']))+1
                if self.wire_bytes>common.MAX_CENSUS:raise ValueError('Census allocation bound')
            elif kind=='CENSUS_END':
                if (not self.census or self.finished or not snapshot_matches(row['snapshot'],self.job,row['census_sha256'])
                    or hashlib.sha256(common.encoded(self.census)).hexdigest()!=row['census_sha256']
                    or row['census_sha256']!=self.status['census_sha256']):raise ValueError('Complete exact census required')
                self.finished=True
            elif kind=='FINALIZE_ACCEPTED':
                if (not self.finalize or self.finished or row['owner']!=self.job['owner']
                    or row['invocation_id']!=self.job['invocation_id']
                    or row['census_sha256']!=self.status['census_sha256']):raise ValueError('Exact finalize acknowledgement required')
                self.finished=True
            else:raise ValueError('Unexpected snapshot protocol frame')
    return SnapshotSegment,CensusReceiver


def run_snapshot(monitor,common,source,base_request,receiver,directory,extra):
    directory.mkdir()
    receiver.owner_path=directory/'NATIVE_OWNER.json'
    payload=common.encoded(dict(base_request,**extra))
    if len(payload)>65536:raise ValueError('Snapshot request cap')
    bootstrap="import base64;exec(compile(base64.b64decode('"+base64.b64encode(source).decode()+"'),'<owned-backup-probe>','exec'))"
    command=monitor.SSH+['exec '+shlex.join(['python3','-B','-c',bootstrap])]
    try:
        receipt=monitor.phase(command,payload,receiver,5*1024**2)
        if receiver.owner is None:raise ValueError('Native early owner missing')
        # Reuse the monitor's conservative PID-absence check after natural exec.
        # A reused PID fails; no arbitrary native PID is ever signalled.
        check=subprocess.Popen(monitor.SSH+['exec /usr/bin/test ! -e /proc/'+str(receiver.owner['pid'])],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        creation=monitor.process_creation(int(check._handle))
        try:out,err=check.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            check.kill();check.communicate(timeout=5);raise RuntimeError('Backup helper absence check timed out')
        if check.returncode or out or len(err)>4096:raise RuntimeError('Backup helper did not prove absent')
        publish_phase(common,directory/'SSH_CLOSURE.json',dict(receipt,utility_pid_absent_after_ssh=True,
            utilities=receiver.utilities,absence_check=dict(pid=check.pid,creation_filetime=creation,
                returncode=check.returncode,naturally_reaped=True)))
        publish_phase(common,directory/'STATUS.json',receiver.status)
        if hasattr(receiver,'segment_complete'):
            if receiver.segment_complete is None:raise ValueError('Missing snapshot segment completion')
            publish_phase(common,directory/'SEGMENT_COMPLETE.json',receiver.segment_complete)
        elif extra['mode']!='ready' and not receiver.finished:raise ValueError('Missing complete census/finalization acknowledgement')
        return receiver
    except BaseException as exc:
        publish_phase(common,directory/'FAILURE.json',dict(error=repr(exc),ssh=getattr(exc,'receipt',None),
            early_native_owner=receiver.owner,certified=False));raise


def complete_backup(common,payload_root,census,source_verified,closure):
    """No COMPLETE is possible from copy success alone; bind native final rehash."""
    digest=hashlib.sha256(common.encoded(census)).hexdigest()
    if (source_verified.get('census_sha256')!=digest or
        any(source_verified.get(key) is not True for key in ('membership_before_after_equal',
            'hashes_before_after_equal','external_asset_pins_equal','locks_held_during_verification')) or
        any(closure.get(key) is not True for key in ('closed','exact_owner_gone','cgroup_empty')) or
        source_verified.get('owner')!=closure.get('owner') or
        source_verified.get('invocation_id')!=closure.get('invocation_id') or
        closure.get('job_exit',{}).get('natural_returncode')!=0 or closure.get('job_exit',{}).get('error')):
        raise ValueError('Actual final source rehash and natural exact owner/cgroup closure required')
    checked=common.verify_payload(payload_root,census['files'])
    return dict(checked,kind='COMPLETE',mirror_scope='all_regular_output_files',closure=closure,
        backup_scope='selected-release-and-user-data',census_sha256=digest,
        source_before_after_verified=True,external_asset_pins_verified=True,
        restoration_directories=census['directories'],source_deleted=False)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--job',type=Path,required=True)
    ap.add_argument('--package-copy',type=Path,required=True,help='Exact independently verified PC copy of admitted package')
    ap.add_argument('--seeds',type=Path,required=True,help='JSON list of explicit destination/local prefix mappings')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--prior-output',type=Path,help='One failed pre-transfer attempt, charged to the same16MiB allocation')
    args=ap.parse_args()
    import psutil
    me=psutil.Process();me.cpu_affinity([14])
    output=args.output.absolute()
    private=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    if (output.parent!=private or output.parent.resolve(strict=True)!=output.parent
        or re.fullmatch(r'production-backup-\d{2}-reconcile-\d{2}',output.name) is None):
        raise ValueError('Fresh canonical private CPU14 output required')
    output.mkdir()
    owner=json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14]),sort_keys=True).encode()
    with (output/'REGISTERED_OWNER.json').open('xb') as stream:
        stream.write(owner);stream.flush();os.fsync(stream.fileno())
    if (output/'REGISTERED_OWNER.json').read_bytes()!=owner:raise OSError('Early owner readback')
    budget=PreparationBudget(output)
    # No project/data imports or reads occur before the actual receipt above.
    import backup_external_common_v2 as common
    from backup_external_protocol_v2 import native_probe_overlay, COMMON_SHA256, SCHEMA
    import monitor_native_job as monitor
    job_raw=args.job.read_bytes()
    if len(job_raw)>65536:raise ValueError('Bounded actual job required')
    job=monitor.validate_job(common.strict(job_raw))
    if not job['output_root'].endswith('/'+job['unit'][7:-8]) or 'production-backup-' not in job['unit']:
        raise ValueError('Explicit production backup guard job required')
    if job.get('external_backup_common_sha256')!=COMMON_SHA256 or job.get('external_backup_schema')!=SCHEMA:
        raise ValueError('Exact external backup job required')
    reserved=job['full_backup_reservation_bytes']
    if type(reserved) is not int or not 0<reserved<2**63:raise ValueError('Explicit full PC backup allocation required')
    prior=prior_attempt_usage(common,args.prior_output,job_raw,output) if args.prior_output else dict(bytes=0,phases=0)
    budget.used+=prior['bytes'];budget.require(0)
    budget.write(output/'PRIOR_ATTEMPT.json',common.encoded(prior))
    monitor.floors(reserved+2*job['maximum_output_bytes']+16*1024**2)
    budget.write(output/'PC_RESERVATION.json',common.encoded(dict(full_payload_bytes=reserved,
        native_output_mirror_bytes=2*job['maximum_output_bytes'],separate_preparation_bytes=16*1024**2,
        c_floor_bytes=50*1024**3,g_floor_bytes=75*1024**3,ssh_started=False)))
    package=common.canonical(args.package_copy)
    manifest_raw=(package/'PACKAGE_MANIFEST.json').read_bytes()
    if len(manifest_raw)>262144 or hashlib.sha256(manifest_raw).hexdigest()!=job['package_manifest_sha256']:
        raise ValueError('Exact admitted package copy required')
    manifest=common.strict(manifest_raw)
    required=('native_backup_probe.py','native_job_probe.py','backup_reconciliation.py')
    pins={}
    for name in required:
        entry=next(row for row in manifest['files'] if row['path']==name)
        value,sha=common.digest(package/name)
        if value['bytes']!=entry['bytes'] or sha!=entry['sha256']:raise ValueError('Package helper pin differs')
        pins[name]=sha
    native_source=native_probe_overlay((package/'native_backup_probe.py').read_text())
    monitor_source=(package/'native_job_probe.py').read_bytes()
    base=dict(job=job,package=manifest['target'],native_job_probe_sha256=pins['native_job_probe.py'],
        backup_reconciliation_sha256=COMMON_SHA256)
    budget.write(output/'JOB.json',job_raw)
    for name in required:
        raw=(package/name).read_bytes()
        budget.write(output/(name+'.backup'),raw);budget.write(output/(name+'.restore'),raw)
    external_raw=Path(common.__file__).read_bytes()
    if hashlib.sha256(external_raw).hexdigest()!=COMMON_SHA256:raise ValueError('Local reviewed external common changed')
    budget.write(output/'EXTERNAL_COMMON.py.backup',external_raw);budget.write(output/'EXTERNAL_COMMON.py.restore',external_raw)
    budget.write(output/'EXTERNAL_NATIVE_PROBE.py.backup',native_source);budget.write(output/'EXTERNAL_NATIVE_PROBE.py.restore',native_source)
    Segment,Catalog=receiver_types(monitor,common)
    counter=prior['phases'];protocol_bytes=0
    def probe(receiver,extra):
        nonlocal counter,protocol_bytes
        if time.time()>=job['deadline_unix']-30:raise TimeoutError('Admitted snapshot lifetime exhausted')
        counter+=1
        if counter>8192:raise ValueError('Bounded snapshot transfer phases exhausted')
        budget.require(PHASE_BYTES)
        directory=output/('snapshot-'+str(counter).zfill(4))
        try:return run_snapshot(monitor,common,native_source,base,receiver,directory,extra)
        finally:
            budget.charge_phase(directory)
            protocol_bytes=budget.used
    try:
        for attempt in range(720):
            ready=probe(monitor.Receiver(output,16384),dict(mode='ready'))
            if ready.status.get('snapshot_ready') is True:break
            time.sleep(5)
        else:raise TimeoutError('Finite snapshot census readiness wait exhausted')
        result=probe(Catalog(output,2*1024**2,job=job),dict(mode='catalog'))
        census=result.census;scope=census['scope'];census_sha=result.status['census_sha256']
        if (scope['maximum_payload_bytes']!=reserved or
            hashlib.sha256(common.encoded(scope)).hexdigest()!=job['backup_scope_sha256']):
            raise ValueError('Live scope differs from independently reserved job allocation')
        monitor.floors(scope['maximum_payload_bytes']+2*job['maximum_output_bytes']+16*1024**2)
        budget.write(output/'CENSUS.json',common.encoded(census))
        seeds_raw=args.seeds.read_bytes()
        if len(seeds_raw)>65536:raise ValueError('Bounded explicit PC seed mappings required')
        plan=common.seed_plan(census['files'],common.strict(seeds_raw))
        plan_raw=common.encoded(dict(files=plan,
            full_payload_bytes=census['bytes'],reused_bytes=sum(row['bytes'] for row in plan if row['seed']),
            missing_transfer_bytes=sum(row['bytes'] for row in plan if not row['seed'])))
        if len(plan_raw)>2*1024**2:raise ValueError('Reconciliation plan exceeds2MiB preparation partition')
        budget.write(output/'RECONCILIATION.json',plan_raw)
        target=output/'payload';target.mkdir()
        for row in census['directories']:
            target.joinpath(*common.relative(row['path']).parts).mkdir(parents=True,exist_ok=True)
        exact_plan=transfer_plan(census['files'],plan)
        if counter+exact_plan['transfer_phases']+1>8192:
            raise ValueError('Readiness probes consumed the exact remaining phase allowance')
        exact_plan.update(preparation_used_bytes=budget.used, preparation_available_bytes=PREPARATION_BYTES-budget.used-budget.held)
        budget.write(output/'TRANSFER_PLAN.json',common.encoded(exact_plan))
        chunk=SEGMENT_BYTES
        for row,planned in zip(census['files'],plan):
            monitor.floors()
            if planned['seed']:
                common.copy_seed(planned['seed'],target/row['path'],row);continue
            offset=0;size=row['identity']['bytes']
            while offset<size or offset==0 and size==0:
                count=min(chunk,size-offset)
                probe(Segment(target,scope['maximum_payload_bytes'],row,offset,count,job=job,census_sha=census_sha),
                    dict(mode='segment',entry=row,offset=offset,count=count,census_sha256=census_sha))
                offset+=count  # Exact reviewed1MiB plan; no adaptive state.
                if not size:break
        common.verify_payload(target,census['files'])
        probe(Catalog(output,16384,job=job,finalize=True),dict(mode='finalize',census_sha256=census_sha))
        # Only ordinary existing monitor code can prove actual guard/unit closure.
        mirror=output/'guard-monitor';mirror.mkdir();index=0
        while time.time()<job['deadline_unix']+60:
            status=monitor.run_probe(monitor_source,job,'status',mirror,index);index+=1
            if status['closed']:break
            time.sleep(5)
        else:raise TimeoutError('Snapshot guard failed exact closure')
        monitor.segmented_mirror(monitor_source,job,mirror,index,time.time()+600)
        monitor.save(mirror/'RESULT.json',dict(status='FULL_CLOSED_OUTPUT_MIRRORED',job=job,
            copied_root=str(mirror/'closed-output'),mirror_scope='all_regular_output_files',native_actions=False))
        closed=common.strict((mirror/'MIRROR_COMPLETE.json').read_bytes())['closure']
        actual_census=(mirror/'closed-output/CENSUS.json').read_bytes()
        if actual_census!=common.encoded(census):raise ValueError('Closed guard census differs from copied snapshot')
        final=common.strict((mirror/'closed-output/SOURCE_VERIFIED.json').read_bytes())
        completed=complete_backup(common,target,census,final,closed)
        if len(common.encoded(completed))>2*1024**2:raise ValueError('Full backup completion exceeds builder receipt bound')
        budget.held=0
        budget.write(output/'MANIFEST.json',common.encoded(census['files']))
        budget.write(output/'COMPLETE.json',common.encoded(completed))
        full_backup=dict(scope='selected-release-and-user-data',root=str(target),
            manifest_path=str(output/'MANIFEST.json'),manifest_sha256=hashlib.sha256(common.encoded(census['files'])).hexdigest(),
            completion_path=str(output/'COMPLETE.json'),completion_sha256=hashlib.sha256(common.encoded(completed)).hexdigest())
        budget.write(output/'FULL_BACKUP.json',common.encoded(full_backup))
        budget.write(output/'RESULT.json',common.encoded(dict(status='VERIFIED_CURRENT_RELEASE_BACKUP',
            full_backup=full_backup,source_preserved=True,desktop_changed=False)))
        print(json.dumps(dict(status='VERIFIED_CURRENT_RELEASE_BACKUP',output=str(output))))
    except BaseException as exc:
        budget.write(output/'FAILURE.json',common.encoded(dict(error=repr(exc),certified=False,
            guard_not_signalled=True,finite_guard_timeout_retained=True)));raise


if __name__=='__main__':main()
