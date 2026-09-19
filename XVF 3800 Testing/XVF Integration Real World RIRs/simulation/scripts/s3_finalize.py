"""Compact S3 analysis-first handoff; raw captures remain local."""
import argparse,copy,difflib,hashlib,json,shutil,subprocess,zipfile
from datetime import datetime,timezone
from pathlib import Path
from s0_common import ROOT,SIM,REPO,HashCache,read,save,now

def run(report):
    report=Path(report);packet=report/'final_packet';packet.mkdir(exist_ok=False);cache=HashCache()
    analysis=read(report/'analysis_metrics.json');inputs=read(report/'inputs_manifest.json');h2=read(report/'h2_smoke.json');offline=read(report/'offline_transport_checks.json')
    owners={a:read(report/a/'hardware_summary.json') for a in ['hardware_initial','hardware_retry1']}
    restores={a:read(report/a/'restoration.json') for a in owners}
    assert len(analysis['cases'])==8 and analysis['total_payload_mismatches']==0
    assert all(c['transport_status']=='PASS' and c['telemetry_status']=='PASS' and c['preframing_all_zero'] and c['callback']['frame_counts_contiguous'] for c in analysis['cases'])
    assert all(r['status']=='PASS' and r['exact_recorded_configuration_match'] and r['packed_input_disabled'] and r['hardware_lease_released'] and r['audio_handles_closed'] and r['telemetry_process_closed'] for r in restores.values())
    assert h2['status']=='PASS' and h2['assets_stat_unchanged']
    assert analysis['repeat']['configuration_equal'] and analysis['repeat']['input_hash_equal']
    assert offline['checks_passed']==9 and len(inputs['offline_checks'])==8 and all(c['passed'] for c in inputs['offline_checks'])
    for b in [inputs['rir_manifest'],*[r['file'] for r in inputs['selected_rirs']]]:
        assert cache.bind(Path(b['path']),b['sha256'])['status']=='BOUND'
    assert shutil.disk_usage(report).free>=50*2**30
    words=len((report/'REPORT_SECTION.md').read_text().split());assert 500<=words<=900,words
    for name in ['START_HERE.md','S3_REPORT.md','REPORT_SECTION.md','NEXT_PHASE_INPUTS.md']:
        shutil.copy2(report/name,packet/name)
    shutil.copy2(report/'analysis/per_case_metrics.csv',packet/'per_case_metrics.csv')
    for p in (report/'analysis/figures').iterdir():shutil.copy2(p,packet/p.name)
    save(packet/'offline_checks.json',{'packing_checks':inputs['offline_checks'],'failure_detection_checks':offline})
    code=[]
    for p in sorted((SIM/'scripts').glob('s3_*.py')):code.append(cache.bind(p))
    code.append(cache.bind(SIM/'scripts/README_S3.md'))
    configurations={}
    for a in owners:
        for c in owners[a]['cases']:
            p=report/a/c['case_id']/'configuration.json';configurations[a+'/'+c['case_id']]={'binding':cache.bind(p),'settings':read(p)['settings']}
    old=(report/'hardware_initial/source/s3_hardware.py').read_text().splitlines(True)
    new=(report/'hardware_retry1/source/s3_hardware.py').read_text().splitlines(True)
    (packet/'INITIALIZATION_CHANGE.diff').write_text(''.join(difflib.unified_diff(old,new,fromfile='executed_initial/s3_hardware.py',tofile='executed_retry1/s3_hardware.py')),encoding='utf-8')
    restore_compact={}
    for a,r in restores.items():
        restore_compact[a]={'status':r['status'],'source':cache.bind(report/a/'restoration.json'),
            'initial_snapshot':cache.bind(report/a/'initial_state.json'),'exact_recorded_configuration_match':r['exact_recorded_configuration_match'],
            'readback_identity':r['readback']['identity'],'packed_input_disabled':r['packed_input_disabled'],'audio_handles_closed':r['audio_handles_closed'],
            'telemetry_process_closed':r['telemetry_process_closed'],'hardware_lease_released':r['hardware_lease_released'],'scope':r['scope']}
    save(packet/'restoration.json',restore_compact)
    measured=copy.deepcopy(analysis)
    for c in measured['cases']:
        c.pop('configuration');c['configuration_reference']=c['attempt']+'/'+c['case_id']
    telemetry={}
    for field in ['AEC_AZIMUTH_VALUES','AEC_SPENERGY_VALUES']:
        values=[c['telemetry'][field] for c in analysis['cases']]
        telemetry[field]={'reply_count':sum(v['count'] for v in values),'read_failures':sum(v['read_failures'] for v in values),
            'per_case_rate_range_hz':[min(v['mean_arrival_rate_hz'] for v in values),max(v['mean_arrival_rate_hz'] for v in values)],
            'max_gap_ms':max(v['interval_max_s'] for v in values)*1000,'identical_adjacent_arrays':sum(v['identical_adjacent_arrays'] for v in values),
            'adjacent_comparisons':sum(v['adjacent_comparisons'] for v in values),'aggregation':'Per-case rates/gaps; counts sum all eight attempts. Not independent DSP estimates.'}
    speech_denominator=sum(c['outputs']['O1']['whole_capture']['samples'] for c in analysis['cases'] if c['case_id']!='T1_tagged')
    captured_h2=[]
    for r in h2['results']:
        assert r['session_summary']['telemetry']['audio_frames_dropped']==0
        captured_h2.append({k:r[k] for k in ['stream','input','duration_s','status','exit_code','exception','elapsed_s','event_counts','final_transcript_payloads','error_events','initial_profile_files']})
        captured_h2[-1]['session_telemetry']=r['session_summary']['telemetry']
        captured_h2[-1]['runtime_validated_assets']=r['session_summary']['assets']
    capabilities={'offline_software':'PASS','physical_quantized_input_transport':'PASS','gain_delay_and_channel_order':'PASS','simultaneous_output_routes':'PASS',
       'processed_output_headroom':'LIMITED','single_seat_angle_plausibility':'LIMITED','direction_transition_behavior':'LIMITED','telemetry_continuity_and_freshness':'LIMITED',
       'optional_selected_azimuth_streaming':'NOT_TESTED','absolute_device_telemetry_alignment':'NOT_TESTED','same_retry_configuration_readback':'PASS','hidden_state_repeatability':'LIMITED',
       'unchanged_H2_mono_file_smoke':'PASS','restoration':'PASS','accuracy_winner_naming_motion_CM5':'NOT_TESTED'}
    elapsed=(datetime.now(timezone.utc)-datetime(2026,9,8,21,49,14,tzinfo=timezone.utc)).total_seconds()
    metrics={'schema_version':'1.0','metric_definition_version':'s3-v1','stage':'S3','run_id':report.name,'status':'READY_WITH_LIMITATIONS','created_utc':now(),
        'capabilities':capabilities,'population':{'physical_attempts':8,'original_cases':6,'retry_cases':2,'distinct_RIRs':3,'distinct_speaker_identities':2,'distinct_utterances':3,'speech_utterance_windows':15,'untouched_evaluation_cases':0},
        'transport':{'compared_mic_samples':analysis['total_compared_mic_samples'],'payload_mismatches':0,'all_nonzero_source_payload_retained':True,
            'denominator':'All four mic samples in each available common-offset overlap, including silence; eight captures of repeated fixtures, not independent corpus examples.',
            'rate_hz':48000,'carrier_channels':2,'container_bits':24,'payload_bits':23,'quantization_step_fs':2**-22,'microphone_rate_hz':16000,
            'tolerances':inputs['predeclared_transport_tolerances'],'proof_scope':'Only the three selected RIRs and recorded configuration; canonical library metadata is not modified.'},
        'outputs':{'speech_capture_count':7,'samples_per_output_in_speech_captures':speech_denominator,'rail_samples':analysis['speech_output_rail_samples'],
            'O1_rail_percent':100*analysis['speech_output_rail_samples']['O1']/speech_denominator,'O1_tagged_fixture_rail_samples':4366,
            'ASR_fixed_gain':1,'O0_mode':'ASR auto, category7/source3, ASROUTONOFF1','O1_mode':'postprocessed auto, category6/source3',
            'winner':None,'winner_null_reason':'Interoperability smoke and digital levels do not establish ASR or diarization accuracy.'},
        'telemetry':{'aggregate':telemetry,'raw_units':['radians','vendor_speech_energy_units'],'beam_order':['focused1','focused2','scanning','auto'],
            'native_linear_range_deg':[0,180],'optional_selected_probe':read(report/'preflight.json')['optional_selected_azimuth_probe'],
            'optional_selected_stream_rate_hz':None,'optional_null_reason':'Existing qualified queued adapter logs the two required AEC fields; optional availability was probed once, no selected/smoothed trajectory captured.'},
        'timing':{'absolute_device_latency_ms':None,'absolute_latency_null_reason':'ADC/DAC counters and QPC currentTime do not establish a calibrated common host epoch; callback availability only.',
            'device_telemetry_offset_ms':None,'offset_null_reason':'No device sample timestamp or atomic DSP/audio marker; no fitted telemetry shift used.',
            'sustained_handoff_latency_ms':None,'handoff_null_reason':'Only first energized coarse-sector receipt relative to source-write callback reported; brief transitions and unknown phonetic onset prevent sustained latency qualification.',
            'callback_availability_block_max_ms':150,'relative_processing_delay_method':'Absolute waveform correlation against recaptured MIC0, 0..250ms search; signed coefficients retained, no polarity change; 0.0625ms sample grid.'},
        'H2_smoke':{'status':h2['status'],'cases':captured_h2,'source_pair':'hardware_initial/T3_ABA_repeat1','scope':h2['scope'],
            'accuracy_qualification':False,'naming_qualification':False,'source_unchanged_vs_S0':all(b['status']=='BOUND' for b in h2['source_bindings'])},
        'source_level_policy':inputs['source_level_policy'],'detailed_measurements':measured,'restoration':{a:r['status'] for a,r in restores.items()},
        'resources':{'physical_playback_s':sum(v['physical_playback_s'] for v in owners.values()),'hardware_owner_elapsed_s':sum(v['elapsed_s'] for v in owners.values()),
            'H2_subprocess_elapsed_s':sum(r['elapsed_s'] for r in h2['results']),'end_to_end_elapsed_s_including_safety_wait':elapsed,
            'free_space_gib':{d:shutil.disk_usage(d+':/').free/2**30 for d in ['C','G']},'ram_peak_bytes':None,'ram_null_reason':'No peak RAM sampling during physical audio; no peak-memory claim.'},
        'unresolved_decisions':['Small bounded level/transition bank before broad campaign','Output headroom policy without choosing an accuracy winner','Stale/held/gapped telemetry policy','Usable audio/metadata timing contract'],
        'excluded_claims':['Output accuracy winner','Enrollment/naming validation','Moving-person validation','CM5 qualification','All-library replay validation']}
    save(packet/'metrics.json',metrics)
    git={}
    for key,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--short'])]:
        proc=subprocess.run(['git','-C',str(REPO),*args],capture_output=True,text=True);git[key]=proc.stdout.strip();assert proc.returncode==0
    manifest={'schema_version':'1.0','stage':'S3','run_id':report.name,'status':'READY_WITH_LIMITATIONS','created_utc':now(),
        'speaker_safety':read(report/'speaker_safety.json'),'inputs_manifest':cache.bind(report/'inputs_manifest.json'),'master_and_pack_bindings':read(report/'input_bindings.json')['workbook'],
        'canonical_RIR_manifest':inputs['rir_manifest'],'selected_RIRs':[{'role':r['role'],'run_id':r['run_id'],'file':r['file'],'time_origin':r['time_origin']} for r in inputs['selected_rirs']],
        'speech_fixtures':inputs['speech_fixtures'],'rights':inputs['rights'],'reserved_development_speakers':inputs['reserved_development_speaker_keys'],
        'case_configurations':configurations,'owner_summaries':{a:cache.bind(report/a/'hardware_summary.json') for a in owners},
        'retry_diagnosis':read(report/'retry_diagnosis.json'),'H2_smoke_binding':cache.bind(report/'h2_smoke.json'),'H2_unchanged_config':h2['config'],
        'H2_assets':h2['assets'],'H2_source_bindings':h2['source_bindings'],'H2_asset_verification':h2['asset_hash_validation'],
        'current_analysis_and_runner_code':code,'executed_code_snapshots':{a:read(report/a/'code_bindings.json') for a in owners},
        'git':git,'untouched_scope':['Canonical RIR outputs and manifest','H2 code/models/thresholds/GUI','Existing speaker profiles','Revision 6 Word workbook'],
        'model_setting_note':'User requested Astra Extra High; current-task selection was not changed or verified by available tools.',
        'figures':{'01_levels_and_relative_delay.png':'Plotted data: per_case_metrics.csv, all eight attempts.',
            '02_ABA_host_timeline.png':'Plotted data: 02_timeline_data.csv. Retry ABA1, full-rate returned telemetry; 20ms audio blocks with exact block peaks. Shading is host callback availability of expected RIR support.',
            '03_repeat_and_logging_gaps.png':'Plotted data: 03_repeat_and_gap_data.csv. Retry pair trajectories, all-attempt gap extrema; no fitted shifts.'}}
    save(packet/'run_manifest.json',manifest)
    omitted=[]
    for p in report.rglob('*'):
        if not p.is_file() or packet in p.parents or 'preflight_packet' in p.parts:continue
        role='local_raw_or_detailed_evidence'
        if p.suffix.lower() in ['.wav','.npy']:role='audio_or_numerical_vector_do_not_play_packed_carriers'
        elif 'transactions' in p.name:role='full_USB_request_response_trace'
        elif 'received_telemetry' in p.name:role='full_telemetry_with_host_bounds'
        omitted.append({**cache.bind(p),'role':role})
    for b in code:omitted.append({**b,'role':'current_code_or_README'})
    commands={'working_directory':str(ROOT),'analysis_powershell':"& 'C:\\Users\\amiri\\anaconda3\\python.exe' simulation\\scripts\\s3_analyze.py --report simulation\\reports\\S3\\20260908T214914Z --hardware simulation\\reports\\S3\\20260908T214914Z\\hardware_retry1",
        'command_prompt_note':'Use the same quoted executable/arguments without the initial PowerShell &. Full instructions are in simulation/scripts/README_S3.md.',
        'hardware_policy':'S3 complete, retry exhausted; no further physical playback. Existing run directories are refused. Future hardware work requires a new bounded phase/prompt.'}
    save(packet/'LOCAL_ARTIFACT_INDEX.json',{'schema_version':'1.0','artifacts':omitted,'commands':commands,
        'selected_sources_and_models':'Exact source/RIR/model paths, sizes where measured and validated hashes are in run_manifest.json; models were validated internally by unchanged H2 and not copied or redundantly rehashed.',
        'omission_policy':'No raw audio, full telemetry/transactions, model weights, vendor PDFs, private enrollment data or nested historical ZIPs in handoff.'})
    inventory=[{'path':p.name,'bytes':p.stat().st_size,'sha256':cache.bind(p)['sha256']} for p in sorted(packet.iterdir()) if p.is_file()]
    save(packet/'FILE_INVENTORY.json',{'files':inventory,'excludes':['FILE_INVENTORY.json','SHA256SUMS.txt'],'zip_hash_is_external':True})
    (packet/'SHA256SUMS.txt').write_text(''.join(cache.bind(p)['sha256']+'  '+p.name+'\n' for p in sorted(packet.iterdir()) if p.name!='SHA256SUMS.txt'),encoding='utf-8')
    archive=SIM/'handoffs'/f'S3_CHATGPT_HANDOFF_{report.name}.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(packet.iterdir()):z.write(p,p.name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None;assert len(z.namelist())<=20
        assert not any(Path(n).suffix.lower() in ['.wav','.npy','.docx','.pdf','.onnx','.zip'] for n in z.namelist())
        for line in z.read('SHA256SUMS.txt').decode().splitlines():
            digest,name=line.split('  ',1);assert hashlib.sha256(z.read(name)).hexdigest()==digest
        files=len(z.namelist())
    assert archive.stat().st_size<=15*2**20
    receipt={'status':'READY_WITH_LIMITATIONS','completed_utc':now(),'zip':cache.bind(archive),'files':files,'CRC_and_SHA256_validation':'PASS',
        'report_section_words':words,'physical_playback_s':metrics['resources']['physical_playback_s'],'hardware_owner_elapsed_s':metrics['resources']['hardware_owner_elapsed_s'],
        'end_to_end_elapsed_s_including_safety_wait':(datetime.now(timezone.utc)-datetime(2026,9,8,21,49,14,tzinfo=timezone.utc)).total_seconds(),
        'local_index_files':len(omitted),'indexed_local_bytes':sum(b['bytes'] for b in omitted),'restoration':{a:r['status'] for a,r in restores.items()},
        'free_space_gib':{d:shutil.disk_usage(d+':/').free/2**30 for d in ['C','G']}}
    save(report/'package_receipt.json',receipt);cache.flush();print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args();run(a.report)
