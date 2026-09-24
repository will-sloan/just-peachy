"""Real Tk / fake backend seat controls. See README_SEATS.md."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import tkinter as tk
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
from prototype.app.ui import PrototypeUI,prepare_dpi_awareness
from prototype.app.beam_diagnostics import arrow_tip
from test_ui import StubController


class SeatsStub(StubController):
    def seats_apply(self,*args):self._record('seats_apply',*deepcopy(args))
    def seats_save_template(self,*args):self._record('seats_save_template',*deepcopy(args))


class SeatUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):prepare_dpi_awareness()
    def setUp(self):
        self.root=tk.Tk();self.c=SeatsStub();self.ui=PrototypeUI(self.root,self.c);self.root.update()
    def tearDown(self):
        if not self.ui._closed:self.ui.close();self.ui.poll()
    def open(self,mode='assigned_direction'):
        self.ui._choose_mode(mode);self.root.update();self.assertEqual(self.ui.page,'seats')
    def place(self,pid,angle):
        self.ui._seat_select(pid);x,y=arrow_tip(angle,*self.ui._seat_geometry());self.ui._seat_arc_press(SimpleNamespace(x=x,y=y))
    def test_real_entries_cancel_clear_and_template_load_are_draft_only(self):
        self.ui.show_modes();self.assertIn('mode_assigned_direction',self.ui.actions);self.assertIn('mode_assigned_hybrid',self.ui.actions)
        self.open();self.place('uuid-alex-1',30);self.ui.actions['seat_clear'].invoke();self.assertEqual(self.ui._seat_draft,[])
        self.assertEqual(self.c.calls,[]);self.ui.actions['seat_cancel'].invoke();self.assertEqual(self.c.calls,[])
        self.assertEqual(self.ui.page,'modes')
    def test_tap_drag_fine_regions_collision_and_explicit_apply(self):
        self.open();self.place('uuid-alex-1',30);self.place('uuid-alex-2',30)
        self.assertEqual(len(self.ui._seat_draft),2);self.assertEqual(str(self.ui.actions['seat_apply']['state']),'disabled')
        self.ui.actions['seat_ack'].invoke();self.assertEqual(str(self.ui.actions['seat_apply']['state']),'normal')
        self.ui.actions['seat_angle_plus'].invoke();self.assertEqual(self.ui._seat_draft[1]['angle_deg'],31.)
        self.ui.actions['seat_region_minus'].invoke();self.assertEqual(self.ui._seat_draft[1]['tolerance_deg'],24.)
        self.assertEqual(str(self.ui.actions['seat_apply']['state']),'disabled')
        x,y=arrow_tip(150,*self.ui._seat_geometry());self.ui._seat_name_drag(SimpleNamespace(x_root=x+self.ui.seat_canvas.winfo_rootx(),y_root=y+self.ui.seat_canvas.winfo_rooty()))
        self.assertEqual(self.ui._seat_draft[1]['angle_deg'],150.)
        self.ui.actions['seat_apply'].invoke();self.assertEqual(self.c.calls[-1][0],'seats_apply');self.assertEqual(self.ui.page,'captions')

    def test_same_projected_names_are_drawn_as_ambiguity_not_overlapping_labels(self):
        self.open();self.place('uuid-alex-1',90);self.place('uuid-alex-2',90)
        self.assertEqual(len(self.ui.seat_canvas.find_withtag('seat_name')),1)
        item=self.ui.seat_canvas.find_withtag('seat_name')[0]
        self.assertIn('2 seats',self.ui.seat_canvas.itemcget(item,'text'))
        self.assertTrue(self.ui.seat_canvas.find_withtag('seat_collision'))

    def test_load_strong_template_into_direction_mode_remains_fixed_and_unapplied(self):
        self.open('assigned_hybrid');self.open('assigned_direction')
        self.ui.snapshot['seating']=dict(template=dict(strength='strong',rows=[dict(person_id='uuid-alex-1',angle_deg=30.,tolerance_deg=25.)]))
        self.ui.actions['seat_load_template'].invoke();self.assertEqual(self.ui._seat_strength,'soft');self.assertEqual(self.c.calls,[])
    def test_hybrid_strength_motion_and_unsupported_tap(self):
        self.c.data['roster_compatibility']=[dict(id='uuid-alex-1',name='Alex',compatible_references=0),dict(id='uuid-alex-2',name='Alex',compatible_references=1)]
        self.ui.snapshot=self.c.snapshot();self.open('assigned_hybrid')
        self.assertEqual(str(self.ui.actions['seat_person_uuid-alex-1']['state']),'disabled')
        self.ui.actions['seat_strength'].invoke();self.assertEqual(self.ui._seat_strength,'strong')
        self.ui.actions['seat_moved'].invoke();self.assertEqual(self.c.calls[-1][0],'reset_spatial')
    def test_canvas_has_native_fold_region_and_portrait_client(self):
        self.open();self.place('uuid-alex-1',30);self.root.update()
        self.assertTrue(self.ui.seat_canvas.find_withtag('seat_region'));self.assertTrue(self.ui.seat_canvas.find_withtag('seat_point'))
        self.assertEqual((self.ui.measure_client()['physical_width'],self.ui.measure_client()['physical_height']),(480,800))


if __name__=='__main__':unittest.main()
