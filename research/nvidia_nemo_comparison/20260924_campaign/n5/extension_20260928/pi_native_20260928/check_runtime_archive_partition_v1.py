"""Focused partition check; README_RUNTIME_ARCHIVE_PARTITION_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,base64,copy,hashlib,json
from pathlib import Path
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--private',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();a.output.mkdir();me=psutil.Process()
    (a.output/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    from field_runtime_archive_partition_v1 import derive
    common=a.private/'field-runtime-v7-install/stage-backup/field-runtime-v7-profiles/COMMON_BUNDLE.json';original=common.read_bytes()
    changed,review=derive(original);member=base64.b64decode(json.loads(changed)['files']['code/field_archive_budget_v4.py'])
    ns={};exec(compile(member,'<actual-new-budget>','exec'),ns);budget=ns['validate'](ns['DEFAULT']);encode=ns['encode_control']
    assert budget['initial_control_bytes']+budget['runtime_control_bytes']+1024==budget['control_file_bytes']==65536
    metadata_path=next((a.private/'field-runtime-v7-preservation-v1/tree/field-operator-sessions-v225').rglob('epoch.json'))
    initial=metadata_path.read_bytes();epoch=json.loads(initial)
    observation=json.loads((a.private/'deployable-runtime-resume-v1/install-inspection-v7/RESULT.json').read_bytes())
    rows=[]
    for name,row in observation['gallery_metadata'].items():
        raw=base64.b64decode(row['base64'],validate=True)
        assert len(raw)==row['pin']['bytes'] and hashlib.sha256(raw).hexdigest()==row['pin']['sha256']
        rows.append(json.loads(raw))
    assert len(rows)==1
    e0=copy.deepcopy(epoch['mode_configuration']['gallery']);e0.pop('namespace');e0.pop('calibration')
    e0['backend_sha256']='5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609'
    e0['preprocessing']='mono-float32-16k-redimnet2-native-l2-v1';e0['loaded_count']=len(rows);e0['personal_ids']=[r['id'] for r in rows]
    e0['templates']=[dict(person_id=r['id'],display_name=r['name'],metadata_sha256=hashlib.sha256(json.dumps(r,sort_keys=True,allow_nan=False).encode()).hexdigest(),centroid_sha256='0'*64,references=r['references']) for r in rows]
    e0['template_availability']='AVAILABLE';epoch['mode_configuration']['gallery']=e0;epoch['mode_configuration']['n2_policy']['calibration']={'status':'UNCALIBRATED'}
    epoch['archive_budget']=budget;epoch['archive_budget_sha256']=ns['digest'](budget)
    projected=encode(epoch,budget['initial_control_bytes']);assert json.loads(projected)==epoch
    rejects=0
    for fn in (lambda:encode(epoch,32768),lambda:encode({'a':'x'*39928},39936),lambda:ns['validate']({**budget,'initial_control_bytes':39937}),lambda:ns['validate']({**budget,'runtime_control_bytes':24575}),lambda:ns['validate']({**budget,'control_file_bytes':65535})):
        try:fn()
        except ValueError:rejects+=1
        else:raise AssertionError('Required partition rejection')
    assert common.read_bytes()==original and metadata_path.read_bytes()==initial
    result=dict(status='PASS_CHANGED_CONTROL_PARTITION',full_metadata_projection_bytes=len(projected),original_initial_limit=32768,partition=budget,required_rejects=rejects,source_metadata_sha256=hashlib.sha256(initial).hexdigest(),derivation=review,
        projection_only=True,centroid_hash_value_placeholder=True,all_actual_gallery_reference_fields_preserved=True,native_executed=False)
    (a.output/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
if __name__=='__main__':main()
