"""Pinned production idle-dispatch derivative; README_NORMAL_GUI_WORKFLOW.md."""
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import stat

REFERENCE_SHA='b123694a1c530090ff860f1a544227ada4e8a5d413dfc5078f6a14cf7d79d40e'
PACKAGE_PIN='5e4b8f21a0cbd04bedbccc6c2504cee7910fc60deda09c4777dc9ffe07c05e3f'
NATIVE_PACKAGE='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-35'


def blob(p,name,maximum):
    raw=base64.b64decode(p[name+'_b64'],validate=True)
    if not 0<len(raw)<=maximum or hashlib.sha256(raw).hexdigest()!=p[name+'_sha256']:
        raise ValueError('Exact bounded independently-backed '+name+' required')
    return raw


def derive_reference(raw):
    """Only the reviewed dispatch boundaries change; reverse AST is exact."""
    if hashlib.sha256(raw).hexdigest()!=REFERENCE_SHA:raise ValueError('Frozen production idle source pin differs')
    original=raw.decode();tree=ast.parse(original)
    dispatch=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='dispatch']
    if len(dispatch)!=1:raise ValueError('Exact sole reference dispatch required')
    node=dispatch[0];lines=original.splitlines(keepends=True)
    old=''.join(lines[node.lineno-1:node.end_lineno]);changed=old
    substitutions=(
        ("p.get('verify_optional_policy')", "p.get('normal_start_stop_discard')"),
        ("r'production-idle-[0-9]{2}'", "r'production-normal-[0-9]{2}'"),
        ("runtime_seconds=120", "runtime_seconds=300"),
        ("'--property=RuntimeMaxSec=120'", "'--property=RuntimeMaxSec=300'"),
        ("deadline_unix=time.time()+165", "deadline_unix=time.time()+345"),
        ("idle_control.py", "normal_control.py"),
        ("wrapper=helper['wrapper_source'](settings).encode()", "wrapper=normal_wrapper(helper,settings).encode()"),
        ("out.mkdir();put=helper['put']", "out.mkdir();put=helper['put']\n    write_extra_sources(out,p)"),
        ("baseline_sha256=helper['sha'](out/'BASELINE.json'),**unchanged", "baseline_sha256=helper['sha'](out/'BASELINE.json'),chooser_rows=CHOOSER_ROWS,**unchanged"),
        ("capture=False,models_constructed=False", "capture_authorized=True,models_constructed_at_admission=False"),
    )
    for before,after in substitutions:
        count=changed.count(before)
        expected=2 if before=='idle_control.py' else 1
        if count!=expected:raise ValueError('Pinned dispatch boundary count differs: '+before)
        changed=changed.replace(before,after)
    # Test metadata reserve only. The normal worker chooses its real independent
    # disk-capacity allocation; no product recording, drain or model limit changes.
    if changed.count('16*1024**2')!=6:raise ValueError('Exact idle metadata reserve boundaries differ')
    changed=changed.replace('16*1024**2','32*1024**2')
    restored=changed.replace('32*1024**2','16*1024**2')
    for before,after in reversed(substitutions):
        restored=restored.replace(after,before)
    if ast.dump(ast.parse(restored),include_attributes=False)!=ast.dump(ast.parse(old),include_attributes=False):
        raise ValueError('Dispatch reverse AST proof differs')
    lines[node.lineno-1:node.end_lineno]=[changed]
    derived=''.join(lines)
    # The original bottom-level injected dispatch is omitted; caller admits all
    # extra source pins first and invokes the sole derived function once.
    entry="if 'PAYLOAD' in globals():RESULT=dispatch(PAYLOAD,BASELINE)"
    if derived.count(entry)!=1:raise ValueError('Reference dispatch entry drift')
    return derived.replace(entry,'')


CHOOSER_ROWS={
    'pyannote_redimnet':'Pyannote + ReDimNet','pyannote_titanet':'Pyannote + TitaNet',
    'delayed_redimnet':'Nemotron Delayed + ReDimNet','delayed_titanet':'Nemotron Delayed + TitaNet',
    'chunk52_2t_redimnet':'Nemotron Chunk52 2T + ReDimNet','chunk52_2t_titanet':'Nemotron Chunk52 2T + TitaNet',
}


def write_extra_sources(out,p):
    for name,raw in (('IDLE_REFERENCE.py',blob(p,'reference_source',262144)),):
        with (out/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short workflow source write')
            stream.flush();os.fsync(stream.fileno())
        if (out/name).read_bytes()!=raw:raise OSError('Independent workflow source readback differs')


def normal_wrapper(helper,settings):
    if settings['kind']!='production_idle' or settings['argv']!=[settings['output']+'/normal_control.py',settings['output']]:
        raise ValueError('Exact external metadata controller wrapper required')
    text=helper['wrapper_source'](settings)
    before='model_address_space_bytes=1024**3 if recording_model_scope else 768*1024**2'
    after='model_address_space_bytes=256*1024**2  # external metadata controller only'
    if text.count(before)!=1:raise ValueError('Exact shared wrapper metadata address-space boundary drift')
    changed=text.replace(before,after)
    if changed.replace(after,before)!=text:raise ValueError('Metadata wrapper reverse proof differs')
    compile(changed,'<normal-gui-metadata-wrapper>','exec')
    return changed


def launch(p,baseline):
    if (p.get('schema')!='just-peachy.normal-production-gui-launch.v1'
            or p.get('normal_start_stop_discard') is not True
            or p.get('package')!=NATIVE_PACKAGE or p.get('package_manifest_sha256')!=PACKAGE_PIN):
        raise ValueError('Explicit exact build35 normal-production action required')
    raw=blob(p,'reference_source',262144);control=blob(p,'control_source',65536)
    if hashlib.sha256(raw).hexdigest()!=REFERENCE_SHA:raise ValueError('Frozen reference source differs')
    compile(control,'<admitted-external-normal-control>','exec')
    space={'__name__':'normal_gui_dispatch_reference','__file__':'<pinned-idle-reference>',
        'normal_wrapper':normal_wrapper,'write_extra_sources':write_extra_sources,'CHOOSER_ROWS':CHOOSER_ROWS}
    exec(compile(derive_reference(raw),'<pinned-normal-dispatch>','exec'),space)
    space['CONTROL_SOURCE']=control.decode()
    return space['dispatch'](p,baseline)


if 'PAYLOAD' in globals():RESULT=launch(PAYLOAD,BASELINE)
