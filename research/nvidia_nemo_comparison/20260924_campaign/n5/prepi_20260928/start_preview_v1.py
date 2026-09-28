"""User-launched saved-file Windows preview. See README_PREVIEW.md."""
import argparse
from dataclasses import replace
import os
from pathlib import Path
import shutil
import signal
import sys
import wave

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'n4'))
from common import load, verify, sha
from metric_process import exact_process,pin

RUNS={'A0':'a0-e0-runtime-v1','A2':'a2-e0-runtime-v1'}


def main():
    pin()
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend',choices=sorted(RUNS),required=True)
    p.add_argument('--check-only',action='store_true')
    p.add_argument('--wav',type=Path)
    args=p.parse_args()
    if os.name!='nt':raise ValueError('Windows engineering preview only')
    local=HERE.parent.parents[4]/'local';base=local/'n5/prepi-20260928'
    review=load(base/(RUNS[args.backend]+'-REVIEW.json'))
    if review['status']!='PASS_PREPI_E0_RUNTIME_WINDOWS_SHADOW_ONLY':raise ValueError('E0 runtime lifecycle not reviewed')
    for b in (review['admission'],review['terminal'],review['source_receipt']):verify(b)
    a=load(review['admission']['path'])
    expected='nemotron_hybrid' if args.backend=='A0' else 'nemotron_600m'
    if a['backend_key']!=expected or a['mode']!='anonymous_conversation':raise ValueError('Backend scope mismatch')
    if load(a['source_receipt']['path'])['schema']!='prepi-e0-runtime-derivative-v1':raise ValueError('Wrong source derivative')
    runtime=next(row for row in a['runtime_configs'] if Path(row['path']).name=='n2_runtime.json')
    if {'titanet_manifest','titanet_manifest_sha256','embedding_namespace'} & set(load(runtime['path'])):
        raise ValueError('Retired E1 fields remain')
    for b in a['code']+a['release_files']+a['assets']+a['runtime_configs']+[a['acceptance']]:verify(b)
    for phase in review['phases']:
        verify(phase['result']);verify(phase['lifetime'])
    if args.wav:
        with wave.open(str(args.wav.resolve(strict=True)),'rb') as wav:
            if (wav.getnchannels(),wav.getframerate(),wav.getsampwidth(),wav.getcomptype())!=(1,16000,2,'NONE'):
                raise ValueError('Choose already-prepared mono16k PCM16 saved audio')
    if args.check_only:
        print('PASS: '+args.backend+'/D1/E0 files and scoped lifecycle evidence verified; no GUI/model/device started.')
        return 0
    worker=load(local/'supervision/worker.json')
    for who in (dict(pid=worker['pid'],create_time=worker['create_time']),
                dict(pid=worker.get('child_pid'),create_time=worker.get('child_create_time'))):
        if who['pid'] and exact_process(who) is not None:raise RuntimeError('Campaign worker active; wait for closure')
    for drive,floor in (('C:/',50),('G:/',75)):
        if shutil.disk_usage(drive).free<floor*1024**3:raise RuntimeError('Free-space reserve unavailable')
    # An OS-held lock permits only one of these two user previews at once.
    sys.path.insert(0,str(HERE.parent.parent/'supervision'))
    from supervisor import lock
    with lock(base/'preview-owner.lock'):
        data=base/('Windows-'+args.backend+'-preview')/'data'
        data.mkdir(parents=True,exist_ok=True)
        for b in a['runtime_configs']:
            target=data/Path(b['path']).name
            if target.exists():
                if sha(target)!=b['sha256']:raise ValueError('Changed preview config preserved for review')
            else:
                with target.open('xb') as f:f.write(Path(b['path']).read_bytes())
        for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
        os.environ['CUDA_VISIBLE_DEVICES']='-1'
        import psutil
        proc=psutil.Process();proc.cpu_affinity([4,14]);proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        source=Path(a['release']);sys.path[:0]=[str(source),str(source/'vendor')]
        from app.controller import Controller
        from app.backends import backend_catalog
        from app.ui import PrototypeUI,prepare_dpi_awareness
        import tkinter as tk
        controller=Controller(data,Path(a['models']),saved_audio_only=True)
        try:
            controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
            selected=next(row['id'] for row in backend_catalog() if row['key']==expected)
            controller.select_backend(selected);controller.commands.join()
            if controller.error:raise RuntimeError(controller.error)
            controller.switch(mode='anonymous_conversation',recipe='balanced',tap='O0');controller.commands.join()
            if controller.error:raise RuntimeError(controller.error)
            prepare_dpi_awareness();root=tk.Tk();ui=PrototypeUI(root,controller,allow_auto_start=False)
            for sig in (signal.SIGINT,signal.SIGTERM):
                signal.signal(sig,lambda signum,frame:root.after(0,ui.close))
            if args.wav:root.after(250,lambda:controller.start_file(str(args.wav.resolve())))
            root.mainloop()
        finally:
            if not controller.closed:
                controller.close();controller.commands.join();controller.worker.join(10)
                if not controller.closed:raise RuntimeError('Application did not close: '+str(controller.error))
    return 0


if __name__=='__main__':raise SystemExit(main())
