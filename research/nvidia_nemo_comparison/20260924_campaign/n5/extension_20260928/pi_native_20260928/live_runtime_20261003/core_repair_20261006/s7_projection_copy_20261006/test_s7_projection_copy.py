"""No-model output/order/ownership checks; README_S7_PROJECTION_COPY.md."""
import ast
from collections import OrderedDict
from copy import deepcopy
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import ModuleType
import unittest
from unittest.mock import patch

from s7_projection_copy import (INITIAL, REPLACEMENT, S7_SOURCE_SHA256,
                                _derive, _method_node, _read_source, _same, bind_project, install_project)


SOURCE_ROOT = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12')
FOLDER = SOURCE_ROOT/'vendor/edge_speech_pipeline'
S7_PATH = FOLDER/'research_s7_presentation.py'
PURE_PINS = {
    'research_s7_presentation.py': S7_SOURCE_SHA256,
    'research_s6d.py': 'ad680e2d3cb30980c07bcd12de2a5a7c20b7ae529889a105fa57ae986fb355a1',
    'research_n1_spans.py': 'a81478569480bb927943a460c17aad0549377e3b7365c4417e3b9f17ecd0d238',
}
PACKAGE_NAME = '_s7_projection_copy_pure_pinned'
HERE = Path(__file__).resolve().parent
MERGED_ENGINE = HERE.parent/'disk_capacity_policy_20261006/installed_engine.py'
ENGINE_PIN = 'f6c5ebd4dfa725baa738aa70d36d86bf7937d7030080ce61f25dee5f83fba25a'
PACKAGE = SOURCE_ROOT.parents[4]/'live-runtime-20261003/audit-preparation/event-package33-efdac72ba11f4e8e93b519e80dc3898a/package'
OBSERVATIONS = {}


def pinned_types():
    for name, expected in PURE_PINS.items():
        raw = _read_source(FOLDER/name)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Fixture pure S7 source differs')
    if PACKAGE_NAME not in sys.modules:
        package = ModuleType(PACKAGE_NAME)
        package.__path__ = [str(FOLDER)]
        sys.modules[PACKAGE_NAME] = package
    s6d = importlib.import_module(PACKAGE_NAME+'.research_s6d')
    s7 = importlib.import_module(PACKAGE_NAME+'.research_s7_presentation')
    return s6d.S6DSettings, s7.S7PresentationState


def state(mode='M2', ownership='timestamped_spans_v3', transcript='T1', all_enrolled=False):
    Settings, Presentation = pinned_types()
    selected = () if all_enrolled else ('synthetic-a',)
    return Presentation(Settings(max_display_rows=512, transcript_mode=transcript,
        selected_profile_ids=selected, all_enrolled=all_enrolled), dict(
        session_id='synthetic-session', mode=mode, ownership_mode=ownership))


def synthetic_row():
    segment = dict(id='synthetic-parent/segment:1', label='Synthetic A', known_name='Synthetic A',
        anonymous_label='Speaker 0', known_profile_id='synthetic-a', naming_state='confirmed', track_id=0,
        text='fixture fixture continuation', source_start_sec=0.125, source_end_sec=2.5,
        token_ids=['synthetic-parent:r1:t0','synthetic-parent:r1:t1'],
        word_spans=[dict(id='synthetic-parent:r1:t0',text='fixture',source_start_sec=0.125,
            source_end_sec=0.5,speaker_history=[dict(label='Synthetic A',revision=1)])])
    other = deepcopy(segment)
    other.update(id='synthetic-parent/segment:2', known_profile_id=None, known_name=None,
        label='Unknown', anonymous_label='Unknown', naming_state='unresolved', track_id=None,
        source_start_sec=2.5, source_end_sec=3.875)
    return dict(utterance_id='synthetic-parent', segments=[segment,other],
        text='fixture fixture continuation', accepted_identity_snapshot={'owners':[{'ids':['synthetic-a']}]},
        source_start_sec=0.125, source_end_sec=3.875, text_revision_id='synthetic-parent:r1',
        word_spans=deepcopy(segment['word_spans']), token_ids=list(segment['token_ids']),
        known_profile_id='synthetic-a', known_name='Synthetic A', naming_state='confirmed',
        track_id=0, label='Synthetic A', anonymous_label='Speaker 0', final=True,
        display_version=7, _internal={'never_projected':[1,2]}, unrelated_history=[{'revision':1}])


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',',':')).encode('utf-8')


class ProjectionCopyChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.Presentation = pinned_types()
        cls.original = staticmethod(cls.Presentation.project)
        cls.project = staticmethod(bind_project(cls.Presentation, S7_PATH, S7_SOURCE_SHA256))

    def compare(self, before, after, row):
        left = self.original(before,row)
        right = self.project(after,row)
        self.assertEqual(right,left)
        self.assertEqual(list(right),list(left))
        self.assertEqual(encoded(right),encoded(left))
        self.assertEqual(after._columns,before._columns)
        self.assertEqual(after.view_revision,before.view_revision)
        return left,right

    def test_all_modes_ownership_settings_and_visibility_exact(self):
        comparisons = 0
        for ownership in ('conservative_v1','supported_prefix_v2','timestamped_spans_v3'):
            for transcript, all_enrolled in (('T0',False),('T1',False),('T2',False),('T2',True)):
                for mode in ('M0','M1','M2','M3','M4','M5','M6','M7'):
                    if mode == 'M4' and transcript == 'T0':
                        continue  # Original validator correctly rejects this combination.
                    for full_view in (False,True):
                        before = state(mode,ownership,transcript,all_enrolled)
                        after = state(mode,ownership,transcript,all_enrolled)
                        before.full_view = after.full_view = full_view
                        self.compare(before,after,synthetic_row())
                        comparisons += 1
        OBSERVATIONS['exact_mode_comparisons'] = comparisons

    def test_optional_missing_and_unattributed_rows_keep_key_order(self):
        fixtures = [{}, {'utterance_id':'synthetic-empty'}, {'segments':[]},
            {'accepted_identity_snapshot':None}, {'segments':[], 'z':[], 'accepted_identity_snapshot':{}, 'a':1},
            {'z':1,'segments':[],'a':2}, {'known_profile_id':None,'naming_state':'unresolved','track_id':None},
            {'segments':[{'anonymous_label':'Unknown','track_id':None}]}]
        for ownership in ('conservative_v1','supported_prefix_v2','timestamped_spans_v3'):
            for row in fixtures:
                with self.subTest(ownership=ownership,keys=list(row)):
                    self.compare(state(ownership=ownership),state(ownership=ownership),row)

    def test_outputs_detach_nested_histories_tokens_and_snapshot(self):
        row = synthetic_row()
        unchanged = deepcopy(row)
        _, shown = self.compare(state(),state(),row)
        shown['segments'][0]['word_spans'][0]['speaker_history'][0]['label'] = 'changed-output'
        shown['segments'][0]['token_ids'].append('output-only')
        shown['accepted_identity_snapshot']['owners'][0]['ids'].append('output-only')
        shown['word_spans'][0]['text'] = 'changed-output'
        shown['unrelated_history'][0]['revision'] = 999
        self.assertEqual(row,unchanged)
        row['segments'][1]['text'] = 'changed-canonical'
        row['accepted_identity_snapshot']['owners'][0]['ids'].append('canonical-only')
        self.assertNotEqual(shown['segments'][1]['text'],row['segments'][1]['text'])
        self.assertNotIn('canonical-only',shown['accepted_identity_snapshot']['owners'][0]['ids'])

    def test_public_aliases_and_per_segment_copy_ownership_match(self):
        row = synthetic_row()
        row['other_public'] = row['segments']
        row['segments'].append(row['segments'][0])
        left,right = self.compare(state(),state(),row)
        self.assertIsNot(right['segments'],right['other_public'])
        self.assertIsNot(right['segments'][0],right['segments'][2])
        self.assertEqual(right['segments'][0] is right['segments'][2],left['segments'][0] is left['segments'][2])
        right['segments'][0]['word_spans'][0]['text'] = 'output-only'
        self.assertNotEqual(right['segments'][2]['word_spans'][0]['text'],'output-only')
        self.assertNotEqual(right['other_public'][0]['word_spans'][0]['text'],'output-only')

    def test_column_state_and_source_clocks_follow_original_sequence(self):
        before,after = state(),state()
        for track in (None,0,1,2,0,None):
            row = synthetic_row()
            row['track_id'] = track
            row['segments'][0]['track_id'] = track
            row['segments'][1]['track_id'] = track
            _,shown = self.compare(before,after,row)
            self.assertEqual(shown['source_start_sec'],0.125)
            self.assertEqual(shown['source_end_sec'],3.875)
        self.assertEqual(after._columns,{0:'left',1:'right'})

    def test_initial_discarded_copies_removed_only_in_supported_modes(self):
        counts = {}
        for ownership in ('conservative_v1','supported_prefix_v2','timestamped_spans_v3'):
            row = synthetic_row()
            actual = {}
            for label,method in (('original',self.original),('derived',self.project)):
                calls = []
                def observed(value):
                    calls.append(id(value))
                    return deepcopy(value)
                with patch.dict(method.__globals__,deepcopy=observed):
                    method(state(ownership=ownership),row)
                actual[label] = dict(segments=calls.count(id(row['segments'])),
                    snapshot=calls.count(id(row['accepted_identity_snapshot'])),
                    each_segment=[calls.count(id(item)) for item in row['segments']])
            if ownership == 'conservative_v1':
                self.assertEqual(actual['derived'],actual['original'])
            else:
                self.assertEqual(actual['original'],dict(segments=1,snapshot=2,each_segment=[1,1]))
                self.assertEqual(actual['derived'],dict(segments=0,snapshot=1,each_segment=[1,1]))
            counts[ownership] = actual
        OBSERVATIONS['direct_copy_counts'] = counts

    def test_deepcopy_still_runs_inside_original_lock(self):
        for method in (self.original,self.project):
            target = state()
            calls = []
            def observed(value):
                self.assertTrue(target._lock._is_owned())
                calls.append(1)
                return deepcopy(value)
            with patch.dict(method.__globals__,deepcopy=observed):
                method(target,synthetic_row())
            self.assertTrue(calls)

    def test_malformed_json_segment_values_raise_same_exception(self):
        for invalid in (None,[None],['invalid'],42):
            row = {'segments':invalid,'accepted_identity_snapshot':None}
            errors = []
            for method in (self.original,self.project):
                try:
                    method(state(),row)
                except Exception as error:
                    errors.append((type(error),str(error)))
                else:
                    self.fail('Original invalid segment shape should fail')
            self.assertEqual(errors[0],errors[1])

    def test_exact_single_assignment_ast_reverse_proof(self):
        original = _method_node(_read_source(S7_PATH),str(S7_PATH))
        derived = _derive(original)
        old = ast.parse(INITIAL).body[0]
        new = ast.parse(REPLACEMENT).body[0]
        matches = [node for node in ast.walk(derived) if isinstance(node,ast.Assign) and _same(node,new)]
        self.assertEqual(len(matches),1)
        matches[0].value = deepcopy(old.value)
        self.assertTrue(_same(derived,original))
        self.assertEqual(self.project.s7_projection_provenance['initial_assignments_replaced'],1)

    def test_assignment_ast_drift_rejected(self):
        original = _method_node(_read_source(S7_PATH),str(S7_PATH))
        initial = next(node for node in ast.walk(original) if isinstance(node,ast.Assign)
                       and _same(node,ast.parse(INITIAL).body[0]))
        initial.value.value = ast.Constant(value=None)
        with self.assertRaisesRegex(ValueError,'initial S7 copy expression differs'):
            _derive(original)

    def test_source_hash_and_bytes_drift_rejected(self):
        with self.assertRaisesRegex(ValueError,'exact admitted S7 source pin'):
            bind_project(self.Presentation,S7_PATH,'0'*64)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'drift.py'
            path.write_bytes(_read_source(S7_PATH)+b'\n# synthetic drift\n')
            with self.assertRaisesRegex(ValueError,'source SHA differs'):
                bind_project(self.Presentation,path,S7_SOURCE_SHA256)

    def test_method_origin_and_owner_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'same-source.py'
            path.write_bytes(_read_source(S7_PATH))
            with self.assertRaisesRegex(ValueError,'origin differs'):
                bind_project(self.Presentation,path,S7_SOURCE_SHA256)
        class Foreign:
            project = self.original
        with self.assertRaisesRegex(ValueError,'Exact admitted S7 class'):
            bind_project(Foreign,S7_PATH,S7_SOURCE_SHA256)

    def test_install_isolated_idempotent_and_rejects_foreign_override(self):
        target,other = state(),state()
        receipt = install_project(target,self.project)
        self.assertEqual(receipt,install_project(target,self.project))
        self.assertIs(target.project.__func__,self.project)
        self.assertIs(other.project.__func__,self.original)
        self.assertIs(self.Presentation.project,self.original)
        self.assertEqual(target.project(synthetic_row()),other.project(synthetic_row()))
        foreign = state()
        foreign.project = lambda row: row
        with self.assertRaisesRegex(ValueError,'override differs'):
            install_project(foreign,self.project)
        with self.assertRaisesRegex(ValueError,'Exact bound S7 presentation instance'):
            install_project(object(),self.project)
        # Compile only the actual merged facade method, without loading its
        # native import graph. The presentation used here is the pinned class.
        raw = _read_source(MERGED_ENGINE)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),ENGINE_PIN)
        owners = [node for node in ast.walk(ast.parse(raw)) if isinstance(node,ast.ClassDef) and node.name=='Engine']
        self.assertEqual(len(owners),1)
        methods = [node for node in owners[0].body if isinstance(node,ast.FunctionDef) and node.name=='_begin_session']
        self.assertEqual(len(methods),1)
        expected = ast.parse('''def _begin_session(engine, mode):
    super()._begin_session(mode)
    if type(engine._s6d_presentation) is S7PresentationState:
        engine.s7_projection_copy_receipt = install_project(engine._s6d_presentation, s7_project)
''').body[0]
        self.assertTrue(_same(methods[0],expected))
        calls = []
        class Base:
            def _begin_session(instance,mode):
                calls.append(mode)
        shell = ast.ClassDef(name='Engine',bases=[ast.Name(id='Base',ctx=ast.Load())],
            keywords=[],body=[deepcopy(methods[0])],decorator_list=[])
        namespace = dict(Base=Base,S7PresentationState=self.Presentation,
            install_project=install_project,s7_project=self.project)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[shell],type_ignores=[])),str(MERGED_ENGINE),'exec'),namespace)
        actual = namespace['Engine']()
        actual._s6d_presentation = state()
        actual._begin_session('synthetic-mode')
        self.assertEqual(calls,['synthetic-mode'])
        self.assertIs(actual._s6d_presentation.project.__func__,self.project)
        self.assertEqual(actual.s7_projection_copy_receipt,receipt)
        untouched = namespace['Engine']()
        untouched._s6d_presentation = object()
        untouched._begin_session('synthetic-other')
        self.assertFalse(hasattr(untouched,'s7_projection_copy_receipt'))

    def test_class_method_drift_before_install_rejected(self):
        target = state()
        with patch.object(self.Presentation,'project',lambda instance,row: row):
            with self.assertRaisesRegex(ValueError,'class project changed'):
                install_project(target,self.project)

    def test_multiple_synthetic_revisions_preserve_order_and_ownership(self):
        before,after = state('M3'),state('M3')
        row = synthetic_row()
        for revision in range(1,41):
            row['text_revision_id'] = 'synthetic-parent:r'+str(revision)
            row['display_version'] = revision
            row['segments'][0]['word_spans'][0]['speaker_history'].append({'revision':revision})
            row['segments'][0]['text'] = 'fixture fixture continuation '+str(revision)
            self.compare(before,after,row)
        OBSERVATIONS['exact_repeated_revisions'] = 40


class RunningDelayChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = _read_source(HERE/'classic_frontend.py')
        cls.tree = ast.parse(raw)
        names = {'running_delay_diagnostic','running_delay_status'}
        methods = [node for node in cls.tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
        if len(methods)!=2:
            raise ValueError('Exact two candidate delay helpers required')
        scope = {'math':math}
        exec(compile(ast.Module(body=deepcopy(methods),type_ignores=[]),str(HERE/'classic_frontend.py'),'exec'),scope)
        cls.status = staticmethod(scope['running_delay_status'])
        cls.diagnostic = staticmethod(scope['running_delay_diagnostic'])

    def test_live_and_saved_actual_lag_values_remain_visible(self):
        measured = {'asr_lag_sec':0.3,'speaker_lag_sec':21.3}
        self.assertEqual(self.status('live',measured),
            'Listening locally · text delay 0.3s · speaker delay 21.3s · analysis behind')
        self.assertTrue(self.status('saved',measured).startswith('Replaying saved audio · text delay 0.3s'))
        for delay in (120.,365.,7200.):
            shown = self.status('live',{'asr_lag_sec':delay,'speaker_lag_sec':delay})
            self.assertIn('speaker delay '+format(delay,'.1f')+'s',shown)
            self.assertIn('analysis behind',shown)
            self.assertLess(len('balanced / O0 · '+shown),200)

    def test_missing_invalid_lag_never_becomes_zero(self):
        for invalid in (None,{}, {'asr_lag_sec':True,'speaker_lag_sec':False},
                {'asr_lag_sec':float('nan'),'speaker_lag_sec':float('inf')},
                {'asr_lag_sec':10**400,'speaker_lag_sec':10**400},
                {'asr_lag_sec':-1,'speaker_lag_sec':'21.3'}):
            shown = self.status('live',invalid)
            self.assertIn('text delay unavailable',shown)
            self.assertIn('speaker delay unavailable',shown)
            self.assertNotIn('0.0s',shown)
            self.assertEqual(self.diagnostic(invalid)['analysis_status'],'delay unavailable')

    def test_measured_cursor_does_not_qualify_real_time(self):
        for measured in ({'asr_lag_sec':0,'speaker_lag_sec':0}, {'asr_lag_sec':0.1,'speaker_lag_sec':7200}):
            diagnostic = self.diagnostic(measured)
            self.assertIs(diagnostic['real_time_qualified'],False)
            self.assertEqual(diagnostic['asr_lag_sec'],measured['asr_lag_sec'])
            self.assertEqual(diagnostic['speaker_lag_sec'],measured['speaker_lag_sec'])
        self.assertEqual(self.diagnostic({'asr_lag_sec':0,'speaker_lag_sec':0})['analysis_status'],
            'at measured input cursor')

    def test_ui_delta_reverses_to_original_all_other_branches_unchanged(self):
        original_raw = _read_source(PACKAGE/'classic_frontend.py')
        self.assertEqual(hashlib.sha256(original_raw).hexdigest(),
            '0e8b0db1b9e227a7a5a9dea61b298d7d28984aad8c2a5dd299a5d1024aa59aaf')
        restored = deepcopy(self.tree)
        restored.body = [node for node in restored.body if not isinstance(node,ast.FunctionDef)
            or node.name not in {'running_delay_diagnostic','running_delay_status'}]
        replacement = ast.parse('self.notice = running_delay_status(self.selection.input_source, measured)').body[0]
        original = ast.parse("self.notice = 'Listening locally' if self.selection.input_source == 'live' else 'Replaying saved audio'").body[0]
        assignments = 0
        keywords = 0
        for node in ast.walk(restored):
            if isinstance(node,ast.Assign) and _same(node,replacement):
                node.value = deepcopy(original.value)
                assignments += 1
            if isinstance(node,ast.Call):
                before = len(node.keywords)
                node.keywords = [keyword for keyword in node.keywords if keyword.arg!='runtime_timing']
                keywords += before-len(node.keywords)
        self.assertEqual((assignments,keywords),(1,1))
        self.assertTrue(_same(restored,ast.parse(original_raw)))


if __name__ == '__main__':
    raise SystemExit('Use the registered CPU14 runner after explicit host authorization')
