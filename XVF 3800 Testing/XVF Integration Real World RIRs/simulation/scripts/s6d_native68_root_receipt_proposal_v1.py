"""One complete, unapproved native176 retention and fixed68 root-receipt proposal."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
G=Path('G:/Just_Peachy_S6D/20260913T195357Z')
PINS={
 'validation':(G/'application/native176_composite_closed_inputs_v2/VALIDATION.json','885634c7ec270c8f177d8241cf73b57a108282785ff878a445b0844692fc36c9'),
 'index':(G/'application/native176_composite_closed_inputs_v2/scores/INDEX.json','3069b2bffbbb9c75f104e81637881c86702371c40c4d978effe03c4777fd5467'),
 'credit_metadata':(G/'application/native176_results_analysis_v1/CREDIT68_METADATA_PROPOSAL.json','cc578c3f14a3f5151efc7f44cfb52c5c2fb7bac2b161072dfb764e27d364bae3'),
 'peer_review':(G/'review_fixtures/native68_membership_independent_v1/REVIEW.json','422a92c108c7f0e1d3f02532e35f7b2351728ee3475faeb98f2efd65064eaabf'),
 'delivery':(R/'application/native176_scoring_results_v1/DELIVERY.json','1f673053469a062b8dba62b247eb48a784ebd4294eb267b34e219a40784d6788'),
 'retention_report':(G/'application/native176_retention_report_v1/RECEIPT.json','835cc578273773aa7a384f073a637c240e8573d2b00a12ea1cdaabb30573bf89'),
}
SCIENCE=('source_root','execution_files','assets','gallery_index','helper','evidence_helper')
JOBSCIENCE=('profile','profile_binding','gallery','telemetry','settings','asr_tap','identity_tap')
LIMITS=('serial_jobs','cell_timeout_sec','resource_sample_sec','cpu_threads_each','cpu_affinity','no_audio_playback')

def need(ok,message):
    if not ok:raise ValueError(message)
def binding(path,data=None):
    p=Path(path).resolve();data=p.read_bytes() if data is None else data
    return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def canonical_digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

class Reader:
    def __init__(self):self.cache={}
    def get(self,b):
        p=str(Path(b['path']).resolve())
        if p not in self.cache:
            raw=Path(p).read_bytes();self.cache[p]=(json.loads(raw.decode('utf-8-sig')),binding(p,raw))
        obj,actual=self.cache[p];need(actual==b,'Metadata binding differs: '+p);return obj

def main(output):
    output=Path(output).resolve();need(not output.exists(),'Fresh output file required')
    reader=Reader();values={};refs={}
    for key,(path,sha) in PINS.items():
        b=binding(path);need(b['sha256']==sha,'Pinned metadata differs: '+key);refs[key]=b;values[key]=reader.get(b)
    validation,index,credit,peer,delivery,report=(values[k] for k in ('validation','index','credit_metadata','peer_review','delivery','retention_report'))
    need(validation['status']=='ALL176_COMPOSITE_CLOSED_INPUTS_VERIFIED' and validation['original_completed']==171 and validation['recovery_completed']==5,'Full composite closure absent')
    need(index['scored_jobs']==index['declared_jobs']==176 and index['complete_metric_matrix'] is True and index['unavailable_jobs']==[],'Scored population absent')
    need(peer['status']=='PASS_METADATA_MEMBERSHIP_ONLY' and peer['source_assets_gallery_graph_equal'] is True and peer['unchanged_profile_gallery_settings'] is True,'Peer source equivalence absent')
    need(peer['conditional_credits']==68 and peer['accepted_credits']==0 and peer['new_jobs']==892 and peer['full_scope']==960,'Peer membership differs')
    matrix=reader.get(peer['matrix']);old=reader.get(peer['original_manifest']);future=[reader.get(b) for b in peer['future_manifests']]
    need(matrix['accepted_credits']==0 and len(matrix['conditional_credits'])==68 and len(matrix['rows'])==892,'Future matrix is not unchanged conditional proposal')
    oldjobs={j['job_id']:j for j in old['jobs']};proofs={x['job_id']:x for x in validation['completion_validations']};scores={x['job_id']:x['score'] for x in index['rows']}
    peermembers={x['scientific_job_id']:x for x in peer['membership']};declared={x['preferred_predeclared_job']:x for x in matrix['conditional_credits']}
    need(len(declared)==len(peermembers)==68 and set(declared)==set(peermembers),'Fixed preferred population differs')
    for fm in future:
        need(all(fm[k]==old[k] for k in SCIENCE),'Scientific model/helper/source/vector graph changed')
        need(all(fm['limits'][k]==old['limits'][k] for k in LIMITS),'Declared pacing/allocation context changed')
        need(fm['limits']['max_new_payload_gib']==80 and old['limits']['max_new_payload_gib']==40,'Unexpected budget migration')
    entries=[];galleries={};profiles={}
    for existing in credit['credits']:
        dec=existing['declaration'];jid=dec['preferred_predeclared_job'];need(dec==declared[jid],'Fixed credit declaration differs')
        j=oldjobs[jid];pr=proofs[jid];member=peermembers[jid]
        need(jid.endswith('_delivery_repair_r1') and j['candidate'] in ('C065','C088') and j['repeat_index']==1,'Forbidden credit substitution')
        need(pr['execution_job_id']==jid and existing['result']==next(a for a in pr['validation']['artifacts'] if Path(a['path']).name=='RESULT.json'),'Actual preferred native result is not in full176 proof')
        need(existing['full_source_audit']==next(a for a in pr['validation']['artifacts'] if Path(a['path']).name=='FULL_SOURCE_AUDIT.json'),'Actual preferred full-source audit absent')
        need(existing['completion']==pr['validation']['completion'] and existing['score']==scores[jid],'Completion/score join differs')
        need(j['audio']==member['audio'] and j['audio_pcm_sha256']==member['audio_pcm_sha256'] and j['expected_frames']==j['expected_identity_frames']==member['expected_frames'],'Exact PCM/frame declaration differs')
        need(j['profile_binding']==member['profile'] and j['gallery']==member['gallery'],'Profile/gallery declaration differs')
        templates=[]
        for ref,fm in zip(peer['future_manifests'],future):
            matches=[x for x in fm['jobs'] if x['candidate']==j['candidate'] and x['asr_tap']==j['asr_tap'] and x['identity_tap']==j['identity_tap']]
            for candidate in matches:need(all(candidate[k]==j[k] for k in JOBSCIENCE),'Future scientific job template differs')
            if matches:templates.append(dict(manifest=ref,matching_native_template_jobs=len(matches),template_job=matches[0]['job_id']))
        need(templates,'Future matching scientific template absent')
        profiles[j['profile_binding']['path']]=dict(binding=j['profile_binding'],declared_profile=j['profile'])
        if j['gallery'] is not None:
            gallery=reader.get(j['gallery'])
            galleries[j['gallery']['path']]=dict(binding=j['gallery'],gallery_id=gallery['gallery_id'],backend_sha256=gallery['backend_sha256'],
                                               exact_profiles_metadata_vectors=gallery['profiles'],vector_bytes_read_in_this_proposal=0,
                                               evidence_scope='Same exact gallery JSON and vector/metadata hashes as the closed native manifest and future templates. No re-enrollment or vector recomputation.')
        entries.append(dict(scientific_job_id=jid,candidate=j['candidate'],case_id=j['scene_id'],asr_tap=j['asr_tap'],identity_tap=j['identity_tap'],
                            proposed_decision='ACCEPT_EXACT_PREFERRED_NATIVE_PREDICTION_CREDIT',decision_effective=False,
                            selected_repeat=1,declared_repeats=dec['all_predeclared_repeats'],all_repeats_retained=existing['all_repeats'],
                            original_manifest=peer['original_manifest'],actual_result=existing['result'],actual_full_source_audit=existing['full_source_audit'],
                            actual_completion=existing['completion'],actual_score=existing['score'],
                            closure_from_full176=pr,source_audio=j['audio'],predeclared_audio_pcm_sha256=j['audio_pcm_sha256'],
                            full_asr_frames=j['expected_frames'],full_identity_frames=j['expected_identity_frames'],profile=j['profile_binding'],gallery=j['gallery'],
                            settings=j['settings'],scientific_job_context_digest=canonical_digest({k:j[k] for k in JOBSCIENCE}),future_template_matches=templates,
                            equivalence='Exact source/PCM/frames are the fixed omitted cell; unchanged profile, gallery/vector declarations, model assets, scientific source, native helper, windows/hops/context, gain, source pacing and serial affinity support reuse of this already computed native prediction. This does not substitute timings from a new host run.'))
    need(len(entries)==68 and len({e['scientific_job_id'] for e in entries})==68,'Incomplete/duplicate credits')
    credited={(e['candidate'],e['case_id'],e['asr_tap']) for e in entries};new={(x['candidate'],x['case_id'],x['tap']) for x in matrix['rows']}
    need(len(new)==892 and not credited&new and len(credited|new)==960 and len({x[1] for x in credited|new})==240,'Coverage does not form exact960/240')
    report_outputs={Path(b['path']).name:b for b in report['outputs']};analysis=report_outputs['ANALYSIS.md'];retention=reader.get(report_outputs['RETENTION_CACHE_PROPOSAL.json'])
    result=dict(schema='s6d-native176-retention-and-native-cache-credit.v1',status='PROPOSED_ROOT_RECEIPT_NOT_APPROVED',
                run_id='20260913T195357Z',root_owner_thread_id='01a0812d-3ff0-7ed0-a06c-4df61b62a459',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                root_approval_created=False,root_acceptance=None,accepted_credits=0,proposed_accepted_credits=68,
                inputs=dict(**refs,analysis=analysis,future_matrix=peer['matrix'],original_native_manifest=peer['original_manifest'],future_native_manifests=peer['future_manifests'],accepted_scoring_spec=delivery['accepted_spec']),
                retention=dict(status='PROPOSED_FORMALIZATION_OF_ROOT_STATED_RESEARCH_RETENTION',
                               candidates=retention['candidate_dispositions'],default_promotion=False,
                               scope='C065 anonymous control and C088 limited named research candidate for full240 confirmation only. C105 diagnostic/adverse only. No universal latency, short-name recovery, GUI or CM5 success claim.'),
                scientific_equivalence=dict(status='SUPPORTED_BY_EXACT_EXISTING_METADATA_AND_FULL176_CLOSURE',
                                            source_root=old['source_root'],execution_files=old['execution_files'],native_helper=old['helper'],evidence_helper=old['evidence_helper'],model_asset_bindings=old['assets'],
                                            profiles=list(profiles.values()),galleries=list(galleries.values()),
                                            settings=peer['settings'],declared_pacing_allocation={k:old['limits'][k] for k in LIMITS},
                                            compared_job_fields=list(JOBSCIENCE),compared_global_fields=list(SCIENCE),
                                            retained_contract='Unchanged actual source PCM, already-applied gain, common origin, stream pair, full frames, native model/window/hop/context and source pacing; all68 already included in strict176 full-source/dispatch/journal/closed-owner validation.',
                                            wrappers='Existing scientifically unchanged V5/V3/80 supervision migration is bound by future manifests. Source/asset/prediction equivalence supports credit; wall-clock observations remain from the original serial176 environment, not a claim that future resource conditions are identical.'),
                full_source_acceptance=dict(validation=refs['validation'],status=validation['status'],original_completed=171,recovery_completed=5,
                                            owner_exit=validation['owner_exit'],preferred_ids_all_in_completion_validations=True,
                                            evidence_method='Reuse exact immutable full176 validation and its already verified result, completion, full PCM/journal/dispatch/source bindings. No audio, model assets, vectors or event journals scanned again.'),
                credits=entries,coverage=dict(fixed_credits=68,conditional_new_serial_jobs=892,disjoint=True,total=960,unique_cases=240,
                                             all_repaired_declared_records_retained=84,repeat_selection='Fixedr1; no favorable r2, C105, original-source or recovery5 substitution'),
                adverse_and_unavailable_preserved=dict(core_jobs=168,C105_diagnostic_jobs=8,all_pair_comparisons=176,all_raw_equivalent=True,
                                                      C088_correct=10,C088_eligible_enrolled=34,C088_never_correct=24,C088_stable=5,C088_unavailable=102,
                                                      incomplete_speech_cases=['S45_01_16','S45_03_19','S45_06_19','S45_10_10'],
                                                      C105_repaired_O0_r2_cp_errors=21,C105_reference_words=41,no_favorable_repeat_selection=True),
                future_execution_not_admitted=dict(queue_approval_created=False,NN_jobs_launched=0,hardware_actions=0,
                                                   required='Root must issue the actual receipt separately and bind it in exact future serial892 admission, with one native efficacy worker, all current C/Tk/HOST allocation gates, V5/V3/80 authorities, resource floors, full source/output gates and original72h deadline/45min reserve.'),
                current_context=dict(source='Root message; not a live query by this helper',C12='RUNNING',C12_reported_pid=634952,
                                     scorer_closed_before_C12_launch_sec=25.6,scorer_running=False,physical_recovery_remains_separate=True,
                                     historical_holds='Older analysis receipts preserve the context when written; this new context supersedes their C12-not-launched statement only.'),
                preservation='Original171 REPORT_BLOCKED is not FINISH; old stopped C105 is uncredited. All failed executions/capture charges and original source epochs remain immutable.',
                proposal_source=binding(__file__),proposal_readme=binding(Path(__file__).with_name('README_S6D_NATIVE68_ROOT_RECEIPT_PROPOSAL_V1.md')),
                work_performed=dict(metadata_files_read=len(reader.cache),audio_journal_vector_model_asset_reads=0,model_scorer_calls=0,process_device_queries=0,root_approval_or_new_queue_created=False))
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    print(json.dumps(binding(output)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args();main(args.output)
