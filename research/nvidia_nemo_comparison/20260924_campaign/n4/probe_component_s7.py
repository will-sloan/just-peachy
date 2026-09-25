"""Eight sealed-smoke D0/E0 S7 development replays. README_COMPONENT_S7_REPLAY.md."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''

from common import audio_only, bind, fingerprint, freeze, load, verify
from component_commands import asr_commands, d0_commands
from component_s7_replay import replay_d0_anonymous, CONTRACT


def read_events(cell, limit=32*1024*1024):
    verify(cell['events'])
    digest, size, rows = hashlib.sha256(), 0, []
    with gzip.open(cell['events']['path'], 'rb') as stream:
        for raw in stream:
            size += len(raw)
            if size > limit:
                raise ValueError('Expanded component exceeds the probe bound')
            digest.update(raw)
            rows.append(json.loads(raw))
    if cell['events_expanded'] != dict(uncompressed_sha256=digest.hexdigest(), uncompressed_bytes=size):
        raise ValueError('Expanded sealed component changed')
    return rows


def save_private(path, value, limit=32*1024*1024):
    # Bounded encoder; no partially admitted oversized record is published.
    text = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(text) > limit:
        raise ValueError('Private replay exceeds per-cell output bound')
    with path.open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as stream:
            stream.write(text)
    with gzip.open(path, 'rb') as stream:
        restored = stream.read(limit+1)
    if restored != text:
        raise ValueError('Private replay gzip round trip failed')
    return dict(compressed=bind(path), expanded_bytes=len(text), expanded_sha256=hashlib.sha256(text).hexdigest())


def main(args):
    import psutil
    process = psutil.Process(); process.cpu_affinity([14])
    if os.name == 'nt': process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    for drive, floor in [('C:\\',50),('G:\\',75)]:
        if shutil.disk_usage(drive).free < floor*1024**3 + 256*1024**2:
            raise ValueError('Disk reserve leaves no admitted 256-MiB probe allocation')
    if args.output.exists():
        raise ValueError('Preserve prior probe evidence; use a fresh output')
    asr_review, d0_review = load(args.asr_review), load(args.d0_review)
    if asr_review['status'] != 'PASS_ASR_COMPONENT_SMOKE' or asr_review['component_cells'] != 8:
        raise ValueError('Require the reviewed eight-cell ASR smoke')
    if d0_review['status'] != 'PASS_MATCHED_FULL_BANK_COMPONENTS_ONLY' or d0_review['encoder_clip_cells'] != 960:
        raise ValueError('Require the reviewed D0 full bank')
    for binding in d0_review['inputs']:
        verify(binding)
    verify(asr_review['admission']); verify(asr_review['final_result'])
    asr_contract = load(asr_review['admission']['path'])
    source_binding = asr_contract['component_contract']['source_receipt']; verify(source_binding)
    source_receipt = load(source_binding['path']); source = Path(source_receipt['prototype'])
    for rel, row in source_receipt['files'].items():
        verify(dict(path=str((source/rel).resolve()), **row))
    d0_admission_binding = next(b for b in d0_review['inputs'] if Path(b['path']).name=='ADMISSION.json')
    d0_contract = load(d0_admission_binding['path'])
    if d0_contract['source_receipt'] != source_binding:
        raise ValueError('Components bind different application sources')
    index_binding = next(b for b in d0_review['inputs']
        if Path(b['path']).name=='RESULT_INDEX.json' and Path(b['path']).parent.name=='E0')
    index = load(index_binding['path'])
    sys.path[:0] = [str(source), str(source/'vendor')]
    import onnxruntime
    with patch.object(onnxruntime, 'InferenceSession', side_effect=AssertionError('No neural model in replay')):
        from app.pipeline import effective_profile
        args.output.mkdir(parents=True, exist_ok=False)
        summaries = []
        try:
            for entry in asr_review['cells']:
                verify(entry['result']); a_cell = load(entry['result']['path'])
                job = audio_only(a_cell['job']); jid = job['job_id']
                d_binding = index['cells'][jid]; verify(d_binding); d_cell = load(d_binding['path'])
                if (a_cell['status'] != 'COMPLETE' or d_cell['status'] != 'COMPLETE' or d_cell['error'] is not None
                        or d_cell['encoder'] != 'E0' or d_cell['job'] != job
                        or a_cell['admission_sha256'] != asr_review['admission']['sha256']
                        or d_cell['admission_sha256'] != d0_admission_binding['sha256']):
                    raise ValueError('Wrong paired source, encoder or sealed admission')
                if bind(job['audio_path'])['sha256'] != job['audio_sha256']:
                    raise ValueError('Original accepted waveform changed')
                profile = effective_profile('balanced', 'anonymous_conversation', job['tap'])
                if a_cell['profile_sha256'] != fingerprint(profile.to_dict()) or d_cell['profile_sha256'] != a_cell['profile_sha256']:
                    raise ValueError('Component application profiles differ')
                a_rows, d_rows = read_events(a_cell), read_events(d_cell)
                duration = job['frames']/16000
                result = replay_d0_anonymous(asr_commands(a_rows,variant=entry['variant'],duration=duration),
                    d0_commands(d_rows,duration=duration), duration=duration, profile=profile,
                    session_id=entry['variant']+'-D0-E0-'+jid,
                    formatting=[r['payload'] for r in a_rows if r['event_type']=='component_final_punctuation'])
                if result['raw_event_count'] != entry['scan']['raw_observations']:
                    raise ValueError('Raw ASR census changed during replay')
                if result['presentation']['formatting_revisions'] != entry['scan']['final_utterances']:
                    raise ValueError('Final formatting census changed during replay')
                artifact = save_private(args.output/(entry['variant']+'-'+jid+'.json.gz'), result)
                summaries.append(dict(variant=entry['variant'],job_id=jid,
                    inputs=[entry['result'], d_binding, a_cell['events'], d_cell['events']],
                    private_output=artifact,commands=result['command_count'],raw_events=result['raw_event_count'],
                    policy_events=result['policy_event_count'],
                    policy_counts=dict(Counter(r['native_record']['event_type'] for r in result['policy'])),
                    source_permissions=dict(Counter(str(r['native_record']['current_source_permission']) for r in result['policy'])),
                    rejected=result['presentation']['rejected'],worker_counts=result['worker_counts'],
                    final_utterances=result['presentation']['final_utterances']))
            receipt = dict(status='PASS_EIGHT_MODELED_D0_E0_S7_DEVELOPMENT_REPLAYS',
                utc=datetime.now(timezone.utc).isoformat(),**CONTRACT,models_loaded=0,
                source_receipt=source_binding,review_inputs=[bind(args.asr_review),bind(args.d0_review)],
                code=[bind(Path(__file__).with_name(n)) for n in ('probe_component_s7.py','component_s7_replay.py',
                    'test_component_s7_replay.py','README_COMPONENT_S7_REPLAY.md','component_commands.py','component_presentation.py')],
                cells=summaries,limits='E0 anonymous only; no D1/named/Controller parity/global activity or performance acceptance')
            freeze(args.output/'RESULT.json',receipt)
            print(json.dumps(dict(status=receipt['status'],cells=len(summaries),receipt=bind(args.output/'RESULT.json'),
                integrated_N4_cells=0),indent=2))
        except BaseException as exc:
            freeze(args.output/'FAILED.json',dict(status='FAILED_PRESERVED',error=repr(exc),completed=len(summaries)))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('asr-review','d0-review','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    main(parser.parse_args())
