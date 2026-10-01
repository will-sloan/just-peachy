"""Current-boot capsule derivation. See README_FINAL_MANAGER_INTEGRATION_V1.md."""
import ast
import base64
import copy
import hashlib
import json

OLD = "owner['boot_id']!=config['baseline']['boot_id'] or ticks(1013)!=569 or ticks(1130)!=607"
NEW = "not baseline_matches(config['baseline'], owner['boot_id'], ticks)"
BASELINE = """
def baseline_matches(baseline, boot, ticks):
    rows = baseline.get('owners')
    if type(rows) is not list or len(rows) != 2:
        return False
    if any(type(o) is not dict or set(o) != {'pid','start_ticks','boot_id'} for o in rows):
        return False
    if any(type(o['pid']) is not int or o['pid'] <= 0 or
           type(o['start_ticks']) is not int or o['start_ticks'] <= 0 or
           o['boot_id'] != boot for o in rows):
        return False
    if len({o['pid'] for o in rows}) != 2 or baseline.get('boot_id') != boot:
        return False
    return all(ticks(o['pid']) == o['start_ticks'] for o in rows)
"""

def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def derive(broker, manager, lifecycle):
    from field_local_manager_owners_v1 import lifecycle as check
    check(lifecycle, hashlib.sha256(encoded(lifecycle)).hexdigest())
    from field_local_joint_contract_v3 import capsule
    files=capsule(broker,'just-peachy.broker-capsule.v1',64,'broker')
    capsule(manager,'just-peachy.local-release-manifest.v1',16,'code/')
    common='code/field_operator_broker_common_v1.py'
    raw=files[common].decode()
    if raw.count(OLD)!=1:
        raise ValueError('Exact reviewed old baseline guard')
    updated=raw.replace(OLD,NEW,1)+BASELINE
    compile(updated,common,'exec')
    # Every original function body except physical is retained exactly.
    old_tree=ast.parse(raw);new_tree=ast.parse(updated)
    old_defs={n.name:ast.dump(n,include_attributes=False) for n in old_tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    new_defs={n.name:ast.dump(n,include_attributes=False) for n in new_tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    for name,value in old_defs.items():
        if name!='physical' and new_defs[name]!=value:raise ValueError('Unexpected changed function')
    files[common]=updated.encode()
    config=json.loads(files['broker/CONFIG.json'])
    if 'local_manager' in config:raise ValueError('Consumed capsule binding')
    config['baseline'].update(boot_id=lifecycle['boot_id'],owners=copy.deepcopy(lifecycle['baseline_owners']))
    for destination,origin in [('install_sha256','install_sha256'),('live_config_sha256','live_config_sha256'),('display_sha256','display_config_sha256')]:
        if config['baseline'][destination]!=lifecycle[origin]:raise ValueError('Baseline source pin drift')
    template=json.loads(files['broker/TEMPLATE.json'])
    template['admission']['boot_id']=lifecycle['boot_id']
    files['broker/CONFIG.json']=encoded(config);files['broker/TEMPLATE.json']=encoded(template)
    # Keep module basenames inside a fresh immutable capsule; original host
    # sources and earlier capsules are never overwritten or reclassified.
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[
        dict(path=n,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in sorted(files.items())])
    result=dict(files={n:base64.b64encode(v).decode() for n,v in files.items()},manifest=manifest)
    capsule(result,'just-peachy.broker-capsule.v1',64,'broker')
    return result

