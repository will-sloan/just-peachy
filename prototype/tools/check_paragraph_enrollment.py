"""Small native enrollment/ASR parity check. See README_ENROLLMENT.md.

Only prerecorded mono 16 kHz audio; no input/output devices or production store.
"""
import argparse
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
import numpy as np
import psutil
import soundfile as sf
from app.enrollment_quality import EnrollmentQuality
from app.enrollment_progress import ReadProgress, reference_text
from app.paths import pipeline_config, default_models_root
from app.people import PersonalStore
from app.pipeline import ResidentModels
from prototype.tests.check_native_people import ROUTE


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wav',required=True,type=Path)
    p.add_argument('--baseline-zip',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--models',type=Path,default=default_models_root())
    args=p.parse_args();args.output_dir.mkdir(parents=True,exist_ok=False)
    begun=time.perf_counter();process=psutil.Process();cpu=process.cpu_times()
    result={'status':'RUNNING','scope':'Real existing models; offline fixture. No microphone, playback or live accuracy claim.','checks':{}}
    try:
        audio,rate=sf.read(args.wav,dtype='float32')
        assert rate==16000 and audio.ndim==1 and 8000<=len(audio)<=16000*14
        result['audio']={'path':str(args.wav),'sha256':sha(args.wav),'samples':len(audio),'sample_rate':rate}
        result['baseline_zip_sha256']=sha(args.baseline_zip)
        result['source_sha256']={str(x.relative_to(ROOT)):sha(x) for x in [Path(__file__),*(ROOT/'app').glob('*.py')]}
        config=pipeline_config(args.output_dir,args.models);models=ResidentModels()
        speakers=models.enrollment_models(config)
        with zipfile.ZipFile(args.baseline_zip) as z:source=z.read('app/enrollment_quality.py')
        namespace={'__name__':'app._before06_quality','__package__':'app'}
        exec(compile(source,'before06_quality.py','exec'),namespace)
        legacy=namespace['EnrollmentQuality'](speakers,config,15)
        timed=EnrollmentQuality(speakers,config,15);done=EnrollmentQuality(speakers,config,None)
        for offset in range(0,len(audio),160000):
            piece=audio[offset:offset+160000]
            legacy.process(piece);timed.process(piece,source_start=offset);done.process(piece,source_start=offset)
        old,ov=legacy.result();tq,tv=timed.result();dq,dv=done.result(source_kind='offline_CMU_task06_fixture')
        assert dq['can_save'] and not tq['can_save'] and dq['usable_s']<15
        assert np.array_equal(ov,tv) and np.array_equal(ov,dv)
        assert all(old[k]==tq[k]==dq[k] for k in ('usable_s','accepted_intervals','clipping','consistency','source_sha256','embedding_count','model_segment_calls','model_embedding_calls'))
        result['checks']['native_before_after_vectors_bit_identical']='PASS'
        result['checks']['native_short_done_accepted_timed_rejected']='PASS'
        result['vector_max_abs_delta']=float(np.max(np.abs(ov-dv)))
        assert not done.process(audio[:160000],source_start=0)
        assert done.result()[0]['usable_s']==dq['usable_s']
        result['checks']['duplicate_support_no_additional_inference']='PASS'
        _,stream=models.acquire(config,caption_only=True)
        offered=json.loads((ROOT/'config/ui.json').read_text(encoding='utf-8'))['enrollment_paragraph']
        reader=ReadProgress(stream,offered)
        for offset in range(0,len(audio),160000):reader.accept(audio[offset:offset+160000])
        estimate=reader.finish()
        assert estimate['recognized_words']>0 and estimate['estimated_coverage']<1
        assert np.array_equal(done.result()[1],dv)
        result['checks']['ordinary_asr_mismatched_script_does_not_change_voice']='PASS'
        dq.update(offered_reference=reference_text(offered),script_estimate=estimate,source_session_id='offline-task06')
        backend=config.asset('redimnet2_b2_fp32').sha256
        store=PersonalStore(args.output_dir/'people',backend);person=store.save('Offline fixture only',dv,dq,ROUTE)
        script="import sys,json;from pathlib import Path;sys.path[:0]=[sys.argv[1],str(Path(sys.argv[1])/'vendor')];from app.people import PersonalStore;s=PersonalStore(Path(sys.argv[2]),sys.argv[3]);print(json.dumps([x['id'] for x in s.list()]))"
        restart=subprocess.run([sys.executable,'-B','-c',script,str(ROOT),str(store.root),backend],capture_output=True,text=True,timeout=30)
        assert restart.returncode==0,restart.stderr
        assert json.loads(restart.stdout)==[person['id']]
        result['checks']['new_process_restart_preserves_paragraph_profile']='PASS'
        archive=args.output_dir/'fixture_profiles.zip';store.export(archive,True)
        imported=PersonalStore(args.output_dir/'imported',backend);imported.import_archive(archive,True)
        assert imported.gallery(ROUTE).ids==[person['id']]
        result['checks']['native_profile_export_import']='PASS'
        for label,attempt in [('tap_mismatch',lambda:imported.gallery(dict(ROUTE,tap='O1'))),
                              ('duplicate_saved_source',lambda:store.save('Offline fixture only',dv,dq,ROUTE,person_id=person['id']))]:
            try:attempt()
            except ValueError:result['checks'][label]='PASS'
            else:raise AssertionError(label+' should have been rejected')
        for label,x in [('too_short',audio[:7999]),('silence',np.zeros(16000,np.float32)),('clipping',np.ones(16000,np.float32))]:
            q=EnrollmentQuality(speakers,config,None);q.process(x)
            assert not q.result()[0]['can_save'],label
            result['checks']['native_reject_'+label]='PASS'
        result['quality']={k:v for k,v in dq.items() if k not in ('offered_reference','script_estimate','accepted_intervals')}
        result['asr_estimate']={k:v for k,v in estimate.items() if k not in ('utterances','partial_raw_asr_text')}
        result['model_loads']={'asr':models.asr_loads,'speaker':models.speaker_loads,'streams':models.streams}
        result['speaker_input']=[{'name':x.name,'shape':x.shape,'type':x.type} for x in speakers._redim.get_inputs()]
        result['assets']={x.component_id:{'sha256':x.sha256,'actual_sha256':sha(x.path)} for x in config.assets}
        assert all(x['sha256']==x['actual_sha256'] for x in result['assets'].values())
        result['versions']={name:version(name) for name in ('numpy','onnxruntime','sherpa-onnx','soundfile')}
        result['status']='PASS'
    except Exception:
        import traceback
        result['status']='FAIL';result['error']=traceback.format_exc()
    finally:
        result['elapsed_sec']=time.perf_counter()-begun
        endcpu=process.cpu_times();result['cpu_sec']=(endcpu.user+endcpu.system)-(cpu.user+cpu.system)
        memory=process.memory_info();result['peak_rss_mib']=getattr(memory,'peak_wset',memory.rss)/2**20
        (args.output_dir/'NATIVE_ENROLLMENT_CHECK.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','checks','elapsed_sec','cpu_sec','peak_rss_mib')}))
    if result['status']!='PASS':print(result.get('error'))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
