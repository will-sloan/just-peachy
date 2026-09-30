"""Explicit UTF-8 repair from immutable V1 bytes; README_FIELD_ARTIFACT_INSTALL_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
from pathlib import Path

P=Path(__file__).resolve().parent
B=Path(r'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928')

def main():
    prior=B/'field-artifact-install-v1-evidence'
    assert json.loads((prior/'REVIEW.json').read_text())['status']=='REVIEWED_INSTALLED_ARTIFACT_FAILURE_ONLY'
    assert json.loads((prior/'BACKUP.json').read_text())['status']=='EXACT_PRIVATE_TARGET_BACKUP_VERIFIED'
    expected=json.loads((P/'ARTIFACT_INSTALL_DERIVATION_V1.json').read_text())
    repairs={}
    for stem in ['field_entry_artifact','controller_artifact']:
        old=P/(stem+'_v1.py');new=P/(stem+'_v2.py');raw=old.read_bytes()
        repaired=raw.decode('cp1252').encode('utf-8')
        digest=hashlib.sha256(repaired).hexdigest()
        assert digest==expected[old.name]['derivative_sha256']
        ast.parse(repaired);compile(repaired,str(new),'exec')
        with new.open('xb') as f:f.write(repaired)
        repairs[new.name]=dict(source=old.name,target=new.name,prior_actual_sha256=hashlib.sha256(raw).hexdigest(),new_sha256=digest,intended_utf8_sha256=expected[old.name]['derivative_sha256'])
    with (P/'ARTIFACT_INSTALL_DERIVATION_V2.json').open('xb') as f:
        f.write(json.dumps(dict(repairs=repairs,reason='Explicit UTF-8 reconstruction exactly matching V1 intended Unicode source; V1 raw bytes preserved'),indent=2).encode('utf-8'))
    def derive(old,new,replacements):
        code=(P/old).read_bytes().decode('utf-8')
        for a,b in replacements:
            assert a in code,a
            code=code.replace(a,b)
        raw=code.encode('utf-8');ast.parse(raw)
        with (P/new).open('xb') as f:f.write(raw)
    derive('field_artifact_install_v1.py','field_artifact_install_v2.py',[
        ('"""Installed artifact binding, no inference/capture; README_FIELD_ARTIFACT_INSTALL_V1.md."""','"""UTF-8 repaired installed integration; README_FIELD_ARTIFACT_INSTALL_V2.md."""'),
        ('controller_artifact_v1.py','controller_artifact_v2.py'),('field_entry_artifact_v1.py','field_entry_artifact_v2.py'),
        ('b01-offline-20260930-v11','b01-offline-20260930-v12'),
        ("'README_FIELD_ARTIFACT_LIMITS_V2.md':'docs/README_FIELD_ARTIFACT_LIMITS_V2.md'","'README_FIELD_ARTIFACT_INSTALL_V2.md':'docs/README_FIELD_ARTIFACT_INSTALL_V2.md',\n             'README_FIELD_ARTIFACT_LIMITS_V2.md':'docs/README_FIELD_ARTIFACT_LIMITS_V2.md'")])
    derive('dispatch_field_artifact_install_v1.py','dispatch_field_artifact_install_v2.py',[
        ('README_FIELD_ARTIFACT_INSTALL_V1.md', 'README_FIELD_ARTIFACT_INSTALL_V2.md'),
        ('field-artifact-install-v1','field-artifact-install-v2'),('dispatch_field_artifact_install_v1','dispatch_field_artifact_install_v2'),
        ('field_artifact_install_v1','field_artifact_install_v2'),('field_entry_artifact_v1.py','field_entry_artifact_v2.py'),('controller_artifact_v1.py','controller_artifact_v2.py'),
        ("'ARTIFACT_INSTALL_DERIVATION_V1.json',","'ARTIFACT_INSTALL_DERIVATION_V1.json', 'ARTIFACT_INSTALL_DERIVATION_V2.json', 'README_FIELD_ARTIFACT_INSTALL_V1.md', 'prepare_field_artifact_install_v2.py',"),
        ("prior=PRIVATE/'field-artifact-limits-v2-evidence'", "failure=PRIVATE/'field-artifact-install-v1-evidence'\n    assert json.loads((failure/'REVIEW.json').read_text())['status']=='REVIEWED_INSTALLED_ARTIFACT_FAILURE_ONLY'\n    assert json.loads((failure/'BACKUP.json').read_text())['status']=='EXACT_PRIVATE_TARGET_BACKUP_VERIFIED'\n    payload['PRIOR_INSTALL_FAILURE_REVIEW.json']=base64.b64encode((failure/'REVIEW.json').read_bytes()).decode()\n    payload['PRIOR_INSTALL_FAILURE_BACKUP.json']=base64.b64encode((failure/'BACKUP.json').read_bytes()).decode()\n    prior=PRIVATE/'field-artifact-limits-v2-evidence'")])
    print(json.dumps(dict(status='UTF8_REPAIRS_PREPARED',repairs=repairs)))

if __name__=='__main__':main()
