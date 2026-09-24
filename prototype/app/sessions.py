"""Private linked conversations and bounded asynchronous exact-input archives.

No capture owner or model inference. See README_SESSIONS.md for format/policy/run.
"""
from __future__ import annotations
from collections import OrderedDict
from copy import deepcopy
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile

import numpy as np
from .paths import atomic_json, read_json, sha256

RATE=16000
MIB=1024**2
POLICY=dict(quota_mib=2048, draft_limit=10, audio_epoch_mib=256, metadata_epoch_mib=64,
            free_floor_mib=2048, queue_bytes=4*MIB, queue_items=512, resource_interval_sec=1.)


def utc(): return datetime.now(timezone.utc).isoformat()
def encoded(value): return (json.dumps(value,ensure_ascii=False,allow_nan=False,default=str)+'\n').encode('utf-8')
def size_tree(path): return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())

def open_index(path):
    connection=sqlite3.connect(path)
    connection.execute('CREATE TABLE IF NOT EXISTS captions (key TEXT PRIMARY KEY, offset INTEGER, length INTEGER)')
    connection.execute('CREATE TABLE IF NOT EXISTS formatted (key TEXT PRIMARY KEY, offset INTEGER, length INTEGER)')
    return connection

def index_event(connection,record,offset,length):
    if record.get('kind')=='s6d_display':
        p=record['payload'];key=p.get('caption_key') or str(p.get('utterance_id'))
        connection.execute('INSERT INTO captions VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET offset=excluded.offset,length=excluded.length',(key,offset,length))
    elif record.get('kind')=='prototype_formatted_text':
        p=record['payload'];key=p.get('caption_key') or str(p.get('utterance_id'))
        connection.execute('INSERT INTO formatted VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET offset=excluded.offset,length=excluded.length',(key,offset,length))

def recover_index(folder):
    target=folder/'captions.sqlite';temporary=folder/'captions.recover.sqlite'
    temporary.unlink(missing_ok=True);db=open_index(temporary)
    try:
        with (folder/'events.jsonl').open('rb') as f:
            while True:
                offset=f.tell();line=f.readline()
                if not line or not line.endswith(b'\n'):break
                index_event(db,json.loads(line),offset,len(line))
        db.commit()
    finally:db.close()
    os.replace(temporary,target)


def records(path):
    """A torn final JSON line is recoverable; malformed interior evidence is not."""
    if not path.exists(): return
    with path.open('rb') as f:
        for line in f:
            if not line.endswith(b'\n'): return
            yield json.loads(line)


