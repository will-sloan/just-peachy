"""Narrow ALSA packaging correction; README_FIELD_LIVE_GUI_V2.md."""
import hashlib,json,shutil,sys
from pathlib import Path


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def build(root,a):
    prior=Path(a['installed_release']);source=root/'source'
    assert {p.relative_to(prior).as_posix():sha(p) for p in prior.rglob('*') if p.is_file()}==a['installed_files']
    shutil.copytree(prior,source,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(root/'field_entry_v5.py',source/'native/field_entry_v5.py')
    shutil.copyfile(root/'alsa_hw_only_v1.conf',source/'config/alsa_hw_only_v1.conf')
    shutil.copyfile(root/'README_FIELD_LIVE_GUI_V2.md',source/'docs/README_FIELD_LIVE_GUI_V2.md')
    shutil.copyfile(root/'README_FIELD_LIVE_GUI_V1.md',source/'docs/README_FIELD_LIVE_GUI_V1.md')
    (source/'main.py').write_text('from native.field_entry_v5 import main\nif __name__=="__main__":raise SystemExit(main())\n')
    tool=source/'release_tools/release.py';old=tool.read_text()
    before="if path.suffix.lower() not in ALLOWED_SUFFIXES and path.name != 'LICENSE':"
    after="if path.suffix.lower() not in ALLOWED_SUFFIXES and path.name != 'LICENSE' and rel.as_posix() != 'config/alsa_hw_only_v1.conf':"
    assert old.count(before)==1;tool.write_text(old.replace(before,after))
    # Confirm the extension whitelist stays closed for unrelated config files.
    (source/'config/unrelated.conf').write_text('SYNTHETIC_EXCLUSION_FIXTURE\n')
    sys.path.insert(0,str(source));from release_tools import release
    built=release.build(source,root/'archives','b01-offline-20260930-v5')
    staged=release.stage(built['archive'],root/'deployment',built['sha256']);installed=Path(staged['path'])
    manifest=json.loads((installed/'RELEASE_MANIFEST.json').read_text());paths={r['path'] for r in manifest['files']}
    assert 'config/alsa_hw_only_v1.conf' in paths and 'config/unrelated.conf' not in paths
    assert sha(installed/'config/alsa_hw_only_v1.conf')=='d81bc353dcab14d172e78b26c6116bfc8462b96e45e44b1a93ac3f217898564d'
    with (root/'CANDIDATE_BUILD.json').open('x') as f:json.dump(dict(built=built,staged=staged,manifest_sha256=sha(installed/'RELEASE_MANIFEST.json'),alsa_configuration_included=True,unrelated_conf_excluded=True,original_release_unchanged=True),f,indent=2)
    sys.path.remove(str(source))
    for name in list(sys.modules):
        if name=='release_tools' or name.startswith('release_tools.'):del sys.modules[name]
    return installed
