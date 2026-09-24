"""Small native task11 fixture/controller check, no mic. See README_ADAPTATION.md."""
import argparse,hashlib,json,os,sys,time,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor'),str(ROOT/'tests')]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(key,'1')
import numpy as np
import soundfile as sf
import psutil
from app.controller import Controller
from app.paths import default_models_root,sha256
from app.enrollment_quality import EnrollmentQuality
from app.reference_adaptation import BaseAnchors,SessionBank
from app.people import PersonalStore
from check_native_people import ROUTE

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--corpus',type=Path,default=ROOT.parent/'Software Validation from Datasets/Raw Datasets (Not formatted)/CMU Arctic')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    proc=psutil.Process();start=time.perf_counter();cpu0=proc.cpu_times();rss=[];stop=threading.Event()
    def sample():
        while not stop.wait(.05):rss.append(proc.memory_info().rss)
    sampler=threading.Thread(target=sample,daemon=True);sampler.start()
    report=dict(status='RUNNING',scope='Native public-corpus functional check; fixture operator confirmations, no participating human, no accuracy gain claim',
        enrollment=[],runs=[],no_microphone=True,no_playback=True,sources={},limits='Dry mono fixtures, not XVF/live people/CM5 qualification')
    c=None
    def save():(args.output/'NATIVE_ADAPTATION_CHECK.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    try:
        c=Controller(args.output/'data',default_models_root());c.models.enrollment_models(c.config);c.route=lambda:dict(ROUTE)
        def load(code,n):
            path=args.corpus/f'cmu_us_{code}_arctic/wav/arctic_a{n:04d}.wav';x,rate=sf.read(path,dtype='float32');assert rate==16000
            report['sources'][f'{code}_{n}']=dict(path=str(path),sha256=sha256(path),samples=len(x));return x
        ids={}
        for code in ('awb','bdl'):
            x=np.concatenate([load(code,n) for n in (1,3)]);q=EnrollmentQuality(c.models.speakers,c.config,None)
            for offset in range(0,len(x),160000):q.process(x[offset:offset+160000])
            quality,vector=q.result(source_kind='offline_public_corpus_task11');assert quality['can_save'],quality
            row=c.store.save('Fixture '+code,vector,quality,ROUTE);ids[code]=row['id'];report['enrollment'].append(dict(speaker=code,quality=quality))
        anchors={str(p.relative_to(c.data_root)):sha256(p) for p in (c.data_root/'people').rglob('*.npy')}
        c.switch(mode='enrolled_names',recipe='balanced',tap='O0');c.commands.join();assert not c.error,c.error
        def action(name,**values):
            c.adaptation_action(name,**values);c.commands.join();assert not c.error,c.error
        def run(label,x,expected,collect=False,use=False):
            path=args.output/(label+'.wav');sf.write(path,x,16000,subtype='PCM_16')
            action('collect',enabled=collect,consent=True);action('use',enabled=use,consent=True)
            c.rows.clear();tick=time.perf_counter();c.start_file(path);c.commands.join();assert not c.error,c.error
            deadline=time.perf_counter()+90
            while c.state in ('STARTING','RUNNING','STOPPING') and time.perf_counter()<deadline:time.sleep(.05)
            assert c.state=='STOPPED' and not c.error,(c.state,c.error)
            assert c.engine.state=='COMPLETED';bank=c.reference_bank
            parts=[p for r in c.rows.values() for p in (r.get('segments') or [r])]
            names=[p.get('known_profile_id') for p in parts if p.get('naming_state')=='confirmed' and p.get('known_profile_id')]
            row=dict(label=label,expected_uuid=expected,confirmed_uuids=sorted(set(names)),
                confirmed_segments=len(names),wrong_named_segments=sum(i!=expected for i in names),total_segments=len(parts),
                accepted_segment_fraction=len(names)/len(parts) if parts else 0.,
                metric_scope='Final caption segments, not word-aligned DER; mixed speech has no one correct UUID',
                bank=bank.snapshot() if bank else None,gallery_calls=c.engine._research_gallery.query_count,
                captions=[dict(text=r.get('text'),segments=r.get('segments')) for r in c.rows.values()],
                wall_sec=time.perf_counter()-tick)
            report['runs'].append(row);save();return bank
        candidate=load('awb',16);query=np.concatenate([load('awb',n) for n in (17,18,19)])
        outsider=load('clb',1);other=load('bdl',16)
        mix=np.zeros(max(len(candidate),len(other)),np.float32);mix[:len(candidate)]+=.5*candidate;mix[:len(other)]+=.5*other
        bank=run('collect_awb',candidate,ids['awb'],collect=True)
        report['candidate_initial']=bank.snapshot();assert bank.candidates and not bank.frozen,bank.snapshot()
        compatible=[v for v in bank.candidates if bank.base.agrees(v['base_scores'],ids['awb'])]
        assert compatible,'No immutable-base agreement in fixed genuine fixture'
        for v in compatible[:4]:action('confirm',id=v['id'],person_id=ids['awb'],consent=True)
        approved=[v for v in bank.candidates if v['confirmation']];report['approved_windows']=[{k:v for k,v in x.items() if k!='vector'} for x in approved]
        action('promote',ids=[v['id'] for v in approved],person_id=ids['awb'],consent=True)
        report['promotion']=dict(count=len(approved),fixture_confirmation_only=True)
        duplicate=run('repeated_saved_audio',candidate,ids['awb'],collect=True)
        assert not duplicate.candidates and duplicate.rejected['duplicate_or_overlapping_window']>0,duplicate.snapshot()
        before=len(report['runs']);run('heldout_base',query,ids['awb']);run('heldout_bank',query,ids['awb'],use=True)
        run('outsider_bank',outsider,None,use=True)
        bad=run('wrong_person_at_assigned_seat',outsider,None,collect=True)
        for v in bad.candidates:
            # Deliberately wrong seat/text labels do not certify outsider speech.
            v['provenance'].update(assigned_seat_person=ids['awb'],forced_closed_group=ids['awb'],revised_text='Fixture awb')
            try:bad.confirm(v['id'],ids['awb'],consent=True)
            except ValueError:pass
            else:raise AssertionError('Intentional outsider contamination accepted')
        report['contamination']=dict(candidates=len(bad.candidates),frozen=bad.frozen,confirmed=sum(bool(v['confirmation']) for v in bad.candidates))
        mixed=run('mixed_speech',mix,None,collect=True)
        report['mixed_collection']=mixed.snapshot()
        action('undo',person_id=ids['awb'],consent=True)
        run('heldout_after_undo',query,ids['awb'],use=True)
        assert not c.store.gallery(ROUTE).environment_bank
        assert anchors=={str(p.relative_to(c.data_root)):sha256(p) for p in (c.data_root/'people').rglob('*.npy')}
        report['base_anchors_unchanged']=True
        c.close();c.commands.join();assert c.closed;c=None
        reopened=Controller(args.output/'data',default_models_root())
        try:
            report['restart']=dict(default_off=not reopened.collect_references and not reopened.use_references,
                bank_empty=not reopened.store.gallery(ROUTE).environment_bank,people=len(reopened.store.list()))
            assert all(report['restart'][k] for k in ('default_off','bank_empty'))
        finally:reopened.close();reopened.commands.join()
        report['status']='PASS_FUNCTIONAL'
    except Exception as exc:
        import traceback
        report.update(status='FAIL',error=repr(exc),traceback=traceback.format_exc());raise
    finally:
        if c is not None:
            try:c.close();c.commands.join()
            except Exception as exc:report['cleanup_error']=repr(exc)
        stop.set();sampler.join();cpu=proc.cpu_times()
        report['resources']=dict(wall_sec=time.perf_counter()-start,cpu_sec=cpu.user+cpu.system-cpu0.user-cpu0.system,
            sampled_peak_rss_bytes=max(rss,default=0),sample_interval_sec=.05)
        report['execution_sha256']={p.relative_to(ROOT).as_posix():sha256(p) for folder in ('app','vendor','config') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        report['harness_sha256']=sha256(Path(__file__));save()
    print(json.dumps(dict(status=report['status'],runs=len(report['runs']),resources=report['resources'])))

if __name__=='__main__':main()
