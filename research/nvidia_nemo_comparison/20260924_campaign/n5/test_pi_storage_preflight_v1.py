"""Tiny artificial ZIP fixtures; never models, audio, network or a target device."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import pi_storage_preflight_v1 as subject


def setUpModule(): subject.pin_windows()


def sha(data): return hashlib.sha256(data).hexdigest()


def zip_bytes(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as z:
        for name,data in files:z.writestr(name,data)
    raw=stream.getvalue()
    # ZipInfo normalizes Windows separators while writing; restore deliberately
    # malformed original names in both local and central fixture headers.
    for name,_ in files:
        if '\\' in name:raw=raw.replace(name.replace('\\','/').encode(),name.encode())
    return raw


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='jp-storage-fixture-');self.root=Path(self.tmp.name)
        self.model=b'artificial model bytes';self.key=sha(self.model)
        self.assets=[dict(filename='model.onnx',sha256=self.key,bytes=len(self.model))]

    def tearDown(self):self.tmp.cleanup()

    def bundle(self, *, assets=None, extra=None, app_extra=None, mutate=None, corrupt=False):
        assets=self.assets if assets is None else assets
        app=zip_bytes([('config/assets.json',json.dumps(assets).encode()),('ui.py',b'fixture source')]+(app_extra or []))
        files={'app/release.zip':app,'models/'+self.key+'/model.onnx':self.model,
            'wheelhouse/fixture-1-py3-none-any.whl':zip_bytes([('module.py',b'fixture wheel')]),
            'install-offline.sh':b'never execute this fixture'}
        if extra:files.update(extra)
        rows=[dict(path=n,bytes=len(data),sha256=sha(data)) for n,data in files.items()]
        m=dict(schema='n5-private-offline-baseline-v1',baseline_only=True,status='ARTIFICIAL_FIXTURE_ONLY',
            application_archive='app/release.zip',application_sha256=sha(app),application_version='fixture-v1',
            N4_selected=False,files=rows)
        if mutate:mutate(m,files)
        if corrupt:files['models/'+self.key+'/model.onnx']=b'x'*len(self.model)
        raw=zip_bytes(list(files.items())+[('BUNDLE_MANIFEST.json',json.dumps(m).encode())])
        p=self.root/'bundle.zip';p.write_bytes(raw);return p,sha(raw)

    def test_full_hash_inventory_without_extraction(self):
        p,h=self.bundle();b=subject.inspect_bundle(p,h)
        self.assertEqual(b['unique_model_count'],1);self.assertEqual(b['wheel_count'],1)
        self.assertEqual(b['unique_model_bytes'],len(self.model));self.assertEqual(b['member_hashes_verified'],4)
        self.assertFalse(b['archive_extracted']);self.assertEqual(list(self.root.iterdir()),[p])

    def test_repeated_same_asset_counted_once(self):
        p,h=self.bundle(assets=self.assets*2);b=subject.inspect_bundle(p,h)
        self.assertEqual(b['unique_model_bytes'],len(self.model));self.assertEqual(b['unique_model_count'],1)

    def test_archive_and_member_corruption_refused(self):
        p,h=self.bundle()
        with self.assertRaisesRegex(ValueError,'Archive SHA256'):subject.inspect_bundle(p,'0'*64)
        p,h=self.bundle(corrupt=True)
        with self.assertRaisesRegex(ValueError,'Member hash'):subject.inspect_bundle(p,h)

    def test_missing_undeclared_and_duplicate_manifest_members(self):
        changes=[lambda m,f:m['files'].pop(),lambda m,f:m['files'].append(m['files'][0]),
            lambda m,f:f.pop('install-offline.sh')]
        for change in changes:
            p,h=self.bundle(mutate=change)
            with self.subTest(change=changes.index(change)),self.assertRaises(ValueError):subject.inspect_bundle(p,h)

    def test_unsafe_outer_and_nested_paths_refused(self):
        for name in ['../escape','/absolute','C:/drive','dir\\escape','a/./b','a//b']:
            for outer in (True,False):
                p,h=self.bundle(extra={name:b'x'} if outer else None,app_extra=None if outer else [(name,b'x')])
                with self.subTest(name=name,outer=outer),self.assertRaises(ValueError):subject.inspect_bundle(p,h)

    def test_case_collision_and_symlink_refused(self):
        raw=zip_bytes([('Name',b'a'),('name',b'b')])
        with zipfile.ZipFile(io.BytesIO(raw)) as z,self.assertRaises(ValueError):subject.inventory(z)
        stream=io.BytesIO();info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=0o120777<<16
        with zipfile.ZipFile(stream,'w') as z:z.writestr(info,b'destination')
        with zipfile.ZipFile(io.BytesIO(stream.getvalue())) as z,self.assertRaises(ValueError):subject.inventory(z)

    def test_model_aliases_and_asset_size_mismatch_refused(self):
        alias=dict(self.assets[0],filename='alias.onnx')
        p,h=self.bundle(assets=self.assets+[alias],extra={'models/'+self.key+'/alias.onnx':self.model})
        with self.assertRaisesRegex(ValueError,'different physical filenames'):subject.inspect_bundle(p,h)
        p,h=self.bundle(assets=[dict(self.assets[0],bytes=999)])
        with self.assertRaisesRegex(ValueError,'manifest join'):subject.inspect_bundle(p,h)

    def test_unsupported_schema_and_missing_runtime_refused(self):
        p,h=self.bundle(mutate=lambda m,f:m.update(baseline_only=False))
        with self.assertRaises(ValueError):subject.inspect_bundle(p,h)
        def remove_wheel(m,f):
            name=next(n for n in f if n.startswith('wheelhouse/'));del f[name]
            m['files']=[r for r in m['files'] if r['path']!=name]
        p,h=self.bundle(mutate=remove_wheel)
        with self.assertRaisesRegex(ValueError,'runtime/model'):subject.inspect_bundle(p,h)

    def test_conservative_space_boundary_and_no_existing_credit(self):
        p,h=self.bundle();b=subject.inspect_bundle(p,h);plan=subject.space_plan(b,overhead_bytes=1024)
        expected=(b['archive']['bytes']+b['extracted_bundle_logical_bytes']+
            2*b['application_unpacked_logical_bytes']+b['unique_model_bytes']+
            b['wheel_unpacked_logical_bytes']+256*1024**2+1024+subject.GIB)
        self.assertEqual(plan['required_available_bytes_with_reserve'],expected)
        self.assertEqual(plan['space_status'],'TARGET_STORAGE_UNCHECKED')
        self.assertEqual(subject.space_plan(b,overhead_bytes=1024,available_bytes=expected)['space_status'],'ESTIMATED_FIT')
        self.assertEqual(subject.space_plan(b,overhead_bytes=1024,available_bytes=expected-1)['space_status'],'INSUFFICIENT_SPACE')
        self.assertEqual(subject.space_plan(b,overhead_bytes=1024,rollback_extra_bytes=99)['required_available_bytes_with_reserve'],expected+99)
        self.assertEqual(plan['existing_file_credit_bytes'],0);self.assertFalse(plan['installation_authorized'])

    def test_invalid_budgets_and_timeout_refused(self):
        p,h=self.bundle();b=subject.inspect_bundle(p,h)
        for kwargs in [dict(overhead_bytes=0),dict(overhead_bytes=True),dict(overhead_bytes=1,reserve_bytes=0),
            dict(overhead_bytes=1,rollback_extra_bytes=-1),dict(overhead_bytes=1,available_bytes=True)]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):subject.space_plan(b,**kwargs)
        with self.assertRaisesRegex(ValueError,'time bound'):subject.inspect_bundle(p,h,max_seconds=0)

    def test_target_roots_remain_uncreated_and_overlaps_refused(self):
        install=self.root/'future-install';data=self.root/'future-data'
        with patch.object(subject.ctypes.util,'find_library',return_value='fixture-library'):
            value=subject.target_observation(install,data)
        self.assertFalse(install.exists());self.assertFalse(data.exists());self.assertFalse(value['writes_performed'])
        for other in [install,install/'data',self.root]:
            with self.subTest(other=other),self.assertRaises(ValueError):subject.target_observation(install,other)


if __name__=='__main__':subject.pin_windows();unittest.main()
