"""Native bounded GUI/auto-start/Stop check; see README_CM5_CHECKS.md."""
import argparse
import json
import os
from pathlib import Path
import sys
import tkinter as tk
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--release', type=Path, required=True)
parser.add_argument('--data-root', type=Path, required=True)
parser.add_argument('--models', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path[:0] = [str(args.release), str(args.release/'vendor')]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(key,'1')
from app.controller import Controller
from app.ui import PrototypeUI, prepare_dpi_awareness

started=time.monotonic(); records={}
c=Controller(args.data_root,args.models)
prepare_dpi_awareness();root=tk.Tk();ui=PrototypeUI(root,c);root.attributes('-fullscreen',True)

def capture():
    snap=c.snapshot()
    records['during']={k:snap[k] for k in ('state','error','motion','metrics','spatial_view')}
    records['page_before_settings']=ui.page
    ui.snapshot=snap;ui.show_motion()

def stop():
    ui.snapshot=c.snapshot();ui.home();ui.toggle_listening()
    root.after(500, finish)

def finish():
    if c.state in ('STOPPING','RUNNING','STARTING') and time.monotonic()-started<100:
        root.after(500,finish);return
    snap=c.snapshot()
    records['after']={k:snap[k] for k in ('state','error','motion','metrics')}
    records['elapsed_sec']=time.monotonic()-started
    records['passed']=records.get('during',{}).get('state')=='RUNNING' and snap['state']=='STOPPED' and not snap['error']
    args.output.write_text(json.dumps(records,indent=2)+'\n')
    ui.close()

root.after(18000,capture)
root.after(35000,stop)
try:root.mainloop()
finally:
    if not c.closed:
        c.close();c.commands.join();c.worker.join(10)
print(json.dumps({'passed':records.get('passed',False),'elapsed_sec':records.get('elapsed_sec')}))
raise SystemExit(0 if records.get('passed') else 1)
