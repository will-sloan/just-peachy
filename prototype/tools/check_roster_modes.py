"""Bounded real-model roster checks on existing disjoint CMU files. See README_ROSTER.md."""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(key,'1')
import numpy as np
import soundfile as sf
from app.controller import Controller
from app.paths import default_models_root,atomic_json,sha256
from app.sessions import records
from prototype.tests.check_native_people import ROUTE,join_files,quality,binding


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources',type=Path,default=Path(r'G:\Just_Peachy_S6C\20260910T123540Z\source_inventory\v2\decoded_16k'))
    p.add_argument('--prior-fixture',type=Path,default=Path(r'G:\Just_Peachy_PROTO1\tests\personal_fixture\20260919T020017_461049Z'))
    p.add_argument('--data-root',type=Path,required=True);args=p.parse_args()
    if args.data_root.exists():raise ValueError('Use a fresh private output directory')
    started=time.perf_counter();c=Controller(args.data_root,default_models_root());c.route=lambda:dict(ROUTE)
    result=dict(status='RUNNING',scope='Offline real models and explicit dry_test_fixture enrollment; no microphone, XVF or audible output',jobs=[])
    bound={}
    def check_command():
        c.commands.join()
        if c.error:raise RuntimeError(c.error)
    try:
        # Recreate only two small fixture references using the unchanged real quality gate.
        refs=dict(A=sorted(args.sources.glob('CMU_awb_*.wav'))[:13],B=sorted(args.sources.glob('CMU_bdl_*.wav'))[6:19])
        prior=json.loads((args.prior_fixture/'TEST_RECEIPT.json').read_text())
        query_hashes={r['sha256'] for key in ('fresh_same_person_query','wrong_person_query') for r in prior['source_inventory'][key]}
        people={};speakers=c.models.enrollment_models(c.config)
        result['reference_quality']={}
        for name,paths in refs.items():
            if len(paths)<13:raise ValueError('Existing disjoint CMU reference pool missing')
            provenance=[binding(path) for path in paths];assert not query_hashes & {r['sha256'] for r in provenance}
            q,v=quality(join_files(paths),speakers,c.config,provenance,'task04_'+name)
            if not q['can_save']:raise RuntimeError('Frozen enrollment gate rejected fixture '+name)
            people[name]=c.store.save('CMU fixture '+name,v,q,ROUTE)['id']
            result['reference_quality'][name]={k:v for k,v in q.items() if k not in ('source_provenance','accepted_intervals')}
            bound[name]=provenance
        queries={}
        for name,source in (('A','fresh_same_person_query.wav'),('B','wrong_person_query.wav')):
            original=args.prior_fixture/source;x,rate=sf.read(original,dtype='float32')
            assert rate==16000 and x.ndim==1 and len(x)>=192000
            destination=args.data_root/(name+'_12s.wav');sf.write(destination,x[:192000],16000,subtype='PCM_16');queries[name]=destination
            assert sf.read(destination,dtype='float32')[0].tobytes()==x[:192000].tobytes(),'Prepared PCM16 source was quantized again'
            bound['query_'+name]=dict(source=binding(original),start_sample=0,end_sample=192000,prepared=binding(destination),gain='none')
        before={str(p.relative_to(c.store.root)):sha256(p) for p in c.store.root.rglob('*') if p.is_file()}
        jobs=[('selected_open_known','selected_focus','A'),('selected_open_outsider','selected_focus','B'),
              ('all_gallery_other','enrolled_names','B'),('closed_outsider','selected_closed','B'),
              ('spatial_selected_known','spatial_selected','A'),('strong_spatial_selected_known','strongly_spatial_selected','A')]
        for name,mode,person in jobs:
            t=time.perf_counter();c.switch(mode=mode,recipe='balanced',tap='O0',selected_ids=[people['A']],strict=False);check_command()
            c.start_file(queries[person]);check_command();deadline=time.perf_counter()+60
            while c.state in ('STARTING','RUNNING','STOPPING') and time.perf_counter()<deadline:time.sleep(.1)
            if c.state!='STOPPED' or c.error:raise RuntimeError(c.error or 'Bounded fixture did not finish')
            engine=c.engine;meta=c.session_store.metadata(c.conversation_id);epoch=meta['epochs'][-1]
            folder=c.session_store.epoch(c.conversation_id,epoch);events=list(records(folder/'events.jsonl'))
            decisions=[r['payload']['decision'] for r in events if r['kind']=='speaker_decision']
            details=[d['identity'] for d in decisions];shown=[r['payload'] for r in events if r['kind']=='s6d_display']
            named={s['known_profile_id'] for r in shown for s in r.get('segments',[]) if s.get('naming_state')=='confirmed' and s.get('known_profile_id')}
            assumed=sum(s.get('prototype_assignment') in ('forced','assumed_unlinked') for r in shown for s in r.get('segments',[]))
            forced=sum(d.get('forced') is True for d in details)
            gallery=engine._research_gallery;expected=[people['A']] if mode!='enrolled_names' else sorted(people.values())
            assert sorted(gallery.ids)==sorted(expected) and gallery.query_count>0
            assert engine.state=='COMPLETED' and shown
            if name=='selected_open_outsider':assert not named and not any(d.get('naming_state')=='confirmed' for d in details),'Outsider received an open-set name'
            if name=='closed_outsider':assert forced>0 and assumed>0 and people['A'] in named,'Closed assumption did not reach native captions'
            if name=='selected_open_known':assert people['A'] in named,'Known fixture did not reach confirmed native captions'
            if name=='all_gallery_other':assert people['B'] in named,'All-gallery reference did not identify disjoint fixture B'
            resources=list(records(folder/'resources.jsonl'))
            job=dict(name=name,mode=mode,state=engine.state,elapsed_sec=time.perf_counter()-t,gallery_ids=gallery.ids,
                actual_gallery_score_calls=gallery.query_count,decision_counts=dict(Counter(d.get('assignment') for d in details)),
                confirmed_caption_ids=sorted(named),assumed_caption_updates=assumed,forced_decisions=forced,
                prototype_resolver=type(engine.prototype_identity).__name__,tracker_mode=engine._research_profile.tracker.mode,
                effective_configuration=c.mode_configuration(engine._research_profile,gallery),epoch_path=str(folder),
                max_sampled_rss_bytes=max(r['process_rss_bytes'] for r in resources),cpu_total_sec=resources[-1]['cpu_total_sec'])
            result['jobs'].append(job);atomic_json(args.data_root/'ROSTER_NATIVE_CHECK.json',result)
            print(json.dumps({k:job[k] for k in ('name','elapsed_sec','actual_gallery_score_calls','decision_counts','assumed_caption_updates')}),flush=True)
        after={str(p.relative_to(c.store.root)):sha256(p) for p in c.store.root.rglob('*') if p.is_file()}
        assert before==after,'Inference altered personal fixture references'
        result.update(profile_files_unchanged=True,reference_query_hashes_disjoint=True,source_inventory=bound,
            model_cache=dict(asr_loads=c.models.asr_loads,speaker_loads=c.models.speaker_loads,streams=c.models.streams),
            model_manifest=json.loads((ROOT/'config/assets.json').read_text()),output_defaults=c.output_defaults,
            source_bindings={p.relative_to(ROOT).as_posix():sha256(p) for folder in ('app','vendor','config') for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.json')})
        # Actual controller/UI state, no audio output. Reopen the closed fixture for assumed labels.
        closed=result['jobs'][3];closed_folder=Path(closed['epoch_path'])
        c.session_action('open',identifier=c.conversation_id);check_command()
        c.mode='selected_closed'  # Stopped history view only; original epochs retain their modes.
        from app.ui import PrototypeUI,prepare_dpi_awareness
        from prototype.tests.native_ui_check import capture
        import tkinter as tk
        prepare_dpi_awareness();root=tk.Tk();ui=PrototypeUI(root,c);root.geometry('+25+25');root.attributes('-topmost',True)
        evidence=args.data_root/'ui';evidence.mkdir()
        ui.show_modes();capture(root,evidence/'01_real_modes.png')
        ui.show_roster('selected_closed');capture(root,evidence/'02_real_roster.png')
        ui.show_advanced();capture(root,evidence/'03_real_advanced.png')
        ui.show_identity_scores();capture(root,evidence/'04_real_scores.png')
        result['client']=ui.measure_client();ui.close();deadline=time.perf_counter()+15
        while not ui._closed and time.perf_counter()<deadline:root.update()
        assert ui._closed
        result['status']='PASS'
    except Exception as exc:
        import traceback
        result.update(status='FAIL',error=str(exc),traceback=traceback.format_exc());raise
    finally:
        if not c.closed:c.close()
        c.commands.join();c.worker.join(15)
        result.update(closed=c.closed,worker_alive=c.worker.is_alive(),elapsed_sec=time.perf_counter()-started,utc=datetime.now(timezone.utc).isoformat())
        atomic_json(args.data_root/'ROSTER_NATIVE_CHECK.json',result)
        print(json.dumps({k:result[k] for k in ('status','elapsed_sec','closed','worker_alive')}),flush=True)


if __name__=='__main__':main()
