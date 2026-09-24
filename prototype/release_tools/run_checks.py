"""Run local packaging checks, optionally WSL Linux tests; no SSH or microphone."""
import argparse
import json
import platform
from pathlib import Path
import subprocess
import sys
import tempfile
from release import build, now, write_json

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--wsl', action='store_true', help='Use the already installed Ubuntu WSL; never install one')
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
base = Path(__file__).resolve().parent
checks = []


def run(name, command, expected=0):
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    (a.output / f'{name}.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
    checks.append(dict(name=name, status='PASS' if result.returncode == expected else 'FAIL', exit_code=result.returncode))


run('windows_stdlib_tests', [sys.executable, '-m', 'unittest', 'discover', '-s', str(base / 'tests'), '-v'])
with tempfile.TemporaryDirectory(prefix='PROTO1 deployment dry run with spaces ') as td:
    root = Path(td); src = root / 'app'; (src / 'config').mkdir(parents=True)
    (src / 'main.py').write_text('print("fixture only")\n', encoding='utf-8')
    write_json(src / 'config' / 'assets.json', [])
    receipt = build(src, root / 'output', 'fixture-1')
    key = root / 'FAKE_KEY_NOT_A_CREDENTIAL'; key.write_text('Test placeholder. No SSH is executed.\n', encoding='utf-8')
    run('powershell_deploy_dryrun', ['powershell.exe', '-NoProfile', '-File', str(base / 'tests' / 'test_deploy.ps1'),
        '-Archive', receipt['archive'], '-FakeKey', str(key), '-Output', str((a.output / 'DEPLOY_DRY_RUN.json').resolve()), '-Python', sys.executable])
run('bash_syntax', [r'C:\Program Files\Git\bin\bash.exe', '-n', str(base / 'install_pi.sh')])
if a.wsl:
    linux = '/mnt/' + base.drive[0].lower() + base.as_posix()[2:]
    run('linux_stdlib_tests', ['wsl', '-d', 'Ubuntu', '--', 'python3', '-m', 'unittest', 'discover', '-s', linux + '/tests', '-v'])
    run('linux_platform', ['wsl', '-d', 'Ubuntu', '--', 'python3', '-c', 'import platform,json;print(json.dumps({"machine":platform.machine(),"python":platform.python_version(),"platform":platform.platform()}))'])
    run('linux_install_arch_guard', ['wsl', '-d', 'Ubuntu', '--', 'bash', linux + '/install_pi.sh', '--archive', '/not-read', '--sha256', '0'*64, '--root', '/not-created', '--data-root', '/not-created-data'], expected=2)
summary = dict(schema='just-peachy.release-tests.v1', checked_utc=now(), host=platform.platform(),
    python=platform.python_version(), status='PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL', checks=checks,
    no_ssh=True, no_microphone=True, no_system_install=True, cm5='CM5_HARDWARE_NOT_TESTED')
write_json(a.output / 'RELEASE_TEST_RESULTS.json', summary)
print(json.dumps(summary, indent=2))
raise SystemExit(0 if summary['status']=='PASS' else 1)
