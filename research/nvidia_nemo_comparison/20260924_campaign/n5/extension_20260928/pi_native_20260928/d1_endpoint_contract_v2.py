"""Pinned chunk52 endpoint accounting; README_D1_APPLICATION_SAVED_V4.md."""
import hashlib
import json
from pathlib import Path

CONTRACT_SHA256 = 'd6aea07355940995d36c81584cd82a0eabd7a95149a94a0eb456cc3269ab3f74'

def expected_frames(samples):
    if type(samples) is not int or not 0 <= samples <= 70327:
        raise ValueError('An admitted integer sample count from 0 through 70327 is required')
    return 0 if samples == 0 else samples // 160 + 1

def verify_binding(campaign, mode):
    if mode != 'chunk52':
        raise ValueError('This endpoint binding is qualified for the selected Chunk52 check only')
    campaign = Path(campaign)
    raw = Path(__file__).with_name('D1_ENDPOINT_CONTRACT_V2.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise RuntimeError('Changed endpoint contract')
    c = json.loads(raw)
    for name, pin in c['pins'].items():
        path = campaign/name
        with path.open('rb') as f:digest = hashlib.file_digest(f, 'sha256').hexdigest()
        if digest != pin['sha256'] or ('bytes' in pin and path.stat().st_size != pin['bytes']):
            raise RuntimeError('Changed endpoint build input: '+name)
    manifest = json.loads((campaign/'scheduler-native-v1/bundle.tar.json').read_bytes())
    entries = {x['name']:x for x in manifest['files']}
    prefix = 'scheduler-native-v1/inputs/'
    for name, pin in c['pins'].items():
        if name.startswith(prefix):
            row = entries[name[len(prefix):]]
            if row['sha256'] != pin['sha256']:
                raise RuntimeError('Source/object bundle mismatch')
    build = json.loads((campaign/'d1-lru-build-v1/BUILD_RESULT.json').read_bytes())
    admission = json.loads((campaign/'d1-lru-build-v1/BUILD_ADMISSION.json').read_bytes())
    if admission['files']['build_d1_lru_v1.py'] != c['pins']['d1-lru-build-v1/build_d1_lru_v1.py']['sha256']:
        raise RuntimeError('Unbound build source')
    link = next(x for x in build['commands'] if x['name'] == 'link-asr')
    for name in ['objects/diar/diar_pipeline.cpp.o', 'objects/features/fe.cpp.o']:
        if str(campaign/prefix/name) not in link['argv']:
            raise RuntimeError('Endpoint object absent from selected link')
    selected = campaign/c['retained_run']/'nemo-arm64/lib/libnemo_speech_asr.so'
    with selected.open('rb') as f: selected_sha = hashlib.file_digest(f, 'sha256').hexdigest()
    if link['returncode'] != 0 or build['library']['sha256'] != selected_sha:
        raise RuntimeError('Selected runtime differs from recorded successful link')
    # Exact header slices are bound to the Q8 asset, which the native factory hashes in full.
    with (campaign/c['retained_run']/'D1.gguf').open('rb') as f:
        for pin in c['model_metadata'].values():
            expected = bytes.fromhex(pin['hex']);f.seek(pin['offset'])
            if f.read(len(expected)) != expected:raise RuntimeError('Changed frontend metadata')
    import d1_modes_v1 as modes
    model = next(x for x in modes.select(mode)['assets'] if x['name']=='D1.gguf')
    if model['sha256'] != c['model_sha256']:raise RuntimeError('Wrong selected weights')
    return dict(contract_sha256=CONTRACT_SHA256, mode=mode, source_object_link_verified=True,
        selected_library_sha256=selected_sha, frontend_hop_samples=160, output_subsampling_factor=1,
        empty_frames=0, nonempty_formula=c['nonempty_formula'], native_empty_input_tested=False,
        independent_rebuild=False)
