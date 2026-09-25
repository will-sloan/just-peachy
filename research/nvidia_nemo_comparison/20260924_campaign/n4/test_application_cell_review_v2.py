"""Synthetic joined V2 cell fixtures; never execute fixture apps or audio."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from application_closure import persisted
from application_closure_v2 import validate_complete
from common import bind, fingerprint, freeze, load
from paced_child_admission import LEASE_SCHEMA
import review_application_cell_v2 as review
from review_native_journal import inspect as inspect_journal
from test_paced_child_admission import fixture_input, fixture_permit
import test_application_observation_review as observations

CONTEXT = {}


def rewrite(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding='utf-8')


def rebind_closure(folder):
    app = folder/'application'; value = load(app/'ENGINE_CLOSURE.json')
    value['persisted'] = persisted(value['session'], value['job']['frames'])
    rewrite(app/'ENGINE_CLOSURE.json', value)
    result = load(app/'RESULT.json'); result['closure'] = validate_complete(value, load(app/'ARCHIVE_INTEGRITY.json'))
    rewrite(app/'RESULT.json', result)
    child = load(folder/'transport/CHILD_RESULT.json'); child['cell_result'] = bind(app/'RESULT.json')
    rewrite(folder/'transport/CHILD_RESULT.json', child)
    collected = load(folder/'COLLECTED.json'); collected['child_result'] = bind(folder/'transport/CHILD_RESULT.json')
    rewrite(folder/'COLLECTED.json', collected)


def rebind_envelope(folder, payload):
    observed = load(folder/'application/ENGINE_CLOSURE.json'); session = Path(observed['session'])
    value = dict(schema='n4-cell-native-envelope-v1', cell_id=payload['cell_id'],
        job_sha256=fingerprint(payload['job']), engine_closure=bind(folder/'application/ENGINE_CLOSURE.json'),
        session=str(session), review=inspect_journal(session, job=payload['job']), integrated_N4_cells=0, N4_accepted=False)
    rewrite(folder/'NATIVE_JOURNAL_ENVELOPE.json', value)
    collected = load(folder/'COLLECTED.json'); collected['native_journal_envelope'] = bind(folder/'NATIVE_JOURNAL_ENVELOPE.json')
    rewrite(folder/'COLLECTED.json', collected)


class CellReviewTests(unittest.TestCase):
    def setUp(self):
        if not CONTEXT: self.skipTest('Use the guarded probe')
        self.root = CONTEXT['output']/self._testMethodName; self.root.mkdir(parents=True); self.number = 0

    def fixture(self, *, invisible=False):
        self.number += 1; base = self.root/str(self.number); base.mkdir()
        observations.CONTEXT.update(CONTEXT)
        helper = observations.ObservationReviewTests(); helper.root = base; helper.number = 0
        app, partial = helper.fixture(invisible=invisible); folder = app.parent
        payload = fixture_input(); payload.update(partial); payload['runtimes'] = CONTEXT['runtimes']
        owner = deepcopy(observations.OWNER); permit = fixture_permit(); permit['application'] = owner
        # Inert bytes and synthetic owner facts are not a new application run.
        for name in ('fixture.exe', 'paced_application_runner_v2.py'):
            (base/name).write_text('INERT JOIN FIXTURE; NEVER EXECUTED', encoding='utf-8')
        exe = bind(base/'fixture.exe'); script = bind(base/'paced_application_runner_v2.py'); code = [script]
        permit.update(code=code, output=str(app), state=str(base/'state'))
        coord_argv = ['inert', 'fixture']; permit['coordinator_argv_sha256'] = fingerprint(coord_argv)
        argv = [exe['path'], '-B', script['path'], 'child', '--permit', str(folder/'transport/PERMIT.json'), '--nonce', permit['nonce']]
        permit['application_argv_sha256'] = fingerprint(argv)
        freeze(folder/'transport/INPUT.json', payload); permit['input'] = bind(folder/'transport/INPUT.json')
        freeze(folder/'transport/PERMIT.json', permit)
        lifetime = dict(status='OWNED_PROCESS_LIFETIME_CLOSED', owner=owner, executable=exe, script=script,
            argv_sha256=fingerprint(argv), desktop=permit['desktop'], input_desktop_before='Default', input_desktop_after='Default',
            source_execution_authorized=False, resumed=True, forced=False, job_empty_verified=True, observed_members_exited=True,
            final_job=dict(active=0, total=1, terminated=0), root_exit_code=0, error=None, cleanup_errors=[], events=[
                dict(kind='spawned_suspended_and_assigned', monotonic=50., owner=owner, affinity=[4], argv_sha256=fingerprint(argv),
                    job=dict(active=1, total=1, terminated=0)),
                dict(kind='resumed_after_registration', monotonic=50.2),
                dict(kind='job_members_observed', monotonic=169., members=[]),
                dict(kind='cancel_requested', monotonic=170.),
                dict(kind='all_observed_member_identities_exited', monotonic=170., owners=[owner])])
        freeze(folder/'transport/LIFETIME.json', lifetime); (folder/'transport/CANCEL').touch()
        freeze(folder/'transport/LEASE.json', dict(schema=LEASE_SCHEMA, status='ADMITTED', nonce=permit['nonce'],
            permit_sha256=fingerprint(permit), coordinator=permit['coordinator'], application=owner,
            supervised_run=permit['supervised_run'], sequence=3, issued_monotonic=169.))
        observed = load(app/'ENGINE_CLOSURE.json'); session = Path(observed['session'])
        consumer = load(session/'s6d_consumer_closure.json'); consumer['monotonic_sec'] = 153.
        consumer['queues']['journal'].update(accepted=6, completed=6)
        consumer['queues']['event_consumer'].update(consumed=5, coalesced_obsolete_ui_partials=1)
        rewrite(session/'s6d_consumer_closure.json', consumer)
        observed['workers']['journal'].update(accepted=6, completed=6)
        observed['publication_census'].update(published=6, consumed=5, coalesced_obsolete_ui_partials=1)
        clock = observed['controller_clock']; clock.update(event_count=5, last_publication_sequence=6, missing_publication_sequences=1)
        start = clock['source_started']['event_payload']; start.update(publication_sequence=2,
            publication_monotonic_sec=100.2, publication_source_cursor_sec=0.)
        observed['persisted'] = persisted(session, payload['job']['frames'])
        rewrite(app/'ENGINE_CLOSURE.json', observed); rewrite(app/'SOURCE_CLOCK.json', clock)
        duration = payload['job']['frames']/16000; events = []
        kinds = ('session_started', 'source_started', 'research_asr_observation', 'transcript_partial', 'transcript_final', 'session_completed')
        for index, (kind, at) in enumerate(zip(kinds, (99., 100.2, 110., 120., 145., 151.))):
            body = dict(publication_sequence=index+1, publication_monotonic_sec=at,
                publication_source_cursor_sec=max(0,index-1)*duration/4, session_id=session.name)
            if kind == 'source_started': body.update(start)
            events.append(dict(schema_version='edge-speech-event.v1', event_type=kind,
                source_time_sec=body['publication_source_cursor_sec'], wall_time_utc='2026-09-25T18:00:00+00:00',
                payload=body, journal_write_monotonic_sec=at+.01))
        (session/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in events), encoding='utf-8')
        prepared = load(app/'PREPARED.json'); prepared.update(status='PREPARED_NO_SOURCE_OR_MODELS_STARTED',
            desktop=permit['desktop'], job=payload['job'], runtimes=payload['runtimes'], gallery_preparation=payload['gallery_preparation'],
            logical_client=[480,800], active_height_px=184, no_auto_start=True, integrated_N4_cells=0)
        rewrite(app/'PREPARED.json', prepared)
        result = load(app/'RESULT.json'); result.update(closure=validate_complete(observed,load(app/'ARCHIVE_INTEGRITY.json')),
            source_start_requested=True, source_to_widget_latency_qualified=False, complete_N4_acceptance=False, integrated_N4_cells=0)
        rewrite(app/'RESULT.json', result)
        freeze(folder/'transport/CHILD_RESULT.json', dict(status='COLLECTED_APPLICATION_CELL_REQUIRES_REVIEW', owner=owner,
            input=permit['input'], error=None, cell_result=bind(app/'RESULT.json'), integrated_N4_cells=0, N4_accepted=False))
        rows = [dict(**permit['coordinator'],affinity=[14],parent_pid=permit['supervisor']['pid'],executable=exe['path'],argv_sha256=fingerprint(coord_argv)),
            dict(**permit['supervisor'],affinity=[14],parent_pid=1)]
        slot = dict(coordinator=permit['coordinator'],supervised_run=permit['supervised_run'],census=dict(rows=rows,errors=[]),
            inventory=dict(errors=[],total_logical_bytes=1024),reservation_bytes=512*1024**2,cpu_affinity=[4],gpu=False,source_execution_authorized=False)
        freeze(folder/'COLLECTED.json', dict(status='COLLECTED_SOURCE_PACED_CELL_REQUIRES_REVIEW',cell_id=payload['cell_id'],input=permit['input'],
            child_result=bind(folder/'transport/CHILD_RESULT.json'),lifetime=bind(folder/'transport/LIFETIME.json'),
            monitoring=dict(renewals=3,elapsed_seconds=119.8),slot_admission=slot,integrated_N4_cells=0,N4_accepted=False))
        rebind_envelope(folder,payload)
        freeze(folder/'PARENT_CLOSURE.json',dict(error=None,cleanup_error=None,lifecycle=lifetime,slot_release=dict(status='APPLICATION_SLOT_RELEASED',
            coordinator=permit['coordinator'],application=owner,child_cleanup_performed_by_guard=False,source_execution_authorized=False),
            integrated_N4_cells=0,N4_accepted=False))
        args = dict(payload=payload,plan_sha256=permit['plan_sha256'],coordinator=permit['coordinator'],code=code,
            executable=exe,coordinator_argv=coord_argv,state=Path(permit['state']))
        return folder,args

    def test_all_real_readers_compose_with_synthetic_facts(self):
        folder,args=self.fixture();result=review.review_cell(folder,**args)
        self.assertEqual(result['status'],'PASS_V2_APPLICATION_CELL_EVIDENCE_JOINS_ONLY')
        self.assertEqual(result['joins']['native_events'],6);self.assertEqual(result['joins']['consumed_events'],5)
        self.assertEqual(result['joins']['coalesced_obsolete_ui_partials'],1)
        self.assertEqual(result['joins']['source_origin_monotonic_sec'],100.)
        for field in ('complete_panel_reviewed','native_payload_semantics_reviewed','caption_strings_independently_scored',
            'names_independently_scored','accuracy_qualified','source_to_widget_latency_qualified','controlled_resources_qualified',
            'physical_scanout_measured','actual_continuity_test','stop_restart_qualified','N4_accepted'):self.assertIs(result[field],False)
        self.assertEqual(result['deployment_tier'],'UNKNOWN');self.assertEqual(result['integrated_N4_cells'],0)
        freeze(self.root/'SYNTHETIC_COMPLETE_JOIN_REVIEW.json',result)

    def test_invisible_final_spans_still_count(self):
        folder,args=self.fixture(invisible=True);result=review.review_cell(folder,**args)
        self.assertEqual(result['observations']['final_span_census']['final_snapshot_spans_never_observed_visible'],1)

    def test_individually_valid_native_and_consumer_starts_must_join(self):
        for field,value in (('publication_sequence',3),('publication_monotonic_sec',100.3)):
            folder,args=self.fixture();observed=load(folder/'application/ENGINE_CLOSURE.json')
            observed['controller_clock']['source_started']['event_payload'][field]=value
            rewrite(folder/'application/ENGINE_CLOSURE.json',observed);rewrite(folder/'application/SOURCE_CLOCK.json',observed['controller_clock'])
            rebind_closure(folder);rebind_envelope(folder,args['payload'])
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'source-start publication differs'):
                review.review_cell(folder,**args)
        folder,args=self.fixture();session=Path(load(folder/'application/ENGINE_CLOSURE.json')['session']);path=session/'events.jsonl'
        rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        rows[1]['payload']['source_epoch_monotonic_sec']=99.9
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8');rebind_envelope(folder,args['payload'])
        with self.assertRaisesRegex(ValueError,'origins differ'):review.review_cell(folder,**args)

    def test_late_native_completion_is_not_closed_engine_evidence(self):
        folder,args=self.fixture();session=Path(load(folder/'application/ENGINE_CLOSURE.json')['session'])
        consumer=load(session/'s6d_consumer_closure.json');consumer['monotonic_sec']=157.;rewrite(session/'s6d_consumer_closure.json',consumer)
        rows=[json.loads(line) for line in (session/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        rows[-1]['payload']['publication_monotonic_sec']=156.;rows[-1]['journal_write_monotonic_sec']=156.01
        (session/'events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
        rebind_closure(folder);rebind_envelope(folder,args['payload'])
        with self.assertRaisesRegex(ValueError,'predates native session completion'):review.review_cell(folder,**args)

    def test_shared_binding_change_between_readers_is_refused(self):
        folder,args=self.fixture();transport=review.review_transport(folder,**args)
        checked=review.review_observations(folder/'application',payload=args['payload'],application_owner=transport['application'])
        changed=deepcopy(checked)
        next(b for b in changed['evidence'] if Path(b['path']).name=='ENGINE_CLOSURE.json')['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'changed between independent reviews'):
            review.join_reviews(folder,args['payload'],transport,changed)

    def test_resource_owner_comes_from_verified_transport(self):
        folder,args=self.fixture();transport=review.review_transport(folder,**args)
        transport['application']=dict(observations.OWNER,create_time=2.)
        with patch.object(review,'review_transport',return_value=transport),self.assertRaisesRegex(ValueError,'different application'):
            review.review_cell(folder,**args)

    def test_transport_failure_stops_before_observation_work(self):
        folder,args=self.fixture();value=load(folder/'COLLECTED.json');value['input']['sha256']='0'*64;rewrite(folder/'COLLECTED.json',value)
        with patch.object(review,'review_observations') as later,self.assertRaisesRegex(ValueError,'Collected receipt'):
            review.review_cell(folder,**args)
        later.assert_not_called()

    def test_observation_failure_cannot_be_hidden_by_valid_transport(self):
        folder,args=self.fixture();snapshot=load(folder/'application/FINAL_SNAPSHOT.json')
        snapshot['rows'][0]['raw_asr_text']='changed fixture';rewrite(folder/'application/FINAL_SNAPSHOT.json',snapshot)
        with self.assertRaisesRegex(ValueError,'Latest viewport metadata differs'):review.review_cell(folder,**args)
