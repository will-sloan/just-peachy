"""Native broker qualification component; README_FIELD_OPERATOR_BROKER_QUALIFICATION_V1.md."""
import base64
import copy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid
from field_operator_session_plan_v3 import rebase,encoded
from field_operator_session_ledger_v4 import read,file_pin,identity,ticks
from field_operator_layout_v2 import specification,encoded as layout_encoded
from field_operator_entry_v8 import sink,available_ram,capture_closed

def stage(broker,root):
    """Runs in the acknowledged broker process before any recording parent."""
    ledger=broker.ledger;ledger._live();root=Path(root)
    from field_operator_broker_common_v1 import bundle,physical
    _,config,_=bundle(ledger.root);physical(config)
    if root!=ledger.root/'recordings'/broker.current or root.exists() or root.is_symlink():
        raise ValueError('One fresh reserved root; no retry')
    records=ledger.records()[broker.current]
    if set(records)!={'RESERVED'} or records['RESERVED']['broker_owner']!=identity():
        raise ValueError('Exact live broker reservation')
    ack=read(ledger.root/'broker/ACK.json')
    if ack['owner']!=identity() or ticks(ack['gate_owner']['pid'])!=ack['gate_owner']['start_ticks']:
        raise RuntimeError('Acknowledged outer resource owner required')
    expiry=datetime.fromisoformat(ledger.policy['expires_utc'])
    if (expiry-datetime.now(timezone.utc)).total_seconds()<365:
        raise RuntimeError('Full300s child,60s cleanup and staging reserve do not fit')
    if not capture_closed() or available_ram()<850*1024**2 or shutil.disk_usage(root.parent).free<5*1024**3+146919980:
        raise RuntimeError('Capture/RAM/full next recording free floor')
    template=read(ledger.root/'broker/TEMPLATE.json',128*1024)
    if set(template)!={'schema','source_root','admission','code_names','data_files'} or template['schema']!='just-peachy.broker-child-template.v1':
        raise ValueError('Exact pre-reviewed child template')
    a=rebase(copy.deepcopy(template['admission']),template['source_root'],str(root))
    from field_operator_qualification_v3 import CONTRACT
    a['qualification']=dict(CONTRACT)
    a.update(created_utc=datetime.now(timezone.utc).isoformat(),expires_utc=ledger.policy['expires_utc'],
        output_root=str(root),session_broker=dict(root=str(ledger.root),owner=identity(),
        policy_sha256=file_pin(ledger.root/'RELEASE.json')['sha256'],slot=broker.current),
        resource_policy=dict(path=str(ledger.root/'RELEASE.json'),sha256=file_pin(ledger.root/'RELEASE.json')['sha256']),
        transfer=dict(import_token=uuid.uuid4().hex))
    decoded={}
    for name in template['code_names']:
        if type(name) is not str or Path(name).name!=name:raise ValueError('Exact capsule basename')
        p=ledger.root/'code'/name;raw=p.read_bytes()
        if not 0<len(raw)<=128*1024:raise ValueError('Capsule member cap')
        decoded['code/'+name]=raw
    if set(template['data_files'])!={'live_config.json','settings.json','DATA_SCHEMA.json','n2_runtime.json'}:
        raise ValueError('Actual four configuration members')
    for name,value in template['data_files'].items():
        decoded['data/'+name]=encoded(rebase(value,template['source_root'],str(root)))
    if len(decoded)>64 or sum(map(len,decoded.values()))>2*1024**2:raise ValueError('Original capsule guard')
    a['files']=[r for r in a['files'] if not r['path'].startswith(str(root)+'/') and not r['path'].endswith('/OPERATOR_RESOURCE_POLICY_V4.json')]
    a['files'] += [dict(path=str(root/name),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for name,raw in decoded.items()]
    a['files'].append(dict(path=str(ledger.root/'RELEASE.json'),**file_pin(ledger.root/'RELEASE.json')))
    if len({r['path'] for r in a['files']})!=len(a['files']):raise ValueError('Duplicate input pin')
    for row in a['files']:
        if row['path'].startswith(str(root)+'/'):continue
        if file_pin(row['path'])!=dict(bytes=row['bytes'],sha256=row['sha256']):raise ValueError('External input drift')
    layout=specification();layout_raw=layout_encoded(layout)
    for key in ('target_maximum_bytes','host_maximum_bytes','combined_request_bytes'):
        if a[key]!=layout[key] or type(a[key]) is not int:raise ValueError('Independent child allocation')
    if a['layout_sha256']!=hashlib.sha256(layout_raw).hexdigest():raise ValueError('Child layout drift')
    raw_admission=encoded(a)
    if len(raw_admission)>65536:raise ValueError('Original admission guard')
    def publish(path,raw,maximum):
        ledger._live()
        if not isinstance(raw,bytes) or len(raw)>maximum:raise ValueError('Staging physical slot')
        with path.open('xb') as f:
            for offset in range(0,len(raw),16384):
                block=raw[offset:offset+16384]
                if f.write(block)!=len(block):raise OSError('Stager short write')
            f.flush();os.fsync(f.fileno())
        if path.read_bytes()!=raw:raise IOError('Stager readback')
    root.mkdir()
    for name in layout['directories']:
        if name and '<' not in name:(root/name).mkdir(parents=True,exist_ok=True)
    publish(root/'control/MANIFEST.json',encoded(dict(stage_owner=identity(),
        files=[dict(path=n,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in decoded.items()])),65536)
    for name,raw in decoded.items():publish(root/name,raw,131072 if name.startswith('code/') else 65536)
    publish(root/'control/LAYOUT.json',layout_raw,65536)
    publish(root/'control/ADMISSION.json',raw_admission,65536)
    issued=time.monotonic_ns()
    deadline=dict(schema='just-peachy.absolute-child-deadline.v1',boot_id=a['boot_id'],issued_ns=issued,
        soft_ns=issued+270000000000,hard_ns=issued+300000000000,grace_ns=30000000000)
    cfg=dict(schema='just-peachy.live-source.v1',capture=True,quiet_only=True,output_root=str(root),
        prototype=a['installed_release'],authority=str(root/'code/AUTONOMOUS_QUIET_AUTHORIZATION_V1.json'),
        alsa_config=a['installed_release']+'/config/alsa_hw_only_v1.conf',live_config=str(root/'data/live_config.json'),
        case_directory=str(root/'source'),admission_path=str(root/'control/ADMISSION.json'),
        admission_sha256=hashlib.sha256(raw_admission).hexdigest(),layout_path=str(root/'control/LAYOUT.json'),
        layout_sha256=a['layout_sha256'],deadline=deadline,source_module='field_live_source_factory_v6',
        source_factory='create',backpressure_seconds=1)
    publish(root/'config/CONFIG.json',encoded(cfg),65536)
    for name in ('data/conversations','data/.archive-imports','conversation_exports','data/sessions','data/people'):
        p=root/name
        if not p.is_dir() or any(p.iterdir()):raise ValueError('Fresh empty actual data path')
    sink(root,'receipts').json('DEPENDENCY_BINDING.json',dict(scope='Fresh broker-owned live recording; no archive copied',
        admitted_files=len(a['files']),initial_capture_closed=True,source_factory='field_live_source_factory_v6'))
    sink(root,'closure').json('stage.json',dict(owner=identity(),work_complete=True,readback_exact=True,
        files=len(decoded),bytes=sum(map(len,decoded.values())),baseline_changed=False,in_process_broker_stage=True))
    return root