class EpochArchive:
    """A bounded, nonblocking side sink after journal admission, outside callback."""
    def __init__(self,path,metadata,audio,*,policy=None,budget_bytes=None,delay_once=0):
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=False)
        self.policy={**POLICY,**(policy or {})};self.audio=bool(audio);self.metadata=deepcopy(metadata)
        self.metadata.update(schema='just-peachy.epoch.v1',created_utc=utc(),state='OPEN',
            archive_epoch_id=self.path.name,audio_enabled=self.audio,sample_rate=RATE,channels=1,
            master='model_input.f32le' if audio else None,format='IEEE754 little-endian float32; headerless',
            domain='post-XVF model input, not raw microphones',identity_stream='same mono source as ASR',
            quantization='none relative to admitted float32 model input',
            available_timestamp_quality='preserve upstream declared clocks; not calibrated acoustic arrival',
            window_index='half-open model-input sample indices; segmentation left padding explicitly recorded')
        self.enhancement=self.metadata.get('enhancement') or {'route':'bypass','asr_stream':'input','identity_stream':'input'}
        self.enhanced_enabled=self.enhancement['route']!='bypass'
        if self.enhanced_enabled:self.metadata.update(identity_stream=self.enhancement['identity_stream'],
            asr_stream=self.enhancement['asr_stream'],enhanced_master='enhanced.f32le' if audio else None,
            master_scope='model_input.f32le is unenhanced post-XVF input; enhanced.f32le is the optional aligned output; consult transforms.jsonl')
        self.enhanced_samples=self.enhanced_written_samples=0;self._enhanced_hash=hashlib.sha256()
        self.queue=queue.Queue(self.policy['queue_items']);self.lock=threading.Lock();self.stop_event=threading.Event()
        self.error=None;self.loss=None;self.closed=False;self.pending_bytes=0;self.max_pending_bytes=0
        self.source_samples=0;self.written_samples=0;self.audio_bytes=0;self.metadata_bytes=0
        self.budget_bytes=budget_bytes if budget_bytes is not None else self.policy['quota_mib']*MIB
        self.accepted=self.completed=0;self.max_queue_age=0.;self.source_origin=None;self.engine=None
        self.delay_once=delay_once;self.windows=0;self.sequence=0;self._hash=hashlib.sha256()
        atomic_json(self.path/'epoch.json',self.metadata)
        self.thread=threading.Thread(target=self._run,name='proto-session-archive',daemon=True);self.thread.start()

    def fail(self,reason,start=None):
        with self.lock:
            if self.error is None:
                self.error=str(reason);self.loss=dict(reason=str(reason),first_unarchived_sample=start,
                    noticed_monotonic_sec=time.perf_counter(),noticed_utc=utc(),
                    policy='Archive stopped; live captions continue. No gap padding or silent resume.')

    def offer(self,kind,data,extra=None):
        n=len(data)
        with self.lock:
            if self.error or self.closed:return False
            if n>128*1024 or self.pending_bytes+n>self.policy['queue_bytes'] or self.queue.full():
                self.error='ARCHIVE_QUEUE_FULL';self.loss=dict(reason=self.error,first_unarchived_sample=self.written_samples,
                    noticed_monotonic_sec=time.perf_counter(),policy='Archive stopped; live captions continue')
                return False
            self.pending_bytes+=n;self.max_pending_bytes=max(self.max_pending_bytes,self.pending_bytes)
            self.queue.put_nowait((kind,data,extra,time.perf_counter()));self.accepted+=1
        return True

    def audio_block(self,start,samples):
        try:self._audio_block(start,samples)
        except Exception as exc:self.fail('Archive audio unavailable: '+str(exc),start)

    def _audio_block(self,start,samples):
        # Called by the source-consumer journal, never PortAudio's callback.
        x=np.asarray(samples,dtype=np.float32).reshape(-1)
        if start!=self.source_samples:self.fail('Noncontiguous model-input source',start)
        self.source_samples=start+len(x)
        if self.audio:
            gain=float(self.metadata.get('pipeline_input_gain',1.))
            if gain!=1.:x=x*np.float32(gain)
            self.offer('audio',x.astype('<f4',copy=False).tobytes(),start)

    def enhanced_block(self,start,samples):
        try:
            if start!=self.enhanced_samples:raise ValueError('Noncontiguous enhanced source')
            self.enhanced_samples+=len(samples)
            if self.audio:self.offer('enhanced',np.asarray(samples,dtype='<f4').tobytes(),start)
        except Exception as exc:self.fail('Enhanced archive unavailable: '+str(exc),start)

    def enhancement_transform(self,start,count,method,available_source,compute):
        self.offer('transforms',encoded(dict(source_start_sample=start,source_end_sample=start+count,
            output_start_sample=start,output_end_sample=start+count,method=method,
            available_source_cursor_sample=available_source,available_monotonic_sec=time.perf_counter(),compute_sec=compute,
            model_sha256=self.enhancement.get('model_sha256'),gain=1.,normalization='none',
            buffer_contract='160-sample hop / 320-sample window; source indices retained; only native flush padding, not source audio')))

    def event(self,event):
        payload=deepcopy(event.payload)
        if event.event_type=='source_started':self.source_origin=payload.get('source_epoch_monotonic_sec')
        record=dict(kind=event.event_type,source_sec=event.source_time_sec if hasattr(event,'source_time_sec') else getattr(event,'source_sec',None),
            archive_epoch_id=self.path.name,received_monotonic_sec=time.perf_counter(),payload=payload,
            original_wall_time_utc=getattr(event,'wall_time_utc',None),original_schema=getattr(event,'schema_version',None))
        self.offer('events',encoded(record))
        if event.event_type in ('research_segmentation','research_embedding'):
            start=payload.get('receptive_start_sec');end=payload.get('receptive_end_sec')
            if not all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in (start,end)) or end<start:
                self.fail('Window source indices unavailable');return
            a,b=round(start*RATE),round(end*RATE)
            if abs(a-start*RATE)>1e-5 or abs(b-end*RATE)>1e-5:
                self.fail('Window sample grid mismatch');return
            pad=round(float(payload.get('left_padding_sec',max(0,10-end) if event.event_type=='research_segmentation' else 0))*RATE)
            self.windows+=1
            self.offer('windows',encoded(dict(window_id=f'w{self.windows:08d}',kind=event.event_type,
                archive_epoch_id=self.path.name,event_id=payload.get('evidence_event_id',payload.get('event_id')),
                publication_sequence=payload.get('publication_sequence'),source_start_sample=a,source_end_sample=b,
                left_padding_samples=pad,audio_stream=self.enhancement['identity_stream'],transform='declared stream slice; prepend recorded zeros for segmentation only; no normalization/gain',
                tensor_shape=[1,1,b-a+pad] if event.event_type=='research_segmentation' else [1,b-a],
                available_clocks={k:v for k,v in payload.items() if 'available' in k or 'monotonic' in k or 'elapsed' in k},
                availability_quality=payload.get('availability_method','upstream observed/publication and modeled clocks kept distinct'))))

    def formatted(self,row,names):
        from .casing import provisional_case
        self.offer('events',encoded(dict(kind='prototype_formatted_text',archive_epoch_id=self.path.name,
            received_monotonic_sec=time.perf_counter(),payload=dict(caption_key=row.get('caption_key'),
                utterance_id=row.get('utterance_id'),text_revision_id=row.get('text_revision_id'),
                raw_asr_text=row.get('text',''),provisional_display_text=provisional_case(row.get('text',''),names=names),
                final_formatted_text=row.get('display_text') if row.get('punctuation_for_text_revision') else None,
                text_assistance=deepcopy(row.get('text_assistance')),
                final=bool(row.get('final')),provenance='controller formatting; raw S7 event kept separately; manual corrections are separate'))))

    def _resource(self):
        import psutil
        proc=psutil.Process();stamp=time.perf_counter();cpu=sum(proc.cpu_times()[:2])
        prior=getattr(self,'_prior_cpu',None);self._prior_cpu=(stamp,cpu)
        telemetry=self.engine.telemetry() if self.engine is not None else {}
        return dict(archive_epoch_id=self.path.name,monotonic_sec=stamp,utc=utc(),source_origin_monotonic_sec=self.source_origin,
            source_cursor_sample=self.source_samples,source_relative_host_sec=stamp-self.source_origin if self.source_origin is not None else None,
            cpu_total_sec=cpu,cpu_percent_one_core=(100*(cpu-prior[1])/(stamp-prior[0]) if prior and stamp>prior[0] else None),
            process_rss_bytes=proc.memory_info().rss,writer_queue_items=self.queue.qsize(),writer_queue_bytes=self.pending_bytes,
            oldest_queue_age_sec=self._oldest_age(),max_writer_queue_age_sec=self.max_queue_age,
            archive_audio_samples=self.written_samples,archive_error=self.error,
            configured_features=self.metadata.get('features',{}),pipeline=telemetry)

    def _oldest_age(self):
        with self.queue.mutex:
            return max(0,time.perf_counter()-self.queue.queue[0][3]) if self.queue.queue else 0.

    def _check_space(self,n,kind):
        limit=self.policy['audio_epoch_mib' if kind in ('audio','enhanced') else 'metadata_epoch_mib']*MIB
        used=self.audio_bytes if kind in ('audio','enhanced') else self.metadata_bytes
        if used+n>limit or self.audio_bytes+self.metadata_bytes+n>self.budget_bytes:
            raise OSError('ARCHIVE_QUOTA_REACHED; pinned data preserved')
        if time.perf_counter()>=getattr(self,'_space_next',0):
            if shutil.disk_usage(self.path).free<self.policy['free_floor_mib']*MIB:raise OSError('ARCHIVE_FREE_SPACE_FLOOR')
            self._space_next=time.perf_counter()+1

    def _write(self,handle,data,kind):
        self._check_space(len(data),kind)
        if handle.write(data)!=len(data):raise OSError('Short archive write')
        if kind=='audio':self.audio_bytes+=len(data);self.written_samples+=len(data)//4;self._hash.update(data)
        elif kind=='enhanced':self.audio_bytes+=len(data);self.enhanced_written_samples+=len(data)//4;self._enhanced_hash.update(data)
        else:self.metadata_bytes+=len(data)

    def snapshot(self):
        return dict(epoch_id=self.path.name,audio_enabled=self.audio,audio_recording=self.audio and not self.error and not self.closed,
            source_samples=self.source_samples,recorded_samples=self.written_samples,archive_error=self.error,loss=deepcopy(self.loss),
            queue_items=self.queue.qsize(),queue_bytes=self.pending_bytes,max_queue_bytes=self.max_pending_bytes,
            max_queue_age_sec=self.max_queue_age,audio_bytes=self.audio_bytes,metadata_bytes=self.metadata_bytes,
            closed=self.closed,worker_alive=self.thread.is_alive() if hasattr(self,'thread') else False,
            enhancement=self.enhancement,enhanced_source_samples=self.enhanced_samples,enhanced_recorded_samples=self.enhanced_written_samples)

    def _checkpoint(self,state):
        atomic_json(self.path/'epoch.json',{**self.metadata,**self.snapshot(),'state':state,'updated_utc':utc(),
            'source_origin_monotonic_sec':self.source_origin,'audio_sha256':self._hash.hexdigest() if self.audio else None,
            'enhanced_sha256':self._enhanced_hash.hexdigest() if self.audio and self.enhanced_enabled else None,
            'accepted_items':self.accepted,'completed_items':self.completed})

    def _run(self):
        handles={};next_resource=0.;db=None
        try:
            db=open_index(self.path/'captions.sqlite')
            for name in ('events','windows','resources'):handles[name]=(self.path/(name+'.jsonl')).open('ab',buffering=0)
            if self.audio:handles['audio']=(self.path/'model_input.f32le').open('ab',buffering=0)
            if self.enhanced_enabled:
                handles['transforms']=(self.path/'transforms.jsonl').open('ab',buffering=0)
                if self.audio:handles['enhanced']=(self.path/'enhanced.f32le').open('ab',buffering=0)
            while not self.stop_event.is_set() or not self.queue.empty():
                try:item=self.queue.get(timeout=.1)
                except queue.Empty:item=None
                if item:
                    kind,data,start,enqueued=item
                    try:
                        if self.delay_once:time.sleep(self.delay_once);self.delay_once=0
                        self.max_queue_age=max(self.max_queue_age,time.perf_counter()-enqueued)
                        if not self.error:
                            if kind=='audio' and start!=self.written_samples:raise OSError('Archive audio discontinuity')
                            if kind=='enhanced' and start!=self.enhanced_written_samples:raise OSError('Archive enhanced audio discontinuity')
                            offset=handles[kind].tell()
                            self._write(handles[kind],data,kind)
                            if kind=='events':index_event(db,json.loads(data),offset,len(data))
                            self.completed+=1
                    except Exception as exc:self.fail(type(exc).__name__+': '+str(exc),start)
                    finally:
                        with self.lock:self.pending_bytes-=len(data)
                        self.queue.task_done()
                if time.perf_counter()>=next_resource:
                    try:
                        if not self.error:self._write(handles['resources'],encoded(self._resource()),'resources')
                        for f in handles.values():os.fsync(f.fileno())
                        db.commit()
                        self._checkpoint('OPEN' if not self.error else 'PARTIAL')
                    except Exception as exc:self.fail(type(exc).__name__+': '+str(exc),self.written_samples)
                    next_resource=time.perf_counter()+self.policy['resource_interval_sec']
        except Exception as exc:self.fail(type(exc).__name__+': '+str(exc),self.written_samples)
        finally:
            if db is not None:
                try:db.commit();db.close()
                except Exception as exc:self.fail(str(exc))
            for f in handles.values():
                try:
                    try:os.fsync(f.fileno())
                    finally:f.close()
                except Exception as exc:self.fail(str(exc))
            self.closed=True
            try:self._checkpoint('PARTIAL' if self.error else 'CLOSED')
            except Exception as exc:self.fail('Final manifest unavailable: '+str(exc))

    def close(self):
        self.stop_event.set();self.thread.join(10)
        if self.thread.is_alive():raise TimeoutError('Archive writer still active; do not delete/reopen it')
        return self.snapshot()


