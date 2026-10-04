"""Pure new qualification bridge refusals; synthetic records are never admissions."""
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import unittest
FROZEN=Path(os.environ['JP_FROZEN08_HOST']);sys.path.insert(0,str(FROZEN))
from profiles import RuntimeSelection
path=Path(__file__).parent/'runtime_derivative09_bridge/optional_refiner_qualification.py'
spec=importlib.util.spec_from_file_location('bridge09_under_test',path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def fixture():
    selection=RuntimeSelection('pyannote','titanet','live',allow_experimental=True,optional_d1_refiner=True)
    pins={key:'a'*64 for key in ('candidate_content_sha256','installed_manifest_sha256','operational_binding_sha256','selected_asset_inventory_sha256')}
    binding=dict(candidate_content_sha256='a'*64,live_config={'fixture':'synthetic'},raw_adapter_enabled=True,
        raw_qualification_evidence=dict(qualified=True,adapter_native_qualified=True,evidence='/fixture/raw.json',evidence_sha256='b'*64))
    source=dict(kind='saved',path='/fixture/source.wav',sha256='c'*64,samples=715127)
    live=dict(kind='live',config_sha256=hashlib.sha256(m.encoded(binding['live_config'])).hexdigest())
    primary=dict(selection.validate(),input_source='saved',optional_d1_refiner=False,allow_experimental=False)
    gate=dict(schema='just-peachy.optional-first-prerequisites.v2',reviewed=True,candidate_content_sha256='a'*64,
        primary_selection=primary,source=source,permission_only_difference_reviewed=True,
        primary_functional_pass=True,gui_functional_pass=True,all_owners_closed=True,allow_first_combined_measurement=True,
        gui_review=dict(path='/fixture/gui.json',sha256='d'*64))
    feasible=dict(schema='just-peachy.optional-feasibility-review.v1',reviewed=True,production_eligible=False,
        selection=dict(selection.validate(),input_source='saved'),source=source,source_change_reviewed=True,
        followup_pins=pins,candidate_content_sha256='a'*64,operational_binding_sha256='a'*64,
        complete_primary_eof=True,complete_refiner_eof=True,all_models_closed=True,all_owners_dead=True,
        cgroup_empty=True,full_mirror_verified=True,allow_followup_policy_measurement=True,source_samples=715127,dropped_samples=0,
        execution=dict(path='/fixture/execution.json',sha256='e'*64),measurement=dict(path='/fixture/measurement.json',sha256='f'*64),closure=dict(path='/fixture/closure.json',sha256='1'*64))
    row=dict(stage='followup_policy',source=live,feasibility_review_sha256='2'*64,reviewed_feasibility=feasible)
    gate['live_composition_review']=dict(schema='just-peachy.optional-live-composition-review.v1',reviewed=True,
        qualification_only=True,live_primary_pass_claimed=False,source_change_reviewed=True,
        matched_model_options_unchanged=True,measured_primary_selection=primary,measured_primary_source=source,
        followup_selection=selection.validate(),live_source=live,pins=pins,first_combined_feasibility_sha256='2'*64,
        raw_qualification_evidence=binding['raw_qualification_evidence'],live_config_sha256=live['config_sha256'],gui_review_sha256='d'*64)
    return gate,row,selection,binding,pins


class Bridge(unittest.TestCase):
    def test_preserves_actual_saved_primary(self):
        args=fixture();before=copy.deepcopy(args[0])
        self.assertTrue(m.validate_prerequisite_gate(*args))
        self.assertEqual(args[0],before)
        self.assertEqual(args[0]['primary_selection']['input_source'],'saved')
        self.assertFalse(args[0]['live_composition_review']['live_primary_pass_claimed'])
    def test_bridge_not_initial_or_production_claim(self):
        gate,row,selection,binding,pins=fixture();row['stage']='initial'
        with self.assertRaises(ValueError):m.validate_prerequisite_gate(gate,row,selection,binding,pins)
        gate,row,selection,binding,pins=fixture();gate['live_composition_review']['live_primary_pass_claimed']=True
        with self.assertRaises(ValueError):m.validate_prerequisite_gate(gate,row,selection,binding,pins)
    def test_changed_models_source_proof_or_missing_first_eof_refused(self):
        for mutation in ('embedding','config','raw','first_eof','first_source'):
            gate,row,selection,binding,pins=fixture()
            if mutation=='embedding':selection=RuntimeSelection('pyannote','redimnet','live',allow_experimental=True,optional_d1_refiner=True)
            elif mutation=='config':binding['live_config']={'fixture':'changed'}
            elif mutation=='raw':binding['raw_qualification_evidence']=dict(binding['raw_qualification_evidence'],evidence_sha256='9'*64)
            elif mutation=='first_eof':row['reviewed_feasibility']['complete_refiner_eof']=False
            else:row['reviewed_feasibility']['source']=dict(row['reviewed_feasibility']['source'],samples=123)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):m.validate_prerequisite_gate(gate,row,selection,binding,pins)
    def test_without_bridge_exact_source_still_required(self):
        gate,row,selection,binding,pins=fixture();gate.pop('live_composition_review')
        with self.assertRaises(ValueError):m.validate_prerequisite_gate(gate,row,selection,binding,pins)
        selection=RuntimeSelection('pyannote','titanet','saved',allow_experimental=True,optional_d1_refiner=True)
        row['stage']='initial';row['source']=gate['source']
        self.assertFalse(m.validate_prerequisite_gate(gate,row,selection,binding,pins))


if __name__=='__main__':unittest.main()
