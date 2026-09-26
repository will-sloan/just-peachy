"""Real native/roster readers and synthetic stopped-run joins. README_RESTART_CONTENT_RUN.md."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, fingerprint, freeze, load
from mode_galleries import backend_contract
from review_viewport_evidence import review as viewport_review
from viewport_ledger_v2 import ViewportLedger
from test_restart_native_content import write_session, relocate
from test_native_widget_review import NativeWidgetTests
import test_native_caption_review as native_fixture
import test_restart_complete as previous
import review_restart_content_cell as cell
import review_restart_content_run_v2 as subject
from test_restart_run_review_v2 import fixture as v2_fixture

CONTEXT = {}


class ContentCellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_fixture.SOURCE=Path(load(CONTEXT['source_receipt']['path'])['prototype'])
        native_fixture.NativeCaptionTests.setUpClass()

    def setUp(self):
        self.root=CONTEXT['output']/self._testMethodName;self.root.mkdir()

    def fixture(self, baseline=False, wrong_text=False, missing_spans=False):
        folder=self.root/'cell';app=folder/'application'
        native_fixture.OUTPUT=self.root
        native=native_fixture.NativeCaptionTests('test_actual_span_state_rewrite_identity_zero_and_formatting')
        native.setUp();native.job['frames']=320000;native.scenario()
        native.folder=app/'data/sessions';native.folder.mkdir(parents=True)
        sources=[write_session(native,name='first',delivered=160000),
                 write_session(native,name='second',origin=300.,delivered=320000)]
        helper=NativeWidgetTests();helper.native=native
        first=relocate(helper.observations(),'first',0.)
        second=relocate(helper.observations(),'second',200.)
        for observation in second:
            observation['source_elapsed_sec']=observation['observed_monotonic_sec']-300.
            observation['rows']=deepcopy(first[-1]['rows'])+observation['rows']
        if wrong_text:second[-1]['rows'][0]['panes']['active']['applied_caption_text']='Fabricated retained words'
        if missing_spans:second=second[:1]
        evidence=[CONTEXT['source_receipt']];views=[]
        for index,values in enumerate((first,second)):
            target=app/'viewport' if index==0 else app/'sessions/02/viewport'
            ledger=ViewportLedger(target)
            for value in values:ledger.add(value)
            ledger.close();summary=bind(target/'SUMMARY.json');review=viewport_review(summary)
            evidence.extend([summary,review['evidence']]);views.append(dict(reconstruction=review))
        catalog=load(CONTEXT['catalog']['path'])
        key='baseline' if baseline else next(row['key'] for row in catalog['backends']
            if row['key']!='baseline' and backend_contract(catalog,row['key'],'open_with_names')['uses_n2'])
        contract=backend_contract(catalog,key,'open_with_names')
        payload=dict(cell_id='synthetic-cell',job=native.job,contract=contract,
            **{k:CONTEXT[k] for k in ('source_receipt','catalog','gallery_preparation','runtimes')})
        gallery=load(CONTEXT['gallery_preparation']['path'])['encoders'][contract['encoder']]['conditions']['open']
        people=[dict(id=p['profile_id'],name=p['name']) for p in load(gallery['condition']['gallery']['path'])['profiles']]
        if baseline:people.sort(key=lambda p:p['name'])
        freeze(app/'PREPARED.json',dict(gallery_condition=gallery['condition'],selected_ids=[]))
        evidence.append(bind(app/'PREPARED.json'))
        for number in ('01','02'):
            freeze(app/'sessions'/number/'CONTROLLER_SNAPSHOT.json',dict(people=people,roster_compatibility=people,
                mode='open_with_names',selected_ids=[],strict=False,text_assistance=dict(enabled=False),settings={},
                reference_comparison=None,rows=[]))
            evidence.append(bind(app/'sessions'/number/'CONTROLLER_SNAPSHOT.json'))
        for source in sources:evidence+=source['envelope']['journal']+source['envelope']['terminal']
        pair=dict(full_job_sha256=fingerprint(native.job),sessions=[dict(index=i,native_session=str(s['session']),
            intent=s['intent'],delivered_frames=s['delivered_frames']) for i,s in enumerate(sources)],
            native_reviews=[s['envelope'] for s in sources])
        base=dict(status='PASS_RESTART_TRANSPORT_AND_OBSERVATIONS_JOINED_ONLY',cell_id=payload['cell_id'],
            transport=dict(pair_review=pair,application=dict(pid=2147483100,create_time=1.),
                           coordinator=dict(pid=2147483101,create_time=1.)),
            observations=dict(viewport_reviews=views),joins=dict(evidence=evidence),
            native_caption_payloads_joined=False,actual_restart_qualified=False,N4_accepted=False,integrated_N4_cells=0,
            source_to_widget_latency_qualified=False,controlled_resources_qualified=False)
        return folder,payload,base

    def checked(self, folder, payload, base):
        with patch.object(cell,'review_complete',return_value=base):return cell.review_cell(folder,payload=payload)

    def rewrite_snapshot(self, folder, base, mutate):
        path=folder/'application/sessions/02/CONTROLLER_SNAPSHOT.json';value=load(path);mutate(value)
        import json
        path.write_text(json.dumps(value),encoding='utf-8')
        base['joins']['evidence']=[bind(path) if b['path']==str(path.resolve()) else b for b in base['joins']['evidence']]

    def test_both_native_histories_and_actual_fixed_roster_join(self):
        folder,payload,base=self.fixture();result=self.checked(folder,payload,base)
        self.assertTrue(result['fixed_display_roster_independently_joined']);self.assertTrue(result['native_caption_payloads_joined'])
        self.assertEqual([w['native_span_population'] for w in result['widgets']],[4,8])
        self.assertEqual({s['native_session'] for s in result['widgets'][1]['states'].values()},{'first','second'})
        for flag in ('N4_accepted','actual_restart_qualified','source_to_widget_latency_qualified','controlled_resources_qualified',
                     'exact_consumed_event_attribution','names_independently_scored'):
            self.assertIs(result[flag],False)
        freeze(self.root/'SYNTHETIC_CONTENT.json',result)

    def test_baseline_roster_is_checked_without_loading_vectors(self):
        result=self.checked(*self.fixture(baseline=True))
        self.assertEqual([r['ordering'] for r in result['rosters']],['baseline_sorted_display_name']*2)
        self.assertTrue(all(r['vectors_loaded'] is False for r in result['rosters']))

    def test_changed_second_roster_refused(self):
        folder,payload,base=self.fixture()
        self.rewrite_snapshot(folder,base,lambda v:v['people'][0].update(name='Foreign name'))
        with self.assertRaisesRegex(ValueError,'Observed display roster'):self.checked(folder,payload,base)

    def test_second_session_manual_edits_refused(self):
        folder,payload,base=self.fixture()
        self.rewrite_snapshot(folder,base,lambda v:v.update(rows=[dict(manual_edit='changed',show_corrected_text=True)]))
        with self.assertRaisesRegex(ValueError,'manual or optional'):self.checked(folder,payload,base)

    def test_snapshot_changed_after_complete_reader_refused(self):
        folder,payload,base=self.fixture();path=folder/'application/sessions/02/CONTROLLER_SNAPSHOT.json'
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'not checked by the complete'):self.checked(folder,payload,base)

    def test_swapped_native_sessions_refused(self):
        folder,payload,base=self.fixture();base['transport']['pair_review']['sessions'].reverse()
        with self.assertRaisesRegex(ValueError,'order or path'):self.checked(folder,payload,base)

    def test_full_job_cannot_be_shortened_to_first_delivery(self):
        folder,payload,base=self.fixture();payload=deepcopy(payload);payload['job']['frames']=160000
        with self.assertRaisesRegex(ValueError,'full planned source'):self.checked(folder,payload,base)

    def test_released_delivery_cannot_be_relabelled(self):
        folder,payload,base=self.fixture();base['transport']['pair_review']['sessions'][0]['delivered_frames']=320000
        with self.assertRaises(ValueError):self.checked(folder,payload,base)

    def test_independent_viewport_reconstruction_must_match(self):
        folder,payload,base=self.fixture();base['observations']['viewport_reviews'][1]['reconstruction']['observations']+=1
        with self.assertRaisesRegex(ValueError,'viewport or roster join'):self.checked(folder,payload,base)

    def test_fabricated_retained_words_fail_real_native_reader(self):
        with self.assertRaisesRegex(ValueError,'compatible preceding'):self.checked(*self.fixture(wrong_text=True))

    def test_missing_spans_remain_in_denominator(self):
        result=self.checked(*self.fixture(missing_spans=True));widget=result['widgets'][1]
        self.assertGreater(len(widget['native_spans_not_observed']),0)
        self.assertEqual(widget['native_span_population'],8);self.assertFalse(result['actual_restart_qualified'])

    def test_foreign_context_fails_before_complete_reader(self):
        folder,payload,base=self.fixture();payload=deepcopy(payload);payload['catalog']['sha256']='0'*64
        with patch.object(cell,'review_complete') as reader,self.assertRaisesRegex(ValueError,'qualified application context'):
            cell.review_cell(folder,payload=payload)
        reader.assert_not_called()

    def test_native_reader_cannot_add_unreviewed_evidence(self):
        folder,payload,base=self.fixture();foreign=self.root/'foreign.json';freeze(foreign,{'unrelated':True})
        original=cell.review_widget
        def changed(*a,**kw):
            value=original(*a,**kw);value['evidence'].append(bind(foreign));return value
        with patch.object(cell,'review_widget',changed),self.assertRaisesRegex(ValueError,'outside the independently'):
            self.checked(folder,payload,base)


class ContentPopulationTests(unittest.TestCase):
    def setUp(self):
        self.folder=CONTEXT['output']/self._testMethodName;self.folder.mkdir()

    def population(self):
        with patch.object(previous,'fixture',side_effect=v2_fixture):
            context,values=previous.RestartCompleteTests.population(self)
        for value in values:
            value.update(status=subject.CELL_STATUS,native_caption_payloads_joined=True,
                fixed_display_roster_independently_joined=True,source_delivery_independently_joined=True,
                widgets=[dict(native_span_population=4,observed_span_population=3),
                         dict(native_span_population=8,observed_span_population=6)])
        return context,values

    def driver(self, context, values, hook=None):
        calls=[]
        def read(folder,**kwargs):
            index=len(calls);calls.append(kwargs)
            if hook:hook(index)
            return deepcopy(values[index])
        with patch.object(subject,'execution_payload',side_effect=lambda plan,i:dict(cell_id=plan['rows'][i]['cell_id'],job=plan['rows'][i]['job'])), \
                patch.object(subject,'review_cell',side_effect=read):
            result=subject.review_population(context,self.folder/'review',checkpoint=lambda:None)
        return result,calls

    test_complete_driver_preserves_both_pair_reviews_and_missing_measurement=previous.RestartCompleteTests.test_complete_driver_preserves_both_pair_reviews_and_missing_measurement
    test_late_input_mutation_refused_after_first_pair_saved=previous.RestartCompleteTests.test_late_input_mutation_refused_after_first_pair_saved
    test_application_identity_or_session_reuse_between_pairs_refused=previous.RestartCompleteTests.test_application_identity_or_session_reuse_between_pairs_refused
    test_second_pair_reader_failure_preserves_first_without_terminal_success=previous.RestartCompleteTests.test_second_pair_reader_failure_preserves_first_without_terminal_success

    def test_missing_pair_refused_before_reader(self):
        context,values=self.population();context['terminal']=dict(context['terminal'],completed=1)
        with patch.object(subject,'review_cell') as reader,self.assertRaisesRegex(ValueError,'Terminal run'):
            subject.review_population(context,self.folder/'review',checkpoint=lambda:None)
        reader.assert_not_called()

    def test_lifecycle_only_cell_cannot_pass_content_population(self):
        context,values=self.population();values[0]['native_caption_payloads_joined']=False
        with self.assertRaisesRegex(ValueError,'incomplete observation'):self.driver(context,values)

    def test_next_receipt_bound_preserves_previous_receipts(self):
        output=self.folder/'bounded';freeze(output/'first.json',{'preserved':True})
        with patch.object(subject,'OUTPUT_LIMIT',66000),self.assertRaisesRegex(ValueError,'output bound'):
            subject.freeze_bounded(output/'second.json',{'data':'x'*1000},output)
        self.assertEqual(load(output/'first.json'),{'preserved':True});self.assertFalse((output/'second.json').exists())

    def test_receipt_bound_counts_utf8_and_platform_newlines(self):
        output=self.folder/'bounded';value={'text':'\u00e9\nsecond line'}
        subject.freeze_bounded(output/'first.json',value,output)
        size=(output/'first.json').stat().st_size
        with patch.object(subject,'OUTPUT_LIMIT',size*2+65536):
            subject.freeze_bounded(output/'second.json',value,output)
        self.assertEqual((output/'second.json').stat().st_size,size)
