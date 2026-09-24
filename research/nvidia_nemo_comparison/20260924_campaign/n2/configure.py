"""Write explicit N2 asset bindings to an isolated data root. See README.md."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def configure(data,local,device='cpu'):
    data=Path(data).resolve();local=Path(local).resolve()
    original=(Path.home()/'JustPeachy/data').resolve()
    if data==original or original in data.parents:raise ValueError('Use a separate research data root')
    model=local.parent/'assets/sha256/08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1/Nemotron-3-Diarization.q8_0.gguf'
    if device not in ('cpu','cuda'):raise ValueError('Explicit CPU or CUDA device required')
    receipt_name='NATIVE_BUILD_RECEIPT.json' if device=='cpu' else 'CUDA_BUILD_RECEIPT.json'
    manifest=local/'titanet/export/titanet_manifest.json'
    build=json.loads((Path(__file__).resolve().parent/'diarization'/receipt_name).read_text())
    if build.get('status')!='ACTUALLY_BUILT' or bool(build.get('gpu'))!=(device=='cuda'):
        raise ValueError('Requested native device has no successful bound build')
    bridge=next(row for row in build['runtime_files'] if Path(row['path']).name=='nemo_speech_asr_c.dll')
    dll=Path(bridge['path'])
    runtime_files=[]
    for row in build['runtime_files']:
        path=dll.parent/Path(row['path']).name
        if sha(path)!=row['sha256']:raise ValueError('Native dependency differs: '+str(path))
        runtime_files.append(dict(path=str(path),sha256=row['sha256'],bytes=path.stat().st_size))
    m=json.loads(manifest.read_text())
    namespace=dict(model_sha256=m['source_model_sha256'],preprocessing=m['preprocessing_version'],
        dimension=m['dimension'],normalization='L2',minimum_samples=m['minimum_samples'],
        onnx_sha256=m['onnx']['sha256'],frontend_sha256=m['frontend']['sha256'])
    if sha(model)!='08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1':raise ValueError('D1 model changed')
    document=dict(schema='just-peachy.n2.runtime.v1',nemotron_model=str(model),nemotron_library=str(dll),
        nemotron_library_sha256=sha(dll),native_runtime_files=runtime_files,
        native_device=dict(kind=device,gpu_index=-1 if device=='cpu' else 0),
        titanet_manifest=str(manifest),titanet_manifest_sha256=sha(manifest),embedding_namespace=namespace,
        streaming_profile='low_latency',research_saved_audio_only=True)
    data.mkdir(parents=True,exist_ok=True)
    output=data/'n2_runtime.json'
    if output.exists() and json.loads(output.read_text())!=document:raise ValueError('Existing runtime binding differs; use a new data root')
    output.write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',required=True,type=Path)
    parser.add_argument('--local',type=Path,default=Path('G:/Just_Peachy_N1/20260924_campaign/local/n2'))
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    args=parser.parse_args();path=configure(args.data,args.local,args.device)
    print(json.dumps(dict(status='CONFIGURED',runtime_binding=str(path),
        launch='"'+sys.executable+'" -B prototype\\main.py gui --data-root "'+str(args.data)+'"'),indent=2))
