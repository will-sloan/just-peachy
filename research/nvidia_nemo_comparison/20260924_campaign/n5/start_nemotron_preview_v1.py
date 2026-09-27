"""User-launched Windows A2 engineering preview. See README_NEMOTRON_WINDOWS_PREVIEW_V1.md."""
import argparse
import os
from pathlib import Path
from dataclasses import replace
import signal
import shutil
import sys
import wave

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'n4'))
from common import load, verify
from metric_process import exact_process


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true',help='Verify files; no GUI or inference')
    parser.add_argument('--mode',default='caption_only',choices=['caption_only','anonymous_conversation'])
    parser.add_argument('--wav',type=Path,help='Optional already-prepared mono16k PCM16 O0 WAV; no added gain')
    args=parser.parse_args()
    if os.name!='nt':raise ValueError('Windows-only preview; CM5 validation is separate')
    suffix='CAPTION' if args.mode=='caption_only' else 'ANONYMOUS'
    check=load(HERE/('NEMOTRON_WINDOWS_'+suffix+'_CHECK_V1.json'))
    if check['status']!='PASS_NEMOTRON_WINDOWS_'+suffix+'_LIFECYCLE_SMOKE':raise ValueError('Preview mode not qualified')
    verify(check['private_admission']); verify(check['private_result'])
    a=load(check['private_admission']['path'])
    if a['mode']!=args.mode or a['backend_key']!='nemotron_600m':raise ValueError('Unexpected preview scope')
    for b in a['code']+a['release_files']+a['assets']+a['runtime_configs']+[a['source_receipt'],a['acceptance']]:verify(b)
    if load(check['private_result']['path'])['status']!='PASS_NEMOTRON_WINDOWS_LIFECYCLE_SMOKE':raise ValueError('Saved lifecycle failed')
    local=HERE.parents[4]/'local'; source=Path(a['release'])
    worker=load(local/'supervision/worker.json')
    for owner in (dict(pid=worker['pid'],create_time=worker['create_time']),
                  dict(pid=worker.get('child_pid'),create_time=worker.get('child_create_time'))):
        if owner['pid'] and exact_process(owner) is not None:raise ValueError('Campaign worker active; wait for it to finish')
    data=local/'Windows Nemotron Preview/data'
    if args.wav:
        with wave.open(str(args.wav.resolve(strict=True)),'rb') as w:
            if (w.getnchannels(),w.getframerate(),w.getsampwidth(),w.getcomptype())!=(1,16000,2,'NONE'):
                raise ValueError('Use an already-prepared mono16k PCM16 WAV')
    if args.check_only:
        print('PASS: A2 Windows '+args.mode+' preview files verified. No GUI, model inference or audio device opened.')
        return 0
    for drive,gib in [('C:/',50),('G:/',75)]:
        if shutil.disk_usage(drive).free<gib*1024**3:raise ValueError('Campaign drive reserve unavailable')
    if (data/'runtime.lock').exists():raise ValueError('Preview already owns this data directory; close it first')
    data.mkdir(parents=True,exist_ok=True)
    for b in a['runtime_configs']:
        target=data/Path(b['path']).name
        if target.exists():
            from common import sha
            if sha(target)!=b['sha256']:raise ValueError('Preview runtime config changed; preserved for review')
        else:
            with target.open('xb') as dest:dest.write(Path(b['path']).read_bytes())
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='-1'
    import psutil
    process=psutil.Process(); process.cpu_affinity([4]); process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    sys.path[:0]=[str(source),str(source/'vendor')]
    from app.controller import Controller
    from app.ui import PrototypeUI,prepare_dpi_awareness
    import tkinter as tk
    controller=Controller(data,Path(a['models']),saved_audio_only=True)
    try:
        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
        controller.select_backend(check['backend_id']); controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        controller.switch(mode=args.mode,recipe='fast' if args.mode=='caption_only' else 'balanced',tap='O0')
        controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        prepare_dpi_awareness(); root=tk.Tk(); ui=PrototypeUI(root,controller,allow_auto_start=False)
        for sig in (signal.SIGINT,signal.SIGTERM):
            signal.signal(sig,lambda signum,frame:root.after(0,ui.close))
        if args.wav:root.after(250,lambda:controller.start_file(str(args.wav.resolve())))
        root.mainloop()
    finally:
        if not controller.closed:
            controller.close();controller.commands.join();controller.worker.join(10)
            if not controller.closed:raise RuntimeError('Application did not close cleanly: '+str(controller.error))
    return 0


if __name__=='__main__':raise SystemExit(main())
