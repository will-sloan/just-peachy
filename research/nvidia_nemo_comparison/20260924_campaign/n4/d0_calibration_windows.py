"""Collect genuine D0 short/mature C evidence; see README_D0_CALIBRATION.md."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''

from common import load, bind, freeze, fingerprint, verify

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LOCAL = ROOT.parent/'local'
SPEC = importlib.util.spec_from_file_location('_d0_supervisor', HERE.parent/'supervision/supervisor.py')
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)
MAX_OUTPUT_BYTES = 1024**3


def select_c(manifest, protection=None):
    """Evaluator preparation only: identities never enter the lane manifest."""
    all_rows = manifest['windows'] + manifest['diagnostic_Q_windows']
    c = [r for r in manifest['windows'] if r['role'] == 'C']
    if not c or len({r['window_id'] for r in c}) != len(c):
        raise ValueError('Unique nonempty C population required')
    if protection is not None:
        audit=protection['material']['leakage_audit']
        if (not audit['known_parent_path_prompt_and_exact_bytes_checked']
                or any(audit['exact_intersections'].values())):
            raise ValueError('Protected E/C/Q leakage audit failed')
        accepted={r['source_id']:r for r in protection['material']['accepted_sources']}
        for row in c:
            original=accepted[row['source_id']]
            if (original['s6c_role']!='C' or original['identity']!=row['identity']
                    or original['decoded_pcm_sha256']!=row['unique_source_pcm_sha256']):
                raise ValueError('C source differs from protected split')
        # Processed E/Q windows do not each carry clean-source IDs. Their
        # original source/PCM/text exclusion is bound by the verified ECQ audit.
        all_rows=[r for r in all_rows if r['domain']=='clean_source']
    for role in ('E', 'Q'):
        other = [r for r in all_rows if r['role'] == role]
        for key in ('source_id', 'unique_source_pcm_sha256'):
            if any(not r.get(key) for r in c+other):
                raise ValueError('Missing protected source identity')
            if {r[key] for r in c} & {r[key] for r in other}:
                raise ValueError('C overlaps protected '+role+' '+key)
    jobs, labels = [], []
    for r in c:
        if r['domain'] != 'clean_source' or r['sample_rate_hz'] != 16000 or r['gain'] != 1:
            raise ValueError('Only unchanged clean C mono16k waveforms are admitted')
        if not r['whole_clip'] or r['start_sample'] != 0 or r['end_sample'] <= 0:
            raise ValueError('Independent whole-clip reset required')
        jobs.append(dict(window_id=r['window_id'], audio={k:r['audio'][k] for k in ('path','sha256','bytes')}, frames=r['end_sample'],
                         sample_rate_hz=16000, gain=1, reset=True))
        labels.append({k:r[k] for k in ('window_id','identity','source_id','unique_source_pcm_sha256')})
    return jobs, labels


def validate_job(job):
    if set(job) != {'window_id','audio','frames','sample_rate_hz','gain','reset'}:
        raise ValueError('Audio-only lane firewall failed')
    if job['sample_rate_hz'] != 16000 or job['gain'] != 1 or job['reset'] is not True:
        raise ValueError('Invalid audio format/gain/reset')
    if type(job['frames']) is not int or not 0 < job['frames'] <= 120*16000:
        raise ValueError('C clip exceeds bounded independent session')
    if not job['window_id'] or any(not (c.isalnum() or c == '_') for c in job['window_id']):
        raise ValueError('Invalid C clip identifier')


def guard(output, state):
    policy = load(state/'campaign.json')
    if datetime.now(timezone.utc) >= datetime.fromisoformat(policy['target_utc']) - timedelta(hours=12):
        raise TimeoutError('Packaging reserve reached')
    _, low = supervisor.disk_reserves(policy)
    if low:
        raise RuntimeError('Disk reserve breached: '+str(low))
    size = sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    # Reserve a bounded complete clip before every dispatch; no existing data is deleted.
    if size + 16*1024**2 > MAX_OUTPUT_BYTES:
        raise RuntimeError('One GiB calibration allocation exhausted')


def prepare(args):
    receipt = load(args.source_receipt)
    source = Path(receipt['prototype'])
    for rel, row in receipt['files'].items():
        actual = bind(source/rel)
        if actual['sha256'] != row['sha256'] or actual['bytes'] != row['bytes']:
            raise ValueError('Frozen application source changed: '+rel)
    manifest = load(args.manifest)
    # The accepted N2 extraction contracts bind these exact protected splits.
    for encoder in ('E0','E1'):
        admission = load(LOCAL/'n2/evaluation/component'/encoder/'ADMISSION.json')
        if admission['manifest'] != bind(args.manifest):
            raise ValueError('Accepted N2 split manifest differs')
    preparation=load(args.manifest.with_name('MANIFEST_RECEIPT.json'))
    if bind(args.manifest) not in preparation['outputs']:
        raise ValueError('Split preparation receipt differs')
    ecq_binding=next(r for r in preparation['inputs'] if Path(r['path']).name=='ECQ_BINDINGS.json')
    verify(ecq_binding); protection=load(ecq_binding['path'])
    query_binding=protection['material']['query_manifest']; verify(query_binding)
    jobs, labels = select_c(manifest,protection)
    for job in jobs:
        validate_job(job)
        verify(job['audio'])
    if args.output.exists():
        raise ValueError('Preserve earlier calibration attempts; choose a fresh output')
    args.output.mkdir(parents=True)
    audio_path = args.output/'C_AUDIO_ONLY.json'
    freeze(audio_path, dict(schema='n4-d0-C-audio-v1', jobs=jobs))
    freeze(args.output/'C_LABELS_EVALUATOR_ONLY.json', dict(schema='n4-d0-C-labels-v1', rows=labels,
        split_manifest=bind(args.manifest), protected_E_Q_source_overlap=0,
        protected_split=ecq_binding, query_manifest=query_binding,
        leakage_audit=protection['material']['leakage_audit']))
    runtime = load(args.runtime)
    titan = Path(runtime['titanet_manifest'])
    tdoc = load(titan)
    model_paths = [titan, *(titan.parent/tdoc[k]['filename'] for k in ('onnx','frontend'))]
    assets = load(source/'config/assets.json')
    for row in assets:
        if row['component_id'] in ('redimnet2_b2_fp32','pyannote_segmentation_3_0_fp32'):
            model_paths.append(args.models/row['sha256']/row['filename'])
    code = [Path(__file__), HERE/'common.py', HERE/'test_d0_calibration.py',
            HERE/'README_D0_CALIBRATION.md', HERE.parent/'supervision/supervisor.py']
    contract = dict(schema='n4-d0-C-extraction-v1', source_receipt=bind(args.source_receipt),
        source=str(source), audio=bind(audio_path), runtime=bind(args.runtime), models_root=str(args.models),
        model_bindings=[bind(p) for p in model_paths], code=[bind(p) for p in code],
        expected_clips=len(jobs), expected_encoder_clip_cells=2*len(jobs),
        recipe='balanced', mode='anonymous_conversation', tap='O0',
        cadence_requirement='fixed with cues disabled; no tracker-dependent query selection',
        boundary='reset at whole C source only; no evaluator activity/turn/text boundaries',
        execution='existing run_speaker_lane_v3; accelerated serial neural lane; no ASR, tracker or names',
        cpu_affinity=[4], threads=1, gpu=False, max_output_bytes=MAX_OUTPUT_BYTES,
        state=str(args.state), output=str(args.output), source_changed=False,
        nominal_or_calibrated_profile_changed=False, completed_N4_integrated_cells=0,
        calibration_claim='COLLECTION_ONLY; clean C score units cannot qualify processed-query naming')
    freeze(args.output/'ADMISSION.json', contract)
    freeze(args.output/'worker.json', dict(argv=[sys.executable,'-B',str(Path(__file__)),
        'run','--admission',str(args.output/'ADMISSION.json')],cwd=str(ROOT)))
    print(json.dumps(dict(status='PREPARED_NOT_STARTED', clips=len(jobs),
        admission=bind(args.output/'ADMISSION.json'), worker=bind(args.output/'worker.json'))))


class AudioJournal:
    def __init__(self, samples):
        self.samples=samples; self.committed_samples=len(samples); self.finished=True
        self.duration_sec=len(samples)/16000
    def read(self, cursor, size):
        return self.samples[cursor:cursor+size]


class FixedScheduler:
    def push(self, event, lane):
        pass
    def tracking_context(self, end):
        raise AssertionError('Tracker-dependent cadence is not admitted to isolated calibration')


class LaneCapture:
    """Run the unchanged lane on audio only; raw probabilities and failures persist."""
    def __init__(self, profile, config, audio, stream):
        if profile.embedding.cadence_policy != 'fixed' or profile.embedding.cadence_cues_enabled:
            raise ValueError('Only tracker-independent fixed cadence may be reused')
        self._research_profile=profile; self.config=config; self.stream=stream
        self._identity_journal=self._journal=AudioJournal(audio)
        self._scheduler=FixedScheduler(); self._state='RUNNING'; self._telemetry={}
        self._started_monotonic=time.perf_counter(); self.vectors=[]; self.error=None
        self._spatial_provider=None; self.segmentation_calls=0
    def _s7_model_call(self, role, end, function, *args, **kwargs):
        if role not in ('segmentation','embedding'):
            raise AssertionError('Unexpected model call')
        return function(*args, **kwargs)
    def _scheduler_advance(self, *args):
        pass
    def _fail(self, error):
        self.error=error; self._state='FAILED'
    def _emit(self, kind, end, payload):
        # No duplicate vector observation or waveform archive. Every emitted
        # segmentation frame and admission rejection remains available privately.
        if kind in ('research_segmentation','research_embedding_admission','research_embedding'):
            self.stream.write(json.dumps(dict(event_type=kind, source_time_sec=end, payload=payload),
                separators=(',',':'), allow_nan=False)+'\n')
        if kind == 'research_segmentation':
            self.segmentation_calls+=1
        if kind == 'research_embedding':
            first=round(payload['source_start_sec']*16000); last=round(end*16000)
            wave=self._journal.samples[first:last]
            if len(wave) != payload['admission']['samples'] or first < 0:
                raise ValueError('Embedding receptive waveform span changed')
            self.vectors.append(dict(start_sample=first,end_sample=last,
                waveform_sha256=hashlib.sha256(wave.astype('<f4').tobytes()).hexdigest(),
                evidence_kind=payload['evidence_kind'], clean_intervals=payload['clean_intervals'],
                normalized_embedding=payload['normalized_embedding']))


def verify_contract(path):
    contract=load(path)
    for row in [contract['source_receipt'],contract['audio'],contract['runtime'],
                *contract['model_bindings'],*contract['code']]:
        verify(row)
    receipt=load(contract['source_receipt']['path'])
    for rel,row in receipt['files'].items():
        actual=bind(Path(contract['source'])/rel)
        if actual['sha256'] != row['sha256'] or actual['bytes'] != row['bytes']:
            raise ValueError('Immutable source changed: '+rel)
    return contract


def extract(args):
    import psutil
    import soundfile as sf
    import numpy as np
    process=psutil.Process(); process.cpu_affinity([4]); process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    contract=verify_contract(args.admission); output=Path(contract['output']); state=Path(contract['state'])
    guard(output,state)
    source=Path(contract['source']); sys.path[:0]=[str(source),str(source/'vendor')]
    from app.pipeline import effective_profile
    from app.paths import pipeline_config
    from app.n2_models import N2SpeakerModels
    from edge_speech_pipeline.research_evidence_v3 import run_speaker_lane_v3
    profile=effective_profile('balanced','anonymous_conversation','O0')
    config=profile.apply(pipeline_config(output/'unused-private-root',Path(contract['models_root'])))
    if config.speaker_threads != 1:
        raise ValueError('One model thread required')
    runtime=load(contract['runtime']['path'])
    destination=output/args.encoder; destination.mkdir(exist_ok=False)
    started=time.monotonic(); model=N2SpeakerModels(config,args.encoder,runtime,pyannote=True)
    jobs=load(contract['audio']['path'])['jobs']; results=[]
    for index,job in enumerate(jobs):
        guard(output,state); validate_job(job); verify(job['audio'])
        info=sf.info(job['audio']['path'])
        if info.frames != job['frames'] or info.samplerate != 16000 or info.channels != 1:
            raise ValueError('C audio header differs')
        audio,rate=sf.read(job['audio']['path'],dtype='float32')
        if rate != 16000 or audio.ndim != 1 or len(audio) != job['frames'] or not np.isfinite(audio).all():
            raise ValueError('C waveform invalid')
        cell=destination/job['window_id']; cell.mkdir()
        with (cell/'LANE_EVENTS.jsonl').open('x',encoding='utf-8',newline='\n') as stream:
            engine=LaneCapture(profile,config,audio,stream)
            run_speaker_lane_v3(engine,model)
        valid=engine.error is None and engine._telemetry.get('identity_audio_samples') == len(audio)
        result=dict(status='COMPLETE' if valid else 'FAILED', job=job, encoder=args.encoder,
            namespace=model.namespace, profile_sha256=fingerprint(profile.to_dict()),
            admission_sha256=bind(args.admission)['sha256'],vectors=engine.vectors,
            segmentation_calls=engine.segmentation_calls,telemetry=engine._telemetry,error=engine.error,
            events=bind(cell/'LANE_EVENTS.jsonl'), latency_qualification=False)
        freeze(cell/'RESULT.json',result); results.append(bind(cell/'RESULT.json'))
        completed=(len(jobs) if args.encoder=='E1' else 0)+index+1
        supervisor.atomic(state/'panel_progress.json',dict(completed=completed,total=2*len(jobs),
            elapsed_seconds=time.monotonic()-started,stage='N4_C_WINDOW_COLLECTION',encoder=args.encoder))
        if not valid:
            raise RuntimeError('C lane failed; original evidence retained: '+str(engine.error))
    freeze(destination/'RESULT.json',dict(status='COMPLETE',completed=len(results),total=len(jobs),
        cells=results,namespace=model.namespace,profile=profile.to_dict(),elapsed_seconds=time.monotonic()-started,
        cpu_affinity=process.cpu_affinity(),resource_scope='isolated lane collection; no complete-stack claim'))


def run(args):
    import psutil
    process=psutil.Process(); process.cpu_affinity([14]); process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    contract=verify_contract(args.admission); output=Path(contract['output'])
    with supervisor.lock(output/'owner.lock'):
        receipt=dict(status='RUNNING',owner=dict(pid=process.pid,create_time=process.create_time()),
            admission=bind(args.admission),completed=0,total=contract['expected_encoder_clip_cells'],
            integrated_N4_cells=0,started_utc=supervisor.now())
        supervisor.atomic(output/'RESULT.json',receipt)
        try:
            for encoder in ('E0','E1'):
                guard(output,Path(contract['state']))
                argv=[sys.executable,'-B',str(Path(__file__)),'extract','--admission',str(args.admission),'--encoder',encoder]
                with (output/(encoder+'.log')).open('x',encoding='utf-8') as log:
                    child=subprocess.Popen(argv,cwd=str(ROOT),stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    receipt.update(child=dict(pid=child.pid,create_time=psutil.Process(child.pid).create_time()),encoder=encoder)
                    supervisor.atomic(output/'RESULT.json',receipt)
                    code=child.wait()
                if code != 0: raise RuntimeError(encoder+' collection exit '+str(code))
                result=load(output/encoder/'RESULT.json')
                if result['status'] != 'COMPLETE' or result['completed'] != contract['expected_clips']:
                    raise ValueError('Incomplete C collection')
                receipt['completed']+=result['completed']
            receipt.update(status='COLLECTED_REQUIRES_CALIBRATION_REVIEW',child=None,
                encoders=[bind(output/e/'RESULT.json') for e in ('E0','E1')],finished_utc=supervisor.now())
        except BaseException as exc:
            receipt.update(status='FAILED',error=repr(exc),finished_utc=supervisor.now())
            raise
        finally:
            supervisor.atomic(output/'RESULT.json',receipt)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    for name in ('source-receipt','manifest','runtime','models','output','state'):
        p.add_argument('--'+name,type=Path,required=True)
    for mode in ('run','extract'):
        p=sub.add_parser(mode); p.add_argument('--admission',type=Path,required=True)
        if mode=='extract': p.add_argument('--encoder',choices=('E0','E1'),required=True)
    args=parser.parse_args()
    {'prepare':prepare,'run':run,'extract':extract}[args.command](args)


if __name__=='__main__': main()
