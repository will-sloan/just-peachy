"""Prepare immutable deterministic-input derivatives; README_STABLE_ASR_CHUNKS_V1.md."""
import argparse
import difflib
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'n4'))
from common import bind, freeze, load, verify
from metric_process import pin


def patch(raw):
    text=raw.decode('utf-8'); newline='\r\n' if '\r\n' in text else '\n'
    text=text.replace('\r\n','\n')
    anchor='                audio = self._journal.read(cursor, read_size)\n'
    replacement='''                # Journal reads return whatever has arrived, not necessarily
                # read_size samples. Gather the configured quantum so native
                # push/observation boundaries do not depend on CPU scheduling.
                parts = []
                gathered = 0
                while gathered < read_size:
                    if self._state == 'FAILED':
                        raise RuntimeError('N3 ASR stops after session failure')
                    block = self._journal.read(cursor+gathered, read_size-gathered)
                    if block.size:
                        parts.append(block)
                        gathered += int(block.size)
                    elif self._journal.finished and cursor+gathered >= self._journal.committed_samples:
                        break
                audio = np.concatenate(parts) if parts else np.empty(0,dtype=np.float32)
'''
    if text.count(anchor)!=1:raise ValueError('Expected exactly one reviewed ASR read site')
    text=text.replace(anchor,replacement)
    compile(text,'app/n3_pipeline.py','exec')
    return text.replace('\n',newline).encode('utf-8')


def prepare(parent_receipt,output):
    pin(); parent_binding=bind(parent_receipt); parent=load(parent_receipt)
    root=Path(parent.get('prototype') or str(parent_receipt.parent/'prototype'))
    if output.exists():raise FileExistsError('Fresh immutable output required')
    payloads={}
    for relative,row in parent['files'].items():
        path=(root/relative).resolve()
        if not path.is_relative_to(root.resolve()):raise ValueError('Source escapes parent')
        verify(dict(path=str(path),**row));payloads[relative]=path.read_bytes()
    original=payloads['app/n3_pipeline.py'];payloads['app/n3_pipeline.py']=patch(original)
    payloads['README_STABLE_ASR_CHUNKS_V1.md']=(HERE/'README_STABLE_ASR_CHUNKS_V1.md').read_bytes()
    payloads['tests/test_stable_asr_chunks_v1.py']=(HERE/'test_stable_asr_chunks_v1.py').read_bytes()
    output.mkdir(); files={}
    for relative,raw in payloads.items():
        path=output/'prototype'/relative;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
        b=bind(path);files[relative]={k:b[k] for k in ('bytes','sha256')}
    diff=''.join(difflib.unified_diff(original.decode().splitlines(True),payloads['app/n3_pipeline.py'].decode().splitlines(True),fromfile='parent/app/n3_pipeline.py',tofile='derivative/app/n3_pipeline.py'))
    (output/'CHANGES.patch').write_text(diff,encoding='utf-8')
    freeze(output/'DERIVATIVE.json',dict(schema='stable-asr-chunks-derivative-v1',status='PREPARED_NOT_RELEASE_ACCEPTED',
        parent_source_receipt=parent_binding,prototype=str(output/'prototype'),files=files,
        changed_code=['app/n3_pipeline.py'],builder=bind(__file__),
        scope='Gather configured journal read quantum, preserving all audio and EOF tail. No model, decoder, diarizer, timeout, or timestamp tolerance change.'))
    print(dict(status='PREPARED_NOT_RELEASE_ACCEPTED',output=str(output),files=len(files)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent-receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();prepare(args.parent_receipt,args.output)
