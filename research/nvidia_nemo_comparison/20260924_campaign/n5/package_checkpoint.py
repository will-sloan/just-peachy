"""Create a small explicitly PARTIAL handoff and dated status snapshot. README.md."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
START=datetime.fromisoformat('2026-09-24T14:48:19.949192+00:00')


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def save(name, value):
    (HERE/name).write_text(json.dumps(value,indent=2)+'\n',newline='\n')


def load_optional(p):
    return json.loads(p.read_text()) if p.exists() else {}


def prepare():
    now=datetime.now(timezone.utc)
    n2=load_optional(LOCAL/'n2/numerical-v2/RESULT.json')
    chain=load_optional(LOCAL/'n2/numerical-v2/CHAIN_RESULT.json')
    n3q=load_optional(LOCAL/'n3/numerical-v3/QUEUE_RESULT.json')
    n3=load_optional(LOCAL/'n3/numerical-v3/RESULT.json')
    status=dict(stage='N5', status='PARTIAL_RELEASE_PREPARATION', completed=False,
        checked_utc=now.isoformat(), elapsed_campaign_wall_seconds=(now-START).total_seconds(),
        N2=dict(status=n2.get('status'), completed=n2.get('completed'), total=n2.get('total'), chain=chain.get('status')),
        N3=dict(queue=n3q.get('status'), run_status=n3.get('status'), jobs_attempted=n3.get('completed'), plan_jobs=32,
                active=n3.get('active'),current_run='numerical-v3',
                prior_run='v2 stopped before inference: bytecode cache was incorrectly bound; preserved'),
        N4=dict(status='PREPARATION_ONLY', intended_cells=7680, executed_cells=0, accepted_profiles=0),
        source_prepared=True, arm64_wheel_elf_binaries_verified=151, arm64_native_binaries_built=6,
        arm64_native_loader='EMULATED_PASS', ARM64_FUNCTIONAL_SMOKE=False, CM5_HARDWARE_NOT_TESTED=True,
        baseline_offline_bundle='MEMBER_HASHES_VERIFIED', new_selected_backend_releases=0,
        current_turn_visible_gui_launched=False, desktop_focus_control=False, microphone_opened=False,
        no_new_capture=True, no_denoising=True, production_personal_data_modified=False,
        tests=dict(windows_release=22, linux_release=22, new_integrity_refusal=4, helper_transfer='PASS', n3_binding_check='32_JOBS_VERIFIED'),
        free_bytes={drive:shutil.disk_usage(drive+':/').free for drive in ('C','G')},
        packaging_cutoff_utc='2026-09-28T02:48:19.949192Z', deadline_utc='2026-09-28T14:48:19.949192Z',
        total_compute_seconds=None, llm_tokens=None, usage_note='Not exposed as complete campaign totals',
        schedules='UPSTREAM_OWNED_PROBES_RETAINED_UNTIL_ACTUAL_COMPLETION', automatic_N4_N5_queue=False)
    save('N5_STATUS.json',status)
    artifacts=[]
    for name in ['just-peachy-baseline-cm5-offline-v1.zip','nemo-speech-arm64-engineering-v1.tar.gz']:
        path=LOCAL/'n5/releases'/name
        artifacts.append(dict(name=name,path=str(path),bytes=path.stat().st_size,sha256=sha(path),
            status='PREPARED_NOT_SELECTED_N4_RELEASE', public_upload=False,
            rollback='External data and immutable releases retained; see UPDATE_ROLLBACK.md'))
    save('ARTIFACT_INDEX.json',dict(status='PARTIAL_CHECKPOINT',artifacts=artifacts))
    with (HERE.parent/'NOTE_COVERAGE.csv').open(encoding='utf-8-sig',newline='') as f:
        original=list(csv.DictReader(f))
    rows=[]
    for r in original:
        state={'ACTUALLY_RUN':'TESTED','IMPLEMENTED':'IMPLEMENTED','NOT_TESTED':'DEFERRED',
               'UNAVAILABLE':'DEFERRED','DEFERRED':'DEFERRED','EXPLORATORY':'EXPLORATORY'}.get(r['final_status'],'EXPLORATORY')
        rows.append(dict(item=r['item'],classification=state, evidence=r['evidence_path'],
            scope='Inherited N1 note audit; not newly run N5 or final comparative acceptance', limitation=r['limitation']))
    rows.extend([
        dict(item='Offline baseline packaging',classification='TESTED',evidence='ARTIFACT_INDEX.json',scope='All ZIP member hashes; private assets included',limitation='Target install/model execution pending'),
        dict(item='Native ARM64 alternative infrastructure',classification='TESTED',evidence='NATIVE_BUILD_RECEIPT.json; ARM64_NATIVE_AUDIT.json; EMULATED_LOADER.json',scope='Actual cross-build and emulated loader',limitation='Model/stateful WAV parity and accepted composition pending'),
        dict(item='Wired deployment helper closure',classification='TESTED',evidence='RELEASE_TEST_RESULTS.json; prototype/release_tools/tests/test_deploy.ps1',scope='Non-networked transfer reconstruction/import',limitation='No physical transfer'),
        dict(item='Full-bank ranking and noisy naming causes',classification='DEFERRED',evidence='../n4/MATRIX.json',scope='0/7680 N4 cells',limitation='No final identity/ASR gain claimed'),
        dict(item='CM5/XVF/IMU/camera/buttons/touch',classification='DEFERRED',evidence='HARDWARE_PROFILE.json',scope='Null/disabled planning only',limitation='Pi offline; pins/ABI/physical performance unknown')])
    with (HERE/'NOTE_COVERAGE_SNAPSHOT.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)


def main(a):
    if a.prepare_only:
        prepare();return
    if a.output is None or a.output.exists():
        raise ValueError('Fresh --output ZIP is required')
    if not (HERE/'GITHUB_BACKUP_RECEIPT.json').exists():
        raise ValueError('Record verified Git state before packaging')
    files=[p for p in sorted(HERE.iterdir()) if p.is_file() and p.suffix in ('.md','.json','.csv','.py','.cmd','.sh')
           and p.name!='HANDOFF_RECEIPT.json']
    if not 30<=len(files)<=60:
        raise ValueError('Expected 30–60 readable handoff files, found '+str(len(files)))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.name)
    if a.output.stat().st_size>20*1024**2:
        raise ValueError('Handoff exceeds 20MiB')
    with zipfile.ZipFile(a.output) as z:
        for p in files:
            if hashlib.sha256(z.read(p.name)).hexdigest()!=sha(p):raise ValueError('Handoff readback mismatch')
    receipt=dict(status='PARTIAL_CHECKPOINT_NOT_COMPLETED_N5',archive=str(a.output),bytes=a.output.stat().st_size,
                 sha256=sha(a.output),files=len(files),readback='PASS',model_weights=False,audio=False,voiceprints=False)
    save('HANDOFF_RECEIPT.json',receipt)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--output',type=Path)
    main(p.parse_args())
