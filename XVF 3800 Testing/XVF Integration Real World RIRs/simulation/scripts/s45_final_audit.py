"""Post-supervisor, read-only conservation/resource audit. README_S45_FINAL_AUDIT.md."""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

from s45_common import BANK, HARDWARE, H2, LIMITS, PAYLOAD, REPO, REPORT, RUN_ID, SIM, START_UTC

EXPECTED = {
    'RIR_manifest': '468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546',
    'master_workbook': 'af393d71060ee25fd2f1d4398dfc1fb52daaa7cb20d182b284a348fc974d72f2',
    'historical_S4_handoff': '3897cf30dc88ecb6e35cd3b20e4a9c869e8cf8f5ddeb20ef4368d026d9981a1c',
}
OUTPUT = REPORT / 'FINAL_RESOURCE_AND_RESTORATION.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def digest(path, expected=None):
    path = Path(path).resolve()
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'File changed while hashing: ' + str(path))
    require(expected is None or h.hexdigest() == expected, 'SHA256 mismatch: ' + str(path))
    return {'path': str(path), 'sha256': h.hexdigest(), 'bytes': after.st_size}


class Evidence:
    def __init__(self):
        self.bindings = {}
        self.absent = []

    def bind(self, path, expected=None):
        row = digest(path, expected)
        prior = self.bindings.setdefault(row['path'], row)
        require(prior == row, 'Evidence changed during audit: ' + row['path'])
        return row

    def load(self, path, expected=None, optional=False):
        path = Path(path)
        if optional and not path.exists():
            self.absent.append(str(path))
            return None
        bound = self.bind(path, expected)
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        require(digest(path) == bound, 'JSON changed during read: ' + str(path))
        return value

    def ref(self, binding):
        row = self.bind(binding['path'], binding['sha256'])
        require('bytes' not in binding or row['bytes'] == binding['bytes'], 'Binding byte-count mismatch')
        return row


def run_bytes(argv, cwd=None):
    return subprocess.run(argv, cwd=cwd, capture_output=True, check=True, timeout=60,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout


def powershell_json(script):
    # EncodedCommand carries constant/query data without shell interpolation.
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    raw = run_bytes(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded])
    return json.loads(raw.decode('utf-8-sig'))


def process_snapshot(recorded_pids):
    ids = ','.join(str(int(x)) for x in sorted(set(recorded_pids)))
    script = r"""
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$recorded=@(__PIDS__)
$rows=@(Get-CimInstance Win32_Process | Where-Object {
    ($_.ProcessId -in $recorded) -or
    ($_.Name -match '^(pythonw?|powershell|pwsh)\.exe$' -and
      ($_.CommandLine -match 's45_(execute(?:_v2)?|campaign|hardware|h2_run)\.py' -or
       ($_.CommandLine -match '20260909T031300Z' -and
        $_.CommandLine -match '(app\.edge_speech_pipeline|Run-S4-Telemetry\.ps1)')))
} | Select-Object ProcessId,ParentProcessId,Name,CommandLine,@{n='CreationDate';e={if($_.CreationDate){$_.CreationDate.ToUniversalTime().ToString('o')}else{$null}}})
foreach($row in $rows) {
  if(-not $row.CommandLine) {
    $services=@(); $serviceError=$null
    try {$services=@(Get-CimInstance Win32_Service -Filter ('ProcessId='+[int]$row.ProcessId) -ErrorAction Stop | Select-Object Name,DisplayName,State,ProcessId,PathName,StartName)} catch {$serviceError=$_.Exception.Message}
    $row | Add-Member -NotePropertyName AssociatedServices -NotePropertyValue $services
    $row | Add-Member -NotePropertyName ServiceQueryError -NotePropertyValue $serviceError
  }
}
@{queried_utc=[DateTime]::UtcNow.ToString('o'); processes=$rows; query_succeeded=$true; system_root=$env:SystemRoot} | ConvertTo-Json -Depth 7 -Compress
""".replace('__PIDS__', ids)
    snapshot = powershell_json(script)
    snapshot['scope'] = 'Live process metadata for S4.5 owners/native telemetry plus historical recorded PIDs; no process was signalled or opened for control.'
    return snapshot


def process_is_related(row):
    command = row.get('CommandLine') or ''
    return bool(re.search(r's45_(?:execute(?:_v2)?|campaign|hardware|h2_run)\.py', command, re.I) or
                (RUN_ID in command and re.search(r'app\.edge_speech_pipeline|Run-S4-Telemetry\.ps1', command, re.I)))


