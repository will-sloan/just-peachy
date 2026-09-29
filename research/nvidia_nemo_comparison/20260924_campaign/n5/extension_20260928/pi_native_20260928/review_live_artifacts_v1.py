"""Independent native stored-event/PCM reader; README_BOUNDED_LIVE_ARTIFACTS_V1.md."""
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import wave


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def canonical(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def ticks(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None


def decode(path):
    # Independent decoder; never imports the writer or its diff function.
    states = {}
    seq = 0
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            if row['format'] == 'footer':
                assert row['count'] == seq and row['status'] == 'COMPLETE'
                assert stream.read() == ''
                return
            assert row['seq'] == seq
            if row['format'] == 'event':
                event = row['value']
            else:
                assert row['format'] == 'patch'
                key = tuple(row['key'])
                oldseq, old = states[key]
                assert oldseq == row['base_seq']
                payload = copy.deepcopy(old)
                for op in row['ops']:
                    action, route = op[:2]
                    assert len(route) <= 24 and action in ('set','del','truncate','append')
                    if action in ('set','del'):
                        if not route:
                            assert action == 'set'
                            payload = op[2]
                        else:
                            parent = payload
                            for token in route[:-1]:
                                parent = parent[token]
                            if action == 'set':
                                parent[route[-1]] = op[2]
                            else:
                                del parent[route[-1]]
                    else:
                        values = payload
                        for token in route:
                            values = values[token]
                        assert isinstance(values, list)
                        if action == 'truncate':
                            assert 0 <= op[2] <= len(values)
                            del values[op[2]:]
                        else:
                            values.extend(op[2])
                event = dict(row['meta'], payload=payload)
            kind = event.get('event_type', event.get('kind'))
            if kind == 's6d_display':
                key = (kind,event['payload']['session_id'])
                states.pop(key, None)
                states[key] = (seq, copy.deepcopy(event['payload']))
                while len(states) > 2:
                    del states[next(iter(states))]
            seq += 1
            yield event
    raise AssertionError('Missing terminal marker')


def main():
    os.sched_setaffinity(0, {3})
    resource.setrlimit(resource.RLIMIT_AS, (768*1024**2,)*2)
    r = Path(__file__).resolve().parent
    a = json.loads((r/'ADMISSION.json').read_text())
    result = json.loads((r/'RESULT.json').read_text())
    dispatch = json.loads((r/'DISPATCH_RESULT.json').read_text())
    envelope = json.loads((r/'LIVE_ENVELOPE.json').read_text())
    assert result['status'] == 'NATIVE_LIVE_ARTIFACT_REPLAY_REVIEW_REQUIRED'
    assert dispatch['exit_code'] == 0 and not dispatch['memory_guard'] and not dispatch['log_overflow']
    for name in ('OWNER.json','DISPATCH_OWNER.json'):
        owner = json.loads((r/name).read_text())
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == owner['boot_id'] == a['boot_id']
        assert ticks(owner['pid']) != owner['start_ticks']
    assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-live-artifact-replay-v1*'],text=True).strip()
    assert a['address_space_max_bytes'] == envelope['address_space'][0] == envelope['address_space'][1] == 768*1024**2
    assert envelope['stack'] == [1048576]*2 and envelope['affinity'] == a['cpus'] == [2,3]
    assert envelope['properties']['TimeoutStopUSec']=='10s' and int(envelope['properties']['LimitFSIZE'])==8*1024**2
    assert a['stop_timeout_seconds'] == 10 and a['tasks_max'] == 64 and a['runtime_seconds'] == 300
    assert a['per_file_max_bytes'] == 8*1024**2 and a['capture'] is False
    assert int(envelope['properties']['MainPID']) == envelope['owner']['pid']
    assert envelope['properties']['TasksMax'] == '64' and envelope['properties']['RuntimeMaxUSec'] == '5min'
    assert int(envelope['cpu_max'][0])/int(envelope['cpu_max'][1]) == 2
    for binding in a['files']:
        assert sha(binding['path']) == binding['sha256']
    reviews = []
    for index, source in enumerate(a['journals']):
        path = r/('journal-'+str(index)+'.compact.jsonl')
        iterator = decode(path)
        digest = hashlib.sha256()
        count = 0
        with Path(source['path']).open() as stream:
            for original_line in stream:
                truth = canonical(json.loads(original_line))
                observed = canonical(next(iterator))
                assert observed == truth
                digest.update(observed+b'\n')
                count += 1
        try:
            next(iterator)
        except StopIteration:
            pass
        else:
            raise AssertionError('Extra event')
        metric = next(x for x in result['cases'] if x['case']=='journal' and x['index']==index)
        assert count == metric['events'] == source['events'] and path.stat().st_size == metric['bytes'] <= 8*1024**2
        assert metric['closed'] and metric['status']=='COMPLETE' and metric['retained_states']==0
        reviews.append(dict(index=index,events=count,source_bytes=source['bytes'],compact_bytes=path.stat().st_size,
                            canonical_sha256=digest.hexdigest(),all_event_fields_exact=True,patch_records=metric['patch_records'],
                            seconds=metric['seconds'],serialization_ns=metric['serialization_ns'],write_ns=metric['write_ns']))
    for name,reason in [('byte','BYTE_LIMIT'),('record','RECORD_LIMIT')]:
        path = r/('limit-'+name+'.jsonl')
        rows = [json.loads(x) for x in path.open()]
        assert path.stat().st_size<=1024 and rows[-1]['status']==reason and rows[-1]['count']==len(rows)-1
    with wave.open(a['source_wav'],'rb') as original, wave.open(str(r/'retained-source.wav'),'rb') as got:
        assert got.getparams() == original.getparams()
        assert got.getnframes() == 715127 and got.readframes(715127) == original.readframes(715127)
    for name,frames,data in [('limit-pcm.wav',3,b'\x01\x00'*3),('clipped-pcm.wav',6,b'\x00\x80\x00\x80\x00\x00\xff\x7f\xff\x7f\xff\x7f'),('invalid-pcm.wav',0,b'')]:
        path=r/name
        with wave.open(str(path),'rb') as wav:
            assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())==(1,2,16000,frames)
            assert wav.readframes(frames)==data and path.stat().st_size==44+2*frames
    assert result['invalid_pcm_cases']==5
    faults=list(decode(r/'callback.compact.jsonl'))
    assert len(faults)==2 and faults[0]['detail'] is None
    detail=faults[1]['detail']
    assert detail['raw_status_bits']==2 and detail['input_overflow'] is True
    assert detail['rejected_callback_frames']==480 and detail['upstream_lost_frames'] is None and detail['loss_extent']=='UNKNOWN'
    assert detail['input_buffer_adc_time_seconds']==123. and detail['callback_current_time_seconds']==123.01
    assert ticks(1013)==569 and ticks(1130)==607
    assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256']
    assert sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
    assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    total=sum(x.stat().st_size for x in r.rglob('*') if x.is_file())
    assert total<a['target_output_max_bytes']
    out=dict(status='PASS_NATIVE_COMPACT_REPLAY_PCM_BOUNDS_AND_FAULT_JOURNAL_ONLY',journals=reviews,
             pcm_samples=715127,pcm_bytes_exact=True,quota_rejection_before_rejected_write=True,
             actual_virtual_limit_bytes=768*1024**2,natural_exit_code=0,exact_owners_closed=True,
             peak_rss_kib=result['ru_maxrss_kib'],target_output_bytes=total,target_output_cap=a['target_output_max_bytes'],
             real_microphone_recording=False,stream_or_callback_repaired=False,application_integrated=False,
             quality_qualified=False,hashes={p.name:sha(p) for p in r.iterdir() if p.is_file()})
    with (r/'REVIEW.json').open('x') as f:
        json.dump(out,f,indent=2)
    print(json.dumps(out))


if __name__=='__main__':
    main()
