"""Explicit four-condition file invocation; see README_S6C_OPERATING_INVOCATIONS_V1.md."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import types

SIM = Path(__file__).resolve().parents[1]
REPO = SIM.parents[2]
REPORT = SIM / 'reports/S6C/20260910T123540Z'
PLANS = {
    'B36': ('long_b36/b36_o0_continuous_fast_v1/MANIFEST.json', '853499c10f3ea80de4cf5ab4e8569a9cf1c8008d6dcdb47ed486dd4d0528ffa7'),
    'C067': ('long_native_epoch4/epoch4_long_c067_o0_fast_v2/MANIFEST.json', '7827894c482464fe0099a349e897f932dc813995432b19c2f228977144c92675'),
    'C088': ('long_native_epoch4/epoch4_long_c088_o0_fast_v2/MANIFEST.json', 'f4cd1952ed92dfb23aa1fcbc082df72dead2433b8de5819885d5ecd6e00a4c85'),
    'C091': ('long_native_epoch4/epoch4_long_c091_o0_fast_v2/MANIFEST.json', '1890486c14c2d3b044bb1d0fc5d2ee65c5e2fac982d80de87bc16c729b6e53d7'),
}
EXAMPLE_WAV = Path('G:/Just_Peachy_S6B/20260909T230840Z/inputs/S45_01_06/O0.wav')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def read(path, expected=None):
    path = Path(path).resolve()
    require(path.stat().st_size <= 8 * 1024**2, 'Source/metadata input only')
    raw = path.read_bytes()
    binding = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    if isinstance(expected, str):
        require(binding['sha256'] == expected, 'Changed pinned source: ' + str(path))
    elif expected:
        require(binding == expected, 'Changed exact binding: ' + str(path))
    return raw, binding

def doc(path, expected=None):
    raw, binding = read(path, expected)
    return json.loads(raw), binding

def admit(candidate):
    rel, sha = PLANS[candidate]
    plan, pb = doc(REPORT / rel, sha)
    historical = candidate == 'B36'
    eb = plan['historical_epoch' if historical else 'execution_manifest']
    epoch, _ = doc(eb['path'], eb)
    if historical:
        row = plan['b36_registry_entry']
        profile_binding = row['file_binding']
        expected_profile = row['profile']
        gallery_binding = None
        app = Path(plan['jobs'][0]['app_path']).resolve()
        require(plan['actual_execution_epoch'] == 'S6B_epoch2', 'Historical generation')
        require(plan['jobs'][0]['profile'] == expected_profile and plan['jobs'][0]['assets'] == epoch['assets'], 'Original B36 settings')
    else:
        row = plan['profile_row']
        require(row['candidate_id'] == candidate and row['asr_tap'] == row['identity_tap'] == 'O0', 'Exact O0 route')
        require(row['cue_condition'] == 'CUES_OFF', 'No telemetry substitution')
        profile_binding = row['profile_binding']
        expected_profile = row['profile']
        gallery_binding = plan['gallery']
        app = SIM / 'staging/s6c/20260910T123540Z/epoch4/app'
        require(plan['actual_execution_epoch'] == 'epoch4', 'Exact C generation')
    profile, _ = doc(profile_binding['path'], profile_binding)
    require(profile == expected_profile, 'Whole registered profile')
    require(profile['xvf']['mode'] == 'none' and profile['tracker']['cues_enabled'] is False, 'Cues off')
    require(profile['input']['gain'] == 1.0 and profile['input']['already_gained'] is True, 'Once-gained input')
    gallery = None
    if gallery_binding:
        gallery, _ = doc(gallery_binding['path'], gallery_binding)
        require(candidate in ('C088', 'C091') and len(gallery['profiles']) == 15, 'Original15 gallery')
    else:
        require(candidate in ('B36', 'C067'), 'Required naming gallery absent')
    app_files = [b for b in epoch['execution_files'] if Path(b['path']).is_relative_to(app) and Path(b['path']).suffix == '.py']
    require(app_files and any(Path(b['path']).name == 'cli.py' for b in app_files), 'Frozen CLI authority')
    current = REPO / 'Software Validation from Datasets/Evaluation Tool/app'
    parity = []
    for b in app_files:
        raw, _ = read(b['path'], b)
        cp = current / Path(b['path']).relative_to(app)
        cb = read(cp)[1] if cp.is_file() else None
        parity.append(dict(relative_path=str(Path(b['path']).relative_to(app)), frozen=b, current=cb, same_bytes=cb is not None and cb['sha256'] == b['sha256']))
    require(len({x['component_id'] for x in epoch['assets']}) == len(epoch['assets']) == 8, 'Exact eight asset declarations')
    for x in epoch['assets']:
        require(x['path'] == x['binding']['path'] and x['sha256'] == x['binding']['sha256'], 'Asset declaration identity')
    return dict(candidate=candidate, historical=historical, plan=pb, epoch=eb, app=str(app), app_files=app_files,
                current_app_parity=parity, profile_binding=profile_binding, profile=profile,
                gallery_binding=gallery_binding, gallery_count=0 if gallery is None else len(gallery['profiles']), assets=epoch['assets'])

def context(admitted, output_root):
    require(not any(k == 'edge_speech_pipeline' or k.startswith('edge_speech_pipeline.') for k in sys.modules), 'Use a fresh interpreter per generation')
    for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    sys.dont_write_bytecode = True
    sys.path.insert(0, admitted['app'])
    cli = importlib.import_module('edge_speech_pipeline.cli')
    cfg = importlib.import_module('edge_speech_pipeline.config')
    profiles = importlib.import_module('edge_speech_pipeline.research_profiles')
    assets = tuple(cfg.AssetSpec(x['component_id'], Path(x['path']), x['sha256'], x['deployment_relative_path']) for x in admitted['assets'])
    base = cfg.PipelineConfig(assets=assets, session_root=output_root/'sessions', profile_root=output_root/'empty_private_profiles')
    profile = profiles.ResearchProfile.from_dict(admitted['profile'])
    require(profile.to_dict() == admitted['profile'], 'Original parser effective profile equality')
    effective = profile.effective(profile.apply(base))
    require(all(getattr(profile.apply(base), k) == 1 for k in ('asr_threads', 'speaker_threads', 'punctuation_threads')), 'Original one-thread settings')
    # A private globals dictionary supplies explicit original AssetSpecs. Original
    # CLI code and imported scientific functions remain untouched.
    globals_copy = dict(cli.main.__globals__)
    globals_copy['PipelineConfig'] = lambda: base
    entry = types.FunctionType(cli.main.__code__, globals_copy, cli.main.__name__, cli.main.__defaults__, cli.main.__closure__)
    return cli, entry, effective

def file_args(admitted, wav):
    args = ['file', str(wav), '--research-profile', admitted['profile_binding']['path']]
    if not admitted['historical']:
        args += ['--identity-wav', str(wav)]
    if admitted['gallery_binding']:
        args += ['--research-gallery', admitted['gallery_binding']['path']]
    return args

def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('mode', choices=('validate', 'file'))
    parser.add_argument('--candidate', required=True, choices=tuple(PLANS))
    parser.add_argument('--wav', type=Path, default=EXAMPLE_WAV)
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--receipt', type=Path, help='Fresh JSON file for model-free validation only')
    args = parser.parse_args()
    if args.mode == 'file':
        require(args.output_root is not None and args.receipt is None, 'File mode requires explicit fresh output root; no validation receipt')
        require(not args.output_root.exists(), 'Fresh output namespace only')
        require(not (REPORT/'PACED_QUIET_OWNER.json').exists(), 'Active measured session')
    else:
        require(args.receipt is None or not args.receipt.exists(), 'Fresh validation receipt only')
    output = (args.output_root or Path('G:/Just_Peachy_S6C/20260910T123540Z/user_invocations/validation_only')).resolve()
    admitted = admit(args.candidate)
    cli, entry, effective = context(admitted, output)
    argv = file_args(admitted, args.wav.resolve())
    parsed = cli._parser().parse_args(argv)
    require(parsed.command == 'file' and parsed.accelerated is False, 'Original source-paced CLI parser')
    if args.mode == 'file':
        return entry(argv)
    result = dict(schema='s6c-operating-invocation-validation.v1', status='VALIDATED_METADATA_AND_EFFECTIVE_PROFILE_NO_INFERENCE',
                  admission=admitted, effective=effective, original_cli_argv=argv, output_root=str(output),
                  source=read(__file__)[1], readme=read(Path(__file__).with_name('README_S6C_OPERATING_INVOCATIONS_V1.md'))[1],
                  models_started=0, audio_or_vectors_read=False, file_execution_performed=False,
                  scope='Original frozen CLI parser/profile application and explicit epoch asset declarations only. Gallery manifest metadata is checked; template/weight/audio contents are not revalidated. File mode is an optional direct application invocation, not a measured campaign coordinator or new study result.')
    raw = (json.dumps(result, indent=2, default=str, allow_nan=False)+'\n').encode()
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        with args.receipt.open('xb') as f:
            f.write(raw)
        print(json.dumps(dict(path=str(args.receipt.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())))
    else:
        print(raw.decode())
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
