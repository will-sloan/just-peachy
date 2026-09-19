"""Just Peachy PROTO1. See START_PROTOTYPE.md for Windows/CM5 commands."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(key,'1')


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',nargs='?',choices=('gui','file','validate'),default='gui')
    p.add_argument('--data-root',type=Path)
    p.add_argument('--models',type=Path)
    p.add_argument('--wav',type=Path)
    p.add_argument('--mode',default='caption_only',choices=('caption_only','enrolled_names','anonymous_conversation','open_with_names','selected_focus','spatial_assisted','strongly_spatial_assisted'))
    p.add_argument('--recipe',default='fast',choices=('fast','classic','balanced','patient'))
    p.add_argument('--tap',default='O0',choices=('O0','O1'))
    p.add_argument('--result',type=Path)
    p.add_argument('--fullscreen',action='store_true')
    return p


def main():
    args=parser().parse_args()
    from app.paths import default_data_root,default_models_root,pipeline_config,atomic_json
    data=args.data_root or default_data_root();models=args.models or default_models_root()
    if args.command=='validate':
        from edge_speech_pipeline.assets import validate_assets
        from app.pipeline import effective_profile
        config=pipeline_config(data,models);validate_assets(config.assets)
        profile=effective_profile(args.recipe,args.mode,args.tap)
        print(json.dumps({'status':'CONFIGURATION_AND_ASSETS_VALID','profile':profile.profile_id,
            'models':str(models),'microphone_opened':False,'native_inference_executed':False}))
        return 0
    from app.controller import Controller
    controller=Controller(data,models)
    try:
        if args.mode!='caption_only' or args.recipe!='fast' or args.tap!='O0':
            controller.switch(mode=args.mode,recipe=args.recipe,tap=args.tap);controller.commands.join()
            if controller.error:raise RuntimeError(controller.error)
        if args.command=='gui':
            import tkinter as tk
            from app.ui import PrototypeUI,prepare_dpi_awareness
            prepare_dpi_awareness();root=tk.Tk();window=PrototypeUI(root,controller)
            if args.fullscreen:root.attributes('-fullscreen',True)
            if args.wav:root.after(250,lambda:controller.start_file(args.wav))
            root.mainloop()
        else:
            if args.wav is None:raise ValueError('file requires --wav')
            controller.start_file(args.wav);controller.commands.join()
            if controller.error:raise RuntimeError(controller.error)
            while controller.state in ('RUNNING','STARTING','STOPPING'):
                time.sleep(.5)
            result=controller.snapshot()
            if args.result:atomic_json(args.result,result)
            print(json.dumps({'status':result['state'],'rows':len(result['rows']),'error':result['error'],
                              'result':str(args.result),'metrics':result['metrics'].get('model_cache')}))
            return 1 if result['error'] else 0
    finally:
        if not controller.closed:
            controller.close();controller.commands.join();controller.worker.join(10)
            if not controller.closed:raise RuntimeError('Application did not close cleanly: '+str(controller.error))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except FileExistsError as exc:
        print('Application/update already owns this personal data directory. Close it first; see README for stale-lock recovery.',file=sys.stderr)
        raise SystemExit(2)
    except Exception as exc:
        print(type(exc).__name__+': '+str(exc),file=sys.stderr);raise SystemExit(1)
