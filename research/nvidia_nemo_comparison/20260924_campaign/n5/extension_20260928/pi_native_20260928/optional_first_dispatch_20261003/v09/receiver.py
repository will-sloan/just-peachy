"""Exact owned09 worker receiver; no alternate model/runtime. See README.md."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import threading
import time
import uuid


class OutputRouter:
    """Bounded existing GUI channel, without changing model callback behavior."""
    def __init__(self,stream,forward,decoder_factory,limit=4*1024**2):
        self.stream,self.forward,self.limit=stream,forward,limit
        self.count=0
        self.decoder=decoder_factory(self.record,self.forward,self.record)
    def record(self,value):
        raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
        if len(raw)>4096 or self.count+len(raw)>self.limit:raise RuntimeError('Finite worker telemetry allocation exhausted')
        if self.stream.write(raw)!=len(raw):raise OSError('Short worker telemetry write')
        self.count+=len(raw)
    def feed(self,raw):self.decoder.feed(raw)
    def finish(self):self.decoder.finish();self.stream.flush()


def execute_worker(argv,job):
    # The worker is normally a Manager child whose fd1 channel is drained by
    # Manager. Here it is the wrapper main PID; retain that same channel behavior
    # externally so health records do not consume the C-diagnostic allowance.
    from runtime_ui_channel import StreamDecoder
    import signal
    saved_stdout=os.dup(1);read_fd,write_fd=os.pipe();os.dup2(write_fd,1);os.close(write_fd)
    failures=[]
    def forward(raw):
        while raw:
            count=os.write(saved_stdout,raw)
            if count<=0:raise OSError('Short forwarded native diagnostic')
            raw=raw[count:]
    def drain():
        try:
            with (job/'WORKER_STATUS.jsonl').open('xb') as stream:
                router=OutputRouter(stream,forward,StreamDecoder)
                while True:
                    raw=os.read(read_fd,8192)
                    if not raw:break
                    router.feed(raw)
                router.finish();os.fsync(stream.fileno())
        except BaseException as error:
            failures.append(repr(error)[:1024]);os.kill(os.getpid(),signal.SIGTERM)
        finally:os.close(read_fd)
    reader=threading.Thread(target=drain,name='optional-owned-worker-channel',daemon=True);reader.start()
    try:
        sys.argv=argv;runpy.run_path(argv[0],run_name='__main__')
    finally:
        os.dup2(saved_stdout,1)
        reader.join(3)
        if reader.is_alive():raise RuntimeError('Owned worker channel reader did not close')
        os.close(saved_stdout)
        if failures:raise RuntimeError('Worker channel failed: '+failures[0])


def main():
    job=Path(sys.argv[1]);intent=json.loads((job/'INTENT.json').read_bytes());package=Path(intent['package'])
    sys.path.insert(0,str(package))
    from optional_refiner_qualification import encoded,digest,launch_context_sha256
    from optional_refiner_admission import operational_binding_sha256
    from release_authorization import selected_inventory_sha256
    from profiles import RuntimeSelection,SessionPolicy
    binding=json.loads((package/'BINDING.json').read_bytes());unit=json.loads((job/'UNIT_OWNERSHIP.json').read_bytes())
    owner=json.loads((job/'OWNER.json').read_bytes())
    actual=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    if owner!=actual or unit['owner']!=owner or unit['main_pid']!=owner['pid']:raise ValueError('Exact wrapper main PID required')
    derivation=json.loads((job/'WRAPPER_DERIVATION.json').read_bytes())
    if derivation['derived_wrapper_sha256']!=digest(job/'wrapper.py'):raise ValueError('Wrapper pin changed')
    selection=RuntimeSelection(**intent['selection']);policy=SessionPolicy(**intent['policy'])
    request=dict(selection=selection.validate(),policy=policy.validate(),binding=str(package/'BINDING.json'),
        binding_sha256=digest(package/'BINDING.json'),data_root=str(job/'recordings'),unit=unit['unit'],
        saved_path=intent['source'].get('path'),storage_policy=binding.get('storage_policy',{}),
        orchestration={name+'_sha256':digest(job/file) for name,file in (
            ('receiver','receiver.py'),('intent','INTENT.json'),('wrapper','wrapper.py'),
            ('wrapper_derivation','WRAPPER_DERIVATION.json'),('candidate_review','CANDIDATE_REVIEW.json'))})
    request['orchestration']['dispatcher_sha256']=intent['dispatcher_sha256']
    memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line)
    now=time.time();followup=intent['stage']=='followup_policy'
    permit=dict(schema='just-peachy.optional-first-combined-qualification.v2',stage=intent['stage'],
        purpose='FOLLOWUP_POLICY_MEASUREMENT_ONLY' if followup else 'FIRST_COMBINED_MEASUREMENT_ONLY',
        production_eligible=False,prior_combined_pass_claimed=followup,prior_production_pass_claimed=False,
        base_target=str(package),base_content_sha256=binding['candidate_content_sha256'],
        package_manifest_sha256=intent['package_manifest_sha256'],selection=selection.validate(),policy=policy.validate(),
        pins=dict(candidate_content_sha256=binding['candidate_content_sha256'],installed_manifest_sha256=binding['installed_manifest_sha256'],
            operational_binding_sha256=operational_binding_sha256(binding),
            selected_asset_inventory_sha256=selected_inventory_sha256(binding,selection,intent['assets'])),
        issued_unix=now,expires_unix=min(now+policy.total_deadline_seconds+90,intent['expires_unix']),
        boot_id=owner['boot_id'],unit=unit['unit'],nonce=uuid.uuid4().hex,
        physical_ram_bytes=int(memory['MemTotal'].split()[0])*1024,
        limits=dict(primary_as_bytes=768*1024**2,child_as_bytes=768*1024**2,
            whole_unit_rss_soft_stop_bytes=1024*1024**2,available_ram_floor_bytes=192*1024**2,
            initial_available_ram_bytes=1216*1024**2,child_physical_planning_reserve_bytes=256*1024**2,
            reserved_optional_output_bytes=4*1024**2,maximum_lag_seconds=intent['maximum_lag_seconds']),
        assets=intent['assets'],source=intent['source'],job_root=str(job),
        unit_ownership_path=str(job/'UNIT_OWNERSHIP.json'),unit_ownership_sha256=digest(job/'UNIT_OWNERSHIP.json'),
        allocation_path=str(job/'ALLOCATION.json'),allocation_sha256=digest(job/'ALLOCATION.json'),
        prerequisite_gate_path=str(job/'PREREQUISITES.json'),prerequisite_gate_sha256=digest(job/'PREREQUISITES.json'),
        launch_context_sha256=launch_context_sha256(request))
    if followup:
        permit.update(feasibility_review_path=str(job/'FEASIBILITY_REVIEW.json'),
            feasibility_review_sha256=digest(job/'FEASIBILITY_REVIEW.json'),
            reviewed_feasibility=json.loads((job/'FEASIBILITY_REVIEW.json').read_bytes()))
    for name,value in (('PERMIT.json',permit),):
        with (job/name).open('xb') as stream:stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
    request['optional_refiner_qualification']=dict(path=str(job/'PERMIT.json'),sha256=digest(job/'PERMIT.json'))
    with (job/'REQUEST.json').open('xb') as stream:stream.write(encoded(request));stream.flush();os.fsync(stream.fileno())
    argv=[str(package/'worker.py'),'--request',str(job/'REQUEST.json'),'--owner-directory',str(job/'worker')]
    execute_worker(argv,job)


if __name__=='__main__':main()
