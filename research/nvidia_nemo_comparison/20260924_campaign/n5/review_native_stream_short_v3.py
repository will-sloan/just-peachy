"""Audit closed Nemotron CPU retest; README_NATIVE_STREAM_SHORT_REVIEW_V3.md."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import wave
import hashlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'n4'))
from common import bind, freeze, load, verify
from metric_process import pin, exact_process
from native_stream_review_v1 import review, require
from native_stream_cpu_config_v2 import cpu_argv, check_cpu_help
from review_baseline_asr_cpu_v5 import windows_binding


def inspect_protocol(path, frames):
    require(path.stat().st_size < 16 * 1024**2, 'Oversized protocol')
    rows = [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
    require(rows and rows[0]['kind'] == 'start' and rows[0]['frames'] == frames, 'Wrong input protocol')
    closed = [{k: r[k] for k in ('case', 'sent_frames', 'events', 'finals', 'stream_closed')}
              for r in rows if r['kind'] == 'case_closed']
    last = {k: rows[-1][k] for k in ('kind', 'case', 'sent_frames') if k in rows[-1]}
    finals = [r['hypothesis'] for r in rows if r['kind'] == 'event'
              and r['case'] == 'saved_source' and r['is_final']]
    return rows, dict(jsonl_rows=len(rows), closed_cases=closed, last_event=last), finals


def run(folder, output):
    pin()
    require(not output.exists(), 'Fresh audit destination required')
    a, host, native = [load(folder / n) for n in ('ADMISSION.json', 'RESULT.json', 'linux/RESULT.json')]
    require(a['scope'] == 'EMULATED_NATIVE_ASR_SHORT_CORTEX_A76_V3', 'Wrong scope')
    require(a['qemu_cpu'] == 'cortex-a76' and a['per_model_seconds'] == 1500 and a['frames'] == 256000, 'Limits changed')
    for b in a['code'] + [a[k] for k in ('precheck', 'census', 'prior_admission',
            'baseline_cpu_audit', 'audio', 'binary', 'build_result', 'short_source', 'full_source_audit', 'accepted_n3')] + [m['asset'] for m in a['models']]:
        verify(b)
    for k in ('admission', 'stdout', 'stderr', 'linux_result'):
        verify(host[k])
    inputs = load(windows_binding(native['inputs']))
    require(windows_binding(inputs['admission']) == folder / 'ADMISSION.json', 'Admission join differs')
    require(inputs['qemu_cpu'] == 'cortex-a76' and inputs['linux_cpu'] == [0], 'CPU scope differs')
    old_folder = Path(a['prior_admission']['path']).parent
    old_inputs = load(old_folder / 'linux/INPUTS.json')
    for k in ('binary', 'qemu', 'runtime_manifest', 'models'):
        require(inputs[k] == old_inputs[k], 'Pinned native input changed: ' + k)
    source = load(a['short_source']['path'])
    require(source['source'] == load(a['prior_admission']['path'])['audio'] and source['output'] == a['audio'], 'Source lineage differs')
    for b in (source['source'], source['output']): verify(b)
    require((source['start_sample'],source['end_sample'],source['sample_rate']) == (0,256000,16000), 'Wrong source interval')
    with wave.open(source['source']['path'],'rb') as original, wave.open(source['output']['path'],'rb') as short:
        require((short.getnchannels(),short.getsampwidth(),short.getframerate(),short.getnframes()) == (1,2,16000,256000), 'Wrong saved PCM format')
        pcm=short.readframes(256000)
        require(pcm == original.readframes(256000) and hashlib.sha256(pcm).hexdigest() == source['pcm_sha256'], 'Short source is not the exact original prefix')
    require(windows_binding(inputs['audio']) == Path(a['audio']['path']), 'Linux audio differs')
    require(load(a['full_source_audit']['path'])['passed_models'] == 0, 'Full-source failure record changed')
    require(host['admission'] == bind(folder/'ADMISSION.json') and host['linux_result'] == bind(folder/'linux/RESULT.json'), 'Host terminal bindings differ')
    owners = [host['owner'], host['child_owner'], {k: a['supervisor'][k] for k in ('pid', 'create_time')}]
    require(all(exact_process(o) is None for o in owners), 'An exact Windows owner remains active')
    help_cmd = load(folder / 'linux/cpu_help.json')
    check_cpu_help(help_cmd, windows_binding(help_cmd['stdout']).read_text(encoding='utf-8'),
                   windows_binding(help_cmd['stderr']).read_text(encoding='utf-8'))
    require(help_cmd['argv'] == [inputs['qemu']['path'], '-cpu', 'help'], 'Help command changed')
    results = native['results']
    require(1 <= len(results) <= 2 and [r['variant'] for r in results] == ['A2', 'A3'][:len(results)], 'Model sequence differs')
    previous = load(old_folder / 'linux/A2.json')
    summaries = []
    linux_owners = [dict(pid=inputs['owner_pid'], start_ticks=inputs['owner_start_ticks']), help_cmd['owner']]
    for r in results:
        variant = r['variant']; cmd = load(folder / 'linux' / (variant + '.json'))
        require(cmd == r['command'] and not cmd['remaining_group_members'], 'Command join/closure differs')
        original = list(previous['argv'])
        original[-2] = next(m['asset']['path'] for m in inputs['models'] if m['variant'] == variant)
        original[-1] = inputs['audio']['path']
        require(cmd['argv'] == original, 'Model command differs beyond declared model/short-source selection')
        stdout = windows_binding(cmd['stdout']); windows_binding(cmd['stderr'])
        rows, counts, finals = inspect_protocol(stdout, a['frames'])
        passed = r['error'] is None
        if passed:
            require(cmd['returncode'] == 0 and cmd['cancelled'] is None, 'Unsuccessful process claimed pass')
            require(review(stdout, a['frames']) == r['review'], 'Strict conformance review differs')
            require(any(f['text'].strip() for f in finals), 'No nonempty speech result')
        else:
            require(r['review'] is None, 'Failed model received success credit')
            if cmd['cancelled'] == 'model_timeout':
                require(cmd['timed_out'] and cmd['returncode'] in (-15, -9)
                        and 1500 <= cmd['elapsed_seconds'] < 1520, 'Timeout contract differs')
            elif cmd['cancelled'] is not None:
                require(cmd['cancelled'] in ('host_cancelled', 'disk_reserve', 'allocation_cap'), 'Unknown cancellation')
        if passed:
            require(0 < cmd['elapsed_seconds'] < 1500 and not cmd['timed_out'], 'Model exceeded declared limit')
        diagnostics=[]
        for case in ('saved_source','saved_source_repeat','saved_source_forced'):
            chosen=[x for x in rows if x['kind']=='event' and x['case']==case and x['is_final']]
            words=[w for x in chosen for w in x['hypothesis']['words']]
            if passed: require(any(x['hypothesis']['text'].strip() for x in chosen) and words, 'Missing final speech/word evidence')
            diagnostics.append(dict(case=case,final_word_objects=len(words),source_duration_ms=a['frames']/16,
                min_raw_start_ms=min((w['start_ms'] for w in words),default=None),
                max_raw_end_ms=max((w['end_ms'] for w in words),default=None),
                raw_words_outside_source=sum(not (0<=w['start_ms']<=w['end_ms']<=a['frames']/16) for w in words)))
        summaries.append(dict(variant=variant, passed=passed, error=r['error'], cancelled=cmd['cancelled'],
            elapsed_seconds=cmd['elapsed_seconds'], **counts, strict_review=r['review'],
            raw_final_word_diagnostics=diagnostics,
            raw_final_words_contained_in_source=all(x['raw_words_outside_source']==0 for x in diagnostics),
            word_timing_accuracy_against_truth_verified=False,
            scope='Unchanged six-case native protocol only; raw offset containment is a separate diagnostic'))
        linux_owners.append(cmd['owner'])
    passed = sum(r['passed'] for r in summaries)
    require((native['required_models'], native['attempted_models'], native['passed_models'], native['unattempted_models'])
            == (2, len(results), passed, 2-len(results)), 'Coverage counts differ')
    require((native['status'] == 'PASS_EMULATED_NATIVE_ASR_COMPONENTS_ONLY') == (passed == 2), 'Terminal acceptance differs')
    require((host['error'] is None) == (passed == 2), 'Host outcome differs')
    live = load(folder / 'LIVE_VERIFICATION.json')['linux']
    program = '''import os,pathlib,json,sys,hashlib
os.sched_setaffinity(0,{0});os.nice(10)
owners,old_boot,bindings=json.loads(sys.argv[1]);boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
verified=[]
for b in bindings:
 p=pathlib.Path(b['path']);d=p.read_bytes();assert len(d)==b['bytes'] and hashlib.sha256(d).hexdigest()==b['sha256'];verified.append(b)
manifest=json.loads(pathlib.Path(bindings[1]['path']).read_text());root=pathlib.Path(bindings[1]['path']).parent
for r in manifest['files']:
 p=root/r['path']
 if 'sha256' in r:assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
 if 'symlink' in r:assert p.is_symlink() and str(p.readlink())==r['symlink']
rows=[]
for o in owners:
 p=pathlib.Path('/proc')/str(o['pid'])/'stat';s=p.read_text().rsplit(')',1)[1].split() if p.exists() else None;members=[]
 for f in pathlib.Path('/proc').glob('[0-9]*/stat'):
  try:
   v=f.read_text().rsplit(')',1)[1].split()
   if int(v[2])==o['pid']:members.append(int(f.parent.name))
  except FileNotFoundError:pass
 rows.append(dict(owner=o,exact_owner_exists=bool(boot==old_boot and s and int(s[19])==o['start_ticks']),same_boot_group_members=members if boot==old_boot else []))
print(json.dumps(dict(boot_id=boot,same_boot=boot==old_boot,rows=rows,verified_bindings=verified,runtime_members_verified=len(manifest['files']))))
'''
    q = subprocess.run(['wsl.exe', '-d', 'Ubuntu', '--', 'python3', '-c', program,
        json.dumps([linux_owners, live['boot_id'], [inputs['qemu'], inputs['runtime_manifest']]])],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30,
        stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    require(not q.stderr.strip(), 'Unexpected Linux audit error')
    closure = json.loads(q.stdout)
    require(all(not x['exact_owner_exists'] and not x['same_boot_group_members'] for x in closure['rows']), 'Linux owner/group still active')
    output.mkdir(); freeze(output / 'LINUX_CLOSURE.json', closure)
    result = dict(status='VERIFIED_SHORT_EMULATED_NATIVE_PROTOCOL_ONLY' if passed == 2 else 'VERIFIED_CLOSED_PARTIAL_SHORT_ATTEMPT',
        utc=datetime.now(timezone.utc).isoformat(), models=summaries, required_models=2, passed_models=passed,
        unattempted_models=2-len(results), code_bindings_verified=len(a['code']), windows_exact_owners_absent=owners,
        source_prefix=bind(a['short_source']['path']), full_source_failure=bind(a['full_source_audit']['path']),
        full_source_failure_resolved=False, native_CM5_performance_measured=False,
        admission=bind(folder/'ADMISSION.json'), host=bind(folder/'RESULT.json'), native=bind(folder/'linux/RESULT.json'),
        linux_closure=bind(output/'LINUX_CLOSURE.json'), live_boot=bind(folder/'LIVE_VERIFICATION.json'),
        code=[bind(__file__), bind(HERE/'README_NATIVE_STREAM_SHORT_REVIEW_V3.md'), bind(HERE/'review_baseline_asr_cpu_v5.py')],
        GUI_validated=False, CM5_tested=False, N4_accepted=False, N5_complete=False)
    freeze(output / 'RESULT.json', result)
    print(json.dumps({k:result[k] for k in ('status', 'models', 'passed_models', 'unattempted_models')}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); run(a.run.resolve(), a.output.resolve())
