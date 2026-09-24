"""N2 contract regressions; run commands are in n2/embeddings/README.md.

Default tests use synthetic vectors/fake timelines. N2_TEST_E1=1 adds a real
saved research waveform and actual E1 model, with an isolated temporary store.
No personal recording, device enumeration, playback, or model training occurs.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "vendor")]
from app.n2_identity import N2Gallery, N2NameMap, binding
from app.n2_models import N2SpeakerModels
from app.n2_people import titanet_store
from app.n2_pipeline import ActivityTimeline, N2Engine
from app.people import PersonalStore, PREPROCESSING

CAMPAIGN = ROOT.parent / "research/nvidia_nemo_comparison/20260924_campaign"
NAMESPACE = {"model_sha256": "a" * 64, "preprocessing": "synthetic-test-v1", "dimension": 192, "normalization": "L2", "minimum_samples": 8000}


def vector(index=0):
    result = np.zeros(192, np.float32)
    result[index] = 1.0
    return result


def gallery_document(calibrated=False):
    gate = {"status": "CALIBRATED" if calibrated else "UNCALIBRATED_REJECT_ALL", "namespace": deepcopy(NAMESPACE), "score_threshold": 0.8, "margin_threshold": 0.1, "profile_ids": ["fixture-a", "fixture-b"], "fit_role": "C", "input_domain": "synthetic_test_only"}
    document={"schema": "just-peachy.n2.gallery.v1", "namespace": deepcopy(NAMESPACE), "profiles": [{"profile_id": "fixture-a", "name": "Fixture A", "vector": vector(0).tolist()}, {"profile_id": "fixture-b", "name": "Fixture B", "vector": vector(1).tolist()}], "calibration": gate, "domain": "synthetic_test_only", "query_domain":"synthetic_test_only", "roster_id":"fixture-roster", "duration_sec":15, "research_only": True}
    if calibrated:
        gate.update(schema='just-peachy.n2.calibrated-gate.v1',query_domain='synthetic_test_only',
            gallery_profiles_sha256=binding(document['profiles']),provenance=dict(fit_role='C',
            input_domain='synthetic_test_only',enrollment_domain='synthetic_test_only',reference_seconds=15,
            roster_id='fixture-roster',window_manifest_sha256='c'*64,calibration_rows_sha256='d'*64))
        gate['gate_sha256']=binding(gate)
    return document


def admitted_gallery(document,selected_ids=None):
    return N2Gallery(document,NAMESPACE,selected_ids=selected_ids,expected_query_domain='synthetic_test_only')


def evidence(index=0, start=0., end=2., **extra):
    return dict(vector=vector(index), source_start_sec=start, source_end_sec=end, speech=True, overlap=False, clean_intervals=[[start, end]], **extra)


def decision(track="test-track"):
    return dict(tracker_id=track, anonymous_label="Speaker 1")


def update(probabilities, start=0, received=None):
    probabilities = np.asarray(probabilities, np.float32)
    return SimpleNamespace(frame_start=start, frame_end=start + len(probabilities), probabilities=probabilities, seconds_per_frame=.01, audio_received_sec=(start+len(probabilities))*.01 if received is None else received, available_at_monotonic=100.+(start+len(probabilities))*.01)


class GalleryAndNameTests(unittest.TestCase):
    def test_wrong_representation_is_rejected_even_with_same_dimension(self):
        document = gallery_document()
        document["namespace"]["model_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "namespace"):
            N2Gallery(document, NAMESPACE)

    def test_duplicate_uuid_and_missing_selected_uuid_rejected(self):
        document = gallery_document()
        document["profiles"][1]["profile_id"] = "fixture-a"
        with self.assertRaises(ValueError):
            N2Gallery(document, NAMESPACE)
        with self.assertRaises(ValueError):
            N2Gallery(gallery_document(), NAMESPACE, selected_ids=["absent"])

    def test_selected_roster_invalidates_gate(self):
        gallery = admitted_gallery(gallery_document(True), selected_ids=["fixture-a"])
        result = N2NameMap(gallery).resolve(decision(), evidence())
        self.assertEqual(result["naming_state"], "unknown")
        self.assertEqual(result["identity"]["calibration_status"], "UNCALIBRATED_ROSTER_CHANGED")

    def test_uncalibrated_exact_match_rejects_and_closed_is_assumption(self):
        gallery = N2Gallery(gallery_document(), NAMESPACE)
        ordinary = N2NameMap(gallery).resolve(decision(), evidence())
        closed = N2NameMap(gallery, closed=True).resolve(decision(), evidence())
        self.assertEqual(ordinary["display_label"], "Unknown")
        self.assertEqual(closed["naming_state"], "closed_assumption")
        self.assertFalse(closed["identity"]["verified"])
        self.assertTrue(closed["identity"]["closed_roster_assumption"])

    def test_closed_caption_annotation_is_separate_unverified_display_metadata(self):
        names=N2NameMap(N2Gallery(gallery_document(),NAMESPACE),closed=True)
        supported=names.resolve(decision(),evidence())
        row=dict(text='unchanged words',segments=[deepcopy(supported),dict(naming_state='unknown',known_profile_id=None)])
        before=deepcopy(row);annotated=names.annotate_caption(row)
        self.assertEqual(row,before)
        choice=annotated['segments'][0]['closed_display_assignment']
        self.assertEqual(choice['profile_id'],'fixture-a');self.assertFalse(choice['verified'])
        self.assertFalse(choice['adaptation_eligible'])
        self.assertNotIn('closed_display_assignment',annotated['segments'][1])
        self.assertEqual(annotated['text'],'unchanged words')

    def test_no_gallery_keeps_anonymous_track_without_person_query(self):
        result = N2NameMap().resolve(decision(), evidence())
        self.assertEqual(result["display_label"], "Speaker 1")
        self.assertFalse(result["identity"]["query_executed"])

    def test_unique_evidence_does_not_count_overlapping_windows_twice(self):
        names = N2NameMap(admitted_gallery(gallery_document(True)))
        names.resolve(decision(), evidence(start=0, end=2))
        second = names.resolve(decision(), evidence(start=1, end=3))
        self.assertAlmostEqual(second["identity"]["unique_clean_sec"], 3.)
        self.assertAlmostEqual(second["identity"]["new_unique_sec"], 1.)

    def test_overlap_never_queries_or_certifies_person(self):
        event = evidence(); event["overlap"] = True
        names = N2NameMap(admitted_gallery(gallery_document(True)))
        result = names.resolve(decision(), event)
        self.assertFalse(result["identity"]["query_executed"])
        self.assertEqual(result["naming_state"], "unknown")
        self.assertEqual(names.gallery.query_count, 0)

    def test_long_session_retains_unique_duration_after_interval_retirement(self):
        names=N2NameMap(N2Gallery(gallery_document(),NAMESPACE))
        for index in range(520):
            latest=names.resolve(decision(),evidence(start=index*2.,end=index*2.+1.))
        self.assertEqual(latest['identity']['unique_clean_sec'],520.)
        self.assertEqual(len(names.states['test-track']['intervals']),512)
        repeated=names.resolve(decision(),evidence(start=0.,end=1.))
        self.assertEqual(repeated['identity']['unique_clean_sec'],520.)
        self.assertEqual(repeated['identity']['new_unique_sec'],0.)

    def test_two_contradictions_reset_evidence_without_changing_track_id(self):
        names = N2NameMap(admitted_gallery(gallery_document(True)))
        first = names.resolve(decision(), evidence(0, 0, 2))
        self.assertEqual(first["known_profile_id"], "fixture-a")
        self.assertEqual(first['naming_state'],'confirmed')
        conflict = names.resolve(decision(), evidence(1, 2, 4))
        self.assertEqual(conflict["naming_state"], "unknown")
        self.assertTrue(conflict["identity"]["contradiction"])
        reset = names.resolve(decision(), evidence(1, 4, 6))
        self.assertTrue(reset["identity"]["contradiction_reset"])
        self.assertEqual(reset["tracker_id"], "test-track")
        self.assertEqual(reset["identity"]["name_map_version"], 1)
        self.assertEqual(names.snapshot()["resets"], 1)

    def test_calibration_function_forbids_query_audio(self):
        path = CAMPAIGN / "n2/evaluation/scoring.py"
        spec = importlib.util.spec_from_file_location("n2_scoring_contract_test", path)
        scoring = importlib.util.module_from_spec(spec); spec.loader.exec_module(scoring)
        provenance = {key: "a"*64 if key.endswith("sha256") else 192 if key == "vector_dimension" else 15 if key == "reference_seconds" else "clean_source" for key in scoring.PROVENANCE_FIELDS}
        row = dict(role="Q", source_id="fixture-source", identity="fixture-a", is_known=True, winner_correct=True, score=.9, margin=.5)
        with self.assertRaisesRegex(ValueError, "C role only"):
            scoring.calibrate_c([row], provenance)

    def test_clean_calibration_status_is_not_processed_runtime_permission(self):
        document = gallery_document(True)
        document["calibration"]["status"] = "C_EMPIRICAL_CALIBRATION_ONLY"
        result = N2NameMap(N2Gallery(document, NAMESPACE)).resolve(decision(), evidence())
        self.assertEqual(result["naming_state"], "unknown")

    def test_calibrated_gate_requires_external_query_domain(self):
        with self.assertRaisesRegex(ValueError,'caller must supply'):
            N2Gallery(gallery_document(True),NAMESPACE)
        with self.assertRaisesRegex(ValueError,'query domain mismatch'):
            N2Gallery(gallery_document(True),NAMESPACE,expected_query_domain='other-input-domain')

    def test_calibrated_gate_rejects_Q_namespace_roster_payload_and_provenance_changes(self):
        cases=[lambda d:d['calibration'].update(fit_role='Q'),
               lambda d:d['calibration']['namespace'].update(model_sha256='b'*64),
               lambda d:d['calibration'].update(profile_ids=['fixture-a']),
               lambda d:d['profiles'][0].update(name='changed name'),
               lambda d:d['calibration']['provenance'].update(input_domain='unmatched-domain'),
               lambda d:d['calibration']['provenance'].update(enrollment_domain='other-enrollment-domain'),
               lambda d:d['calibration']['provenance'].update(calibration_rows_sha256=''),
               lambda d:d['calibration'].update(score_threshold=float('inf'))]
        for index,change in enumerate(cases):
            document=gallery_document(True);change(document)
            # Rehash legitimate finite schema mutations: provenance admission
            # must fail independently of the final integrity guard.
            if index!=7:
                document['calibration']['gate_sha256']=binding({k:v for k,v in document['calibration'].items() if k!='gate_sha256'})
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,'Unproven CALIBRATED'):
                admitted_gallery(document)

    def test_calibrated_gate_detects_threshold_tampering(self):
        document=gallery_document(True);document['calibration']['score_threshold']=.1
        with self.assertRaisesRegex(ValueError,'integrity'):
            admitted_gallery(document)


class TimelineTests(unittest.TestCase):
    def timeline(self):
        frames = np.zeros((200, 8), np.float32)
        frames[:100, 0] = .9; frames[100:, 1] = .9
        result = ActivityTimeline(); result.append(update(frames))
        return result

    def test_short_turn_association_uses_real_timeline(self):
        timeline = self.timeline()
        self.assertEqual(timeline.associate(.90, 1.)["slot"], 0)
        self.assertEqual(timeline.associate(1., 1.10)["slot"], 1)
        self.assertIsNone(timeline.associate(1.95, 2.10))

    def test_mixed_coarse_window_and_overlap_remain_unassigned(self):
        self.assertIsNone(self.timeline().associate(.9, 1.1)["slot"])
        frames = np.zeros((100, 8), np.float32); frames[:, :2] = .9
        timeline = ActivityTimeline(); timeline.append(update(frames))
        result = timeline.associate(0, 1)
        self.assertIsNone(result["slot"]); self.assertTrue(result["overlap"])
        self.assertEqual(result["slots"], [0, 1]); self.assertIsNone(timeline.exclusive_tail())

    def test_native_endpoint_overhang_is_not_audio_support(self):
        frames = np.zeros((104, 8), np.float32); frames[:, 0] = .9
        timeline = ActivityTimeline(); timeline.append(update(frames, received=1.))
        self.assertAlmostEqual(timeline.end, 1.)
        self.assertIsNone(timeline.associate(.9, 1.02))
        self.assertEqual(timeline.next_frame, 104)

    def test_discontinuous_updates_fail(self):
        timeline = self.timeline()
        with self.assertRaisesRegex(ValueError, "discontinuity"):
            timeline.append(update(np.zeros((10, 8), np.float32), start=201))

    def test_exclusive_windows_include_turn_ending_inside_native_chunk(self):
        frames = np.zeros((104, 8), np.float32); frames[:60, 0] = .9
        timeline = ActivityTimeline(); timeline.append(update(frames))
        self.assertIsNone(timeline.exclusive_tail())
        windows = timeline.exclusive_windows({})
        self.assertEqual(len(windows), 1)
        slot, start, end, run_start = windows[0]
        self.assertEqual(slot, 0); self.assertAlmostEqual(start, 0.); self.assertAlmostEqual(end, .5)
        self.assertEqual(timeline.exclusive_windows({0: end}), [])

    def test_fixed_hop_windows_never_cross_overlap_and_are_at_most_two_seconds(self):
        frames = np.zeros((600, 8), np.float32); frames[:, 0] = .9; frames[300:350, 1] = .9
        timeline = ActivityTimeline(); timeline.append(update(frames))
        windows = timeline.exclusive_windows({})
        self.assertTrue(all(.5-1e-6 <= end-start <= 2.+1e-6 for _, start, end, _ in windows))
        self.assertTrue(all(end <= 3.+1e-6 or start >= 3.5-1e-6 for _, start, end, _ in windows))
        self.assertTrue(any(abs(end-4.) < 1e-6 for _, _, end, _ in windows))

    def test_actual_dispatch_covers_ended_run_and_reports_short_run_denominator(self):
        frames = np.zeros((160, 8), np.float32)
        frames[:60, 0] = .9; frames[70:90, 1] = .9; frames[100:, 0] = .9
        item = update(frames)
        item.is_final=True;item.emitted_audio_end_sec=1.6;item.received_at_monotonic=100.
        item.compute_sec=.01;item.track_ids=[f"track-{i}" for i in range(8)];item.capacity_status="AVAILABLE"
        engine = object.__new__(N2Engine)
        engine._n2_lock=threading.RLock();engine._n2_timeline=ActivityTimeline()
        engine._n2_last_query={};engine._n2_embedding_serial=0;engine._n2_admitted_runs=set()
        engine._n2_reported_runs=set();engine._n2_short_run_count=0;engine._n2_short_run_sec=0.;engine._n2_reported_run_end=-1.
        engine._n2_names={};engine._n2_name_history={};engine.n2_name_map=N2NameMap()
        engine._s7_observed_clock=SimpleNamespace(relative=lambda: 2.)
        engine._identity_journal=SimpleNamespace(read=lambda start, length, wait_sec: np.arange(start,start+length,dtype=np.float32)/16000.)
        events=[];calls=[]
        engine._emit=lambda event,end,payload: events.append((event,payload))
        engine._revise_supported_spans=lambda: None
        model=SimpleNamespace(embed=lambda wave: (calls.append(wave.copy()) or vector()), last_embed_ms=.1, namespace=NAMESPACE)
        engine._accept_activity(item,model)
        self.assertEqual([len(wave) for wave in calls], [8000,8000])
        self.assertAlmostEqual(float(calls[0][0]),0.);self.assertAlmostEqual(float(calls[1][0]),1.)
        coverage=[row for kind,row in events if kind=='n2_exclusive_run_coverage']
        self.assertEqual(len(coverage),3)
        self.assertEqual(sum(row['embedding_selected'] for row in coverage),2)
        self.assertEqual(engine._n2_short_run_count,1)
        self.assertAlmostEqual(engine._n2_short_run_sec,.2)
        self.assertTrue(any(row['unavailable_reason']=='BELOW_EMBEDDING_MINIMUM' for row in coverage))
        # Ring retention changes old run start, never its fixed end. A final
        # flush must not count that same short run again.
        engine._n2_timeline.frames.popleft()
        engine._accept_activity(SimpleNamespace(**{**vars(item),'probabilities':np.empty((0,8),np.float32)}),model)
        self.assertEqual(len([row for kind,row in events if kind=='n2_exclusive_run_coverage']),3)

    def test_later_name_only_revises_spans_supported_by_its_query_audio(self):
        engine=object.__new__(N2Engine)
        engine._n2_name_history={0:[dict(display_label='First',evidence_start_sec=0.,evidence_end_sec=1.),
                                   dict(display_label='Later',evidence_start_sec=5.,evidence_end_sec=7.)]}
        self.assertEqual(engine._name_for_span(0,.2,.8)['display_label'],'First')
        self.assertEqual(engine._name_for_span(0,5.2,5.8)['display_label'],'Later')
        self.assertEqual(engine._name_for_span(0,2.,3.),{})

    def test_caption_revisions_target_spans_preserve_all_words_and_coarse_truth(self):
        rows = [dict(utterance_id="u1", text_revision_id="r1", source_start_sec=0., source_end_sec=2., raw_text="First speaker then second reply", word_spans=[dict(id="sA", source_start_sec=0., source_end_sec=1., text="First speaker"), dict(id="sB", source_start_sec=1., source_end_sec=2., text="second reply"), dict(id="mixed", source_start_sec=.9, source_end_sec=1.1, text="then")])]
        before = deepcopy(rows); emitted = []
        engine = object.__new__(N2Engine)
        engine._n2_lock = threading.RLock(); engine._n2_timeline = self.timeline()
        engine._n2_names = {}; engine._n2_name_history = {}; engine._n2_span_signatures = {}; engine._n2_revision = 0; engine._n2_associations = {}
        engine._session_dir = Path("fixture-session"); engine.mode = "anonymous_conversation"
        engine._s6d_presentation = SimpleNamespace(snapshot_rows=lambda: rows)
        engine._s7_observed_clock = SimpleNamespace(relative=lambda: 3.)
        engine._emit = lambda event, end, payload: emitted.append((event, payload))
        engine._revise_supported_spans()
        labels = {row["target_span_ids"][0]: row["latest_label"] for _, row in emitted}
        self.assertEqual(labels, {"sA": "Speaker 1", "sB": "Speaker 2", "mixed": "Unknown"})
        self.assertEqual(rows, before)
        self.assertTrue(all(not row["changes_raw_words"] for _, row in emitted))
        self.assertTrue(all(row["timing_kind"] == "ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT" for _, row in emitted))
        engine._revise_supported_spans()
        self.assertEqual(len(emitted), 3)
        # Retiring the audio/name history must preserve already displayed
        # historical labels rather than replacing them with Unknown.
        engine._n2_timeline.end=200.
        engine._n2_span_signatures[('sA','r1')]=('old-track','Saved name','fixture-a','known','single_activity_channel_in_coarse_window')
        engine._revise_supported_spans()
        self.assertEqual(len(emitted),3)
        self.assertEqual(engine._n2_span_signatures[('sA','r1')][1],'Saved name')

    def test_caption_producer_does_not_wait_for_identity_lock(self):
        engine = object.__new__(N2Engine)
        engine._s6d_presentation = object()
        engine._n2_lock = threading.RLock()
        held, release = threading.Event(), threading.Event()
        def owner():
            with engine._n2_lock:
                held.set(); release.wait(2.)
        worker = threading.Thread(target=owner); worker.start()
        self.assertTrue(held.wait(1.))
        returned = threading.Event()
        probe = threading.Thread(target=lambda: (engine._revise_supported_spans(blocking=False), returned.set()))
        try:
            probe.start(); self.assertTrue(returned.wait(.5), "caption producer waited for identity work")
        finally:
            release.set(); worker.join(1.); probe.join(1.)


class N2PolicyPresentationTests(unittest.TestCase):
    @staticmethod
    def view(n2):
        texts=[];buttons=[]
        def button(frame,label,callback,**options):
            buttons.append(dict(label=label,**options))
            return SimpleNamespace(pack=lambda **kwargs:None,button=SimpleNamespace(configure=lambda **kwargs:None))
        view=SimpleNamespace(snapshot=dict(backend=dict(composition={'n2':{'diarization':'D1','embedding':'E1'}} if n2 else {}),
            mode='enrolled_names',recipe='balanced',tap='O0'),_page=lambda *args,**kwargs:object(),
            _paragraph_label=lambda frame,text,*args:texts.append(text),button=button,px=lambda v:v,
            show_identity_scores=lambda:None,home=lambda:None)
        return view,texts,buttons

    def test_n2_settings_explains_gate_without_exposing_baseline_controls(self):
        from app.roster_ui import RosterUI
        view,texts,buttons=self.view(True)
        with patch('app.pipeline.effective_profile',side_effect=AssertionError('N2 page read unused baseline thresholds')):
            RosterUI.show_identity_parameters(view)
        self.assertIn('C-only calibration',' '.join(texts));self.assertIn('evidence stays Unknown',' '.join(texts))
        self.assertEqual([b['label'] for b in buttons],['Return to captions'])

    def test_baseline_settings_keeps_existing_six_controls_and_reset(self):
        from app.roster_ui import RosterUI
        view,texts,buttons=self.view(False);RosterUI.show_identity_parameters(view)
        self.assertEqual(len([b for b in buttons if b.get('key','').startswith('parameter_')]),6)
        self.assertIn('reset_identity_parameters',[b.get('key') for b in buttons])
        self.assertFalse(any('C-only calibration' in text for text in texts))

    def test_controller_reports_n2_closed_unknown_exception_and_rejects_override(self):
        from app.controller import Controller
        c=object.__new__(Controller)
        c.mode='selected_closed';c.recipe='balanced';c.tap='O0';c.selected_ids=[];c.display_ids=[]
        c.settings={};c.strict=False;c.identity_overrides={'score_threshold':.6};c._n2_components={'diarization':'D1','embedding':'E1'}
        c._ensure_no_enrollment=lambda:None
        configuration=c.mode_configuration()
        self.assertIn('evidence stays Unknown',configuration['closed_assignment'])
        self.assertEqual(configuration['overrides'],{})
        with self.assertRaisesRegex(ValueError,'C calibration'):c._do_identity_parameters({'score_threshold':.7})
        self.assertEqual(c.identity_overrides,{'score_threshold':.6})
        c._n2_components=None
        self.assertIn('missing ownership uses separate assumed selected-name display',c.mode_configuration()['closed_assignment'])


class BackendRosterAndAdaptationTests(unittest.TestCase):
    class Store:
        preprocessing=PREPROCESSING
        def __init__(self,root,ids):self.root=Path(root);self.ids=ids
        def list(self):return [dict(id=i,name=i) for i in self.ids]
        def gallery(self,route,person_ids=None,**kwargs):
            ids=self.ids if person_ids is None else person_ids
            if not ids or set(ids)-set(self.ids):raise ValueError('No compatible selected profiles')
            return SimpleNamespace(ids=ids,receipt={})

    def test_empty_e1_preserves_mode_allows_full_captions_and_restores_baseline_roster(self):
        from app.controller import Controller
        from app.backends import backend_catalog,BASELINE_BACKEND_ID
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);c=Controller(root/'data',root/'models',saved_audio_only=True)
            try:
                baseline=self.Store(root/'baseline',['a','b']);empty=self.Store(root/'E1',[])
                c.store=c._baseline_store=baseline;c.selected_ids=['a'];c.display_ids=['b']
                c.mode='selected_focus';c.recipe='balanced';c.strict=True
                bank=Mock();c.reference_bank=bank;c.collect_references=c.use_references=True
                backend=next(r['id'] for r in backend_catalog() if r['key']=='nemotron_titanet')
                with patch('app.n2_models.load_runtime',return_value={'embedding_namespace':NAMESPACE}),patch('app.n2_people.titanet_store',return_value=empty):
                    c._do_select_backend(backend)
                self.assertEqual(c.mode,'selected_focus');self.assertEqual(c.selected_ids,[]);self.assertEqual(c.display_ids,[])
                self.assertFalse(c.strict);self.assertIn('re-enroll',c.status)
                bank.discard.assert_called_once();self.assertIsNone(c.reference_bank)
                self.assertFalse(c.collect_references);self.assertFalse(c.use_references)
                c._do_switch('caption_only',None,None,None,False)
                self.assertEqual(c.mode,'caption_only')
                c._do_select_backend(BASELINE_BACKEND_ID)
                self.assertEqual(c.selected_ids,['a']);self.assertEqual(c.display_ids,['b'])
                self.assertEqual(c.mode,'caption_only');self.assertIs(c.store,baseline)
                self.assertIsNone(c.reference_bank);self.assertFalse(c.collect_references)
            finally:
                c.close();c.commands.join();c.worker.join(10)
                self.assertFalse(c.worker.is_alive())

    def test_compatible_same_uuid_can_carry_into_first_e1_selection(self):
        from app.controller import Controller
        from app.backends import backend_catalog
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);c=Controller(root/'data',root/'models',saved_audio_only=True)
            try:
                baseline=self.Store(root/'baseline',['shared']);e1=self.Store(root/'E1',['shared'])
                c.store=c._baseline_store=baseline;c.selected_ids=['shared'];c.display_ids=['shared']
                backend=next(r['id'] for r in backend_catalog() if r['key']=='titanet')
                with patch('app.n2_models.load_runtime',return_value={'embedding_namespace':NAMESPACE}),patch('app.n2_people.titanet_store',return_value=e1):
                    c._do_select_backend(backend)
                self.assertEqual(c.selected_ids,['shared']);self.assertEqual(c.display_ids,['shared'])
            finally:c.close();c.commands.join();c.worker.join(10)

    def test_n2_adaptation_rejects_all_enabling_and_never_accesses_base_bank(self):
        from app.controller import Controller
        c=object.__new__(Controller);c._n2_components={'diarization':'D1','embedding':'E1'}
        c.reference_bank=Mock();bank=c.reference_bank;c.collect_references=c.use_references=True
        c.store=SimpleNamespace(gallery=Mock(side_effect=AssertionError('N2 accessed base adaptation gallery')))
        for action,values in [('collect',dict(enabled=True,consent=True)),('use',dict(enabled=True,consent=True)),
                              ('confirm',{}),('promote',{}),('undo',{})]:
            with self.assertRaisesRegex(ValueError,'unavailable for N2'):c._do_adaptation(action,values)
        bank.discard.assert_called_once();self.assertIsNone(c.reference_bank)
        c._do_adaptation('collect',dict(enabled=False));self.assertFalse(c.collect_references)
        gallery=SimpleNamespace(adaptation=object());c._adaptation_start(gallery)
        self.assertIsNone(gallery.adaptation)
        with self.assertRaisesRegex(ValueError,'unavailable for N2'):c._adaptation_prepare(gallery)
        c.store.gallery.assert_not_called()
        state=c.adaptation_snapshot();self.assertFalse(state['available']);self.assertEqual(state['candidates'],[])

    def test_n2_adaptation_page_has_no_collection_or_promotion_controls(self):
        from app.adaptation_ui import AdaptationUI
        view,texts,buttons=N2PolicyPresentationTests.view(True);view.show_advanced=lambda:None
        AdaptationUI.show_adaptation(view)
        self.assertEqual([b['label'] for b in buttons],['Return to captions'])
        self.assertIn('unavailable',' '.join(texts))
        view.show_adaptation=Mock();AdaptationUI.show_reference_candidates(view)
        view.show_adaptation.assert_called_once()


class ActualEngineGalleryAdmissionTests(unittest.TestCase):
    """Real constructors/config/profile/store; synthetic vectors, no model start."""
    E1_NAMESPACE=dict(NAMESPACE,model_sha256='e'*64,preprocessing='fixture-titanet-frontend-v1',
        onnx_sha256='c'*64,frontend_sha256='d'*64)

    def setUp(self):
        from app.paths import pipeline_config
        from app.pipeline import effective_profile
        self.temp=tempfile.TemporaryDirectory(prefix='N2 constructor gallery fixture ')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.config=pipeline_config(self.root/'data',self.root/'nonexistent_models')
        self.profile=effective_profile('balanced','enrolled_names','O0')

    def research_gallery(self,namespace=None):
        document=gallery_document();document['namespace']=deepcopy(namespace or self.E1_NAMESPACE)
        return N2Gallery(document,document['namespace'])

    def personal_gallery(self,e1=True):
        from app.people import PersonalGallery
        namespace=self.E1_NAMESPACE
        store=titanet_store(self.root/'personal_e1',namespace) if e1 else PersonalStore(self.root/'personal_e0',self.config.asset('redimnet2_b2_fp32').sha256)
        route=dict(tap='O0',sample_rate=16000,gain_policy='O0_host_plus3dB_once',preprocessing=store.preprocessing,waveform_domain='xvf_ua')
        quality=dict(can_save=True,gaps=0,elapsed_s=2.,usable_s=1.,accepted_intervals=[[0.,1.]],capture_mode='paragraph',target_sec=None,
            source_sha256='f'*64,source_kind='explicit_synthetic_store_contract_fixture',clipping=0.,consistency=1.,embedding_count=1)
        store.save('Constructor fixture',vector(),quality,route)
        result=store.gallery(route);self.assertIsInstance(result,PersonalGallery)
        return result

    def construct(self,gallery,*,embedding='E1',profile=None):
        from app.n2_models import N2ResidentModels
        models=N2ResidentModels('D1',embedding,dict(embedding_namespace=deepcopy(self.E1_NAMESPACE)))
        with (patch.object(models,'acquire',side_effect=AssertionError('Constructor loaded neural models')),
              patch.object(models,'acquire_diarizer',side_effect=AssertionError('Constructor opened native model'))):
            engine=N2Engine(self.config,models,profile or self.profile,gallery,'enrolled_names',diarization='D1')
        self.assertEqual(engine.state,'IDLE');self.assertEqual(engine._threads,[])
        self.assertIsNone(models.speakers);self.assertIsNone(models.diarizer);self.assertEqual(models.asr_loads,0)
        self.assertIs(engine._research_gallery,gallery);self.assertIs(engine.n2_name_map.gallery,gallery)
        return engine

    def test_actual_n2_engine_accepts_e1_research_gallery_object(self):
        gallery=self.research_gallery();engine=self.construct(gallery)
        self.assertEqual(engine._research_gallery.receipt['backend_sha256'],self.E1_NAMESPACE['model_sha256'])
        self.assertEqual(engine.n2_name_map.resolve(decision(),evidence())['naming_state'],'unknown')

    def test_actual_n2_engine_accepts_e1_personal_gallery_from_real_store(self):
        gallery=self.personal_gallery();engine=self.construct(gallery)
        self.assertEqual(engine._research_gallery.namespace,self.E1_NAMESPACE)
        self.assertEqual(gallery.score(vector())[0]['name'],'Constructor fixture')
        self.assertEqual(engine.n2_name_map.resolve(decision(),evidence())['naming_state'],'unknown')

    def test_n2_constructor_rejects_wrong_e1_namespace_and_profile_count(self):
        from dataclasses import replace
        wrong=dict(self.E1_NAMESPACE,preprocessing='another-preprocessor')
        with self.assertRaisesRegex(ValueError,'namespace|representation|backend'):self.construct(self.research_gallery(wrong))
        limited=replace(self.profile,identity=replace(self.profile.identity,max_gallery_profiles=1))
        with self.assertRaisesRegex(ValueError,'count|bound|exceed'):self.construct(self.research_gallery(),profile=limited)

    def test_n2_accepts_compatible_legacy_e0_personal_gallery_and_rejects_wrong_frontend(self):
        gallery=self.personal_gallery(e1=False);self.assertFalse(hasattr(gallery,'namespace'))
        self.construct(gallery,embedding='E0')
        gallery.receipt['preprocessing']='unrelated-frontend'
        with self.assertRaisesRegex(ValueError,'preprocessing|namespace|backend'):self.construct(gallery,embedding='E0')

    def test_baseline_pipeline_still_rejects_e1_personal_gallery(self):
        from edge_speech_pipeline.runtime import PipelineEngine
        with self.assertRaisesRegex(ValueError,'different backend|backend mismatch'):
            PipelineEngine(self.config,research_profile=self.profile,research_gallery=self.personal_gallery())


class RuntimeConfigurationTests(unittest.TestCase):
    def runtime(self,root):
        library=root/'fixture.dll';library.write_bytes(b'harmless DLL binding fixture, never loaded')
        manifest=root/'titanet_manifest.json';manifest.write_text('{"fixture":true}',encoding='utf-8')
        sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
        document=dict(schema='just-peachy.n2.runtime.v1',native_runtime_files=[dict(path=str(library),sha256=sha(library))],
            titanet_manifest=str(manifest),titanet_manifest_sha256=sha(manifest),nemotron_model='fixture.gguf',
            nemotron_library=str(library),nemotron_library_sha256=sha(library))
        return document,library,manifest

    @staticmethod
    def write(root,document):
        (root/'n2_runtime.json').write_text(json.dumps(document),encoding='utf-8')

    def test_device_admission_legacy_cpu_explicit_cpu_cuda_and_invalid(self):
        from app.n2_models import load_runtime
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);document,_,_=self.runtime(root)
            self.write(root,document);self.assertNotIn('native_device',load_runtime(root))
            for device in (dict(kind='cpu',gpu_index=-1),dict(kind='cuda',gpu_index=0)):
                document['native_device']=device;self.write(root,document)
                self.assertEqual(load_runtime(root)['native_device'],device)
            for device in (dict(kind='cpu',gpu_index=0),dict(kind='cuda',gpu_index=-1),dict(kind='cuda',gpu_index=1),
                           dict(kind='cuda',gpu_index=False),dict(kind='unknown',gpu_index=-1)):
                document['native_device']=device;self.write(root,document)
                with self.assertRaises(ValueError):load_runtime(root)

    def test_changed_titanet_manifest_and_native_sibling_are_rejected(self):
        from app.n2_models import load_runtime
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);document,library,manifest=self.runtime(root);self.write(root,document)
            original=manifest.read_bytes();manifest.write_bytes(original+b' ')
            with self.assertRaisesRegex(ValueError,'TitaNet export manifest'):load_runtime(root)
            manifest.write_bytes(original);library.write_bytes(b'changed sibling')
            with self.assertRaisesRegex(ValueError,'Native runtime dependency'):load_runtime(root)
            document['native_runtime_files']=[];self.write(root,document)
            with self.assertRaisesRegex(ValueError,'Complete native'):load_runtime(root)

    def test_selected_device_is_passed_to_adapter_and_session_reset_reuses_model(self):
        from app.n2_models import N2ResidentModels
        for device,gpu in ((None,-1),(dict(kind='cpu',gpu_index=-1),-1),(dict(kind='cuda',gpu_index=0),0)):
            document=dict(nemotron_model='fixture.gguf',nemotron_library='fixture.dll',nemotron_library_sha256='a'*64,
                streaming_profile='low_latency')
            if device is not None:document['native_device']=device
            with patch('edge_speech_pipeline.nemotron_diarization.NemotronDiarizer') as constructor:
                models=N2ResidentModels('D1','E1',document)
                first=models.acquire_diarizer('first');self.assertEqual(constructor.call_args.kwargs['gpu'],gpu)
                self.assertEqual(constructor.call_args.kwargs['session_id'],'first')
                self.assertIs(models.acquire_diarizer('second'),first)
                self.assertEqual(constructor.call_count,1);first.reset.assert_called_once_with(session_id='second')
                models.close();first.close.assert_called_once()


class ModelBindingTests(unittest.TestCase):
    def test_e1_runtime_cannot_claim_an_unrelated_namespace(self):
        native = dict(backend_sha256="a"*64, preprocessing_version="official-titanet-test", dimension=192, normalization="l2", minimum_samples=8000, onnx_sha256="c"*64, frontend_sha256="d"*64)
        with patch("edge_speech_pipeline.titanet_embedding.TitanetEmbedding", return_value=SimpleNamespace(namespace=native)):
            with self.assertRaisesRegex(ValueError, "namespace"):
                N2SpeakerModels(SimpleNamespace(speaker_threads=1), "E1", {"titanet_manifest": "fixture", "embedding_namespace": NAMESPACE}, pyannote=False)


class ObserverPublicationTests(unittest.TestCase):
    def test_observer_receives_actual_stamped_event_after_journal_writer(self):
        from edge_speech_pipeline.contracts import PipelineEvent
        engine=object.__new__(N2Engine);order=[]
        engine.n2_observer_factory=None
        engine.n2_observer=SimpleNamespace(event=lambda kind,source,payload:order.append(('observer',kind,source,dict(payload))))
        payload={'publication_sequence':13,'publication_monotonic_sec':101.2,'session_id':'fixture-session','event_id':'text:1'}
        event=PipelineEvent('s6d_text_ready',1.2,payload)
        with patch('app.pipeline.PrototypeEngine._s6d_write_event',side_effect=lambda item:order.append(('writer',item))):
            engine._s6d_write_event(event)
        self.assertEqual(order[0],('writer',event))
        self.assertEqual(order[1],('observer','s6d_text_ready',1.2,payload))

    def test_unstamped_producer_payload_is_not_sent_to_observer(self):
        engine=object.__new__(N2Engine);seen=[]
        engine.n2_diarization='D0'
        engine.n2_observer=SimpleNamespace(event=lambda *args:seen.append(args))
        with patch('app.pipeline.PrototypeEngine._emit'):
            engine._emit('transcript_final',1.,{'raw_text':'unchanged words'})
        self.assertEqual(seen,[])


@unittest.skipUnless(os.environ.get("N2_TEST_E1") == "1", "set N2_TEST_E1=1 for actual saved-waveform E1 store exercise")
class ActualE1PersonalStoreTests(unittest.TestCase):
    def test_actual_embedding_save_reload_query_namespace_isolation(self):
        from edge_speech_pipeline.titanet_embedding import TitanetEmbedding, sha256_file
        import soundfile as sf
        base = Path("G:/Just_Peachy_N1/20260924_campaign/local/n2")
        model = TitanetEmbedding(os.environ.get("N2_E1_BUNDLE", str(base / "titanet/export")))
        native = model.namespace
        namespace = dict(model_sha256=native["backend_sha256"], preprocessing=native["preprocessing_version"], dimension=192, normalization="L2", minimum_samples=8000, onnx_sha256=native["onnx_sha256"], frontend_sha256=native["frontend_sha256"])
        manifest = json.loads(Path(os.environ.get("N2_WINDOWS", str(base / "evaluation/WINDOW_MANIFEST.json"))).read_text())
        row = next(row for row in manifest["windows"] if row["role"] == "E" and row["domain"] == "clean_source" and row["end_sample"] >= 16000)
        path = Path(row["audio"]["path"])
        self.assertEqual(sha256_file(path), row["audio"]["sha256"])
        waveform, sr = sf.read(path, dtype="float32"); waveform = waveform[row["start_sample"]:row["end_sample"]]
        actual = model.embed(waveform, sr)
        with tempfile.TemporaryDirectory(prefix="N2 research E1 store contract ") as temp:
            private = Path(temp)
            store = titanet_store(private, namespace)
            route = dict(tap="O1", sample_rate=16000, gain_policy="fixture_unity", preprocessing=store.preprocessing, waveform_domain="dry_test_fixture")
            # Explicit store-contract quality fixture, not an operational claim
            # that a real enrollment quality gate admitted this corpus clip.
            quality = dict(can_save=True, gaps=0, elapsed_s=len(waveform)/sr, usable_s=1., accepted_intervals=[[0., 1.]], capture_mode="paragraph", target_sec=None, source_sha256=row["audio"]["sha256"], source_kind="n2_research_store_contract_fixture", clipping=0., consistency=1., embedding_count=1, source_provenance={"quality_gate_fixture": True, "not_personal_enrollment": True})
            saved = store.save("Research fixture", actual, quality, route)
            loaded = titanet_store(private, namespace)
            gallery = loaded.gallery(route)
            score = gallery.score(actual)[0]
            self.assertEqual(score["profile_id"], saved["id"])
            self.assertGreater(score["cosine"], .9999)
            self.assertEqual(gallery.namespace, namespace)
            self.assertEqual(N2NameMap(gallery).resolve(decision(), evidence()) ["naming_state"], "unknown")
            altered = dict(namespace, preprocessing="another-preprocessor")
            other = titanet_store(private, altered)
            self.assertEqual(other.list(), [])
            baseline = PersonalStore(private / "baseline-people", "b"*64)
            self.assertEqual(baseline.list(), [])
            with self.assertRaises(ValueError):
                baseline.gallery(route)
            self.assertEqual(PersonalStore.preprocessing, PREPROCESSING)
        model.close()


if __name__ == "__main__":
    if os.name == "nt":
        import ctypes
        if not ctypes.windll.kernel32.SetPriorityClass(ctypes.c_void_p(-1), 0x00004000):
            raise OSError("could not set BelowNormal priority")
    unittest.main(verbosity=2)