def service_pid_reuse_basis(row, jobs, system_root):
    """Strict metadata proof for an inaccessible command line of a reused PID."""
    def timestamp(value):
        require(isinstance(value, str), 'Missing PID-reuse timestamp')
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(parsed.tzinfo is not None and parsed.utcoffset() is not None, 'PID-reuse timestamp lacks timezone')
        return parsed

    require(not process_is_related(row) and not row.get('CommandLine'), 'PID-reuse fallback requires missing, unrelated command line')
    require(str(row.get('Name', '')).casefold() == 'svchost.exe', 'Missing-command process is not svchost.exe')
    pid = row.get('ProcessId')
    require(isinstance(pid, int) and not isinstance(pid, bool) and pid > 0, 'Invalid current PID')
    created = timestamp(row.get('CreationDate'))
    historical = [job for job in jobs if job.get('owned_process_pid') == pid]
    require(historical, 'No bound completed model receipt for reused PID')
    bases = []
    for job in historical:
        require(job.get('status') == 'COMPLETE' and job.get('exit_code') == 0 and not job.get('error'),
                'Historical PID receipt is not complete/exit0')
        exited, completed = timestamp(job.get('model_exited_utc')), timestamp(job.get('completed_utc'))
        require(exited <= completed < created, 'Current service creation is not strictly after historical exit/completion')
        bases.append({k: job[k] for k in ('case_id', 'stream', 'owned_process_pid', 'model_exited_utc', 'completed_utc')})
    require(isinstance(system_root, str) and re.fullmatch(r'[A-Za-z]:\\[^\r\n"]+', system_root), 'SystemRoot identity unavailable')
    expected = system_root.rstrip('\\') + r'\System32\svchost.exe'
    services = row.get('AssociatedServices')
    require(not row.get('ServiceQueryError') and isinstance(services, list) and len(services) == 1,
            'Missing or ambiguous associated service for reused PID')
    service = services[0]
    require(service.get('ProcessId') == pid and service.get('State') == 'Running' and
            isinstance(service.get('Name'), str) and bool(service['Name'].strip()), 'Associated running service/PID identity mismatch')
    path = service.get('PathName')
    match = re.match(r'^(?:"([^"]+)"|([^\s"]+))(?:\s|$)', path.strip()) if isinstance(path, str) else None
    executable = (match.group(1) or match.group(2)) if match else None
    require(executable is not None and executable.casefold() == expected.casefold(), 'Associated service executable is not exact SystemRoot System32 svchost.exe')
    return {'status': 'CONFIRMED_REUSED_SERVICE_PID', 'current_process': {k: row[k] for k in ('ProcessId', 'Name', 'CreationDate')},
            'associated_service': service, 'expected_system_executable': expected, 'historical_completed_model_receipts': bases,
            'basis': 'Current svchost creation strictly follows every bound COMPLETE/exit0 model receipt for this PID; one associated Running service has the same PID and exact SystemRoot\\System32\\svchost.exe executable. No process control or command-line inference.'}


def closure_errors(markers, snapshot, ledger, jobs):
    errors = []
    snapshot['confirmed_reused_service_pids'] = []
    if snapshot.get('query_succeeded') is not True:
        errors.append('Live process query unavailable')
    for row in snapshot.get('processes', []):
        if process_is_related(row):
            errors.append('Live S4.5 owner/native child PID ' + str(row['ProcessId']))
        elif not row.get('CommandLine'):
            try:
                snapshot['confirmed_reused_service_pids'].append(service_pid_reuse_basis(row, jobs, snapshot.get('system_root')))
            except (ValueError, KeyError, TypeError) as error:
                errors.append('Recorded PID exists but command identity is unavailable: ' + str(row['ProcessId']) + '; ' + str(error))
    post = markers.get('supervisor_postpackage_receipt.json')
    if not post or post.get('status') != 'SUPERVISOR_CLOSED' or not post.get('ended_utc'):
        errors.append('Final supervisor closure receipt missing or not closed')
    for name in ('owned_process.json', 'supervisor_process.json'):
        row = markers.get(name)
        if not row or row.get('pid') is not None or not row.get('closed_utc'):
            errors.append('Missing/uncleared owner marker: ' + name)
    if markers.get('UNRESOLVED_SUPERVISOR_CHILD.json') is not None:
        errors.append('Unresolved supervisor-child marker retained')
    for name in ('keep_awake.json', 'supervisor_keep_awake.json'):
        row = markers.get(name)
        if not row or row.get('active') is not False or row.get('prior_state_restored') is not True or not row.get('released_utc'):
            errors.append('Keep-awake release is not recorded: ' + name)
    if any(row.get('status') not in ('PASS', 'FAIL') for row in ledger.get('passes', [])):
        errors.append('Physical ledger contains an unresolved/nonterminal attempt')
    for row in jobs:
        if row.get('status') in (None, 'STARTED', 'RUNNING', 'STARTING'):
            errors.append('Unresolved model receipt: ' + str(row.get('case_id')) + '/' + str(row.get('stream')))
    return errors


def verify_restoration(folder, evidence):
    """Pure JSON equivalent of the existing exact-readback/recovery receipt gate."""
    folder = Path(folder)
    original_path = folder / 'restoration.json'
    original = evidence.load(original_path)
    effective, effective_path = original, original_path
    if original.get('status') == 'FAIL':
        effective_path = folder / 'restoration_recovery.json'
        effective = evidence.load(effective_path)
        ref = effective['original_failure_binding']
        require(Path(ref['path']).resolve() == original_path.resolve(), 'Restoration recovery points elsewhere')
        evidence.ref(ref)
        require(effective.get('original_failure') == original, 'Recovery original-failure content mismatch')
    require(effective.get('status') == 'PASS', 'Restoration did not pass: ' + folder.name)
    for key in ('exact_recorded_configuration_match', 'hardware_lease_released', 'audio_handles_closed', 'telemetry_process_closed', 'packed_input_disabled'):
        require(effective.get(key) is True, 'Restoration field not true: ' + folder.name + '/' + key)
    initial = evidence.load(folder / 'initial_state.json')
    for key in ('settings', 'identity', 'observe_only'):
        require(key in initial and effective.get('readback', {}).get(key) == initial[key], 'Exact initial readback mismatch: ' + folder.name + '/' + key)
    identity = effective['readback']['identity']
    require(identity.get('I2S_INPUT_PACKED') == [0], 'Packed input not disabled')
    require('usb_bits' in initial and identity.get('USB_BIT_DEPTH') == initial['usb_bits'], 'USB width not restored')
    return {'batch': folder.name, 'restoration': evidence.bind(effective_path), 'initial_state': evidence.bind(folder / 'initial_state.json'),
            'original_restoration': evidence.bind(original_path), 'recovery_used': effective_path != original_path,
            'status': 'PASS', 'exact_initial_settings_identity_observe_only_match': True,
            'recorded_release_fields': {k: effective[k] for k in ('hardware_lease_released', 'audio_handles_closed', 'telemetry_process_closed', 'packed_input_disabled')},
            'recorded_scope': effective.get('scope'), 'independent_device_readback_performed_by_this_audit': False}


