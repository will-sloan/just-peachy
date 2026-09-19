"""Bind the supplied S1 update to immutable S0; no signal extraction or hardware."""
import argparse, copy, collections, hashlib, importlib.metadata, sys
from s0_common import *

S0=SIM/'reports/S0/20260908T181703Z'
EXPECTED={'input_catalog.json':'4f272903b86d02193b9934439cd77b0e478ce048a6a0c0d451048b3d581dced2',
 'resolved_pilot.json':'ecffdb9477704f394baf85e8ef8e49984ac90005bd32f25fdbc3f4f7fe1ac844',
 'user_context_overlay.v2.json':'b0e25bc18fc84a08d8f9a5fa7f071bfec51db1c4a3ab26cf68afc053e3b8b711'}
ADDED=['JPXVF_P1_R03_T01_D01_S01_F00_NAT_CU_R03','JPXVF_P1_R03_T01_D01_S01_F00_NAT_CU_R01']

def prepare(report,update_pack):
    report=Path(report);update_pack=Path(update_pack);cache=HashCache()
    parents=[cache.bind(S0/n,h) for n,h in EXPECTED.items()]
    if any(x['status']!='BOUND' for x in parents):raise ValueError('S0 parent hash mismatch')
    sums=parse_sums(update_pack/'SHA256SUMS.txt')
    pack_bindings=[cache.bind(safe_child(update_pack,n),h) for n,h in sums.items()]
    if any(x['status']!='BOUND' for x in pack_bindings):raise ValueError('S1 update pack hash mismatch')
    c=read(S0/'input_catalog.json');original=read(S0/'resolved_pilot.json')['recordings']
    supplied=read(update_pack/'S1_pilot_selection.v2.json');scope=read(update_pack/'scope_and_room_context.v3.json')
    if supplied['scope_overlay_sha256']!=next(x['sha256'] for x in pack_bindings if x['path'].endswith('scope_and_room_context.v3.json')):
        raise ValueError('Selection/room overlay hash mismatch')
    byid={r['run_id']:r for r in c['recordings']};active=[];removed=[]
    for r in c['recordings']:
        row=copy.deepcopy(r); included=row['room_table']!='Loeb Caf'
        row['active_campaign_included']=included;row['scope_exclusion_reason']=None if included else 'USER_EXCLUDES_EXACT_LOEB_CAF_CURRENT_CAMPAIGN_AND_NOISE'
        (active if included else removed).append(row)
    groups={(r['room_table'],r['recorder_position'],r['source_distance_m_effective'],r['speaker_angle_deg_effective']) for r in active}
    poses=collections.Counter('flat_obstructed' if r['obstructed'] else 'flat_unobstructed' if r['orientation']=='FLAT' else 'upright_unobstructed' for r in active)
    expected_ids=[r['run_id'] for r in original[:10]]+ADDED
    if [r['run_id'] for r in supplied['recordings']]!=expected_ids:raise ValueError('Supplied revised pilot order/identity mismatch')
    if not(len(active)==121 and len(removed)==6 and len(groups)==51 and dict(poses)==scope['selection']['active_pose_counts'] and set(scope['selection']['active_run_ids'])=={r['run_id'] for r in active}):
        raise ValueError('Active campaign scope counts mismatch')
    selected=[]
    with Progress(report,'S1_input_binding',12) as progress:
        for proposed in supplied['recordings']:
            row=copy.deepcopy(byid[proposed['run_id']])
            for k in ['canonical_audio_sha256','parent_manifest_sha256','recorded_utc','excitation_sha256','source_distance_m_effective','speaker_angle_deg_effective']:
                if row[k]!=proposed[k]:raise ValueError('Pilot identity mismatch '+row['run_id']+' '+k)
            if row['room_table']=='Loeb Caf':raise ValueError('Forbidden Loeb Caf pilot')
            row['s1_file_bindings']=[cache.bind(f['path'],f['sha256']) for f in row['file_bindings']]
            if any(f['status']!='BOUND' for f in row['s1_file_bindings']):raise ValueError('Selected input binding failure '+row['run_id'])
            row.update(active_campaign_included=True,scope_exclusion_reason=None,pilot_order=proposed['pilot_order'],selection_reason=proposed['selection_reason'])
            selected.append(row);progress.done+=1
    merged=read(S0/'user_context_overlay.v2.json');merged['schema_version']='jp_active_user_context_v3';merged['revision']='v3'
    merged['room_scope_update']=scope;merged['angle_uncertainty']=scope['angle_uncertainty']
    merged['provenance_S1']={'S0_parents':parents,'update_pack':pack_bindings,'applied_utc':now()}
    save(report/'scope_and_room_context.v3.json',merged);save(SIM/'config/scope_and_room_context.v3.json',merged)
    save(report/'active_campaign_manifest.json',{'schema_version':'jp_active_campaign_v3','original_audit_candidates':127,'original_audit_excluded_count':52,
      'active_count':121,'scope_excluded_count':6,'active_room_counts':dict(collections.Counter(r['room_table'] for r in active)),
      'metadata_geometry_groups':len(groups),'active_pose_counts':dict(poses),'recordings':active,'scope_excluded_recordings':removed,
      'original_audit_exclusions':c['excluded_recordings'],'only_selected_12_may_be_extracted':True})
    save(report/'selected_pilot_manifest.json',{'schema_version':'jp_s1_selected_pilot_v2','count':12,'recordings':selected,
      'source_selection_binding':next(x for x in pack_bindings if x['path'].endswith('S1_pilot_selection.v2.json'))})
    save(report/'selection_delta.json',{'kept_in_order':expected_ids[:10],'removed':[r['run_id'] for r in original[10:]],'added_in_order':ADDED,'reason':'Current exact-room scope change; no acoustic score based replacement'})
    save(report/'input_bindings.json',{'S0_parents':parents,'update_pack':pack_bindings,'fresh_unique_hashes':cache.fresh,'cached_receipts_used':cache.hits,'bytes_newly_hashed':cache.bytes})
    config={'schema_version':'jp_s1_extractor_config_v1','sample_rate_hz':16000,'channel_order':['MIC0','MIC1','MIC2','MIC3'],
      'source_sample_rate_hz':48000,'excitation_sha256':'cba5b09d4d3963d508340711210804d2dd80cf62741a60a2544120e60acbf488',
      'playback_gain_db':-6,'gain_convention':'h maps numerical post-software-gain drive to Category 3 recorded normalized full-scale samples; divide by archived excitation times 10**(-6/20) exactly once; retain mic gain 10 and all analog transfer',
      'capture_domain':'Category 3, gain 10, SYS_DELAY -32 originally included; common landmark anchor absorbs bulk unseparated latency, never a selective device-delay subtraction',
      'resample_source':{'method':'scipy.signal.resample_poly exact archived source 48k->16k','fir_taps':385,'cutoff_hz':7400,'window':['kaiser',8.6],'group_delay':'center compensated'},
      'clock_reference_warp':{'method':'common 64-tap normalized Kaiser-windowed sinc on excitation reference only; microphone vector is never individually warped','taps':64,'kaiser_beta':8.6},
      'sweep_source_start_sec':3.,'sweep_source_end_sec':13.,'marker_source_times_sec':[2.,16.,16.2],
      'sweep_start_hz':80.,'sweep_end_hz':7500.,'analysis_anchor_sec':0.1,'end_marker_guard_sec':0.08,
      'maximum_response_sec':2.8,'inverse':'reversed archived resampled sweep times exp(-t/L); normalize median zero-phase self-convolution transfer over 300..6000Hz',
      'calibration_band_hz':[300.,6000.],'candidate_band_edges_hz':[160.,6400.],'candidate_fir_taps':513,
      'marker_bands_hz':[[1000.,3000.],[2500.,4500.],[4000.,6000.]],'marker_regularization_relative':0.001,
      'clock_limit_ppm':500.,'clock_uncertainty_floor_ppm':5.,'clock_sweep_min_concentration_improvement_fraction':0.03,
      'noise_bands_hz':[[125,250],[250,500],[500,1000],[1000,2000],[2000,4000],[4000,6400]],
      'noise_window_before_marker_sec':[-1.5,-0.25],'noise_welch_nperseg':2048,'tail_block_sec':0.02,
      'tail_required_below_noise_sec':0.1,'tail_minimum_after_arrival_sec':0.08,'tail_maximum_after_arrival_sec':2.4,'tail_taper_sec':0.06,
      'common_pre_arrival_margin_sec':0.02,'crosscheck_fd_regularization_relative':0.0001,
      'crosscheck_pilot_orders':[1,12],'workers_max':4,'inner_threads':1,'task_ram_cap_gib':16,'min_available_ram_gib':16,
      'scratch_cap_gib':5,'free_disk_floor_gib':50,'handoff_cap_mib':50,'hardware_access':False,'simulation_ready':False}
    qc={'schema_version':'jp_s1_qc_policy_v1','created_utc':now(),'status':'DEVELOPMENT_INITIAL_BEFORE_REAL_PILOT_SCORING',
      'synthetic_acceptance':{'max_clock_error_ppm':8.,'max_pairwise_peak_delay_error_samples':0.35,'max_midband_gain_error_db':0.4,
                            'late_reflection_location_error_samples':1.,'repeat_regeneration_equal':True},
      'real_policy':{'no_claim_full_simulation_ready':True,'all_outputs_provisional_until_review':True,
        'band_support_min_sweep_to_pre_noise_db':10.,'marker_tail_above_noise_warning_db':6.,
        'timing_supported_requires_marker_zero_exclusion_and_sweep_sharpening':True,
        'timing_unresolved_is_retained_not_silently_fixed':True,'conservative_shared_tail_noise_multiplier':4.,
        'unknown_direct_path_not_strongest_peak':True,'no_exact_angle_or_distance_fit':True,
        'statuses':['PROVISIONAL_LIMITED_BAND_TAIL','PROVISIONAL_TIMING_REVIEW','HOLD_INPUT_OR_PROCESSING'],
        'allowed_uses':['extraction-method review','within-declared-band and tail diagnostic comparison'],
        'forbidden_uses':['production simulation','physical HIL before later authorization','claiming independent acoustic validation']},
      'policy_adjustments':[],'S2_requires_reviewed_frozen_policy':True}
    save(report/'extraction_config.json',config)
    if not (report/'qc_policy.initial.json').exists():save(report/'qc_policy.initial.json',qc)
    if not (report/'qc_policy.json').exists():save(report/'qc_policy.json',qc)
    save(report/'environment.json',{'python':sys.executable,'python_version':sys.version,'packages':{n:importlib.metadata.version(n) for n in ['numpy','scipy','soundfile','matplotlib','psutil']},'threads':{k:os.environ.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']}})
    context='\n\n## S1 active scope update — 2026-09-08\n\nS1 is authorized only for the revised 12-record pilot. Historical 127 eligible and 52 excluded remain. Active set: 121; six exact `Loeb Caf` records additionally excluded, including all noise/stress/training uses. `Upper Loeb` remains active. Preserve the two bound 1.00 m corrections and ±5 degree user-estimated angle half-width. Qualitative context is not a numeric room model.\n\n'
    context+='\n'.join('- '+r['room_table']+': '+r['description'] for r in scope['room_context'])
    context+='\n\nCurrent overlay: `config/scope_and_room_context.v3.json`. S0 and both supplied reference packs stay immutable. No hardware/H2 changes or automatic S2.\n'
    for name in ['CONTEXT.md','DECISIONS.md']:
        p=SIM/name
        if '## S1 active scope update' not in p.read_text(encoding='utf-8'):
            with p.open('a',encoding='utf-8') as f:f.write(context)
    cache.flush();print(json.dumps({'active':121,'scope_excluded':6,'audit_excluded':52,'pilot':12,'groups':51,'poses':dict(poses),'cached':cache.hits,'fresh':cache.fresh}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--update-pack',required=True);a=p.parse_args();prepare(a.report,a.update_pack)
