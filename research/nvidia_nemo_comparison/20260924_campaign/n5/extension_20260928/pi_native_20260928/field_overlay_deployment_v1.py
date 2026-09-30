"""Explicit compact-binding/overlay adapter; README_FIELD_OVERLAY_LAUNCHER_V1.md."""
import importlib.util
from pathlib import Path
import sys
import field_dependencies_v2 as pins
import field_dependency_binding_v1 as compact

KEYS={'schema','version','release','manifest_sha256','candidate_root','data_root','config_sha256','base_binding','overlay'}
OVERLAY_KEYS={'source','source_sha256','descriptor','descriptor_sha256'}

def loaded_overlay(row):
    path=Path(row['source'])
    if pins.sha(path)!=row['source_sha256']:raise ValueError('Overlay source hash changed')
    name='bound_retained_archive_overlay'
    if name in sys.modules:
        module=sys.modules[name]
        if Path(module.__file__).resolve()!=path:raise ValueError('Overlay loaded module origin')
        return module
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    try:spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module

def check_descriptor(path,expected_sha,release_tools):
    path=Path(path)
    if path.stat().st_size>32768 or pins.sha(path)!=expected_sha:raise ValueError('Deployment adapter descriptor hash/bound')
    d=pins.read(path);campaign=Path(__file__).resolve().parent.parent
    if type(d) is not dict or set(d)!=KEYS or d['schema']!='just-peachy.overlay-deployment.v1':raise ValueError('Explicit overlay deployment schema')
    release=campaign/'field-artifact-install-v2/deployment/releases/b01-offline-20260930-v12'
    if d['release']!=str(release) or d['manifest_sha256']!='274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0':raise ValueError('Deployment base release')
    for key in ['candidate_root','data_root']:
        p=Path(d[key])
        if not p.is_absolute() or p.resolve()!=p:raise ValueError('Deployment canonical path')
    if set(d['config_sha256'])!={'DATA_SCHEMA.json','live_config.json','n2_runtime.json'}:raise ValueError('Required deployment configuration set')
    for name,digest in d['config_sha256'].items():
        p=Path(d['data_root'])/name
        if not p.is_file() or p.is_symlink() or pins.sha(p)!=digest:raise ValueError('Deployment configuration changed: '+name)
    binding=d['base_binding']
    if type(binding) is not dict or set(binding)!={'path','sha256'} or binding['path']!=str(campaign/'field-dependency-binding-v1/CONTRACT_BINDING.json') or binding['sha256']!='b51bcd761f66ba5be2cba9ad6855519ffeab09c9c835df7b52518fcabd67d814':
        raise ValueError('Explicit retained compact binding required')
    row=d['overlay'];bound=None
    if row is not None:
        if type(row) is not dict or set(row)!=OVERLAY_KEYS:raise ValueError('Overlay deployment fields')
        if row['source']!=str(campaign/'field-archive-overlay-v1/field_archive_overlay_v1.py') or row['descriptor']!=str(campaign/'field-archive-overlay-v1/OVERLAY_MANIFEST.json'):
            raise ValueError('Retained overlay origin')
        module=loaded_overlay(row);bound=module.verify(row['descriptor'],row['descriptor_sha256'])
        if bound['base']!=release:raise ValueError('Overlay base conflicts with compact binding')
    version='b01-offline-20260930-v12'+('+archive-budget-v2' if row is not None else '')
    if d['version']!=version:raise ValueError('Overlay deployment version')
    # Validate the original five-change contract plus all 7890 retained entries.
    # The extra archive-policy delta is checked independently by the bound overlay.
    exact=compact.verify(binding['path'],binding['sha256'],release_tools)
    if exact['selected_release']['path']!=str(release):raise ValueError('Compact selection mismatch')
    manifest=release_tools.verify_release(release)
    if pins.sha(release/'RELEASE_MANIFEST.json')!=d['manifest_sha256']:raise ValueError('Deployment manifest changed')
    checked={**exact['dependency_check'], 'compact_binding_sha256':binding['sha256'],
             'overlay_source_sha256':row['source_sha256'] if row else None,
             'overlay_descriptor_sha256':row['descriptor_sha256'] if row else None,
             'archive_budget_sha256':bound['descriptor']['budget_canonical_sha256'] if bound else None,
             'catalogue_copied':False,'new_inventory':False}
    return d,manifest,checked