def conservation(evidence):
    checkpoint = evidence.load(REPORT / 'PRESERVATION_CHECKPOINT.json')
    require(checkpoint.get('status') == 'PASS', 'Preservation checkpoint not PASS')
    result = {}
    for name, expected in EXPECTED.items():
        require(checkpoint[name]['sha256'] == expected, 'Unexpected preservation authority: ' + name)
        result[name] = evidence.ref(checkpoint[name])
    manifest = evidence.load(result['RIR_manifest']['path'], EXPECTED['RIR_manifest'])
    expected_wavs = {str(Path(r['output']['path']).resolve()): r['output'] for r in manifest['records']}
    preserved = {str(Path(r['path']).resolve()): r for r in checkpoint['RIR_WAV_bindings']}
    require(len(expected_wavs) == len(preserved) == checkpoint['RIR_WAV_count'] == 121, 'Require all121 preserved RIR records')
    require(set(expected_wavs) == set(preserved), 'RIR checkpoint/library WAV path set differs')
    wavs = []
    for name in sorted(expected_wavs):
        require(expected_wavs[name]['sha256'] == preserved[name]['sha256'], 'RIR checkpoint/library hash differs')
        wavs.append(evidence.ref(expected_wavs[name]))
    result.update(status='PASS', RIR_WAV_count=len(wavs), RIR_WAV_bindings=wavs,
                  scope='Actual current bytes of all121 indexed RIR WAVs, manifest, V9 original and prior S4 ZIP; no extraction, decoding or regeneration.')
    return result


def current_input_bindings(evidence):
    pre = evidence.load(REPORT / 'PRE_CAPTURE_VERIFICATION.json')
    require(pre.get('status') == 'PASS', 'Pre-capture verification was not PASS')
    require(Path(pre['bank']['path']).resolve() == (BANK / 'SCENE_MANIFEST.json').resolve(), 'Pre-capture bank path differs')
    bank = evidence.load(pre['bank']['path'], pre['bank']['sha256'])
    require(bank.get('validation', {}).get('status') == 'PASS' and len(bank['scenes']) == 240, 'Frozen canonical bank is not validated240')
    for key in ('sources_binding', 'noise_binding', 'legacy_development_sources_binding'):
        evidence.ref(bank[key])
    for key in ('plan', 'dry_plan'):
        evidence.ref(pre[key])
    for item in pre.get('owner_code', []):
        evidence.ref(item)
    code = bank.get('code')
    require(isinstance(code, dict) and 'path' in code and 'sha256' in code, 'Bank code binding missing')
    evidence.ref(code)
    ref = evidence.load(BANK / 'REFERENCE_SCENE_MANIFEST.json', optional=True)
    return bank, ref


def acceptance(evidence, bank, reference_bank, ledger):
    result = {}
    policy = evidence.load(REPORT / 'OUTPUT_LEVEL_POLICY.json')
    require(policy.get('frozen') is True, 'Output/recipe policy is not frozen')
    for reference, manifest in ((False, bank), (True, reference_bank)):
        name = 'REFERENCE_CAPTURES.json' if reference else 'ACCEPTED_CAPTURES.json'
        obj = evidence.load(REPORT / name, optional=reference)
        expected_scenes = {s['case_id']: s for s in manifest['scenes']} if manifest else {}
        if obj is None:
            result['optional_references'] = {'prepared': len(expected_scenes), 'accepted': None, 'status': 'NO_CAPTURE_MANIFEST'}
            continue
        manifest_ref = obj['reference_scene_manifest' if reference else 'scene_manifest']
        manifest_path = BANK / ('REFERENCE_SCENE_MANIFEST.json' if reference else 'SCENE_MANIFEST.json')
        require(Path(manifest_ref['path']).resolve() == manifest_path.resolve(), 'Acceptance references a different bank path')
        evidence.ref(manifest_ref)
        require(obj.get('reserve_task_scored') is False, 'Acceptance manifest reserve-task flag is not false')
        require(obj.get('excluded_from_240') is reference, 'Reference/canonical count categories mixed')
        require(obj.get('in_progress_count', 0) == 0, 'Acceptance still contains in-progress captures')
        rows = obj['accepted']
        require(obj['accepted_count'] == len(rows) == len({x['case_id'] for x in rows}), 'Acceptance count/duplicate mismatch')
        require(obj.get('pending_count') == len(expected_scenes) - len(rows), 'Pending capture denominator mismatch')
        for row in rows:
            cid = row['case_id']; require(cid in expected_scenes, 'Unknown accepted scene')
            case = evidence.load(row['case_result']['path'], row['case_result']['sha256'])
            require(case.get('case_id') == cid, 'Accepted case identity mismatch')
            folder = Path(row['folder']).resolve()
            require(Path(row['case_result']['path']).resolve() == folder / 'case_result.json', 'Accepted receipt folder mismatch')
            require(folder.parent.name == case.get('batch'), 'Accepted batch/folder identity mismatch')
            contract = evidence.load(folder.parent / 'batch_contract.json')
            require(case.get('recipe') == contract.get('recipe') == policy['hardware_recipe'], 'Accepted recipe differs from frozen policy/batch contract')
            require(case.get('reserve_task_scored') is False, 'Accepted case reports reserve task scoring or omits its prohibition')
            require(contract.get('scene_manifest_sha256') == manifest_ref['sha256'], 'Accepted batch contract uses a different scene manifest')
            require(contract.get('code_key') == case.get('code_key') == row.get('code_key') and isinstance(case.get('code_key'), str), 'Accepted batch/case/selection code key differs')
            require(contract.get('final_recipe_capture') is True, 'Batch contract is not a final recipe capture')
            require(case.get('split') == row.get('split') == expected_scenes[cid]['split'], 'Accepted case split mismatch')
            require(row.get('task_scoring_allowed') is (not reference and expected_scenes[cid]['split'] == 'development'), 'Accepted task-permission mismatch')
            require(case.get('input_scene_sha256') == row['input_scene_sha256'] == expected_scenes[cid]['canonical_audio']['sha256'], 'Accepted input hash mismatch')
            require(all(case.get(k) == 'PASS' for k in ('status', 'audio_integrity_status', 'telemetry_status')), 'Accepted case was not PASS')
            require(case.get('payload', {}).get('status') == 'PASS' and case.get('final_recipe_capture') is True, 'Accepted capture recipe/payload not qualified')
            charges = [x for x in ledger['passes'] if x['case_id'] == cid and x['batch'] == case['batch'] and x['status'] == 'PASS']
            require(len(charges) == 1, 'Accepted case lacks exactly one matching PASS ledger charge')
        for row in obj.get('failed_attempts', []):
            evidence.ref(row['case_result'])
        result['optional_references' if reference else 'canonical'] = {'intended_or_prepared': len(expected_scenes), 'accepted': len(rows),
            'development_accepted': sum(x.get('split') == 'development' for x in rows), 'reserve_accepted': sum(x.get('split') == 'reserve' for x in rows),
            'pending': obj.get('pending_count'), 'failed_attempts': len(obj.get('failed_attempts', [])), 'excluded_from_240': reference}
    return result


