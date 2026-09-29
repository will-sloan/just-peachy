"""Bind reviewed B01 saved-file preview. See README_B01_PREVIEW_QUALIFICATION_V2.md."""
import ast
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import psutil
from dispatch_geometry_v2 import remote, PRIVATE

HERE=Path(__file__).resolve().parent

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def dump(node):
    return ast.dump(node,include_attributes=False)

def idle_branch(source):
    tree=ast.parse(source)
    matches=[node for node in ast.walk(tree) if isinstance(node,ast.If) and dump(node.test)==dump(ast.parse("admission['ui_mode']=='withdrawn_check'",mode='eval').body)]
    assert len(matches)==1
    return ast.Module(body=matches[0].orelse,type_ignores=[])

def main():
    psutil.Process().cpu_affinity([14])
    prior=json.loads((HERE/'B05_PREVIEW_V3_QUALIFICATION.json').read_text())
    assert prior['status']=='QUALIFIED_BOUNDED_SAVED_FILE_PREVIEW'
    for name,digest in prior['source_sha256'].items():assert sha(HERE/name)==digest,name
    old=(HERE/'b05_preview_app_v2.py').read_text();new=(HERE/'b01_preview_app_v1.py').read_text()
    assert dump(idle_branch(old))==dump(idle_branch(new))
    old_gate=(HERE/'b05_preview_gate_v1.py').read_text()
    expected_gate=old_gate.replace('README_B05_PREVIEW_V3.md','README_B01_PREVIEW_V1.md').replace("assert admission['ui_mode'] == 'user_visible'","assert admission['ui_mode'] in ('user_visible','withdrawn_check')").replace('b05_preview_app_v2.py','b01_preview_app_v1.py')
    assert dump(ast.parse(expected_gate))==dump(ast.parse((HERE/'b01_preview_gate_v1.py').read_text()))
    expected={'b01-preview-controls-v1':'PASS_B01_GUARDED_PREVIEW_CONTROLS_ONLY',
              'b01-ui-archive-v1':'PASS_B01_WITHDRAWN_WIDGETS_AND_ARCHIVE_ONLY',
              'b01-e0-reference-v1':'PASS_NATIVE_E0_APPLICATION_WINDOW_PARITY_ONLY',
              'b05-preview-idle-v1':'PASS_B05_WITHDRAWN_IDLE_TIMER_ONLY',
              'b05-preview-guard-v1':'PASS_PREVIEW_DISPATCH_LEASE_AND_ENVELOPE_ONLY'}
    x=remote('EXPECTED='+repr(expected)+'\n'+r'''
import hashlib,json,os,subprocess
from pathlib import Path
os.sched_setaffinity(0,{3});root=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
reviews={}
for run,status in EXPECTED.items():
 d=root/run;r=json.loads((d/'REVIEW.json').read_text());assert r['status']==status
 for name,digest in r.get('bindings',{}).items():
  if name=='source_final_snapshot':
   assert run=='b01-ui-archive-v1'
   target=Path(json.loads((d/'ADMISSION.json').read_text())['source_final_snapshot'])
   assert target==root/'b01-restart-gui-v1/FINAL_SNAPSHOT.json'
  else:target=d/name
  assert sha(target)==digest,(run,name)
 for name in ('OWNER.json','PROBE_OWNER.json','DISPATCH_OWNER.json'):
  p=d/name
  if p.exists():
   owner=json.loads(p.read_text());proc=Path('/proc',str(owner['pid']),'stat')
   ticks=int(proc.read_text().rsplit(')',1)[1].split()[19]) if proc.exists() else None
   assert not(boot==owner['boot_id'] and ticks==owner['start_ticks'])
 reviews[run]=dict(status=status,review_sha256=sha(d/'REVIEW.json'))
d=root/'b01-preview-controls-v1';a=json.loads((d/'ADMISSION.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
assert a['mode']=='open_with_names' and a['empty_new_gallery']
bound={Path(row['path']).name:row['sha256'] for row in a['files'] if Path(row['path']).parent==d}
print(json.dumps(dict(reviews=reviews,admission_sha256=sha(d/'ADMISSION.json'),source_sha256=bound)))
''')
    for name in ('b01_preview_v1.py','b01_preview_app_v1.py','b01_preview_gate_v1.py','README_B01_PREVIEW_V1.md'):
        assert sha(HERE/name)==x['source_sha256'][name],name
    for name in ('b05-preview-idle-v1','b05-preview-guard-v1'):
        assert x['reviews'][name]==prior['reviews'][name]
    review=json.loads((PRIVATE/'b01-preview-controls-v1-evidence/REVIEW.json').read_text())
    assert sha(PRIVATE/'b01-preview-controls-v1-evidence/REVIEW.json')==x['reviews']['b01-preview-controls-v1']['review_sha256']
    assert review['sessions'][1]['reference_max_abs']==review['sessions'][1]['E0_full_restart_max_abs']==0
    assert review['encoder_model_loads']==1 and review['preview_controls']['close_button']
    names=['b01_preview_v1.py','b01_preview_app_v1.py','b01_preview_gate_v1.py','launch_b01_preview_v1.py',
           'README_B01_PREVIEW_V1.md','review_b01_preview_v1.py','README_B01_PREVIEW_REVIEW_V1.md',
           'qualify_b01_preview_v2.py','README_B01_PREVIEW_QUALIFICATION_V2.md','dispatch_b01_stack_v2.py','../window_guard.py']
    q=dict(status='QUALIFIED_BOUNDED_SAVED_FILE_PREVIEW',qualified_utc=datetime.now(timezone.utc).isoformat(),
           entry='launch_b01_preview_v1.py --mode user',source_sha256={n:sha(HERE/n) for n in names},reviews=x['reviews'],
           controls_admission_sha256=x['admission_sha256'],idle_loop_AST_sha256=hashlib.sha256(dump(idle_branch(new)).encode()).hexdigest(),
           scope='One original saved 16kHz file; retained E0, empty research gallery, Sherpa/PnC plus delayed D1; explicit user invocation',
           idle_timer_evidence='B05 actual145s idle pass plus unchanged idle-loop AST; B01 controls verify initial idle/no selection/no inference',
           dispatch_envelope_evidence='B05 exact envelope/contender pass; gate AST changed only README/app path and withdrawn-check allowance; actual B01 gate/service closure checked',
           physical_display_qualified=False,real_speech_accuracy_qualified=False,sustained_memory_fit=False,
           personal_naming_qualified=False,live_resampling_qualified=False,stage_release_acceptance=False,
           maximum_starts=2,application_seconds=145,service_seconds=180,address_space_limit_bytes=768*1024**2)
    with (PRIVATE/'B01_PREVIEW_QUALIFICATION_INPUTS_V2.json').open('x') as f:json.dump(x,f,indent=2)
    with (HERE/'B01_PREVIEW_V1_QUALIFICATION.json').open('x') as f:json.dump(q,f,indent=2)
    print(json.dumps(dict(status=q['status'],scope=q['scope'],entry=q['entry'])))

if __name__=='__main__':main()
