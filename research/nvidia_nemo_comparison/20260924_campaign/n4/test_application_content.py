"""All-reader synthetic cell composition; no application or audio launch."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import unittest
from types import MethodType
from unittest.mock import patch

from common import bind, freeze, load
from mode_galleries import backend_contract
from test_application_cell_review_v2 import rewrite, rebind_closure, rebind_envelope
from test_viewport_ledger_v2 import fixture as empty_viewport
from viewport_ledger_v2 import ViewportLedger
import test_application_cell_review_v2 as cells
import test_native_caption_review as captions
from test_native_widget_review import NativeWidgetTests
import review_application_content as content

CONTEXT = {}


class ContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        captions.SOURCE = Path(load(CONTEXT['source']['path'])['prototype'])
        captions.NativeCaptionTests.setUpClass()

    def setUp(self):
        self.root = CONTEXT['output']/self._testMethodName; self.root.mkdir()
        self.number = 0

    def fixture(self, *, baseline=False, wrong_caption=False):
        self.number += 1; base = self.root/str(self.number); base.mkdir()
        cells.CONTEXT.update(CONTEXT)
        helper = cells.CellReviewTests(); helper.root = base; helper.number = 0
        folder, args = helper.fixture(); payload = args['payload']; app = folder/'application'
        prepared = load(app/'PREPARED.json'); snapshot = load(app/'FINAL_SNAPSHOT.json')
        observed = load(app/'ENGINE_CLOSURE.json'); session = Path(observed['session'])
        if baseline:
            catalog = load(payload['catalog']['path'])
            payload['contract'] = backend_contract(catalog, 'baseline', 'open_with_names')
            prepared.update(contract=payload['contract'], backend_id=next(r['manifest_id'] for r in catalog['backends'] if r['key']=='baseline'))
            snapshot['backend_id'] = prepared['backend_id']; observed['engine_class'] = 'PrototypeEngine'
        gallery = load(payload['gallery_preparation']['path'])['encoders'][payload['contract']['encoder']]['conditions']['open']
        prepared['gallery_condition'] = gallery['condition']
        people = [dict(id=p['profile_id'],name=p['name']) for p in load(gallery['condition']['gallery']['path'])['profiles']]
        if baseline: people.sort(key=lambda p:p['name'])
        snapshot.update(people=deepcopy(people), roster_compatibility=deepcopy(people), text_assistance=dict(enabled=False))
        captions.OUTPUT = base
        native = captions.NativeCaptionTests('test_actual_span_state_rewrite_identity_zero_and_formatting'); native.setUp()
        native.job = deepcopy(payload['job']); native.events = []; native.tick = 101.; native.raw_serial = 0
        native.state = native.build(native.settings(max_display_rows=512), s7=dict(mode='M2',session_id=session.name,ownership_mode='timestamped_spans_v3'))
        def emit(n, kind, body, source=None):
            n.tick += .25; body=deepcopy(body)
            body.update(publication_sequence=len(n.events)+1,publication_monotonic_sec=n.tick,
                session_id=session.name,publication_source_cursor_sec=0. if kind in ('session_started','source_started') else n.job['frames']/16000)
            if kind=='s6d_text_ready':body.update(available_at_sec=n.tick-100.-.01,observed_text_ready_at_sec=n.tick-100.-.01)
            event=dict(schema_version='edge-speech-event.v1',event_type=kind,
                source_time_sec=source if source is not None else body.get('source_end_sec',body['publication_source_cursor_sec']),
                wall_time_utc='2026-09-25T20:40:00+00:00',payload=body,journal_write_monotonic_sec=n.tick+.001)
            n.events.append(event);shown=n.state.consume(kind,body,now=n.tick+.01)
            if shown is not None:n.emit('s6d_display',shown,source=event['source_time_sec'])
            return body
        # Session identity must agree before the real state consumes each event.
        native.emit=MethodType(emit,native)
        native.emit('session_started', {})
        native.emit('source_started', dict(mode='file',path=payload['job']['audio_path'],start_sample=0,gain=1.,pacing='absolute',source_epoch_monotonic_sec=100.))
        native.scenario(); native.emit('session_completed', {})
        (session/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in native.events), encoding='utf-8')
        n = len(native.events); consumer = load(session/'s6d_consumer_closure.json')
        consumer['queues']['journal'].update(accepted=n,completed=n)
        consumer['queues']['event_consumer'].update(consumed=n,coalesced_obsolete_ui_partials=0)
        rewrite(session/'s6d_consumer_closure.json',consumer)
        observed['workers']['journal'].update(accepted=n,completed=n)
        observed['publication_census'].update(published=n,consumed=n,coalesced_obsolete_ui_partials=0)
        clock = observed['controller_clock']; clock.update(event_count=n,last_publication_sequence=n,missing_publication_sequences=0,
            event_counts=dict(Counter(e['event_type'] for e in native.events)))
        clock['source_started']['event_payload'] = deepcopy(native.events[1]['payload'])
        rewrite(app/'SOURCE_CLOCK.json',clock); rewrite(app/'ENGINE_CLOSURE.json',observed)
        widget_fixture = NativeWidgetTests(); widget_fixture.native = native
        samples = widget_fixture.observations()
        if wrong_caption: samples[-1]['rows'][-1]['panes']['active']['applied_caption_text'] = 'Fabricated caption'
        last = deepcopy(samples[-1]); last.update(observed_monotonic_sec=156.,source_elapsed_sec=56.); samples.append(last)
        ledger = ViewportLedger(base/'semantic-viewport'); ledger.add(empty_viewport(98.,[]))
        for sample in samples: ledger.add(sample)
        ledger.close()
        # These are new synthetic fixture files, not retained campaign evidence.
        log = app/'viewport/OBSERVATIONS.jsonl'; log.write_bytes(ledger.path.read_bytes())
        summary = load(ledger.directory/'SUMMARY.json'); summary['log'] = bind(log)
        rewrite(app/'viewport/SUMMARY.json',summary)
        vr = load(app/'viewport/RESULT.json'); vr.update(samples=summary['samples'],render_calls=4,periodic_calls=1,ledger=bind(app/'viewport/SUMMARY.json'))
        rewrite(app/'viewport/RESULT.json',vr)
        snapshot['rows'] = []
        for raw in samples[-1]['rows']:
            row = {k:deepcopy(v) for k,v in raw.items() if k not in ('row_id','panes','verified_profile_id','caption_visible','heading_visible','strictly_filtered')}
            row.update(id=raw['row_id'], profile_id=raw['verified_profile_id'], manual_edit=None, show_corrected_text=False)
            snapshot['rows'].append(row)
        rewrite(app/'FINAL_SNAPSHOT.json',snapshot); rewrite(app/'PREPARED.json',prepared)
        rewrite(folder/'transport/INPUT.json',payload)
        permit = load(folder/'transport/PERMIT.json'); permit['input'] = bind(folder/'transport/INPUT.json'); rewrite(folder/'transport/PERMIT.json',permit)
        from common import fingerprint
        lease = load(folder/'transport/LEASE.json'); lease['permit_sha256'] = fingerprint(permit); rewrite(folder/'transport/LEASE.json',lease)
        child = load(folder/'transport/CHILD_RESULT.json'); child['input'] = permit['input']; rewrite(folder/'transport/CHILD_RESULT.json',child)
        collected = load(folder/'COLLECTED.json'); collected['input'] = permit['input']; rewrite(folder/'COLLECTED.json',collected)
        rebind_closure(folder); rebind_envelope(folder,payload)
        return folder,args

    def test_actual_readers_join_complete_synthetic_n2_cell(self):
        folder,args = self.fixture(); result = content.review_cell(folder,**args)
        self.assertTrue(result['fixed_display_roster_independently_joined'])
        self.assertTrue(result['application_owner_and_primary_settings_joined'])
        self.assertEqual(result['widget']['native_span_population'],4)
        self.assertEqual(result['roster']['ordering'],'document_profile_order')
        for key in ('accuracy_qualified','names_independently_scored','source_to_widget_latency_qualified',
                    'exact_consumed_event_attribution','complete_panel_reviewed','N4_accepted'):
            self.assertIs(result[key],False)
        self.assertEqual(result['integrated_N4_cells'],0)
        freeze(self.root/'SYNTHETIC_CONTENT_REVIEW.json',result)

    def test_actual_readers_join_baseline_sorted_roster(self):
        folder,args = self.fixture(baseline=True); result = content.review_cell(folder,**args)
        self.assertEqual(result['roster']['ordering'],'baseline_sorted_display_name')
        self.assertFalse(result['roster']['vectors_loaded'])

    def test_snapshot_roster_cannot_change_display_spelling(self):
        folder,args = self.fixture(); path=folder/'application/FINAL_SNAPSHOT.json'; value=load(path)
        value['people'][0]['name']='Foreign display name'; rewrite(path,value)
        with self.assertRaisesRegex(ValueError,'Observed display roster'): content.review_cell(folder,**args)

    def test_snapshot_roster_order_is_not_a_set(self):
        folder,args = self.fixture(); path=folder/'application/FINAL_SNAPSHOT.json'; value=load(path)
        self.assertGreater(len(value['people']),1); value['people'].reverse(); rewrite(path,value)
        with self.assertRaisesRegex(ValueError,'Observed display roster'): content.review_cell(folder,**args)

    def test_enabled_assistance_fails_before_widget_interpretation(self):
        folder,args=self.fixture(); path=folder/'application/FINAL_SNAPSHOT.json'; value=load(path)
        value['settings']['text_assistance']=True; rewrite(path,value)
        with patch.object(content,'review_widget') as later, self.assertRaisesRegex(ValueError,'assistance/reference'):
            content.review_cell(folder,**args)
        later.assert_not_called()

    def test_manual_correction_is_not_primary_caption_evidence(self):
        folder,args=self.fixture(); path=folder/'application/FINAL_SNAPSHOT.json'; value=load(path)
        value['rows'][0]['manual_edit']=dict(text='Fixture edit'); rewrite(path,value)
        with self.assertRaisesRegex(ValueError,'manual or optional'): content.review_cell(folder,**args)

    def test_valid_transport_does_not_certify_wrong_widget_text(self):
        folder,args=self.fixture(wrong_caption=True)
        with self.assertRaisesRegex(ValueError,'compatible preceding'): content.review_cell(folder,**args)

    def test_valid_envelope_does_not_certify_corrupt_native_partition(self):
        folder,args=self.fixture(); session=Path(load(folder/'application/ENGINE_CLOSURE.json')['session'])
        rows=[json.loads(line) for line in (session/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        next(e['payload'] for e in rows if e['event_type']=='s6d_display')['segments'][0]['raw_text']='Fabricated'
        (session/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in rows),encoding='utf-8');rebind_envelope(folder,args['payload'])
        with self.assertRaisesRegex(ValueError,'fragment changed'): content.review_cell(folder,**args)

    def test_foreign_source_context_fails_before_cell_review(self):
        folder,args=self.fixture(); args['payload']['gallery_preparation']=dict(args['payload']['gallery_preparation'],sha256='0'*64)
        with patch.object(content,'review_evidence') as later,self.assertRaisesRegex(ValueError,'qualified application context'):
            content.review_cell(folder,**args)
        later.assert_not_called()

    def test_changed_snapshot_between_readers_is_rejected(self):
        folder,args=self.fixture(); original=content.review_evidence
        def changed(*a,**kw):
            result=original(*a,**kw);path=folder/'application/FINAL_SNAPSHOT.json';value=load(path)
            value['people'][0]['name']='Changed after first reader';rewrite(path,value);return result
        with patch.object(content,'review_evidence',changed),self.assertRaisesRegex(ValueError,'not checked by the cell reader'):
            content.review_cell(folder,**args)

    def roster_fixture(self, baseline=False):
        folder,args=self.fixture(baseline=baseline);payload=deepcopy(args['payload'])
        prepared=load(folder/'application/PREPARED.json');snapshot=load(folder/'application/FINAL_SNAPSHOT.json')
        galleries=load(payload['gallery_preparation']['path'])
        return folder,payload,prepared,snapshot,galleries

    def test_roster_denominators_are_not_inferred_from_observed_people(self):
        folder,payload,prepared,snapshot,galleries=self.roster_fixture()
        condition=galleries['encoders'][payload['contract']['encoder']]['conditions']['open']['condition']
        condition['intended_size']+=1;prepared['gallery_condition']=deepcopy(condition)
        path=folder/'altered-gallery.json';freeze(path,galleries);payload['gallery_preparation']=bind(path)
        with self.assertRaisesRegex(ValueError,'Roster denominators'): content.fixed_roster(payload,prepared,snapshot)

    def test_changed_baseline_metadata_is_not_a_compatible_roster(self):
        folder,payload,prepared,snapshot,galleries=self.roster_fixture(baseline=True)
        row=galleries['encoders']['E0']['conditions']['open'];manifest=load(row['baseline_manifest']['path'])
        manifest['profiles'][0]['display_name']='Foreign display name'
        # The expected root remains the actual bound root; this helper test
        # reaches the roster mismatch before attempting any profile file reads.
        manifest_path=folder/'GALLERY.json';freeze(manifest_path,manifest)
        row['baseline_manifest']=bind(manifest_path)
        manifest['profile_root']=str(folder/'profiles');(folder/'profiles').mkdir();rewrite(manifest_path,manifest);row['baseline_manifest']=bind(manifest_path)
        path=folder/'altered-gallery.json';freeze(path,galleries);payload['gallery_preparation']=bind(path)
        with self.assertRaisesRegex(ValueError,'display rosters differ'): content.fixed_roster(payload,prepared,snapshot)
