"""Read-only independent CPU-contrast audit; README_BASELINE_ASR_CPU_REVIEW_V5.md."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'n4'))
from common import bind, freeze, load, verify
from metric_process import pin, exact_process
from run_baseline_asr_diagnostic_v3 import read_events


def windows_binding(b):
    p = b['path']
    if p.startswith('/mnt/') and len(p) > 7 and p[6] == '/':
        p = p[5].upper()+':/'+p[7:]
    actual = bind(p)
    if (actual['bytes'], actual['sha256']) != (b['bytes'], b['sha256']):
        raise ValueError('Binding differs: '+p)
    return Path(p)


def review(run, output):
    pin()
    if output.exists():
        raise ValueError('Fresh audit directory required')
    a = load(run/'ADMISSION.json'); terminal = load(run/'RESULT.json')
    assert a['scope'] == 'BASELINE_C_API_CPU_CONTRAST_V5'
    assert terminal['status'] == 'DIAGNOSTIC_COMPLETED_NO_ACCEPTANCE' and terminal['error'] is None
    verify(terminal['admission']); verify(terminal['linux_result'])
    for b in a['code']+[a[k] for k in ('precheck','census','prior_admission','prior_linux_inputs','prior_model_command','prior_binary_record','prior_windows_events','audio')]+[r['asset'] for r in a['models']]:
        verify(b)
    owners = [terminal['owner'], terminal['wsl_owner'], {k:a['supervisor'][k] for k in ('pid','create_time')}]
    assert all(exact_process(o) is None for o in owners)
    lt = load(run/'linux/RESULT.json'); model = load(run/'linux/model.json'); help_result = load(run/'linux/cpu_help.json')
    assert lt['status'] == 'DIAGNOSTIC_COMPLETED_NO_ACCEPTANCE' and lt['error'] is None
    for c in (model, help_result):
        windows_binding(c['stdout']); windows_binding(c['stderr'])
        assert c['cancelled'] is None and not c['remaining_group_members']
    assert model['returncode'] == 0 and help_result['returncode'] in (0,1)
    assert (run/'linux/cpu_help.stderr').read_bytes() == b''
    assert 'cortex-a76' in [x.strip() for x in (run/'linux/cpu_help.stdout').read_text(encoding='utf-8').splitlines()[1:]]
    old_command = load(a['prior_model_command']['path'])
    assert model['argv'][1:3] == ['-cpu','cortex-a76']
    assert model['argv'][:1]+model['argv'][3:] == old_command['argv']
    assert lt['commands'][-1] == model
    inputs = load(run/'linux/INPUTS.json')
    old_binary = load(a['prior_binary_record']['path'])
    assert inputs['reused_binary'] == old_binary
    windows_binding(old_binary)
    fresh = read_events(run/'linux/model.stdout', a['frames'])
    old = read_events(windows_binding(old_command['stdout']), a['frames'])
    reference = read_events(a['prior_windows_events']['path'], a['frames'])
    for measurement in (old, reference):
        for key in ('frames','nonzero','f32_le_fnv1a64','sherpa_version','sherpa_git'):
            assert fresh['info'][key] == measurement['info'][key]
    # Fresh read-only Linux census, with exact PID/start-tick identities and groups.
    linux_owners = [lt['owner'], model['owner'], help_result['owner']]
    program = '''import json,pathlib
owners=json.loads(__import__('sys').argv[1]);rows=[]
for o in owners:
 p=pathlib.Path('/proc')/str(o['pid'])/'stat'
 s=p.read_text().rsplit(')',1)[1].split() if p.exists() else None
 members=[]
 for f in pathlib.Path('/proc').glob('[0-9]*/stat'):
  try:
   v=f.read_text().rsplit(')',1)[1].split()
   if int(v[2])==o['pid']:members.append(dict(pid=int(f.parent.name),start_ticks=int(v[19])))
  except FileNotFoundError:pass
 rows.append(dict(owner=o,exact_owner_exists=bool(s and int(s[19])==o['start_ticks']),group_members=members))
print(json.dumps(dict(boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),rows=rows)))
'''
    check = subprocess.run(['wsl.exe','-d','Ubuntu','--','python3','-c',program,json.dumps(linux_owners)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    assert not check.stderr.strip()
    census = json.loads(check.stdout)
    assert all(not r['exact_owner_exists'] and not r['group_members'] for r in census['rows'])
    output.mkdir()
    freeze(output/'LINUX_CLOSURE.json', census)
    result = dict(status='REVIEWED_CPU_CONTRAST_NONEMPTY_REQUIRES_RETEST' if fresh['complete']['nonempty'] else 'REVIEWED_CPU_CONTRAST_EMPTY_TEXT_PERSISTS',
        checked_utc=datetime.now(timezone.utc).isoformat(), frames=a['frames'], audio_seconds=a['frames']/16000,
        diagnostic_models_rerun=1, changed_variable='QEMU -cpu cortex-a76 only; same binary/models/audio/recognizer settings',
        decoded_input_and_sherpa_revision_identical=True,
        reference_windows=dict(finals=len(reference['case']['finals']),endpoint_resets=reference['case']['endpoint_resets']),
        original_emulated=dict(finals=len(old['case']['finals']),endpoint_resets=old['case']['endpoint_resets'],elapsed_seconds=old_command['elapsed_seconds']),
        cortex_a76_emulated=dict(finals=len(fresh['case']['finals']),endpoint_resets=fresh['case']['endpoint_resets'],elapsed_seconds=model['elapsed_seconds']),
        reference_finals_equal=fresh['case']['finals']==reference['case']['finals'],
        old_emulated_finals_equal=fresh['case']['finals']==old['case']['finals'],
        windows_owners_closed=owners,linux_closure=bind(output/'LINUX_CLOSURE.json'),
        run=bind(run/'RESULT.json'),admission=bind(run/'ADMISSION.json'),model=bind(run/'linux/model.json'),
        preserved_preflight=a['preserved_preflight'],source_bindings_verified=len(a['code']),
        review_code=[bind(__file__),bind(HERE/'README_BASELINE_ASR_CPU_REVIEW_V5.md')],
        inference_acceptance=False,CM5_tested=False,N5_complete=False)
    freeze(output/'RESULT.json', result)
    print(json.dumps({k:result[k] for k in ('status','reference_windows','original_emulated','cortex_a76_emulated')},indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a = p.parse_args();review(a.run,a.output)
