"""Lossless whole-session host-continuity input. README_CONTINUITY_SEQUENCE.md."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import time
import wave

from common import audio_only, bind, fingerprint, freeze, load, verify
from integrated_bank_plan import exact_jobs
from metric_process import identity, pin
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock

RATE = 16000
TARGET_FRAMES = 1200*RATE
MAX_FRAMES = 1300*RATE
MAX_ACTORS = 8
MAX_SESSIONS = 64
TAP = 'O0'
CLASSES = {'complete_nonoverlap', 'complete_overlap', 'empty_control'}
HERE = Path(__file__).resolve().parent


def inputs():
    preparation = load(HERE/'PREPARATION_V2_CHECK.json')['preparation']; verify(preparation)
    prep = load(preparation['path']); bindings = {Path(b['path']).name:b for b in prep['inputs']+prep['outputs']}
    names = ('AUDIO_ONLY_480.json','EVALUATOR_STRATA.json','EVALUATOR_TRUTH.json','PAIRED_CAPTURE_PROVENANCE.json')
    selected = {n:bindings[n] for n in names}
    for b in selected.values(): verify(b)
    docs = {n:load(b['path']) for n,b in selected.items()}
    require(all(docs[n]['NEVER_PASS_TO_RUNTIME'] is True for n in ('EVALUATOR_STRATA.json','EVALUATOR_TRUTH.json')), 'Evaluator-only boundary required')
    return preparation, selected, docs


def validate_bank(docs):
    jobs = exact_jobs(docs['AUDIO_ONLY_480.json']['jobs'])
    scenes = docs['EVALUATOR_STRATA.json']['scenes']; truths = docs['EVALUATOR_TRUTH.json']['cells']; pairs = docs['PAIRED_CAPTURE_PROVENANCE.json']['pairs']
    require(len(scenes)==240 and len({s['case_id'] for s in scenes})==240 and len(truths)==480
        and {t['job_id'] for t in truths}==set(jobs) and len(pairs)==240 and {p['case_id'] for p in pairs}=={s['case_id'] for s in scenes}, 'Full preparation census differs')
    by_truth={t['job_id']:t for t in truths};by_pair={p['case_id']:p for p in pairs}
    for scene in scenes:
        pair=by_pair[scene['case_id']]; require(len(pair['cells'])==2 and {p['tap'] for p in pair['cells']}=={'O0','O1'}, 'Complete original capture pair required')
        require(type(scene['actor_group_ids']) is list and len(scene['actor_group_ids'])==len(set(scene['actor_group_ids'])), 'Duplicate actor identifiers')
        lengths=[]
        for tap in ('O0','O1'):
            jid='N2_'+scene['case_id']+'_'+tap;job=jobs[jid];truth=by_truth[jid];cell=next(c for c in pair['cells'] if c['tap']==tap)
            require(truth['case_id']==scene['case_id'] and truth['tap']==tap and truth['frames']==job['frames']
                and truth['reference_class']==scene['reference_class'] and truth['complete_reference']==scene['complete_reference'], 'Audio/reference join differs')
            require(cell['audio']['path']==job['audio_path'] and cell['audio']['sha256']==job['audio_sha256']
                and cell['runtime_gain']==job['gain']==1. and cell['gain_already_applied']==(1.4125375446227544 if tap=='O0' else 1.)
                and cell['output_mapping']==truth['output_mapping'], 'Paired capture/gain/timebase differs')
            require(set(truth['scene_cast'])==set(scene['actor_group_ids'])
                and {t['identity'] for t in truth['turns']}<=set(scene['actor_group_ids']), 'Global actor identities differ')
            lengths.append(job['frames'])
        require(lengths[0]==lengths[1], 'Paired outputs do not share the same frame length')
    return jobs, scenes, by_truth, by_pair


def choose(scenes, jobs):
    """Freeze coverage using metadata only, never predictions or model scores."""
    eligible=[r for r in scenes if r['complete_reference'] and r['reference_class'] in CLASSES]
    speech=[r for r in eligible if r['actor_group_ids'] and r['reference_class']!='empty_control']
    def frames(row):return jobs['N2_'+row['case_id']+'_'+TAP]['frames']
    actors=set()
    # Grow a <=8-actor pool by maximum available complete-reference speech time.
    # This permits a stable capacity claim across joins instead of resetting IDs.
    for _ in range(MAX_ACTORS):
        choices={tuple(sorted(actors|set(r['actor_group_ids']))) for r in speech if len(actors|set(r['actor_group_ids']))<=MAX_ACTORS}
        require(bool(choices), 'No capacity-compatible continuity population')
        def support(a):return sum(frames(r) for r in speech if set(r['actor_group_ids'])<=set(a))
        best=min(choices,key=lambda a:(-support(a),len(a),a))
        if set(best)==actors:break
        actors=set(best)
    available=[r for r in eligible if set(r['actor_group_ids'])<=actors]
    def features(r):
        return {(k,str(r[k])) for k in ('family_id','reference_class','room','orientation','relative_source_level_db','requested_snr_db','has_short_turn')}
    chosen=[];covered=set();total=0
    while total<TARGET_FRAMES:
        candidates=[r for r in available if r not in chosen and (r['reference_class']!='empty_control'
            or not any(c['reference_class']=='empty_control' for c in chosen)) and total+frames(r)<=MAX_FRAMES]
        require(candidates and len(chosen)<MAX_SESSIONS, 'Insufficient whole-session duration under capacity/length bounds')
        pick=min(candidates,key=lambda r:(-len(features(r)-covered),r['case_id']))
        chosen.append(pick);covered|=features(pick);total+=frames(pick)
    require({'complete_nonoverlap','complete_overlap','empty_control'}<={r['reference_class'] for r in chosen}, 'Continuity requires speech, overlap and an empty control')
    return chosen


def shifted_turn(turn, offset, frames, occurrence):
    value=deepcopy(turn)
    require(value['word_times'] is None, 'Exact word-time transformation not implemented; do not silently discard it')
    def shift(pair):
        require(type(pair) is list and len(pair)==2 and all(type(x) is int for x in pair)
            and 0<=pair[0]<pair[1]<=frames, 'Reference interval outside original session')
        return [x+offset for x in pair]
    value['turn_id']=f'{occurrence:03d}:'+value['turn_id']
    value['file_support_samples']=shift(value['file_support_samples'])
    value['activity_ranges_samples_estimated']=[shift(pair) for pair in value['activity_ranges_samples_estimated']]
    # Speaker identity, source identity, full raw/canonical transcript, window
    # availability and timing scope are deliberately preserved unchanged.
    return value


def build(docs, bindings):
    jobs,scenes,truths,pairs=validate_bank(docs);chosen=choose(scenes,jobs);segments=[];turns=[];offset=0;actors=set()
    for i,scene in enumerate(chosen):
        job=jobs['N2_'+scene['case_id']+'_'+TAP];truth=truths[job['job_id']];frames=job['frames']
        segments.append(dict(index=i,job=deepcopy(job),destination_start_frame=offset,destination_end_frame=offset+frames,
            original_capture_id=pairs[scene['case_id']]['capture_id'],reference_class=truth['reference_class']))
        turns.extend(shifted_turn(t,offset,frames,i) for t in truth['turns']);actors.update(scene['actor_group_ids']);offset+=frames
    key=fingerprint(dict(inputs=bindings,segments=segments));sequence_id='N4_CONTINUITY_'+TAP+'_'+key[:16]
    grids={truths[s['job']['job_id']]['activity_grid_s'] for s in segments}
    require(len(grids)==1, 'Mixed estimated activity grids require a separate evaluator')
    truth=dict(schema='n4-continuity-evaluator-truth-v1',NEVER_PASS_TO_RUNTIME=True,job_id=sequence_id,case_id=sequence_id,
        tap=TAP,frames=offset,reference_class='complete_overlap',complete_reference=True,turns=turns,scene_cast=sorted(actors),
        exact_word_timing='UNAVAILABLE',activity_grid_s=next(iter(grids)),
        output_mapping='Each original output mapping is already applied within its segment; add only the exact concatenation frame offset',
        segment_references=[dict(index=i,original_job_id=s['job']['job_id'],destination_start_frame=s['destination_start_frame'],
            original_output_mapping=deepcopy(truths[s['job']['job_id']]['output_mapping'])) for i,s in enumerate(segments)])
    plan=dict(schema='n4-continuity-sequence-plan-v1',status='PREPARED_INPUT_ONLY',inputs=deepcopy(bindings),sequence_id=sequence_id,
        tap=TAP,segments=segments,frames=offset,sample_rate_hz=RATE,actor_capacity=MAX_ACTORS,distinct_actor_count=len(actors),
        target_seconds=1200,actual_seconds=offset/RATE,reference_classes=dict(Counter(s['reference_class'] for s in segments)),
        original_sessions=len(segments),joins=len(segments)-1,gain=1.,lossless_pcm_concatenation=True,
        add_silence=False,crossfade=False,resample=False,trim=False,reset_at_joins=False,adaptation=False,
        actual_source_execution=False,actual_continuity_test=False,integrated_N4_cells=0,
        limitations=['Whole captured sessions are concatenated for host software continuity; this is not continuous physical XVF state.',
            'The first whole-session boundary after 20 minutes is retained; no words or waveform tail are truncated.',
            'Original actor IDs remain global across joins; no seat/session renaming can reduce the <=8-actor union.',
            'Selection uses complete-reference metadata coverage, not model performance; incomplete ambient scenes remain covered by the main bank.',
            'O0 is the fixed continuity tap; O1 continuity is not implied by paired-bank coverage.',
            'Repeated voices/text are dependent engineering evidence, not independent samples.',
            'Approximate activity stays approximate; ordinary WER over overlapping speaker text is unavailable.',
            'No candidate, application launch, source delivery, stop/restart or release acceptance is established.'])
    return plan,truth


def materialize(plan, path, *, checkpoint=None):
    """Copy exact admitted PCM16 bytes; no resampling, mixing, padding or decoding."""
    require(not path.exists() and plan['schema']=='n4-continuity-sequence-plan-v1' and plan['status']=='PREPARED_INPUT_ONLY'
        and TARGET_FRAMES<=plan['frames']<=MAX_FRAMES and 0<len(plan['segments'])<=MAX_SESSIONS, 'Fresh bounded sequence required')
    offset=0;copies=[];pcm=hashlib.sha256()
    with path.open('xb') as raw:
        with wave.open(raw,'wb') as destination:
            destination.setnchannels(1);destination.setsampwidth(2);destination.setframerate(RATE);destination.setnframes(plan['frames'])
            for i,segment in enumerate(plan['segments']):
                if checkpoint:checkpoint()
                job=audio_only(segment['job']);before=bind(job['audio_path'])
                require(before['sha256']==job['audio_sha256'] and job['tap']==TAP and job['gain']==1.
                    and segment['index']==i and segment['destination_start_frame']==offset
                    and segment['destination_end_frame']==offset+job['frames'], 'Sequence source/hash/offset differs')
                count=0;source_pcm=hashlib.sha256()
                with wave.open(job['audio_path'],'rb') as source:
                    require((source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getnframes(),source.getcomptype())
                        ==(1,2,RATE,job['frames'],'NONE'), 'Original mono 16-kHz PCM16 required')
                    while count<job['frames']:
                        data=source.readframes(min(RATE*4,job['frames']-count))
                        require(data and len(data)%2==0 and count+len(data)//2<=job['frames'], 'Truncated or oversized source PCM')
                        destination.writeframesraw(data);pcm.update(data);source_pcm.update(data);count+=len(data)//2
                    require(not source.readframes(1), 'Unexpected source tail')
                verify(before);offset+=count
                copies.append(dict(index=i,original_waveform=before,frames=count,pcm_sha256=source_pcm.hexdigest()))
            require(offset==plan['frames'], 'Sequence frame census differs')
    require(path.stat().st_size==44+2*offset, 'Unexpected PCM output encoding')
    rebuilt=hashlib.sha256()
    with wave.open(str(path),'rb') as source:
        require(source.getnframes()==offset, 'Written sequence header differs')
        while True:
            data=source.readframes(RATE*4)
            if not data:break
            rebuilt.update(data)
    require(rebuilt.hexdigest()==pcm.hexdigest(), 'Written sequence PCM differs from source stream')
    job=audio_only(dict(job_id=plan['sequence_id'],audio_path=str(path.resolve()),audio_sha256=bind(path)['sha256'],frames=offset,
        sample_rate_hz=RATE,gain=1.,reset_between_scenes=True,tap=TAP))
    return job,dict(status='COPIED_EXACT_SAVED_PCM_ONLY',output=bind(path),frames=offset,pcm_sha256=pcm.hexdigest(),segments=copies,
        reset_scope='Initial sequence reset only; the application receives one file and no internal join commands',actual_source_execution=False)


def code_bindings():
    return [bind(HERE/name) for name in ('continuity_sequence.py','test_continuity_sequence.py','probe_continuity_sequence.py',
        'README_CONTINUITY_SEQUENCE.md','common.py','integrated_bank_plan.py','metric_process.py','review_scoring_bank.py','scoring_bank.py','asr_full_bank.py')]


def prepare(output):
    process=pin();started=time.monotonic();local=Path('G:/Just_Peachy_N1/20260924_campaign/local')
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'), 'Fresh private output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output,local,started,720);inventory=shared_allowance(local);code=code_bindings()
        qualification=load(HERE/'CONTINUITY_SEQUENCE_CHECK_V1.json')
        require(qualification['status']=='PASS_CONTINUITY_SEQUENCE_DEVELOPMENT_ONLY' and qualification['code']==code, 'Qualified sequence implementation required')
        preparation,bindings,docs=inputs();plan,truth=build(docs,bindings)
        for b in code:verify(b)
        freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,preparation=preparation,inputs=bindings,inventory=inventory,
            qualification=bind(HERE/'CONTINUITY_SEQUENCE_CHECK_V1.json'),source_execution_authorized=False))
        freeze(output/'PLAN.json',plan)
        try:
            job,copied=materialize(plan,output/'CONTINUITY_O0.wav',checkpoint=lambda:guard(output,local,started,720))
            freeze(output/'INFERENCE_AUDIO_ONLY.json',dict(schema='n4-audio-only-v1',jobs=[job]))
            freeze(output/'EVALUATOR_TRUTH.json',dict(schema='n4-evaluator-truth-v1',NEVER_PASS_TO_RUNTIME=True,cells=[truth]))
            freeze(output/'COPY_RECEIPT.json',copied)
            for b in code+list(bindings.values()):verify(b)
            guard(output,local,started,720)
            freeze(output/'RESULT.json',dict(status='PREPARED_LOSSLESS_CONTINUITY_INPUT_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),plan=bind(output/'PLAN.json'),audio_only=bind(output/'INFERENCE_AUDIO_ONLY.json'),
                evaluator_truth=bind(output/'EVALUATOR_TRUTH.json'),copy_receipt=bind(output/'COPY_RECEIPT.json'),
                sessions=plan['original_sessions'],seconds=plan['actual_seconds'],distinct_actor_count=plan['distinct_actor_count'],
                actual_application_spawned=False,actual_source_execution=False,actual_continuity_test=False,integrated_N4_cells=0,N4_accepted=False))
            print('Prepared lossless saved-session continuity input; no application or audio playback',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_SEQUENCE_PREPARATION_PRESERVED',error_type=type(exc).__name__,admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    prepare(parser.parse_args().output)
