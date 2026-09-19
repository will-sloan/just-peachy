"""Package an explicitly reviewed S6C handoff; README_S6C_PACKAGE_HANDOFF.md."""
from __future__ import annotations
import argparse, hashlib, json, os, re, uuid, zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SIM = Path(__file__).resolve().parents[1]
HANDOFFS = SIM / 'handoffs'
REPORT = SIM / 'reports/S6C/20260910T123540Z'
SCHEMA = 'jp_s6c_handoff_package.v1'
MAX_FILE = 128 * 1024**2
MAX_TOTAL = 512 * 1024**2
MAX_ZIP = 20 * 1024**2
ALLOWED = {'.md', '.csv', '.json', '.txt', '.png', '.svg', '.pdf'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def binding(path, raw):
    return dict(path=str(Path(path).resolve()), bytes=len(raw), sha256=sha(raw))


def exact_file(item):
    if type(item.get('bytes')) is not int or not 0 <= item['bytes'] <= MAX_FILE:
        raise ValueError('Invalid or oversized declared file')
    if not re.fullmatch('[0-9a-f]{64}', item.get('sha256', '')):
        raise ValueError('Explicit lowercase SHA256 required')
    path = Path(item['path'])
    if not path.is_absolute() or not path.is_file():
        raise ValueError('Existing absolute source file required: '+str(path))
    with path.open('rb') as handle:
        raw = handle.read(MAX_FILE+1)
    if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
        raise ValueError('Declared source bytes changed: '+str(path))
    return raw


def archive_name(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('Archive names must be relative POSIX paths')
    path = PurePosixPath(value)
    if path.is_absolute() or any(x in ('', '.', '..') for x in value.split('/')):
        raise ValueError('Unsafe archive path')
    for component in value.split('/'):
        if component.endswith((' ', '.')) or any(ord(c) < 32 or ord(c) == 127 or c in '<>"|?*' for c in component):
            raise ValueError('Archive component is not a portable Windows filename')
        stem = component.split('.', 1)[0].rstrip(' .').upper()
        if stem in {'CON', 'PRN', 'AUX', 'NUL'} or re.fullmatch(r'(?:COM|LPT)[1-9]', stem):
            raise ValueError('Reserved Windows device name in archive')
    if path.suffix.lower() not in ALLOWED:
        raise ValueError('Unsupported handoff type; keep raw payload local')
    return value


def admit(manifest_path):
    raw = Path(manifest_path).read_bytes()
    doc = json.loads(raw)
    if doc.get('schema') != SCHEMA or doc.get('status') != 'APPROVED_FOR_PACKAGING':
        raise ValueError('Explicit reviewed packaging manifest required')
    if doc.get('study_status') != 'COMPLETE_WITH_LIMITATIONS':
        raise ValueError('This final packer does not relabel partial work complete')
    acceptance_raw = exact_file(doc['acceptance'])
    acceptance = json.loads(acceptance_raw)
    required = ('mandatory_offline_complete', 'native_confirmation_complete',
                'paced_panel_complete', 'continuous_host_sessions_complete',
                'owned_processes_closed', 'independent_review_complete')
    if acceptance.get('status') != 'ACCEPTED_WITH_LIMITATIONS' or any(acceptance.get(k) is not True for k in required):
        raise ValueError('Final source-bound acceptance has unmet required work')
    if not isinstance(doc.get('files'), list) or not doc['files']:
        raise ValueError('Explicit nonempty file list required')
    names = {'package_manifest.json', 'checksums_sha256.txt'}
    files = []
    total = 0
    plots = 0
    for item in doc['files']:
        name = archive_name(item['archive_name'])
        folded = name.casefold()
        if folded in names or any(folded.startswith(n+'/') or n.startswith(folded+'/') for n in names):
            raise ValueError('Duplicate/reserved name or file-directory prefix collision: '+name)
        names.add(folded)
        role = item.get('role')
        if role not in ('analysis', 'table', 'plot', 'metadata', 'readme'):
            raise ValueError('Explicit artifact role required')
        if PurePosixPath(name).suffix.lower() in ('.png', '.svg', '.pdf') and role != 'plot':
            raise ValueError('Every visual must count toward the plot limit')
        plots += role == 'plot'
        data = exact_file(item)
        total += len(data)
        if total > MAX_TOTAL or plots > 6:
            raise ValueError('Uncompressed payload or six-plot budget exceeded')
        files.append((name, data))
    required_names = doc.get('required_archive_names')
    if not isinstance(required_names, list) or not required_names or any(archive_name(n).casefold() not in names for n in required_names):
        raise ValueError('Declared required deliverables missing')
    if not any(item['path'] == doc['acceptance']['path'] and item['sha256'] == doc['acceptance']['sha256'] for item in doc['files']):
        raise ValueError('Include the acceptance receipt inside the archive')
    return doc, raw, files, dict(files=len(files), plots=plots, uncompressed_bytes=total,
                                 manifest=binding(manifest_path, raw), acceptance=doc['acceptance'])


def package(manifest_path, output, check_only=False):
    doc, raw, files, admission = admit(manifest_path)
    if check_only:
        return dict(status='PACKAGING_INPUTS_VERIFIED_NO_ARCHIVE_WRITTEN', **admission)
    output = output.resolve()
    allowed_root = HANDOFFS.resolve()
    if output.parent != allowed_root or output.suffix.lower() != '.zip':
        raise ValueError('Final ZIP must be directly under the S6C handoffs directory')
    receipt_path = output.with_suffix('.zip.receipt.json')
    if output.exists() or receipt_path.exists():
        raise ValueError('Preserve existing package/receipt; choose a fresh filename')
    allowed_root.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name('.'+output.name+'.'+uuid.uuid4().hex+'.tmp')
    # Both final resolved paths are checked before the Windows rename below.
    if temporary.resolve().parent != allowed_root or output.resolve().parent != allowed_root:
        raise ValueError('Temporary/final target escaped the intended handoff directory')
    checksums = ''.join(sha(data)+'  '+name+'\n' for name, data in files)
    checksums += sha(raw)+'  PACKAGE_MANIFEST.json\n'
    with temporary.open('xb') as handle:
        with zipfile.ZipFile(handle, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in files:
                archive.writestr(name, data)
            archive.writestr('PACKAGE_MANIFEST.json', raw)
            archive.writestr('CHECKSUMS_SHA256.txt', checksums.encode('utf-8'))
    if temporary.stat().st_size > MAX_ZIP:
        raise ValueError('Archive exceeds20MiB; preserved temporary needs reviewed scope/format revision')
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise ValueError('Archive CRC verification failed')
        expected = dict(files)
        expected['PACKAGE_MANIFEST.json'] = raw
        expected['CHECKSUMS_SHA256.txt'] = checksums.encode('utf-8')
        if set(archive.namelist()) != set(expected) or len(archive.namelist()) != len(expected):
            raise ValueError('Archive member coverage differs')
        for name, data in expected.items():
            if archive.read(name) != data:
                raise ValueError('Archive content verification failed: '+name)
    os.rename(temporary, output)
    zip_raw = output.read_bytes()
    result = dict(status='VERIFIED_FINAL_HANDOFF_PACKAGE', utc=datetime.now(timezone.utc).isoformat(),
                  study_status=doc['study_status'], **admission, archive=binding(output, zip_raw),
                  target10MiB_met=len(zip_raw) <= 10*1024**2,
                  exact_archive_members=len(files)+2,
                  package_code=binding(__file__, Path(__file__).read_bytes()),
                  readme=binding(Path(__file__).with_name('README_S6C_PACKAGE_HANDOFF.md'),
                                 Path(__file__).with_name('README_S6C_PACKAGE_HANDOFF.md').read_bytes()),
                  scope='Exact manifest-only packaging and archive round-trip; scientific completion depends on the explicitly bound final acceptance review.')
    with receipt_path.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=HANDOFFS/'S6C_JOINT_CHATGPT_HANDOFF_20260910T123540Z.zip')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(package(args.manifest, args.output, args.check), indent=2))
