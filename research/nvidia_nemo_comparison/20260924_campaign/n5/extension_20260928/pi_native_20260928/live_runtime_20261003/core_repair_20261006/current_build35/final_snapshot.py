"""Closed scheduler rows on bounded disk; see README_FINAL_SNAPSHOT.md."""
from copy import copy, deepcopy
import hashlib
import os
from pathlib import Path

from runtime_support import encoded, strict, publish, digest

RECORD_MAX = 1024**2
SEGMENT_MAX = 8*1024**2
ROW_MAX = 4096


class RowArchive:
    """Synchronous one-row writer: no second all-history list or queue."""
    def __init__(self, path, budget):
        self.path, self.budget = Path(path), budget
        self.stream = None
        self.segment = -1
        self.segment_bytes = 0
        self.bytes = self.count = 0
        self.hash = hashlib.sha256()
        self.closed = False
        self.error = None
        self.reference = None
        # Finite receipt + index publication is part of the shared allocation.
        budget.claim(8192)

    def append(self, row):
        if self.closed or self.error or self.count >= ROW_MAX:
            raise RuntimeError('Closed/failed archive or retained scheduler row bound')
        raw = encoded(dict(sequence=self.count,row=row))+b'\n'
        if len(raw)>RECORD_MAX:
            raise BufferError('Final scheduler row exceeds explicit 1 MiB record bound')
        self.budget.claim(len(raw))
        try:
            self.budget.check_free(self.path.parent,len(raw))
            if self.stream is None or self.segment_bytes+len(raw)>SEGMENT_MAX:
                self._seal()
                self.segment+=1
                self.stream=self.path.with_name(self.path.name+'.%06d'%self.segment).open('xb')
                self.segment_bytes=0
            if self.stream.write(raw)!=len(raw):
                raise OSError('Short final scheduler row write')
            self.hash.update(raw)
            self.bytes+=len(raw); self.segment_bytes+=len(raw); self.count+=1
        except BaseException as exc:
            self.error=repr(exc)
            raise

    def _seal(self):
        if self.stream is not None:
            stream,self.stream=self.stream,None
            try:
                stream.flush(); os.fsync(stream.fileno())
            finally:
                stream.close()

    def close(self):
        if self.closed:
            if self.error: raise RuntimeError(self.error)
            return self.reference
        self.closed=True
        try:
            self._seal()
            if self.error: raise RuntimeError(self.error)
            receipt=dict(schema='just-peachy.scheduler-rows.v1',path=self.path.name,
                count=self.count,bytes=self.bytes,sha256=self.hash.hexdigest(),
                segment_count=self.segment+1,record_maximum=RECORD_MAX,complete=True)
            destination=self.path.with_name(self.path.name+'.index.json')
            publish(destination,receipt,cap=4096)
            self.reference=dict(receipt,index_sha256=digest(destination))
            return self.reference
        except BaseException as exc:
            self.error=repr(exc)
            raise


def iter_rows(directory, reference):
    """Read all rows to obtain end-of-stream integrity certification; never aggregate."""
    directory=Path(directory)
    name=reference['path']
    if Path(name).name!=name or '/' in name or '\\' in name:
        raise ValueError('Local scheduler archive basename required')
    index=directory/(name+'.index.json')
    if index.is_symlink() or index.stat().st_size>4096 or digest(index)!=reference['index_sha256']:
        raise ValueError('Final scheduler index pin changed')
    receipt=strict(index.read_bytes())
    if receipt != {k:v for k,v in reference.items() if k!='index_sha256'}:
        raise ValueError('Scheduler archive reference differs from index')
    if (receipt.get('schema')!='just-peachy.scheduler-rows.v1' or receipt.get('complete') is not True
            or type(receipt['count']) is not int or not 0<=receipt['count']<=ROW_MAX
            or type(receipt['segment_count']) is not int or not 0<=receipt['segment_count']<=ROW_MAX
            or type(receipt['bytes']) is not int or not 0<=receipt['bytes']<=ROW_MAX*RECORD_MAX):
        raise ValueError('Bounded complete scheduler archive required')
    count=total=0; checksum=hashlib.sha256()
    for number in range(receipt['segment_count']):
        path=directory/(name+'.%06d'%number)
        if path.is_symlink() or not 0<path.stat().st_size<=SEGMENT_MAX:
            raise ValueError('Final scheduler segment bound')
        with path.open('rb') as stream:
            while True:
                raw=stream.readline(RECORD_MAX+1)
                if not raw: break
                if len(raw)>RECORD_MAX or not raw.endswith(b'\n'):
                    raise ValueError('Final scheduler record bound/truncation')
                total+=len(raw)
                if total>receipt['bytes'] or count>=receipt['count']:
                    raise ValueError('Unexpected final scheduler record')
                value=strict(raw)
                if set(value)!={'sequence','row'} or value['sequence']!=count or not isinstance(value['row'],dict):
                    raise ValueError('Final scheduler row order/type')
                checksum.update(raw); count+=1
                yield value['row']
    if count!=receipt['count'] or total!=receipt['bytes'] or checksum.hexdigest()!=receipt['sha256']:
        raise ValueError('Final scheduler complete count/hash mismatch')


