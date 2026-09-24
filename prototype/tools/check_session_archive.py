"""Short native saved-file archive proof; no mic or audible output. See README_SESSIONS.md."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(key,'1')
import numpy as np
import soundfile as sf
from app.controller import Controller
from app.paths import default_models_root
from app.sessions import SessionStore,records
from app.session_playback import SessionPlayback
from prototype.tests.test_sessions import FakeBackend


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wav',type=Path,required=True);p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--portrait-during-run',action='store_true',help='Pump the real portrait UI during the bounded native replay; no microphone')
    args=p.parse_args();assert not args.data_root.exists(),'Fresh output directory required'
    began=time.perf_counter();c=Controller(args.data_root,default_models_root());failures=[];result={};live_ui=None
    def command(action,**values):
        c.session_action(action,**values);c.commands.join()
        if c.error:raise RuntimeError(c.error)
    try:
        command('new',audio=True,consent=True,title='Native prepared-file archive proof')
        identifier=c.conversation_id
        c.switch(mode='anonymous_conversation',recipe='balanced',tap='O0');c.commands.join()
        if args.portrait_during_run:
            import tkinter as tk
            import psutil
            from app.ui import PrototypeUI,prepare_dpi_awareness
            prepare_dpi_awareness();live_root=tk.Tk();live_ui=PrototypeUI(live_root,c)
            live_root.geometry('+25+25');live_root.update()
            stamps=[];rss=[];process=psutil.Process();initial_rss=process.memory_info().rss
        c.start_file(args.wav)
        if not live_ui:c.commands.join()
        if c.error:raise RuntimeError(c.error)
        deadline=time.perf_counter()+60
        while (c.commands.unfinished_tasks or c.state in ('STARTING','RUNNING','STOPPING')) and time.perf_counter()<deadline:
            if live_ui:
                live_root.update();stamps.append(time.perf_counter());rss.append(process.memory_info().rss)
            time.sleep(.03 if live_ui else .1)
        if c.error or c.state!='STOPPED':raise RuntimeError(c.error or 'Native run failed to finish')
        command('save',identifier=identifier)
        meta=c.session_store.metadata(identifier);epoch=meta['epochs'][0];folder=c.session_store.epoch(identifier,epoch)
        input_audio,rate=sf.read(args.wav,dtype='float32');master=np.fromfile(folder/'model_input.f32le',dtype='<f4')
        assert rate==16000 and master.tobytes()==input_audio.tobytes(),'Model-input audio differs from prepared source'
        epoch_meta=json.loads((folder/'epoch.json').read_text())
        assert epoch_meta['state']=='CLOSED' and not epoch_meta['archive_error'],epoch_meta
        formatted=[r for r in records(folder/'events.jsonl') if r['kind']=='prototype_formatted_text']
        assert formatted and all('raw_asr_text' in r['payload'] and 'provisional_display_text' in r['payload'] for r in formatted)
        windows=list(records(folder/'windows.jsonl'));assert any(w['kind']=='research_embedding' for w in windows)
        assert any(w['kind']=='research_segmentation' for w in windows)
        for kind in ('research_embedding','research_segmentation'):
            row=next(w for w in windows if w['kind']==kind);out=args.data_root/(kind+'.npy')
            c.session_store.export_window(identifier,epoch,row['window_id'],out)
            expected=np.pad(input_audio[row['source_start_sample']:row['source_end_sample']],(row['left_padding_samples'],0))
            assert np.load(out).tobytes()==expected.tobytes()
        resources=list(records(folder/'resources.jsonl'));assert len(resources)>=5
        clocks=[r['monotonic_sec'] for r in resources];assert all(b>a for a,b in zip(clocks,clocks[1:]))
        assert all(r['archive_epoch_id']==epoch and r['source_cursor_sample']<=len(master) for r in resources)
        text_before=c.session_store.rows(identifier)
        command('rename',identifier=identifier,title='Renamed archive proof')
        command('note',identifier=identifier,note='Fixture validation; no live microphone.')
        command('correct',identifier=identifier,row_id=text_before[0]['caption_key'],correction='Explicit test correction, kept separate.')
        assert c.session_store.rows(identifier)==text_before
        command('export',identifier=identifier,path=str(args.data_root/'text.zip'),consent=True,audio=False)
        command('export',identifier=identifier,path=str(args.data_root/'full.zip'),consent=True,audio=True)
        model_counts=(c.models.asr_loads,c.models.speaker_loads)
        if live_ui:
            assert len(stamps)>2
            from app.motion import MotionEvent
            now=time.monotonic_ns();c.motion_event(MotionEvent('moving',now,now,.9,True));c.commands.join()
            assert not c.seating_snapshot()['valid'] and c.error is None
            c.switch(mode='caption_only',recipe='fast',tap='O0');c.commands.join()
            assert c.error is None and (c.models.asr_loads,c.models.speaker_loads)==model_counts
            live_ui.home();live_root.update()
            result['integrated_desktop']=dict(ui_updates=len(stamps),max_update_gap_sec=max(b-a for a,b in zip(stamps,stamps[1:])),
                initial_rss_bytes=initial_rss,peak_rss_bytes=max(rss),final_rss_bytes=process.memory_info().rss,
                sample_scope='One 12-second saved fixture; model loading included, not a sustained-memory/CM5 claim',
                mode_switch_to_captions=True,mock_motion_invalidates=True,client=live_ui.measure_client())
        command('new',audio=False,title='Empty preserved text-only draft')
        assert (c.models.asr_loads,c.models.speaker_loads)==model_counts
        result.update(conversation_id=identifier,archive_path=str(folder),master_samples=len(master),
            exact_float_bytes_equal=True,source_sha256=hashlib.sha256(args.wav.read_bytes()).hexdigest(),
            model_cache=dict(asr_loads=c.models.asr_loads,speaker_loads=c.models.speaker_loads,streams=c.models.streams),
            windows=len(windows),resource_samples=len(resources),resource_intervals_sec=[b-a for a,b in zip(clocks,clocks[1:])],
            formatted_events=len(formatted),
            max_process_rss_bytes=max(r['process_rss_bytes'] for r in resources),cpu_total_sec=resources[-1]['cpu_total_sec'],
            epoch_metadata=json.loads((folder/'epoch.json').read_text()),original_caption_count=len(text_before),
            hardware_playback='NOT_TESTED; explicit-output fake sink checks isolation and exact samples',
            output_defaults=c.output_defaults)
    finally:
        if live_ui:
            live_ui.close();deadline=time.perf_counter()+15
            while not live_ui._closed and time.perf_counter()<deadline:live_root.update();time.sleep(.02)
            assert live_ui._closed
        if not c.closed:c.close()
        c.commands.join();c.worker.join(10)
    assert c.closed
    # A fresh owner, no recognizer/model load: restart -> reopen -> matching clip.
    c=Controller(args.data_root,default_models_root())
    try:
        command('open',identifier=identifier)
        assert c.session_store.rows(identifier)==text_before
        c.chosen_output=dict(index=17,name='Explicit fixture headphones',hostapi='Fixture API');backend=FakeBackend()
        selected=c.session_rows[0];stop_calls=[]
        original_stop=c._stop_session
        def release():original_stop();assert c.engine is None;stop_calls.append('released')
        with patch.object(c,'_stop_session',side_effect=release),patch('app.session_playback.SessionPlayback',side_effect=lambda x,d:SessionPlayback(x,d,backend=backend)):
            command('play',identifier=identifier,epoch=selected['epoch'],start=selected['start'],end=selected['end'])
            c.playback.thread.join(3)
            assert c.playback.error is None
            np.testing.assert_array_equal(np.concatenate(backend.audio).ravel(),master[selected['start']:selected['end']])
            command('stop_playback')
        result.update(restart_reopen=True,corresponding_caption_playback_fake_sink=True,
            playback_capture_released=bool(stop_calls),restart_model_loads=c.models.asr_loads+c.models.speaker_loads)
        # Real application screenshots of the actual archived fixture (microphone off).
        import tkinter as tk
        from app.ui import PrototypeUI,prepare_dpi_awareness
        from prototype.tests.native_ui_check import capture
        prepare_dpi_awareness();root=tk.Tk();ui=PrototypeUI(root,c);root.geometry('+25+25');root.attributes('-topmost',True)
        evidence=args.data_root/'ui';evidence.mkdir()
        ui.show_sessions();capture(root,evidence/'01_real_sessions.png')
        ui.show_session(identifier);capture(root,evidence/'02_real_conversation.png')
        ui.home();capture(root,evidence/'03_real_reopened_captions.png')
        result['client']=ui.measure_client();ui.close()
        deadline=time.perf_counter()+15
        while not ui._closed and time.perf_counter()<deadline:root.update()
        assert ui._closed
    finally:
        if not c.closed:c.close()
        c.commands.join();c.worker.join(10)
    result.update(status='PASS',elapsed_sec=time.perf_counter()-began,utc=datetime.now(timezone.utc).isoformat(),
        code_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [ROOT/'app'/name for name in ('sessions.py','session_controller.py','session_ui.py','session_playback.py','controller.py','pipeline.py','buffers.py','ui.py')]})
    (args.data_root/'SESSION_ARCHIVE_CHECK.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','elapsed_sec','master_samples','windows','resource_samples','exact_float_bytes_equal','restart_reopen','model_cache','restart_model_loads')}))


if __name__=='__main__':main()
