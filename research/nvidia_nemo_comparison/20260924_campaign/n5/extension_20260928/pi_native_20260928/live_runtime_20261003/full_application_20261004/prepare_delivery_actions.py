"""Prepare two exact delivery adapters. See README_DELIVERY_ACTIONS.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def main():
    here = Path(__file__).resolve().parent
    private = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    package = private/'audit-preparation/full-application-package-e366bb9496184252bc36bd4576fd8c04/package'
    out = private/'audit-preparation'/('delivery-adapters-'+uuid.uuid4().hex)
    out.mkdir(); me = psutil.Process(); started = time.time()
    def write(name, raw):
        with (out/name).open('xb') as stream:
            assert stream.write(raw) == len(raw); stream.flush(); os.fsync(stream.fileno())
        assert (out/name).read_bytes() == raw
    def put(name, value):
        write(name, json.dumps(value, sort_keys=True, allow_nan=False).encode())
    put('REGISTERED_OWNER.json', dict(pid=me.pid, create_time=me.create_time(), affinity=[14]))
    put('HOST_SCOPE.json', dict(issued_unix=started, maximum_seconds=600, maximum_bytes=2*1024**2, native_action=False))
    def once(text, before, after):
        assert text.count(before) == 1, before
        return text.replace(before, after)
    activation_source = (here.parent/'ui_restore_20261004/activate_classic_desktop_action.py').read_bytes()
    activation = activation_source.decode()
    activation = once(activation, "field-runtime-v29-build-17", "field-runtime-v29-build-21")
    activation = once(activation, "len(rows) != 2", "len(rows) != 1")
    activation = once(activation,
        "{str(HOME/'Desktop/Just Peachy.desktop'), str(HOME/'Desktop/just-peachy-field-runtime-v28-d1-delayed.desktop')}",
        "{str(HOME/'Desktop/Just Peachy.desktop')}")
    activation = activation.replace('Exactly the two observed owned shortcuts required', 'Exactly the observed owned shortcut required')
    begin = activation.index("        'Exec=\"")
    end = activation.index("        'Terminal=false", begin)
    activation = activation[:begin]+"        'Exec='+binding['python']+' -B '+str(package/'native_scope.py')+' --binding '+str(package/'BINDING.json')+\n        ' --manifest-sha256 '+payload['package_manifest_sha256']+' --data-root '+str(DATA)+'\\n'\n"+activation[end:]
    activation = once(activation, "    raw = ('[Desktop Entry]", "    if any(any(c.isspace() for c in str(p)) for p in (binding['python'], package, DATA)):\n        raise ValueError('Exact launcher paths must contain no whitespace')\n    raw = ('[Desktop Entry]")
    begin = activation.index("    duplicate = HOME/")
    end = activation.index("    if read(autostart", begin)
    activation = activation[:begin]+activation[end:]
    activation = once(activation, "        archived_shortcut=str(evidence/'archived-shortcuts'/duplicate.name),", "        archived_shortcut=None,")
    activation = activation.replace('the two explicitly named owned Desktop entries', 'the one explicitly named owned Desktop entry')
    export_source = (here.parent/'launch_recording_export_action_v3.py').read_bytes()
    tree = ast.parse(export_source)
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'EXPORT_HELPER' for t in n.targets))
    helper = (package/'owned_export.py').read_bytes()
    manifest_raw = (package/'PACKAGE_MANIFEST.json').read_bytes()
    assert hashlib.sha256(manifest_raw).hexdigest() == '9abaaaffe35d328fd97f5fc47f1f5b938803705dffb728c5d804d225a646ba6e'
    entry = next(r for r in json.loads(manifest_raw)['files'] if r['path'] == 'owned_export.py')
    assert len(helper) == entry['bytes'] and hashlib.sha256(helper).hexdigest() == entry['sha256']
    lines = export_source.decode().splitlines(keepends=True)
    lines[assignment.lineno-1:assignment.end_lineno] = ['EXPORT_HELPER = '+repr(helper.decode())+'\n']
    export = ''.join(lines)
    export = once(export, "r'gui-qualification-\\d{2}'", "r'classic-ui-check-\\d{2}'")
    export = once(export, "Path(p['recordings_root'])!=source_root/'data/recordings'", "Path(p['recordings_root'])!=Path('/home/peachyprototype/JustPeachy/data/runtime-v29/recordings')")
    export = once(export, "    # Use the existing independently owned systemd helper", "    proof=json.loads((source_root/'NATIVE_CHECK_V2.json').read_bytes())\n    if (proof.get('status')!='PASS' or proof.get('session_id')!=p['session_id'] or\n        proof.get('processed_save_passed') is not True or proof.get('workers_closed') is not True or\n        proof.get('package_manifest_sha256')!=p['package_manifest_sha256'] or proof.get('boot_id')!=boot):\n        raise ValueError('Exact actually kept rich session and independently finalized source required')\n    # Use the existing independently owned systemd helper")
    results = [('activate_full_desktop_action_v1.py', activation_source, activation.encode()),
               ('launch_full_recording_export_action_v1.py', export_source, export.encode())]
    reviews = []
    for name, original, result in results:
        compile(result, '<delivery-adapter>', 'exec')
        before = {n.name:ast.dump(n, include_attributes=False) for n in ast.parse(original).body if isinstance(n, ast.FunctionDef)}
        after = {n.name:ast.dump(n, include_attributes=False) for n in ast.parse(result).body if isinstance(n, ast.FunctionDef)}
        expected = {'activate'} if name.startswith('activate') else {'dispatch'}
        assert set(before) == set(after) and {n for n in before if before[n] != after[n]} == expected
        for prefix, raw in [('ORIGINAL-',original),('BACKUP-',result),('RESTORE-',result)]: write(prefix+name, raw)
        with (here/name).open('xb') as stream:
            assert stream.write(result) == len(result); stream.flush(); os.fsync(stream.fileno())
        assert (here/name).read_bytes() == result
        reviews.append(dict(path=name, sha256=hashlib.sha256(result).hexdigest(), changed_functions=sorted(expected)))
    for name, raw in [('OWNED_EXPORT.py',helper),('README.md',(here/'README_DELIVERY_ACTIONS.md').read_bytes()),('PREPARER.py',Path(__file__).read_bytes())]:
        write(name, raw); write(name+'.restore',raw)
    assert sum(p.stat().st_size for p in out.iterdir()) < 2*1024**2 and time.time()-started < 600
    put('SOURCE_CLOSED.json', dict(reviews=reviews, independent_restore=True, native_action=False, closed_unix=time.time(), package_owned_export_sha256=entry['sha256']))
    print(json.dumps(dict(status='PASS', output=str(out), reviews=reviews)))


if __name__ == '__main__': main()
