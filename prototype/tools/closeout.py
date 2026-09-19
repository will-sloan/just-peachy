"""Read-only acceptance audit and compact handoff assembly. See tools/README.md."""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def audit(acceptance):
    """Audit every completed epoch, rather than trusting a top-level pass flag."""
    soak = read(acceptance / 'soak_v1/SOAK_RESULT.json')
    rows = []
    for folder in sorted((acceptance / 'soak_v1/private_data/sessions').iterdir()):
        if not folder.is_dir():
            continue
        final = read(folder / 'session_finalization_v3.json')
        closure = read(folder / 's6d_consumer_closure.json')
        summary = read(folder / 'session_summary.json')
        telemetry = summary['telemetry']
        lanes = {k: v for k, v in closure['queues'].items()
                 if isinstance(v, dict) and 'accepted' in v}
        checks = {
            'finalized': final['state'] == 'COMPLETED',
            'no_live_lanes': not final['live_lanes_at_finalization'],
            'closed_handles': final['event_and_transcript_handles_closed'],
            'no_finalization_error': final['finalization_error'] is None,
            'consumer_drained': closure['full_event_consumer_drained'],
            'all_queues_drained': all(v['accepted'] == v['completed'] and
                v['depth'] == 0 and not v['error'] and not v['thread_alive'] for v in lanes.values()),
            'no_capture_loss': all(telemetry.get(k, 0) == 0 for k in
                ('audio_frames_dropped', 'portaudio_input_overflows', 'raw_capture_reserve_failures')),
        }
        rows.append({'session': folder.name, 'checks': checks, 'pass': all(checks.values()),
            'source_samples': final['source_samples'],
            'identity_samples': final['identity_samples'],
            'event_queue_max_age_sec': closure['queues']['event_consumer']['max_age_sec'],
            'queues': {k: {n: v[n] for n in ('accepted', 'completed', 'max_depth', 'max_age_sec')}
                       for k, v in lanes.items()},
            'evidence': {n: digest(folder / n) for n in
                         ('session_finalization_v3.json', 's6d_consumer_closure.json', 'session_summary.json')}})
    samples = soak['resource_samples']
    baseline = samples[0]['rss_mib']
    rss = [s['rss_mib'] for s in samples if s['rss_mib'] is not None]
    lags = [s['asr_lag_sec'] for s in samples if s['asr_lag_sec'] is not None]
    observations = soak['output_default_observations']
    role_ids = [{role: value.get('endpoint_id') for role, value in
                 row.get('value', {}).get('default_render', {}).items()}
                for row in observations]
    complete_roles = all(set(row) == {'console', 'multimedia', 'communications'}
                         and all(row.values()) for row in role_ids)
    result = {
        'schema': 'proto1.closeout-audit.v1', 'utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Saved-file desktop checks; no microphone, human enrollment or CM5 execution',
        'soak_result_sha256': digest(acceptance / 'soak_v1/SOAK_RESULT.json'),
        'soak_pass': soak['pass'], 'source_unchanged_during_soak': soak['source_unchanged'],
        'epochs': rows, 'epoch_count': len(rows),
        'source_frames': soak['source_frames'], 'sum_epoch_source_frames': sum(r['source_samples'] for r in rows),
        'private_test_audio_or_vectors_included': False,
        'output_defaults': {
            'observation_count': len(observations), 'all_three_roles_observed': complete_roles,
            'unchanged_within_soak': bool(role_ids) and complete_roles and all(row == role_ids[0] for row in role_ids),
            'first': role_ids[0] if role_ids else None,
            'last': role_ids[-1] if role_ids else None,
            'causal_claim': 'None; compared read-only observations, not a study of Windows endpoint changes.'},
        'resources': {'elapsed_sec': soak['elapsed_sec'], 'source_sec': soak['source_duration_sec'],
            'sample_count': len(samples), 'rss_first_mib': baseline, 'rss_peak_sampled_mib': max(rss),
            'rss_last_mib': rss[-1], 'threads_peak_sampled': max(s['threads'] for s in samples),
            'asr_lag_peak_sampled_sec': max(lags) if lags else None,
            'model_cache': soak['final']['model_cache'],
            'limitations': 'Once-per-minute process samples, not instantaneous peak or UI word latency. Some early parallel checks. Not CM5 capacity or thermal qualification.'},
    }
    result['pass'] = (soak['pass'] and soak['source_unchanged'] and len(rows) == 21
                      and all(r['pass'] for r in rows)
                      and result['sum_epoch_source_frames'] == result['source_frames'])
    write(ROOT / 'evidence/CLOSEOUT_AUDIT.json', result)
    print(json.dumps({'audit_pass': result['pass'], 'epochs': len(rows), 'resources': result['resources']}))
    if not result['pass']:
        raise RuntimeError('Per-epoch closeout audit failed; inspect evidence/CLOSEOUT_AUDIT.json')


