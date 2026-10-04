"""Host-only exact interpreter inventory checks. See README_RELEASE_AUTHORIZATION.md."""
import argparse,ctypes,json,os,sys,uuid,hashlib,copy,importlib.util
from pathlib import Path
def early(output_root):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p;handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,1<<14):raise ctypes.WinError(ctypes.get_last_error())
    values=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    output=Path(output_root)/('interpreter-derivative-'+uuid.uuid4().hex);output.mkdir(parents=True,exist_ok=False)
    with (output/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
            affinity_mask=1<<14,creation_filetime=values[0].value,
            create_time=(values[0].value-116444736000000000)/10000000),stream)
        stream.flush();os.fsync(stream.fileno())
    return output


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output-root',required=True);a=p.parse_args();o=early(a.output_root);sys.dont_write_bytecode=True
 sys.path.insert(0,str(a.source));spec=importlib.util.spec_from_file_location('candidate_authorization',Path(__file__).with_name('release_authorization.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 from profiles import RuntimeSelection
 binding=json.loads((a.source/'BINDING.json').read_bytes());actual=json.loads(a.assets.read_bytes());assets=actual['assets'];assert len(assets)==61 and actual['actual_hashes_verified'] is True
 fixture=dict(schema='just-peachy.v29.production-acceptance.v1',accepted=True,reviewer='synthetic host-only validation',accepted_unix=1,target=binding['target'],candidate_content_sha256=binding['candidate_content_sha256'],installed_manifest_sha256=binding['installed_manifest_sha256'],previous_desktop_sha256='0'*64,allowed_selections=[RuntimeSelection('pyannote','titanet','saved').validate()],limits=dict(maximum_session_seconds=300,maximum_developer_seconds=3600,max_drain_seconds=600,max_backlog_seconds=120),assets=assets,full_backup=dict(scope='selected-release-and-user-data',root='fixture',manifest_path='fixture',completion_path='fixture',manifest_sha256='0'*64,completion_sha256='0'*64))
 m.validate_acceptance(fixture,binding);m.validate_acceptance(fixture,{key:binding[key] for key in ('target','candidate_content_sha256','installed_manifest_sha256','python')});checks=['actual61_asset_inventory_accepted_only_in_memory','exact_builder_binding_shape']
 oldspec=importlib.util.spec_from_file_location('old_authorization',a.source/'release_authorization.py');old=importlib.util.module_from_spec(oldspec);oldspec.loader.exec_module(old)
 try:old.validate_acceptance(fixture,binding)
 except ValueError:checks.append('frozen11_actual_resolution_refusal_reproduced')
 else:raise AssertionError('Old validator unexpectedly passed')
 def refuse(label,field,value,other=False):
  v=copy.deepcopy(fixture);row=next(x for x in v['assets'] if x['path']==binding['python']);row[field]=value
  if other:row['path']=binding['python']+'.other'
  try:m.validate_acceptance(v,binding)
  except ValueError:checks.append(label)
  else:raise AssertionError(label+' did not refuse')
 refuse('other_external_alias','path',binding['python']+'.other');refuse('other_usr_resolution','resolved','/usr/bin/python3.12');refuse('extent_mismatch','bytes',6616895);refuse('content_mismatch','sha256','1'*64);refuse('external_alias_itself','path','/usr/bin/python3.11');refuse('traversal','resolved','/usr/bin/../bin/python3.11');refuse('other_external_asset','resolved','/usr/bin/python3.11',True)
 raw=json.dumps(dict(status='PASS',checks=checks,native_executed=False,acceptance_issued=False,source_manifest_sha256=hashlib.sha256((a.source/'PACKAGE_MANIFEST.json').read_bytes()).hexdigest(),assets_sha256=hashlib.sha256(a.assets.read_bytes()).hexdigest()),sort_keys=True).encode()
 with (o/'RESULT.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 print(json.dumps(dict(output=str(o),checks=len(checks))))
if __name__=='__main__':main()