class SessionStore:
    def __init__(self,data_root,policy=None):
        self.root=Path(data_root).resolve()/'conversations';self.root.mkdir(parents=True,exist_ok=True)
        self.policy={**POLICY,**(policy or {})};self.active={};self.recover()
        self.lock=threading.RLock()

    def folder(self,identifier):
        if not re.fullmatch('[0-9a-f]{32}',str(identifier)):raise ValueError('Invalid conversation ID')
        p=(self.root/identifier).resolve()
        if p.parent!=self.root.resolve():raise ValueError('Conversation path escaped its store')
        return p

    def metadata(self,identifier):return read_json(self.folder(identifier)/'conversation.json')

    def update(self,identifier,**values):
        with self.lock:
            doc=self.metadata(identifier);doc.update(values,updated_utc=utc());atomic_json(self.folder(identifier)/'conversation.json',doc);return doc

    def new(self,audio=False,consent=False,title=None):
        if audio and consent is not True:raise ValueError('Participant audio-recording consent required')
        self.enforce()
        if self.usage()['bytes']>=self.policy['quota_mib']*MIB:raise OSError('Conversation quota is full; pinned sessions preserved')
        identifier=uuid.uuid4().hex;p=self.folder(identifier);p.mkdir()
        atomic_json(p/'conversation.json',dict(schema='just-peachy.conversation.v1',id=identifier,
            title=self.title(title or 'Conversation '+datetime.now().strftime('%Y-%m-%d %H:%M')),
            created_utc=utc(),updated_utc=utc(),state='DRAFT',pinned=False,audio_requested=bool(audio),
            consent=dict(audio_storage=bool(audio and consent),recorded_utc=utc(),scope='this logical conversation only'),
            privacy='Local unencrypted sensitive speech/text; no profiles or cloud upload',epochs=[],notes=[],corrections=[]))
        return identifier

    @staticmethod
    def title(value):
        value=str(value).strip()
        if not value or len(value)>160:raise ValueError('Use 1–160 characters')
        return value

    def begin(self,identifier,metadata,**test_options):
        if identifier in self.active:raise RuntimeError('Conversation already has an archive owner')
        meta=self.metadata(identifier)
        if meta['pinned']:raise ValueError('Saved conversation is immutable; create a new draft to record')
        self.enforce(exclude=identifier)
        remaining=self.policy['quota_mib']*MIB-self.usage()['bytes']
        if remaining<=0:raise OSError('Archive quota full; choose text/live captions without archive or free space')
        epoch=uuid.uuid4().hex
        archive=EpochArchive(self.folder(identifier)/'epochs'/epoch,metadata,meta['audio_requested'],
            policy=self.policy,budget_bytes=remaining,**test_options)
        self.active[identifier]=archive
        try:self.update(identifier,state='DRAFT',epochs=meta['epochs']+[epoch])
        except Exception:
            archive.close();self.active.pop(identifier,None);raise
        return archive

    def ended(self,identifier,archive):
        receipt=archive.close()
        if self.active.get(identifier) is archive:self.active.pop(identifier)
        try:self.update(identifier,last_archive_status=receipt,state='DRAFT')
        except OSError:pass  # Disk full remains visible in the epoch/RAM receipt.
        return receipt

    def save(self,identifier):
        self._quiet(identifier);return self.update(identifier,pinned=True,state='SAVED')

    def rename(self,identifier,title):self._quiet(identifier);return self.update(identifier,title=self.title(title))

    def annotate(self,identifier,note,*,row_id=None,correction=None,source=None,review=None):
        if correction is not None:self._quiet(identifier)
        m=self.metadata(identifier)
        item=dict(id=uuid.uuid4().hex,utc=utc(),monotonic_sec=time.perf_counter(),row_id=row_id,author='explicit local user')
        if source:item['source']=deepcopy(source)
        if correction is not None:
            if not row_id:raise ValueError('Correction requires a caption ID')
            caption=next((r for r in self.iter_rows(identifier) if r.get('caption_key')==row_id),None)
            if caption is None:
                raise ValueError('Correction caption does not belong to this conversation')
            item.update(corrected_text=str(correction)[:4000],provenance='manual; never overwrite automatic output')
            if review:
                stored=next((r for r in m.get('audio_reviews',[]) if r['id']==review.get('review_id')),None)
                candidate=next((r for r in stored['candidates'] if r['id']==review.get('candidate_id')),None) if stored else None
                if (not candidate or candidate['id']=='original' or candidate['text']!=correction or stored['request']['caption_id']!=row_id
                    or stored['request']['audio_sha256']!=review.get('audio_sha256')):raise ValueError('Review correction is not bound to a saved candidate')
                item.update(review=deepcopy(review),provenance='explicit user adoption of audio-review candidate; not recovered audio truth')
            item.update(original_raw=caption.get('text'),original_formatted=caption.get('display_text'),
                        source={'caption_key':row_id,'epoch':caption['archive_epoch_id'],'start_sample':caption['source_start_sample'],
                                'end_sample':caption['source_end_sample'],'text_revision_id':caption.get('text_revision_id')})
            key='corrections'
        else:item['note']=str(note).strip()[:1000];key='notes'
        if len(m[key])>=200:raise ValueError('Annotation limit reached; export or start a new conversation')
        self.update(identifier,**{key:m[key]+[item]})

    def undo_correction(self,identifier,edit_id):
        self._quiet(identifier);m=self.metadata(identifier)
        edit=next((x for x in m['corrections'] if x['id']==edit_id and not x.get('reverts')),None)
        if edit is None or any(x.get('reverts')==edit_id for x in m['corrections']):raise ValueError('Correction is missing or already undone')
        if len(m['corrections'])>=200:raise ValueError('Annotation limit reached')
        item=dict(id=uuid.uuid4().hex,utc=utc(),row_id=edit['row_id'],reverts=edit_id,corrected_text='',
                  author='explicit local user',provenance='undo; original journal unchanged',source=edit.get('source'))
        self.update(identifier,corrections=m['corrections']+[item])

    def _quiet(self,identifier):
        if identifier in self.active:raise RuntimeError('Stop and drain this conversation before this action')

    def delete(self,identifier,confirmed=False):
        if confirmed is not True:raise ValueError('Explicit delete confirmation required')
        self._quiet(identifier);target=self.folder(identifier)
        if target.parent!=self.root:raise ValueError('Unsafe delete target')
        shutil.rmtree(target)  # One verified UUID conversation; never people/.

    def list(self):
        result=[]
        for p in self.root.glob('*/conversation.json'):
            try:
                m=read_json(p);self.folder(m['id']);m['size_bytes']=size_tree(p.parent);m['issues']=[]
                for ep in (p.parent/'epochs').glob('*/epoch.json'):
                    status=read_json(ep)
                    if status.get('archive_error') or status.get('state')=='RECOVERED_PARTIAL' or status.get('pipeline_terminal_state')=='FAILED':
                        m['issues'].append(dict(epoch=ep.parent.name,state=status.get('state'),error=status.get('archive_error') or 'Source/pipeline failed; inspect linked native events'))
                result.append(m)
            except (ValueError,KeyError,OSError):continue
        return sorted(result,key=lambda m:m['created_utc'],reverse=True)

    def usage(self):
        return dict(path=str(self.root),bytes=size_tree(self.root),free_bytes=shutil.disk_usage(self.root).free,
            quota_bytes=self.policy['quota_mib']*MIB,draft_limit=self.policy['draft_limit'],policy=deepcopy(self.policy))

    def enforce(self,exclude=None):
        rows=self.list();drafts=[r for r in reversed(rows) if not r['pinned'] and r['id'] not in self.active and r['id']!=exclude]
        total=sum(r['size_bytes'] for r in rows)
        while drafts and (len(drafts)>=self.policy['draft_limit'] or total>=self.policy['quota_mib']*MIB):
            old=drafts.pop(0);self.delete(old['id'],confirmed=True);total-=old['size_bytes']

    def recover(self):
        for p in self.root.glob('*/epochs/*/epoch.json'):
            try:
                m=read_json(p)
                if m.get('state') not in ('OPEN','PARTIAL') or m.get('closed'):continue
                audio=p.parent/'model_input.f32le';size=audio.stat().st_size if audio.exists() else 0
                # Never relabel an interrupted writer as complete or invent samples.
                m.update(state='RECOVERED_PARTIAL',closed=True,worker_alive=False,recovered_utc=utc(),
                    recovered_complete_float_samples=size//4,trailing_audio_bytes=size%4,
                    archive_error='Previous process ended without archive finalization; tail completeness unknown',
                    audio_sha256=sha256(audio) if audio.exists() else None)
                enhanced=p.parent/'enhanced.f32le'
                if enhanced.exists():
                    m.update(recovered_enhanced_complete_float_samples=enhanced.stat().st_size//4,
                        trailing_enhanced_bytes=enhanced.stat().st_size%4,enhanced_sha256=sha256(enhanced))
                atomic_json(p,m)
                if (p.parent/'events.jsonl').exists():recover_index(p.parent)
            except (OSError,ValueError):continue

    def epoch(self,identifier,epoch):
        m=self.metadata(identifier)
        if epoch not in m['epochs']:raise ValueError('Epoch does not belong to this conversation')
        p=(self.folder(identifier)/'epochs'/epoch).resolve()
        if p.parent.parent!=self.folder(identifier):raise ValueError('Invalid epoch path')
        return p

    def iter_rows(self,identifier,limit=None):
        """Reconstruct from source-backed event records, not a rolling UI cache."""
        self._quiet(identifier)
        for epoch in self.metadata(identifier)['epochs']:
            folder=self.epoch(identifier,epoch)
            if not (folder/'captions.sqlite').exists():recover_index(folder)
            with closing(sqlite3.connect(folder/'captions.sqlite')) as check:
                has_format=check.execute("SELECT 1 FROM sqlite_master WHERE name='formatted'").fetchone()
            if not has_format:recover_index(folder)
            with closing(sqlite3.connect(folder/'captions.sqlite')) as db, (folder/'events.jsonl').open('rb') as f:
                sql='SELECT offset,length FROM captions ORDER BY rowid'
                if limit is not None:sql='SELECT offset,length FROM (SELECT rowid,offset,length FROM captions ORDER BY rowid DESC LIMIT ?) ORDER BY rowid'
                for offset,length in db.execute(sql,() if limit is None else (limit,)):
                    f.seek(offset);record=json.loads(f.read(length))
                    row=deepcopy(record['payload']);key=row.get('caption_key') or str(row.get('utterance_id'))
                    row['archive_epoch_id']=epoch;row['archive_conversation_id']=identifier
                    row['source_start_sample']=round(float(row.get('source_start_sec',0))*RATE)
                    row['source_end_sample']=round(float(row.get('source_end_sec',0))*RATE)
                    row['audio_link_quality']='coarse utterance interval; not phonetic word alignment'
                    location=db.execute('SELECT offset,length FROM formatted WHERE key=?',(key,)).fetchone()
                    if location:
                        f.seek(location[0]);formatting=json.loads(f.read(location[1]))['payload']
                        if formatting.get('text_revision_id')==row.get('text_revision_id'):
                            row['archived_provisional_display_text']=formatting['provisional_display_text']
                            row['archived_final_formatted_text']=formatting['final_formatted_text']
                            row['text_assistance']=deepcopy(formatting.get('text_assistance'))
                    yield row

    def rows(self,identifier,limit=512):
        from collections import deque
        return list(deque(self.iter_rows(identifier,limit),maxlen=limit))

    def audio_slice(self,identifier,epoch,start,end,pad=0,stream='input'):
        self._quiet(identifier);p=self.epoch(identifier,epoch);m=read_json(p/'epoch.json')
        if not m.get('audio_enabled'):raise ValueError('Text-only session has no stored audio')
        if not all(type(x) is int for x in (start,end,pad)) or not 0<=start<end or pad<0:raise ValueError('Invalid sample interval')
        if end-start+pad>60*RATE:raise ValueError('Select at most 60 seconds per listening/window action')
        if stream not in ('input','enhanced','asr','identity'):raise ValueError('Unknown audio stream')
        if stream=='identity' and end>m.get('identity_stopped_at_sample',end):raise ValueError('Identity processing stopped at helper failure; this interval was not sent to identity')
        selected=(m.get('enhancement') or {}).get(stream+'_stream','input') if stream in ('asr','identity') else stream
        if selected=='enhanced' and not m.get('enhanced_master'):raise ValueError('No enhanced audio in this epoch')
        path=p/('enhanced.f32le' if selected=='enhanced' else 'model_input.f32le');count=path.stat().st_size//4
        if end>count:raise ValueError('Requested interval was not recorded; archive is partial')
        with path.open('rb') as f:f.seek(start*4);x=np.frombuffer(f.read((end-start)*4),dtype='<f4').copy()
        return np.pad(x,(pad,0)) if pad else x

    def export_window(self,identifier,epoch,window_id,destination):
        if not self.metadata(identifier)['pinned']:raise ValueError('Save/pin the source before exporting windows')
        row=next((r for r in records(self.epoch(identifier,epoch)/'windows.jsonl') if r['window_id']==window_id),None)
        if row is None:raise ValueError('Unknown source-backed model window')
        x=self.audio_slice(identifier,epoch,row['source_start_sample'],row['source_end_sample'],row['left_padding_samples'],stream=row.get('audio_stream','input'))
        path=Path(destination)
        if path.exists() or path.with_suffix(path.suffix+'.json').exists():raise FileExistsError(path)
        source=self.folder(identifier)
        if source==path.resolve() or source in path.resolve().parents:raise ValueError('Export must be outside its pinned source')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:np.save(f,x,allow_pickle=False)
        atomic_json(path.with_suffix(path.suffix+'.json'),dict(**row,source_conversation=identifier,sha256=sha256(path),format='NumPy float32; exact recorded slice + declared left padding'))
        return str(path)

    def export(self,identifier,destination,*,include_audio=False,consent=False):
        self._quiet(identifier)
        if consent is not True:raise ValueError('Explicit privacy-aware export confirmation required')
        root=self.folder(identifier);target=Path(destination).resolve()
        if target==root or root in target.parents:raise ValueError('Export must be outside the conversation source')
        if target.exists():raise FileExistsError(target)
        target.parent.mkdir(parents=True,exist_ok=True)
        if include_audio and not self.metadata(identifier)['pinned']:raise ValueError('Save/pin source before audio export')
        # ZIP mode x never overwrites. Text-only export deliberately omits native
        # event payloads/roster UUIDs/voice vectors; audio export is full sensitive evidence.
        try:
            with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as z:
                if include_audio:
                    for p in root.rglob('*'):
                        if p.is_file():z.write(p,p.relative_to(root).as_posix())
                else:
                    with z.open('transcript.jsonl','w') as f:
                        for r in self.iter_rows(identifier):
                            f.write(encoded(dict(caption_id=r.get('caption_key'),raw_asr=r.get('text'),formatted=r.get('display_text'),
                                provisional_display=r.get('archived_provisional_display_text'),final_formatted=r.get('archived_final_formatted_text'),
                                text_assistance=r.get('text_assistance'),manual_edit=r.get('manual_edit'),
                                final=r.get('final'),source_start_sample=r['source_start_sample'],source_end_sample=r['source_end_sample'],
                                archive_epoch_id=r['archive_epoch_id'])))
                    m=self.metadata(identifier);z.writestr('user_annotations.json',json.dumps(dict(notes=m['notes'],corrections=m['corrections']),ensure_ascii=False,indent=2))
                    if m.get('audio_reviews'):z.writestr('audio_reviews.json',json.dumps(m['audio_reviews'],ensure_ascii=False,indent=2))
                z.writestr('EXPORT_NOTICE.txt','Sensitive local speech/text. Not encrypted. No automatic cloud upload.\n'+
                    ('Includes exact float audio, raw identity/model events and roster IDs.\n' if include_audio else 'Text-only; may still contain spoken names/private words.\n'))
        except BaseException:
            # Keep incomplete output for diagnosis, explicitly distinguish it.
            if target.exists():target.rename(target.with_name(target.name+'.partial-'+uuid.uuid4().hex[:8]))
            raise
        return str(target)
