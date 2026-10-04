"""Owned same-process receiver; entered only by pinned service wrapper. See README.md."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time
import uuid


def main():
    # Wrapper has already persisted OWNER before any project import, rehashed the
    # full frozen package and these exact receiver/intent bytes, and checked unit.
    job=Path(sys.argv[1]); intent=json.loads((job/'INTENT.json').read_bytes())
    package=Path(intent['package'])
    sys.path.insert(0,str(package))
    from optional_refiner_qualification import encoded,digest,launch_context_sha256
    from optional_refiner_admission import operational_binding_sha256
    from release_authorization import selected_inventory_sha256
    from profiles import RuntimeSelection,SessionPolicy
    binding=json.loads((package/'BINDING.json').read_bytes())
    unit=json.loads((job/'UNIT_OWNERSHIP.json').read_bytes())
    owner=json.loads((job/'OWNER.json').read_bytes())
    actual=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    if owner!=actual or unit['owner']!=owner or unit['main_pid']!=owner['pid']:
        raise ValueError('Receiver must retain exact wrapper owner/main PID')
    derivation=json.loads((job/'WRAPPER_DERIVATION.json').read_bytes())
    if derivation['derived_wrapper_sha256']!=digest(job/'wrapper.py') or derivation.get('runtime_code_changed') is not False:
        raise ValueError('Actual orchestration wrapper differs from its derivation record')
    selection=RuntimeSelection(**intent['selection']);policy=SessionPolicy(**intent['policy'])
    request=dict(selection=selection.validate(),policy=policy.validate(),binding=str(package/'BINDING.json'),
        binding_sha256=digest(package/'BINDING.json'),data_root=str(job/'recordings'),unit=unit['unit'],
        saved_path=intent['source']['path'],storage_policy=binding.get('storage_policy',{}),
        orchestration=dict(dispatcher_sha256=intent['dispatcher_sha256'],receiver_sha256=digest(job/'receiver.py'),
            intent_sha256=digest(job/'INTENT.json'),wrapper_sha256=digest(job/'wrapper.py'),
            wrapper_derivation_sha256=digest(job/'WRAPPER_DERIVATION.json')))
    memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line)
    now=time.time()
    permit=dict(schema='just-peachy.optional-first-combined-qualification.v2',stage='initial',
        purpose='FIRST_COMBINED_MEASUREMENT_ONLY',production_eligible=False,prior_combined_pass_claimed=False,
        prior_production_pass_claimed=False,base_target=str(package),base_content_sha256=binding['candidate_content_sha256'],
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
    for name,value in (('PERMIT.json',permit),):
        with (job/name).open('xb') as stream:stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
    request['optional_refiner_qualification']=dict(path=str(job/'PERMIT.json'),sha256=digest(job/'PERMIT.json'))
    with (job/'REQUEST.json').open('xb') as stream:stream.write(encoded(request));stream.flush();os.fsync(stream.fileno())
    sys.argv=[str(package/'worker.py'),'--request',str(job/'REQUEST.json'),'--owner-directory',str(job/'worker')]
    # No constructor substitution or alternate runtime. Frozen worker bootstrap
    # records the same PID again before its own imports and pre-model admission.
    runpy.run_path(sys.argv[0],run_name='__main__')


if __name__=='__main__':main()
