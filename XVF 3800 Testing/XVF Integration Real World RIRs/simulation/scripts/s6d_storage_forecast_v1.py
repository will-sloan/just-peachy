"""Bounded metadata-only whole-study forecast; README_S6D_STORAGE_FORECAST_V1.md."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import statistics

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
G=Path('G:/Just_Peachy_S6D/20260913T195357Z')
GIB=2**30


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bound_bytes(p):
    data=Path(p).read_bytes();return data,dict(path=str(Path(p).resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def save(p,value):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
def inventory(p):
    """Only explicitly selected closed sample folders, never any whole payload root."""
    p=Path(p);rows=[]
    for q in p.rglob('*'):
        if q.is_symlink():raise ValueError('Sample symlink needs explicit accounting')
        if q.is_file():rows.append(dict(path=str(q.relative_to(p)),bytes=q.stat().st_size))
        if len(rows)>1000:raise ValueError('Sample inventory exceeded bound')
    return dict(path=str(p),files=len(rows),bytes=sum(r['bytes'] for r in rows),inventory=rows)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output.resolve()
    if not out.is_relative_to(R.resolve()) or out.exists():raise ValueError('Fresh small report directory required')
    out.mkdir(parents=True)
    refs=[]
    def get(p):
        data,b=bound_bytes(p);refs.append(b);return json.loads(data.decode('utf-8-sig'))
    health_path=G/'runner/native_execution_queue_preparation_v1/native176_state/HEALTH.jsonl'
    # Reading an existing log does not start or repeat its census.
    health_bytes,health_binding=bound_bytes(health_path);health=json.loads(health_bytes.splitlines()[-1])
    census=health['payload_census'];assert census['has_complete'] and not census['stale'] and not census['pending'] and census['error'] is None
    existing=census['complete_bytes']
    cp_path=G/'runner/native_execution_queue_preparation_v1/native176_state/CHECKPOINT.json';cp_data,cp_binding=bound_bytes(cp_path);cp=json.loads(cp_data)
    ledger_data,ledger_binding=bound_bytes(R/'physical_ledger.json');ledger=json.loads(ledger_data)
    assert len(ledger['passes'])==52, 'Re-declare remaining bank if actual physical state changes'
    bank=get(R/'physical_bank_preparation_v1/PREPARATION_RESULT.json')
    attempts=[row for group in bank['groups'] for row in get(group['plan']['path'])['attempts']]
    assert len(attempts)==394
    retained={f'P_MAIN6_S45_01_{i:02d}' for i in range(1,17)}
    assert all(next(x for x in ledger['passes'] if x['attempt_id']==key)['status']=='PASS' for key in retained)
    remaining=[x for x in attempts if x['attempt_id'] not in retained]
    # Original pre-QA and failed17 are replacements under fresh IDs, not an extra second copy.
    assert len(remaining)==378
    source_seconds=sum(x['duration_sec'] for x in remaining);carrier_seconds=sum(x['duration_sec']+4 for x in remaining)
    charged_seconds=sum(x['duration_sec']+4+16383/48000 for x in remaining)
    assert abs(sum(x['charged_playback_s'] for x in ledger['passes'])+charged_seconds-19744.058)<1e-5
    samples=[]
    passed=[x for x in ledger['passes'] if x['status']=='PASS' and x.get('result')]
    chosen=[next(x for x in passed if x['attempt_id']=='P_MAIN6_S45_01_01')]
    for profile in ('P_MAIN6','P_SCAN6','P_INPUT_QA6'):
        candidates=[x for x in passed if x['profile']==profile]
        chosen.append(max(candidates,key=lambda x:x['source_duration_s']))
    for row in chosen:
        inv=inventory(Path(row['result']['path']).parent);inv.update(kind='physical',attempt_id=row['attempt_id'],profile=row['profile'],source_seconds=row['source_duration_s'],carrier_seconds=row['source_duration_s']+4,bytes_per_carrier_second=inv['bytes']/(row['source_duration_s']+4));samples.append(inv)
    physical_rates=[z['bytes_per_carrier_second'] for z in samples]

    manifests={}
    for name in ('ORIGINAL_PARENT','REPAIRED_GUIV3','TK8','HOST2'):
        manifests[name]=get(R/'runner/native_execution_queue_preparation_v1/manifests'/f'{name}_MANIFEST.json')
    jobs=manifests['ORIGINAL_PARENT']['jobs']+manifests['REPAIRED_GUIV3']['jobs'];assert len(jobs)==176
    done=set(cp['completed']);assert done<=set(x['job_id'] for x in jobs)
    pending=[x for x in jobs if x['job_id'] not in done]
    selected={}
    for job in jobs:
        if job['job_id'] in done:
            selected.setdefault((job['candidate'],job['variant'],job['asr_tap']),job)
    assert len(selected)<=12 and len(selected)>=4
    for job in selected.values():
        inv=inventory(job['output']);seconds=job['expected_frames']/16000
        result=get(Path(job['output'])/'RESULT.json');assert result['status']=='COMPLETE' and result['job']['job_id']==job['job_id']
        inv.update(kind='native',job_id=job['job_id'],candidate=job['candidate'],variant=job['variant'],source_seconds=seconds,bytes_per_source_second=inv['bytes']/seconds);samples.append(inv)
    native_rates=[x['bytes_per_source_second'] for x in samples if x['kind']=='native']
    low,center,high=min(native_rates),statistics.median(native_rates),max(native_rates)
    serial_prep=get(R/'runner/native_serial892_preparation_v1/PREPARATION_RESULT.json')
    serial_jobs=[row for ref in serial_prep['manifests'] for row in get(ref['path'])['jobs']];assert len(serial_jobs)==892
    serial_seconds=sum(j['expected_frames']/16000 for j in serial_jobs)
    historical_serial=get(R/'runner/native_serial892_preparation_v1/FORECAST.json')
    beam=get(R/'application/beam_execution_predecl_v3/PROSPECTIVE_PLAN.json')
    c=get(R/'application/beam_C_collection_preparation_v2/MANIFEST.json')
    task_groups=defaultdict(list)
    for x in beam['tasks']:task_groups[x['stage']].append(x)
    assert {k:len(v) for k,v in task_groups.items()}=={'C_collection':12,'main_core':96,'stream_diagnostics':528}
    scene_duration={x['case_id']:x['duration_sec'] for x in attempts if x['role']=='canonical'}
    core_sources=sum(scene_duration[t['case_id']] for t in task_groups['main_core'])
    diag_sources=sum(scene_duration[t['case_id']] for t in task_groups['stream_diagnostics'])
    core_seconds=core_sources+96*4;diag_seconds=diag_sources+528*4
    c_seconds=sum(x['expected_frames']/16000 for x in c['jobs'])
    enrollment=get(G/'enrollment_continuous_inputs_v1/PREPARATION_RESULT.json')
    assert enrollment['enrollment_file_count']==60 and enrollment['continuous_file_count']==2
    rows=[]
    def row(name,count,seconds,lo,mid,hi,basis):
        rows.append(dict(work=name,remaining_jobs=count,seconds=seconds,low_bytes=lo,central_bytes=mid,high_bytes=hi,basis=basis))
    row('physical remaining bank including E60 and continuous2',378,charged_seconds,carrier_seconds*min(physical_rates),carrier_seconds*statistics.median(physical_rates),charged_seconds*max(physical_rates)*1.15,'Four closed MAIN/SCAN/QA samples; all retained representations. High adds 15% sensitivity, not a proven bound. Separate batch/control overhead is in allowance.')
    remaining_seconds=sum(j['expected_frames']/16000 for j in pending)
    row('native176 not yet declared complete',len(pending),remaining_seconds,remaining_seconds*low,remaining_seconds*center,remaining_seconds*high*1.15,'Actual original/repaired closed job inventories. Active unfinished cell is allocated in full, conservatively double-counting its already-written prefix.')
    row('serial892 full native confirmation',892,serial_seconds,serial_seconds*low,serial_seconds*center,serial_seconds*high*1.15,'Same current native output schema; observed bytes per source second. Source profiles can alter event population. Historical forecast is recorded separately.')
    tk_seconds=sum(j['expected_frames']/16000 for j in manifests['TK8']['jobs'])
    row('real Tk views eight jobs',8,tk_seconds,tk_seconds*low,tk_seconds*center*1.5,tk_seconds*high*3,'No completed native Tk sample. 1x/1.5x/3x native factors are explicit view/text-log sensitivity assumptions, not measurements.')
    host_seconds=sum(j['expected_frames']/16000 for j in manifests['HOST2']['jobs'])
    row('HOST continuous two jobs',2,host_seconds,host_seconds*low,host_seconds*center,host_seconds*high*2,'Exact declared 1827.426625s each. Linear low/central and 2x high sensitivity; growing transcript/event text can exceed linear scaling. Distinct from physical900s sessions.')
    row('beam C collection12',12,c_seconds,c_seconds*(low+32000),c_seconds*(center*1.5+32000),c_seconds*(high*3+32000),'Exact captured frames. Usually3 PCM16 journals versus2 native journals; extra32kB/s plus unmeasured beam/probe log factors.')
    row('beam main core96',96,core_seconds,core_seconds*(low+32000),core_seconds*(center*1.5+32000),core_seconds*(high*2.5+32000),'No completed beam sample. Source+4s convention approximates future decoded capture duration;3-journal allowance. Beam identity/control events require sensitivity factors.')
    row('beam independent stream diagnostics528',528,diag_seconds,diag_seconds*low,diag_seconds*center,diag_seconds*high*1.25,'Two PCM16 journals per ordinary native stream diagnostic, even same-tap ASR/identity. Source+4s approximate future decoded duration;25% high sensitivity.')
    row('future batch/control, scoring, galleries, listening, reports and closeout allowance',None,None,.5*GIB,1.5*GIB,3*GIB,'Explicit unmeasured planning allowance, not an authorization or statistical interval. Includes small future E-derived gallery/calibration outputs and CM5/report logs; new weight copies or broad reruns are not assumed.')
    totals={k:existing+sum(z[k+'_bytes'] for z in rows) for k in ('low','central','high')}
    nominal_physical_pcm=carrier_seconds*4*48000*2*3
    snapshot=dict(created_utc=datetime.now(timezone.utc).isoformat(),health_log_at_read=health_binding,health=health,checkpoint_at_read=cp_binding,checkpoint=cp,ledger_at_read=ledger_binding,ledger=ledger,immutable_metadata_bindings=refs,closed_sample_inventories=samples)
    save(out/'INPUT_SNAPSHOT.json',snapshot)
    report=dict(schema='s6d-whole-study-storage-forecast.v1',status='FORECAST_ONLY_NOT_ADMISSION',created_utc=snapshot['created_utc'],source=bound_bytes(__file__)[1],input_snapshot=bound_bytes(out/'INPUT_SNAPSHOT.json')[1],cap_bytes=40*GIB,current_complete_census_bytes=existing,census_utc=health['utc'],census_age_seconds=health['payload_accounting_age_s'],census_roots=census['logical_roots'],disk_free_bytes_observed=health['disk_free_bytes'],physical_remaining=dict(count=378,source_seconds=source_seconds,carrier_seconds=carrier_seconds,charged_seconds=charged_seconds,total_eventual_attempts=430,total_eventual_charged_seconds=19744.058,roles=dict(Counter(x['role'] for x in remaining)),nominal_four_PCM_representations_bytes=nominal_physical_pcm,replacement_ids=['QA_P_MAIN6_B1_PRE_R3','P_MAIN6_S45_01_17_R2'],physical_ledger_52_preserved=True),native176_completed_snapshot=len(done),samples=dict(physical_rate_range=physical_rates,native_rate_range=native_rates),existing_E_continuous_inputs=dict(count=62,bytes=enrollment['output_WAV_bytes'],already_in_census=True,additional_construction_bytes=0),rows=rows,total_bytes=totals,total_gib={k:v/GIB for k,v in totals.items()},exceeds_cap={k:v>40*GIB for k,v in totals.items()},historical_serial892_forecast=historical_serial['new_payload_max_observed_cell_scaled_gib'],conclusion='40 GiB is not plausible under current retained-output formats and these measured-rate extrapolations; even the low planning estimate exceeds it. This is not a mathematical minimum or permission to change the cap.',limitations=['Ranges are sensitivity scenarios, not confidence intervals or guaranteed upper bounds.','No full root walk or waveform-content hashing. Only existing census plus up to12 native and4 physical closed folders were inventoried.','Census complete_bytes is from its last completed all-root pass; currently shown root_coverage may describe its in-progress next scan.','Plans beyond fixed jobs, unplanned retries, actual beam event populations, continuous growing text and model/deployment copies may add more.','Mandatory E60 and physical900s2 are already within physical378; HOST2 is separately included. Their prepared input WAVs are already in the census.','Current cap/floors, scopes, outputs and evidence retention are unchanged; this artifact makes no admission, deletion, compression or capacity decision.'],no_NN=True,no_hardware=True,no_scope_or_cap_change=True)
    save(out/'FORECAST.json',report)
    lines=[f"# S6D whole-study storage forecast\n\nThe current retention plan is **not plausibly within 40 GiB**. The sample-based total is **{totals['central']/GIB:.2f} GiB**, with a **{totals['low']/GIB:.2f}â€“{totals['high']/GIB:.2f} GiB planning sensitivity range**. These are estimates, not a statistical interval or a mathematical minimum. No cap or output requirement changed.\n",f"The saved {health['utc']} completed census reports **{existing/GIB:.3f} GiB** across R, G and the listening root. The active census pass was not repeated. The native176 checkpoint had {len(done)} completed jobs; all other jobs, including the active prefix, receive full future allocation.\n","| Remaining work | Jobs | Low GiB | Central GiB | High GiB |\n|---|---:|---:|---:|---:|"]
    for z in rows:lines.append(f"| {z['work']} | {z['remaining_jobs'] or 'allowance'} | {z['low_bytes']/GIB:.2f} | {z['central_bytes']/GIB:.2f} | {z['high_bytes']/GIB:.2f} |")
    lines.extend([f"\nPhysical378 has {charged_seconds:.6f} charged seconds; combined with the preserved52 attempts it is430 attempts/{19744.058:.3f}s. Its four aggregate PCM representations alone nominally require {nominal_physical_pcm/GIB:.2f} GiB before telemetry/control metadata. Four actual sample folders establish the physical range. {len(native_rates)} current closed native samples establish mono rates; the saved earlier serial892 forecast was {report['historical_serial892_forecast']:.2f} GiB.\n",f"The62 E/continuous input WAVs ({enrollment['output_WAV_bytes']/GIB:.3f} GiB) are already included in the census. E60 and the two900s physical sessions are inside physical378. HOST2 uses two exact1827.426625s existing sources and is counted separately. C12 uses actual declared capture frames; core96/diagnostics528 use original source duration plus4s until exact future capture frames exist.\n","No real Tk/beam/host-long storage sample exists. Their factors and the0.5â€“3GiB reporting/gallery/listening allowance are explicit assumptions. Full widget text, beam probes, growing transcript state, retries or new deployment copies can exceed these scenarios. The cap remains a hard admission/runtime check; this forecast does not choose deletion, compression, larger capacity or reduced scope.\n",f"Evidence and reproduction: [FORECAST.json](<{(out/'FORECAST.json').as_posix()}>), [frozen input snapshot and sample inventories](<{(out/'INPUT_SNAPSHOT.json').as_posix()}>), [README](<{(SIM/'scripts/README_S6D_STORAGE_FORECAST_V1.md').as_posix()}>). The snapshot contains exact metadata hashes, saved mutable census/checkpoint/ledger contents, selected file-size inventories and all limitations. No waveform data or large payload was copied.\n"])
    (out/'FORECAST.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(output=str(out),forecast=bound_bytes(out/'FORECAST.json')[1],total_gib=report['total_gib'],native_remaining=len(pending),physical_remaining=378),indent=2))


if __name__=='__main__':main()
