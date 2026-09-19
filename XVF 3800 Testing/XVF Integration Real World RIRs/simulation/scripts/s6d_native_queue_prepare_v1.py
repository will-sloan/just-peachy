"""Build literal held production queues; see README_S6D_NATIVE_QUEUE_PREPARE_V1.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

SIM=Path(__file__).resolve().parent.parent
R=SIM/'reports/S6D/20260913T195357Z'
G=Path('G:/Just_Peachy_S6D/20260913T195357Z')
PYTHON=SIM.parents[2]/'.edge-speech-env/python.exe'
RUNNER=R/'runner/source_epoch_census_v4/s6d_runner_v1.py'
RUNNER_SHA='fdffb4cae7c111302b90d4128d8b44049354cd225f241868f6d83a5a2fab15b4'
EVIDENCE=SIM/'scripts/s6d_native_evidence_v1.py'
EVIDENCE_SHA='bb1b5ff846f8edad386b573dea203df7b08e9c31b8126e7c3aa14a8cccb226d2'


def binding(path):
    path=Path(path).resolve();h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1048576),b''):h.update(part)
    return dict(path=str(path),bytes=path.stat().st_size,sha256=h.hexdigest())


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def write(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    return binding(path)


def unique(bindings):
    result={}
    for b in bindings:
        if b['path'] in result and result[b['path']]!=b:raise ValueError('Conflicting source binding')
        result[b['path']]=b
    return list(result.values())


def prepare(preparation,wrapper,wrapper_sha256,wrapper_review,output):
    preparation=Path(preparation).resolve();output=Path(output).resolve()
    if output.parent!=R/'runner':raise ValueError('Fresh runner report directory required')
    prior=read(preparation/'PREPARATION_RECEIPT.json')
    wrapper_bound=binding(wrapper);review_bound=binding(wrapper_review)
    if wrapper_bound['sha256']!=wrapper_sha256:raise ValueError('Reviewed wrapper changed')
    runner=binding(RUNNER);evidence=binding(EVIDENCE)
    if runner['sha256']!=RUNNER_SHA or evidence['sha256']!=EVIDENCE_SHA:raise ValueError('Accepted protocol dependencies changed')
    accepted=read(RUNNER.parent/'ROOT_SOURCE_ACCEPTANCE.json')
    if accepted['status']!='ROOT_ACCEPTED_CENSUS_RUNNER_V4' or accepted['runner']!=runner:raise ValueError('Census runner not accepted')
    output.mkdir(exist_ok=False);manifests=output/'manifests';manifests.mkdir()
    final_manifests=[];by_job={};source_manifests={}
    for prior_bound in prior['manifests']:
        if binding(prior_bound['path'])!=prior_bound:raise ValueError('Prepared manifest changed')
        m=read(prior_bound['path'])
        if m['evidence_helper']['sha256']!=EVIDENCE_SHA or binding(m['evidence_helper']['path'])!=m['evidence_helper']:raise ValueError('Prepared evidence helper changed')
        m.update(protocol_sources=dict(runner=runner,evidence=m['evidence_helper']),protocol_wrapper=wrapper_bound,protocol_review=review_bound,prior_prepared_manifest=prior_bound)
        if m['limits']['cpu_affinity']!=[12,13,14,15]:raise ValueError('Root-agreed affinity changed')
        mb=write(manifests/Path(prior_bound['path']).name,m);final_manifests.append(mb);source_manifests[prior_bound['path']]=mb
        for job in m['jobs']:
            if job['job_id'] in by_job:raise ValueError('Duplicate across native/Tk/HOST jobs')
            by_job[job['job_id']]=(job,m,mb)
    order=read(preparation/'NATIVE176_READY_FOR_PROTOCOL.json')['job_order']
    tk_ids=[j['job_id'] for j in read(final_manifests[2]['path'])['jobs']]
    host_ids=[j['job_id'] for j in read(final_manifests[3]['path'])['jobs']]
    if [len(order),len(tk_ids),len(host_ids)]!=[176,8,2]:raise ValueError('Fixed population differs')
    owner=read(R/'runner/native_pilot_proposed_v1/PROPOSED_QUEUE.json')
    outputs=[];literal=[]
    for group,ids in [('native176',order),('tk8',tk_ids),('host2',host_ids)]:
        folder=output/group;folder.mkdir();jobs=[]
        for identifier in ids:
            job,m,mb=by_job[identifier];protocol=G/'runner'/output.name/group/identifier
            completion=protocol/'COMPLETION.json';native_output=Path(job['output']);audit=native_output/'FULL_SOURCE_AUDIT.json'
            argv=[str(PYTHON),wrapper_bound['path'],'--helper',m['helper']['path'],'--helper-sha256',m['helper']['sha256'],'--manifest',mb['path'],'--manifest-sha256',mb['sha256'],'--native-job-id',identifier]
            sources=unique([runner,wrapper_bound,mb,m['helper'],m['readme'],evidence,*m['execution_files'],*m.get('support_files',[]),job['profile_binding'],*([job['gallery']] if job['gallery'] else [])])
            expected=dict(status='COMPLETE',failure=None,native_job_id=identifier,protocol_observer_closed=True,protocol_observer_errors=[],native_run_one_same_process=True,subprocess_spawned_by_wrapper=False,stop_requested=False,full_source_evidence_validated=True,affinity_verified=[12,13,14,15])
            expected.update({'manifest.sha256':mb['sha256'],'helper.sha256':m['helper']['sha256'],'wrapper.sha256':wrapper_bound['sha256'],'completion_audit.path':str(audit)})
            if group=='tk8':expected['tk_view_evidence_validated']=True
            artifacts=[dict(path=str(completion),format='json',min_bytes=1,expected_fields=expected),
                dict(path=str(native_output/'RESULT.json'),format='json',min_bytes=1,expected_fields={'status':'COMPLETE','failure':None,'native_tested':True,'resource_observer_closed':True,'observer_errors':[],'completion_errors':[],'event_consumer_drained':True,'telemetry.state':'COMPLETED','job.job_id':identifier,'manifest.sha256':mb['sha256']}),
                dict(path=str(audit),format='json',min_bytes=1,expected_fields={'status':'PASS_OFFLINE_EVIDENCE','errors':[],'expected_frames_predeclared':True,'job_id':identifier,'manifest.sha256':mb['sha256'],'source.sha256':EVIDENCE_SHA,'dispatch.frames':job['expected_frames'],'journals.source.frames':job['expected_frames'],'journals.source.sha256':job['audio_pcm_sha256']})]
            if group=='tk8':
                artifacts.append(dict(path=str(native_output/'OWNED_RESOURCE_CLOSURE.json'),format='json',min_bytes=1,expected_fields={'resources_closed':True,'setup_or_loop_error':None,'cleanup_errors':[],'startup_thread_alive':False,'observer_thread_alive':False,'root_destroyed':True,'consumer_closed':True,'render_files_closed':True,'gallery_spy_restored':True}))
            qjob=dict(job_id=identifier,kind='offline',workload='sensitive',argv=argv,cwd=m['source_root'],source_bindings=sources,
                heartbeat_path=str(protocol/'HEARTBEAT.json'),completion_path=str(completion),stop_request_path=str(protocol/'STOP_REQUEST.json'),timeout_s=7500 if group=='host2' else 360,stall_after_s=300 if group=='host2' else 180,heartbeat_stale_s=45,stop_grace_s=75,allow_owned_termination=True,expected_artifacts=artifacts,native_input_seconds=job['audio_duration_sec'],scientific_role=job['scientific_role'],stop_policy_note='Same-process checkpoint engine.stop;75-second cooperative grace then only exact owned offline termination; stopped prefixes cannot satisfy full-source evidence')
            jobs.append(qjob);literal.append(dict(group=group,job_id=identifier,argv=argv,cwd=m['source_root'],manifest=mb,output=job['output']))
        queue={k:deepcopy(owner[k]) for k in ['schema','run_id','owner_thread_id','owner_session_id','fixture_only','campaign','disk_policy','payload_policy']}
        queue.update(runner_sha256=runner['sha256'],created_utc=datetime.now(timezone.utc).isoformat(),production_status='PROPOSED_ROOT_COMBINED_ADOPTION_REQUIRED',jobs=jobs,preparation=binding(preparation/'PREPARATION_RECEIPT.json'),protocol_wrapper=wrapper_bound,protocol_review=review_bound,group=group)
        qb=write(folder/'QUEUE.json',queue)
        proposal=dict(schema='s6d_queue_approval_v1',run_id=queue['run_id'],queue_sha256=qb['sha256'],authorization_ref=str(folder/'ROOT_ADMISSION.json'),approved_job_sha256=[],proposed_job_sha256=[digest(j) for j in jobs],executable_bindings=[binding(PYTHON)],allowed_working_directories=sorted({j['cwd'] for j in jobs}),allowed_output_roots=queue['payload_policy']['new_payload_roots'],approval_state='NOT_APPROVED_ROOT_MUST_ADOPT_EXACT_JOBS')
        ab=write(folder/'APPROVAL_PROPOSAL.json',proposal)
        outputs.append(dict(group=group,queue=qb,approval_proposal=ab,job_count=len(jobs),state_dir=str(G/'runner'/output.name/(group+'_state')),root_admission_path=str(folder/'ROOT_ADMISSION.json'),approval_path=str(folder/'APPROVAL.json')))
    scoring=read(preparation/'PROSPECTIVE_SCORING_BINDINGS.json');scoring['execution_manifests']=[source_manifests[x['path']] for x in scoring['execution_manifests']]
    for row in scoring['rows']:row['manifest']=source_manifests[row['manifest']['path']]
    scoring['host_manifest']=source_manifests[scoring['host_manifest']['path']];scoring['tk_manifest']=source_manifests[scoring['tk_manifest']['path']]
    scoring['root_approval_required']=True;scoring['protocol_audits_required']=True
    sb=write(output/'PROSPECTIVE_SCORING_BINDINGS.json',scoring)
    receipt=dict(schema='s6d-native-queue-preparation.v1',status='PROPOSED_EXACT_QUEUES_NOT_APPROVED',source=binding(__file__),preparation=binding(preparation/'PREPARATION_RECEIPT.json'),runner=runner,runner_acceptance=binding(RUNNER.parent/'ROOT_SOURCE_ACCEPTANCE.json'),wrapper=wrapper_bound,wrapper_review=review_bound,manifests=final_manifests,groups=outputs,literal_jobs=literal,prospective_scoring=sb,job_counts=dict(native176=176,tk8=8,host2=2),no_launches=True)
    rb=write(output/'QUEUE_PREPARATION_RECEIPT.json',receipt)
    launcher='''param([ValidateSet('native176','tk8','host2')][string]$Group='native176', [switch]$Execute)
$ErrorActionPreference = 'Stop'
$plan = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'QUEUE_PREPARATION_RECEIPT.json') | ConvertFrom-Json
$selected = @($plan.groups | Where-Object { $_.group -eq $Group })
if ($selected.Count -ne 1) { throw 'One exact group required' }
$selected = $selected[0]
if (-not (Test-Path -LiteralPath $selected.approval_path)) { throw 'Root must write exact APPROVAL.json before validation or execution' }
$approval = Get-Content -Raw -LiteralPath $selected.approval_path | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $approval.authorization_ref)) { throw 'Root admission evidence is absent' }
$queueSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $selected.queue.path).Hash.ToLower()
if ($queueSha -ne $selected.queue.sha256 -or $approval.queue_sha256 -ne $queueSha) { throw 'Exact reviewed queue/approval binding differs' }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $plan.runner.path).Hash.ToLower() -ne $plan.runner.sha256) { throw 'Accepted runner source differs' }
$approvalSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $selected.approval_path).Hash.ToLower()
$python = 'C:\\Users\\amiri\\Documents\\GitHub\\just-peachy\\.edge-speech-env\\python.exe'
$runnerArgs = @('-B', $plan.runner.path, '--queue', $selected.queue.path, '--queue-sha256', $queueSha, '--approval', $selected.approval_path, '--approval-sha256', $approvalSha, '--state-dir', $selected.state_dir)
if ($Execute) { $runnerArgs += '--keep-awake' } else { $runnerArgs += '--validate-only' }
& $python @runnerArgs
exit $LASTEXITCODE
'''
    (output/'Invoke-Native-Queue.ps1').write_text(launcher,encoding='utf-8')
    lines=['# Exact native production queues — root adoption required','',
        'These queues are prepared, not approved. Native176 has priority; Tk8 and HOST2 are separately admitted groups. No job was launched by preparation. Root must review wrapper/queue and write each exact ROOT_ADMISSION.json plus APPROVAL.json before these commands can run. APPROVAL_PROPOSAL.json deliberately has no approved jobs. Preserve its proposed_job_sha256 list; root may adopt those exact hashes only after review. Do not edit historical inputs or manufacture protocol completion.','',
        'All groups use accepted censusV4, serial workers on logical CPUs12,13,14,15 and one thread per model pool. C50/G75GiB floors, shared40GiB cap, matching owner exit,75-second cooperative stop grace, whole-source bb1b audit and Sep16 19:53:57Z deadline with45-minute closeout reserve remain enforced. Do not overlap with physical observer contrasts or another native queue without root admission. Headless clocks are not Tk render clocks; Tk callback/widget clocks are not scanout.','',
        'Inputs are the frozen manifests, exact original waveforms/galleries/profiles/weights and the independently reviewed wrapper. Outputs are fresh G native/session/consumer/PCM/audit/result/protocol files. A native RESULT alone never makes a queue cell COMPLETE; wrapper full-input proof and protocol closure must also pass. Later correctness uses PROSPECTIVE_SCORING_BINDINGS.json only after actual output/owner admission; this preparation does not run scoring.','',
        '`Invoke-Native-Queue.ps1` accepts `-Group native176`, `tk8` or `host2`. It verifies the exact queue/approval/runner and requires root admission evidence. Its default is validate-only; `-Execute` is a separate root-authorized launch. Inputs are the local preparation receipt and adopted approval; outputs are supervisor validation or the declared state/native/protocol files.','',
        'Anaconda Prompt / CMD (validate-only after root adoption):','','```bat',f'powershell -NoProfile -File "{output / "Invoke-Native-Queue.ps1"}" -Group native176','```','','PowerShell can invoke the same file with `&` and the same group. Change only the group to validate Tk8 or HOST2. Add `-Execute` only after root explicitly admits that group; no task was launched while writing these commands.','']
    for group in outputs:
        lines.extend([f"## {group['group']} ({group['job_count']} jobs)",'',f"Queue SHA256: `{group['queue']['sha256']}`.",'','PowerShell (validate-only after root writes the exact approval):','','```powershell',f"$approval = '{group['approval_path']}'",f"& '{PYTHON}' -B '{RUNNER}' --queue '{group['queue']['path']}' --queue-sha256 '{group['queue']['sha256']}' --approval $approval --approval-sha256 (Get-FileHash -Algorithm SHA256 -LiteralPath $approval).Hash.ToLower() --state-dir '{group['state_dir']}' --validate-only",'```','','For the separately authorized launch, replace `--validate-only` with `--keep-awake`. Do not run multiple groups concurrently.','','Anaconda Prompt / CMD can start PowerShell and paste the exact block above (`powershell -NoProfile`); it uses the existing Python environment and needs no package installation.',''])
    lines.extend(['## Remaining allocation','',
        'The176 forecast is3.77–4.05h from actual12-job timings. Tk8 extrapolation is0.18–0.25h and HOST2 is1.75–1.88h, roughly5.70–6.18h before scoring/closeout; reserve7h. The four-CPU placement and concurrent Tk view load are not benchmarked. Full240/both-tap repairedC065/C088 remains960 new calls (about20.89–22.41h); original controls add960 if exact cache equivalence cannot be proven. These are separate pending allocations, not silently completed by176 or replay. B15 native/gallery checks, physical beam/C calibration/CM5 and retained selected-mode coverage remain separate.'])
    (output/'README_RUN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(rb));return rb


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['preparation','wrapper','wrapper-review','output']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--wrapper-sha256',required=True);a=p.parse_args()
    prepare(a.preparation,a.wrapper,a.wrapper_sha256,a.wrapper_review,a.output)