def final_bindings(release, workbook, acceptance):
    migration = read(ROOT / 'evidence/SOURCE_MIGRATION.json')
    historical = Path(migration['source_root'])
    historical_checks = []
    vendor_differences = []
    for row in migration['source_files']:
        old = historical / row['relative_path']
        historical_checks.append(digest(old) == row['sha256'])
        migrated = ROOT / 'vendor' / row['relative_path']
        if digest(migrated) != row['sha256']:
            vendor_differences.append(row['relative_path'])
    with zipfile.ZipFile(release) as z:
        manifest = json.loads(z.read('RELEASE_MANIFEST.json'))
        release_checks = {row['path']: digest(ROOT / row['path']) == row['sha256']
                          and hashlib.sha256(z.read(row['path'])).hexdigest() == row['sha256']
                          for row in manifest['files']}
    expected_workbook = 'f11c4786f3487fe783a9197b48bd3bf77f6732f006ac6401e5d345ac1fddd64d'
    data = Path.home() / 'JustPeachy/data'
    people = list((data / 'people').iterdir()) if (data / 'people').exists() else []
    record = {'schema': 'proto1.final-bindings.v1', 'utc': datetime.now(timezone.utc).isoformat(),
        'git_head': subprocess.check_output(['git', '-C', str(ROOT.parent), 'rev-parse', 'HEAD'], text=True).strip(),
        'initial_git_head': migration['git_head'], 'historical_files_checked': len(historical_checks),
        'all_historical_source_hashes_unchanged': all(historical_checks),
        'migrated_vendor_differences': vendor_differences,
        'workbook': {'path': str(workbook), 'sha256': digest(workbook), 'unchanged': digest(workbook) == expected_workbook},
        'release': {'path': str(release), 'sha256': digest(release), 'files_checked': len(release_checks),
                    'all_payloads_match_current_source': all(release_checks.values()),
                    'mismatches': [k for k, v in release_checks.items() if not v]},
        'default_personal_store': {'path': str(data), 'people_entries': len(people),
                                   'runtime_lock_present': (data / 'runtime.lock').exists()},
        'storage': {str(p): {'free_gib': shutil.disk_usage(p).free / 1024**3,
                             'total_gib': shutil.disk_usage(p).total / 1024**3}
                    for p in (ROOT.anchor, acceptance.anchor)},
        'scope': 'Read-only source/release/storage audit. No hardware access, training, RIR regeneration or deletion.'}
    record['pass'] = (all(historical_checks) and record['workbook']['unchanged']
        and all(release_checks.values()) and record['git_head'] == record['initial_git_head']
        and not people and not (data / 'runtime.lock').exists())
    write(ROOT / 'evidence/FINAL_SOURCE_REVIEW.json', record)
    print(json.dumps(record))
    if not record['pass']:
        raise RuntimeError('Final binding audit failed')


