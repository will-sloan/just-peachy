"""One-shot exact installed integration derivatives; README_FIELD_ARTIFACT_INSTALL_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
from pathlib import Path

P=Path(__file__).resolve().parent
B=Path(r'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928')
BASE=B/'field-sustained-v4-evidence/target/deployment/releases/b01-offline-20260930-v10'


def main():
    manifest={}
    def derive(source,target,edits):
        raw=source.read_bytes();code=raw.decode().replace('\r\n','\n')
        for old,new in edits:
            assert code.count(old)==1,(str(source),old,code.count(old))
            code=code.replace(old,new)
        ast.parse(code)
        with (P/target).open('x',newline='\n') as f:f.write(code)
        manifest[target]=dict(source_sha256=hashlib.sha256(raw).hexdigest(),derivative_sha256=hashlib.sha256(code.encode()).hexdigest())
    derive(BASE/'native/field_entry_v5.py','field_entry_artifact_v1.py',[
        ('docs/README_FIELD_SUSTAINED_V1.md','docs/README_FIELD_ARTIFACT_INSTALL_V1.md'),
        ('def health():','def artifact_contract():\n    from field_artifact_binding_v1 import bound_limits\n    contract=json.loads((ROOT/"config/field_contract.json").read_text())\n    return contract,bound_limits(ROOT,contract)\n\n\ndef health():'),
        ("contract=json.loads((ROOT/'config/field_contract.json').read_text())\n    if platform", 'contract,limits=artifact_contract()\n    if platform'),
        ('assets=assets,extra_assets=extra,contract=contract,capture_opened=False,models_loaded=False)', 'assets=assets,extra_assets=extra,contract=contract,artifact_limits=limits,artifact_limits_binding=contract["artifact_limits"],capture_opened=False,models_loaded=False)'),
        ('class FieldController(Base):\n        def _sessions_initialize(self):', 'class FieldController(Base):\n        def _artifact_limits_for_epoch(self):\n            from field_artifact_limits_v1 import resolved\n            contract,limits=artifact_contract()\n            if resolved(self.session_store.policy.get("artifact_limits"))!=limits:\n                raise ValueError("Installed archive policy conflicts with artifact contract")\n            return limits\n\n        def _sessions_initialize(self):'),
        ('from field_archive_v2 import FieldArchiveStore','from field_archive_v3 import FieldArchiveStore'),
        ("contract=json.loads((ROOT/'config/field_contract.json').read_text())\n            self.session_store=FieldArchiveStore(self.data_root,contract,before_publish=self._validate_import_projection)", 'contract,limits=artifact_contract()\n            self.session_store=FieldArchiveStore(self.data_root,contract,before_publish=self._validate_import_projection,artifact_limits=limits)'),
        ('def _start_session(self):\n            contract=', 'def _start_session(self):\n            self._artifact_limits_for_epoch()  # Reject drift before state/epoch/writer publication.\n            contract='),
        ("def create_controller(data):\n    contract=json.loads((ROOT/'config/field_contract.json').read_text())", 'def create_controller(data):\n    contract,limits=artifact_contract()  # Missing config must fail before creating private data.')])
    derive(BASE/'native/field_archive_v2.py','field_archive_v3.py',[
        ('README_FIELD_ARCHIVE_V2.md','README_FIELD_ARTIFACT_INSTALL_V1.md'),
        ('def __init__(self,data_root,contract,before_publish=None):\n        self.before_publish=before_publish', 'def __init__(self,data_root,contract,before_publish=None,*,artifact_limits):\n        from field_artifact_limits_v1 import validate,digest\n        limits=validate(artifact_limits)\n        if digest(limits)!=contract["artifact_limits"]["canonical_sha256"]:raise ValueError("Archive constructor artifact conflict")\n        self.before_publish=before_publish'),
        ('policy=dict(quota_mib=512,free_floor_mib=5120)', 'policy=dict(quota_mib=512,free_floor_mib=5120,artifact_limits=limits,record_bytes=MIB)')])
    raw=(BASE/'app/controller.py').read_bytes();code=raw.decode().replace('\r\n','\n')
    start=code.index('        engine_type=PrototypeEngine;engine_args={}')
    end=code.index('\n        self.engine=engine',start)
    factory=code[start:end].replace('engine_type=PrototypeEngine;engine_args={}', 'engine_type=PrototypeEngine;engine_args={"artifact_limits":self._artifact_limits_for_epoch()}')
    factory=factory.replace('        engine=engine_type(', '        return engine_type(')
    code=code[:start]+'        engine=self._create_epoch_engine(profile,gallery,spatial)'+code[end:]
    helpers='    def _artifact_limits_for_epoch(self):\n        from field_artifact_limits_v1 import resolved\n        return resolved(self.session_store.policy.get("artifact_limits"))\n\n    def _create_epoch_engine(self,profile,gallery,spatial):\n'+factory+'\n\n'
    needle='    def _start_session(self):';assert code.count(needle)==1
    code=code.replace(needle,helpers+needle)
    ast.parse(code)
    with (P/'controller_artifact_v1.py').open('x',newline='\n') as f:f.write(code)
    manifest['controller_artifact_v1.py']=dict(source_sha256=hashlib.sha256(raw).hexdigest(),derivative_sha256=hashlib.sha256(code.encode()).hexdigest())
    with (P/'ARTIFACT_INSTALL_DERIVATION_V1.json').open('x') as f:json.dump(manifest,f,indent=2)
    print('Prepared three exact fresh installed integration derivatives')


if __name__=='__main__':main()
