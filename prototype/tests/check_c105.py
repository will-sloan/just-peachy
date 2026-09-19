"""One bounded C105 native replay and pinned post-hoc scorer; see README_C105.md."""
from __future__ import annotations
import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
SIM=ROOT.parent/'XVF 3800 Testing/XVF Integration Real World RIRs/simulation'
R7=SIM/'reports/S7/20260917T141700Z'
SCORE=R7/'application/c105_scoring_v1/SCORE.json'
SOURCE=Path(r'G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_08_07\O0.wav')


def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def bind(path):
    p=Path(path)
    return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def rows(path):return [json.loads(s) for s in Path(path).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec)
    sys.modules[name]=obj;spec.loader.exec_module(obj);return obj
def source_bindings():
    return {str(p.relative_to(ROOT)).replace('\\','/'):bind(p)['sha256']
            for folder in ('app','vendor','config') for p in sorted((ROOT/folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}


def replay(folder):
    folder.mkdir(parents=True,exist_ok=False)
    sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
    from app.controller import Controller
    from app.paths import default_models_root
    before=source_bindings();started=time.perf_counter()
    c=Controller(folder/'private_data',default_models_root())
    failure=None
    try:
        c.switch(mode='anonymous_conversation',recipe='balanced',tap='O0')
        c.start_file(SOURCE)
        deadline=time.monotonic()+110
        while time.monotonic()<deadline:
            if c.error:raise RuntimeError(c.error)
            if c.metrics['completed_sessions']==1 and c.state=='STOPPED':break
            time.sleep(.05)
        else:raise TimeoutError('C105 source/consumer did not close within110seconds')
        with c.lock:raw=deepcopy(list(c.rows.values()))
        projected=c.snapshot()['rows'];session=Path(c.metrics['last_session'])
        if len(raw)!=3:raise AssertionError('Expected three complete C105 utterance rows')
        write(folder/'CONTROLLER_RAW_ROWS.json',raw)
        write(folder/'CONTROLLER_PROJECTED_ROWS.json',projected)
        after=source_bindings()
        receipt={'status':'PASS','session':str(session),'input_audio':bind(SOURCE),
                 'full_token_rows':bind(folder/'CONTROLLER_RAW_ROWS.json'),
                 'projected_rows':bind(folder/'CONTROLLER_PROJECTED_ROWS.json'),
                 'source_bindings_before':before,'source_bindings_after':after,'source_unchanged':before==after,
                 'mode':'anonymous_conversation','recipe':'balanced','tap':'O0','models_loaded':c.metrics.get('model_cache'),
                 'source_frames':c.engine._journal.committed_samples,'wall_seconds':time.perf_counter()-started,
                 'scope':'Actual native controller rows and projection; no Tk widget acknowledgment claimed',
                 'concurrent_workload':'Separate GUI soak active; this replay is a correctness check, not an isolated performance benchmark',
                 'captured_utc':datetime.now(timezone.utc).isoformat()}
        write(folder/'CAPTURE.json',receipt)
    except Exception as exc:
        failure=exc
    finally:
        c.close();deadline=time.monotonic()+100
        while not c.closed and time.monotonic()<deadline:time.sleep(.05)
        if not c.closed:raise RuntimeError('C105 controller did not release ownership')
    if failure:raise failure
    return folder/'CAPTURE.json'


def score(capture_path,summary):
    historic=load(SCORE);capture=load(capture_path)
    scorer_binding=historic['scorer'];assert bind(scorer_binding['path'])==scorer_binding
    assert scorer_binding['sha256']=='4260ba5d1ac59f1e5fc057b7fa105fd1f525982ccf546353b5f283c054f092d4'
    sys.path.insert(0,str(Path(scorer_binding['path']).parent))
    scorer=module(scorer_binding['path'],'proto1_c105_pinned_scorer');dep=scorer.dependencies()
    assert dep['sources']==historic['dependencies']
    assert bind(historic['reference']['path'])==historic['reference']
    reference=load(historic['reference']['path']);scorer.validate_reference(reference)
    assert capture['input_audio']['sha256']==reference['input_audio']['sha256']
    assert capture['source_frames']==715127 and capture['source_unchanged']
    for key in ('full_token_rows','projected_rows'):assert bind(capture[key]['path'])==capture[key]
    raw=load(capture['full_token_rows']['path']);projected=load(capture['projected_rows']['path'])
    session=Path(capture['session']);finals=rows(session/'latest_labelled_transcript.jsonl')
    finalmap={r['utterance_id']:r for r in finals};rawmap={r['utterance_id']:r for r in raw}
    assert set(rawmap)==set(finalmap) and len(finalmap)==3
    norm=dep['normalize'];refs=defaultdict(list);hyp=defaultdict(list);segments=[];flat=[]
    for turn in reference['projected_turns']:refs[turn['metadata_identity']].extend(norm(turn['transcript']).split())
    all_token_ids=[];casing_ok=True;ids=sorted(finalmap)
    for uid in ids:
        row=rawmap[uid];final=finalmap[uid];tokens=row['token_ids']
        assert row['final'] and row['text']==final['text']
        assert len(tokens)==len(set(tokens))
        assert [t for p in row['segments'] for t in p['token_ids']]==tokens
        actual=[]
        for part in row['segments']:
            start,end=part['raw_character_range'];assert part['raw_text']==final['text'][start:end]
            words=norm(part['raw_text']).split();actual.extend(words)
            label=part.get('anonymous_label') or 'Unknown'
            if part.get('track_id') is None:label='Unknown'
            hyp[label].extend(words)
            segments.append({'utterance_id':uid,'segment_id':part['segment_id'],'track_id':part.get('track_id'),
                             'anonymous_label':label,'word_count':len(words),'token_count':len(part['token_ids']),
                             'raw_text':part['raw_text'],'evidence_ids':part.get('evidence_ids'),
                             'application_scope':part.get('application_scope'),
                             'current_source_permission':part.get('current_source_permission')})
        assert actual==norm(final['text']).split();flat.extend(actual);all_token_ids.extend(tokens)
        projected_parts=[p for p in projected if p['utterance_id']==uid]
        assert [w for p in projected_parts for w in norm(p['raw_asr_text']).split()]==actual
        assert [p['label'] for p in projected_parts]==[p.get('anonymous_label') or 'Unknown' for p in row['segments']]
        for part in projected_parts:
            casing_ok &= norm(part['provisional_display_text'])==norm(part['raw_asr_text'])
            if part['final_punctuated_display_text']:
                casing_ok &= norm(part['final_punctuated_display_text'])==norm(part['raw_asr_text'])
        if final.get('punctuation'):assert final['punctuation']['raw_text']==final['text']
    assert len(all_token_ids)==len(set(all_token_ids)) and len(flat)==41 and casing_ok
    current_raw=' '.join(flat)
    assert current_raw==historic['cells'][0]['latest_policy']['entire_raw_normalized']
    metric=dep['rate'](dep['cpwer']({k:' '.join(v) for k,v in refs.items()},
                                  {k:' '.join(v) for k,v in hyp.items()}),len(flat),
                       'PROTO1_FINAL_CONTROLLER_SUPPORTED_SEGMENT_CPWER',
                       'Actual retained native controller token partitions and final projection; not a new Tk widget acknowledgment.')
    lexical=scorer.text_metrics(reference,finals,dep)['serialized_words']
    assert metric['word_counts']['errors']==lexical['counts']['errors']==1
    assert metric['word_counts']['reference_words']==lexical['counts']['reference_words']==41
    owners=[finalmap[uid]['tracker_id'] for uid in ids]
    assert owners[0]==owners[2] and owners[0]!=owners[1]
    checks={}
    seed=R7/'source_epochs/gui_startup_v3/edge_speech_pipeline'
    for name in ('research_s7_policy.py','research_s7_presentation.py','research_scheduler_v3.py','research_evidence_v3.py','research_scheduler.py','research_s6d.py'):
        original=bind(seed/name);current=bind(ROOT/'vendor/edge_speech_pipeline'/name)
        expected=capture['source_bindings_before']['vendor/edge_speech_pipeline/'+name]
        checks[name]={'s7_sha256':original['sha256'],'prototype_sha256':current['sha256'],
                      'native_execution_sha256':expected,'byte_identical':original['sha256']==current['sha256']==expected}
    assert all(row['byte_identical'] for row in checks.values())
    runtime={'s7':bind(seed/'runtime.py'),'prototype':bind(ROOT/'vendor/edge_speech_pipeline/runtime.py')}
    shared=[p for p in (ROOT/'vendor/edge_speech_pipeline').iterdir() if p.is_file() and (seed/p.name).is_file()]
    changed=[p.name for p in shared if bind(p)['sha256']!=bind(seed/p.name)['sha256']]
    assert changed==['runtime.py']
    result={'schema':'proto1_c105_regression.v1','status':'PASS','lexical':lexical,'anonymous_attribution':metric,
            'reference_words':41,'raw_words':41,'full_raw_word_partition_verified':True,
            'full_unique_token_partition_verified':True,'case_and_punctuation_preserve_normalized_raw_words':True,
            'first_and_third_return_same_owner':True,'utterance_owners':owners,'segments':segments,
            'historic_corrected_gui_cpwer':next(c['actual_latest_gui']['cpwer'] for c in historic['cells'] if c['job_id'].startswith('v03_')),
            'input_audio':capture['input_audio'],'native_capture_receipt':bind(capture_path),
            'source_epoch':{'native_source_unchanged':capture['source_unchanged'],'policy_presentation_checks':checks,'runtime_adaptation':runtime,
                            'all_shared_vendor_files':len(shared),'byte_identical_vendor_files':len(shared)-len(changed),'changed_vendor_files':changed},
            'scorer':scorer_binding,'dependencies':dep['sources'],'reference':historic['reference'],
            'scoring_script':bind(__file__),'model_inferences_started_by_scoring':0,
            'scope':capture['scope'],'concurrent_workload':capture['concurrent_workload'],
            'historical_panel_limit':'Initial panel_v1 rolling events no longer retain token partitions for first two utterances; this one final-source native replay preserved full controller rows before closure.',
            'finished_utc':datetime.now(timezone.utc).isoformat()}
    write(summary,result)
    print(json.dumps({'status':result['status'],'lexical_errors':lexical['counts']['errors'],
                      'anonymous_errors':metric['word_counts']['errors'],'reference_words':41,'owners':owners,
                      'token_partition_verified':True,'policy_sources_identical':True,'summary':str(summary)},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-replay',action='store_true')
    parser.add_argument('--run-dir',type=Path,default=Path(r'G:\Just_Peachy_PROTO1\acceptance\c105_final_v1'))
    parser.add_argument('--capture',type=Path)
    parser.add_argument('--summary',type=Path,default=ROOT/'tests/evidence/C105_REGRESSION.json')
    args=parser.parse_args()
    capture=replay(args.run_dir) if args.native_replay else args.capture or args.run_dir/'CAPTURE.json'
    if args.native_replay:
        interpreter=SIM/'staging/s5_text_metrics/analysis_env/Scripts/python.exe'
        completed=subprocess.run([str(interpreter),str(Path(__file__).resolve()),'--capture',str(capture),'--summary',str(args.summary)],timeout=60)
        return completed.returncode
    score(capture,args.summary);return 0


if __name__=='__main__':raise SystemExit(main())
