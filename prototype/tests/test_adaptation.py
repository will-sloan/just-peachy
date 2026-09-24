"""Synthetic safety/transaction contracts; no accuracy claims. See README_ADAPTATION.md."""
from copy import deepcopy
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor'),str(ROOT/'tests')]
from app.people import PersonalStore,route_compatible
from app.reference_adaptation import BaseAnchors,SessionBank,domain,FEATURE,MAX_PENDING
from app.paths import read_json,sha256,ApplicationLock
from app.controller import Controller
from test_people import ROUTE,BACKEND,quality

def event(vector,start=0.,**kw):
    return dict(dict(source_start_sec=start,source_end_sec=start+1.5,publication_monotonic_sec=10+start,
        consumer_monotonic_sec=10.01+start,publication_source_cursor_sec=start+1.52,event_id=str(start),
        evidence_kind='mature',speech=True,overlap=False,clean_intervals=[[start,start+1.5]],
        normalized_embedding=vector.tolist(),admission={'admitted':True}),**kw)

def audio(seed=0):return np.random.default_rng(seed).uniform(-.1,.1,24000).astype(np.float32)

class AdaptationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=PersonalStore(self.root/'a'/'people',BACKEND)
        self.v=np.eye(192,dtype=np.float32)[0];self.other=np.eye(192,dtype=np.float32)[1]
        self.person=self.store.save('Actual speaker',self.v,quality(),ROUTE)
        self.competitor=self.store.save('Other speaker',self.other,quality('other'),ROUTE)
        self.gallery=self.store.gallery(ROUTE);self.bank=SessionBank(BaseAnchors(self.gallery),'fixture',collect=True)
        self.gallery.adaptation=self.bank
    def tearDown(self):self.temp.cleanup()
    def candidate(self,start=0.,seed=0,vector=None):return self.bank.observe(event(self.v if vector is None else vector,start),audio(seed),ROUTE,{'seat_name':'untrusted','revised_text':'untrusted','forced':True})
    def confirmed(self):
        c=self.candidate();self.bank.confirm(c['id'],self.person['id'],consent=True);return c
    def promote(self):
        c=self.confirmed();return self.store.promote_candidates(self.bank,[c['id']],self.person['id'],consent=True)
    def test_default_off_and_exact_score_baseline(self):
        bank=SessionBank(BaseAnchors(self.gallery),'off');self.assertFalse(bank.collect);self.assertFalse(bank.enabled)
        self.assertIsNone(bank.observe(event(self.v),audio(),ROUTE));self.confirmed()
        self.assertEqual(self.gallery.score(self.v),self.store.gallery(ROUTE).score(self.v));self.assertEqual(self.bank.query_count,0)
    def test_low_weight_changes_score_and_reload_retains_it(self):
        v=(self.v+.4*self.other);v/=np.linalg.norm(v)
        c=self.candidate(vector=v);self.bank.confirm(c['id'],self.person['id'],consent=True);self.bank.enabled=True
        original=self.store.gallery(ROUTE).score(v);changed=self.gallery.score(v)
        self.assertGreater(changed[0]['cosine'],original[0]['cosine']);self.assertLess(changed[0]['cosine']-original[0]['cosine'],.02)
        self.store.promote_candidates(self.bank,[c['id']],self.person['id'],consent=True)
        restarted=PersonalStore(self.store.root,BACKEND).gallery(ROUTE)
        restarted.adaptation=SessionBank(BaseAnchors(restarted),'restart',persisted=restarted.environment_bank)
        restarted.adaptation.enabled=True;self.assertEqual(restarted.score(v),changed)
        self.assertEqual(len(restarted.adaptation.last_match['query_vector_sha256']),64)
    def test_unique_windows_hashes_and_usable_not_wall_time(self):
        c=self.candidate();self.assertIsNotNone(c)
        self.assertIsNone(self.candidate(.5,1));self.assertIsNone(self.candidate(2,0))
        self.assertIsNotNone(self.candidate(3,2))
        state=self.bank.snapshot();self.assertEqual(state['usable_sec'],3.);self.assertEqual(state['confirmed_sec'],0.)
        self.assertEqual(state['rejected']['duplicate_or_overlapping_window'],2)
    def test_wrong_seat_forced_text_labels_cannot_confirm(self):
        c=self.candidate(vector=self.other)
        with self.assertRaises(ValueError):self.bank.confirm(c['id'],self.person['id'],consent=True)
        self.assertEqual(self.bank.frozen,'strong_base_voice_conflict');self.assertFalse(self.bank.entries())
        with self.assertRaises(ValueError):self.store.promote_candidates(self.bank,[c['id']],self.person['id'],consent=True)
        self.assertEqual(self.store.list()[0].get('environment_bank',[]),[])
    def test_explicit_consent_and_confirmation_required(self):
        c=self.candidate()
        with self.assertRaises(ValueError):self.bank.confirm(c['id'],self.person['id'])
        with self.assertRaises(ValueError):self.store.promote_candidates(self.bank,[c['id']],self.person['id'],consent=True)
        self.bank.confirm(c['id'],self.person['id'],consent=True)
        with self.assertRaises(ValueError):self.store.promote_candidates(self.bank,[c['id']],self.person['id'])
    def test_overlap_music_motion_clock_and_domain_freeze(self):
        for change in ({'overlap':True},{'music':True},{'consumer_monotonic_sec':9.},{'consumer_monotonic_sec':13.},
                       {'publication_monotonic_sec':float('nan')},{'publication_source_cursor_sec':1.0}):
            bank=SessionBank(BaseAnchors(self.gallery),'failure',collect=True)
            self.assertIsNone(bank.observe(event(self.v,**change),audio(),ROUTE));self.assertTrue(bank.frozen)
            bank.discard();self.assertTrue(bank.frozen)
        bad=dict(ROUTE,tap='O1');self.bank.observe(event(self.v),audio(),bad);self.assertEqual(self.bank.frozen,'reference_domain_mismatch')
        self.bank=SessionBank(BaseAnchors(self.gallery),'motion',collect=True);self.confirmed();self.bank.enabled=True
        self.bank.freeze('tablet_moved');plain=self.store.gallery(ROUTE).score(self.v)
        self.assertEqual(self.bank.match(self.v,plain),plain)
    def test_quality_fails_without_counting(self):
        for e,x in ((event(self.v,speech=False),audio()),(event(self.v,clean_intervals=[[0.,.5]]),audio()),
                    (event(self.v,clean_intervals=[[0.,1.],[.5,1.5]]),audio()),(event(self.v),np.ones(24000,np.float32)),
                    (event(self.v),np.zeros(24000,np.float32)),(event(self.v,evidence_kind='short'),audio())):
            self.assertIsNone(self.bank.observe(e,x,ROUTE))
        self.assertEqual(self.bank.snapshot()['usable_sec'],0.)
    def test_caps_limit_memory_and_person_weight(self):
        for i in range(MAX_PENDING+2):self.candidate(i*2.,i)
        self.assertEqual(len(self.bank.candidates),MAX_PENDING)
        for c in self.bank.candidates[:4]:self.bank.confirm(c['id'],self.person['id'],consent=True)
        with self.assertRaises(ValueError):self.bank.confirm(self.bank.candidates[4]['id'],self.person['id'],consent=True)
        self.bank.enabled=True;self.gallery.score(self.v)
        self.assertEqual(self.bank.last_match['effective_weights'][self.person['id']],.1)
    def test_bank_cannot_bootstrap_weak_or_different_winner(self):
        self.confirmed();self.bank.enabled=True
        weak=np.eye(192,dtype=np.float32)[3]
        plain=self.store.gallery(ROUTE).score(weak);self.assertEqual(self.gallery.score(weak),plain)
        self.assertFalse(self.bank.last_match['applied']);self.assertTrue(all(w==0 for w in self.bank.last_match['effective_weights'].values()))
        self.bank.enabled=False;self.assertEqual(self.gallery.score(self.v),self.store.gallery(ROUTE).score(self.v))
    def test_atomic_promotion_restart_rename_export_import_undo_delete(self):
        before={p.name:sha256(p) for p in self.store.root.rglob('*.npy')};base=self.bank.base.version;transaction=self.promote()
        store=PersonalStore(self.store.root,BACKEND);self.assertEqual(BaseAnchors(store.gallery(ROUTE)).version,base)
        store.rename(self.person['id'],'Renamed');self.assertEqual(BaseAnchors(store.gallery(ROUTE)).version,base)
        export=self.root/'profiles.zip';store.export(export,True)
        imported=PersonalStore(self.root/'b'/'people',BACKEND);imported.import_archive(export,True)
        self.assertEqual(imported.gallery(ROUTE).environment_bank[0]['transaction_id'],transaction['id'])
        self.assertIn(FEATURE,read_json(self.root/'b'/'DATA_SCHEMA.json')['required_features'])
        imported.undo_enrichment(self.person['id'],consent=True);self.assertFalse(imported.gallery(ROUTE).environment_bank)
        self.assertEqual(before,{p.name:sha256(p) for p in imported.root.rglob('*.npy')})
        imported.delete(self.person['id']);self.assertFalse((imported.root/self.person['id']).exists())
        self.assertTrue(store.gallery(ROUTE).environment_bank)
    def test_failure_before_atomic_replace_leaves_profile_unchanged(self):
        c=self.confirmed();path=self.store.root/self.person['id']/'person.json';before=path.read_bytes()
        with patch('app.adaptation_store.atomic_json',side_effect=OSError('injected disk failure')):
            with self.assertRaises(OSError):self.store.promote_candidates(self.bank,[c['id']],self.person['id'],consent=True)
        self.assertEqual(path.read_bytes(),before);self.assertEqual(len(self.bank.candidates),1)
        self.assertFalse(PersonalStore(self.store.root,BACKEND).gallery(ROUTE).environment_bank)
    def test_duplicate_promotion_and_corrupt_import_are_rejected(self):
        c=self.confirmed();self.store.promote_candidates(self.bank,[c['id']],self.person['id'],consent=True)
        self.bank.candidates.append(deepcopy(self.bank.persisted[0]))
        with self.assertRaises(ValueError):self.store.promote_candidates(self.bank,[c['id']],self.person['id'],consent=True)
        path=self.store.root/self.person['id']/'person.json';row=read_json(path);row['environment_bank'][0]['vector'][0]=.1
        path.write_text(json.dumps(row))
        with self.assertRaises(ValueError):PersonalStore(self.store.root,BACKEND).list()
    def test_saved_audio_cannot_be_collected_again_at_another_source_time(self):
        self.promote();gallery=self.store.gallery(ROUTE)
        self.bank=SessionBank(BaseAnchors(gallery),'another session',collect=True,persisted=gallery.environment_bank)
        self.assertIsNone(self.candidate(15.,0));self.assertEqual(self.bank.snapshot()['usable_sec'],0.)
    def test_shifted_window_in_same_file_replay_cannot_recount_samples(self):
        self.bank.source_id='file:'+'b'*64;self.bank.source_offset=16000;self.promote()
        gallery=self.store.gallery(ROUTE);self.bank=SessionBank(BaseAnchors(gallery),'second playback',collect=True,persisted=gallery.environment_bank)
        self.bank.source_id='file:'+'b'*64
        self.assertIsNone(self.candidate(1.5,8)) # Different waveform hash, same canonical file support.
        self.assertIsNotNone(self.candidate(4.,9))
    def test_import_rejects_unapproved_bank_before_publishing(self):
        import zipfile
        self.promote();good=self.root/'good.zip';self.store.export(good,True)
        with zipfile.ZipFile(good) as z:files={n:z.read(n) for n in z.namelist() if n!='MANIFEST.json'}
        name=self.person['id']+'/person.json';row=json.loads(files[name]);row['environment_bank'][0]['confirmation']['kind']='assigned_seat'
        files[name]=json.dumps(row).encode();bad=self.root/'bad.zip'
        with zipfile.ZipFile(bad,'w') as z:
            for name,raw in files.items():z.writestr(name,raw)
            z.writestr('MANIFEST.json',json.dumps(dict(schema_version=1,files={n:hashlib.sha256(raw).hexdigest() for n,raw in files.items()})))
        other=PersonalStore(self.root/'unapproved'/'people',BACKEND)
        with self.assertRaises(ValueError):other.import_archive(bad,True)
        self.assertEqual(other.list(),[])
    def test_changed_anchor_invalidates_old_bank(self):
        self.promote();self.store.save('Actual speaker',self.v,quality('new clean anchor'),ROUTE,person_id=self.person['id'])
        gallery=self.store.gallery(ROUTE);bank=SessionBank(BaseAnchors(gallery),'new',persisted=gallery.environment_bank)
        self.assertEqual(bank.entries(),[])
    def test_old_reader_feature_guard_and_default_off_restart(self):
        self.promote()
        with patch('app.paths.read_json',wraps=read_json) as reader:
            # Actual current reader must accept task11-marked data.
            lock=ApplicationLock(self.root/'a');lock.close()
        def old_reader(path):
            value=read_json(path)
            if Path(path).name=='release_capabilities.json':value['data_features_supported']=[v for v in value['data_features_supported'] if v!=FEATURE]
            return value
        with patch('app.paths.read_json',side_effect=old_reader):
            with self.assertRaisesRegex(ValueError,'Unsupported personal-data features'):ApplicationLock(self.root/'a')
        bank=SessionBank(BaseAnchors(self.store.gallery(ROUTE)),'restarted',persisted=self.store.gallery(ROUTE).environment_bank)
        self.assertFalse(bank.enabled);self.assertEqual(len(bank.entries()),1)
    def test_storage_cap_duplicate_source_and_undo_failure(self):
        self.promote()
        full=self.store.gallery(ROUTE);self.bank=SessionBank(BaseAnchors(full),'second',collect=True,persisted=full.environment_bank)
        for i in range(4):
            c=self.candidate(i*2.,i+10);self.bank.confirm(c['id'],self.person['id'],consent=True)
        self.store.promote_candidates(self.bank,[c['id'] for c in self.bank.candidates],self.person['id'],consent=True)
        for i in range(2):
            c=self.candidate(i*2+10.,i+20);self.bank.confirm(c['id'],self.person['id'],consent=True)
        with self.assertRaisesRegex(ValueError,'cap is six'):self.store.promote_candidates(self.bank,[c['id'] for c in self.bank.candidates],self.person['id'],consent=True)
        path=self.store.root/self.person['id']/'person.json';before=path.read_bytes()
        with patch('app.adaptation_store.atomic_json',side_effect=OSError('injected Undo disk failure')):
            with self.assertRaises(OSError):self.store.undo_enrichment(self.person['id'],consent=True)
        self.assertEqual(path.read_bytes(),before)
    def test_controller_real_motion_hook_freezes_bank(self):
        from app.seats import SeatSession
        from app.motion import MotionSafety
        from unittest.mock import Mock
        c=Controller.__new__(Controller);c.reference_bank=self.bank;c.seats=SeatSession();c.engine=None;c._record_seat_state=Mock()
        c._invalidate_seats('manual_tablet_moved');self.assertTrue(self.bank.frozen)
    def test_domains_are_never_pooled_and_legacy_is_compatible(self):
        self.assertTrue(route_compatible(ROUTE,domain(ROUTE)))
        for change in ({'tap':'O1'},{'beam_stream':'fixed_beam_1'},{'enhancement_config':'unknown'},{'enhancement':'other'}):
            self.assertFalse(route_compatible(ROUTE,dict(ROUTE,**change)))
    def test_controller_discard_reset_and_motion_preserve_transcript(self):
        c=Controller.__new__(Controller);c.reference_bank=self.bank;c.collect_references=True;c.use_references=True
        c.engine=None;c.rows={'immutable':{'text':'earlier words','label':'Original'}}
        self.confirmed();before=deepcopy(c.rows);c._do_adaptation('discard',{})
        self.assertEqual(c.rows,before);self.assertFalse(self.bank.candidates);self.assertFalse(c.use_references)
        c._adaptation_initialize();self.assertIsNone(c.reference_bank)

if __name__=='__main__':unittest.main()