def physical_summary(ledger):
    rows = ledger['passes']
    require(all(isinstance(x.get('charged_playback_s'), (int, float)) and math.isfinite(x['charged_playback_s']) and x['charged_playback_s'] > 0 for x in rows), 'Invalid playback charge')
    require(len({(r['batch'], r['case_id']) for r in rows}) == len(rows), 'Duplicate physical charge in same batch/case')
    attempts = Counter(r['case_id'] for r in rows)
    require(not attempts or max(attempts.values()) <= LIMITS['attempts_per_scene'], 'Physical per-scene attempt budget exceeded')
    active = sum(r['charged_playback_s'] for r in rows)
    require(len(rows) <= LIMITS['physical_passes'] and active <= LIMITS['active_playback_s'], 'Physical global budget exceeded')
    groups = {}
    for kind in ('canonical', 'optional_reference', 'diagnostic'):
        chosen = [r for r in rows if ('optional_reference' if r['case_id'].startswith('S45_REF_') else 'canonical' if r['case_id'].startswith('S45_') else 'diagnostic') == kind]
        groups[kind] = {'passes': len(chosen), 'statuses': dict(Counter(r['status'] for r in chosen)), 'charged_playback_s': sum(r['charged_playback_s'] for r in chosen)}
    return {'passes': len(rows), 'charged_active_playback_s': active, 'statuses': dict(Counter(r['status'] for r in rows)), 'groups': groups,
            'captured_native_48000Hz_frames_recorded': sum(r.get('captured_frames', 0) for r in rows),
            'passes_missing_captured_frame_count': sum('captured_frames' not in r for r in rows),
            'scope': 'Charges include diagnostics, failures and references. Charged scene seconds are not measured device-on wall time; missing frame counts are not zero-length captures.'}


