"""Lossless archive queue pieces; see README_FIELD_ARCHIVE_RECORDS_V1.md."""
import hashlib
import json
import threading
import time

PIECE_BYTES = 65536
# Preserve the existing CompactJournal/compact_records 1MiB encoded-event ceiling.
# 1KiB remains for its format/sequence/value wrapper; no new disk allowance.
LOGICAL_BYTES = 1024**2 - 1024


class Piece(bytes):
    def __new__(cls, raw, token, index, count, total, digest):
        value = super().__new__(cls, raw)
        value.token, value.index, value.count = token, index, count
        value.total, value.digest = total, digest
        return value


def pieces(data, token):
    if type(data) is not bytes or not PIECE_BYTES < len(data) <= LOGICAL_BYTES:
        raise ValueError('Large archive event outside bounded logical envelope')
    record = json.loads(data)
    if record.get('kind') != 'n2_diarization_frames':
        raise ValueError('Only complete Nemotron frame events use piece admission')
    p = record['payload']; rows = p['probabilities']; start = p['frame_start']
    if type(start) is not int or type(rows) is not list or not 0 <= start <= 13001 or not 1 <= len(rows) <= 13001-start:
        raise ValueError('Diarization frame geometry exceeds admitted source ceiling')
    if any(type(row) is not list or len(row) != 8 for row in rows):
        raise ValueError('Eight ordered probabilities per frame required')
    if any(type(v) not in (int,float) or not 0 <= v <= 1 for row in rows for v in row):
        raise ValueError('Invalid activity probability')
    if len(json.dumps({k:v for k,v in record.items() if k!='payload'},ensure_ascii=False).encode()) > 2048:
        raise ValueError('Archive event envelope exceeds bound')
    meta={k:v for k,v in p.items() if k!='probabilities'}
    if len(json.dumps(meta,ensure_ascii=False,allow_nan=False).encode()) > 8192:
        raise ValueError('Frame event metadata exceeds bound')
    # Bytes are split without interpreting or replacing ANY serialized field.
    count=(len(data)+PIECE_BYTES-1)//PIECE_BYTES
    digest=hashlib.sha256(data).hexdigest()
    return [Piece(data[i*PIECE_BYTES:(i+1)*PIECE_BYTES],token,i,count,len(data),digest) for i in range(count)]


def chunked_binary(Base):
    class ChunkedBinary(Base):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            sink=self.sink
            def write(data):
                begin=time.perf_counter_ns();view=memoryview(data)
                while view:
                    n=sink.file.write(view[:PIECE_BYTES])
                    if not n or n>min(len(view),PIECE_BYTES):
                        raise OSError('Incomplete bounded journal write')
                    sink.bytes+=n;view=view[n:]
                sink.write_ns+=time.perf_counter_ns()-begin
            sink._write=write
    return ChunkedBinary


def archive_class(Base):
    class RecordArchive(Base):
        def __init__(self,*args,**kwargs):
            self._record_serial=0;self._record_parts=[];self._record_header=None
            self._assembling_bytes=0;self._record_max=0;self._record_groups=0
            self._record_piece_max=0;self._record_reassembled=0;self._record_total_max=0
            super().__init__(*args,**kwargs)
            if self.policy['record_bytes']!=PIECE_BYTES or self.policy['queue_bytes']!=4*1024**2 or self.policy['queue_items']!=512:
                raise ValueError('Exact retained archive queue limits required')

        def offer(self,kind,data,extra=None):
            try:
                # This lock also excludes the original audio/event producers.
                with self.lock:
                    if self.error or self.closed:return False
                    if len(data)>PIECE_BYTES:
                        if kind!='events':raise ValueError('ARCHIVE_RECORD_OVERSIZE')
                        batch=pieces(data,self._record_serial)
                    else:batch=[data]
                    total=self.pending_bytes+self._assembling_bytes+len(data)
                    if total>self.policy['queue_bytes'] or self.queue.qsize()+len(batch)>self.policy['queue_items']:
                        raise ValueError('ARCHIVE_QUEUE_AND_ASSEMBLY_FULL')
                    stamp=time.perf_counter()
                    self.pending_bytes+=len(data)
                    self.max_pending_bytes=max(self.max_pending_bytes,self.pending_bytes)
                    self._record_total_max=max(self._record_total_max,total)
                    if len(batch)>1:
                        self._record_serial+=1
                        self._record_max=max(self._record_max,len(data))
                        self._record_piece_max=max(self._record_piece_max,max(map(len,batch)))
                        self._record_groups+=1
                    for part in batch:self.queue.put_nowait((kind,part,extra,stamp))
                    self.accepted+=len(batch)
                return True
            except Exception as exc:
                # Never call Stop/fail while holding the non-reentrant queue lock.
                self.fail('ARCHIVE_RECORD_PIECES: '+str(exc),self.written_samples)
                return False

        def _write(self,handle,data,kind):
            if not isinstance(data,Piece):
                if kind=='events' and self._record_header is not None:
                    raise ValueError('Incomplete event followed by another record')
                return super()._write(handle,data,kind)
            header=(data.token,data.count,data.total,data.digest)
            with self.lock:
                if data.index==0:
                    if self._record_header is not None:raise ValueError('Overlapping archive event groups')
                    self._record_header=header
                if self._record_header!=header or data.index!=len(self._record_parts) or not 0<len(data)<=PIECE_BYTES:
                    raise ValueError('Archive event piece order or identity mismatch')
                if self._assembling_bytes+len(data)>LOGICAL_BYTES:
                    raise ValueError('Archive event assembly bound')
                self._record_parts.append(bytes(data));self._assembling_bytes+=len(data)
                if data.index+1!=data.count:return
                raw=b''.join(self._record_parts)
                if len(raw)!=data.total or hashlib.sha256(raw).hexdigest()!=data.digest:
                    raise ValueError('Archive event reconstruction differs')
            # Original CompactBinary/JSON/patch writer receives the exact bytes once.
            result=super()._write(handle,raw,kind)
            with self.lock:
                self._record_parts.clear();self._record_header=None;self._assembling_bytes=0
                self._record_reassembled+=1
            return result

        def snapshot(self):
            value=super().snapshot()
            value['event_pieces']=dict(logical_maximum=LOGICAL_BYTES,piece_maximum=PIECE_BYTES,
                accepted_groups=self._record_groups,reassembled_groups=self._record_reassembled,
                largest_logical_record=self._record_max,largest_piece=self._record_piece_max,
                assembling_bytes=self._assembling_bytes,maximum_queue_and_assembly=self._record_total_max,
                persisted_format_unchanged=True)
            return value

        def _checkpoint(self,state):
            if state in ('CLOSED','PARTIAL') and self._record_header is not None:
                self.fail('ARCHIVE_RECORD_ASSEMBLY_INCOMPLETE',self.written_samples)
            return super()._checkpoint(state)
    return RecordArchive
