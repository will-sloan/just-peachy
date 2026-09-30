"""No-capture retained D1 packet scheduling diagnostic. README_SERIALIZATION_PROBE_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace


def run(root, admission):
    prototype=Path(admission['prototype'])
    sys.path[:0]=[str(prototype),str(prototype/'vendor')]
    from app.pipeline import PrototypeEngine
    from app.sessions import SessionStore
    from app import sessions as S
    from app import bounded_live_artifacts_v1 as B
    from review_live_artifacts_v1 import decode
    events=[e for e in decode(Path(admission['event_journal'])) if e['event_type']=='n2_diarization_frames']
    event=events[0]
    assert len(event['payload']['probabilities'])==2112
    canonical=json.dumps(event,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    original_hash=hashlib.sha256(canonical.encode()).hexdigest()
    source_bytes=Path(admission['event_journal']).read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest()==admission['event_sha256']
    cgroup=next(x.split(':',2)[2].strip() for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
    statpath=Path('/sys/fs/cgroup')/cgroup.lstrip('/')/'cpu.stat'
    def cpu():return {k:int(v) for k,v in (l.split() for l in statpath.read_text().splitlines())}
    thread_samples=[];stop=threading.Event();ready=threading.Event()
    def probe():
        ready.set()
        while not stop.wait(.001):
            if len(thread_samples)>=20000:raise RuntimeError('Timing sample bound')
            thread_samples.append(time.perf_counter_ns())
    thread=threading.Thread(target=probe,name='diagnostic-timing-probe');thread.start();assert ready.wait(2)
    peer_code=r'''
import os,json,time,sys,resource
from pathlib import Path
r=Path(sys.argv[1]);resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2)
owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
with (r/'PROBE_OWNER.json').open('x') as f:json.dump(owner,f)
data=[];began=time.monotonic()
while not (r/'PROBE_STOP').exists():
 if time.monotonic()-began>45 or len(data)>=20000:raise RuntimeError('Bounded peer probe exhausted')
 data.append(time.perf_counter_ns());time.sleep(.001)
with (r/'PEER_TIMES.json').open('x') as f:json.dump(data,f)
'''
    peer=subprocess.Popen([sys.executable,'-B','-c',peer_code,str(root)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    began=time.monotonic()
    while not (root/'PROBE_OWNER.json').exists():
        assert peer.poll() is None and time.monotonic()-began<3;time.sleep(.01)
    phases=[];artifacts=[]
    original_encode=B.encoded;original_archive_encode=S.encoded
    def iterative(value,**kwargs):return ''.join(json.JSONEncoder(**kwargs).iterencode(value))
    def begin(name):return dict(name=name,start_ns=time.perf_counter_ns(),cpu_before=cpu())
    def end(row):row.update(end_ns=time.perf_counter_ns(),cpu_after=cpu());phases.append(row)
    try:
        row=begin('idle_control');time.sleep(1);end(row)
        for variant in ['original','iterencode_candidate']:
            # Fresh per-phase writers; the admitted application source is never edited.
            if variant=='iterencode_candidate':
                B.encoded=lambda value:iterative(value,ensure_ascii=False,allow_nan=False,separators=(',',':'),sort_keys=True).encode('utf-8')
                S.encoded=lambda value:(iterative(value,ensure_ascii=False,allow_nan=False,default=str)+'\n').encode('utf-8')
            directory=root/variant;directory.mkdir()
            engine=PrototypeEngine.__new__(PrototypeEngine);engine.writer_delay=0;engine.text_writers=[]
            writer=engine._open_journal_text(directory/'events.jsonl')
            store=SessionStore(directory/'data',dict(quota_mib=16,draft_limit=2,free_floor_mib=5120))
            identifier=store.new(audio=False,title='Retained probability packet diagnostic')
            archive=store.begin(identifier,dict(conversation_id=identifier,enhancement=dict(route='bypass',asr_stream='input',identity_stream='input')))
            row=begin(variant);iterations=[]
            try:
                for index in range(3):
                    t=time.perf_counter_ns()
                    text=(json.dumps(event) if variant=='original' else iterative(event))+'\n'
                    a=time.perf_counter_ns();writer.write(text)
                    b=time.perf_counter_ns();archive.event(SimpleNamespace(**event))
                    c=time.perf_counter_ns();writer.queue.join();archive.queue.join();writer.flush()
                    assert not archive.error
                    iterations.append(dict(start_ns=t,encode_ns=a-t,enqueue_ns=b-a,archive_offer_ns=c-b,drain_ns=time.perf_counter_ns()-c))
                    time.sleep(.05)
            finally:
                writer.close();receipt=store.ended(identifier,archive)
            end(row)
            assert writer.accepted==writer.completed==3 and not writer.thread.is_alive() and writer.pending_bytes==0
            assert receipt['closed'] and not receipt['archive_error'] and receipt['queue_items']==receipt['queue_bytes']==0
            got=list(decode(directory/'events.jsonl'));assert got==[event]*3
            archived=list(decode(archive.path/'events.jsonl'));assert len(archived)==3
            assert all(e['kind']==event['event_type'] and e['payload']==event['payload'] for e in archived)
            artifacts.append(dict(variant=variant,iterations=iterations,engine_metrics=writer.sink.metrics(),archive_metrics=receipt.get('artifact_metrics'),archive_path=str(archive.path),raw_record_bytes=len(text.encode()),events=3,exact_event_roundtrip=True))
            B.encoded=original_encode;S.encoded=original_archive_encode
            time.sleep(.1)
    finally:
        B.encoded=original_encode;S.encoded=original_archive_encode
        stop.set();thread.join(2);assert not thread.is_alive()
        (root/'PROBE_STOP').write_text('closed')
        assert peer.wait(timeout=3)==0,peer.stderr.read().decode()
    peer_samples=json.loads((root/'PEER_TIMES.json').read_text())
    assert len(thread_samples)<20000 and len(peer_samples)<20000
    def gaps(samples,phase):
        pairs=[b-a for a,b in zip(samples,samples[1:]) if phase['start_ns']<=a and b<=phase['end_ns']]
        assert pairs
        return dict(count=len(pairs),max_ns=max(pairs),above_10ms=sum(v>10000000 for v in pairs),above_32ms=sum(v>32000000 for v in pairs),above_90ms=sum(v>90000000 for v in pairs))
    for phase in phases:
        phase['python_thread_intervals']=gaps(thread_samples,phase)
        phase['separate_process_intervals']=gaps(peer_samples,phase)
        phase['cpu_delta']={k:phase['cpu_after'][k]-v for k,v in phase['cpu_before'].items()}
    with (root/'THREAD_TIMES.json').open('x') as f:json.dump(thread_samples,f)
    assert hashlib.sha256(Path(admission['event_journal']).read_bytes()).hexdigest()==admission['event_sha256']
    assert hashlib.sha256(json.dumps(event,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==original_hash
    return dict(status='COLLECTED_SERIALIZATION_SCHEDULING_DIAGNOSTIC_ONLY',phases=phases,artifacts=artifacts,event_sha256=original_hash,probability_frames=2112,capture=False,models_loaded=False,peer_closed=True,thread_closed=True,live_fault_cause_proven=False,application_candidate_integrated=False,scope='Three repeated retained packets per variant, not a source stream or live callback test')
