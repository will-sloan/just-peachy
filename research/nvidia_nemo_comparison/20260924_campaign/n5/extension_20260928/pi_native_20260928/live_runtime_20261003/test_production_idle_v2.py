"""Focused external idle V2 contract; README_PRODUCTION_IDLE_V2.md."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import uuid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-package', type=Path, required=True)
parser.add_argument('--output-root', type=Path, required=True)
parser.add_argument('--test', help='Only one named changed/failing contract')
args = parser.parse_args()
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
handle = kernel.GetCurrentProcess()
kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
if not kernel.SetProcessAffinityMask(handle, 16384): raise ctypes.WinError(ctypes.get_last_error())
times = [ctypes.c_ulonglong() for _ in range(4)]
kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
if not kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in times)): raise ctypes.WinError(ctypes.get_last_error())
output = args.output_root/('idle-v2-check-'+uuid.uuid4().hex)
output.mkdir(exist_ok=False)
with (output/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
        affinity_mask=16384, creation_filetime=times[0].value,
        create_time=(times[0].value-116444736000000000)/10000000), stream)
    stream.flush(); os.fsync(stream.fileno())

import ast
from dataclasses import replace
import hashlib
import importlib.util
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True
here = Path(__file__).resolve().parent
base = args.base_package.resolve()
assert hashlib.sha256((base/'PACKAGE_MANIFEST.json').read_bytes()).hexdigest() == '8ec7f83c148d4cf5b043f0a8f044033b6881164b83f0c7bdb3d5af7757e0dcb8'
candidate = here/'gui_optional_policy_derivative_20261004/launcher.py'
assert hashlib.sha256(candidate.read_bytes()).hexdigest() == 'a520e51e6bf033fc06d2fe60c708f047f8e357bfe3de1dbc691410abf0268fb5'
sys.path.insert(0, str(base))
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
controller = load('idle_controller_v2_under_test', here/'production_idle_control_v2.py')
launcher = load('idle_gui_under_test', candidate)
import release_authorization as authorization
import optional_refiner_dispatch as dispatch
from profiles import RuntimeSelection, SessionPolicy


class IdleV2(unittest.TestCase):
    def test_preserved_identity_watchdog_and_copy_guards(self):
        before_raw = (here/'production_idle_control.py').read_bytes()
        self.assertEqual(hashlib.sha256(before_raw).hexdigest(), '109fafea3ae057ddadd417be36b63b973969f7fddc685329e38cad00450e739d')
        old = ast.parse(before_raw); new = ast.parse((here/'production_idle_control_v2.py').read_bytes())
        old_defs = {n.name: n for n in old.body if isinstance(n, ast.FunctionDef)}
        new_defs = {n.name: n for n in new.body if isinstance(n, ast.FunctionDef)}
        self.assertEqual(set(new_defs)-set(old_defs), {'inspect_optional_policy'})
        for name, node in old_defs.items():
            if name != '_main': self.assertEqual(ast.dump(node), ast.dump(new_defs[name]), name)
        old_main = ast.get_source_segment(before_raw.decode(), old_defs['_main'])
        new_raw = (here/'production_idle_control_v2.py').read_text()
        new_main = ast.get_source_segment(new_raw, new_defs['_main'])
        # Critical unchanged main boundaries surround the added GUI-only inspection.
        for start, end in (("        process=subprocess.Popen", "        todo=['.']"),
                           ("        process.wait(timeout=", "    passed=")):
            self.assertEqual(old_main[old_main.index(start):old_main.index(end)],
                             new_main[new_main.index(start):new_main.index(end)])

    def test_action_embeds_exact_controller_and_dispatch_only_adds_optin(self):
        before_raw = (here/'launch_production_idle_action.py').read_bytes()
        self.assertEqual(hashlib.sha256(before_raw).hexdigest(), '1d946305f3955e927cc7fb74eb5c7911ed9afcdd4725853864040bb2d6a3bed8')
        old = ast.parse(before_raw); new = ast.parse((here/'launch_production_idle_action_v2.py').read_bytes())
        def literal(tree): return next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CONTROL_SOURCE' for t in n.targets))
        current = literal(new)
        self.assertEqual(ast.literal_eval(current.value), (here/'production_idle_control_v2.py').read_text())
        new.body[new.body.index(current)] = literal(old)
        new.body[0] = old.body[0]
        function = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == 'dispatch')
        condition = function.body.pop(0)
        self.assertIsInstance(condition, ast.If)
        self.assertIn('verify_optional_policy', ast.dump(condition))
        self.assertEqual(ast.dump(old), ast.dump(new))

    def test_enabled_start_refused_before_any_other_command(self):
        calls = []
        def send(*args): calls.append(args); return 0
        with self.assertRaisesRegex(ValueError, 'Start must remain disabled'):
            controller.inspect_optional_policy(send, tuple, '.start')
        self.assertEqual(calls, [('.start', 'instate', 'disabled')])

    def run_tk_contract(self, wrong_policy=False):
        import tkinter as tk
        from tkinter import ttk
        selected = RuntimeSelection('pyannote', 'titanet', 'live', allow_experimental=True,
                                    revision_window_seconds=60, optional_d1_refiner=True)
        policy = SessionPolicy(300, False, 60, 31 if wrong_policy else 30, 120, 60)
        ref = dict(selection=selected.validate(), policy=policy.validate(),
            path='/home/peachyprototype/JustPeachy/research/test-measured-proof.json', sha256='1'*64,
            asset_inventory_sha256='2'*64)
        class Store:
            def history(self, **kwargs): return {'items': [], 'next_cursor': None}
        class Manager:
            binding = {}; unit_ownership = None; store = Store(); process = None
            export_task = None; latest_spatial = None; request = None
            def __init__(self): self.closed = False; self.starts = 0
            def poll(self): return None
            def poll_export(self): return None
            def active_session_id(self): return None
            def show_spatial(self, value): pass
            def stop(self): pass
            def start(self, *args, **kwargs): self.starts += 1; raise AssertionError('Start is forbidden')
            def close(self): self.closed = True
        manager = Manager(); window = tk.Tk(); window.withdraw(); commands = []; result = []
        def children(widget):
            for child in widget.winfo_children(): yield child; yield from children(child)
        def drive():
            widgets = list(children(window))
            start = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget('text') == 'Start')
            leave = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget('text') == 'Exit to desktop')
            start.state(['disabled'])
            def send(*items):
                commands.append(items)
                if items == (str(start), 'invoke'): raise AssertionError('Driver must never invoke Start')
                return window.tk.call(*items)
            try:
                if wrong_policy:
                    with self.assertRaisesRegex(ValueError, 'checked optional policy differs'):
                        controller.inspect_optional_policy(send, window.tk.splitlist, str(start))
                else: result.append(controller.inspect_optional_policy(send, window.tk.splitlist, str(start)))
                self.assertTrue(start.instate(['disabled'])); self.assertEqual(manager.starts, 0)
                leave.invoke(); self.assertTrue(manager.closed)
            finally:
                try: window.destroy()
                except tk.TclError: pass
        window.mainloop = drive
        with mock.patch.object(tk, 'Tk', return_value=window), mock.patch.object(authorization, 'authorization',
                return_value=('production', {'optional_refiner_admissions': [ref]})), mock.patch.object(dispatch, 'reviewed_options', return_value=(ref, b'fixture')):
            launcher.show(manager)
        if not wrong_policy:
            self.assertEqual(result[0]['checked_policy_summary'], 'Source 300 s; load 120 s; drain 60 s; backlog 30 s; cleanup 60 s.')
            self.assertEqual(result[0]['unchecked_policy_summary'], launcher.gui_policy_summary(SessionPolicy()))
            self.assertFalse(result[0]['optional_final_checked']); self.assertGreater(result[0]['start_disabled_checks'], 100)

    def test_actual_tk_optional_toggle_ordinary_restore_and_exit_without_start(self): self.run_tk_contract()
    def test_actual_tk_wrong_reviewed_policy_is_refused(self): self.run_tk_contract(wrong_policy=True)


began = time.monotonic()
suite = (unittest.defaultTestLoader.loadTestsFromName(args.test, IdleV2) if args.test else
         unittest.defaultTestLoader.loadTestsFromTestCase(IdleV2))
result = unittest.TextTestRunner(verbosity=2).run(suite)
row = dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
           errors=len(result.errors), failures=len(result.failures), seconds=time.monotonic()-began,
           native_executed=False, models_started=False, tkinter='actual withdrawn host Tk; fake Manager',
           controller_sha256=hashlib.sha256((here/'production_idle_control_v2.py').read_bytes()).hexdigest(),
           action_sha256=hashlib.sha256((here/'launch_production_idle_action_v2.py').read_bytes()).hexdigest())
with (output/'RESULT.json').open('x') as stream:
    json.dump(row, stream, indent=2); stream.flush(); os.fsync(stream.fileno())
print(json.dumps(dict(output=str(output), **row)))
raise SystemExit(0 if result.wasSuccessful() else 1)
