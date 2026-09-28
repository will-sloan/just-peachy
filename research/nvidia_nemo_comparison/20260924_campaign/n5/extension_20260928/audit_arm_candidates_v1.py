"""Audit cached ARM build configuration and GGUF metadata, without execution. README_ARM_CANDIDATES_V1.md."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'n4'))
from common import bind,freeze,load,verify
from metric_process import pin
from window_guard import window


def gguf_header(path):
    """Read bounded GGUF v3 metadata/tensor descriptors; never load tensors."""
    with path.open('rb') as f:
        def unpack(fmt):
            n=struct.calcsize(fmt);data=f.read(n)
            if len(data)!=n:raise ValueError('Truncated GGUF header')
            return struct.unpack(fmt,data)[0]
        def string():
            n=unpack('<Q')
            if n>1024*1024:raise ValueError('Unbounded metadata string')
            value=f.read(n)
            if len(value)!=n:raise ValueError('Truncated string')
            return value.decode('utf-8')
        def value(kind,depth=0):
            formats={0:'<B',1:'<b',2:'<H',3:'<h',4:'<I',5:'<i',6:'<f',7:'<?',10:'<Q',11:'<q',12:'<d'}
            if depth>3:raise ValueError('Nested metadata exceeds bound')
            if kind in formats:return unpack(formats[kind])
            if kind==8:return string()
            if kind==9:
                subtype=unpack('<I');count=unpack('<Q')
                if count>1000000:raise ValueError('Unbounded metadata array')
                for _ in range(count):value(subtype,depth+1)
                return dict(array_type=subtype,count=count)
            raise ValueError('Unknown GGUF metadata type')
        if f.read(4)!=b'GGUF' or unpack('<I')!=3:raise ValueError('Only GGUF v3 admitted')
        tensors=unpack('<Q');count=unpack('<Q')
        if tensors>100000 or count>10000:raise ValueError('Unbounded GGUF header')
        metadata={}
        for _ in range(count):
            key=string();item=value(unpack('<I'))
            if key in ('general.architecture','general.name','general.file_type','general.quantization_version'):metadata[key]=item
        types=Counter()
        for _ in range(tensors):
            string();dims=unpack('<I')
            if dims>8:raise ValueError('Unexpected tensor rank')
            for _ in range(dims):unpack('<Q')
            types[unpack('<I')]+=1;unpack('<Q')
        return dict(version=3,tensor_count=tensors,metadata=metadata,
                    tensor_type_counts={str(k):v for k,v in sorted(types.items())},header_bytes_read=f.tell())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    pin();window();local=HERE.parent.parents[4]/'local'
    if args.output.exists() or not args.output.resolve().is_relative_to(local/'n5/research-extension-20260928'):
        raise ValueError('Fresh private extension receipt required')
    native=load(HERE.parent/'NATIVE_BUILD_RECEIPT.json')
    opts=next(r['argv'] for r in native['commands'] if r['name']=='nemo-configure')
    require=['-DGGML_CPU_ARM_ARCH=armv8-a','-DGGML_NATIVE=OFF','-DGGML_CPU_KLEIDIAI=OFF',
             '-DGGML_CUDA=OFF','-DGGML_OPENMP=OFF']
    if not all(s in opts for s in require):raise ValueError('Build baseline changed')
    archive=next(r for r in native['source_archives'] if r['filename'].startswith('ggml-'))
    zpath=local/'assets'/archive['filename'];zb=bind(zpath)
    if zb['sha256']!=archive['sha256']:raise ValueError('Pinned source archive differs')
    extracts=[]
    with zipfile.ZipFile(zpath) as z:
        root=archive['filename'][:-4]
        for relative,patterns in {
            'src/ggml-cpu/CMakeLists.txt':['if (GGML_CPU_ARM_ARCH)','list(APPEND ARCH_FLAGS -march=${GGML_CPU_ARM_ARCH})'],
            'src/ggml-cpu/arch/arm/quants.c':['__ARM_FEATURE_DOTPROD','__ARM_FEATURE_MATMUL_INT8'],
            'src/ggml-cpu/ggml-cpu.c':['__ARM_FEATURE_FP16_VECTOR_ARITHMETIC','__ARM_FEATURE_DOTPROD'],
            'include/ggml.h':['GGML_TYPE_Q8_0','GGML_FTYPE_MOSTLY_Q8_0'],
        }.items():
            raw=z.read(root+'/'+relative);text=raw.decode('utf-8')
            if not all(s in text for s in patterns):raise ValueError('Expected source evidence absent')
            extracts.append(dict(member=relative,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
                matches=[dict(line=i,text=line.strip()) for i,line in enumerate(text.splitlines(),1)
                         if any(s in line for s in patterns)]))
    models=[]
    for label,digest,name in [
        ('D1','08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1','Nemotron-3-Diarization.q8_0.gguf'),
        ('A2','d9a01898d2a611c8764e23a1c2f45e70bbd5a425dc4de93692ac951dd603812d','nemotron-speech-streaming-en-0.6b.q8_0.gguf'),
        ('A3','3fc991d3badad7277c11030a7519832cddaf2057aafed6d4b25147e953a070b1','nemotron-3.5-asr-streaming-0.6b.q8_0.gguf')]:
        path=local/'assets/sha256'/digest/name;b=bind(path)
        if b['sha256']!=digest:raise ValueError('Model bytes differ')
        models.append(dict(component=label,binding=b,header=gguf_header(path)))
    result=dict(status='STATIC_CONFIG_AND_GGUF_HEADER_AUDIT_ONLY',utc=datetime.now(timezone.utc).isoformat(),
        code=[bind(HERE/n) for n in ('audit_arm_candidates_v1.py','README_ARM_CANDIDATES_V1.md')],
        build_receipt=bind(HERE.parent/'NATIVE_BUILD_RECEIPT.json'),source_archive=zb,source_evidence=extracts,
        recorded_configure_options=[s for s in opts if s.startswith('-D')],models=models,
        compiled_instruction_disassembly=False,model_execution=False,performance_measured=False,CM5_tested=False,
        limits=['Selected cached artifacts only; not an exhaustive artifact search',
                'Build recipe and pinned source evidence do not prove emitted machine instructions',
                'GGUF precision and size do not determine peak runtime RAM or accuracy',
                'No new build, conversion, download, WSL launch or target access'])
    freeze(args.output,result)
    print(json.dumps(dict(status=result['status'],output=str(args.output),
        models=[dict(component=r['component'],bytes=r['binding']['bytes'],header=r['header']) for r in models]),indent=2))


if __name__=='__main__':main()
