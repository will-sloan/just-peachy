"""Prepare disabled14 from actual admitted13. See README_IDENTITY_DERIVATIVE.md."""
import argparse
import ast
import ctypes
import json
import os
from pathlib import Path
import sys
import uuid

SOURCE_MANIFEST = 'a8808f4807321bfaae814a0297c7602cb071ba1f54c849381d3a4d63473fb476'
SOURCE_BINDING = 'fd7dac1400f66f54862025434af416c5b9dc5d1d9a2a86c622c5ed2aaaead04f'
SOURCE_CONTENT = '5cae6376494d703a9600c020ebce725ed0f86999d1ed4ffa613a5f1485a0fd79'
BUILDER = '0a706522770d21d8b4846d3121cc430eef81ec73fcced965eca7d804fbf47832'
OLD_BUILDER = '8deb7b4f6ae26071597b00e27b85b401f3f9606205f026fcd451b85a46099876'
REVIEW = '4639541714ea03f12665afc4bdc3d056edd2c09ee074a478889b27551c3b29f7'
REPAIRS = {
    'late_labels.py': '23f44c295133b90848c3c2ad375494739db5ca76773ecc79081070911595a0d1',
    'admitted_identity.py': '917b4746c5cc6caad2337c9f28bbd2e5752b4ab3dd3a74c54afa3d18304f7542',
    'README_LATE_LABELS.md': 'b2fae05f80599fde47638f5e47b45c96116d44af4a8adb3128913a2664e6ddd9',
    'README_IDENTITY_CORRECTION.md': '772e42f28279447078357523cf6a0081bf6a7dff19ff66150e7d7c9af323e08f',
}


def early(root):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle, 1 << 14):
        raise ctypes.WinError(ctypes.get_last_error())
    values = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    output = root / ('identity-derivative-' + uuid.uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
                       affinity_mask=16384, creation_filetime=values[0].value,
                       create_time=(values[0].value - 116444736000000000) / 10000000), stream)
        stream.flush()
        os.fsync(stream.fileno())
    return output


