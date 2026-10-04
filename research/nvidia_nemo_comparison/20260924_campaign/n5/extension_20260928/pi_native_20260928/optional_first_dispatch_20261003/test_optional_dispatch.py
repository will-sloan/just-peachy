"""Changed pure orchestration contract only; no native execution. See README.md."""
import base64
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import unittest

HERE=Path(__file__).parent
FROZEN=Path(os.environ['JP_FROZEN08_HOST'])


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


action=load(HERE/'launch_optional_first_action.py','optional_action_test')


def fixture():
    def doc(raw):return dict(sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode())
    selection=dict(diarizer='pyannote',embedding='titanet',input_source='saved',nemotron_profile=None,
        allow_experimental=True,provisional_correction=False,optional_d1_refiner=True,
        speaker_attribution='retained',refinement_profile='current_delayed',revision_window_seconds=30,
        refinement_period_seconds=5,embedding_schedule='continuous',embedding_refresh_seconds=2)
    source=dict(kind='saved',path=(action.CAMPAIGN/'d1-geometry-delayed-a76-v1/source.wav').as_posix(),
        sha256='0ee26e8aa6f815d8b202419aafb71ff5bc25093d193e95e972036f488c5040b8',samples=715127)
    gate=dict(schema='just-peachy.optional-first-prerequisites.v2',reviewed=True,candidate_content_sha256=action.CONTENT,
        source=source,primary_selection=dict(selection,optional_d1_refiner=False),primary_functional_pass=True,
        gui_functional_pass=True,all_owners_closed=True,allow_first_combined_measurement=True)
    return dict(schema='just-peachy.optional-first-dispatch.v1',reviewed=True,package=action.TARGET.as_posix(),
        package_manifest_sha256=action.MANIFEST,binding_sha256=action.BINDING,candidate_content_sha256=action.CONTENT,
        maximum_output_bytes=256*1024**2,independent_pc_copy_bytes=256*1024**2,runtime_seconds=585,
        label='optional-first-01',dispatcher_sha256='a'*64,expires_unix=500,selection=selection,
        policy=dict(maximum_session_seconds=45,developer_soak=False,max_drain_seconds=60,max_backlog_seconds=30,
            model_load_seconds=120,cleanup_seconds=60),source=source,maximum_lag_seconds=30,
        assets=[{'fixture':'pure synthetic contract only'}],receiver=doc((HERE/'receiver.py').read_bytes()),
        evidence=dict(primary=doc(b'{"synthetic":true}'),gui=doc(b'{"synthetic":true}')),prerequisites=gate)


class Contracts(unittest.TestCase):
    def test_exact_prerequisites_and_receiver(self):
        value=fixture();self.assertEqual(action.shape(value,now=100),(HERE/'receiver.py').read_bytes())
        for key in ('primary_functional_pass','gui_functional_pass','all_owners_closed'):
            bad=copy.deepcopy(value);bad['prerequisites'][key]=False
            with self.assertRaises(ValueError):action.shape(bad,now=100)
        bad=copy.deepcopy(value);bad['receiver']=dict(base64=base64.b64encode(b'print(1)').decode(),sha256=hashlib.sha256(b'print(1)').hexdigest())
        with self.assertRaises(ValueError):action.shape(bad,now=100)
    def test_no_cross_configuration_or_budget_reuse(self):
        value=fixture()
        for key,replacement in [('package_manifest_sha256','f'*64),('maximum_output_bytes',512*1024**2),('runtime_seconds',3600),('expires_unix',1000)]:
            bad=copy.deepcopy(value);bad[key]=replacement
            with self.assertRaises(ValueError):action.shape(bad,now=100)
        bad=copy.deepcopy(value);bad['selection']['embedding']='redimnet'
        with self.assertRaises(ValueError):action.shape(bad,now=100)
    def test_actual_frozen_wrapper_two_narrow_changes(self):
        helper=FROZEN/'launch_raw_qualification_action.py'
        self.assertEqual(hashlib.sha256(helper.read_bytes()).hexdigest(),action.COMMON)
        common=load(helper,'frozen_common_wrapper_test')
        settings=dict(kind='optional_first',external_inputs=[],budget=dict(file_limit_bytes=256*1024**2))
        derived,receipt=action.derive_wrapper(common,settings)
        self.assertEqual(hashlib.sha256(derived.encode()).hexdigest(),receipt['derived_wrapper_sha256'])
        self.assertFalse(receipt['runtime_code_changed'])
        self.assertIn("put('OWNER.json',owner)",derived)
        self.assertLess(derived.index("put('OWNER.json',owner)"),derived.index('scope_path='))
        self.assertLess(derived.index("for entry in SETTINGS['external_inputs']"),derived.index('try:runpy.run_path'))
        self.assertIn('if available<192*1024**2',derived)
        self.assertIn("kind'] not in ('full_app_hour','optional_first')",derived)


if __name__=='__main__':unittest.main()
