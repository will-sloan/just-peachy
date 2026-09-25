"""Verify completed N3 receipts and emit redacted tables; README_REVIEW.md."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def binding(path):
    path = Path(path).resolve(strict=True)
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)


def require_hash(row):
    actual = binding(row['path'])
    if any(actual[k] != row[k] for k in ('path','sha256')) or ('bytes' in row and actual['bytes'] != row['bytes']):
        raise ValueError('Evidence binding changed')
    return load(row['path'])


def completed_job(plan_path, job_id, receipts):
    plan = load(plan_path)
    terminal = Path(plan['output'])/'RESULT.json'
    result = load(terminal)
    if result['status'] != 'READY_FOR_REVIEW' or result['plan_sha256'] != binding(plan_path)['sha256']:
        raise ValueError('Exact numerical plan is not terminal')
    row = result['jobs'][job_id]
    if row['status'] != 'COMPLETE' or row['exit_code'] != 0:
        raise ValueError('Required job failed: '+job_id)
    value = require_hash(row['result'])
    if value['status'] != 'COMPLETE':
        raise ValueError('Required completed result differs')
    receipts.extend([binding(plan_path), binding(terminal), binding(row['result']['path'])])
    return value, next(job for job in plan['jobs'] if job['id'] == job_id)


def complete_cells(folder, expected, receipts):
    result_path = folder/'RESULT.json'
    result = load(result_path)
    if (result['status'] != 'COMPLETE' or result['total'] != expected
            or result['completed'] != expected or len(result['cells']) != expected):
        raise ValueError('Incomplete cell census')
    cells = [require_hash(row) for row in result['cells']]
    if len({c['job_id'] for c in cells}) != expected or any(c['status'] != 'COMPLETE' for c in cells):
        raise ValueError('Duplicate or failed cell in complete census')
    receipts.extend([binding(result_path), binding(folder/'RUN_LOCK.json')])
    return result, cells, load(folder/'RUN_LOCK.json')


def validate_paced_manifest(jobs, cells):
    if len(jobs)!=8 or len(cells)!=8:
        raise ValueError('Exactly eight predeclared paced files required')
    expected = {j['job_id'].replace('N2_','N3_',1):j for j in jobs}
    if len(expected)!=8 or {c['job_id'] for c in cells}!=set(expected):
        raise ValueError('Paced files differ from frozen manifest')
    for cell in cells:
        job=expected[cell['job_id']]
        if (cell['status']!='COMPLETE' or cell['input_samples']!=job['frames']
                or cell['audio_sha256']!=job['audio_sha256'] or job['gain']!=1
                or job['sample_rate_hz']!=16000 or job['reset_between_scenes'] is not True
                or cell['delivery']!='source_paced_independent_producer'):
            raise ValueError('Paced waveform/sample/delivery contract differs')


def a1_paced_census(local, receipts):
    """Narrow adjudication of one preserved coordinator count defect, never a generic failure override."""
    plan_path=local/'plan-a1nominalv1.json';plan=load(plan_path)
    terminal=Path(plan['output'])/'RESULT.json';queue=load(terminal)
    job=next(j for j in plan['jobs'] if j['id']=='paced-A1-onnx')
    history=queue['jobs'][job['id']]
    if (queue['status']!='READY_FOR_REVIEW' or queue['plan_sha256']!=binding(plan_path)['sha256']
            or history['status']!='FAILED' or history['reason']!='incomplete cell census'
            or history['exit_code']!=0 or job['expected_cells']!=4 or '--paced' not in job['argv']):
        raise ValueError('Not the reviewed A1 coordinator count defect')
    require_hash(history['result'])
    argv=job['argv'];manifest=Path(argv[argv.index('--audio-manifest')+1])
    actual_manifest=binding(manifest)
    if not any(row['path']==actual_manifest['path'] and row['sha256']==actual_manifest['sha256'] for row in plan['bindings']):
        raise ValueError('Paced manifest was not bound before inference')
    result,cells,lock=complete_cells(Path(job['result']).parent,8,receipts)
    if lock['audio_manifest_sha256']!=actual_manifest['sha256']:
        raise ValueError('Runtime used a different paced manifest')
    validate_paced_manifest(load(manifest)['jobs'],cells)
    for row,cell in zip(result['cells'],cells):
        events=Path(row['path']).parent/'events.jsonl'
        if binding(events)['sha256']!=cell['events_sha256']:
            raise ValueError('Paced events changed')
    receipts.extend([binding(plan_path),binding(terminal),actual_manifest])
    correction=dict(status='ACCEPTED_PREDECLARED_EIGHT_FILE_EVIDENCE',original_queue_status='FAILED',
        original_reason=history['reason'],coordinator_expected_cells=4,frozen_manifest_cells=8,
        completed_cells=8,all_result_event_and_manifest_hashes_verified=True,
        new_inference=False,original_plan_or_evidence_modified=False,
        interpretation='The frozen command executed its complete eight-file manifest; only the coordinator count was wrong. Preserve both records.')
    return resource_summary(result,cells,lock),correction


def span(values):
    values = [v for v in values if v is not None]
    return dict(n=len(values), min=min(values) if values else None, max=max(values) if values else None)


def resource_summary(result, cells, lock):
    seconds = sum(c['source_seconds'] for c in cells)
    return dict(variant=result['variant'], runtime=result['runtime'], cells=len(cells),
        gpu=bool((lock.get('model_binding') or {}).get('gpu',False)),
        cpu_affinity=lock['cpu_affinity'], numerical_threads=lock['numerical_threads'],
        delivery=lock['delivery'], source_seconds=seconds,
        load_seconds=result.get('model_load_seconds'),
        compute_RTF=sum(c['compute_ms'] for c in cells)/1000/seconds,
        peak_sampled_process_rss_bytes=max(c['peak_process_rss_bytes'] for c in cells),
        first_text_elapsed_sec=span(c['first_text_elapsed_sec'] for c in cells),
        completion_after_audio_duration_sec=span(c['elapsed_seconds']-c['source_seconds'] for c in cells)
            if lock['delivery']=='source_paced_independent_producer' else None,
        last_speech_final_vs_audio_end_sec=span(c['finalization_after_source_sec'] for c in cells),
        timing_interpretation='Negative last-speech-final offsets mean EOU before trailing audio, not negative completion latency. Completion residual includes producer/flush/closure overhead.',
        memory_scope='sampled Windows ASR-process RSS; excludes full GUI/identity stack and native GPU device memory')


def primary_tables(lexical):
    if lexical['status'] != 'COMPLETE' or {r['variant'] for r in lexical['runs']} != {'A0','A1','A2','A3'}:
        raise ValueError('Four complete variants required')
    if len(lexical['runs']) != 4:
        raise ValueError('Duplicate variant')
    tables = []
    jobs = None
    for run in lexical['runs']:
        observed = {c['job_id'] for c in run['cells']}
        if (run['completed'] != 96 or run['total'] != 96 or len(observed) != 96
                or len(run['cells']) != 96 or not all(c['all_samples'] for c in run['cells'])):
            raise ValueError('Incomplete screen or audio accounting')
        if jobs is not None and observed != jobs:
            raise ValueError('Unmatched screen cells')
        jobs = observed
        rows = [row for row in run['table'] if row['reference_class']=='complete_nonoverlap']
        if len(rows)!=2 or {row['tap'] for row in rows}!={'O0','O1'}:
            raise ValueError('Missing primary tap')
        errors, words = sum(r['word_errors'] for r in rows), sum(r['reference_words'] for r in rows)
        tables.append(dict(variant=run['variant'], runtime=run['runtime'],
            primary_cells=sum(r['cells'] for r in rows), reference_words=words, word_errors=errors,
            combined_lexical_WER=errors/words, by_tap=rows,
            other_reference_classes=[r for r in run['table'] if r['reference_class']!='complete_nonoverlap']))
    return tables


def build(local):
    receipts = []
    lexical, lexical_job = completed_job(local/'plan-a1nominalv1.json', 'lexical-comparison', receipts)
    text, _ = completed_job(local/'plan-a1nominalv1.json', 'text-comparison', receipts)
    tables = primary_tables(lexical)
    # Exact paths from the completed scoring command, including legitimate reused parents.
    folders = [Path(lexical_job['argv'][i+1]) for i,v in enumerate(lexical_job['argv'][:-1]) if v=='--run']
    if len(folders)!=4:
        raise ValueError('Need the four bound screen inputs')
    screen_resources = []
    for folder in folders:
        result, cells, lock = complete_cells(folder, 96, receipts)
        score = next(r for r in lexical['runs'] if r['variant']==result['variant'])
        if score['run_result_sha256'] != binding(folder/'RESULT.json')['sha256']:
            raise ValueError('Scoring used different screen evidence')
        screen_resources.append(resource_summary(result, cells, lock))
    regressions, paced, cpu = [], [], []
    census_review = None
    for variant in ('A0','A1','A2','A3'):
        plan = local/('plan-a1nominalv1.json' if variant=='A1' else 'plan-v4.json')
        suffix = variant+'-onnx' if variant=='A1' else variant
        for kind, expected, output in [('regression',8,regressions), ('paced',8 if variant=='A1' else 4,paced)]:
            if kind=='paced' and variant=='A1':
                summary,census_review=a1_paced_census(local,receipts)
                output.append(summary)
                continue
            result, job = completed_job(plan, kind+'-'+suffix, receipts)
            result, cells, lock = complete_cells(Path(job['result']).parent, expected, receipts)
            output.append(resource_summary(result, cells, lock))
        if variant in ('A2','A3'):
            _, job = completed_job(plan, 'cpu-panel-'+variant, receipts)
            result, cells, lock = complete_cells(Path(job['result']).parent, 4, receipts)
            cpu.append(resource_summary(result, cells, lock))
    suite, _ = completed_job(local/'plan-a1controllerv2.json','prototype-suite-A1',receipts)
    if not suite['successful'] or suite['failures'] or suite['errors'] or not suite['source_unchanged']:
        raise ValueError('Final prototype suite failed')
    gui = []
    for variant, plan, job in [('A1','plan-a1controllerv2.json','actual-gui-A1'),
                               ('A2','plan-guifinalv1.json','actual-gui-A2'),
                               ('A3','plan-gui2corev1.json','actual-gui-A3-two-core')]:
        panel, _ = completed_job(local/plan,job,receipts)
        if panel['completed']!=3 or panel['requested_cells']!=3 or len(panel['cells'])!=3:
            raise ValueError('Incomplete GUI census')
        for cell in panel['cells']:
            if cell['status']!='COMPLETE' or not cell['archive_integrity_passed'] or cell.get('cleanup_error'):
                raise ValueError('GUI/closure/archive failure')
        expected_affinity = [4,14] if variant=='A3' else [4]
        actual_processes = []
        for process in panel['private_processes']:
            actual = require_hash(process['report'])
            if actual['cpu_affinity'] != expected_affinity:
                raise ValueError('Actual GUI process allocation differs')
            receipts.append(binding(process['report']['path']))
            actual_processes.append(dict(cell_id=process['cell_id'],cpu_affinity=actual['cpu_affinity']))
        gui.append(dict(variant=variant, cpu_affinity=[4,14] if variant=='A3' else [4],
            completed=3, elapsed_seconds=panel['elapsed_seconds'],
            verified_actual_processes=actual_processes,
            cells=[{k:c[k] for k in ['cell_id','status','archive_integrity_passed','elapsed_seconds']} for c in panel['cells']],
            scope='actual private desktop; unchanged 480x800 common GUI; functional checks, not CM5/realtime qualification'))
    parity_path = local/'numerical-a1servicev2/parity/RESULT.json'
    parity = load(parity_path)
    if parity['status']!='PASS_SERVICE_PARITY' or not parity['host_service_qualified']:
        raise ValueError('A1 service parity is not qualified')
    receipts.append(binding(parity_path))
    routes, _ = completed_job(local/'plan-v4.json','route-comparison',receipts)
    return dict(schema='n3-completed-evidence-review-v1',status='EVIDENCE_REVIEW_COMPLETE',
        utc=datetime.now(timezone.utc).isoformat(),stage_acceptance_claimed=False,
        screen_cells=384,regression_cells=32,paced_cells=20,gui_cells=9,a1_paced_census_review=census_review,
        lexical_normalization=lexical['runs'][0]['lexical_normalization'],primary=tables,
        screen_resources=screen_resources,regression_resources=regressions,paced_resources=paced,cpu_panels=cpu,
        text={k:text[k] for k in ['metrics','P0','P1','P2','ITN','contextual_reconstruction_F1','limits']},
        gui=gui,suite={k:suite[k] for k in ['tests','skipped','failures','errors','requested_modules','successful_modules','source','source_unchanged']},
        route_comparison=routes,
        receipts=list({r['path']:r for r in receipts}.values()),review_source=binding(__file__),
        limitations=['A3 one-core GUI failure remains; two-core contrast is a separate resource configuration.',
            'A0/A1 screens use CPU; A2/A3 screens use native CUDA. Compare CPU panels separately.',
            'One mono overlap hypothesis cpWER is diagnostic, not a diarized-system result.',
            '48 paired seen scenes do not select an N4 winner; complete 240-scene bank is pending.',
            'No raw transcripts, voice vectors, audio or weights are copied to this report.',
            'ARM64 software deployment is N5 work; physical CM5 checks remain deferred.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=build(args.local)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(status=report['status'],report=binding(args.output),stage_accepted=False)))


if __name__=='__main__':
    main()
