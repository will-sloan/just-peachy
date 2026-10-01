"""Derive the offline manual broker capsule; README_FIELD_RUNTIME_CAPSULE_V1.md."""
import ast
import base64
import hashlib
import json

ORIGINAL_SHA='b9d2a1444b6fb7bd1b9c427b1905d6756d81bc11e0e0ac4af85d7665cf93d2c7'
POLICY_SHA='0d41599b96c8ac81b8196c9c13152d3933e0f9b31b160721c070a5ecf275c3f6'
PLAN_SHA='090a479ec43e34446d6a368279bba393f8150cbddc6456cc55aa17ac763b1407'


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def sha(raw):return hashlib.sha256(raw).hexdigest()


def replace_once(source,old,new):
    if source.count(old)!=1:raise ValueError('Exact reviewed source boundary changed: '+old[:80])
    return source.replace(old,new,1)


def replace_function(source,name,replacement):
    nodes=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(nodes)!=1:raise ValueError('Unique function required: '+name)
    node=nodes[0];lines=source.splitlines(keepends=True)
    result=''.join(lines[:node.lineno-1])+replacement.rstrip()+'\n'+''.join(lines[node.end_lineno:])
    before={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    after={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(result).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    if {k:v for k,v in before.items() if k!=name}!={k:v for k,v in after.items() if k!=name}:
        raise ValueError('Unrelated function changed')
    return result


COMMON = '''
def runtime_binding(config):
    from field_runtime_policy_v2 import validate,validate_operation,digest,identity as exact_identity
    binding=config.get('runtime')
    fields={'root','policy_sha256','operation_sha256','slot','manager_owner','launch_slot',
            'manager_unit','slice','settings_sha256','baseline_owners','baseline_expected'}
    if type(binding) is not dict or set(binding)!=fields:
        raise ValueError('Exact runtime supervisor binding')
    root=Path(binding['root'])
    runtime=validate(read(root/'control/RELEASE.json',65536))
    if runtime['manager_root']!=str(root) or file_pin(root/'control/RELEASE.json')['sha256']!=binding['policy_sha256']:
        raise ValueError('Actual immutable runtime policy')
    slot=binding['slot']
    if slot not in runtime['allocation']['recording_slots']:raise ValueError('Allocated runtime slot')
    reserved=read(root/'recordings'/slot/'RESERVED.json',16384)
    if reserved.get('policy_sha256')!=binding['policy_sha256'] or reserved.get('slot')!='recordings/'+slot:
        raise ValueError('Actual manager reservation envelope')
    operation=validate_operation(reserved['operation'],runtime,now=datetime.now(timezone.utc))
    manager=exact_identity(binding['manager_owner'])
    if operation['owner']!=manager or digest(operation)!=binding['operation_sha256']:
        raise ValueError('Current manager operation binding')
    now=identity()
    if manager['boot_id']!=now['boot_id'] or ticks(manager['pid'])!=manager['start_ticks']:
        raise RuntimeError('Current manager process is absent')
    if binding['launch_slot'] not in runtime['allocation']['launch_slots']:raise ValueError('Allocated launch')
    launch=read(root/'launches'/binding['launch_slot']/'OWNER.json',16384)
    if launch.get('owner')!=manager or launch.get('policy_sha256')!=binding['policy_sha256']:
        raise ValueError('Actual durable manager launch owner')
    if (root/'launches'/binding['launch_slot']/'EXIT.json').exists():
        raise RuntimeError('Manager has closed this launch')
    if binding['manager_unit']!='jp-'+root.name+'.service' or binding['slice']!='jpfield'+root.name.replace('-','')+'.slice':
        raise ValueError('Exact shared runtime service and slice')
    if file_pin(Path.home()/'JustPeachy/data/settings.json')['sha256']!=binding['settings_sha256']:
        raise ValueError('Idle startup settings drift')
    owners=binding['baseline_owners']
    if type(owners) is not list or len(owners)!=2 or binding['baseline_expected'] not in ('idle','stopped'):
        raise ValueError('Independently observed prior application lifecycle')
    for old in owners:
        exact_identity(old)
        alive=old['boot_id']==now['boot_id'] and ticks(old['pid'])==old['start_ticks']
        if alive!=(binding['baseline_expected']=='idle'):raise RuntimeError('Baseline lifecycle changed')
    runtime_units(config)
    return runtime,operation,binding


def runtime_units(config):
    import subprocess
    binding=config['runtime']
    command=['systemctl','--user','show',binding['manager_unit'],'-p','MainPID','-p','ActiveState',
             '-p','LimitAS','-p','LimitSTACK','-p','LimitFSIZE','-p','TasksMax','-p','Slice','-p','RuntimeMaxUSec']
    proc=subprocess.run(command,capture_output=True,timeout=5)
    if proc.returncode or len(proc.stdout)>8192 or len(proc.stderr)>4096:raise RuntimeError('Manager service observation failed')
    row=dict(line.split('=',1) for line in proc.stdout.decode().splitlines())
    expected={'MainPID':str(binding['manager_owner']['pid']),'ActiveState':'active',
              'LimitAS':'134217728','LimitSTACK':'1048576','LimitFSIZE':'33554432','TasksMax':'64',
              'Slice':binding['slice'],'RuntimeMaxUSec':'1d'}
    if row!=expected:raise RuntimeError('Actual manager service envelope differs')
    proc=subprocess.run(['systemctl','--user','show',binding['slice'],'-p','CPUQuotaPerSecUSec',
        '-p','TasksMax','-p','AllowedCPUs','-p','ActiveState'],capture_output=True,timeout=5)
    if proc.returncode or len(proc.stdout)>4096 or len(proc.stderr)>4096:raise RuntimeError('Shared slice observation failed')
    row=dict(line.split('=',1) for line in proc.stdout.decode().splitlines())
    if row!={'CPUQuotaPerSecUSec':'2s','TasksMax':'64','AllowedCPUs':'2-3','ActiveState':'active'}:
        raise RuntimeError('Actual combined manager/broker CPU and task budget absent')
    proc=subprocess.run(['systemctl','--user','list-units','--state=active,activating,deactivating',
        '--no-legend','--plain','jp-*'],capture_output=True,timeout=5)
    if proc.returncode or len(proc.stdout)>16384 or len(proc.stderr)>4096:raise RuntimeError('Bounded active unit inventory')
    names={line.split()[0] for line in proc.stdout.decode().splitlines() if line.strip()}
    allowed={binding['manager_unit']}
    reservation=read(Path(binding['root'])/'recordings'/binding['slot']/'RESERVED.json',16384)
    source=Path(reservation['operation']['root']);broker_unit='jp-'+source.name+'.service'
    if broker_unit in names:
        who=read(source/'broker/OWNER.json',16384)
        if who['boot_id']!=identity()['boot_id'] or ticks(who['pid'])!=who['start_ticks']:
            raise RuntimeError('Active broker exact identity missing')
        observation=subprocess.run(['systemctl','--user','show',broker_unit,'-p','MainPID','-p','Slice',
            '-p','ActiveState'],capture_output=True,timeout=5)
        if observation.returncode or len(observation.stdout)>4096 or len(observation.stderr)>4096:
            raise RuntimeError('Owned broker unit observation failed')
        actual=dict(line.split('=',1) for line in observation.stdout.decode().splitlines())
        if actual!={'MainPID':str(who['pid']),'Slice':binding['slice'],'ActiveState':'active'}:
            raise RuntimeError('Unexpected broker service identity or shared slice')
        allowed.add(broker_unit)
    if names!=allowed:
        raise RuntimeError('Unexpected research/runtime unit remains; leave it untouched')
    return row


def runtime_started(root,policy,gate,worker,check):
    config=read(root/'broker/CONFIG.json');binding=config['runtime']
    path=Path(binding['root'])/'recordings'/binding['slot']/'STARTED.json'
    end=time.monotonic()+12
    while not path.exists():
        check()
        if ticks(binding['manager_owner']['pid'])!=binding['manager_owner']['start_ticks']:
            raise RuntimeError('Manager disappeared before actual STARTED')
        if time.monotonic()>=end:raise TimeoutError('Manager durable Start acknowledgment')
        time.sleep(.01)
    row=read(path,16384)
    if (row.get('policy_sha256')!=binding['policy_sha256'] or row.get('slot')!='recordings/'+binding['slot']
            or row.get('owner')!=worker or row.get('gate_owner')!=gate
            or row.get('binding',{}).get('source')!=str(root)
            or row['binding'].get('policy_sha256')!=file_pin(root/'RELEASE.json')['sha256']
            or row.get('unit',{}).get('MainPID')!=str(worker['pid'])
            or row['unit'].get('ActiveState')!='active'):
        raise RuntimeError('Actual durable STARTED must bind broker, gate, unit and policy before ACK')
    return row
'''


def derive(raw_bundle,policy_source,plan_source):
    """Pure source derivation. No files, native imports, policy or admission issued."""
    if type(raw_bundle) is not bytes or len(raw_bundle)>1048576 or sha(raw_bundle)!=ORIGINAL_SHA:
        raise ValueError('Exact backed manual source bundle required')
    if type(policy_source) is not bytes or sha(policy_source)!=POLICY_SHA:
        raise ValueError('Selected backed production policy bytes required')
    if type(plan_source) is not bytes or sha(plan_source)!=PLAN_SHA:
        raise ValueError('Original full independent allocation bytes required')
    value=json.loads(raw_bundle)
    if set(value)!={'manifest','files'}:raise ValueError('Exact original bundle')
    files={name:base64.b64decode(raw,validate=True) for name,raw in value['files'].items()}
    pins={row['path']:row for row in value['manifest']['files']}
    if len(pins)!=len(value['manifest']['files']) or set(pins)!=set(files):raise ValueError('Complete original pins')
    for name,raw in files.items():
        if pins[name]!=dict(path=name,bytes=len(raw),sha256=sha(raw)):raise ValueError('Original byte drift')
    originals=dict(files);changes={}
    def change(name,fn):
        key='code/'+name;old=files[key];new=fn(old.decode()).encode()
        compile(new,key,'exec');files[key]=new
        changes[key]=dict(before_sha256=sha(old),after_sha256=sha(new),bytes=len(new))
    change('field_operator_session_plan_v3.py',lambda s:replace_function(s,'validate_policy',
        "def validate_policy(value, now=None):\n    from field_runtime_policy_v2 import load_broker_policy\n    return load_broker_policy(value,now=now)"))
    def common(s):
        s=replace_once(s,"if owner['boot_id']!=config['baseline']['boot_id'] or ticks(1013)!=569 or ticks(1130)!=607:",
            "runtime_binding(config)\n    if owner['boot_id']!=config['baseline']['boot_id']:")
        return s+COMMON
    change('field_operator_broker_common_v1.py',common)
    def gate(s):
        s=replace_once(s,'from field_operator_broker_common_v1 import bundle,physical,ready',
            'from field_operator_broker_common_v1 import bundle,physical,ready,runtime_units,runtime_started')
        s=replace_once(s,"active=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','--plain','jp-*'],text=True,timeout=10)\n    if active.strip():raise RuntimeError('Healthy research unit remains; leave it untouched')",
            "runtime_units(config)")
        s=replace_once(s,"cmd=['systemd-run','--user','--unit='+unit,",
            "cmd=['systemd-run','--user','--slice='+config['runtime']['slice'],'--unit='+unit,")
        s=replace_once(s,"                    files.json('ACK.json',dict(owner=worker,policy_sha256=policy_sha256,gate_owner=owner));acked=True",
            "                    runtime_started(root,policy,owner,worker,check)\n                    files.json('ACK.json',dict(owner=worker,policy_sha256=policy_sha256,gate_owner=owner));acked=True")
        return s
    change('field_operator_broker_gate_v8.py',gate)
    def outputs(s):
        s=replace_once(s,"    if cfg['capture'] is not True or cfg['quiet_only'] is not True:\n        raise ValueError('Only authorized quiet capture is admitted')",
            "    if cfg['capture'] is not True or cfg['quiet_only'] is not False:\n        raise ValueError('Explicit user-operated production capture required')")
        s=replace_once(s,"    if not now < expiry <= DEADLINE or (expiry-now).total_seconds() > 600:",
            "    from field_runtime_policy_v2 import load_broker_policy\n    broker=admission.get('session_broker',{})\n    policy=load_broker_policy(bounded_json(Path(broker['root'])/'RELEASE.json'),now=now)\n    if (sha(Path(broker['root'])/'RELEASE.json')!=broker.get('policy_sha256')\n            or str(root)!=str(Path(broker['root'])/'recordings'/broker.get('slot',''))\n            or admission['boot_id']!=policy['boot_id'] or admission['expires_utc']!=policy['expires_utc']):\n        raise ValueError('Actual durable runtime operation/source binding')\n    if not now < expiry or (expiry-now).total_seconds() > 600:")
        s=replace_once(s,"    if authority['scheduled_quiet_capture_authorized'] is not True or authority['quiet_audio_retention_authorized'] is not True:\n        raise ValueError('Quiet source authority missing')",
            "    expected_authority=dict(schema='just-peachy.user-runtime-authority.v1',explicit_start_required=True,\n        recording_authorized=True,local_audio_retention=True,automatic_capture=False,playback=False,enrollment=False)\n    if authority!=expected_authority:raise ValueError('Explicit user runtime recording authority required')")
        return s
    change('field_live_source_outputs_v6.py',outputs)
    change('field_operator_broker_stage_v5.py',lambda s:replace_once(replace_once(s,'capture=True,quiet_only=True','capture=True,quiet_only=False'),
        "authority=str(root/'code/AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')","authority=str(root/'code/OFFLINE_RUNTIME_AUTHORITY_V1.json')"))
    old_authority='code/AUTONOMOUS_QUIET_AUTHORIZATION_V1.json'
    if old_authority not in files:raise ValueError('Expected historical authority member')
    del files[old_authority]
    files['code/OFFLINE_RUNTIME_AUTHORITY_V1.json']=encoded(dict(schema='just-peachy.user-runtime-authority.v1',
        explicit_start_required=True,recording_authorized=True,local_audio_retention=True,
        automatic_capture=False,playback=False,enrollment=False))
    files['code/field_runtime_policy_v2.py']=policy_source
    files['code/field_local_release_plan_v2.py']=plan_source
    template=json.loads(files['broker/TEMPLATE.json'])
    # Source child now checks the actual production policy through a complete graph.
    child=list(template['code_names'])
    child=[n if n!='AUTONOMOUS_QUIET_AUTHORIZATION_V1.json' else 'OFFLINE_RUNTIME_AUTHORITY_V1.json' for n in child]
    additions=('field_runtime_policy_v2.py','field_local_release_plan_v2.py',
        'field_operator_broker_layout_v2.py','field_operator_session_plan_v1.py')
    for name in additions:
        if name not in child:child.append(name)
    if len(child)+len(template['data_files'])>64:raise ValueError('Original complete child capsule cap')
    for name in child:
        if 'code/'+name not in files:raise ValueError('Child depends on missing outer member')
    template['code_names']=child
    files['broker/TEMPLATE.json']=encoded(template)
    code={n:r for n,r in files.items() if n.startswith('code/')}
    if len(code)>64 or sum(map(len,code.values()))>2097152 or any(len(r)>131072 for r in code.values()):
        raise ValueError('Original outer code caps')
    for name,raw in code.items():
        if name.endswith('.py'):compile(raw,name,'exec')
    # Only these reviewed function boundaries change; all other source bytes remain exact.
    unchanged=[name for name in originals if name in files and originals[name]==files[name]]
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[
        dict(path=name,bytes=len(raw),sha256=sha(raw)) for name,raw in sorted(files.items())])
    output=encoded(dict(manifest=manifest,files={n:base64.b64encode(r).decode() for n,r in sorted(files.items())}))
    if len(output)>1048576:raise ValueError('Original prepared bundle byte cap')
    review=dict(status='PREPARED_OFFLINE_BROKER_TEMPLATE',original_bundle_sha256=ORIGINAL_SHA,
        bundle_sha256=sha(output),manifest_sha256=sha(encoded(manifest)),changed=changes,
        unchanged_members=unchanged,outer_code_members=len(code),outer_code_bytes=sum(map(len,code.values())),
        child_code_members=len(child),child_data_members=len(template['data_files']),
        source_graph_executed=False,native_executed=False,admission_issued=False,
        profile='d1-delayed',requires_fresh_native_runtime_binding=True)
    return output,review