def native_completion(evidence, row, summary):
    """Verify current native journal/event bytes and the frozen runner's recorded completion proof."""
    completion = row['completion_evidence']
    require(completion.get('native_summary') is True and completion.get('unique_completion_event') is True, 'Native recorded completion flags missing')
    samples = completion.get('exact_full_pcm16_samples')
    require(isinstance(samples, int) and not isinstance(samples, bool) and samples > 0 and samples == row['adapter']['samples'], 'Native complete-input journal sample count differs')
    session = Path(row['session_dir']).resolve()
    for key, filename in (('session_summary_binding', 'session_summary.json'), ('events_binding', 'events.jsonl')):
        require(Path(row[key]['path']).resolve() == session / filename, 'Native completion artifact points outside its session')
    journal = evidence.ref(completion['journal'])
    journal_path = Path(journal['path']).resolve()
    require(journal_path.parent == session and journal_path.suffix == '.pcm16', 'Native PCM16 journal path differs')
    require({p.resolve() for p in session.glob('*.pcm16')} == {journal_path}, 'Expected exactly one native PCM16 journal')
    require(journal['bytes'] == samples * 2, 'Native PCM16 journal byte/sample count differs')
    telemetry = summary['telemetry']
    counters = {}
    for key in ('audio_frames_dropped', 'portaudio_input_overflows', 'raw_capture_reserve_failures'):
        require(key in telemetry and telemetry[key] == 0, 'Missing or nonzero native drop counter: ' + key)
        counters[key] = telemetry[key]
    events_binding = evidence.ref(row['events_binding'])
    events_path = Path(events_binding['path'])
    events = [json.loads(line) for line in events_path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    require(digest(events_path) == events_binding, 'Native event journal changed during completion audit')
    counts = Counter(e['event_type'] for e in events)
    require(counts['session_completed'] == 1 and counts['failure'] == counts['session_stopped'] == 0, 'Native event journal lacks unique failure-free completion')
    return {'case_id': row['case_id'], 'stream': row['stream'], 'recorded_native_summary': True,
            'recorded_exact_full_pcm16_samples': samples, 'current_PCM16_journal_bytes': journal['bytes'],
            'native_event_count': len(events), 'session_completed_events': counts['session_completed'], 'recorded_zero_drop_counters': counters,
            'scope': 'Current journal hash and byte count plus native events/telemetry verified. The frozen runner recorded exact adapter-to-PCM16 value equality; this audit does not decode/reconvert the source adapter.'}


def h2_summary(evidence, paths, jobs):
    sentinel = evidence.load(REPORT / 'SENTINEL_PLAN.json')
    scenes = {s['case_id']: s for s in evidence.load(BANK / 'SCENE_MANIFEST.json')['scenes']}
    require(len(sentinel['scene_ids']) == len(set(sentinel['scene_ids'])) == 24, 'Expected24 unique frozen sentinels')
    require(all(scenes[c]['split'] == 'development' and scenes[c]['task_scoring_allowed'] is True for c in sentinel['scene_ids']), 'Sentinel plan contains reserve or disabled task input')
    dry_plan = evidence.load(REPORT / 'DRY_CONTROL_PLAN.json', optional=True)
    allowed = {(cid, stream) for cid in sentinel['scene_ids'] for stream in ('O0', 'O1')}
    allowed_dry = set(dry_plan['control_ids']) if dry_plan else set()
    contract = evidence.load(REPORT / 'h2/execution_contract.json', optional=True)
    if jobs:
        require(contract is not None, 'Jobs exist without execution contract')
    if contract:
        for key, path in (('scene_manifest', BANK / 'SCENE_MANIFEST.json'), ('sentinel_plan', REPORT / 'SENTINEL_PLAN.json'),
                          ('dry_plan', REPORT / 'DRY_CONTROL_PLAN.json'), ('output_policy', REPORT / 'OUTPUT_LEVEL_POLICY.json')):
            require(Path(contract[key]['path']).resolve() == path.resolve(), 'H2 contract path mismatch: ' + key)
            evidence.ref(contract[key])
        for row in contract['code'] + contract['baseline']['source_identities']:
            evidence.ref(row)
        evidence.ref(contract['baseline']['durability_fix'])
        require(contract.get('reserve_jobs') == 0, 'H2 contract reserve job count is not zero')
    result = {}
    for kind in ('outputs', 'dry'):
        chosen = [(p, r) for p, r in zip(paths, jobs) if ('dry' if p.is_relative_to(REPORT / 'h2_dry') else 'outputs') == kind]
        seen = set()
        completions = []
        for path, row in chosen:
            key = (row['case_id'], row.get('stream'))
            require(key not in seen, 'Duplicate H2 case/stream'); seen.add(key)
            require((key in allowed) if kind == 'outputs' else (row['case_id'] in allowed_dry), 'Unexpected H2 job or reserve score')
            identity = row['identity']
            require(identity['contract_sha256'] == stable_hash(contract) and row['job_key'] == stable_hash(identity), 'H2 job/contract identity mismatch')
            require(identity['id'] == row['case_id'] and identity['stream'] == row['stream'] and identity['kind'] == row['kind'] == kind, 'H2 job identity field mismatch')
            require(identity['raw_audio_sha256'] == row['raw_audio']['sha256'] and identity['input_provenance'] == row['input_provenance'], 'H2 raw-input provenance mismatch')
            require(row.get('labels_or_transcripts_sent_to_model') is False, 'Truth was not excluded from model inputs')
            if kind == 'outputs':
                evidence.ref(row['input_provenance']['case_result'])
            else:
                require(row['stream'] == 'DRY', 'Unexpected dry stream identifier')
            if row['status'] == 'QUARANTINED':
                require(kind == 'outputs' and row.get('model_invocations') == 0, 'Quarantine contains a model invocation')
                evidence.ref(row['metrics_binding'])
            if row['status'] == 'COMPLETE':
                require(row.get('exit_code') == 0 and not row.get('error'), 'Completed H2 receipt has failure/unknown exit')
                summary = evidence.load(row['session_summary_binding']['path'], row['session_summary_binding']['sha256'])
                require(summary.get('state') == 'COMPLETED' and 'reconstruction_provenance' not in summary, 'S4.5 summary is not native complete')
                completions.append(native_completion(evidence, row, summary))
                for name in ('metrics_binding', 'events_binding'):
                    evidence.ref(row[name])
            if 'model_wall_s' in row:
                require(isinstance(row['model_wall_s'], (int, float)) and math.isfinite(row['model_wall_s']) and row['model_wall_s'] >= 0, 'Invalid model wall time')
        expected = 48 if kind == 'outputs' else len(allowed_dry)
        require(len(chosen) <= (48 if kind == 'outputs' else 24), 'Model job budget exceeded')
        result[kind] = {'intended_or_planned': expected if (kind == 'outputs' or dry_plan) else None,
            'receipt_count': len(chosen), 'statuses': dict(Counter(r['status'] for _, r in chosen)),
            'pending_without_receipt': expected - len(chosen) if (kind == 'outputs' or dry_plan) else None,
            'nonquarantined_attempt_receipts': sum(r['status'] != 'QUARANTINED' for _, r in chosen),
            'observed_model_child_PID_receipts': sum(isinstance(r.get('owned_process_pid'), int) for _, r in chosen),
            'model_wall_s_recorded': sum(r.get('model_wall_s', 0) for _, r in chosen),
            'native_completion_audits': completions,
            'nonquarantined_receipts_missing_model_wall_s': sum(r['status'] != 'QUARANTINED' and 'model_wall_s' not in r for _, r in chosen)}
    result['model_time_scope'] = 'Sum of recorded model child/process wall time, including native asset checks/finalization; absent times remain counted as missing, not zero-work evidence. No model weights were rehashed.'
    result['total_model_wall_s_recorded'] = sum(result[k]['model_wall_s_recorded'] for k in ('outputs', 'dry'))
    return result


def validate_storage_observations(snapshot):
    """Join provider identities without assuming their numeric identifiers agree."""
    def identity(value, field):
        text = value.get(field)
        require(isinstance(text, str) and bool(text.strip()), 'Missing storage identity: ' + field)
        return text.strip()

    rows = snapshot.get('volumes', [])
    require(len(rows) == 2 and {x['drive'] for x in rows} == {'C:', 'G:'}, 'Incomplete or duplicate disk mapping')
    physical = snapshot.get('physical_disks', [])
    supplement = snapshot.get('get_disk_records', [])
    require(isinstance(physical, list) and isinstance(supplement, list), 'Storage provider rows unavailable')
    volumes = {}
    for row in rows:
        drive = row['drive']
        require(row['free_bytes'] >= LIMITS[drive[0] + '_free_gib'] * 2**30, 'Free-space floor violated: ' + drive)
        require(row['mapping'], 'SSD mapping/health not established: ' + drive)
        mappings = []
        for mapping in row['mapping']:
            require(mapping.get('win32_status') == 'OK', 'Win32 disk status not OK: ' + drive)
            serial, model = identity(mapping, 'serial_number'), identity(mapping, 'model')
            matches = [p for p in physical
                       if isinstance(p.get('serial_number'), str) and isinstance(p.get('friendly_name'), str)
                       and p['serial_number'].strip() == serial and p['friendly_name'].strip() == model]
            require(len(matches) == 1, 'Unique exact serial/model Get-PhysicalDisk match not established: ' + drive)
            health = matches[0]
            require(health.get('health_status') == 'Healthy' and health.get('operational_status') == ['OK'],
                    'Get-PhysicalDisk health/OK not established: ' + drive)
            disks = [d for d in supplement if d.get('number') == mapping['index']]
            require(len(disks) <= 1, 'Ambiguous Get-Disk index supplement: ' + drive)
            if disks:
                disk = disks[0]
                require(identity(disk, 'serial_number') == serial and identity(disk, 'friendly_name') == model,
                        'Get-Disk supplement identity mismatch: ' + drive)
                require(disk.get('health_status') == 'Healthy' and disk.get('operational_status') == ['Online'],
                        'Get-Disk supplement health/Online not established: ' + drive)
            mappings.append({**mapping, 'health_status': health['health_status'],
                             'operational_status': health['operational_status'],
                             'friendly_name': health['friendly_name'], 'bus_type': health.get('bus_type'),
                             'health_provider': 'Get-PhysicalDisk unique exact trimmed serial+model',
                             'matched_physical_disk': health, 'get_disk_supplement': disks[0] if disks else None,
                             'get_disk_supplement_status': 'PRESENT_IDENTITY_HEALTH_VERIFIED' if disks else 'NOT_PRESENT_OPTIONAL'})
        volumes[drive] = {**row, 'mapping': mappings}
    mapping = volumes['G:']['mapping']
    require(len(mapping) == 1 and mapping[0]['index'] == 3 and 'KINGSTON SNVS2000G' in mapping[0]['model'],
            'G no longer maps to verified Kingston PhysicalDrive3')
    return {**snapshot, 'volumes': list(volumes.values()),
            'provider_join_status': 'PASS',
            'missing_get_disk_is_health_failure': False,
            'scope': 'Current Windows storage-provider observations. Logical/partition/Win32 drive associations establish volume identity; unique exact trimmed serial+model Get-PhysicalDisk Healthy/OK establishes provider health. Matching-index Get-Disk is an optional identity/Healthy/Online supplement. Missing Get-Disk alone is not a health failure or evidence of a dynamic-disk cause. No destructive disk test or comprehensive SMART diagnosis.'}


def ssd_and_space():
    script = r"""
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$physical=@(Get-PhysicalDisk | ForEach-Object {
  @{device_id=[string]$_.DeviceId; friendly_name=[string]$_.FriendlyName; serial_number=[string]$_.SerialNumber; health_status=[string]$_.HealthStatus; operational_status=@($_.OperationalStatus | ForEach-Object {[string]$_}); bus_type=[string]$_.BusType; size_bytes=[long]$_.Size}
})
$getDiskError=$null
$diskRecords=@(try {Get-Disk -ErrorAction Stop | ForEach-Object {
  @{number=[int]$_.Number; friendly_name=[string]$_.FriendlyName; serial_number=[string]$_.SerialNumber; health_status=[string]$_.HealthStatus; operational_status=@($_.OperationalStatus | ForEach-Object {[string]$_}); bus_type=[string]$_.BusType; size_bytes=[long]$_.Size}
}} catch {$getDiskError=$_.Exception.Message})
$rows=@(foreach($letter in @('C:','G:')) {
  $logical=Get-CimInstance Win32_LogicalDisk -Filter ("DeviceID='"+$letter+"'")
  if(-not $logical){throw 'Missing requested volume'}
  $parts=@(Get-CimAssociatedInstance -InputObject $logical -Association Win32_LogicalDiskToPartition)
  $mapped=@(foreach($part in $parts) {foreach($disk in @(Get-CimAssociatedInstance -InputObject $part -Association Win32_DiskDriveToDiskPartition)) {
    @{partition=$part.DeviceID; physical_drive=$disk.DeviceID; index=[int]$disk.Index; model=[string]$disk.Model; serial_number=[string]$disk.SerialNumber; win32_status=$disk.Status; size_bytes=[long]$disk.Size}
  }})
  @{drive=$letter; free_bytes=[long]$logical.FreeSpace; size_bytes=[long]$logical.Size; file_system=$logical.FileSystem; mapping=$mapped}
})
@{queried_utc=[DateTime]::UtcNow.ToString('o');volumes=$rows;physical_disks=$physical;get_disk_records=$diskRecords;get_disk_query_error=$getDiskError;method='Win32_LogicalDiskToPartition -> Win32_DiskDriveToDiskPartition; unique exact trimmed serial+model Get-PhysicalDisk health join; optional Get-Disk index supplement'} | ConvertTo-Json -Depth 8 -Compress
"""
    return validate_storage_observations(powershell_json(script))


def storage_bytes():
    roots = [PAYLOAD, REPORT, BANK, SIM / ('scene_bank/s45_v1_' + RUN_ID)]
    roots += sorted((SIM / 'staging').glob('s45_*'))
    files = sorted({* (SIM / 'scripts').glob('s45_*.py'), * (SIM / 'scripts').glob('test_s45_*.py'), * (SIM / 'scripts').glob('README_S45*.md'), * (SIM / 'handoffs').glob('*S4_5*' + RUN_ID + '*')})
    seen, rows, rejected = set(), [], []
    for root in roots + files:
        total = count = 0
        if not root.exists():
            continue
        pending = [root]
        while pending:
            path = pending.pop(); info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
                rejected.append(str(path)); continue
            key = str(path.resolve()).casefold()
            if key in seen:
                continue
            seen.add(key)
            if path.is_dir():
                pending.extend(path.iterdir())
            elif path.is_file():
                count += 1; total += info.st_size
        rows.append({'root': str(root), 'logical_bytes': total, 'files': count})
    require(not rejected, 'Reparse points prevent exact bounded new-file accounting: ' + repr(rejected))
    all_bytes = sum(x['logical_bytes'] for x in rows)
    require(all_bytes <= LIMITS['new_storage_gib'] * 2**30, 'Expanded new-run storage budget exceeded')
    common = sum(x['logical_bytes'] for x in rows if Path(x['root']) in (PAYLOAD, REPORT, BANK))
    return {'bounded_attributed_logical_bytes': all_bytes, 'common_PAYLOAD_REPORT_activeBANK_scope_bytes': common,
            'by_root': rows, 'scope': 'Only known S4.5 payload/report/v1+v2 banks, S4.5 staging, scripts/tests/READMEs and matching handoff files. Logical file sizes, not allocated disk blocks or a whole-drive before/after delta. Excludes this not-yet-written audit receipt and existing source datasets/model assets.'}


def git_and_h2_sources(evidence):
    fix_path = SIM / 'staging/s45_h2_fix/v3/FIX_RECEIPT.json'
    fix = evidence.load(fix_path)
    changed = fix['changed_sources']
    require(len(changed) == 2 and {Path(x['after']['path']).name for x in changed} == {'cli.py', 'runtime.py'}, 'Unexpected H2 authorized source set')
    current_sources = [evidence.ref(x['after']) for x in changed]
    unchanged = [evidence.ref(x) for x in fix['unchanged_baseline_sources']]
    def git(*args):
        return run_bytes(['git', '--no-optional-locks', *args], REPO)
    head = git('rev-parse', 'HEAD').decode().strip()
    branch = git('rev-parse', '--abbrev-ref', 'HEAD').decode().strip()
    status = git('status', '--short', '--untracked-files=normal').decode('utf-8', errors='replace')
    paths = [str(Path(x['path']).relative_to(REPO)).replace('\\', '/') for x in current_sources]
    diffs = []
    for relative in paths:
        raw = git('diff', '--no-ext-diff', '--no-textconv', '--binary', 'HEAD', '--', relative)
        diffs.append({'path': relative, 'git_diff_HEAD_worktree_sha256': hashlib.sha256(raw).hexdigest(), 'diff_bytes': len(raw)})
    tracked = git('diff', '--name-only', 'HEAD', '--').decode('utf-8').splitlines()
    return {'HEAD': head, 'branch': branch, 'status_short': status, 'tracked_changed_paths_vs_HEAD': tracked,
            'HEAD_equals_active_fix_start': head == fix['git_head'], 'two_authorized_diff_hashes': diffs,
            'H2_current_sources_match_active_v3_fix': current_sources, 'unchanged_baseline_source_count': len(unchanged),
            'scope': 'Read-only Git commands with optional index locks disabled. No commit, stage, checkout or clean. Diff hashes describe current HEAD-to-worktree bytes; active-fix source hashes independently establish allowed H2 changes.'}


def audit():
    evidence = Evidence()
    result = {'schema': 'jp_s45_final_resource_restoration_audit_v1', 'run_id': RUN_ID, 'audit_started_utc': utc(),
              'start_utc': START_UTC.isoformat(), 'status': 'BLOCKED_OR_FAILED', 'errors': [],
              'scope': 'Post-supervisor receipt/resource/conservation audit. PASS is not a campaign accuracy verdict or proof all intended tasks completed.',
              'no_hardware_or_model_execution': True, 'reserve_task_results_read': False}
    try:
        marker_names = ['supervisor_postpackage_receipt.json', 'supervisor_receipt.json', 'owned_process.json', 'supervisor_process.json',
                        'UNRESOLVED_SUPERVISOR_CHILD.json', 'keep_awake.json', 'supervisor_keep_awake.json']
        markers = {n: evidence.load(REPORT / n, optional=True) for n in marker_names}
        ledger = evidence.load(REPORT / 'physical_ledger.json')
        paths = sorted((REPORT / 'h2').glob('*/*/run_receipt.json')) + sorted((REPORT / 'h2_dry').glob('*/run_receipt.json'))
        jobs = [evidence.load(p) for p in paths]
        acquired_paths = sorted(HARDWARE.glob('*/owner_acquired.json'))
        acquired = [evidence.load(p) for p in acquired_paths]
        pids = [r['pid'] for r in list(markers.values()) + acquired if isinstance(r, dict) and isinstance(r.get('pid'), int)]
        pids += [r['owned_process_pid'] for r in jobs if isinstance(r.get('owned_process_pid'), int)]
        snapshot = process_snapshot(pids)
        result['owner_evidence'] = {'markers': markers, 'live_process_snapshot': snapshot}
        result['errors'].extend(closure_errors(markers, snapshot, ledger, jobs))
        result['keep_awake'] = {'campaign_recorded': markers['keep_awake.json'], 'supervisor_recorded': markers['supervisor_keep_awake.json'],
            'independent_OS_keep_awake_state_verified': False,
            'scope': 'Receipts record SetThreadExecutionState restoration intent and flags. The frozen code does not retain the cleanup call return value. This audit does not query or change thread power state; process exit and receipt claims are separate evidence.'}
        if result['errors']:
            return result
        result['conservation'] = conservation(evidence)
        bank, references = current_input_bindings(evidence)
        result['capture_counts'] = acceptance(evidence, bank, references, ledger)
        result['physical'] = physical_summary(ledger)
        required_batches = {r['batch'] for r in ledger['passes']} | {p.parent.name for p in acquired_paths}
        required_batches |= {p.parent.name for p in HARDWARE.glob('*/initial_state.json')}
        for path in HARDWARE.glob('*/restoration.json'):
            if evidence.load(path).get('status') != 'NOT_NEEDED':
                required_batches.add(path.parent.name)
        result['restorations'] = [verify_restoration(HARDWARE / name, evidence) for name in sorted(required_batches)]
        result['hardware_batch_summaries'] = []
        for p in sorted(HARDWARE.glob('*/hardware_summary.json')):
            row = evidence.load(p)
            result['hardware_batch_summaries'].append({'binding': evidence.bind(p), **{k: row.get(k) for k in ('batch', 'status', 'error', 'elapsed_s', 'restoration_status')}})
        result['H2'] = h2_summary(evidence, paths, jobs)
        for p in sorted((REPORT / 'supervisor').glob('*.json')):
            row = evidence.load(p)
            if row.get('status') == 'STARTED':
                result['errors'].append('Unclosed supervisor invocation receipt: ' + p.name)
            if row.get('latest_invocation'):
                evidence.ref(row['latest_invocation'])
        for name in ('campaign_receipt.json', 'reference_campaign_receipt.json', 'CAPTURE_ANALYSIS.json', 'REFERENCE_CAPTURE_ANALYSIS.json',
                     'summary_metrics.json', 'EXECUTION_INCIDENTS.json', 'INCIDENT_REVIEW.json', 'H2_RELEASE.json', 'preflight.json'):
            evidence.load(REPORT / name, optional=True)
        result['git_and_H2_source_conservation'] = git_and_h2_sources(evidence)
        result['ssd'] = ssd_and_space()
        result['new_storage'] = storage_bytes()
        # Close the timing window again after the hashes; no receipt-free owner may start mid-audit.
        result['final_live_process_snapshot'] = process_snapshot(pids)
        result['errors'].extend(closure_errors(markers, result['final_live_process_snapshot'], ledger, jobs))
        for binding in list(evidence.bindings.values()):
            require(digest(binding['path']) == binding, 'Consumed evidence changed before audit finished')
        result['status'] = 'PASS' if not result['errors'] else 'BLOCKED_OR_FAILED'
    except (Exception, KeyboardInterrupt) as exc:
        result['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        result['audit_finished_utc'] = utc()
        result['elapsed_wall_s_since_run_start'] = (dt.datetime.now(dt.timezone.utc) - START_UTC).total_seconds()
        result['consumed_bindings'] = list(evidence.bindings.values())
        result['absent_optional_or_closure_receipts'] = evidence.absent
        result['audit_code'] = digest(Path(__file__))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='Run the same final read-only checks, printing JSON without creating a receipt.')
    args = parser.parse_args()
    if OUTPUT.exists() and not args.check_only:
        parser.error('Final audit receipt already exists; preserve it. Use --check-only for a later observation.')
    result = audit()
    if not args.check_only:
        # Exclusive creation prevents replacement of any prior evidence, including failed audits.
        with OUTPUT.open('x', encoding='utf-8') as out:
            json.dump(result, out, indent=2, ensure_ascii=False, allow_nan=False)
            out.write('\n')
    print(json.dumps({'status': result['status'], 'errors': result['errors'], 'output': None if args.check_only else str(OUTPUT)}, indent=2))
    if args.check_only:
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
