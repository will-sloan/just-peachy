"""Only final review/post-content metadata boundaries; README_PRODUCTION_FINALIZATION.md."""
import ast
import copy
from pathlib import Path
import tempfile
import tarfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import finalize_production_release as finalizer


class FinalizationBoundaryTests(unittest.TestCase):
    BUILDER=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/identity14-builder-source-006b6025a1db428094791fbcdf0dcf8c/prepare_package.py.after')

    def test_only_one_ast_insertion_in_exact_reviewed_builder(self):
        source=self.BUILDER
        raw=source.read_bytes();namespace,tree=finalizer.extend_builder(raw,str(source),lambda production,binding:{})
        build=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build')
        found=[n for n in build.body if isinstance(n,ast.Expr) and ast.unparse(n)=='files.update(_reviewed_post_content(production, binding))']
        self.assertEqual(len(found),1);build.body.remove(found[0])
        self.assertEqual(ast.dump(tree,include_attributes=False),ast.dump(ast.parse(raw),include_attributes=False))
        self.assertIn('build',namespace)
        with self.assertRaisesRegex(ValueError,'builder'):finalizer.extend_builder(raw+b'\n',str(source),lambda *_:{})

    def test_post_content_member_is_in_written_manifest_and_archive(self):
        # Execute the unchanged serialization tail only with tiny synthetic files.
        # No production review, actual acceptance or full runtime build is made.
        metadata=b'{"synthetic_test_only":true}'
        name='authorization/optional-'+finalizer.sha(metadata)+'.json'
        namespace,tree=finalizer.extend_builder(self.BUILDER.read_bytes(),str(self.BUILDER),lambda *_:{name:metadata})
        build=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build')
        index=next(i for i,n in enumerate(build.body) if isinstance(n,ast.Expr) and ast.unparse(n)=='files.update(_reviewed_post_content(production, binding))')
        tail=ast.FunctionDef(name='serialization_tail',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=copy.deepcopy(build.body[index:]),decorator_list=[])
        with tempfile.TemporaryDirectory(prefix='production-metadata-',dir=str(finalizer.PRIVATE/'storage-preparation')) as directory:
            root=Path(directory);bundle=root/'bundle';bundle.write_bytes(b'synthetic')
            namespace.update(files={'BINDING.json':b'{}'},production={},binding={},runtime_files=(),output=root,
                target='/synthetic',content_sha='c'*64,admission=None,bundle_raw=b'synthetic',bundle_path=bundle,
                rows=[],options_raw=None,descriptors={},snapshot_manifest_sha256=None,release_id='synthetic',source=root)
            module=ast.fix_missing_locations(ast.Module(body=[tail],type_ignores=[]));exec(compile(module,'synthetic-serialization-tail','exec'),namespace)
            result=namespace['serialization_tail']();manifest=finalizer.strict((root/'package/PACKAGE_MANIFEST.json').read_bytes())
            self.assertEqual(result['candidate_content_sha256'],'c'*64)
            self.assertEqual(next(r for r in manifest['files'] if r['path']==name)['sha256'],finalizer.sha(metadata))
            with tarfile.open(result['archive'],'r:gz') as archive:
                self.assertEqual(archive.extractfile(name).read(),metadata)
                self.assertEqual(archive.extractfile('PACKAGE_MANIFEST.json').read(),(root/'package/PACKAGE_MANIFEST.json').read_bytes())

    def test_pending_review_and_changed_content_cannot_create_acceptance(self):
        binding=dict(target=finalizer.PARENT+'field-runtime-v29-build-14',candidate_content_sha256='1'*64,installed_manifest_sha256='2'*64)
        plan={key:[] for key in finalizer.PLAN_FIELDS};plan.update(accepted=False,target=finalizer.PARENT+'field-runtime-v29-build-15',candidate_content_sha256='1'*64,installed_manifest_sha256='2'*64)
        review=dict(schema='just-peachy.production-finalization-review.v1',reviewed=False,reviewer='synthetic boundary test',reviewed_unix=time.time(),source={},destination_target=plan['target'],builder={},relocation_certificate={},production_plan={},proofs=[dict(purpose=p,sha256='3'*64) for p in finalizer.PROOF_PURPOSES],optional_documents=[],limitations=['Synthetic host contract only'])
        with self.assertRaisesRegex(ValueError,'completed'):finalizer.reviewed_acceptance(review,plan,binding)
        review['reviewed']=True;bad=copy.deepcopy(plan);bad['candidate_content_sha256']='4'*64
        with self.assertRaisesRegex(ValueError,'same-content'):finalizer.reviewed_acceptance(review,bad,binding)
        result=finalizer.reviewed_acceptance(review,plan,binding)
        self.assertTrue(result['accepted']);self.assertFalse(plan['accepted'])
        bad=copy.deepcopy(review);bad['proofs']=[]
        with self.assertRaisesRegex(ValueError,'incomplete'):finalizer.reviewed_acceptance(bad,plan,binding)

    def test_exact_optional_metadata_membership_and_measured_validator_called(self):
        binding=dict(target=finalizer.PARENT+'field-runtime-v29-build-15')
        selection=dict(optional_d1_refiner=True);policy=dict(maximum_session_seconds=300)
        raw=finalizer.encoded(dict(schema='measured-test-schema',measured=dict(total_ram_bytes=2000000000)))
        digest=finalizer.sha(raw);name='authorization/optional-'+digest+'.json'
        ref=dict(selection=selection,policy=policy,path=binding['target']+'/'+name,sha256=digest,asset_inventory_sha256='a'*64)
        acceptance=dict(optional_refiner_admissions=[ref],allowed_selections=[selection]);calls=[]
        modules=dict(optional_refiner_dispatch=SimpleNamespace(validate_references=lambda rows:rows,expected_pins=lambda *_:{'exact':'pins'}),
            optional_refiner_admission=SimpleNamespace(SCHEMA='measured-test-schema',validate_admission=lambda *args,**kwargs:calls.append((args,kwargs))),
            profiles=SimpleNamespace(RuntimeSelection=lambda **kw:kw,SessionPolicy=lambda **kw:kw))
        doc=dict(native_path=ref['path'],path='synthetic-only.json',sha256=digest)
        with patch.object(finalizer,'pinned',return_value=raw):
            self.assertEqual(finalizer.optional_metadata(acceptance,binding,[doc],modules),{name:raw})
            self.assertEqual(calls[0][0][5],0);self.assertEqual(calls[0][1]['phase'],'historical_evidence')
            with self.assertRaisesRegex(ValueError,'one document'):finalizer.optional_metadata(acceptance,binding,[],modules)
            changed=copy.deepcopy(acceptance);changed['optional_refiner_admissions'][0]['path']=binding['target']+'/escape.json'
            with self.assertRaisesRegex(ValueError,'authorization directory'):
                finalizer.optional_metadata(changed,binding,[dict(doc,native_path=changed['optional_refiner_admissions'][0]['path'])],modules)
        with patch.object(finalizer,'pinned',return_value=finalizer.encoded(dict(schema='qualification-permit'))):
            with self.assertRaisesRegex(ValueError,'Measured normal'):finalizer.optional_metadata(acceptance,binding,[doc],modules)


if __name__=='__main__':unittest.main()
