"""User-launched Windows A2 engineering preview. See README_D1_ANONYMOUS_PREVIEW_V1.md."""
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
from metric_process import exact_process, pin


def main():
    pin()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true',help='Verify files; no GUI or inference')
    parser.add_argument('--encoder',default='redimnet',choices=['redimnet','none'],help='Paired qualified source: retain E0 or bypass it for anonymous labels')
    parser.add_argument('--mode',default='anonymous_conversation',choices=['anonymous_conversation'])
    parser.add_argument('--wav',type=Path,help='Optional already-prepared mono16k PCM16 O0 WAV; no added gain')
    args=parser.parse_args()
    if os.name!='nt':raise ValueError('Windows-only preview; CM5 validation is separate')
    check=load(HERE/'D1_ANONYMOUS_WINDOWS_CHECK_V1.json')
    if check['status']!='PASS_D1_ANONYMOUS_WINDOWS_PAIRED_LIFECYCLE' or not check['paired_semantic_parity']:raise ValueError('Anonymous derivative not qualified')
    arm='parent' if args.encoder=='redimnet' else 'candidate'
    selected_arm=next(row for row in check['arms'] if row['arm']==arm)
    verify(selected_arm['admission']);verify(selected_arm['result'])
    a=load(selected_arm['admission']['path'])
    if a['mode']!=args.mode or a['backend_key']!='nemotron_600m' or a['arm']!=arm:raise ValueError('Unexpected preview scope')
    if a['application_cpus']!=[4,14] or a['numerical_threads_per_model']!=1:raise ValueError('Qualified CPU configuration differs')
    expected_loads=1 if arm=='parent' else 0
    if selected_arm['model_cache']['speaker_loads']!=expected_loads:raise ValueError('Qualified encoder load differs')
    if arm=='candidate' and selected_arm['embedding_calls']!=0:raise ValueError('Encoder bypass not verified')
    if arm=='parent' and selected_arm['embedding_calls']<=0:raise ValueError('ReDimNet execution not verified')
    for b in a['reference_inputs']+check['reviewer_code']:verify(b)
    for b in a['code']+a['release_files']+a['assets']+a['runtime_configs']+[a['source_receipt'],a['acceptance'],a['upstream_source_receipt'],a['accepted_source_receipt'],a['parent_source_receipt']]:verify(b)
    if load(selected_arm['result']['path'])['status']!='PASS_NEMOTRON_WINDOWS_LIFECYCLE_SMOKE':raise ValueError('Saved lifecycle failed')
    local=HERE.parents[4]/'local'; source=Path(a['release'])
    worker=load(local/'supervision/worker.json')
    for owner in (dict(pid=worker['pid'],create_time=worker['create_time']),
                  dict(pid=worker.get('child_pid'),create_time=worker.get('child_create_time'))):
        if owner['pid'] and exact_process(owner) is not None:raise ValueError('Campaign worker active; wait for it to finish')
    data=local/('Windows Nemotron Stable '+args.encoder+' Preview')/'data'
    if args.wav:
        with wave.open(str(args.wav.resolve(strict=True)),'rb') as w:
            if (w.getnchannels(),w.getframerate(),w.getsampwidth(),w.getcomptype())!=(1,16000,2,'NONE'):
                raise ValueError('Use an already-prepared mono16k PCM16 WAV')
    if args.check_only:
        print('PASS: A2/D1 '+args.encoder+' preview files verified. No GUI, model inference or audio device opened.')
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
    process=psutil.Process(); process.cpu_affinity(a['application_cpus']); process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
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
