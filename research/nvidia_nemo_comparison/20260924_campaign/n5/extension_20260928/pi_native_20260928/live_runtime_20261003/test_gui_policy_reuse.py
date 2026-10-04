"""Synthetic composition/strict-delta checks only; README_GUI_POLICY_REUSE.md."""
import copy
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest

import gui_policy_reuse as subject


class ReuseBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='gui-reuse-test-',dir=str(subject.PRIVATE/'storage-preparation'))
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.before=b'"""synthetic fixture"""\nclass Manager:\n def start(self): return 1\ndef show(): return 1\ndef main(): return 1\n'
        self.after=self.before.replace(b'def show(): return 1',b'def show(): return 2')+b'def gui_session_policy(binding, selection): return 1\ndef gui_policy_summary(policy): return "test"\n'
        self.s,self.sh,self.sb=self.package('14',self.before,False)
        self.d,self.dh,self.db=self.package('15',self.after,True)

    def package(self,label,launcher,new,extra=None):
        root=self.root/label;root.mkdir();target='/home/example/build-'+label
        binding=dict(target=target,reference_code=target+'/reference',raw_factory_path=target+'/reference/raw.py',
            profiles={'baseline':{'path':target+'/profiles/baseline.json','sha256':'f'*64}},candidate_content_sha256=label[0]*64,
            installed_manifest_sha256='b'*64,installed_release='/home/example/installed',native_launch_enabled=False,
            authorization_kind='qualification',production_acceptance_sha256=None,admission_sha256=None)
        if new:binding['candidate_content_sha256']='d'*64
        files={'launcher.py':launcher,'source-backups/launcher.py.backup':launcher,'source-backups/launcher.py.restore':launcher,
            'worker.py':b'# unchanged worker\n','BINDING.json':subject.encoded(binding)}
        if new:files['README_GUI_OPTIONAL_POLICY.md']=b'UI policy fixture'
        files.update(extra or {})
        for name,raw in files.items():
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        manifest=dict(schema='just-peachy.v29.package.v1',target=target,candidate_content_sha256=binding['candidate_content_sha256'],
            files=[dict(path=name,bytes=len(raw),sha256=subject.sha(raw)) for name,raw in sorted(files.items())])
        raw=subject.encoded(manifest);(root/'PACKAGE_MANIFEST.json').write_bytes(raw)
        return root,subject.sha(raw),binding

    def test_full_inventory_and_non_gui_ast_scope(self):
        value=subject.compare(self.s,self.sh,self.d,self.dh)
        self.assertFalse(value['reviewed']);self.assertTrue(value['launcher_ast']['manager_ast_identical'])
        changed=self.after.replace(b'def start(self): return 1',b'def start(self): return 3')
        with self.assertRaisesRegex(ValueError,'Non-GUI'):subject.launcher_scope(self.before,changed)
        bad,badsha,_=self.package('16',self.after,True,{'worker.py':b'# unapproved worker change'})
        with self.assertRaisesRegex(ValueError,'non-GUI delta'):subject.compare(self.s,self.sh,bad,badsha)
        (self.d/'unlisted.txt').write_text('not in inventory')
        with self.assertRaisesRegex(ValueError,'membership'):subject.compare(self.s,self.sh,self.d,self.dh)

    def test_reviewed_certificate_exact_facts_required(self):
        value=subject.compare(self.s,self.sh,self.d,self.dh);raw=subject.encoded(value)
        with self.assertRaisesRegex(ValueError,'reviewed'):subject.validate_certificate(raw,subject.sha(raw),self.s,self.sh,self.d,self.dh)
        value.update(reviewed=True,reviewer='synthetic host test',reviewed_unix=time.time());raw=subject.encoded(value)
        self.assertEqual(subject.validate_certificate(raw,subject.sha(raw),self.s,self.sh,self.d,self.dh),value)
        value['worker_source_model_storage_optional_code_unchanged']=False;raw=subject.encoded(value)
        with self.assertRaisesRegex(ValueError,'reviewed'):subject.validate_certificate(raw,subject.sha(raw),self.s,self.sh,self.d,self.dh)

    def test_compose_preserves_actual_fact_fields_and_refuses_asset_or_chain_change(self):
        cert=subject.compare(self.s,self.sh,self.d,self.dh);cert.update(reviewed=True,reviewer='synthetic test',reviewed_unix=time.time());cr=subject.encoded(cert)
        assets=[dict(path='/home/example/model',resolved='/home/example/model',bytes=123,sha256='a'*64)]
        op=lambda binding:subject.sha(subject.encoded({k:v for k,v in binding.items() if k not in subject.AUTH}))
        original=dict(schema='synthetic-only',qualified_binding_sha256=subject.sha((self.s/'BINDING.json').read_bytes()),qualified_package_manifest_sha256=self.sh,
            selection={'unchanged':'selection'},policy={'unchanged':'policy'},measured={'total_ram_bytes':2000000000,'source_samples':4800000},
            closure={'actual_facts':'preserve'},pins=dict(candidate_content_sha256=self.sb['candidate_content_sha256'],installed_manifest_sha256='b'*64,
                operational_binding_sha256=op(self.sb),selected_asset_inventory_sha256=subject.sha(subject.encoded(assets))))
        def validate(raw,digest,selection,policy,pins,*args,**kwargs):
            self.assertEqual(subject.sha(raw),digest);self.assertEqual(subject.strict(raw)['pins'],pins)
        admission=SimpleNamespace(operational_binding_sha256=op,validate_admission=validate)
        builder=SimpleNamespace(validate_relocation=lambda *args:None)
        profiles=SimpleNamespace(RuntimeSelection=lambda **kw:kw,SessionPolicy=lambda **kw:kw)
        final=copy.deepcopy(self.db);final['target']='/home/example/build-16'
        raw=subject.encoded(original);pc=b'{}'
        def invoke(source_raw=raw,selected=assets):
            return subject.compose_measured_admission(source_raw,subject.sha(source_raw),cr,subject.sha(cr),self.s,self.sh,self.d,self.dh,final,pc,subject.sha(pc),selected,builder,admission,profiles,'synthetic test',time.time())
        result=invoke();unchanged=copy.deepcopy(result);unchanged.pop('reuse_basis');unchanged['pins']=copy.deepcopy(original['pins'])
        self.assertEqual(unchanged,original);self.assertFalse(result['reuse_basis']['destination_native_measurement_claimed'])
        with self.assertRaises(AssertionError):invoke(selected=[dict(assets[0],sha256='f'*64)])
        with self.assertRaisesRegex(ValueError,'Original'):invoke(subject.encoded(dict(original,reuse_basis={})))
        with self.assertRaisesRegex(ValueError,'package-local'):invoke(selected=[dict(assets[0],path=self.db['target']+'/model')])


if __name__=='__main__':unittest.main()
