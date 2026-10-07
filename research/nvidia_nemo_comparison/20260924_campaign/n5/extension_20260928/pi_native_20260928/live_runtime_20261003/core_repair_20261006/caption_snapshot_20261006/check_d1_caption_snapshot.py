"""No-model checks of pinned caption snapshots; see README_D1_CAPTION_SNAPSHOT.md."""
import ast
from collections import OrderedDict
from copy import deepcopy
import hashlib
import importlib
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from d1_caption_snapshot import (N2_SOURCE_SHA256, ROW_FIELDS, SPAN_FIELDS,
                                 _derive, _method_node, bind_revision, selected_identity_rows)


SOURCE_ROOT = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12')
N2_PATH = SOURCE_ROOT/'app/n2_pipeline.py'
PURE_PINS = {
    'research_s7_presentation.py': 'a6229a1cc1f967012de2b79780ab92029e63dc3a64e52bf56b563d7e44f18f10',
    'research_s6d.py': 'ad680e2d3cb30980c07bcd12de2a5a7c20b7ae529889a105fa57ae986fb355a1',
    'research_n1_spans.py': 'a81478569480bb927943a460c17aad0549377e3b7365c4417e3b9f17ecd0d238',
}


def pinned_parent():
    """Compile only the admitted method/class shell; import no N2 native graph."""
    raw = N2_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != N2_SOURCE_SHA256:
        raise ValueError('Fixture pinned source differs')
    method = deepcopy(_method_node(raw, str(N2_PATH)))
    owner = ast.ClassDef(name='N2Engine', bases=[], keywords=[], body=[method], decorator_list=[])
    namespace = {'__name__': '_caption_snapshot_method_fixture', 'NAMED_MODES': {'named'}}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[owner], type_ignores=[])),
                 str(N2_PATH), 'exec'), namespace)
    return namespace['N2Engine']


def presentation(mode='M1'):
    package = '_caption_snapshot_pure_pinned'
    folder = SOURCE_ROOT/'vendor/edge_speech_pipeline'
    for name, expected in PURE_PINS.items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest() != expected:
            raise ValueError('Fixture S7 source differs')
    if package not in sys.modules:
        module = ModuleType(package)
        module.__path__ = [str(folder)]
        sys.modules[package] = module
    s6d = importlib.import_module(package+'.research_s6d')
    s7 = importlib.import_module(package+'.research_s7_presentation')
    return s7.S7PresentationState(s6d.S6DSettings(max_display_rows=512), dict(
        session_id='synthetic-session', mode=mode, ownership_mode='timestamped_spans_v3'))


def row(key, revision='revision:1', start=0., end=20.):
    spans = [dict(id=key+'/token:1', source_start_sec=start+.1, source_end_sec=start+.2,
                  text='fixture', speaker_history=[{'label': 'synthetic'}]),
             dict(id=key+'/token:2', source_start_sec=start+.2, source_end_sec=start+.4,
                  text='repetition', speaker_history=[])]
    return dict(utterance_id=key, caption_key='synthetic-session/'+key,
                text_revision_id=revision, source_start_sec=start, source_end_sec=end,
                word_spans=spans, text='fixture repetition', display_text='Fixture repetition',
                label='Pending identity', anonymous_label='Unknown', known_profile_id=None,
                known_name=None, naming_state='unresolved', track_id=None,
                final=True, segments=[], accepted_identity_snapshot=None,
                unrelated_display_history=[{'private_fixture': list(range(128))}])


def identity_fields(projected):
    return [{**{name: item[name] for name in ROW_FIELDS if name in item},
             'word_spans': [{name: span[name] for name in SPAN_FIELDS if name in span}
                            for span in item.get('word_spans', [])]} for item in projected]


def engine(state):
    result = SimpleNamespace(
        _s6d_presentation=state, _n2_lock=threading.RLock(),
        _n2_timeline=SimpleNamespace(end=30., reserve_sec=120.,
            associate=lambda a,b: dict(slot=0, reason='fixture_supported')),
        _n2_associations={}, _n2_span_signatures={}, _n2_revision=0,
        _session_dir=SimpleNamespace(name='synthetic-session'), mode='anonymous',
        _s7_observed_clock=SimpleNamespace(relative=lambda:100.))
    result._name_for_span = lambda slot,a,b: {}
    result.emitted = []
    result._emit = lambda kind,end,payload: result.emitted.append((kind,end,deepcopy(payload)))
    return result


class SnapshotChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Parent = pinned_parent()
        cls.revise = staticmethod(bind_revision(cls.Parent, N2_PATH, N2_SOURCE_SHA256))

    def test_actual_s7_modes_preserve_exact_identity_inputs(self):
        for mode in ('M0', 'M1', 'M2', 'M3', 'M5', 'M6', 'M7'):
            with self.subTest(mode=mode):
                state = presentation(mode)
                state.rows = OrderedDict((key,row(key,start=i*20,end=(i+1)*20))
                                         for i,key in enumerate(('parent:a','parent:b')))
                self.assertEqual(selected_identity_rows(state), identity_fields(state.snapshot_rows()))
                self.assertEqual(selected_identity_rows(state,'parent:b'),
                                 identity_fields([state.project(state.rows['parent:b'])]))

    def test_selected_snapshot_never_projects_unrelated_rows(self):
        state = presentation()
        state.rows = OrderedDict((key,row(key)) for key in ('parent:a','parent:b'))
        with patch.object(state, 'project', side_effect=AssertionError('Display projection forbidden')):
            selected = selected_identity_rows(state,'parent:b')
        self.assertEqual([item['utterance_id'] for item in selected],['parent:b'])
        self.assertNotIn('text',selected[0])
        self.assertNotIn('speaker_history',selected[0]['word_spans'][0])
        self.assertEqual(selected_identity_rows(state,'missing-parent'),[])

    def test_empty_placeholder_preserves_absent_fields_and_native_skip(self):
        state = presentation()
        state.rows['empty-parent'] = {'utterance_id':'empty-parent'}
        expected = identity_fields(state.snapshot_rows())
        self.assertEqual(selected_identity_rows(state),expected)
        self.assertNotIn('source_start_sec',expected[0])
        self.assertNotIn('text_revision_id',expected[0])
        old, new = engine(state), engine(state)
        self.Parent._revise_supported_spans(old)
        self.revise(new)
        self.assertEqual(new.emitted,old.emitted)
        self.assertEqual(new._n2_span_signatures,old._n2_span_signatures)

    def test_global_order_exact_coarse_intervals_and_detachment(self):
        state = presentation()
        state.rows = OrderedDict((key,row(key,start=start,end=start+20))
                                 for key,start in (('parent:b',20.),('parent:a',0.)))
        selected = selected_identity_rows(state)
        self.assertEqual([item['utterance_id'] for item in selected],['parent:b','parent:a'])
        self.assertEqual(selected[0]['word_spans'][0]['source_start_sec'],20.1)
        selected[0]['word_spans'][0]['source_start_sec'] = -1
        self.assertEqual(state.rows['parent:b']['word_spans'][0]['source_start_sec'],20.1)

    def test_bound_native_method_preserves_all_emitted_revision_payloads(self):
        first, second = presentation(), presentation()
        first.rows = OrderedDict((key,row(key,start=i*20,end=(i+1)*20))
                                 for i,key in enumerate(('parent:a','parent:b')))
        second.rows = deepcopy(first.rows)
        old, new = engine(first), engine(second)
        self.Parent._revise_supported_spans(old)
        self.revise(new)
        self.assertEqual(new.emitted,old.emitted)
        self.assertEqual(new._n2_span_signatures,old._n2_span_signatures)
        self.assertEqual(new._n2_associations,old._n2_associations)
        before = deepcopy(new.emitted)
        self.revise(new)
        self.assertEqual(new.emitted,before)

    def test_bound_native_selected_parent_avoids_full_projection(self):
        state = presentation()
        state.rows = OrderedDict((key,row(key)) for key in ('parent:a','parent:b'))
        target = engine(state)
        with patch.object(state,'project',side_effect=AssertionError('Unrelated display projection')):
            self.revise(target,'parent:b',False)
        self.assertEqual(len(target.emitted),2)
        self.assertTrue(all(item[2]['utterance_id']=='parent:b' for item in target.emitted))

    def test_actual_candidate_engine_wrapper_calls_bound_method_and_records_cost(self):
        path = Path(__file__).with_name('installed_engine.py')
        module = ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
        owners = [item for item in ast.walk(module) if isinstance(item,ast.ClassDef) and item.name=='Engine']
        self.assertEqual(len(owners),1)
        method = next(item for item in owners[0].body if isinstance(item,ast.FunctionDef) and
                      item.name=='_revise_supported_spans')
        costs = []
        namespace = dict(Parent=self.Parent,N2Engine=self.Parent,n2_caption_reviser=self.revise,
                         time=time,session=SimpleNamespace(_cost=lambda *values:costs.append(values)))
        exec(compile(ast.Module(body=[deepcopy(method)],type_ignores=[]),str(path),'exec'),namespace)
        state = presentation()
        state.rows = OrderedDict((key,row(key)) for key in ('parent:a','parent:b'))
        target = engine(state)
        target.n2_name_map = SimpleNamespace()
        with patch.object(state,'project',side_effect=AssertionError('Full projection forbidden')):
            namespace['_revise_supported_spans'](target,'parent:b',False)
        self.assertEqual(len(target.emitted),2)
        self.assertEqual(len(costs),1)
        self.assertEqual(costs[0][0],'d1_caption_revision')
        self.assertGreaterEqual(costs[0][1],0.)
        self.assertEqual(costs[0][2],0)

    def test_stable_prefix_revision_cleanup_keeps_only_current_pairs(self):
        state = presentation()
        native_spans = importlib.import_module('_caption_snapshot_pure_pinned.research_n1_spans')
        current = row('parent:a',start=0.,end=1.)
        current.update(_token_owners=[None,None],_token_serial=2,_previous_source_end_sec=1.)
        stable_id = current['word_spans'][0]['id']
        for index,text in enumerate(('fixture repetition next','fixture repetition next again',
                                     'fixture repetition next again final'),2):
            prior = current['text']
            current.update(text=text,text_revision_id='revision:'+str(index),source_end_sec=float(index))
            native_spans.update_tokens(current,prior,{},float(index))
            self.assertEqual(current['word_spans'][0]['id'],stable_id)
        state.rows['parent:a'] = current
        target = engine(state)
        target._n2_timeline.end = 200.
        target._n2_span_signatures = {(stable_id,'obsolete:'+str(index)):('old',)
                                      for index in range(16385)}
        current_pairs = {(span['id'],current['text_revision_id']) for span in current['word_spans']}
        target._n2_span_signatures.update({pair:('expired-supported-current',) for pair in current_pairs})
        self.revise(target)
        self.assertEqual(set(target._n2_span_signatures),current_pairs)
        self.assertTrue(all(value==('expired-supported-current',) for value in target._n2_span_signatures.values()))
        self.assertEqual(target.emitted,[])

    def test_source_hash_and_native_origin_drift_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory)/'n2_pipeline.py'
            changed.write_bytes(N2_PATH.read_bytes()+b'\n# changed fixture\n')
            with self.assertRaisesRegex(ValueError,'hash differs'):
                bind_revision(self.Parent,changed,N2_SOURCE_SHA256)
            changed.write_bytes(N2_PATH.read_bytes())
            with self.assertRaisesRegex(ValueError,'origin differs'):
                bind_revision(self.Parent,changed,N2_SOURCE_SHA256)
        with self.assertRaisesRegex(ValueError,'exact original N2 pin'):
            bind_revision(self.Parent,N2_PATH,'0'*64)

    def test_ast_shape_drift_rejected_and_narrow_provenance_reported(self):
        original = _method_node(N2_PATH.read_bytes(),str(N2_PATH))
        drifted = deepcopy(original)
        first = next(item for item in ast.walk(drifted) if isinstance(item,ast.For) and
                     isinstance(item.iter,ast.Call) and isinstance(item.iter.func,ast.Attribute) and
                     item.iter.func.attr=='snapshot_rows')
        first.iter.func.attr = 'unexpected_snapshot'
        with self.assertRaisesRegex(ValueError,'AST regions differ'):
            _derive(drifted)
        proof = self.revise.caption_snapshot_provenance
        self.assertEqual(proof['snapshot_calls_replaced'],2)
        self.assertTrue(proof['cleanup_pairs_replaced'])
        self.assertTrue(proof['other_ast_unchanged'])
        self.assertTrue(proof['word_timing_unchanged'])

    def test_nonblocking_busy_owner_performs_no_snapshot(self):
        state = presentation()
        target = engine(state)
        target._n2_lock = SimpleNamespace(acquire=lambda blocking:False,
                                         release=lambda: self.fail('Unowned release'))
        with patch('d1_caption_snapshot.selected_identity_rows',side_effect=AssertionError('Unexpected snapshot')):
            self.revise(target,blocking=False)
        self.assertEqual(target.emitted,[])


if __name__ == '__main__':
    unittest.main()
