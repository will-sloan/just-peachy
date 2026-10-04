"""Host-only package protocol checks. See README_PACKAGE.md."""
import argparse
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import unittest
import uuid


def bootstrap(output_root):
    if os.name != 'nt':
        raise RuntimeError('Host package checks require Windows CPU14')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle, 1 << 14):
        raise ctypes.WinError(ctypes.get_last_error())
    values = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    root = Path(output_root)/('package-checks-'+uuid.uuid4().hex)
    root.mkdir(parents=True, exist_ok=False)
    with (root/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
            affinity_mask=16384, creation_filetime=values[0].value,
            create_time=(values[0].value-116444736000000000)/10000000), stream)
        stream.flush(); os.fsync(stream.fileno())
    return root


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True)
    ap.add_argument('--profiles', required=True)
    ap.add_argument('--output-root', required=True)
    ap.add_argument('--release-id', default='field-runtime-v29-build-01')
    args = ap.parse_args()
    root = bootstrap(args.output_root)
    sys.dont_write_bytecode = True
    sys.path.insert(0, args.source)
    import prepare_package as builder
    import install_candidate as installer
    import native_scope
    result = builder.build(args.source, args.profiles, root, release_id=args.release_id)
    archive = Path(result['archive']).read_bytes()

    class Checks(unittest.TestCase):
        def test_complete_roundtrip_and_disabled_launch(self):
            manifest, files = installer.validate_payload(archive, result['archive_sha256'], result['manifest_sha256'])
            binding = json.loads(files['BINDING.json'])
            self.assertFalse(binding['native_launch_enabled'])
            self.assertIsNone(binding['live_config']['evidence_dir'])
            self.assertEqual(result['capsule_files'], 66)
            self.assertEqual(len([name for name in files if name.startswith('reference-v28/')]), 67)
            self.assertFalse(manifest['model_or_gallery_files_copied'])
            self.assertEqual(files['installed_source.py'], files['source-backups/installed_source.py.restore'])
            self.assertEqual(binding['reference_files'][0]['path'], 'D1_ENDPOINT_CONTRACT_V3.json')

        def test_corrupt_archive_rejected_before_parse(self):
            with self.assertRaises(ValueError):
                installer.validate_payload(archive[:-1]+b'X', result['archive_sha256'], result['manifest_sha256'])

        def test_traversal_rejected_before_write(self):
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode='w:gz') as handle:
                member = tarfile.TarInfo('../outside'); member.size = 1
                handle.addfile(member, io.BytesIO(b'x'))
            payload = raw.getvalue()
            with self.assertRaises(ValueError):
                installer.validate_payload(payload, hashlib.sha256(payload).hexdigest(), '0'*64)

        def test_invalid_review_admission_cannot_enable(self):
            path = root/'invalid-admission.json'
            path.write_text(json.dumps(dict(reviewed=True, native_launch_enabled=True)))
            with self.assertRaises(ValueError):
                builder.build(args.source, args.profiles, root/'invalid-build', path)

        def test_all_file_verification_detects_tamper(self):
            path = Path(result['package'])/'source-backups/audio_journal.py.backup'
            original = path.read_bytes()
            try:
                path.write_bytes(original+b'\n')
                with self.assertRaises(ValueError):
                    installer.verify_tree(Path(result['package']), result['manifest_sha256'])
            finally:
                path.write_bytes(original)
            installer.verify_tree(Path(result['package']), result['manifest_sha256'])

        def test_finite_systemd_duration(self):
            self.assertEqual(native_scope.duration_seconds('1h 5min 2s'), 3902)
            self.assertEqual(native_scope.duration_seconds('32min'), 1920)
            with self.assertRaises(ValueError):
                native_scope.duration_seconds('infinity')

    results = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    receipt = dict(evidence=str(root), tests=results.testsRun, failures=len(results.failures),
        errors=len(results.errors), native_executed=False, package=result)
    builder.write(root/'TEST_RESULT.json', builder.encoded(receipt))
    print(builder.encoded(receipt).decode())
    return 0 if results.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
