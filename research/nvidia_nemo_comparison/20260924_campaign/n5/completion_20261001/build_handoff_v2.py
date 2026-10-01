"""Bounded documentation-only handoff builder; see README_HANDOFF_TOOLS_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
assert psutil.Process().cpu_affinity() == [14]
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
BACKUPS = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/completion-20261001-backups')
DOCS = ('START_HERE.md', 'COMPLETION_PLAN.md', 'CHATGPT_HANDOFF.md', 'MODE_GUIDE.md',
        'OFFLINE_ACCEPTANCE.md', 'FIELD_VALIDATION.md', 'FIELD_RUN_TEMPLATE.json',
        'PATHS_AND_BACKUPS.md', 'ACCEPTANCE.json', 'DEADLINE_AUTHORITY_V1.json',
        'README_HANDOFF_TOOLS.md', 'build_handoff.py',
        'PI_RAM_MODEL_REPORT_V1.md', 'OPERATOR_SHORTCUTS_AUDIO_REQUIREMENTS_V1.md',
        'README_HANDOFF_TOOLS_V2.md', 'build_handoff_v2.py')
MIB = 1024 ** 2


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--summary-version', type=int, required=True)
    parser.add_argument('--owner-receipt', required=True)
    args = parser.parse_args()
    owner_path = Path(args.owner_receipt)
    with owner_path.open('x', encoding='utf-8') as stream:
        json.dump(dict(pid=psutil.Process().pid, create_time=psutil.Process().create_time(),
            affinity=psutil.Process().cpu_affinity(), purpose='documentation-handoff'), stream)
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', args.label):
        raise ValueError('Use a new lowercase version label; never overwrite a closed pack')
    if not 1 <= args.summary_version <= 9999:
        raise ValueError('Explicit valid summary version required')
    for drive, floor in [('C:/', 50*1024**3), ('G:/', 75*1024**3)]:
        if shutil.disk_usage(drive).free < floor + 4*MIB:
            raise RuntimeError('Host free-space floor would be violated')
    sources = {name: HERE/name for name in DOCS}
    reports = HERE.parent/'extension_20260928/pi_native_20260928'
    summary_name = f'CHECK_SUMMARY_V{args.summary_version}.json'
    sources['evidence/'+summary_name] = reports/summary_name
    sources['evidence/D1_METHOD_APPLICATION_FINDINGS_V1.md'] = reports/'D1_METHOD_APPLICATION_FINDINGS_V1.md'
    payloads = {}
    for name, path in sources.items():
        if path.is_symlink() or path.stat().st_size > 256*1024:
            raise ValueError('Symlink or oversized documentation input: '+name)
        raw = path.read_bytes()
        if len(raw) > 256*1024:
            raise ValueError('Input changed size while reading')
        if path.suffix == '.json':
            json.loads(raw)
        payloads[name] = raw
    if sum(map(len, payloads.values())) > 2*MIB:
        raise ValueError('Documentation input budget exceeded')
    manifest = dict(schema='just-peachy.documentation-handoff.v1', label=args.label,
        created_utc=datetime.now(timezone.utc).isoformat(),
        status=json.loads(payloads['ACCEPTANCE.json'])['overall'],
        deadline_utc=json.loads(payloads['DEADLINE_AUTHORITY_V1.json'])['hard_deadline_utc'],
        summary=summary_name, deployable_runtime=False, private_payloads_included=False,
        files={name:dict(bytes=len(raw), sha256=digest(raw)) for name,raw in payloads.items()})
    manifest_raw = (json.dumps(manifest, indent=2)+'\n').encode()
    payloads['BUNDLE_MANIFEST.json'] = manifest_raw
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in payloads.items():
            archive.writestr(name, raw)
    archive_raw = buf.getvalue()
    if len(archive_raw) > 2*MIB:
        raise ValueError('Compact package budget exceeded')
    existing = sum(q.stat().st_size for q in BACKUPS.rglob('*') if q.is_file()) if BACKUPS.exists() else 0
    if existing + len(archive_raw) + len(manifest_raw) + 65536 > 4*MIB:
        raise ValueError('All retained handoff outputs would exceed4MiB; no cleanup/retry')
    output = BACKUPS/args.label
    output.mkdir(parents=True, exist_ok=False)
    archive_path = output/f'NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_{args.label}.zip'
    with archive_path.open('xb') as stream:
        stream.write(archive_raw)
    with (output/'BUNDLE_MANIFEST.json').open('xb') as stream:
        stream.write(manifest_raw)
    assert archive_path.read_bytes() == archive_raw
    with zipfile.ZipFile(archive_path) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist())) == len(payloads)
        assert set(archive.namelist()) == set(payloads)
        for name, raw in payloads.items():
            assert not name.startswith('/') and '..' not in Path(name).parts
            assert archive.read(name) == raw
    receipt = dict(status='EXACT_DOCUMENTATION_BACKUP_VERIFIED', label=args.label,
        archive=str(archive_path), bytes=len(archive_raw), sha256=digest(archive_raw),
        member_count=len(payloads), cpu_affinity=psutil.Process().cpu_affinity(),
        delivery_status=manifest['status'], runtime_or_offline_acceptance=False)
    with (output/'BACKUP_RECEIPT.json').open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
