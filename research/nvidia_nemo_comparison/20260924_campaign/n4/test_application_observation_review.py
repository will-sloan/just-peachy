"""Joined observation fixtures; no new application, audio or model execution."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, freeze, load, verify
from application_resources import PHASES, ResourceLedger
from application_closure_v2 import validate_complete
from mode_galleries import backend_contract
import review_application_observations as review
from test_application_resources import process, sample
import test_application_closure_v2 as closure_fixture
from test_resource_review import write as write_resources
from test_viewport_ledger_v2 import fixture as viewport_fixture
from viewport_ledger_v2 import ViewportLedger

CONTEXT={}
OWNER=dict(pid=2147483000,create_time=1.)


class ObservationReviewTests(unittest.TestCase):
    def setUp(self):
        if not CONTEXT:self.skipTest('Use the guarded probe')
        self.root=CONTEXT['output']/self._testMethodName;self.root.mkdir(parents=True);self.number=0

    def fixture(self,*,invisible=False):
        self.number+=1;folder=self.root/str(self.number)/'application';folder.mkdir(parents=True)
        case=deepcopy(CONTEXT['case']);old_session=Path(case['session']);session=folder/'data/sessions'/old_session.name;session.mkdir(parents=True)
        for field in ('finalization','consumer'):
            source=case[field];verify(source);target=session/Path(source['path']).name;target.write_bytes(Path(source['path']).read_bytes());case[field]=bind(target)
        case['session']=str(session)
        archive=load(case['archive']['path']);epoch=load(archive['epoch']['path']);epoch['native_session_path']=str(session)
        epoch_path=folder/'data/conversations/fixture/epoch.json';freeze(epoch_path,epoch);archive['epoch']=bind(epoch_path)
        freeze(folder/'ARCHIVE_INTEGRITY.json',archive);case['archive']=bind(folder/'ARCHIVE_INTEGRITY.json')
        closure_fixture.CONTEXT.update(cases=[case],output=self.root)
        observed=closure_fixture.observed_fixture();observed['observed_monotonic_sec']=154.
        clock=observed['controller_clock'];clock.update(schema='n4-consumer-source-clock-v1',epoch=1,installed=True,
            violations=[],violations_truncated=False,observer_elapsed_sec=.01,actual_source_delivery_verified=False,
            full_event_consumer_closure_verified=False,source_to_widget_latency_qualified=False)
        prepared_source=load(CONTEXT['source']['path']);catalog=load(CONTEXT['catalog']['path'])
        catalog_row=next(r for r in catalog['backends'] if r['key']=='compact_eou')
        contract=backend_contract(catalog,'compact_eou','open_with_names');self.assertEqual(contract['engine'],observed['engine_class'])
        galleries=load(CONTEXT['galleries']['path']);condition=galleries['encoders'][contract['encoder']]['conditions'][contract['gallery_condition']]['condition']
        payload=dict(job=case['audio'],contract=contract,source_receipt=CONTEXT['source'],catalog=CONTEXT['catalog'],gallery_preparation=CONTEXT['galleries'])
        prepared=dict(source=dict(path=str((Path(prepared_source['prototype'])/'app/ui.py').resolve()),**prepared_source['files']['app/ui.py']),
            contract=contract,backend_id=catalog_row['manifest_id'],gallery_condition=condition,selected_ids=[])
        freeze(folder/'PREPARED.json',prepared);freeze(folder/'ENGINE_CLOSURE.json',observed);freeze(folder/'SOURCE_CLOCK.json',clock)
        viewport=ViewportLedger(folder/'viewport');viewport.add(viewport_fixture(98.,[]))
        for at,final in ((105.,False),(150.,True),(156.,True)):
            seen=viewport_fixture(at);seen.update(source_origin_monotonic_sec=100.,source_elapsed_sec=at-100.,source_clock='ACTUAL_SOURCE_MONOTONIC',source_relative_times_available=True)
            seen['rows'][0]['final']=final
            for pane in seen['rows'][0]['panes'].values():
                pane.update(caption_visible=not invisible,heading_visible=not invisible)
                for field in ('caption','heading'):
                    pane[field+'_viewport']=dict(visible_nonspace_characters=0 if invisible else 2,checked_characters=2,partially_clipped_characters=0,mapped=True,any_visible=not invisible)
            seen['rows'][0].update(caption_visible=not invisible,heading_visible=not invisible);viewport.add(seen)
        summary=viewport.close();freeze(folder/'viewport/RESULT.json',dict(status='RECORDED_RENDER_AND_TIMER_OBSERVATIONS',failure=None,
            render_calls=2,periodic_calls=1,deferred_context=0,timer_cancelled=True,samples=summary['samples'],ledger=bind(folder/'viewport/SUMMARY.json'),
            actual_source_delivery_verified=False,source_to_widget_latency_qualified=False,physical_scanout_measured=False,integrated_N4_cells=0))
        raw=viewport_fixture()['rows'][0]
        row=dict(id=raw['row_id'],caption_key=raw['caption_key'],span_ids=raw['span_ids'],final=True,
            **{k:raw[k] for k in ('raw_asr_text','source_start_sec','source_end_sec','timing_kind','speaker_revision','display_profile_id','naming_state','identity_assignment')},profile_id=None)
        snapshot=dict(rows=[row],state='STOPPED',error=None,saved_audio_only=True,backend_id=prepared['backend_id'],epoch=1,
            mode='open_with_names',recipe='balanced',tap=case['audio']['tap'],selected_ids=[],strict=False,pending_actions=0,settings={},reference_comparison=None)
        freeze(folder/'FINAL_SNAPSHOT.json',snapshot)
        rows=[];marks=[];ledger=ResourceLedger(OWNER)
        for index,(phase,at) in enumerate(zip(PHASES,(80.,85.,90.,95.,105.,150.,155.))):
            mark=dict(kind='phase',phase=phase,monotonic_sec=at);rows.append(mark);marks.append(mark)
            r=sample(at+.1,[process(pid=OWNER['pid'],created=OWNER['create_time'],cpu=index+1,memory=(index+1)*100)],phase=phase)
            r['kind']='sample';r['tree']['incomplete_processes']=[];rows.append(r);ledger.accept(r)
        resources=dict(ledger.summary(),status='OBSERVED_HOST_RESOURCES',owner=OWNER,error=None,observer_thread_exited=True,phase_marks=marks,
            all_lifecycle_marks_present=True,interval_sec=.5,elapsed_sec=90.,gpu_visibility_environment='-1',controlled_whole_stack_qualified=False,target_qualified=False,integrated_N4_cells=0)
        (folder/'resources').mkdir();resource_binding=write_resources(folder/'resources',rows,resources)
        freeze(folder/'RESULT.json',dict(status='CELL_CLOSED_REQUIRES_REVIEW',closure=validate_complete(observed,archive),errors=[],callback_errors=[],
            controller_closed=True,controller_worker_exited=True,resources=resource_binding))
        return folder,payload

    def checked(self,folder,payload):
        return review.review_observations(folder,payload=payload,application_owner=OWNER)

    def mutate(self,path,change):
        row=load(path);change(row);path.write_text(json.dumps(row,allow_nan=False),encoding='utf-8')

    def test_real_review_components_compose_on_explicit_synthetic_owner_facts(self):
        folder,payload=self.fixture();result=self.checked(folder,payload)
        self.assertEqual(result['status'],'PASS_APPLICATION_OBSERVATION_JOINS_ONLY')
        self.assertTrue(result['recorded_source_closure_verified']);self.assertTrue(result['source_and_viewport_origin_joined'])
        self.assertEqual(result['final_span_census']['final_snapshot_spans'],1)
        self.assertEqual(result['viewport_review']['observations'],4)
        for key in ('native_publication_content_reviewed','accuracy_qualified','source_to_widget_latency_qualified','controlled_resources_qualified',
            'physical_scanout_measured','actual_continuity_test','stop_restart_qualified','N4_accepted'):self.assertIs(result[key],False)
        self.assertEqual(result['deployment_tier'],'UNKNOWN');freeze(self.root/'SYNTHETIC_JOIN_REVIEW.json',result)

    def test_invisible_and_never_final_visible_spans_remain_denominators(self):
        folder,payload=self.fixture(invisible=True);result=self.checked(folder,payload)
        counts=result['final_span_census'];self.assertEqual(counts['final_snapshot_spans'],1)
        self.assertEqual(counts['final_snapshot_spans_never_observed_visible'],1);self.assertEqual(counts['finalized_spans_without_final_visibility'],1)

    def test_final_snapshot_backend_state_epoch_mode_and_assistance_cannot_change(self):
        for change in (lambda r:r.update(epoch=2),lambda r:r.update(backend_id='foreign'),lambda r:r.update(state='RUNNING'),
            lambda r:r.update(mode='selected_closed'),lambda r:r.update(strict=True),lambda r:r['settings'].update(text_assistance=True)):
            folder,payload=self.fixture();self.mutate(folder/'FINAL_SNAPSHOT.json',change)
            with self.assertRaises(ValueError):self.checked(folder,payload)

    def test_source_clock_and_engine_cannot_come_from_another_cell(self):
        for relative,change in [('SOURCE_CLOCK.json',lambda r:r.update(epoch=2)),
            ('ENGINE_CLOSURE.json',lambda r:r.update(engine_class='N2Engine')),
            ('ENGINE_CLOSURE.json',lambda r:r.update(observed_monotonic_sec=149.)),
            ('ENGINE_CLOSURE.json',lambda r:r['job'].update(tap='O1' if r['job']['tap']=='O0' else 'O0'))]:
            folder,payload=self.fixture();self.mutate(folder/relative,change)
            with self.assertRaises(ValueError):self.checked(folder,payload)

    def test_foreign_resource_owner_and_binding_refused(self):
        folder,payload=self.fixture()
        with self.assertRaisesRegex(ValueError,'different application'):
            review.review_observations(folder,payload=payload,application_owner=dict(pid=OWNER['pid'],create_time=2.))
        self.mutate(folder/'RESULT.json',lambda r:r['resources'].update(sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'swapped'):self.checked(folder,payload)

    def test_prepared_frontend_backend_and_gallery_must_match_bound_context(self):
        for change in (lambda r:r.update(backend_id='foreign'),lambda r:r['source'].update(sha256='0'*64),
            lambda r:r.update(selected_ids=['forced-fixture']),lambda r:r['gallery_condition'].update(available_size=-1)):
            folder,payload=self.fixture();self.mutate(folder/'PREPARED.json',change)
            with self.assertRaises(ValueError):self.checked(folder,payload)

    def test_final_controller_span_metadata_must_exist_in_latest_viewport(self):
        for change in (lambda r:r['rows'][0].update(span_ids=['foreign']),lambda r:r['rows'][0].update(raw_asr_text='Changed fixture'),
            lambda r:r['rows'][0].update(profile_id='foreign'),lambda r:r['rows'].append(deepcopy(r['rows'][0]))):
            folder,payload=self.fixture();self.mutate(folder/'FINAL_SNAPSHOT.json',change)
            with self.assertRaises(ValueError):self.checked(folder,payload)

    def test_viewport_observer_must_be_closed_with_matching_census(self):
        for change in (lambda r:r.update(timer_cancelled=False),lambda r:r.update(samples=9),
            lambda r:r.update(periodic_calls=0),lambda r:r['ledger'].update(sha256='0'*64)):
            folder,payload=self.fixture();self.mutate(folder/'viewport/RESULT.json',change)
            with self.assertRaises(ValueError):self.checked(folder,payload)

    def test_late_engine_or_archive_errors_cannot_be_hidden_by_cell_status(self):
        for relative,change in [('ENGINE_CLOSURE.json',lambda r:r['source'].update(sent=0)),
            ('ARCHIVE_INTEGRITY.json',lambda r:r['owner'].update(archive_error='late fixture failure')),
            ('RESULT.json',lambda r:r.update(callback_errors=['late Tk failure']))]:
            folder,payload=self.fixture();self.mutate(folder/relative,change)
            with self.assertRaises(ValueError):self.checked(folder,payload)

    def test_cpu_only_environment_is_part_of_observation_join(self):
        folder,payload=self.fixture();self.mutate(folder/'resources/RESULT.json',lambda r:r.update(gpu_visibility_environment=''))
        self.mutate(folder/'RESULT.json',lambda r:r.update(resources=bind(folder/'resources/RESULT.json')))
        with self.assertRaisesRegex(ValueError,'GPU environment'):self.checked(folder,payload)

    def test_individually_valid_source_clock_with_foreign_viewport_origin_refused(self):
        folder,payload=self.fixture();observed=load(folder/'ENGINE_CLOSURE.json');clock=observed['controller_clock']
        clock['source_epoch_monotonic_sec']=101.;clock['source_started']['source_epoch_monotonic_sec']=101.
        clock['source_started']['event_payload']['source_epoch_monotonic_sec']=101.
        (folder/'ENGINE_CLOSURE.json').write_text(json.dumps(observed),encoding='utf-8')
        (folder/'SOURCE_CLOCK.json').write_text(json.dumps(clock),encoding='utf-8')
        self.mutate(folder/'RESULT.json',lambda r:r.update(closure=validate_complete(observed,load(folder/'ARCHIVE_INTEGRITY.json'))))
        with self.assertRaisesRegex(ValueError,'origins differ'):self.checked(folder,payload)

    def test_transport_failure_prevents_observation_review(self):
        with (patch.object(review,'review_transport',side_effect=ValueError('fixture transport refusal')) as transport,
            patch.object(review,'review_observations') as observations):
            with self.assertRaisesRegex(ValueError,'transport refusal'):review.review_collected_cell(self.root,payload={})
            transport.assert_called_once();observations.assert_not_called()
