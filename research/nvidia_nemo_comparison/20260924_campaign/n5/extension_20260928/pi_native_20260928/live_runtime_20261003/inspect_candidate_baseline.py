"""Read current Pi state with explicit legacy host timestamp decoding. See README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import types


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--label', required=True)
    args = ap.parse_args()
    if not args.label.replace('-', '').isalnum():
        raise ValueError('Unique simple label')
    b = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
    p = Path(__file__).resolve().parent.parent
    out = b/'live-runtime-20261003'/('inspection-preparation-'+args.label)
    out.mkdir()
    me = psutil.Process()
    (out/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=me.pid, create_time=me.create_time(), affinity=[14])))
    original = (p/'field_runtime_host_precheck_v2.py').read_text()
    anchor = '            for pk,tk in ((\'pid\',\'create_time\'),(\'child_pid\',\'child_create_time\')):'
    if original.count(anchor) != 1:
        raise ValueError('Exact host identity decoder source changed')
    # These are actual early registrations from this iteration, not process
    # identities invented from a close/result. Keep the original bytes intact.
    injection = '''            relative = path.relative_to(private).as_posix() if path.is_relative_to(private) else ''
            if relative == 'live-runtime-20261003/presets-preparation-f8695921eb904d2cbdfa0ebb20b7b982/REGISTERED_OWNER.json':
                if type(value.get('create_time')) is not str or not value['create_time'].endswith('Z') or value.get('pid') != 45000:
                    raise ValueError('Exact retained ISO early registration changed')
                value = dict(value, create_time=datetime.fromisoformat(value['create_time'].replace('Z','+00:00')).timestamp())
            elif relative.startswith('live-runtime-20261003/audit-preparation/') and path.name == 'REGISTERED_OWNER.json' and 'creation_filetime' in value:
                if (value.get('schema') != 'just-peachy.host-registered-owner.v1' or type(value['creation_filetime']) is not int
                    or value['creation_filetime'] <= 116444736000000000 or value.get('cpu') != 14 or value.get('affinity_mask') != 16384):
                    raise ValueError('Exact Windows FILETIME early registration required')
                value = dict(value, create_time=(value['creation_filetime']-116444736000000000)/10000000)
'''
    derived = original.replace(anchor, injection+anchor)
    compile(derived, '<v29-host-owner-decoder>', 'exec')
    for name, data in (('source.py', derived.encode()), ('runner.py', Path(__file__).read_bytes())):
        for suffix in ('.backup', '.restore'):
            target = out/(name+suffix)
            with target.open('xb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            if target.read_bytes() != data:
                raise OSError('Independent source readback')
    (out/'DERIVATION.json').write_text(json.dumps(dict(original_sha256=hashlib.sha256(original.encode()).hexdigest(),
        derived_sha256=hashlib.sha256(derived.encode()).hexdigest(), original_owner_files_unchanged=True,
        timestamp_units=['UTC ISO8601', 'Windows FILETIME 100ns since 1601'], no_native_mutation=True)))
    module = types.ModuleType('field_runtime_host_precheck_v2')
    exec(compile(derived, '<v29-host-owner-decoder>', 'exec'), module.__dict__)
    sys.modules[module.__name__] = module
    runner = Path('C:/Users/amiri/Documents/GitHub/just-peachy/Resumes/desktop_exit_20261003/inspect_current.py')
    sys.argv = [str(runner), '--label', args.label]
    runpy.run_path(str(runner), run_name='__main__')


if __name__ == '__main__':
    main()
