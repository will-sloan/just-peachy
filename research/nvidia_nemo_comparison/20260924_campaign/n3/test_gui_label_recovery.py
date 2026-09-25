"""Prove the GUI rescue changes only corrupted expected labels; README_GUI_RECOVERY.md."""
import ast
from pathlib import Path
import unittest


class GuiLabelRecoveryTests(unittest.TestCase):
    def test_only_expected_literals_and_module_identifier_change(self):
        here=Path(__file__).resolve().parent
        old=(here/'gui.py').read_text(encoding='utf-8')
        bad=' \u00c2\u00b7 assumed'
        self.assertEqual(old.count(bad),2)
        expected=old.replace(bad,r' \u00b7 assumed').replace(
            "MODULE = 'research.nvidia_nemo_comparison.20260924_campaign.n3.gui'",
            "MODULE = 'research.nvidia_nemo_comparison.20260924_campaign.n3.gui_labels'")
        self.assertEqual((here/'gui_labels.py').read_text(encoding='utf-8'),expected)

    def test_both_assertions_use_the_real_unicode_suffix(self):
        tree=ast.parse((Path(__file__).with_name('gui_labels.py')).read_text(encoding='utf-8'))
        values=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
        self.assertEqual(values.count(' \u00b7 assumed'),2)
        self.assertNotIn(' \u00c2\u00b7 assumed',values)
        label='Research fixture \u00b7 assumed'
        self.assertTrue(label.endswith(' \u00b7 assumed'))
        self.assertFalse(label.endswith(' \u00c2\u00b7 assumed'))


if __name__=='__main__':unittest.main(verbosity=2)
