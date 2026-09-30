"""CPU14 changed-source review; README_FIELD_NATIVE_BINDING_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from field_native_binding_v1 import derive, METHODS, CONTROL_NAMES


def dump(value):
    if isinstance(value, list):
        return [dump(n) for n in value]
    return ast.dump(value, include_attributes=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--installed-mirror', type=Path, required=True)
    args = parser.parse_args()
    admission = json.loads((args.preparation/'ADMISSION_REVIEW_V1.json').read_bytes())
    assert datetime.now(timezone.utc) < datetime.fromisoformat(admission['expires_utc'])
    assert psutil.Process().cpu_affinity() == [14] and admission['native_dispatch'] is False
    output = args.preparation/'SOURCE_BINDING_REVIEW_V1.json'
    if output.exists():
        raise FileExistsError('Closed source review cannot be replayed')
    base = args.installed_mirror
    manifest_raw = (base/'RELEASE_MANIFEST.json').read_bytes()
    assert hashlib.sha256(manifest_raw).hexdigest() == '274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0'
    manifest = {row['path']:row for row in json.loads(manifest_raw)['files']}
    pins = {}
    for name, relative in [('pipeline','app/pipeline.py'), ('runtime','vendor/edge_speech_pipeline/runtime.py'),
                           ('trace','vendor/edge_speech_pipeline/research_s7.py')]:
        raw = (base/relative).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        assert sha == manifest[relative]['sha256']
        pins[name] = dict(relative=relative, bytes=len(raw), sha256=sha)
    source = (base/pins['runtime']['relative']).read_bytes()
    old, new = derive(source)
    checks = []

    # Full session-watcher body, handlers, and cleanup prefix are unchanged.
    a, b = old['_watch_session'].body[0], new['_watch_session'].body[0]
    assert dump(a.body) == dump(b.body) and dump(a.handlers) == dump(b.handlers)
    assert dump(a.orelse) == dump(b.orelse) and dump(a.finalbody[:-1]) == dump(b.finalbody[:-1])
    x, y = a.finalbody[-1], b.finalbody[-1]
    assert dump(x.test) == dump(y.test) and dump(x.body[0]) == dump(y.body[0])
    assert dump(x.body[2].body[:-2]) == dump(y.body[1].body[:-1])
    assert dump(x.body[2].handlers) == dump(y.body[1].handlers)
    checks.append('watcher lane drainage, model release, handle close and terminal payload/error handler AST exact')

    a, b = old['_write_revised_transcript'], new['_write_revised_transcript']
    assert dump(a.body[:-1]) == dump(b.body[:-1])
    assert dump(a.body[-1].body[:-1]) == dump(b.body[-1].body)
    assert dump(a.body[-1].items[0].optional_vars) == dump(b.body[-1].items[0].optional_vars)
    checks.append('revised transcript final-row selection and punctuation payload AST exact')

    a, b = old['_write_summary'], new['_write_summary']
    assert dump(a.body[:-3]) == dump(b.body[:-1])
    checks.append('summary telemetry/assets/scientific policy payload AST exact; retry removed')

    a, b = old['record_s6d_consumer_closure'], new['record_s6d_consumer_closure']
    assert dump(a.body[:-1]) == dump(b.body[:-1]) and dump(a.body[-1].test) == dump(b.body[-1].test)
    original_payload = a.body[-1].body[0].value.args[0].left.args[0]
    actual_payload = b.body[-1].body[0].value.args[1]
    assert dump(original_payload) == dump(actual_payload)
    checks.append('consumer full-drain check, idempotence gate and payload AST exact')

    for name in METHODS:
        node = ast.fix_missing_locations(ast.Module(body=[deepcopy(new[name])], type_ignores=[]))
        compile(node, '<reviewed-installed-'+name+'>', 'exec')
        calls = [ast.unparse(n.func) for n in ast.walk(new[name]) if isinstance(n, ast.Call)]
        assert not any(n in ('os.replace', 'path.open', 'temporary.open', 'path.write_text') for n in calls)
    assert set(CONTROL_NAMES) == {'session_summary.json','session_finalization_v3.json','s6d_consumer_closure.json'}
    checks.append('all four changed methods compile; old direct writer/replace sites absent')

    rejects = []
    for label, before, after in [
        ('changed revised open mode', 'with path.open("x", encoding="utf-8") as handle:', 'with path.open("w", encoding="utf-8") as handle:'),
        ('changed finalization replace', 'os.replace(temporary, destination)', 'os.rename(temporary, destination)')]:
        changed = source.decode().replace(before, after, 1)
        assert changed.encode() != source
        try:
            derive(changed)
        except ValueError as exc:
            rejects.append(dict(case=label, error=str(exc)))
        else:
            raise AssertionError('Changed publication structure was accepted')

    code = {}
    for name in ('field_native_binding_v1.py','field_native_text_v2.py','check_field_native_binding_v1.py'):
        raw = (Path(__file__).parent/name).read_bytes()
        compile(raw, name, 'exec')
        code[name] = dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    receipt = dict(status='PASS_ACTUAL_NATIVE_SOURCE_DERIVATION_ONLY',
        checked_utc=datetime.now(timezone.utc).isoformat(), affinity=psutil.Process().cpu_affinity(),
        installed_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(), pins=pins,
        checks=checks, changed_structure_rejects=rejects, code=code,
        native_execution=False, actual_runtime_binding=False, source=False, model=False,
        full_composition=False, original_bound_sources_changed=False)
    raw = json.dumps(receipt,indent=2).encode()
    assert len(raw) < 32768
    with output.open('xb') as f:
        f.write(raw)
    print(json.dumps(dict(status=receipt['status'], checks=len(checks), rejects=len(rejects))))


if __name__ == '__main__':
    main()
