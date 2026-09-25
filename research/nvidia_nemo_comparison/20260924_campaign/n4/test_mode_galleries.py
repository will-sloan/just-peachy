"""Integrity and actual policy-mode tests; see README_MODE_GALLERIES.md."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from common import bind, fingerprint, freeze, load
from mode_galleries import (CONDITIONS, ROW_FIELDS, verified_primary, materialize_baseline,
    backend_contract, configure_actual_mode)


class TestModeGalleries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path(os.environ.get('JP_N4_SOURCE',r'G:\Just_Peachy_N1\20260924_campaign\local\releases\n4-catalog-v3\prototype'))
        sys.path[:0]=[str(cls.source),str(cls.source/'vendor')]
        cls.catalog=load(cls.source/'config/backends.json')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.namespace=dict(model_sha256='a'*64,preprocessing='mono-float32-16k-redimnet2-native-l2-v1',
            dimension=192,normalization='L2',minimum_samples=8000)

    def fixture(self):
        original_namespace={**self.namespace,'preprocessing':'original_redimnet2_b2_fp32_graph_waveform_mono16k_gain1'}
        rows=[]; documents=[]
        for mode in sorted(set(CONDITIONS.values())):
            profiles=[] if mode=='none' else [dict(profile_id='ref-1',name='Protocol One',vector=[1.]+[0.]*191,
                unique_sec=15.,provenance={'role':'E'})]
            count=len(profiles)
            document=dict(schema='just-peachy.n2.gallery.v1',namespace=original_namespace,profiles=profiles,
                domain='clean_source',duration_sec=15,roster_id='roster-'+mode,mode=mode,position='original',
                stream='mono16k',intended_size=count+(mode!='none'),available_size=count,
                unavailable_count=int(mode!='none'),matched_duration_diagnostic=False,
                calibration=dict(status='UNCALIBRATED_REJECT_ALL',gallery_profiles_sha256=fingerprint(profiles)))
            path=self.root/(mode+'-source.json'); freeze(path,document)
            rows.append(dict(gallery_id='gallery-'+mode,roster_id=document['roster_id'],mode=mode,
                domain='clean_source',position='original',stream='mono16k',tier_seconds=15,
                matched_duration_diagnostic=False,intended_size=document['intended_size'],available_size=count,
                unavailable_count=document['unavailable_count'],gallery=bind(path)))
            documents.append(document)
        result_path=self.root/'RESULT.json'; freeze(result_path,dict(status='COMPLETE',encoder='E0',galleries=rows))
        receipt_path=self.root/'RECEIPT.json'; freeze(receipt_path,dict(status='COMPLETE',encoder='E0',private_result=bind(result_path)))
        safe=[]
        for row,doc in zip(rows,documents):
            doc=deepcopy(doc); old=doc['namespace'];doc['namespace']=self.namespace
            doc['research_only']=True
            doc['publication_provenance']=dict(component_result=bind(result_path),source_gallery=row['gallery'],
                source_namespace=old,metadata_alias_only=True,vectors_changed=False)
            gate=doc['calibration'];gate['namespace']=self.namespace;gate['namespace_sha256']=fingerprint(self.namespace)
            gate['source_evaluator_profiles_sha256']=gate.pop('gallery_profiles_sha256')
            gate['gallery_profiles_sha256']=fingerprint(doc['profiles']);gate['gate_sha256']=fingerprint(gate)
            path=self.root/(row['mode']+'-runtime.json');freeze(path,doc)
            safe.append({**row,'gallery':bind(path)})
        index_path=self.root/'INDEX.json';freeze(index_path,dict(schema='n2-runtime-safe-gallery-index-v1',encoder='E0',
            namespace=self.namespace,conditions=safe))
        return index_path,receipt_path

    def rewrite(self,path,value): path.write_text(json.dumps(value),encoding='utf-8')

    def test_primary_rosters_keep_missing_denominators_and_profiles(self):
        ip,rp=self.fixture(); rows=verified_primary(bind(ip),bind(rp),'E0')
        self.assertEqual(set(rows),set(CONDITIONS.values()))
        self.assertEqual(rows['open']['condition']['intended_size'],2)
        self.assertEqual(rows['open']['condition']['unavailable_count'],1)
        self.assertEqual(len(rows['open']['document']['profiles']),1)

    def test_changed_published_vector_rejected_even_after_index_rebind(self):
        ip,rp=self.fixture();index=load(ip); row=next(r for r in index['conditions'] if r['mode']=='open')
        p=Path(row['gallery']['path']);g=load(p);g['profiles'][0]['vector']=[0.,1.]+[0.]*190
        self.rewrite(p,g);row['gallery']=bind(p);self.rewrite(ip,index)
        with self.assertRaisesRegex(ValueError,'vector/namespace'):verified_primary(bind(ip),bind(rp),'E0')

    def test_forged_gate_rejected_without_fitting_or_query(self):
        ip,rp=self.fixture();index=load(ip);row=index['conditions'][0];p=Path(row['gallery']['path']);g=load(p)
        g['calibration']['status']='CALIBRATED';self.rewrite(p,g);row['gallery']=bind(p);self.rewrite(ip,index)
        with self.assertRaisesRegex(ValueError,'reject-all'):verified_primary(bind(ip),bind(rp),'E0')

    def test_missing_duplicate_foreign_and_evaluator_index_fields_rejected(self):
        ip,rp=self.fixture(); original=load(ip)
        for transform in (lambda x:x['conditions'].pop(),lambda x:x['conditions'].append(x['conditions'][0]),
                          lambda x:x.update(encoder='E1'),lambda x:x['conditions'][0].update(Q_truth='forbidden'),
                          lambda x:x['conditions'][0].update(unavailable_count=9)):
            index=deepcopy(original);transform(index);self.rewrite(ip,index)
            with self.assertRaises(ValueError):verified_primary(bind(ip),bind(rp),'E0')

    def test_original_gallery_corruption_rejected(self):
        ip,rp=self.fixture();r=load(load(rp)['private_result']['path'])['galleries'][0]
        Path(r['gallery']['path']).write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Binding changed'):verified_primary(bind(ip),bind(rp),'E0')

    def test_baseline_actual_profilestore_roundtrip_and_mutation_refusal(self):
        from edge_speech_pipeline.research_identity_v3 import ResearchGallery
        ip,rp=self.fixture();row=verified_primary(bind(ip),bind(rp),'E0')['open']
        manifest=materialize_baseline(row,self.root/'bridge')
        gallery=ResearchGallery(manifest['path'],self.namespace['model_sha256'])
        self.assertEqual(gallery.ids,['ref-1']);self.assertEqual(gallery.score(gallery.matrix[0])[0]['cosine'],1.)
        self.assertEqual(load(manifest['path'])['provenance_binding'],row['condition']['gallery'])
        with self.assertRaisesRegex(ValueError,'Preserve'):materialize_baseline(row,self.root/'bridge')
        p=Path(load(manifest['path'])['profiles'][0]['vector']['path']);p.write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError,'byte binding'):ResearchGallery(manifest['path'],self.namespace['model_sha256'])

    def test_wrong_encoder_and_path_traversal_cannot_materialize(self):
        ip,rp=self.fixture();row=verified_primary(bind(ip),bind(rp),'E0')['open']
        wrong=deepcopy(row);wrong['namespace']['preprocessing']='nemo-other-space'
        with self.assertRaisesRegex(ValueError,'E0'):materialize_baseline(wrong,self.root/'wrong')
        row['document']['profiles'][0]['profile_id']='../outside'
        with self.assertRaisesRegex(ValueError,'filename'):materialize_baseline(row,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())

    def start(self,key,mode,gallery=None):
        from app.pipeline import effective_profile
        from edge_speech_pipeline.research_s6d import S6DSettings,build_s6d_scheduler
        from edge_speech_pipeline.research_s7_policy import ObservedClock
        from component_s7_replay import ReplayClock
        profile=effective_profile('balanced',mode,'O0');clock=ReplayClock();observed=ObservedClock(clock=clock);observed.set_origin(0.)
        dispatcher=build_s6d_scheduler(profile,gallery,None,lambda r:None,S6DSettings(),observed_clock=observed)
        self.addCleanup(lambda:dispatcher.worker.close(timeout=5.) if not dispatcher.worker.closed else None)
        harness=configure_actual_mode(dispatcher,observed,profile,gallery,backend_contract(self.catalog,key,mode))
        return harness,dispatcher,clock

    def test_exact_catalog_routes_original_baseline_and_other_fifteen(self):
        from app.n2_identity import N2NameMap
        from edge_speech_pipeline.research_identity_v3 import ResearchIdentityResolver
        count=0
        for row in self.catalog['backends']:
            if not row['implemented']:continue
            h,d,_=self.start(row['key'],'anonymous_conversation');count+=1
            if row['key']=='baseline':self.assertIs(type(d.scheduler.identity_resolver.target),ResearchIdentityResolver)
            else:self.assertIs(type(h.n2_name_map),N2NameMap)
            d.worker.close(timeout=5.)
        self.assertEqual(count,16)
        for key,mode in [('multitalker','anonymous_conversation'),('baseline','spatial_assisted'),('unknown','selected_closed')]:
            with self.assertRaises(ValueError):backend_contract(self.catalog,key,mode)

    def galleries(self):
        from app.n2_identity import N2Gallery
        from edge_speech_pipeline.research_identity_v3 import ResearchGallery
        ip,rp=self.fixture();row=verified_primary(bind(ip),bind(rp),'E0')['closed']
        manifest=materialize_baseline(row,self.root/'bridge')
        return ResearchGallery(manifest['path'],self.namespace['model_sha256']),N2Gallery(row['document'],self.namespace)

    def test_actual_closed_missing_voice_annotation_differs_without_mutating_state(self):
        baseline,n2=self.galleries(); original=dict(text='unchanged',source_start_sec=0.,source_end_sec=1.,
            known_profile_id=None,naming_state='unknown',voice_available=False,segments=[])
        for key,gallery in [('baseline',baseline),('compact_eou',n2),('nemotron_hybrid',n2)]:
            h,d,_=self.start(key,'selected_closed',gallery)
            result=h.prototype_identity.annotate_caption(original)
            if key=='baseline':
                self.assertFalse(result['closed_display_assignment']['voice_identity_verified'])
                self.assertEqual(result['closed_display_assignment']['basis'],'roster_default_no_voice_match')
            else:self.assertNotIn('closed_display_assignment',result)
            self.assertNotIn('closed_display_assignment',original)
            self.assertEqual(result['text'],original['text']);d.worker.close(timeout=5.)

    def test_actual_n2_open_rejects_and_closed_assumes_without_calibration(self):
        from app.n2_identity import N2NameMap
        _,g=self.galleries();vector=[1.]+[0.]*191
        event=dict(event_id='e',source_start_sec=0.,source_end_sec=2.,available_at_sec=2.,speech=True,
            overlap=False,vector=vector,clean_intervals=[[0.,2.]],evidence_kind='mature')
        decision=dict(tracker_id='track',anonymous_label='Speaker 1',state='committed',committed=True)
        opened=N2NameMap(g).resolve(decision,event);closed=N2NameMap(g,closed=True).resolve(decision,event)
        self.assertEqual(opened['display_label'],'Unknown');self.assertFalse(opened['identity']['verified'])
        self.assertEqual(closed['naming_state'],'closed_assumption');self.assertFalse(closed['identity']['verified'])
        self.assertEqual(closed['identity']['calibration_status'],'UNCALIBRATED_REJECT_ALL')

    def test_baseline_original_thresholds_can_name_without_a_processed_gate(self):
        baseline,_=self.galleries();h,d,clock=self.start('baseline','enrolled_names',baseline)
        result=None
        for i in range(6):
            start=2.*i;end=start+2.;clock.set(end)
            event=dict(event_id=f'e{i}',source_start_sec=start,source_end_sec=end,available_at_sec=end,
                speech=True,overlap=False,vector=[1.]+[0.]*191,clean_intervals=[[start,end]],evidence_kind='mature')
            result=h.prototype_identity.resolve(dict(tracker_id='t',anonymous_label='Speaker 1',state='committed',committed=True),event)
        self.assertEqual(result['naming_state'],'confirmed')
        self.assertEqual(result['known_profile_id'],'ref-1')
        self.assertNotIn('calibration',baseline.receipt)

    def test_new_mode_instances_do_not_share_name_history(self):
        _,g=self.galleries();left,d,_=self.start('compact_eou','selected_closed',g)
        right,d2,_=self.start('compact_eou','selected_closed',g)
        left.n2_name_map.states['t']={}
        self.assertEqual(right.n2_name_map.states,{})
        self.assertIsNot(left.prototype_identity,right.prototype_identity)


if __name__=='__main__':unittest.main()
