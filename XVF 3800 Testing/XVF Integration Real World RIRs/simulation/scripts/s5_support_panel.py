"""Freeze180 source supports, resume360 native-output diagnostics. README_S5_SUPPORT_METRICS.md."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path
import threading
import time

from s5_common import REPORT, PRIOR, BANK, RUN_ID, bind, read, save, now, manifest
import s5_support_metrics as support


def indexed_binding(value, path):
    """Resolve exact saved binding; no filename/WAV glob or heuristic selection."""
    target=str(Path(path).resolve()).casefold(); found=[]
    def visit(obj):
        if isinstance(obj,dict):
            if 'path' in obj and 'sha256' in obj and str(Path(obj['path']).resolve()).casefold()==target:found.append(obj)
            for child in obj.values():visit(child)
        elif isinstance(obj,list):
            for child in obj:visit(child)
    visit(value)
    if not found or len({r['sha256'] for r in found})!=1:raise ValueError('Missing/ambiguous indexed binding: '+str(path))
    return found[0]


def validate_jobs(bank, jobs):
    scenes={s['case_id']:s for s in bank['scenes']}
    development={cid for cid,s in scenes.items() if s.get('split')=='development' and s.get('task_scoring_allowed') is True}
    expected={(cid,out) for cid in development for out in ['O0','O1']}
    actual=[(j['case_id'],j['stream']) for j in jobs['jobs']]
    if len(actual)!=len(set(actual)) or set(actual)!=expected:raise ValueError('Job panel differs from exact development pairs')
    if set(jobs['development_ids'])!=development:raise ValueError('Job allowlist differs from canonical development')
    for job in jobs['jobs']:
        scene=scenes[job['case_id']]
        if job['identity']['scene_reference_sha256']!=support.fingerprint(scene):raise ValueError('Reference identity mismatch')
        if job['job_key']!=support.fingerprint(job['identity']):raise ValueError('Job key mismatch')
        if job['input_provenance']['accepted_record']['split']!='development':raise PermissionError('Accepted record is not development')
        if job['identity']['raw_audio_sha256']!=job['raw_audio']['sha256']:raise ValueError('Raw output binding differs')
        if job['identity']['input_case_result_sha256']!=job['input_provenance']['case_result']['sha256']:raise ValueError('Capture binding differs')
    return scenes


def saved_record(path, identity):
    """Reuse only self-consistent output with identical frozen inputs and code."""
    if not path.exists():return None
    row=read(path)
    if row.get('analysis_identity')!=identity:raise ValueError('Existing support result has changed analysis inputs/code: '+str(path))
    if row.get('metrics_sha256')!=support.fingerprint(row['metrics']):raise ValueError('Existing metric record changed')
    return row


class Panel:
    def __init__(self,workers=4):
        if not 1<=workers<=4:raise ValueError('At most4 analysis workers')
        self.workers=workers;self.started=time.monotonic();self.lock=threading.Lock()
        self.folder=REPORT/'support';self.folder.mkdir(parents=True,exist_ok=True)
        run=read(REPORT/'run_manifest.json')
        if not run.get('protocol_frozen_utc'):raise ValueError('Protocol must be frozen')
        self.protocol=bind(REPORT/'SCORING_PROTOCOL.json')
        self.jobs_binding=bind(REPORT/'JOB_MANIFEST.json',run['jobs']['sha256'])
        self.jobs=read(self.jobs_binding['path']);self.bank=manifest()
        self.scenes=validate_jobs(self.bank,self.jobs)
        if len(self.jobs['jobs'])!=360 or len(self.jobs['development_ids'])!=180:raise ValueError('Require authorized180/360 S5 inventory')
        self.guard=support.DevelopmentGuard(self.bank['scenes'],scoring_protocol_sha256=self.protocol['sha256'])
        self.by_case={}
        for job in self.jobs['jobs']:self.by_case.setdefault(job['case_id'],{})[job['stream']]=job
        self.bank_binding=bind(BANK/'SCENE_MANIFEST.json')
        self.noise_binding=self.bank['noise_binding']
        bind(self.noise_binding['path'],self.noise_binding['sha256']);self.noise=read(self.noise_binding['path'])
        # The supplied S5 pack index is itself bound by the frozen run manifest.
        pack_index=next(p for p in run['pack_files'] if Path(p['path']).name=='S45_LOCAL_ARTIFACT_INDEX.json')
        bind(pack_index['path'],pack_index['sha256']);index=read(pack_index['path'])
        self.capture_index_binding=indexed_binding(index,PRIOR/'CAPTURE_ANALYSIS.json')
        bind(self.capture_index_binding['path'],self.capture_index_binding['sha256'])
        self.capture_index={r['case_id']:r for r in read(self.capture_index_binding['path'])['cases']}
        self.codes=[bind(Path(__file__)),bind(Path(support.__file__))]
        self.spatial_codes=[bind(Path(__file__).with_name(name)) for name in ['s4_spatial_analysis.py','s4_geometry.py','s4_telemetry.py']]
        self.done=0;self.phase='INITIALIZED'

    def tick(self,cid,status):
        with self.lock:
            self.done+=1
            if self.done==1 or self.done%10==0:
                save(self.folder/'status.json',{'phase':self.phase,'done':self.done,'last_case':cid,'last_status':status,
                     'elapsed_s':time.monotonic()-self.started,'updated_utc':now(),'workers':self.workers})

    def freeze_one(self,cid):
        scene=self.scenes[cid];self.guard.require(scene,'support_freeze')
        job=self.by_case[cid]['O0'];other=self.by_case[cid]['O1']
        for field in ['case_result']:
            if job['input_provenance'][field]!=other['input_provenance'][field]:raise ValueError('Paired capture differs')
        if job['analysis_provenance']['audio_metrics']!=other['analysis_provenance']['audio_metrics']:raise ValueError('Paired mapping evidence differs')
        capbind=job['input_provenance']['case_result'];audiobind=job['analysis_provenance']['audio_metrics']
        capture=self.guard.read_json(scene,capbind);audio=self.guard.read_json(scene,audiobind)
        if capture.get('status')!='PASS' or capture.get('split')!='development' or capture['input_scene_sha256']!=scene['canonical_audio']['sha256']:
            raise ValueError('Accepted capture/source mismatch')
        value=support.freeze_scene_support(scene,capture,audio,self.noise,self.guard)
        target=self.folder/'source'/f'{cid}.json'
        record={'support':value,'provenance':{'scene_manifest':self.bank_binding,'case_result':capbind,'audio_metrics':audiobind,
                 'noise_catalog':self.noise_binding,'scoring_protocol':self.protocol,'input_only':True}}
        if target.exists():
            if read(target)!=record:raise ValueError('Frozen support differs; preserve prior version before any explicit correction')
        else:save(target,record)
        self.tick(cid,'FROZEN')
        return {'case_id':cid,'support':bind(target),'support_sha256':value['support_sha256'],
                'noise_events':len(value['noise_events']),'output_mapping_available':{o:value['output_mappings'][o]['source_with_rir_to_output_offset_samples'] is not None for o in ['O0','O1']}}

    def freeze(self):
        self.phase='FREEZE_INPUT_SUPPORT';self.done=0
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
            rows=list(pool.map(self.freeze_one,sorted(self.by_case)))
        result={'schema':'jp_s5_frozen_support_index_v1','run_id':RUN_ID,'count':len(rows),'scenes':rows,
                'real_noise_scene_count':sum(r['noise_events']>0 for r in rows),'job_manifest':self.jobs_binding,
                'scene_manifest':self.bank_binding,'scoring_protocol':self.protocol,'support_policy':support.POLICY,
                'support_policy_sha256':support.fingerprint(support.POLICY),'input_only_masks':True,'reserve_support_task_count':0}
        if result['real_noise_scene_count']!=39:raise ValueError('Expected39 development real-noise cases; do not force counts')
        target=self.folder/'FROZEN_SUPPORT_INDEX.json'
        if target.exists():
            if read(target)!=result:raise ValueError('Frozen support index changed')
        else:save(target,result)
        save(REPORT/'access/support_freeze.json',self.guard.receipt())
        return result

    def load_support_index(self):
        path=self.folder/'FROZEN_SUPPORT_INDEX.json'
        value=read(path)
        if value['scoring_protocol']!=self.protocol or value['job_manifest']!=self.jobs_binding or value['support_policy_sha256']!=support.fingerprint(support.POLICY):
            raise ValueError('Frozen support panel/protocol differs')
        if {r['case_id'] for r in value['scenes']}!=set(self.by_case):raise ValueError('Support population differs')
        return {r['case_id']:r for r in value['scenes']}

    def shared_one(self,cid,record):
        scene=self.scenes[cid];self.guard.require(scene)
        source=self.guard.read_json(scene,record['support'])['support'];support.validate_support(scene,source)
        job=self.by_case[cid]['O0'];capbind=job['input_provenance']['case_result']
        capture=self.guard.read_json(scene,capbind)
        # Capture analysis binds the historical spatial receipt; that receipt
        # contains the exact callback/telemetry bindings, not guessed file paths.
        spatialbind=self.capture_index[cid]['spatial_metrics']
        spatial=self.guard.read_json(scene,spatialbind)
        folder=Path(job['input_provenance']['accepted_record']['folder']).resolve()
        metadata_binding=indexed_binding(spatial['bindings'],folder/'capture_metadata.json')
        telemetry_binding=indexed_binding(spatial['bindings'],folder/'telemetry/received_telemetry.jsonl')
        if indexed_binding(spatial['bindings'],folder/'case_result.json')['sha256']!=capbind['sha256']:raise ValueError('Shared trace refers to different capture')
        identity=support.fingerprint({'case_id':cid,'support':record['support'],'protocol':self.protocol,'code':self.codes+self.spatial_codes,
                                      'capture':capbind,'metadata':metadata_binding,'telemetry':telemetry_binding})
        target=self.folder/'shared_direction'/f'{cid}.json'
        cached=saved_record(target,identity)
        if not cached:
            if source['noise_events']:
                metadata=self.guard.read_json(scene,metadata_binding,'callback_metadata')
                raw=self.guard.verified_path(scene,telemetry_binding,'shared_task_telemetry')
                telemetry=[json.loads(line) for line in raw.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
                metrics=support.shared_direction_metrics(scene,source,capture,metadata,telemetry,self.guard)
            else:
                metrics={'schema':'jp_s5_shared_noise_direction_v1','case_id':cid,'support_sha256':source['support_sha256'],
                         'physical_trace_evidence_units':1,'paired_output_evidence_units':0,'noise_events':[],
                         'status':'NO_REAL_NOISE_EVENTS','whole_capture_availability_reused':spatial['whole_capture_availability'],
                         'scope':'Existing shared whole-capture availability retained once; no duplicate O0/O1 direction scoring'}
            cached={'analysis_identity':identity,'metrics':metrics,'metrics_sha256':support.fingerprint(metrics),
                    'provenance':{'support':record['support'],'capture':capbind,'historical_spatial_receipt':spatialbind,
                                  'callback_metadata':metadata_binding,'telemetry':telemetry_binding,'codes':self.codes+self.spatial_codes,'scoring_protocol':self.protocol}}
            save(target,cached)
        self.tick(cid,'SHARED_DIRECTION_READY')
        return {'case_id':cid,'result':bind(target),'noise_events':len(source['noise_events'])}

    def output_one(self,job,record):
        cid,out=job['case_id'],job['stream'];scene=self.scenes[cid];self.guard.require(scene)
        receipt_path=Path(job['report_dir'])/'run_receipt.json'
        if not receipt_path.exists():return {'case_id':cid,'stream':out,'status':'WAITING_NATIVE_RECEIPT'}
        binding=bind(receipt_path);receipt=self.guard.read_json(scene,binding)
        if receipt.get('job_key')!=job['job_key'] or receipt.get('identity')!=job['identity']:raise ValueError('Native wrapper/job identity mismatch')
        if receipt.get('status')!='COMPLETE':return {'case_id':cid,'stream':out,'status':'NATIVE_'+str(receipt.get('status')),'receipt':binding}
        native_binding=receipt.get('reused_receipt',binding)
        native=self.guard.read_json(scene,native_binding)
        if native['raw_audio']['sha256']!=job['raw_audio']['sha256'] or native['adapter']['gain_scalar']!=job['gain']:
            raise ValueError('Native raw/gain differs from frozen paired job')
        source=self.guard.read_json(scene,record['support'])['support'];support.validate_support(scene,source)
        identity=support.fingerprint({'job_key':job['job_key'],'native_receipt':native_binding,'support':record['support'],'protocol':self.protocol,'code':self.codes})
        target=self.folder/'outputs'/cid/f'{out}.json';cached=saved_record(target,identity)
        if not cached:
            metrics=support.analyze_bound_output(scene,source,out,native,self.guard)
            cached={'analysis_identity':identity,'metrics':metrics,'metrics_sha256':support.fingerprint(metrics),
                    'provenance':{'job_key':job['job_key'],'job_receipt':binding,'native_receipt':native_binding,
                                  'support':record['support'],'codes':self.codes,'scoring_protocol':self.protocol}}
            save(target,cached)
        self.tick(cid+'/'+out,'OUTPUT_READY')
        return {'case_id':cid,'stream':out,'status':'COMPLETE','result':bind(target),
                'reference_local_status':cached['metrics']['reference_local_status']}

    def score(self):
        records=self.load_support_index();self.phase='SHARED_DIRECTION';self.done=0
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
            shared=list(pool.map(lambda cid:self.shared_one(cid,records[cid]),sorted(self.by_case)))
        self.phase='NATIVE_OUTPUT_SUPPORT';self.done=0
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
            rows=list(pool.map(lambda job:self.output_one(job,records[job['case_id']]),self.jobs['jobs']))
        completed=sum(r['status']=='COMPLETE' for r in rows)
        result={'schema':'jp_s5_support_panel_receipt_v1','status':'COMPLETE' if completed==360 else 'PARTIAL_AWAITING_NATIVE_JOBS',
                'updated_utc':now(),'requested_scenes':180,'requested_outputs':360,'completed_outputs':completed,
                'remaining_outputs':360-completed,'shared_scene_records':len(shared),'real_noise_scene_records':sum(r['noise_events']>0 for r in shared),
                'rows':rows,'shared_direction':shared,'frozen_support_index':bind(self.folder/'FROZEN_SUPPORT_INDEX.json'),
                'scoring_protocol':self.protocol,'codes':self.codes+self.spatial_codes,'workers':self.workers,
                'elapsed_s':time.monotonic()-self.started,'reserve_task_performance_accesses':0,
                'limitations':['Missing saved output lag stays unavailable','Unknown ambient flags are noise-associated and source attribution unavailable',
                               'Shared direction scored once per scene','Native final text lacks word intervals; event-local insertion/turn omission unavailable']}
        save(self.folder/'SUPPORT_PANEL_RECEIPT.json',result)
        save(REPORT/'access/support_metrics.json',self.guard.receipt())
        save(self.folder/'status.json',{k:v for k,v in result.items() if k not in ['rows','shared_direction']})
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['freeze','score','all'])
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args();panel=Panel(args.workers)
    try:
        if args.mode in ['freeze','all']:result=panel.freeze()
        if args.mode in ['score','all']:result=panel.score()
        print(json.dumps({k:v for k,v in result.items() if k not in ['scenes','rows','shared_direction']},indent=2))
    finally:
        save(REPORT/'access/support_last_invocation.json',panel.guard.receipt())


if __name__=='__main__':main()
