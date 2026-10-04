"""Changed allocation guard only, no model execution. See README.md."""
import ast
import importlib.util
import os
from pathlib import Path
import sys
import unittest

FROZEN=Path(os.environ['JP_FROZEN08_HOST'])
sys.path.insert(0,str(FROZEN))
from profiles import RuntimeSelection,SessionPolicy
path=Path(__file__).parent/'runtime_derivative09/optional_refiner_qualification.py'
spec=importlib.util.spec_from_file_location('allocation09_under_test',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class Allocation(unittest.TestCase):
    def test_fully_reserved_raw_live300(self):
        selection=RuntimeSelection('pyannote','titanet','live',allow_experimental=True,optional_d1_refiner=True)
        policy=SessionPolicy(300,max_drain_seconds=60,max_backlog_seconds=30)
        plan=module.qualification_output_plan({'raw_adapter_enabled':True},selection,policy,'followup_policy')
        self.assertEqual(plan['audio_and_metadata_bytes'],202684712)
        self.assertEqual(plan['additional_primary_allocation_bytes'],106954752)
        self.assertEqual(plan['native_maximum_output_bytes'],330610984)
        self.assertEqual(plan['mode'],'raw_processed')
        self.assertGreater(plan['native_maximum_output_bytes'],256*1024**2)
        with self.assertRaises(ValueError):module.qualification_output_plan({'raw_adapter_enabled':True},selection,policy,'initial')
    def test_saved_initial_stays256(self):
        selection=RuntimeSelection('pyannote','titanet','saved',allow_experimental=True,optional_d1_refiner=True)
        plan=module.qualification_output_plan({'raw_adapter_enabled':True},selection,SessionPolicy(45,max_drain_seconds=60),'initial')
        self.assertEqual(plan['native_maximum_output_bytes'],256*1024**2)
        self.assertEqual(plan['mode'],'processed')
        self.assertLess(plan['computed_output_bytes'],plan['native_maximum_output_bytes'])
    def test_all_other_admission_functions_unchanged(self):
        before=ast.parse((FROZEN/'optional_refiner_qualification.py').read_text())
        after=ast.parse(path.read_text())
        funcs=lambda tree:{node.name:ast.dump(node,include_attributes=False) for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
        old,new=funcs(before),funcs(after)
        self.assertEqual(set(new)-set(old),{'qualification_output_plan'})
        for name,value in old.items():
            if name!='initialize':self.assertEqual(new[name],value,name)
        self.assertNotEqual(new['initialize'],old['initialize'])


if __name__=='__main__':unittest.main()