def prepare(args, output):
    from hashlib import sha256
    builder_path = Path(__file__).with_name('prepare_package.py')
    builder_raw = builder_path.read_bytes()
    prior_builder = args.builder_prior.read_bytes()
    if sha256(builder_raw).hexdigest() != BUILDER or sha256(prior_builder).hexdigest() != OLD_BUILDER:
        raise ValueError('Exact reviewed builder/prior required')
    before, after = ast.parse(prior_builder), ast.parse(builder_raw)
    def inventory(tree):
        statement = next(node for node in tree.body if isinstance(node, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == 'OPTIONAL_RUNTIME_FILES' for t in node.targets))
        return statement, ast.literal_eval(statement.value)
    old_statement, old_names = inventory(before)
    new_statement, new_names = inventory(after)
    if tuple(name for name in new_names if name != 'admitted_identity.py') != old_names or new_names.count('admitted_identity.py') != 1:
        raise ValueError('Only one new explicit pure runtime module is allowed')
    after.body[after.body.index(new_statement)] = old_statement
    if ast.dump(before, include_attributes=False) != ast.dump(after, include_attributes=False):
        raise ValueError('Unexpected builder behavior change')
    from prepare_package import build, encoded, strict, sha, write, read_regular, relative, operational_binding
    from install_candidate import verify_tree
    source = args.source.resolve(strict=True)
    verify_tree(source, SOURCE_MANIFEST)
    manifest = strict(read_regular(source/'PACKAGE_MANIFEST.json'))
    old_binding_raw = read_regular(source/'BINDING.json', 65536)
    old_binding = strict(old_binding_raw)
    if sha(old_binding_raw) != SOURCE_BINDING or manifest['candidate_content_sha256'] != SOURCE_CONTENT:
        raise ValueError('Actual admitted13 source identity differs')
    review_raw = read_regular(args.review, 65536)
    if sha(review_raw) != REVIEW:
        raise ValueError('Actual-row focused review pin differs')
    review = strict(review_raw)
    if (review.get('native_executed') is not False or review['counts']['actual_display_rows'] != 102
            or review['counts']['old_supported_publications'] != 0
            or review['counts']['new_supported_publications'] != 30
            or review['counts']['unknown_retraction_and_no_duplicate_verified'] != 1):
        raise ValueError('Expected changed-path actual-row review required')
    repairs = {}
    for name, pin in REPAIRS.items():
        raw = read_regular(args.repairs/name, 262144)
        if sha(raw) != pin:
            raise ValueError('Reviewed repair differs: ' + name)
        if name.endswith('.py'):
            compile(raw, name, 'exec')
        repairs[name] = raw
    copied = output/'source'
    copied.mkdir()
    for row in manifest['files']:
        raw = read_regular(source.joinpath(*relative(row['path']).parts))
        if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
            raise ValueError('Source changed during copy')
        write(copied.joinpath(*relative(row['path']).parts), repairs.get(row['path'], raw))
    for name in ('admitted_identity.py', 'README_IDENTITY_CORRECTION.md'):
        if (copied/name).exists():
            raise ValueError('New helper unexpectedly existed in13')
        write(copied/name, repairs[name])
    write(copied/'profiles/COMMON_BUNDLE.json', read_regular(copied/'reference-v28/COMMON_BUNDLE.json'))
    result = build(copied, copied/'profiles', output, release_id='field-runtime-v29-build-14')
    package = Path(result['package'])
    new_manifest = strict(read_regular(package/'PACKAGE_MANIFEST.json'))
    def content(rows):
        return {row['path']: row for row in rows if row['path'] not in
                ('BINDING.json', 'NATIVE_ADMISSION.json', 'PRODUCTION_ACCEPTANCE.json', 'RELOCATION_CERTIFICATE.json')
                and not row['path'].startswith('source-backups/')}
    old_rows, new_rows = content(manifest['files']), content(new_manifest['files'])
    added = sorted(set(new_rows) - set(old_rows))
    removed = sorted(set(old_rows) - set(new_rows))
    changed = sorted(name for name in set(old_rows) & set(new_rows) if old_rows[name] != new_rows[name])
    if (added != ['README_IDENTITY_CORRECTION.md', 'admitted_identity.py'] or removed
            or changed != ['README_LATE_LABELS.md', 'late_labels.py']):
        raise ValueError('Unexpected late-only package difference: ' + repr((added, removed, changed)))
    binding = strict(read_regular(package/'BINDING.json', 65536))
    expected = strict(encoded(old_binding))
    old_root, new_root = old_binding['target'], binding['target']
    if not old_root.endswith('/field-runtime-v29-build-13') or not new_root.endswith('/field-runtime-v29-build-14'):
        raise ValueError('Exact13 to14 target pair required')
    def moved(value):
        if not value.startswith(old_root + '/'):
            raise ValueError('Package reference outside original source root')
        return new_root + value[len(old_root):]
    expected['target'] = new_root
    expected['candidate_content_sha256'] = binding['candidate_content_sha256']
    for key in ('reference_code', 'raw_factory_path'):
        expected[key] = moved(expected[key])
    for row in expected['profiles'].values():
        row['path'] = moved(row['path'])
    if encoded(operational_binding(expected)) != encoded(operational_binding(binding)):
        raise ValueError('Late-only derivative changed another operational field')
    if binding['native_launch_enabled'] is not False or (package/'NATIVE_ADMISSION.json').exists():
        raise ValueError('Disabled preparation must not inherit native authorization')
    verify_tree(source, SOURCE_MANIFEST)
    verify_tree(package, result['manifest_sha256'])
    import tarfile
    archive_raw = read_regular(Path(result['archive']))
    restore_archive = output/'independent-restore'/Path(result['archive']).name
    write(restore_archive, archive_raw)
    restored = output/'independent-restore'/'package'
    expected_members = {row['path']: row for row in new_manifest['files']}
    manifest_raw = read_regular(package/'PACKAGE_MANIFEST.json')
    expected_members['PACKAGE_MANIFEST.json'] = dict(bytes=len(manifest_raw), sha256=sha(manifest_raw))
    seen, total = set(), 0
    with tarfile.open(restore_archive, 'r:gz') as archive:
        for member in archive:
            name = relative(member.name).as_posix()
            if not member.isfile() or name in seen or name not in expected_members:
                raise ValueError('Unexpected archive restore member')
            row = expected_members[name]
            total += member.size
            if member.size != row['bytes'] or member.size > 2*1024**2 or total > 16*1024**2:
                raise ValueError('Archive restore extent bound')
            with archive.extractfile(member) as stream:
                raw = stream.read(member.size+1)
            if len(raw) != member.size or sha(raw) != row['sha256']:
                raise ValueError('Independent archive member readback differs')
            write(restored.joinpath(*relative(name).parts), raw)
            seen.add(name)
    if seen != set(expected_members):
        raise ValueError('Archive restore membership differs')
    verify_tree(restored, result['manifest_sha256'])
    for name, raw in repairs.items():
        if read_regular(args.repairs/name, 262144) != raw:
            raise ValueError('Repair changed during preparation')
        write(output/'reviewed-repairs'/(name+'.backup'), raw)
        write(output/'reviewed-repairs'/(name+'.restore'), raw)
    write(output/'HOST_FOCUSED_RESULT.json', review_raw)
    write(output/'SOURCE_PACKAGE_MANIFEST.json', read_regular(source/'PACKAGE_MANIFEST.json'))
    write(output/'SOURCE_BINDING.json', old_binding_raw)
    write(output/'builder'/ 'prepare_package.py.backup', builder_raw)
    write(output/'builder'/ 'prepare_package.py.restore', builder_raw)
    receipt = dict(schema='just-peachy.late-anonymous-derivative.v1', source_package=str(source),
        source_manifest_sha256=SOURCE_MANIFEST, source_binding_sha256=SOURCE_BINDING,
        source_content_sha256=SOURCE_CONTENT, destination=result,
        changed_content_files=[dict(path=name, source_sha256=old_rows[name]['sha256'],
                                   destination_sha256=REPAIRS[name]) for name in changed],
        added_content_files=[dict(path=name, sha256=REPAIRS[name]) for name in added],
        all_other_content_bytes_unchanged=True, ordinary_local_import_closure=True,
        independent_archive_and_member_restore=True, restored_files=len(seen), restored_bytes=total,
        builder_sha256=BUILDER, builder_only_change='admitted_identity.py explicit inventory entry',
        host_focused_review_sha256=REVIEW, reviewer=args.reviewer, native_executed=False,
        native_qualified=False, production_accepted=False,
        evidence_reuse='Actual13 observations retain original identity; only anonymous late-label evidence resolution changes; no14 native execution claimed')
    write(output/'DERIVATION.json', encoded(receipt))
    return dict(result, derivation=str(output/'DERIVATION.json'), derivation_sha256=sha(encoded(receipt)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'repairs', 'review', 'builder-prior', 'output-root'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--reviewer', required=True)
    args = parser.parse_args()
    output = early(args.output_root)
    sys.dont_write_bytecode = True
    if not args.reviewer.strip() or len(args.reviewer) > 128:
        raise ValueError('Explicit bounded source reviewer required')
    try:
        print(json.dumps(prepare(args, output), sort_keys=True))
    except BaseException as error:
        (output/'FAILURE.json').write_text(json.dumps(dict(type=type(error).__name__, message=str(error)[:2048])), encoding='utf8')
        raise


if __name__ == '__main__':
    main()
