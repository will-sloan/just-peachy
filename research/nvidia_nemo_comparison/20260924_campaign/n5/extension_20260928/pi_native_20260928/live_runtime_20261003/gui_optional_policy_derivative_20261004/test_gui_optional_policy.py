"""Focused host-only GUI policy contract. See README_GUI_OPTIONAL_POLICY.md."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import uuid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-package', required=True, type=Path)
parser.add_argument('--output-root', required=True, type=Path)
parser.add_argument('--test', help='Run one named changed/failing contract only')
args = parser.parse_args()
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
handle = kernel.GetCurrentProcess()
kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
if not kernel.SetProcessAffinityMask(handle, 16384):
    raise ctypes.WinError(ctypes.get_last_error())
clocks = [ctypes.c_ulonglong() for _ in range(4)]
kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in clocks)):
    raise ctypes.WinError(ctypes.get_last_error())
output = args.output_root / ('gui-policy-check-' + uuid.uuid4().hex)
output.mkdir(exist_ok=False)
with (output/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
                   affinity_mask=16384, creation_filetime=clocks[0].value,
                   create_time=(clocks[0].value-116444736000000000)/10000000), stream)
    stream.flush(); os.fsync(stream.fileno())

# No project access or GUI imports precede the exact owner registration.
import ast
from dataclasses import replace
import hashlib
import importlib.util
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True
base = args.base_package.resolve()
manifest_raw = (base/'PACKAGE_MANIFEST.json').read_bytes()
assert hashlib.sha256(manifest_raw).hexdigest() == '8ec7f83c148d4cf5b043f0a8f044033b6881164b83f0c7bdb3d5af7757e0dcb8'
manifest = json.loads(manifest_raw)
for row in manifest['files']:
    if '/' not in row['path'] and row['path'].endswith('.py'):
        raw = (base/row['path']).read_bytes()
        assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
sys.path.insert(0, str(base))
source = Path(__file__).with_name('launcher.py')
spec = importlib.util.spec_from_file_location('gui_policy_candidate', source)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
import release_authorization as authorization
import optional_refiner_dispatch as dispatch
from profiles import RuntimeSelection, SessionPolicy

selection = RuntimeSelection('pyannote', 'titanet', 'live', allow_experimental=True,
                             revision_window_seconds=60, optional_d1_refiner=True)
measured_policy = SessionPolicy(300, False, 60, 30, 120, 60)


def ref(policy=measured_policy, selected=selection):
    return dict(selection=selected.validate(), policy=policy.validate(),
                path='/home/peachyprototype/JustPeachy/research/optional-reviewed.json',
                sha256='1'*64, asset_inventory_sha256='2'*64)


class PolicyContract(unittest.TestCase):
    def setUp(self):
        self.receipt = {'optional_refiner_admissions': [ref()]}
        self.auth = mock.patch.object(authorization, 'authorization', return_value=('production', self.receipt))
        self.guard = mock.patch.object(dispatch, 'reviewed_options', return_value=(ref(), b'fixture'))
        self.auth_mock = self.auth.start(); self.guard_mock = self.guard.start()
        self.addCleanup(self.auth.stop); self.addCleanup(self.guard.stop)

    def test_ordinary_defaults_do_not_consume_optional_proof(self):
        self.assertEqual(launcher.gui_session_policy({}, replace(selection, optional_d1_refiner=False)), SessionPolicy())
        self.auth_mock.assert_not_called(); self.guard_mock.assert_not_called()

    def test_unique_full_policy_reaches_unchanged_review_guard(self):
        self.assertEqual(launcher.gui_session_policy({}, selection), measured_policy)
        self.guard_mock.assert_called_once_with({}, selection, measured_policy)
        self.assertEqual(launcher.gui_policy_summary(measured_policy),
                         'Source 300 s; load 120 s; drain 60 s; backlog 30 s; cleanup 60 s.')

    def test_absent_wrong_selection_and_ambiguous_are_refused(self):
        for refs, selected in (([], selection), ([ref()], replace(selection, embedding='redimnet')),
                               ([ref(), ref(replace(measured_policy, max_drain_seconds=59))], selection)):
            with self.subTest(refs=len(refs), selected=selected.embedding):
                self.receipt['optional_refiner_admissions'] = refs
                with self.assertRaises(ValueError): launcher.gui_session_policy({}, selected)
        self.guard_mock.assert_not_called()

    def test_invalid_developer_and_changed_proof_are_refused(self):
        bad = ref(); bad['policy']['max_drain_seconds'] = True
        self.receipt['optional_refiner_admissions'] = [bad]
        with self.assertRaises(ValueError): launcher.gui_session_policy({}, selection)
        self.receipt['optional_refiner_admissions'] = [ref(SessionPolicy(3600, True, 60, 30, 120, 60))]
        with self.assertRaises(ValueError): launcher.gui_session_policy({}, selection)
        self.receipt['optional_refiner_admissions'] = [ref()]
        self.guard_mock.side_effect = ValueError('Changed proof or asset inventory')
        with self.assertRaises(ValueError): launcher.gui_session_policy({}, selection)

    def test_only_show_and_two_new_helpers_change(self):
        before = ast.parse((base/'launcher.py').read_bytes())
        after = ast.parse(source.read_bytes())
        allowed = {'gui_session_policy', 'gui_policy_summary'}
        self.assertEqual({n.name for n in after.body if isinstance(n, ast.FunctionDef)} -
                         {n.name for n in before.body if isinstance(n, ast.FunctionDef)}, allowed)
        old_show = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == 'show')
        after.body = [n for n in after.body if not isinstance(n, ast.FunctionDef) or n.name not in allowed]
        for index, node in enumerate(after.body):
            if isinstance(node, ast.FunctionDef) and node.name == 'show': after.body[index] = old_show
        self.assertEqual(ast.dump(before, include_attributes=False), ast.dump(after, include_attributes=False))

    def test_actual_withdrawn_tk_controls_and_start_policy(self):
        import tkinter as tk
        from tkinter import ttk, messagebox

        class Store:
            def history(self, **kwargs): return {'items': [], 'next_cursor': None}
        class Manager:
            binding = {}; unit_ownership = None; store = Store()
            process = None; export_task = None; latest_spatial = None; request = None
            def __init__(self): self.starts = []; self.closed = False
            def poll(self): return None
            def poll_export(self): return None
            def active_session_id(self): return None
            def show_spatial(self, visible): pass
            def start(self, chosen, policy, saved, **kwargs): self.starts.append((chosen, policy))
            def stop(self): pass
            def close(self): self.closed = True
        manager = Manager()
        real_tk = tk.Tk
        window = real_tk(); window.withdraw()
        def close_fixture():
            try: window.destroy()
            except tk.TclError: pass  # Normal Exit already destroyed the Tcl application.
        self.addCleanup(close_fixture)
        def children(widget):
            for child in widget.winfo_children():
                yield child; yield from children(child)
        def drive():
            widgets = list(children(window))
            experimental = next(w for w in widgets if isinstance(w, ttk.Checkbutton) and w.cget('text') == 'Enable experimental configurations')
            optional = next(w for w in widgets if isinstance(w, ttk.Checkbutton) and w.cget('text').startswith('Optional anonymous'))
            encoder = next(w for w in widgets if isinstance(w, ttk.Combobox) and tuple(w.cget('values')) == ('redimnet', 'titanet', 'anonymous'))
            revision = next(w for w in widgets if isinstance(w, ttk.Entry) and window.getvar(w.cget('textvariable')) == '30')
            start = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget('text') == 'Start')
            leave = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget('text') == 'Exit to desktop')
            self.assertEqual(str(optional.cget('state')), 'disabled')
            encoder.set('titanet'); experimental.invoke()
            self.assertEqual(str(revision.cget('state')), 'normal')
            self.assertEqual(str(optional.cget('state')), 'disabled')
            window.setvar(revision.cget('textvariable'), '60')
            self.assertEqual(str(optional.cget('state')), 'normal')
            optional.invoke()
            summaries = [window.getvar(w.cget('textvariable')) for w in widgets
                         if isinstance(w, ttk.Label) and w.cget('textvariable')]
            self.assertIn(launcher.gui_policy_summary(measured_policy), summaries)
            start.invoke(); self.assertEqual(manager.starts[-1][1], measured_policy)
            self.assertTrue(manager.starts[-1][0].optional_d1_refiner)
            optional.invoke(); start.invoke()
            self.assertEqual(manager.starts[-1][1], SessionPolicy())
            self.assertFalse(manager.starts[-1][0].optional_d1_refiner)
            self.receipt['optional_refiner_admissions'].append(ref(replace(measured_policy, max_drain_seconds=59)))
            window.setvar(revision.cget('textvariable'), '60')
            self.assertEqual(str(optional.cget('state')), 'disabled')
            leave.invoke(); self.assertTrue(manager.closed)
        window.mainloop = drive
        with mock.patch.object(tk, 'Tk', return_value=window), mock.patch.object(messagebox, 'askokcancel', return_value=True), mock.patch.object(messagebox, 'showerror', side_effect=AssertionError('Unexpected GUI refusal')):
            launcher.show(manager)


began = time.monotonic()
suite = (unittest.defaultTestLoader.loadTestsFromName(args.test, PolicyContract) if args.test else
         unittest.defaultTestLoader.loadTestsFromTestCase(PolicyContract))
result = unittest.TextTestRunner(verbosity=2).run(suite)
receipt = dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
               failures=len(result.failures), errors=len(result.errors), wall_seconds=time.monotonic()-began,
               native_executed=False, model_executed=False, tkinter='actual withdrawn host Tk; fake Manager only',
               source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
               base_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest())
with (output/'RESULT.json').open('x') as stream:
    json.dump(receipt, stream, indent=2); stream.flush(); os.fsync(stream.fileno())
print(json.dumps(dict(output=str(output), **receipt)))
raise SystemExit(0 if result.wasSuccessful() else 1)
