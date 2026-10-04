"""Prepare one exact output-admission-only source derivative. See README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import os,json,uuid,hashlib,ast
from pathlib import Path
Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
owner=Q/('presets-preparation-optional-allocation09-'+uuid.uuid4().hex);owner.mkdir()
with (owner/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(pid=os.getpid(),create_time=psutil.Process().create_time(),affinity=[14]),stream)
    stream.flush();os.fsync(stream.fileno())
frozen=Q/'audit-preparation/package-preparation-2ff19e509d254293a8010369339661cf/package'
if hashlib.sha256((frozen/'PACKAGE_MANIFEST.json').read_bytes()).hexdigest()!='2ec99c80d5d070c30a1b4a7959be1a9e552d5fc7688fe703ab9ad650891ee841':
    raise ValueError('Exact frozen08 source manifest required')
source=frozen/'optional_refiner_qualification.py';raw=source.read_bytes()
manifest=json.loads((frozen/'PACKAGE_MANIFEST.json').read_bytes())
entry=next(row for row in manifest['files'] if row['path']=='optional_refiner_qualification.py')
if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Exact frozen08 source module required')
text=raw.decode('utf-8').replace('\r\n','\n')
addition='''def qualification_output_plan(binding,selection,policy,stage):
    """Complete finite physical output reservation, separate from process AS."""
    if stage not in ('initial','followup_policy'):
        raise ValueError('Explicit qualification allocation stage required')
    from storage import StoragePolicy
    disk=StoragePolicy(**binding.get('storage_policy',{}))
    metadata=16*MIB+policy.maximum_session_seconds*256*1024
    spec=dict(duration_seconds=policy.maximum_session_seconds,sample_rate=16000,
              mode='processed',metadata_reserve_bytes=metadata)
    if binding.get('raw_adapter_enabled') is True and selection.input_source=='live':
        # Allocation only. The unchanged worker independently verifies its exact
        # raw proof before opening a physical source or accepting samples.
        spec.update(mode='raw_processed',raw=dict(sample_rate=16000,channels=4,
            sample_width_bytes=4,encoding='PCM_S32LE',
            qualification=dict(qualified=True,evidence='allocation only; worker verifies actual receipt')))
    audio_metadata=disk.estimate_bytes(spec)
    primary_extra=metadata+disk.metadata_allowance_bytes+10*MIB
    optional_bytes=4*MIB
    unit_trace_bytes=16*MIB
    complete=audio_metadata+primary_extra+optional_bytes+unit_trace_bytes
    maximum=256*MIB if stage=='initial' else max(256*MIB,complete)
    if complete>maximum or maximum>512*MIB:
        raise ValueError('Complete qualification output exceeds exact finite stage allocation')
    return dict(schema='just-peachy.optional-output-plan.v1',stage=stage,
        source_kind=selection.input_source,session_seconds=policy.maximum_session_seconds,
        mode=spec['mode'],audio_and_metadata_bytes=audio_metadata,
        additional_primary_allocation_bytes=primary_extra,optional_output_bytes=optional_bytes,
        outer_unit_trace_bytes=unit_trace_bytes,computed_output_bytes=complete,
        native_maximum_output_bytes=maximum,maximum_files=256)


'''
anchor='def initialize(request,binding,owner_directory,identity,authorization):\n'
if text.count(anchor)!=1:raise ValueError('Exact source insertion boundary changed')
text=text.replace(anchor,addition+anchor)
before="""    if (allocation.get('schema')!='just-peachy.optional-first-allocation.v1' or allocation.get('job_root')!=str(job) or
        allocation.get('native_maximum_output_bytes')!=256*MIB or
        type(allocation.get('independent_backup_reserved_bytes')) is not int or allocation['independent_backup_reserved_bytes']<256*MIB or
        allocation.get('free_space_floor_bytes')!=5*1024**3):
        raise ValueError('Explicit native256MiB and independent mirror reservation required')
    import shutil
    if shutil.disk_usage(job).free<256*MIB+5*1024**3:raise OSError('Actual free-space floor unavailable')
"""
after="""    output_plan=qualification_output_plan(binding,selection,policy,row['stage'])
    output_bytes=output_plan['native_maximum_output_bytes']
    if (allocation.get('schema')!='just-peachy.optional-first-allocation.v1' or allocation.get('job_root')!=str(job) or
        allocation.get('native_maximum_output_bytes')!=output_bytes or allocation.get('output_plan')!=output_plan or
        type(allocation.get('independent_backup_reserved_bytes')) is not int or allocation['independent_backup_reserved_bytes']<output_bytes or
        allocation.get('free_space_floor_bytes')!=5*1024**3):
        raise ValueError('Exact complete stage-specific native and independent mirror reservations required')
    import shutil
    if shutil.disk_usage(job).free<output_bytes+5*1024**3:raise OSError('Actual free-space floor unavailable')
"""
if text.count(before)!=1:raise ValueError('Exact fixed allocation guard changed')
text=text.replace(before,after);ast.parse(text)
new=text.replace('\n','\r\n').encode('utf-8')
destination=Path(__file__).parent/'runtime_derivative09';destination.mkdir()
with (destination/'optional_refiner_qualification.py').open('xb') as stream:
    stream.write(new);stream.flush();os.fsync(stream.fileno())
receipt=dict(source_path=str(source),source_sha256=hashlib.sha256(raw).hexdigest(),
    replacement_path=str(destination/'optional_refiner_qualification.py'),replacement_sha256=hashlib.sha256(new).hexdigest(),
    changes=['add pure stage-specific output calculation','replace fixed256MiB allocation guard with exact calculated plan'],
    model_constructor_changes=False,native_execution=False)
with (owner/'SOURCE_DIFFERENCE.json').open('x') as stream:json.dump(receipt,stream,indent=2)
print(json.dumps(receipt));print(owner)
