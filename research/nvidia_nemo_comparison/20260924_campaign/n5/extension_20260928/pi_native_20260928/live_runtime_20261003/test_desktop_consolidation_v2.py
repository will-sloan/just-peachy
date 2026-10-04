"""Pinned production metadata imports only; README_DESKTOP_CONSOLIDATION_V2.md."""
import ast
import builtins
from pathlib import Path
import sys
import symtable
import tempfile
import unittest
from unittest.mock import patch

import desktop_activation_action as reviewed
import desktop_consolidation_action as original
import desktop_consolidation_action_v2 as target
import test_guarded_activation as fixture

FROZEN12=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/interpreter-derivative-77e2ff9f17964e0893411a39f781bc7e/package')


class ConsolidationImports(unittest.TestCase):
    def test_final_external_helpers_have_no_unbound_global_references(self):
        for filename in ('desktop_consolidation_action_v2.py', 'desktop_activation_action.py',
                         'launch_production_idle_action.py', 'production_idle_control.py'):
            path=Path(__file__).with_name(filename)
            table=symtable.symtable(path.read_text(),str(path),'exec')
            defined={s.get_name() for s in table.get_symbols()
                     if s.is_assigned() or s.is_imported() or s.is_namespace()}
            # Only these two names are supplied by the reviewed action dispatcher.
            defined.update(set(dir(builtins))|{'__name__','__file__','PAYLOAD','BASELINE'})
            def inspect(scope):
                for symbol in scope.get_symbols():
                    if symbol.is_global() and symbol.is_referenced():
                        self.assertIn(symbol.get_name(),defined,
                                      (filename,scope.get_name(),symbol.get_name()))
                for child in scope.get_children():inspect(child)
            inspect(table)

    def test_reviewed_import_code_and_shortcut_transaction_are_unchanged(self):
        def definition(module,name):
            node=next(n for n in ast.parse(Path(module.__file__).read_text()).body if getattr(n,'name',None)==name)
            return ast.dump(node,include_attributes=False)
        for name in ('module_bytes','VerifiedImports'):self.assertEqual(definition(target,name),definition(reviewed,name))
        for name in ('archive_shortcuts','restore_shortcuts'):self.assertEqual(definition(target,name),definition(original,name))
        self.assertEqual(target.OWNED,original.OWNED);self.assertEqual(target.STARTUP,original.STARTUP)

    def test_actual_frozen12_metadata_imports_restore_host_namespace(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(fixture,'PACKAGE',FROZEN12):
            _,package,desktop,old,manifest,_,payload=fixture.ActivationTests().fixture(directory)
            with patch.dict(sys.modules):
                for name in target.IMPORTS:sys.modules.pop(name,None)
                with target.VerifiedImports(package,manifest) as imported:
                    accepted=sys.modules['release_authorization'].validate_acceptance(
                        reviewed.strict((package/'PRODUCTION_ACCEPTANCE.json').read_bytes()),
                        reviewed.strict((package/'BINDING.json').read_bytes()))
                    self.assertEqual(accepted['target'],str(package))
                    self.assertEqual(set(imported.origins),set(target.IMPORTS))
                for name in target.IMPORTS:self.assertNotIn(name,sys.modules)
            self.assertEqual(desktop.read_bytes(),old)


if __name__=='__main__':unittest.main()
