"""Pure file/AST fixtures only; never import hardware APIs. README_S45_HARDWARE_GATES.md."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import types
import unittest

from s45_common import SIM, BANK, LIMITS, now, read, save, bind


def pure_helpers(folder):
    path=Path(__file__).with_name('s45_hardware.py')
    tree=ast.parse(path.read_text(encoding='utf-8'))
    names={'verified_restoration','manifest_path_for_cases','verify_prior_restorations','check_global_attempts','close_started_pass','check_physical_budget'}
    module=types.ModuleType('pure_s45_hardware_gates')
    module.__dict__.update(Path=Path,SIM=SIM,BANK=BANK,REPORT=folder/'report',HARDWARE=folder/'hardware',LIMITS=LIMITS,read=read,save=save,bind=bind,now=now)
    for n in tree.body:
        if isinstance(n,ast.FunctionDef) and n.name in names:
            exec(compile(ast.Module(body=[n],type_ignores=[]),str(path),'exec'),module.__dict__)
    return module


class GatesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.h=pure_helpers(self.root)
        self.h.REPORT.mkdir();self.h.HARDWARE.mkdir()

    def restoration(self,batch='a'):
        folder=self.h.HARDWARE/batch;folder.mkdir(exist_ok=True)
        initial={'identity':{'I2S_INPUT_PACKED':[0],'USB_BIT_DEPTH':[16,16]},'settings':{'gain':[1.]},'observe_only':{'unchanged':[7]},'usb_bits':[16,16]}
        restored={'status':'PASS','exact_recorded_configuration_match':True,
                  'hardware_lease_released':True,'audio_handles_closed':True,'telemetry_process_closed':True,'packed_input_disabled':True,
                  'readback':{k:copy.deepcopy(initial[k]) for k in ['identity','settings','observe_only']}}
        save(folder/'initial_state.json',initial);save(folder/'restoration.json',restored)
        return folder,restored

    def attempt(self,batch,cid='S45_01_01',status='FAIL',sha='input'):
        folder=self.h.HARDWARE/batch/cid;folder.mkdir(parents=True,exist_ok=True)
        save(folder/'case_result.json',{'batch':batch,'case_id':cid,'status':status,'input_scene_sha256':sha})

    def test_manifest_routing_reference_only_and_reject_mixed_duplicates(self):
        self.assertEqual(self.h.manifest_path_for_cases(['S45_REF_01']).name,'REFERENCE_SCENE_MANIFEST.json')
        self.assertEqual(self.h.manifest_path_for_cases(['S45_01_01']).name,'SCENE_MANIFEST.json')
        self.assertEqual(self.h.manifest_path_for_cases(['transport_regression']).name,'inputs_manifest.json')
        for ids in [[],['S45_REF_01','S45_01_01'],['transport_regression','S45_01_01'],['S45_01_01','S45_01_01']]:
            with self.assertRaises(AssertionError):self.h.manifest_path_for_cases(ids)

    def test_one_failure_allows_only_one_retry(self):
        scenes={'S45_01_01':{'canonical_audio':{'sha256':'input'}}}
        self.h.check_global_attempts(list(scenes),scenes,'first')
        self.attempt('first');self.h.check_global_attempts(list(scenes),scenes,'second')
        self.attempt('second')
        with self.assertRaisesRegex(AssertionError,'attempt limit'):self.h.check_global_attempts(list(scenes),scenes,'third')

    def test_previously_accepted_or_changed_input_cannot_replay(self):
        scenes={'S45_01_01':{'canonical_audio':{'sha256':'input'}}}
        self.attempt('first',status='PASS')
        with self.assertRaisesRegex(AssertionError,'Already accepted'):self.h.check_global_attempts(list(scenes),scenes,'second')
        scenes['S45_01_01']['canonical_audio']['sha256']='changed'
        with self.assertRaisesRegex(AssertionError,'identity changed'):self.h.check_global_attempts(list(scenes),scenes,'second')

    def test_charged_attempts_without_case_receipts_still_count(self):
        scenes={'S45_01_01':{'canonical_audio':{'sha256':'input'}}}
        save(self.h.REPORT/'physical_ledger.json',{'passes':[{'case_id':'S45_01_01','batch':b,'status':'FAIL','charged_playback_s':45} for b in ['a','b']]})
        with self.assertRaisesRegex(AssertionError,'attempt limit'):self.h.check_global_attempts(list(scenes),scenes,'c')

    def test_missing_restoration_detected_from_each_acquisition_evidence(self):
        for name in ['initial_state.json','owner_acquired.json']:
            folder=self.h.HARDWARE/name;folder.mkdir();save(folder/name,{})
            with self.assertRaisesRegex(AssertionError,'Missing restoration'):self.h.verify_prior_restorations()

    def test_missing_restoration_detected_from_ledger_without_folder(self):
        save(self.h.REPORT/'physical_ledger.json',{'passes':[{'batch':'crashed','case_id':'C','status':'STARTED','charged_playback_s':45}]})
        with self.assertRaisesRegex(AssertionError,'Missing restoration'):self.h.verify_prior_restorations()

    def test_PASS_still_requires_exact_readback_and_close_flags(self):
        folder,good=self.restoration()
        self.assertEqual(len(self.h.verify_prior_restorations()),1)
        for key in ['hardware_lease_released','audio_handles_closed','telemetry_process_closed','packed_input_disabled','exact_recorded_configuration_match']:
            bad=copy.deepcopy(good);bad[key]=False;save(folder/'restoration.json',bad)
            with self.assertRaises(AssertionError):self.h.verify_prior_restorations()
        bad=copy.deepcopy(good);bad['readback']['settings']['gain']=[2];save(folder/'restoration.json',bad)
        with self.assertRaises(AssertionError):self.h.verify_prior_restorations()

    def test_bound_recovery_requires_original_failure_hash(self):
        folder,good=self.restoration();original={'status':'FAIL','error':'fixture failure'}
        save(folder/'restoration.json',original)
        recovery={**good,'original_failure':original,'original_failure_binding':bind(folder/'restoration.json')}
        save(folder/'restoration_recovery.json',recovery)
        self.assertTrue(self.h.verify_prior_restorations()[0]['recovery_used'])
        recovery['original_failure_binding']['sha256']='0'*64;save(folder/'restoration_recovery.json',recovery)
        with self.assertRaises(ValueError):self.h.verify_prior_restorations()

    def test_restored_but_unresolved_started_row_blocks(self):
        self.restoration()
        save(self.h.REPORT/'physical_ledger.json',{'passes':[{'batch':'a','case_id':'C','status':'STARTED','charged_playback_s':45}]})
        with self.assertRaisesRegex(AssertionError,'Unresolved'):self.h.verify_prior_restorations()
        self.h.close_started_pass('a','C','fixture decoder failure',{'captured_frames':123})
        self.assertEqual(len(self.h.verify_prior_restorations()),1)

    def test_exception_closure_preserves_charge_and_other_rows(self):
        other={'batch':'other','case_id':'D','status':'STARTED','charged_playback_s':100}
        closed={'batch':'a','case_id':'done','status':'PASS','charged_playback_s':20}
        save(self.h.REPORT/'physical_ledger.json',{'passes':[{'batch':'a','case_id':'C','status':'STARTED','charged_playback_s':45},other,closed]})
        self.h.close_started_pass('a','C','fixture capture failure',{'captured_frames':200})
        rows=read(self.h.REPORT/'physical_ledger.json')['passes']
        self.assertEqual(rows[0]['status'],'FAIL');self.assertEqual(rows[0]['charged_playback_s'],45)
        self.assertEqual(rows[0]['captured_frames'],200);self.assertEqual(rows[1],other);self.assertEqual(rows[2],closed)
        self.assertIsNone(self.h.close_started_pass('a','done','do not alter'))

    def test_pass_and_active_time_caps_include_failed_diagnostics(self):
        ledger={'passes':[{'charged_playback_s':1,'status':'FAIL'} for _ in range(320)]}
        with self.assertRaises(AssertionError):self.h.check_physical_budget(ledger,1)
        ledger={'passes':[{'charged_playback_s':16155,'status':'FAIL'}]}
        self.h.check_physical_budget(ledger,45)
        with self.assertRaises(AssertionError):self.h.check_physical_budget(ledger,46)
        for duration in [0,-1,float('nan')]:
            with self.assertRaises(AssertionError):self.h.check_physical_budget({'passes':[]},duration)

    def test_global_gates_are_inside_lease_before_control_mutation(self):
        tree=ast.parse(Path(__file__).with_name('s45_hardware.py').read_text(encoding='utf-8'))
        run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        lines={}
        for n in ast.walk(run):
            if isinstance(n,ast.Call):
                name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
                lines.setdefault(name,[]).append(n.lineno)
        self.assertLess(min(lines['locking']),min(lines['verify_prior_restorations']))
        self.assertLess(min(lines['verify_prior_restorations']),min(lines['Control']))
        self.assertLess(min(lines['check_global_attempts']),min(lines['reset']))


if __name__=='__main__':unittest.main(verbosity=2)
