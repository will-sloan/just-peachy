"""Host-only GUI driver contracts, no Tk instance. README_NATIVE_GUI_DRIVER.md."""
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import native_gui_driver as driver


class Widget:
    def __init__(self, kind='TFrame', text='', parent=None):
        self.kind,self.text,self.master=kind,text,parent
        self.children=[]
        if parent is not None:parent.children.append(self)
    def winfo_children(self):return self.children
    def winfo_class(self):return self.kind
    def cget(self,key):return self.text


class DriverTests(unittest.TestCase):
    def test_plan_cannot_invent_missing_gui_controls(self):
        plan=driver.validate_plan({},'inspect',5)
        self.assertEqual(plan['input_source'],'live')
        with self.assertRaises(ValueError):driver.validate_plan(dict(refinement_period_seconds=6),'inspect',5)
        with self.assertRaises(ValueError):driver.validate_plan(dict(input_source='saved'),'capture-discard',5)
        with self.assertRaises(ValueError):driver.validate_plan({},'replay-discard',5,saved_session_id='x')
        with self.assertRaises(ValueError):driver.validate_plan({},'inspect',float('nan'))

    def test_save_discard_require_actual_successful_nested_closure(self):
        closure=dict(returncode=0,direct_child_reaped=True,stdout_reader_joined=True,
            nested_source=dict(closed=True),result=dict(session_id='synthetic',failure=None))
        self.assertEqual(driver.require_closed(closure),'synthetic')
        for change in (dict(returncode=1),dict(direct_child_reaped=False),dict(output_error='bounded fault'),
                       dict(nested_source=dict(closed=False)),dict(result=dict(session_id='synthetic',failure='failed'))):
            with self.assertRaises(RuntimeError):driver.require_closed(dict(closure,**change))

    def test_widget_selection_requires_unique_exact_label_relationship(self):
        root=Widget();heading=Widget('TLabel','Diarizer',root);control=Widget('TCombobox',parent=root)
        self.assertIs(driver.labeled_control(root,'Diarizer','TCombobox'),control)
        with self.assertRaises(ValueError):driver.named_widget(root,'Start')
        Widget('TLabel','Diarizer',root)
        with self.assertRaises(ValueError):driver.labeled_control(root,'Diarizer','TCombobox')

    def test_consent_is_explicit_programmatic_and_never_a_touch_claim(self):
        events=[]
        manager=types.SimpleNamespace(process=None)
        runner=driver.GuiDriver(manager,dict(input_source='live'),'capture-discard',5,Path('synthetic'),
            lambda path,row:events.append(row))
        self.assertTrue(runner.consent('Temporary audio','Capture?'))
        self.assertTrue(events[-1]['programmatic'])
        self.assertFalse(events[-1]['physical_touch'])
        self.assertFalse(runner.consent('Unrecognized permission','Unexpected'))
        self.assertIsNotNone(runner.failure)
        manager.process=object()
        with self.assertRaises(RuntimeError):runner.exit()

    def test_scroll_reveal_selects_containing_tab_and_refuses_clipped_control(self):
        events=[]
        runner=driver.GuiDriver(types.SimpleNamespace(process=None),{},'inspect',5,Path('synthetic'),
            lambda path,row:events.append(row))
        runner.root=types.SimpleNamespace(update_idletasks=lambda:None)
        notebook=types.SimpleNamespace(winfo_class=lambda:'TNotebook',select=mock.Mock())
        tab=types.SimpleNamespace(master=notebook,winfo_class=lambda:'TFrame')
        canvas=types.SimpleNamespace(master=tab,winfo_class=lambda:'Canvas',
            winfo_rooty=lambda:100,winfo_height=lambda:200,yview=lambda:(.5,.7))
        body=types.SimpleNamespace(master=canvas,_scroll_viewport=canvas,winfo_class=lambda:'TFrame',
            winfo_rooty=lambda:100,winfo_height=lambda:1000)
        top=[600]
        def scroll(fraction):top[0]-=fraction*1000
        canvas.yview_moveto=scroll
        control=types.SimpleNamespace(master=body,winfo_rooty=lambda:top[0],winfo_height=lambda:40)
        runner.reveal(control)
        notebook.select.assert_called_once_with(tab)
        self.assertEqual(events[-1]['kind'],'scroll-visible')
        self.assertGreaterEqual(top[0],100)
        self.assertLessEqual(top[0]+40,300)
        top[0]=600
        control.winfo_height=lambda:300
        with self.assertRaisesRegex(RuntimeError,'wholly'):runner.reveal(control)

    def test_host_entry_refuses_before_tk_or_application_import(self):
        args=['driver','--binding','missing','--package-manifest-sha256','0'*64,
            '--unit','synthetic','--unit-ownership','missing','--owner-directory','missing',
            '--data-root','missing','--selection','missing','--selection-sha256','0'*64]
        before=set(sys.modules)
        with mock.patch.object(sys,'argv',args),mock.patch.object(driver.platform,'system',return_value='Windows'):
            with self.assertRaisesRegex(RuntimeError,'cannot open a PC window'):driver.main()
        self.assertFalse(any(name.startswith('tkinter') or name.startswith('app.') for name in set(sys.modules)-before))


if __name__=='__main__':unittest.main()
