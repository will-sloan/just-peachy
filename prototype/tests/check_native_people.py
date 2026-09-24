"""Bounded real-model personal-store replay; see README_NATIVE_PEOPLE.md."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
import numpy as np
import soundfile as sf
from app.paths import pipeline_config,default_models_root,atomic_json
from app.people import PersonalStore,PREPROCESSING
from app.enrollment_quality import EnrollmentQuality
from app.pipeline import ResidentModels,PrototypeEngine,effective_profile

ROUTE={'tap':'O0','sample_rate':16000,'gain_policy':'fixture_unity',
       'waveform_domain':'dry_test_fixture','preprocessing':PREPROCESSING,
       'source':'CMU ARCTIC existing consent-safe offline fixture; no XVF/live claim'}


def binding(path):
    p=Path(path)
    return {'path':str(p),'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),
            'frames':sf.info(p).frames,'sample_rate':sf.info(p).samplerate}


def join_files(paths):
    chunks=[]
    for path in paths:
        x,rate=sf.read(path,dtype='float32')
        if rate!=16000 or x.ndim!=1:raise ValueError('Fixtures must already be mono16k')
        chunks.append(x)
    return np.concatenate(chunks)


def quality(audio,models,config,provenance,label):
    state=EnrollmentQuality(models,config,15)
    for offset in range(0,len(audio),160000):state.process(audio[offset:offset+160000])
    q,v=state.result(source_kind='offline_disjoint_CMU_fixture')
    q.update(source_session_id=label,source_provenance=provenance)
    return q,v


def native_query(label,wav,config,models,store,*,alternate_advisory=False):
    gallery=store.gallery(ROUTE,alternate_advisory=alternate_advisory)
    profile=effective_profile('balanced','enrolled_names','O0')
    engine=PrototypeEngine(config,models,profile,gallery,'enrolled_names')
    started=time.perf_counter();engine.start_prepared_file(wav)
    counts={};decisions=[];captions={};deadline=time.monotonic()+90
    def inspect(value):
        if isinstance(value,dict):
            if value.get('query_executed') is True and 'top1_score' in value:
                decisions.append({k:value.get(k) for k in ('known_profile_id','known_name','naming_state',
                   'candidate_profile_id','top1_score','margin','unique_clean_sec','disjoint_count','reason')})
            for child in value.values():
                if isinstance(child,(dict,list)):inspect(child)
        elif isinstance(value,list):
            for child in value:
                if isinstance(child,(dict,list)):inspect(child)
    while True:
        if time.monotonic()>deadline:
            engine.stop();raise TimeoutError(label+' bounded native query exceeded90s')
        try:
            event=engine.events.get(timeout=.1)
            counts[event.event_type]=counts.get(event.event_type,0)+1
            inspect(event.payload)
            if event.event_type=='s6d_display':
                key=event.payload.get('caption_key',str(event.payload.get('utterance_id')))
                captions[key]=event.payload
        except queue.Empty:pass
        finished=engine._finalization_thread is not None and not engine._finalization_thread.is_alive()
        if finished and engine.events.empty():break
    engine.wait_for_completion(10)
    engine.record_s6d_consumer_closure('PROTO1 native personal fixture test; complete event drain')
    confirmed=set()
    for row in captions.values():
        for part in row.get('segments') or [row]:
            if part.get('naming_state')=='confirmed' and part.get('known_profile_id'):
                confirmed.add(part['known_profile_id'])
    return {'label':label,'status':'PASS' if engine.state=='COMPLETED' else 'FAIL','state':engine.state,
        'wall_seconds':time.perf_counter()-started,'source_seconds':sf.info(wav).duration,
        'gallery_ids_loaded':gallery.ids,'gallery_id':gallery.gallery_id,'actual_gallery_score_calls':gallery.query_count,
        'confirmed_profile_ids_in_final_rows':sorted(confirmed),'caption_rows':len(captions),'event_counts':counts,
        'identity_decisions':decisions,'session_path':str(engine.session_dir),
        'naming_policy':asdict(profile.identity),'raw_query_wav':binding(wav),
        'alternate_advisory':alternate_advisory,'last_alternate_comparison':gallery.last_alternate}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,default=Path(r'G:\Just_Peachy_S6C\20260910T123540Z\source_inventory\v2\decoded_16k'))
    parser.add_argument('--private-root',type=Path,default=Path(r'G:\Just_Peachy_PROTO1\tests\personal_fixture'))
    parser.add_argument('--models',type=Path,default=default_models_root())
    parser.add_argument('--summary',type=Path,default=ROOT/'tests/evidence/native_people_summary.json')
    parser.add_argument('--verify-store',type=Path)
    parser.add_argument('--backend')
    args=parser.parse_args()
    if args.verify_store:
        store=PersonalStore(args.verify_store,args.backend)
        print(json.dumps({'ids':[p['id'] for p in store.list()],'gallery_ids':store.gallery(ROUTE).ids}));return 0
    started=time.perf_counter()
    run=args.private_root/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run.mkdir(parents=True,exist_ok=False)
    result={'schema':'proto1_native_personal_fixture.v1','run_path':str(run),'status':'RUNNING',
            'live_enrollment_status':'LIVE_READY_AWAITING_USER','physical_microphone_opened':False,
            'private_audio_vectors_in_summary':False,'route':ROUTE,'checks':{},'native_queries':[]}
    result['execution_source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__).resolve(),ROOT/'app/enrollment_quality.py',ROOT/'app/people.py',ROOT/'app/pipeline.py')}
    try:
        awb=sorted(args.sources.glob('CMU_awb_*.wav'))
        bdl=sorted(args.sources.glob('CMU_bdl_*.wav'))
        if len(awb)<27 or len(bdl)<6:raise ValueError('Expected existing disjoint source inventory unavailable')
        pools={'reference_first':awb[:13],'reference_additional':awb[13:21],
               'fresh_same_person_query':awb[21:],'wrong_person_query':bdl[:6]}
        bound={key:[binding(p) for p in paths] for key,paths in pools.items()}
        all_hashes=[row['sha256'] for rows in bound.values() for row in rows]
        if len(all_hashes)!=len(set(all_hashes)):raise ValueError('Source pool hashes overlap')
        result['source_inventory']=bound
        result['checks']['reference_query_source_hashes_disjoint']='PASS'
        config=pipeline_config(run,args.models)
        models=ResidentModels();speakers=models.enrollment_models(config)
        backend=config.asset('redimnet2_b2_fp32').sha256
        result['model_sha256']=backend
        store=PersonalStore(run/'people',backend)
        q,v=quality(join_files(pools['reference_first']),speakers,config,bound['reference_first'],'reference_first')
        result['reference_quality']={k:value for k,value in q.items() if k not in ('source_provenance','accepted_intervals')}
        if not q['can_save']:
            result['status']='LIMITED';result['limitation']='Frozen quality gate did not admit first unique reference; no threshold changed.'
            return 2
        first=store.save('Fixture voice',v,q,ROUTE)
        identifier=first['id'];result['person_uuid']=identifier
        result['checks']['native_reference_extraction_and_save']='PASS'
        replay=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--verify-store',str(store.root),'--backend',backend],
                              capture_output=True,text=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if replay.returncode:raise RuntimeError(replay.stderr)
        restart=json.loads(replay.stdout)
        if restart['ids']!=[identifier] or restart['gallery_ids']!=[identifier]:raise AssertionError('Restart lost UUID')
        result['checks']['new_process_restart_loads_same_uuid']='PASS'
        second=store.save('Fixture voice',v,q,ROUTE)
        if second['id']==identifier or len(store.list())!=2:raise AssertionError('Duplicate names did not use unique IDs')
        result['checks']['duplicate_names_distinct_uuids']='PASS'
        store.delete(second['id'])
        store.rename(identifier,'Fixture voice renamed')
        if store.list()[0]['name']!='Fixture voice renamed':raise AssertionError('Rename failed')
        result['checks']['rename_persistence']='PASS'
        q2,v2=quality(join_files(pools['reference_additional']),speakers,config,bound['reference_additional'],'reference_additional')
        result['additional_reference_quality']={k:value for k,value in q2.items() if k not in ('source_provenance','accepted_intervals')}
        if q2['can_save']:
            store.save('Fixture voice renamed',v2,q2,ROUTE,person_id=identifier)
            result['checks']['add_disjoint_reference']='PASS' if len(store.list()[0]['references'])==2 else 'FAIL'
        else:result['checks']['add_disjoint_reference']='LIMITED_QUALITY_GATE_REJECTED'
        try:store.save('Fixture voice renamed',v,q,ROUTE,person_id=identifier)
        except ValueError:result['checks']['duplicate_audio_reference_rejected']='PASS'
        else:raise AssertionError('Duplicate reference accepted')
        for label in ('fresh_same_person_query','wrong_person_query'):
            wav=run/(label+'.wav');sf.write(wav,join_files(pools[label]),16000,subtype='PCM_16')
            native=native_query(label,wav,config,models,PersonalStore(store.root,backend))
            result['native_queries'].append(native)
            if native['state']!='COMPLETED' or not native['actual_gallery_score_calls']:
                raise AssertionError('Native query did not execute the personal gallery')
        same,wrong=result['native_queries']
        result['checks']['actual_native_gallery_queries_use_personal_uuid']='PASS' if all(x['gallery_ids_loaded']==[identifier] for x in result['native_queries']) else 'FAIL'
        result['checks']['fresh_same_person_recognition']='PASS' if identifier in same['confirmed_profile_ids_in_final_rows'] else 'LIMITED_NO_CONFIRMED_NAME'
        wrong_named=any(d.get('known_profile_id')==identifier for d in wrong['identity_decisions']) or identifier in wrong['confirmed_profile_ids_in_final_rows']
        result['checks']['wrong_person_preserves_unknown']='FAIL_FALSE_NAME' if wrong_named else 'PASS'
        store.delete(identifier)
        if store.list() or store.gallery(ROUTE).ids:raise AssertionError('Delete retained a matchable UUID')
        result['checks']['delete_invalidates_new_gallery']='PASS'
        result['model_loads']={'speaker':models.speaker_loads,'asr':models.asr_loads,'streams':models.streams}
        result['status']='PASS' if all(v=='PASS' for v in result['checks'].values()) else 'LIMITED'
    except Exception as exc:
        import traceback
        result.update(status='FAIL',error=str(exc),traceback=traceback.format_exc())
    finally:
        result['wall_seconds']=time.perf_counter()-started
        result['finished_utc']=datetime.now(timezone.utc).isoformat()
        atomic_json(args.summary,result)
        atomic_json(run/'TEST_RECEIPT.json',result)
        print(json.dumps({k:result.get(k) for k in ('status','checks','error','wall_seconds','run_path')},indent=2))
    return 0 if result['status']=='PASS' else 2 if result['status']=='LIMITED' else 1


if __name__=='__main__':raise SystemExit(main())
