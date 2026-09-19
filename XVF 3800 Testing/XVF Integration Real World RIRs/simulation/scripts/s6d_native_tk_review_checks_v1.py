"""Independent no-Tk review probes; see README_S6D_NATIVE_TK_REVIEW_CHECKS_V1.md."""
from __future__ import annotations
import argparse
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def selected_class(path, name, methods, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    cls = deepcopy(cls)
    cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in methods]
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(path), 'exec'), namespace)
    return namespace[name]


class Widget:
    def __init__(self): self.text = ''
    def configure(self, **kw): pass
    def delete(self, *a): self.text = ''
    def insert(self, index, content): self.text = content
    def see(self, *a): pass
    def get(self, *a): return self.text


class Tests(unittest.TestCase):
    def stream(self):
        views = []
        for mode, ids in [('T0', ()), ('T1', ('a',)), ('T2', ('a', 'b'))]:
            settings = S.S6DSettings(transcript_mode=mode, selected_profile_ids=ids)
            views.append(dict(name=mode, settings=settings, presentation=S.PresentationState(settings), inbox=S.EventInbox(64), input_digest=hashlib.sha256(), input_count=0, forwarded=0, consumer_closed=False))
        fan = H.LiveFanout(views, C.PipelineEvent, clock=lambda: 20.)
        producer = S.PresentationState(S.S6DSettings())
        serial = [0]
        def send(kind, payload):
            serial[0] += 1
            payload = dict(payload, publication_sequence=serial[0], publication_monotonic_sec=10.+serial[0]/100, pilot_publication_monotonic_sec=10.+serial[0]/100, session_id='session_A')
            fan.accept(C.PipelineEvent(kind, 1., payload))
            shown = producer.consume(kind, payload, now=15.)
            if shown is not None: send('s6d_display', shown)
        send('source_started', {})
        return views, fan, send

    def render_probe(self):
        if hasattr(self, 'render_rows'): return self.render_rows
        views, fan, send = self.stream()
        send('s6d_text_ready', dict(utterance_id='u', text='first words', source_start_sec=0., source_end_sec=1., final=False))
        send('transcript_final', dict(utterance_id='u', text='first words revised', source_start_sec=0., source_end_sec=1., latest_known_profile_id='a', latest_naming_state='confirmed', speaker='A'))
        base = selected_class(APP/'gui.py', 'EdgeSpeechWindow', {'_consume_s6d_display', '_render_transcript'}, dict(time=time))
        tree = ast.parse(HELPER.read_text(encoding='utf-8-sig'))
        execute = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'execute_gui')
        window = deepcopy(next(n for n in execute.body if isinstance(n, ast.ClassDef) and n.name == 'Window'))
        namespace = dict(gui=SimpleNamespace(EdgeSpeechWindow=base), output=OUT/self._testMethodName, fanout=fan, hashlib=hashlib, time=time, json=json, fail=lambda e: (_ for _ in ()).throw(e))
        namespace['output'].mkdir()
        exec(compile(ast.fix_missing_locations(ast.Module(body=[window], type_ignores=[])), str(HELPER), 'exec'), namespace)
        w = namespace['Window'].__new__(namespace['Window'])
        w.engine = H.ViewFacade(SimpleNamespace(), views[0], fan)
        w._s6d_render_handle = None; w._s6d_gui_session_id = 'session_A'; w.s6d_rows = {}
        w.s6d_status = SimpleNamespace(set=lambda x: None); w.s6d_full_view = SimpleNamespace(get=lambda: False); w.transcript = Widget()
        payloads = []
        try:
            while not views[0]['inbox'].empty():
                event = views[0]['inbox'].get()
                if event.event_type == 's6d_display':
                    payloads.append(deepcopy(event.payload)); w._consume_s6d_display(event.payload)
        finally:
            if w._s6d_render_handle is not None: w._s6d_render_handle.close()
        rows = [json.loads(x) for x in (namespace['output']/'views'/'T0'/'s6d_gui_render.jsonl').read_text().splitlines()]
        OBS[self._testMethodName] = dict(payloads=payloads, receipts=rows)
        self.render_rows = (payloads, rows)
        return payloads, rows

    def test_render_receipt_binds_trigger_not_dispatcher_frontier(self):
        payloads, rows = self.render_probe()
        self.assertEqual(len(rows), 2)
        for payload, row in zip(payloads, rows):
            for field in ('session_id', 'source_native_publication_sequence', 'source_native_publication_monotonic_sec', 'causal_view_input_count'):
                self.assertEqual(row.get(field), payload[field], field)

    def test_actual_widget_content_can_be_verified_without_reconstruction(self):
        _, rows = self.render_probe()
        for row in rows:
            self.assertIsInstance(row.get('widget_text'), str)
            self.assertEqual(hashlib.sha256(row['widget_text'].encode()).hexdigest(), row['widget_text_sha256'])
            self.assertIn('scanout', row['clock_scope'].lower())

    def test_window_construction_failure_releases_owned_resources(self):
        folder = OUT/self._testMethodName; folder.mkdir()
        class Root:
            def __init__(self): self.destroyed = False
            def destroy(self): self.destroyed = True
            def title(self, x): pass
        root = Root()
        class Gallery:
            def score(self, value): return []
        gallery = Gallery(); original = gallery.score
        class BadWindow:
            def __init__(self, *a, **kw): raise RuntimeError('synthetic window setup failure')
        engine = SimpleNamespace(_research_gallery=gallery, config=None, stop=lambda: None)
        opened = []; real_open = Path.open
        def record_open(path, *a, **kw):
            f = real_open(path, *a, **kw); opened.append(f); return f
        job = dict(views=[dict(name='T0', settings={})])
        try:
            with patch.dict(sys.modules, {'tkinter': SimpleNamespace(Tk=lambda: root, Toplevel=lambda r: root)}), patch.object(Path, 'open', record_open):
                with self.assertRaisesRegex(RuntimeError, 'synthetic window setup failure'):
                    H.execute_gui(engine, job, {}, {}, folder, {}, None, S, SimpleNamespace(EdgeSpeechWindow=BadWindow), C.PipelineEvent, None, None)
            OBS[self._testMethodName] = dict(root_destroyed=root.destroyed, gallery_restored=gallery.score == original, handles_closed=all(f.closed for f in opened))
            self.assertTrue(root.destroyed and gallery.score == original and all(f.closed for f in opened), OBS[self._testMethodName])
        finally:
            for f in opened: f.close()
            gallery.score = original; root.destroy()

    def test_views_do_not_consume_native_inbox(self):
        views, fan, send = self.stream(); native = H.CausalInbox(2)
        native.put(C.PipelineEvent('untouched', 0., {}))
        engine = SimpleNamespace(events=native)
        facades = [H.ViewFacade(engine, v, fan) for v in views]
        for facade in facades:
            while not facade.events.empty(): facade.events.get()
        self.assertEqual(native.qsize(), 1)
        self.assertEqual(len({id(f.events) for f in facades}), 3)

    def test_longer_raw_revision_demotes_selected_identity_preserves_id(self):
        views, fan, send = self.stream()
        send('transcript_partial', dict(utterance_id='u', text='yes', source_start_sec=0., source_end_sec=1., latest_known_profile_id='a', latest_naming_state='confirmed', speaker='A'))
        send('s6d_text_ready', dict(utterance_id='u', text='yes please', source_start_sec=0., source_end_sec=2., final=False))
        for v in views:
            self.assertEqual(list(v['presentation'].rows), ['u'])
            self.assertEqual(v['presentation'].rows['u']['text'], 'yes please')
        self.assertTrue(views[0]['presentation'].rows['u']['visible'])
        self.assertFalse(views[1]['presentation'].rows['u']['visible'])
        self.assertFalse(views[2]['presentation'].rows['u']['visible'])

    def test_gui_old_session_payload_is_not_rendered(self):
        base = selected_class(APP/'gui.py', 'EdgeSpeechWindow', {'_consume_s6d_display'}, dict(time=time))
        w = base.__new__(base); w._s6d_gui_session_id = 'B'; w.s6d_rows = {}
        w._consume_s6d_display(dict(session_id='A', utterance_id='u'))
        self.assertEqual(w.s6d_rows, {})

    def test_gallery_failure_not_recorded_as_success_and_views_issue_zero_queries(self):
        class Gallery:
            calls = 0
            def score(self, vector):
                self.calls += 1
                raise RuntimeError('gallery failed')
        gallery = Gallery(); spy = H.GalleryScoreSpy(gallery); spy.install()
        try:
            views, fan, send = self.stream()
            send('transcript_final', dict(utterance_id='u', text='full words', source_start_sec=0., source_end_sec=1., latest_known_profile_id='a', latest_naming_state='confirmed', speaker='A'))
            self.assertEqual(gallery.calls, 0)
            with self.assertRaisesRegex(RuntimeError, 'gallery failed'): gallery.score(None)
            self.assertEqual(gallery.calls, 1); self.assertEqual(spy.rows, [])
        finally: spy.restore()

    def test_view_backlog_prevents_closure_and_does_not_overwrite_committed_display(self):
        views, fan, send = self.stream()
        views[0]['inbox'] = S.EventInbox(2); views[0]['forwarded'] = 0
        send('transcript_final', dict(utterance_id='u', text='one', source_start_sec=0., source_end_sec=1.))
        views[0]['consumer_closed'] = True
        self.assertTrue(any('not fully consumed' in e for e in fan.complete()))
        with self.assertRaises(RuntimeError):
            send('transcript_final', dict(utterance_id='v', text='two', source_start_sec=1., source_end_sec=2.))
        retained = []
        while not views[0]['inbox'].empty(): retained.append(views[0]['inbox'].get())
        self.assertEqual([r.payload.get('text') for r in retained], ['one', 'one'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--helper', type=Path, required=True); p.add_argument('--app-source', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); HELPER=args.helper.resolve(); APP=args.app_source.resolve(); OUT=args.output.resolve()
    if OUT.drive.upper() != 'G:': raise ValueError('Review outputs must stay on G')
    OUT.mkdir(parents=True, exist_ok=False); OBS={}
    H=load(HELPER, 'independent_tk_helper'); S=load(APP/'research_s6d.py', 'independent_tk_policy'); C=load(APP/'contracts.py', 'independent_tk_contracts')
    with (OUT/'TESTS.log').open('x', encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    H.write_new(OUT/'OBSERVATIONS.json', OBS)
    H.write_new(OUT/'RECEIPT.json', dict(status='PASS' if result.wasSuccessful() else 'ADVERSE_REPRODUCED', tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), helper=H.binding(HELPER), policy=H.binding(APP/'research_s6d.py'), gui=H.binding(APP/'gui.py'), contracts=H.binding(APP/'contracts.py'), fixture=H.binding(__file__), log=H.binding(OUT/'TESTS.log'), observations=H.binding(OUT/'OBSERVATIONS.json'), limitations=['AST-selected exact GUI methods use in-memory widget double; actual execute_gui setup uses fake tkinter module only', 'No actual Tk/window/model/device/source replay or scientific result scoring']))
    print(json.dumps(dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), receipt=str(OUT/'RECEIPT.json'))))
    sys.exit(0 if result.wasSuccessful() else 1)
