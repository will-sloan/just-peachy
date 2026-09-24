"""Write the explicit 422-cell N2 execution plan; never launch it. See README.md."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

from run_campaign import admit

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--local',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    source=args.source.resolve(strict=True);local=args.local.resolve(strict=True)
    destination=args.output.resolve()
    if destination.exists():raise ValueError('Plan output must be new')
    evaluation=local/'evaluation';cwd=HERE.parents[3]
    for name,count in [('AUDIO_ONLY.json',96),('REGRESSION_AUDIO_ONLY.json',8)]:
        manifest=json.loads((evaluation/name).read_text())
        if len(manifest['jobs'])!=count or len({j['job_id'] for j in manifest['jobs']})!=count:
            raise ValueError('Unexpected fixed population '+name)
    def controller(combo,scope,cpu,device):
        out=local/('factorial-v1' if scope=='screen' else 'regressions-v1')/combo
        manifest=evaluation/('AUDIO_ONLY.json' if scope=='screen' else 'REGRESSION_AUDIO_ONLY.json')
        encoder=combo.split('_')[1]
        argv=[sys.executable,'-B',str(HERE/'run_screen.py'),'--source',str(source),'--output',str(out),
              '--manifest',str(manifest),'--combination',combo,'--galleries',
              str(evaluation/'component'/encoder/'RUNTIME_GALLERY_INDEX_SAFE.json'),
              '--cpu',str(cpu),'--device',device,'--profile','low_latency','--stop-on-failure']
        return dict(id=scope+'-'+combo,argv=argv,cwd=str(cwd),cells=96 if scope=='screen' else 8,
                    device=device,result_kind='controller',timeout_seconds=12600 if scope=='screen' else 1800,
                    result=str(out/'RESULT_INDEX.json'),progress=str(out/'PROGRESS.json'))
    gui_out=local/'gui-panel-isolated-v1'
    gui=[sys.executable,'-B',str(HERE/'gui/panel.py'),'--source',str(source),
         '--common-source',str(local.parent/'releases/n1-common-v1/prototype'),
         '--models-root','C:/Users/amiri/JustPeachy/shared/models',
         '--runtime-config',str(local/'runtime/cpu/n2_runtime.json'),
         '--regression-manifest',str(local.parent/'data/REGRESSION_AUDIO_ONLY.json'),
         '--screen-manifest',str(local.parent/'data/BASELINE_SCREEN_AUDIO_ONLY.json')]
    for encoder in ('E0','E1'):
        gui += ['--'+encoder.lower()+'-gallery',str(evaluation/'component'/encoder/'runtime_galleries/gallery_69c1a03b24b0c86e7998.json')]
    gui += ['--output',str(gui_out),'--cpu','4','--timeout-seconds','2400']
    gui_job=dict(id='gui-panel',argv=gui,cwd=str(cwd),cells=6,device='cpu',result_kind='gui',
                 timeout_seconds=2500,result=str(gui_out/'GUI_PANEL_REPORT.json'),progress=str(gui_out/'PROGRESS.json'))
    cpu_jobs=[gui_job]+[controller(combo,scope,4,'cpu') for scope in ('screen','regression') for combo in ('D0_E0','D0_E1')]
    gpu_jobs=[controller(combo,scope,14,'cuda') for scope in ('screen','regression') for combo in ('D1_E0','D1_E1')]
    plan=dict(schema='n2-numerical-coordinator-v1',lanes=[dict(cpu=4,jobs=cpu_jobs),dict(cpu=14,jobs=gpu_jobs)])
    admit(plan)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x',encoding='utf-8') as stream:json.dump(plan,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status='PREPARED_NOT_LAUNCHED',path=str(destination),jobs=9,cells=422,
                         sha256=hashlib.sha256(destination.read_bytes()).hexdigest())))


if __name__=='__main__':main()