class ClosedSchedulerSnapshot:
    def __init__(self, dispatcher, directory, budget):
        self.dispatcher,self.directory,self.budget=dispatcher,Path(directory),budget
        self.original=dispatcher.snapshot
        self.value=None

    def snapshot(self):
        if self.value is not None:
            return deepcopy(self.value)
        dispatcher=self.dispatcher
        policy=dispatcher.scheduler
        worker=dispatcher.worker
        if not worker.closed or worker.thread.is_alive() or worker.error or worker.completed!=worker.accepted:
            raise RuntimeError('Final history requires the exact drained, closed policy worker')
        with policy._lock:
            if not policy._closed or policy._heap:
                raise RuntimeError('Final history requires closed scheduler with no pending events')
            rows=policy._utterances
            if len(rows)>ROW_MAX:
                raise RuntimeError('Pinned retained scheduler row bound changed')
            # Shallow shadows reuse closed locks/counters/identity state but
            # never mutate the original mapping or copy its retained history.
            shadow_policy=copy(policy)
            shadow_policy._utterances={}
            shadow_dispatcher=copy(dispatcher)
            shadow_dispatcher.scheduler=shadow_policy
            metadata=self.original.__func__(shadow_dispatcher)
            if metadata.pop('utterances')!=[]:
                raise RuntimeError('Pinned snapshot empty-row contract changed')
            archive=RowArchive(self.directory/'scheduler-utterances.jsonl',self.budget)
            try:
                for value in rows.values():
                    row=deepcopy(value)
                    dispatcher.clock.annotate_snapshot(dict(utterances=[row]))
                    archive.append(row)
                reference=archive.close()
            except BaseException:
                archive._seal()
                raise
        value=dict(metadata,original_schema_version=metadata['schema_version'],
            schema_version='just-peachy.scheduler-external.v1',utterances_external=reference)
        if len(encoded(value))>RECORD_MAX:
            raise BufferError('Final scheduler metadata exceeds explicit 1 MiB bound')
        self.value=value
        return deepcopy(value)

    def rows(self):
        return iter_rows(self.directory,self.snapshot()['utterances_external'])


def write_revised_transcript(engine, snapshot, budget):
    """Same final-row/punctuation fields as pinned runtime, streamed one at a time."""
    archive=RowArchive(engine._session_dir/'latest_labelled_transcript.jsonl',budget)
    try:
        for row in snapshot.rows():
            if row['is_final']:
                punctuated=engine._s6d_punctuated.get(row['utterance_id'])
                if punctuated is not None and punctuated['raw_text']==row['text']:
                    row={**row,'display_text':punctuated['text'],'punctuation':punctuated}
                archive.append(dict(schema_version='edge-latest-labelled-transcript.v3' if engine._research_v3 else 'edge-latest-labelled-transcript.v2',**row))
        engine._telemetry['latest_labelled_transcript_external']=archive.close()
    except BaseException:
        archive._seal()
        raise


def write_summary(engine,budget):
    """Pinned summary fields, with shared allocation claimed before any write."""
    if engine._session_dir is None: return
    summary=dict(schema_version='edge-speech-session.v1',state=engine._state,
        telemetry=engine.telemetry(),assets=[dict(component_id=a.component_id,sha256=a.sha256) for a in engine.config.assets],
        scientific_policy=dict(identity_score_threshold=engine.config.identity_score_threshold,
            identity_margin_threshold=engine.config.identity_margin_threshold,
            identity_minimum_evidence_sec=engine.config.identity_minimum_evidence_sec,
            clustering_threshold=engine.config.clustering_threshold),
        xvf=dict(contract_available=True,result_effects_enabled=False))
    if engine._research_profile is not None:
        summary['research']=engine._research_profile.effective(engine.config)
        summary['research']['telemetry_sha256']=getattr(engine._spatial_provider,'sha256',None)
        summary['xvf']['result_effects_enabled']=engine._research_profile.xvf.mode!='none'
    if engine._research_v3:
        summary['scientific_policy']['scope']='Historical PipelineConfig values; actual S6C anonymous/naming policies are bound in research.profile.tracker and research.profile.identity'
    size=len(encoded(summary))+1
    if size>RECORD_MAX: raise BufferError('Final summary exceeds explicit 1 MiB bound')
    budget.claim(size); budget.check_free(engine._session_dir,size)
    publish(engine._session_dir/'session_summary.json',summary,replace=True,cap=RECORD_MAX)
