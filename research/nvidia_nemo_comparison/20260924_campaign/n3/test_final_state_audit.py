"""Unchanged-text final-state observation checks; README_GUI_RECOVERY.md."""
from types import SimpleNamespace
import unittest
from final_state_audit import observe_final_rows


class FinalStateAuditTests(unittest.TestCase):
    def fixture(self):
        first=dict(original=True)
        class Audit:
            spans={'s':dict(first_applied=first,first_final=None)}
            receipts=[]
            def observe(self,receipt,row,kind):
                self.receipts.append((receipt,row,kind));self.spans['s']['first_final']=receipt
        ui=SimpleNamespace(snapshot=dict(strict=False),_row_cache={'r':('', 'same words',False)},
            caption_text=SimpleNamespace(get=lambda *marks:'same words\n\n'),_marks={'r':('start','end')},
            _display_row=lambda row:('Unknown','same words',False),_history_order=[])
        return ui,[dict(id='r',span_ids=['s'],final=True)],Audit(),first

    def test_unchanged_widget_text_has_one_final_observation_without_new_first_display(self):
        ui,rows,audit,first=self.fixture();observe_final_rows(ui,rows,audit)
        self.assertIs(audit.spans['s']['first_applied'],first)
        self.assertEqual(len(audit.receipts),1)
        self.assertEqual(audit.receipts[0][2],'verified_Tk_final_state_after_render')
        observe_final_rows(ui,rows,audit);self.assertEqual(len(audit.receipts),1)

    def test_final_observation_rejects_caption_not_in_widget(self):
        ui,rows,audit,_=self.fixture();ui.caption_text.get=lambda *marks:'wrong words'
        with self.assertRaises(ValueError):observe_final_rows(ui,rows,audit)
        self.assertEqual(audit.receipts,[])

    def test_final_observation_cannot_fill_missing_first_display(self):
        ui,rows,audit,_=self.fixture();audit.spans['s']['first_applied']=None
        with self.assertRaises(ValueError):observe_final_rows(ui,rows,audit)


if __name__=='__main__':unittest.main(verbosity=2)
