"""Lossless patch-first event writer. See README_EVENT_WRITER_STREAMING.md."""
import copy
import hashlib
import io
import json
from pathlib import Path
import threading

from runtime_support import SegmentedText, encoded, publish, strict

FORMAT='just-peachy.compact-events.v1'
LOGICAL_MAX=1024**2
MAX_OPS=4096
MAX_DEPTH=24
UTF8_CHARS=4096


def _canonical_parts(value):
    """Retain the C JSON fast path; slice its text before UTF-8/hash submission."""
    encoder=json.JSONEncoder(ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    for fragment in encoder.iterencode(value,_one_shot=True):
        for offset in range(0,len(fragment),UTF8_CHARS):
            yield fragment[offset:offset+UTF8_CHARS].encode('utf-8')


def _canonical_info(value,logical_digest=None):
    """Hash/count canonical bytes without retaining a full encoded event."""
    size=0;digest=hashlib.sha256()
    staged=None if logical_digest is None else logical_digest.copy()
    for part in _canonical_parts(value):
        size+=len(part)
        if size>LOGICAL_MAX:raise ValueError('Canonical logical event bound')
        digest.update(part)
        if staged is not None:staged.update(part)
    if staged is not None:staged.update(b'\n')
    return size,digest.hexdigest(),staged


def _record(value):
    """Build only a selected complete record; queue submission remains atomic."""
    with io.BytesIO() as stream:
        for part in _canonical_parts(value):
            if stream.tell()+len(part)+1>LOGICAL_MAX:raise ValueError('Encoded event wrapper bound')
            stream.write(part)
        stream.write(b'\n')
        return stream.getvalue()


def _check_text(value):
    if not isinstance(value,str):raise TypeError('Event text required')
    if not 0<len(value)<=LOGICAL_MAX:raise ValueError('Logical event bound')
    size=0
    for offset in range(0,len(value),UTF8_CHARS):
        size+=len(value[offset:offset+UTF8_CHARS].encode('utf-8'))
        if size>LOGICAL_MAX:raise ValueError('Logical event bound')


class _Prepared:
    __slots__=('event','logical_size','logical_digest','payload_size','payload_sha','session','is_patch')

    def __init__(self,event,logical_size,logical_digest,payload_size,payload_sha,session,is_patch):
        self.event=event;self.logical_size=logical_size;self.logical_digest=logical_digest
        self.payload_size=payload_size;self.payload_sha=payload_sha;self.session=session;self.is_patch=is_patch


def changes(old,new,path=(),ops=None):
    """Retained v28 replacement/append/truncate semantics with finite complexity."""
    if ops is None:ops=[]
    if len(path)>MAX_DEPTH or len(ops)>=MAX_OPS:raise ValueError('Patch complexity')
    if type(old) is not type(new):ops.append(['set',list(path),new])
    elif isinstance(new,dict):
        for key in sorted(old.keys()-new.keys()):
            ops.append(['del',list(path)+[key]])
            if len(ops)>=MAX_OPS:raise ValueError('Patch complexity')
        for key in sorted(new):
            if key not in old:ops.append(['set',list(path)+[key],new[key]])
            else:changes(old[key],new[key],path+(key,),ops)
            if len(ops)>=MAX_OPS:raise ValueError('Patch complexity')
    elif isinstance(new,list):
        for index in range(min(len(old),len(new))):changes(old[index],new[index],path+(index,),ops)
        if len(new)<len(old):ops.append(['truncate',list(path),len(new)])
        elif len(new)>len(old):ops.append(['append',list(path),new[len(old):]])
    elif old!=new or (isinstance(new,float) and encoded(old)!=encoded(new)):
        # Preserve signed zero as well as every other finite JSON number.
        ops.append(['set',list(path),new])
    if len(ops)>MAX_OPS:raise ValueError('Patch complexity')
    return ops


def apply_changes(previous,ops):
    if not isinstance(ops,list) or len(ops)>MAX_OPS:raise ValueError('Patch operation bound')
    result=copy.deepcopy(previous)
    for op in ops:
        if (not isinstance(op,list) or len(op) not in (2,3) or not isinstance(op[1],list)
                or len(op[1])>MAX_DEPTH):raise ValueError('Patch shape')
        kind,path=op[:2]
        if kind not in ('set','del','append','truncate') or len(op)!=(2 if kind=='del' else 3):
            raise ValueError('Patch operation')
        target=result
        for key in path[:-1] if kind in ('set','del') else path:
            if (isinstance(target,list) and (type(key) is not int or not 0<=key<len(target))
                    or isinstance(target,dict) and (type(key) is not str or key not in target)
                    or not isinstance(target,(dict,list))):raise ValueError('Patch path')
            target=target[key]
        if kind in ('set','del'):
            if not path:
                if kind!='set':raise ValueError('Cannot delete payload root')
                result=copy.deepcopy(op[2]);continue
            key=path[-1]
            if (isinstance(target,list) and (type(key) is not int or not 0<=key<len(target))
                    or isinstance(target,dict) and type(key) is not str
                    or not isinstance(target,(dict,list))):raise ValueError('Patch target')
            if kind=='del':
                if not isinstance(target,dict) or key not in target:raise ValueError('Patch deletion')
                del target[key]
            else:target[key]=copy.deepcopy(op[2])
        elif kind=='append':
            if not isinstance(target,list) or not isinstance(op[2],list):raise ValueError('Patch append')
            target.extend(copy.deepcopy(op[2]))
        else:
            if not isinstance(target,list) or type(op[2]) is not int or not 0<=op[2]<=len(target):
                raise ValueError('Patch truncation')
            del target[op[2]:]
    return result


class Codec:
    """One prior display payload only; no session-history or per-kind cache."""
    def __init__(self):
        self.sequence=0;self.previous=None;self.previous_seq=None;self.session=None
        self.previous_sha=None;self.previous_bytes=0;self.maximum_state_bytes=0
        self.logical_digest=hashlib.sha256();self.logical_bytes=0;self.patches=0

    def prepare(self,raw):
        if type(raw) is not bytes or not 0<len(raw)<=LOGICAL_MAX:raise ValueError('Logical event bound')
        return self._prepare_event(strict(raw))

    def prepare_text(self,value):
        _check_text(value)
        # json.loads(bytes) accepts a leading UTF-8 BOM, as the original writer did.
        return self._prepare_event(strict(value[1:] if value.startswith('\ufeff') else value))

    def _prepare_event(self,event):
        if not isinstance(event,dict):raise ValueError('Event object required')
        logical_size,event_sha,logical_digest=_canonical_info(event,self.logical_digest)
        # Replacing the four-byte literal null gives the exact canonical full size.
        full=dict(format=FORMAT,encoding='full',seq=self.sequence,event_sha256=event_sha,value=None)
        full_size=len(encoded(full))-4+logical_size+1
        output=None;payload=event.get('payload');session=None;payload_size=0;payload_sha=None;is_patch=False
        if event.get('event_type',event.get('kind'))=='s6d_display':
            if not isinstance(payload,dict) or not isinstance(payload.get('session_id'),str):
                raise ValueError('Display session identity required')
            session=payload['session_id'];payload_size,payload_sha,_=_canonical_info(payload)
            if self.previous is not None and session==self.session:
                try:
                    ops=changes(self.previous,payload)
                    candidate=_record(dict(format=FORMAT,encoding='display_patch',seq=self.sequence,
                        event_sha256=event_sha,base_seq=self.previous_seq,base_sha256=self.previous_sha,
                        session_id=session,meta={key:value for key,value in event.items() if key!='payload'},ops=ops))
                    if len(candidate)<full_size:output=candidate;is_patch=True
                except ValueError:
                    pass  # Complete literal fallback; the same finite record bound still applies.
        if output is None:
            if full_size>LOGICAL_MAX:raise ValueError('Encoded event wrapper bound')
            full['value']=event;output=_record(full)
        return output,_Prepared(event,logical_size,logical_digest,payload_size,payload_sha,session,is_patch)

    def commit(self,state):
        if isinstance(state,_Prepared):
            event=state.event;session=state.session;is_patch=state.is_patch
            self.logical_digest=state.logical_digest;self.logical_bytes+=state.logical_size+1
            payload_sha=state.payload_sha;payload_size=state.payload_size
        else:
            # Existing reader state, including its detached internal payload cache.
            event,logical,payload_raw,session,is_patch=state
            self.logical_digest.update(logical);self.logical_digest.update(b'\n');self.logical_bytes+=len(logical)+1
            payload_sha=None if payload_raw is None else hashlib.sha256(payload_raw).hexdigest()
            payload_size=0 if payload_raw is None else len(payload_raw)
        if session is not None:
            self.previous=event['payload'];self.previous_seq=self.sequence;self.session=session
            self.previous_sha=payload_sha;self.previous_bytes=payload_size
            self.maximum_state_bytes=max(self.maximum_state_bytes,self.previous_bytes)
        self.sequence+=1;self.patches+=bool(is_patch)

    def decode(self,row):
        if row.get('format')!=FORMAT or type(row.get('seq')) is not int or row['seq']!=self.sequence:
            raise ValueError('Event sequence/format mismatch')
        encoding=row.get('encoding')
        if encoding=='full':
            if set(row)!={'format','encoding','seq','event_sha256','value'}:raise ValueError('Full event fields')
            event=row['value']
        elif encoding=='display_patch':
            if set(row)!={'format','encoding','seq','event_sha256','base_seq','base_sha256','session_id','meta','ops'}:
                raise ValueError('Display patch fields')
            if (self.previous is None or type(row['base_seq']) is not int or row['base_seq']!=self.previous_seq or row['base_sha256']!=self.previous_sha
                    or row['session_id']!=self.session or not isinstance(row['meta'],dict) or 'payload' in row['meta']):
                raise ValueError('Display patch base differs')
            event=dict(row['meta'],payload=apply_changes(self.previous,row['ops']))
            if event.get('event_type',event.get('kind'))!='s6d_display':raise ValueError('Only display patches allowed')
        else:raise ValueError('Unknown event encoding')
        if not isinstance(event,dict):raise ValueError('Decoded event object required')
        logical=encoded(event)
        if len(logical)>LOGICAL_MAX or hashlib.sha256(logical).hexdigest()!=row['event_sha256']:
            raise ValueError('Reconstructed full event digest/bound differs')
        payload=event.get('payload');session=None;payload_raw=None
        if event.get('event_type',event.get('kind'))=='s6d_display':
            if not isinstance(payload,dict) or not isinstance(payload.get('session_id'),str):raise ValueError('Display session')
            session=payload['session_id'];payload_raw=encoded(payload)
            if encoding=='display_patch' and session!=self.session:raise ValueError('Reconstructed session changed')
        self.commit((event,logical,payload_raw,session,encoding=='display_patch'))
        # Keep the internal state private from consumers that annotate events.
        return copy.deepcopy(event)

    def metrics(self):
        return dict(format=FORMAT,records=self.sequence,patches=self.patches,logical_bytes=self.logical_bytes,
            logical_sha256=self.logical_digest.hexdigest(),cached_displays=int(self.previous is not None),
            cached_payload_bytes=self.previous_bytes,maximum_cached_payload_bytes=self.maximum_state_bytes,
            logical_record_maximum=LOGICAL_MAX,maximum_patch_operations=MAX_OPS,maximum_patch_depth=MAX_DEPTH)


class CompactEventText:
    """File-compatible adapter; compaction runs on the existing journal consumer."""
    def __init__(self,path,**kwargs):
        self.sink=SegmentedText(path,**kwargs);self.codec=Codec();self.lock=threading.RLock()
        self.thread=self.sink.thread;self.path=self.sink.path;self.closed=False;self.error=None
        self.receipt_reserve=4096
        try:self.sink.budget.claim(self.receipt_reserve)
        except BaseException:
            self.sink.close();raise

    def write(self,value):
        if not isinstance(value,str):raise TypeError('Event text required')
        with self.lock:
            if self.closed or self.error:raise RuntimeError('Compact writer closed/failed')
            try:
                data,state=self.codec.prepare_text(value)
                self.sink.write_bytes(data)
                self.codec.commit(state)
            except BaseException as exc:
                self.error=repr(exc);self.sink._fault(self.error);raise
        return len(value)

    def close(self):
        with self.lock:
            if self.closed:
                if self.error:raise RuntimeError(self.error)
                return
            self.closed=True
        failure=None
        try:self.sink.close()
        except BaseException as exc:failure=exc;self.error=self.error or repr(exc)
        row=dict(self.codec.metrics(),complete=failure is None and self.error is None,
                 physical=self.sink.metrics(),error=self.error)
        path=self.path.with_name(self.path.name+'.compaction.json')
        try:
            if len(encoded(row))+1>self.receipt_reserve:raise ValueError('Compaction receipt reserve exceeded')
            self.sink.budget.check_free(path.parent,len(encoded(row))+1)
            publish(path,row,cap=16384)
        except BaseException as exc:
            self.error=self.error or repr(exc);self.sink._fault(self.error)
            if failure is None:failure=exc
            else:failure.add_note('Compaction receipt publication failed: '+repr(exc))
        finally:self.codec.previous=None;self.codec.previous_bytes=0
        if failure is not None:raise failure
        if self.error:raise RuntimeError(self.error)

    def tell(self):return self.sink.tell()
    def metrics(self):return dict(self.sink.metrics(),compaction=self.codec.metrics())


def iter_events(path,*,maximum_bytes,maximum_records,allow_partial=False):
    """Read old plain or new compact segments; require full indexes by default."""
    if type(maximum_bytes) is not int or maximum_bytes<=0 or type(maximum_records) is not int or maximum_records<=0:
        raise ValueError('Explicit finite reader limits required')
    path=Path(path)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Real event directory required')
    def receipt(file):
        if file.is_symlink() or not file.is_file() or file.stat().st_size>16384:raise ValueError('Bounded real event index')
        return strict(file.read_bytes())
    index=receipt(path.with_name(path.name+'.index.json'))
    count=index['segment_count']
    if type(count) is not int or not 0<=count<=maximum_records or index['completed_bytes']>maximum_bytes:
        raise ValueError('Segment count/byte bound')
    receipt_path=path.with_name(path.name+'.compaction.json')
    compact=receipt(receipt_path) if receipt_path.exists() else None
    if not allow_partial and (index['complete'] is not True or compact is not None and compact['complete'] is not True):
        raise ValueError('Complete event closure required')
    codec=Codec();total=0;records=0
    for number in range(count):
        segment=path.with_name(path.name+'.%06d'%number)
        if segment.is_symlink() or not segment.is_file():raise ValueError('Real event segment required')
        with segment.open('rb') as stream:
            while raw:=stream.readline(LOGICAL_MAX+1):
                total+=len(raw);records+=1
                if len(raw)>LOGICAL_MAX or not raw.endswith(b'\n') or total>maximum_bytes or records>maximum_records:
                    raise ValueError('Complete bounded event record required')
                row=strict(raw)
                if not isinstance(row,dict):raise ValueError('Event object required')
                if compact is not None:yield codec.decode(row)
                elif row.get('format')==FORMAT:raise ValueError('Compact closure receipt missing')
                else:yield row
    if total!=index['completed_bytes']:raise ValueError('Segment byte total differs')
    if compact is not None:
        observed=codec.metrics()
        if not compact['complete'] and allow_partial:
            if observed['records']>compact['records']:raise ValueError('Partial stream exceeds accepted records')
        elif any(observed[key]!=compact[key] for key in ('records','logical_bytes','logical_sha256','patches')):
            raise ValueError('Full logical stream receipt differs')
