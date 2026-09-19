"""Model-free private-store regressions; synthetic vectors stay in OS temp folders."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from app.people import PersonalStore,PREPROCESSING,route_compatible,vector_valid

BACKEND='a'*64
ROUTE=dict(tap='O0',sample_rate=16000,gain_policy='fixture_unity',preprocessing=PREPROCESSING,waveform_domain='dry_test_fixture')


def quality(seed='fixture'):
    return dict(can_save=True,gaps=0,elapsed_s=15.,usable_s=15.,target_sec=15,
        accepted_intervals=[[float(n),float(n)+.5] for n in np.arange(0,15,.5)],
        source_sha256=hashlib.sha256(seed.encode()).hexdigest(),source_kind='file_fixture',
        source_session_id=seed,clipping=0.,consistency=.9,embedding_count=30)


class PersonalStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='PROTO1 synthetic people tests ')
        self.root=Path(self.temp.name)
        self.store=PersonalStore(self.root/'people',BACKEND)
        self.vector=np.zeros(192,np.float32);self.vector[0]=1.

    def tearDown(self):self.temp.cleanup()

    def save(self,name='Fixture person',seed='fixture'):
        return self.store.save(name,self.vector,quality(seed),ROUTE)

    def archive(self):
        path=self.root/'export.zip';self.store.export(path,consent=True);return path

    def mutated_archive(self,mutate):
        original=self.archive()
        with zipfile.ZipFile(original) as z:files={n:z.read(n) for n in z.namelist() if n!='MANIFEST.json'}
        mutate(files)
        target=self.root/'mutated.zip'
        with zipfile.ZipFile(target,'w') as z:
            for name,data in files.items():z.writestr(name,data)
            z.writestr('MANIFEST.json',json.dumps(dict(schema_version=1,files={n:hashlib.sha256(v).hexdigest() for n,v in files.items()})))
        return target

    @staticmethod
    def edit_person(files,edit):
        name=next(n for n in files if n.endswith('/person.json'));row=json.loads(files[name]);edit(row);files[name]=json.dumps(row).encode()

    def test_save_reload_query_duplicate_names_use_uuids(self):
        first=self.save();second=self.save(seed='second')
        loaded=PersonalStore(self.root/'people',BACKEND)
        gallery=loaded.gallery(ROUTE);scores=gallery.score(self.vector)
        self.assertEqual(len(scores),2);self.assertEqual({s['profile_id'] for s in scores},{first['id'],second['id']})
        self.assertEqual(scores[0]['name'],scores[1]['name'])
        self.assertEqual(gallery.query_count,1)

    def test_rename_changes_binding_not_uuid(self):
        row=self.save();old=self.store.gallery(ROUTE).gallery_id
        self.store.rename(row['id'],'MiXeD Fixture')
        gallery=self.store.gallery(ROUTE)
        self.assertNotEqual(old,gallery.gallery_id);self.assertEqual(gallery.ids,[row['id']]);self.assertEqual(gallery.names,['MiXeD Fixture'])

    def test_added_reference_changes_binding(self):
        row=self.save();old=self.store.gallery(ROUTE).gallery_id
        self.store.save(row['name'],self.vector,quality('new source'),ROUTE,person_id=row['id'])
        gallery=self.store.gallery(ROUTE)
        self.assertNotEqual(old,gallery.gallery_id);self.assertEqual(len(gallery.receipt['templates'][0]['references']),2)

    def test_delete_invalidates_gallery(self):
        row=self.save();self.store.delete(row['id'])
        self.assertEqual(self.store.list(),[]);self.assertEqual(self.store.gallery(ROUTE).score(self.vector),[])

    def test_exact_duplicate_reference_refused(self):
        row=self.save()
        with self.assertRaises(ValueError):self.store.save(row['name'],self.vector,quality(),ROUTE,person_id=row['id'])
        self.assertEqual(len(self.store.list()[0]['references']),1)

    def test_route_and_fixture_domains_do_not_silently_mix(self):
        self.save();route=dict(ROUTE,waveform_domain='xvf_ua',gain_policy='O0_host_plus3dB_once')
        self.assertFalse(route_compatible(ROUTE,route))
        with self.assertRaisesRegex(ValueError,'none match'):self.store.gallery(route)
        with self.assertRaises(ValueError):self.store.gallery(dict(ROUTE,tap='O1',gain_policy='O0_host_plus3dB_once',waveform_domain='xvf_ua'))

    def test_quality_support_and_gaps_enforced(self):
        invalid=[dict(gaps=1),dict(usable_s=float('nan')),dict(usable_s=-1),dict(accepted_intervals=[[0,10],[5,10]]),dict(usable_s=14.5),dict(clipping=.1),dict(consistency=.1)]
        for update in invalid:
            with self.subTest(update=update),self.assertRaises(ValueError):self.store.save('Fixture',self.vector,dict(quality(),**update),ROUTE)
        self.assertEqual(self.store.list(),[])

    def test_nonfinite_and_wrong_shape_rejected(self):
        for vector in [np.full(192,np.nan,np.float32),np.ones(191,np.float32),np.zeros(192,np.float32)]:
            with self.assertRaises(ValueError):self.store.save('Fixture',vector,quality(),ROUTE)

    def test_large_finite_input_normalizes_without_overflow(self):
        result=vector_valid(np.full(192,1e30,np.float32))
        self.assertAlmostEqual(float(np.linalg.norm(result)),1.,places=5)

    def test_export_import_explicit_consent_and_roundtrip(self):
        row=self.save();path=self.root/'profiles.zip'
        with self.assertRaises(ValueError):self.store.export(path)
        self.store.export(path,consent=True)
        other=PersonalStore(self.root/'other',BACKEND)
        with self.assertRaises(ValueError):other.import_archive(path)
        other.import_archive(path,consent=True)
        self.assertEqual(other.gallery(ROUTE).ids,[row['id']])
        with self.assertRaises(ValueError):other.import_archive(path,consent=True)

    def test_invalid_import_metadata_is_not_published(self):
        self.save()
        path=self.mutated_archive(lambda files:self.edit_person(files,lambda row:row['references'][0].update(usable_s=-15)))
        other=PersonalStore(self.root/'other',BACKEND)
        with self.assertRaises(ValueError):other.import_archive(path,consent=True)
        self.assertEqual(other.list(),[])

    def test_invalid_backend_import_not_published(self):
        self.save();other=PersonalStore(self.root/'other','b'*64)
        with self.assertRaises(ValueError):other.import_archive(self.archive(),consent=True)
        self.assertEqual(other.list(),[])

    def test_npy_shape_preflight_prevents_unbounded_allocation(self):
        self.save()
        def alter(files):
            name=next(n for n in files if n.endswith('.npy'))
            out=io.BytesIO();np.lib.format.write_array_header_1_0(out,dict(descr='<f4',fortran_order=False,shape=(10**12,)))
            files[name]=out.getvalue()
            self.edit_person(files,lambda row:row['references'][0].update(sha256=hashlib.sha256(files[name]).hexdigest()))
        path=self.mutated_archive(alter);other=PersonalStore(self.root/'other',BACKEND)
        with self.assertRaises(ValueError):other.import_archive(path,consent=True)
        self.assertEqual(other.list(),[])

    def test_failed_multi_person_import_rolls_back_new_uuids(self):
        self.save(seed='one');self.save(seed='two');archive=self.archive()
        other=PersonalStore(self.root/'other',BACKEND)
        original=__import__('os').replace;calls=[]
        def fail_second(src,dst):
            calls.append(dst)
            if len(calls)==2:raise OSError('Injected atomic publish failure')
            return original(src,dst)
        with patch('app.people.os.replace',side_effect=fail_second),self.assertRaises(OSError):other.import_archive(archive,consent=True)
        self.assertEqual(other.list(),[])

    def test_reader_waits_for_mutation_lock(self):
        self.save();started=threading.Event();done=threading.Event()
        def reader():started.set();self.store.list();done.set()
        with self.store._lock:
            thread=threading.Thread(target=reader);thread.start();self.assertTrue(started.wait(1));self.assertFalse(done.wait(.05))
        thread.join(1);self.assertTrue(done.is_set())

    def test_save_metadata_failure_removes_new_vector(self):
        with patch('app.people.atomic_json',side_effect=OSError('Injected write failure')),self.assertRaises(OSError):self.save()
        self.assertEqual(list((self.root/'people').iterdir()),[])

    def test_ui_metadata_cache_avoids_vector_io_and_cannot_be_mutated(self):
        row=self.save()
        with patch.object(self.store,'_load_vector',wraps=self.store._load_vector) as load:
            first=self.store.list();self.assertEqual(load.call_count,1)
            first[0]['name']='External mutated returned object'
            first[0]['references'][0]['source_spans'][0][0]=999
            for _ in range(25):
                self.assertEqual(self.store.list()[0]['name'],row['name'])
                self.assertEqual(self.store.summaries()[0]['references'],1)
            self.assertEqual(load.call_count,1)
        self.assertEqual(self.store.list()[0]['references'][0]['source_spans'][0][0],0.)

    def test_gallery_admission_revalidates_despite_ui_cache(self):
        row=self.save();self.store.list()
        path=self.store._path(row['id'])/row['references'][0]['vector']
        replacement=np.zeros(192,np.float32);replacement[1]=1.
        with path.open('wb') as file:np.save(file,replacement,allow_pickle=False)
        self.assertEqual(self.store.summaries()[0]['id'],row['id'])
        with self.assertRaisesRegex(ValueError,'checksum'):self.store.gallery(ROUTE)

    def test_failed_add_reference_preserves_previous_cache_and_exact_files(self):
        row=self.save();before=self.store.list()
        with patch('app.people.atomic_json',side_effect=OSError('Injected add-reference failure')),self.assertRaises(OSError):
            self.store.save(row['name'],self.vector,quality('second reference'),ROUTE,person_id=row['id'])
        self.assertEqual(self.store.list(),before)
        self.assertEqual(len(list(self.store._path(row['id']).iterdir())),2)
        self.assertEqual(len(self.store.gallery(ROUTE).receipt['templates'][0]['references']),1)


if __name__=='__main__':unittest.main(verbosity=2)