def package(output, acceptance, start_here):
    """Only explicit allowlisted files enter the analysis ZIP; never recurse data."""
    output.mkdir(parents=True, exist_ok=False)
    files = {
        'START_HERE.md': start_here,
        'IMPLEMENTATION_RESULTS.md': ROOT / 'evidence/PROTO1_IMPLEMENTATION_RESULTS.md',
        'WORKBOOK_UPDATE.md': ROOT / 'evidence/WORKBOOK_UPDATE.md',
    }
    for name in ('START_PROTOTYPE.md', 'MODE_GUIDE.md', 'README.md'):
        files['guides/' + name] = ROOT / name
    for name in ('ENROLLMENT_GUIDE.md', 'LIVE_USER_CHECKLIST.md', 'LIVE_AUDIO.md',
                 'UI_ITERATION.md', 'PI_DEPLOYMENT_WORKFLOW.md', 'HARDWARE_PENDING.json'):
        files['guides/' + name] = ROOT / 'docs' / name
    evidence = {
        'C105_REGRESSION.json': 'tests/evidence/C105_REGRESSION.json',
        'NATIVE_PEOPLE.json': 'tests/evidence/native_people_summary.json',
        'UI_CHECKS.json': 'tests/evidence/UI_CHECK_SUMMARY.json',
        'CONTROLLER_VIEWS.json': 'tests/evidence/CONTROLLER_VIEWS_CHECK.json',
        'UNIT_CHECKS.json': 'tests/evidence/FINAL_UNIT_CHECKS.json',
        'ENROLLMENT_CLEANUP.json': 'tests/evidence/enrollment_cleanup_summary.json',
        'CLOSEOUT_AUDIT.json': 'evidence/CLOSEOUT_AUDIT.json',
        'LIVE_READINESS_REVIEW.md': 'evidence/LIVE_READINESS_REVIEW.md',
        'LIVE_ADAPTER.json': 'evidence/live_adapter/LIVE_ADAPTER_RESULT.json',
        'AUDIO_DEFAULT_NOTE.md': 'evidence/live_adapter/AUDIO_DEFAULT_NOTE.md',
        'READONLY_DEVICE.json': 'evidence/live_adapter/readonly_device_inventory.json',
        'RELEASE_TOOL_CHECKS.json': 'release_tools/evidence/RELEASE_TEST_RESULTS.json',
        'RC_RELEASE.json': 'release_tools/evidence/actual_release/ACTUAL_RELEASE_RESULTS.json',
        'FINAL_RELEASE.json': 'release_tools/evidence/final_release/FINAL_RELEASE_RESULTS.json',
        'FINAL_RUNTIME_RELEASE.json': 'release_tools/evidence/final_release/FINAL_RUNTIME_RESULTS.json',
        'RC_TO_FINAL.patch': 'release_tools/evidence/final_release/RC_TO_FINAL.patch',
        'ARM64_WHEELS.json': 'release_tools/evidence/ARM64_WHEELS.json',
        'XMOS_ARCHITECTURE.json': 'release_tools/evidence/XMOS_ARCHITECTURE.json',
        'FINAL_SOURCE_REVIEW.json': 'evidence/FINAL_SOURCE_REVIEW.json',
    }
    for target, relative in evidence.items():
        files['evidence/' + target] = ROOT / relative
    files['evidence/SOAK_RESULT.json'] = acceptance / 'soak_v1/SOAK_RESULT.json'
    files['evidence/NATIVE_UI_RESULT.json'] = acceptance.parent / 'tests/ui_native_v1/NATIVE_UI_RESULT.json'
    for name in ('controller.py', 'pipeline.py', 'live_audio.py', 'people.py', 'buffers.py', 'paths.py', 'enrollment_quality.py'):
        files['review_source/' + name] = ROOT / 'app' / name
    for name in ('test_lifecycle.py', 'test_file_tap.py', 'test_buffers_quality.py',
                 'test_enrollment_cleanup.py', 'test_live_stop_ownership.py', 'README.md'):
        files['review_tests/' + name] = ROOT / 'tests' / name
    for target, source in files.items():
        destination = output / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    shots = read(ROOT / 'docs/SCREENSHOT_MANIFEST.json')
    for row in shots['images']:
        source = Path(row['path'])
        if digest(source) != row['sha256']:
            raise ValueError('Screenshot hash changed: ' + str(source))
        target = 'screens/' + row['id'] + '.png'
        (output / 'screens').mkdir(exist_ok=True)
        shutil.copyfile(source, output / target)
        row['archive_path'] = target
    write(output / 'manifests/SCREENSHOTS.json', shots)
    write(output / 'manifests/CONFIG_AND_ASSETS.json', {
        str(p.relative_to(ROOT)): read(p) for p in sorted((ROOT / 'config').glob('*.json'))})
    source_files = [p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                    and p.suffix in ('.py', '.json', '.md', '.ps1', '.cmd', '.sh', '.lock', '.in')
                    and p.relative_to(ROOT).parts[0] not in ('evidence', 'tests')
                    and 'evidence' not in p.relative_to(ROOT).parts]
    write(output / 'manifests/SOURCE_FILES.json', {
        'root': str(ROOT), 'files': {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(source_files)}})
    migration = read(ROOT / 'evidence/SOURCE_MIGRATION.json')
    seed = Path(migration['source_root']) / 'edge_speech_pipeline/runtime.py'
    current = ROOT / 'vendor/edge_speech_pipeline/runtime.py'
    patch = ''.join(difflib.unified_diff(seed.read_text(encoding='utf-8').splitlines(True),
        current.read_text(encoding='utf-8').splitlines(True), fromfile='S7/runtime.py', tofile='PROTO1/runtime.py'))
    (output / 'review_source/S7_RUNTIME_ADAPTATION.patch').write_text(patch, encoding='utf-8')
    write(output / 'manifests/SOURCE_MIGRATION.json', migration)
    write(output / 'manifests/RECIPE_PARENT_BINDINGS.json', read(ROOT / 'evidence/RECIPE_PARENT_BINDINGS.json'))
    panel = read(acceptance / 'panel_v1/PANEL_RESULT.json')
    write(output / 'evidence/PANEL_SUMMARY.json', {
        'scope': panel['scope'], 'pass': panel['pass'], 'source_unchanged': panel['source_unchanged'],
        'limitation': 'Development epoch: some on-disk code changed while this process held prior imports. Final-source C105 and frozen RC soak are separate evidence.',
        'full_result_path': str(acceptance / 'panel_v1/PANEL_RESULT.json'),
        'full_result_sha256': digest(acceptance / 'panel_v1/PANEL_RESULT.json'),
        'jobs': [{k: row[k] for k in ('scene', 'tap', 'recipe', 'mode', 'pass', 'elapsed_sec',
            'source_frames', 'delivered_frames', 'writer_delay_injected_sec', 'writer_counts')}
            for row in panel['jobs']]})
    paths = sorted(p for p in output.rglob('*') if p.is_file())
    if len(paths) + 1 > 60:
        raise ValueError('Handoff exceeds 60 files')
    forbidden = {'.wav', '.flac', '.mp3', '.npy', '.npz', '.onnx', '.docx', '.dll', '.exe', '.whl', '.key', '.pem'}
    if any(p.suffix.lower() in forbidden for p in paths):
        raise ValueError('Disallowed private/binary file type in handoff')
    write(output / 'MANIFEST.json', {'created_utc': datetime.now(timezone.utc).isoformat(),
        'allowlist_only': True, 'private_audio_or_vectors_included': False,
        'files': {p.relative_to(output).as_posix(): {'sha256': digest(p), 'bytes': p.stat().st_size} for p in paths}})
    archive = output.with_suffix('.zip')
    if archive.exists():
        raise FileExistsError(archive)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(output.rglob('*')):
            if p.is_file():
                z.write(p, p.relative_to(output).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
    if archive.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('Handoff exceeds 20 MiB')
    print(json.dumps({'archive': str(archive), 'sha256': digest(archive),
                      'bytes': archive.stat().st_size, 'files': len(paths) + 1}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('audit', 'final-bindings', 'package'))
    p.add_argument('--acceptance', type=Path, required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--start-here', type=Path)
    p.add_argument('--release', type=Path)
    p.add_argument('--workbook', type=Path)
    a = p.parse_args()
    if a.command == 'audit':
        audit(a.acceptance)
    elif a.command == 'final-bindings':
        if a.release is None or a.workbook is None:
            p.error('final-bindings requires --release and --workbook')
        final_bindings(a.release, a.workbook, a.acceptance)
    else:
        if a.output is None or a.start_here is None:
            p.error('package requires --output and --start-here')
        package(a.output, a.acceptance, a.start_here)
