"""Real saved models/audio plus labelled synthetic telemetry. See README_SEATS.md."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(key,'1')
from app.controller import Controller
from app.pipeline import FileSource
from app.paths import default_models_root,atomic_json,sha256
from app.sessions import records
from app.live_spatial import ANGLE,ENERGY,SELECTED
from prototype.tests.check_native_people import ROUTE


class SyntheticTelemetryJournal:
    """Test-only injection; actual file sample clock and model availability remain real."""
    def __init__(self,target,provider):self.target=target;self.provider=provider;self.sent=0;self.last=-1.
    def __getattr__(self,name):return getattr(self.target,name)
    def append(self,audio):
        self.sent+=len(audio);end=self.sent/16000;now=time.perf_counter()
        # Five groups/sec at most. Stable direction changes are synthetic and
        # are never labelled hardware receipts or an acoustic accuracy measure.
        if end-self.last>=.2-1e-6 and end<9.:
            angle=30. if end<4.5 else 150.;self.last=end
            for i,(field,values) in enumerate(((ANGLE,[math.radians(angle)]*4),(ENERGY,[.5,0.,0.,.5]),(SELECTED,[math.radians(angle)]*2))):
                completed=now-(2-i)*.0002
                self.provider.receive(field,values,completed-.0001,completed)
        self.provider.advance_audio(SimpleNamespace(callback_perf_counter_ns=round(now*1e9),
            model_start_sample=self.sent-len(audio),audio=audio))
        self.target.append(audio)


class SyntheticTelemetryFile(FileSource):
    def start(self):
        provider=self.callback.__self__.live_spatial
        provider.attach(SimpleNamespace(beam_diagnostics=SimpleNamespace(snapshot=lambda:dict(state='RUNNING'),set_fast=lambda value:None)))
        self.journal=SyntheticTelemetryJournal(self.journal,provider)
        super().start()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--case',choices=['all','direction_change_motion'],default='all');a=p.parse_args()
    out=a.data_root.resolve();fixture=a.fixture.resolve()
    if out.exists() or ROOT==out or ROOT in out.parents:raise ValueError('Use a fresh private output outside prototype')
    out.mkdir(parents=True);shutil.copytree(fixture/'people',out/'people')
    previous=json.loads((fixture/'ROSTER_NATIVE_CHECK.json').read_text())
    ids=previous['jobs'][2]['gallery_ids'];person_a=previous['jobs'][0]['gallery_ids'][0];person_b=next(i for i in ids if i!=person_a)
    result=dict(status='RUNNING',scope='Real saved CMU/model inference + synthetic telemetry. NO live XVF/person accuracy claim.',jobs=[])
    began=time.perf_counter();c=Controller(out,default_models_root());c.route=lambda:dict(ROUTE)
    before={p.relative_to(c.store.root).as_posix():sha256(p) for p in c.store.root.rglob('*') if p.is_file()}
    bindings={p.relative_to(ROOT).as_posix():sha256(p) for folder in ('app','vendor','config') for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.json')}
    ui=None
    try:
        import tkinter as tk
        from app.ui import PrototypeUI,prepare_dpi_awareness
        from prototype.tests.native_ui_check import capture
        prepare_dpi_awareness();root=tk.Tk();ui=PrototypeUI(root,c);root.title('Task 05 · REAL saved audio / SYNTHETIC directions');root.geometry('+25+25');root.attributes('-topmost',True)
        pictures=out/'ui';pictures.mkdir()
        def commands():
            c.commands.join()
            if c.error:raise RuntimeError(c.error)
        jobs=[('direction_change_motion','assigned_direction','A',[person_a,person_b]),
                ('hybrid_voice_conflict','assigned_hybrid','A',[person_a,person_b]),('hybrid_outsider','assigned_hybrid','B',[person_a])]
        for name,mode,query,subset in jobs if a.case=='all' else jobs[:1]:
            started=time.perf_counter();c.session_action('new');commands()
            rows=[dict(person_id=pid,angle_deg=30. if pid==person_a else 150.,tolerance_deg=25.) for pid in subset]
            c.seats_apply(rows,mode);commands()
            with patch('app.pipeline.FileSource',SyntheticTelemetryFile):c.start_file(fixture/(query+'_12s.wav'));commands()
            engine=c.engine;streams=c.models.streams;motion=False;captured=False;motion_stamp=None;assumed_widget=False
            deadline=time.perf_counter()+60
            while c.state in ('STARTING','RUNNING','STOPPING') and time.perf_counter()<deadline:
                root.update()
                if name=='direction_change_motion' and 'seat assumed' in ui.caption_text.get('1.0','end') and not captured:
                    assumed_widget=True
                    capture(root,pictures/'01_real_caption_synthetic_seat.png');ui.show_identity_scores();capture(root,pictures/'02_real_scores_synthetic_seat.png');ui.home();captured=True
                if name=='direction_change_motion' and engine._source_time()>8. and not motion:
                    state=engine.prototype_identity.states
                    c.reset_spatial();commands();motion=True;motion_stamp=engine._s7_observed_clock.relative()
                    assert c.engine is engine and c.models.streams==streams and engine.prototype_identity.states is state
                    assert not c.seats.snapshot()['valid']
                time.sleep(.02)
            assert c.state=='STOPPED' and not c.error,c.error or c.state
            meta=c.session_store.metadata(c.conversation_id);folder=c.session_store.epoch(c.conversation_id,meta['epochs'][-1])
            events=list(records(folder/'events.jsonl'));decisions=[r['payload'] for r in events if r['kind']=='speaker_decision']
            details=[r['decision']['identity'] for r in decisions];shown=[r['payload'] for r in events if r['kind']=='s6d_display']
            assert details and shown and engine.state=='COMPLETED'
            if mode=='assigned_direction':
                assert assumed_widget,'Assumption never reached the actual caption widget'
                assert engine._research_gallery is None and engine.prototype_identity.query_calls==0
                assert {d['known_profile_id'] for d in details if d['assignment']=='seat_assumed'}=={person_a,person_b}
                assert any(s.get('prototype_assignment')=='seat_assumed' for r in shown for s in r.get('segments',[]))
                assert any(r['kind']=='prototype_seat_configuration' and r['payload']['action']=='manual_tablet_moved' for r in events)
                assert not any(r['decision']['identity']['known_profile_id'] for r in decisions if r['input_available_at_sec']>motion_stamp+.05)
            elif name=='hybrid_outsider':
                assert not any(d.get('known_profile_id') for d in details if d['naming_state']=='confirmed')
            else:
                assert any(d['known_profile_id']==person_a and d['assignment']=='accepted' for d in details)
                assert not any(d['known_profile_id']==person_b for d in details)
            resources=list(records(folder/'resources.jsonl'))
            job=dict(name=name,mode=mode,elapsed_sec=time.perf_counter()-started,decisions=dict(Counter(d['assignment'] for d in details)),
                caption_updates=len(shown),epoch=str(folder),model_telemetry=engine.telemetry(),
                native_pipeline_state=engine.state,motion_without_restart=motion,assumed_label_in_actual_widget=assumed_widget,
                gallery_ids=engine._research_gallery.ids if engine._research_gallery else [],
                query_file=dict(path=str(fixture/(query+'_12s.wav')),sha256=sha256(fixture/(query+'_12s.wav'))),
                max_sampled_rss_bytes=max(r['process_rss_bytes'] for r in resources),cpu_total_sec=resources[-1]['cpu_total_sec'])
            result['jobs'].append(job);atomic_json(out/'SEAT_NATIVE_CHECK.json',result)
            print(json.dumps({k:job[k] for k in ('name','elapsed_sec','decisions')}),flush=True)
        ui.snapshot=c.snapshot();ui.show_seats('assigned_hybrid');capture(root,pictures/'03_native_people_seat_editor.png')
        ui._seat_draft=[dict(person_id=person_a,angle_deg=90.,tolerance_deg=25.),dict(person_id=person_b,angle_deg=90.,tolerance_deg=25.)]
        ui._paint_seats();capture(root,pictures/'04_synthetic_front_back_collision.png')
        ui.show_modes();capture(root,pictures/'05_real_menu.png')
        result.update(status='PASS',client=ui.measure_client(),source_bindings=bindings,
            profiles_unchanged=before=={p.relative_to(c.store.root).as_posix():sha256(p) for p in c.store.root.rglob('*') if p.is_file()},
            reference_provenance=dict(receipt=str(fixture/'ROSTER_NATIVE_CHECK.json'),sha256=sha256(fixture/'ROSTER_NATIVE_CHECK.json'),disjoint_admission=previous['reference_query_hashes_disjoint']),
            model_cache=dict(asr_loads=c.models.asr_loads,speaker_loads=c.models.speaker_loads,streams=c.models.streams),output_defaults=c.output_defaults)
        assert result['profiles_unchanged'] and result['reference_provenance']['disjoint_admission']
    except BaseException as exc:
        import traceback
        result.update(status='FAIL',error=str(exc),traceback=traceback.format_exc());raise
    finally:
        if ui is not None:
            ui.close();deadline=time.perf_counter()+15
            while not ui._closed and time.perf_counter()<deadline:root.update();time.sleep(.01)
        if not c.closed:c.close()
        c.commands.join();c.worker.join(15)
        result.update(elapsed_sec=time.perf_counter()-began,closed=c.closed,worker_alive=c.worker.is_alive())
        atomic_json(out/'SEAT_NATIVE_CHECK.json',result)
        print(json.dumps({k:result[k] for k in ('status','elapsed_sec','closed','worker_alive')}),flush=True)


if __name__=='__main__':main()
