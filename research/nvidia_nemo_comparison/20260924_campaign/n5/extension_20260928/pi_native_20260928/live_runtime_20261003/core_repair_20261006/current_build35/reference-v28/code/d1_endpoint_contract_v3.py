import hashlib
import json
import base64
from pathlib import Path

def verify_streaming(campaign, mode):
    if mode != 'streaming':
        raise ValueError('This endpoint binding is qualified for the selected Streaming check only')
    campaign = Path(campaign)
    container=json.loads(Path(__file__).with_name('D1_ENDPOINT_CONTRACT_V3.json').read_bytes())
    if set(container)!={'streaming','chunk52','delayed'}:raise ValueError('Exact endpoint contract set')
    raw=base64.b64decode(container[mode],validate=True)
    if hashlib.sha256(raw).hexdigest() != '34f7971469307436ecb7ffbda3785ed6a4c79720abab777c95ad91fc30fc776c':
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
    return dict(contract_sha256='34f7971469307436ecb7ffbda3785ed6a4c79720abab777c95ad91fc30fc776c', mode=mode, source_object_link_verified=True,
        selected_library_sha256=selected_sha, frontend_hop_samples=160, output_subsampling_factor=1,
        empty_frames=0, nonempty_formula=c['nonempty_formula'], native_empty_input_tested=False,
        independent_rebuild=False)

def verify_chunk52(campaign, mode):
    if mode != 'chunk52':
        raise ValueError('This endpoint binding is qualified for the selected Chunk52 check only')
    campaign = Path(campaign)
    container=json.loads(Path(__file__).with_name('D1_ENDPOINT_CONTRACT_V3.json').read_bytes())
    if set(container)!={'streaming','chunk52','delayed'}:raise ValueError('Exact endpoint contract set')
    raw=base64.b64decode(container[mode],validate=True)
    if hashlib.sha256(raw).hexdigest() != 'd6aea07355940995d36c81584cd82a0eabd7a95149a94a0eb456cc3269ab3f74':
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
    return dict(contract_sha256='d6aea07355940995d36c81584cd82a0eabd7a95149a94a0eb456cc3269ab3f74', mode=mode, source_object_link_verified=True,
        selected_library_sha256=selected_sha, frontend_hop_samples=160, output_subsampling_factor=1,
        empty_frames=0, nonempty_formula=c['nonempty_formula'], native_empty_input_tested=False,
        independent_rebuild=False)

def verify_delayed(campaign, mode):
    if mode != 'delayed':
        raise ValueError('This endpoint binding is qualified for the selected Delayed check only')
    campaign = Path(campaign)
    container=json.loads(Path(__file__).with_name('D1_ENDPOINT_CONTRACT_V3.json').read_bytes())
    if set(container)!={'streaming','chunk52','delayed'}:raise ValueError('Exact endpoint contract set')
    raw=base64.b64decode(container[mode],validate=True)
    if hashlib.sha256(raw).hexdigest() != 'd6b4c142c21c32407f0f7bf7ace554d9f33fcfe0ffbf843ca40a85a85637aaea':
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
    build = json.loads((campaign/'d1-lru1-build-v1/BUILD_RESULT.json').read_bytes())
    admission = json.loads((campaign/'d1-lru1-build-v1/BUILD_ADMISSION.json').read_bytes())
    if admission['files']['build_d1_lru1_v1.py'] != c['pins']['d1-lru1-build-v1/build_d1_lru1_v1.py']['sha256']:
        raise RuntimeError('Unbound build source')
    link = next(x for x in build['commands'] if x['name'] == 'link-asr')
    for name in ['objects/diar/diar_pipeline.cpp.o', 'objects/features/fe.cpp.o']:
        if str(campaign/prefix/name) not in link['argv']:
            raise RuntimeError('Endpoint object absent from selected link')
    if build['patch']['old_graph_cache_capacity'] != 8 or build['patch']['new_graph_cache_capacity'] != 1:
        raise RuntimeError('Wrong delayed graph-cache build')
    if build['patch']['before_sha256'] != c['pins']['d1-lru-build-v1/sortformer_model.cpp']['sha256'] or build['patch']['after_sha256'] != c['pins']['d1-lru1-build-v1/sortformer_model.cpp']['sha256']:
        raise RuntimeError('Changed delayed patch lineage')
    compile_step = next(x for x in build['commands'] if x['name'] == 'compile-sortformer')
    if compile_step['returncode'] != 0 or str(campaign/'d1-lru1-build-v1/sortformer_model.cpp') not in compile_step['argv']:
        raise RuntimeError('Missing successful LRU1 compile record')
    for name in ['d1-lru1-build-v1/output/sortformer_model.cpp.o', 'd1-metadata2-build-v2/output/runtime.a']:
        if str(campaign/name) not in link['argv']:
            raise RuntimeError('Delayed object/runtime absent from selected link')
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
    return dict(contract_sha256='d6b4c142c21c32407f0f7bf7ace554d9f33fcfe0ffbf843ca40a85a85637aaea', mode=mode, source_object_link_verified=True,
        selected_library_sha256=selected_sha, frontend_hop_samples=160, output_subsampling_factor=1,
        empty_frames=0, nonempty_formula=c['nonempty_formula'], native_empty_input_tested=False,
        independent_rebuild=False)

def verify_binding(campaign, mode):
    callbacks={'streaming':verify_streaming,'chunk52':verify_chunk52,'delayed':verify_delayed}
    if mode not in callbacks:raise ValueError('Exact supported mode')
    return callbacks[mode](campaign,mode)
