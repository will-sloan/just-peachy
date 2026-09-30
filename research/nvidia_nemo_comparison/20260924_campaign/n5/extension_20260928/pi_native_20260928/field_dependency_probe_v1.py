"""Import/link probe without streams/models/windows. README_FIELD_DEPENDENCIES_V1.md."""
import ctypes
import json
import os
from pathlib import Path
import resource
import sys
sys.dont_write_bytecode = True


def main():
    assert sorted(os.sched_getaffinity(0)) == [2,3]
    assert resource.getrlimit(resource.RLIMIT_AS) == (768*1024**2,)*2
    assert resource.getrlimit(resource.RLIMIT_STACK) == (1024**2,)*2
    root=Path(sys.argv[1]); lock=json.loads((root/'DEPENDENCIES.json').read_text())
    # Import APIs only; no InferenceSession, model object, stream or Tk root.
    import numpy, onnxruntime, sherpa_onnx, sounddevice, tkinter
    libraries=[r['path'] for r in lock['entries'] if r['category']=='retained_native' and r['path'].endswith('libnemo_speech_asr_c.so.1')]
    assert len(libraries)==1
    native=ctypes.CDLL(libraries[0],mode=os.RTLD_NOW|os.RTLD_LOCAL)
    assert native is not None
    mapped=sorted({line.split(None,5)[5].strip() for line in Path('/proc/self/maps').read_text().splitlines() if len(line.split(None,5))==6 and line.split(None,5)[5].startswith('/')})
    mapped_elf=[]
    for name in mapped:
        with Path(name).open('rb') as f:
            if f.read(4)==b'\x7fELF': mapped_elf.append(str(Path(name).resolve()))
    pinned={r['resolved'] for r in lock['entries'] if r['kind']=='file'}
    assert set(mapped_elf)<=pinned,sorted(set(mapped_elf)-pinned)
    assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    print(json.dumps(dict(status='IMPORTED_AND_LINKED_WITHOUT_MODEL_OR_CAPTURE',mapped_elf=mapped_elf,
                         versions=dict(numpy=numpy.__version__,onnxruntime=onnxruntime.__version__,sherpa_onnx=sherpa_onnx.__version__,sounddevice=sounddevice.__version__),
                         capture_closed=True,models_loaded=False,Tk_root_created=False,
                         address_space=list(resource.getrlimit(resource.RLIMIT_AS)),stack=list(resource.getrlimit(resource.RLIMIT_STACK)))))


if __name__=='__main__': main()
