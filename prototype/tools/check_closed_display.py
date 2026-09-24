"""Two bounded existing CMU/native cases; no private gallery/capture. See README_ROSTER.md."""
import argparse,hashlib,json,os,shutil,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(k,'1')
from app.controller import Controller
from app.paths import default_models_root,atomic_json,sha256
from app.caption_display import IdentityLabels
from app.sessions import records
from prototype.tests.check_native_people import ROUTE

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixture',type=Path,default=ROOT.parent/'Resumes/.uiiter2_04/native_v2')
    p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    if args.output.exists():p.error('Use a fresh private output')
    previous=json.loads((args.fixture/'ROSTER_NATIVE_CHECK.json').read_text())
    assert previous['status']=='PASS' and previous['reference_query_hashes_disjoint']
    # The prior receipt qualifies exactly two disclosed public-corpus fixture people.
    rows=[json.loads(f.read_text()) for f in (args.fixture/'people').glob('*/person.json')]
    assert len(rows)==2 and {r['name'] for r in rows}=={'CMU fixture A','CMU fixture B'}
    ids={r['name'][-1]:r['id'] for r in rows}
    args.output.mkdir(parents=True);shutil.copytree(args.fixture/'people',args.output/'people')
    before={str(f.relative_to(args.output)):sha256(f) for f in (args.output/'people').rglob('*') if f.is_file()}
    c=Controller(args.output,default_models_root());c.route=lambda:dict(ROUTE)
    result=dict(status='RUNNING',scope='Two existing12s public CMU file cases; real ASR/segmentation/ReDimNet, no microphone, playback or enrollment',cases=[])
    started=time.perf_counter()
    def command():
        c.commands.join()
        if c.error:raise RuntimeError(c.error)
    try:
        for mode,selected in [('selected_closed',[ids['A'],ids['B']]),('selected_focus',[ids['A']])]:
            c.switch(mode=mode,recipe='balanced',tap='O0',selected_ids=selected,strict=False);command()
            c.start_file(args.fixture/'B_12s.wav');command();deadline=time.perf_counter()+40
            labels=IdentityLabels();checked=assumed=0
            while c.state in ('STARTING','RUNNING','STOPPING'):
                if time.perf_counter()>deadline:raise TimeoutError('Native source did not complete')
                snap=c.snapshot()
                for r in snap['rows']:
                    if not r['raw_asr_text'].strip():continue
                    shown=labels.label(r,mode,time.perf_counter());checked+=1
                    if mode=='selected_closed':
                        assert r['display_profile_id'] in selected,(r['identity_assignment'],r['identity_status'])
                        assert not shown.startswith(('Unknown','•••')),(r['identity_assignment'],shown)
                        assumed+=r.get('closed_display_assignment') is not None
                time.sleep(.08)
            command();assert c.state=='STOPPED' and c.engine.state=='COMPLETED'
            meta=c.session_store.metadata(c.conversation_id);epoch=meta['epochs'][-1]
            folder=c.session_store.epoch(c.conversation_id,epoch);events=list(records(folder/'events.jsonl'))
            displays=[e['payload'] for e in events if e['kind']=='s6d_display']
            parts=[s for row in displays for s in row.get('segments') or [row] if s.get('raw_text',row.get('text','')).strip()]
            fallbacks=[s['closed_display_assignment'] for s in parts if s.get('closed_display_assignment')]
            for s in parts:
                if mode=='selected_closed':
                    assert s.get('closed_display_assignment',{}).get('profile_id') in selected or (s.get('naming_state')=='confirmed' and s.get('known_profile_id') in selected)
                    if s.get('closed_display_assignment'):assert s['closed_display_assignment']['acoustic_confidence'] is None
                else:assert not s.get('closed_display_assignment') and not s.get('known_profile_id')
            assert checked and parts
            if mode=='selected_closed':assert fallbacks and assumed,'Missing initial-unowned evidence coverage'
            result['cases'].append(dict(mode=mode,state=c.engine.state,display_observations=checked,caption_updates=len(displays),
                segment_updates=len(parts),display_assumptions=len(fallbacks),fallback_bases=dict(Counter(x['basis'] for x in fallbacks)),
                selected_name_missing=0 if mode=='selected_closed' else None,open_outsider_remains_unnamed=mode=='selected_focus',
                epoch_path=str(folder)))
            if mode=='selected_closed':
                # Actual native rows, actual480x800 Tk, no fixture speech played.
                import tkinter as tk
                from app.ui import PrototypeUI,prepare_dpi_awareness
                from prototype.tests.native_ui_check import capture
                prepare_dpi_awareness();root=tk.Tk();ui=PrototypeUI(root,c);root.geometry('+30+30');root.attributes('-topmost',True)
                ui.snapshot=c.snapshot();ui._render_rows(ui.snapshot['rows']);root.update()
                capture(root,args.output/'closed_native.png');result['client']=ui.measure_client()
                # Destroy only this test view; keep the same controller/models for the open comparison.
                root.destroy()
        assert before=={str(f.relative_to(args.output)):sha256(f) for f in (args.output/'people').rglob('*') if f.is_file()}
        result.update(status='PASS',references_unchanged=True,model_cache=dict(asr=c.models.asr_loads,speaker=c.models.speaker_loads),
            fixture_sha256=sha256(args.fixture/'ROSTER_NATIVE_CHECK.json'),input_sha256=sha256(args.fixture/'B_12s.wav'))
    except Exception as exc:result.update(status='FAIL',error=repr(exc));raise
    finally:
        c.close();c.commands.join();c.worker.join(10)
        result.update(closed=c.closed,elapsed_sec=time.perf_counter()-started,
            source_bindings={str(f.relative_to(ROOT)):sha256(f) for folder in ('app','vendor','config') for f in (ROOT/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts},
            tool_sha256=sha256(__file__))
        atomic_json(args.output/'CLOSED_DISPLAY_CHECK.json',result)
        print(json.dumps({k:result.get(k) for k in ('status','error','cases','closed','elapsed_sec')}))

if __name__=='__main__':main()
