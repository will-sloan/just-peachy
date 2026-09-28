"""Independent cumulative-cost conservation reader. README_COST_RUN_V1.md."""
import math


def validate_costs(result, persisted):
    def require(ok,message):
        if not ok:raise ValueError(message)
    ledger=result['telemetry']['component_costs']
    require(ledger['schema']=='component-call-costs.v1','Wrong cost schema')
    require(ledger==persisted['telemetry']['component_costs'],'Summary does not preserve completed counters')
    rows=ledger['rows'];n=result['expected_samples']
    require(set(rows)=={'model_setup','diarizer_setup','diarizer_push','diarizer_finish','embedding','asr_accept','asr_reset','asr_finish'},'Counter set differs')
    for key,row in rows.items():
        require(row['started']==row['completed'] and row['in_flight']==row['errors']==0,'Unfinished/failed calls: '+key)
        require(row['attempted_samples']==row['successful_samples'],'Dropped successful samples: '+key)
        require(all(math.isfinite(row[f]) and row[f]>=0 for f in ('wall_seconds','calling_thread_cpu_seconds')),'Invalid time')
    require(n>0 and result['source_samples']==result['asr_samples']==result['identity_samples']==n,'Input coverage differs')
    require(rows['asr_accept']['successful_samples']==rows['diarizer_push']['successful_samples']==n,'Call sample conservation failed')
    require(rows['asr_accept']['completed']==math.ceil(n/result['asr_quantum_samples']),'ASR input quantum differs')
    for key in ('model_setup','diarizer_setup','diarizer_finish','asr_finish'):
        require(rows[key]['completed']==1,'Wrong setup/finish count: '+key)
    require(rows['diarizer_push']['zero_output_calls']>0,'Empty-output native calls not exercised')
    require(rows['diarizer_push']['output_frames']+rows['diarizer_finish']['output_frames']==result['native_activity_frame_end'],'Native output frame conservation failed')
    require(rows['embedding']['completed']==result['telemetry']['n2_embedding_calls']>0,'Embedding calls differ')
    require(rows['embedding']['successful_samples']>=8000*rows['embedding']['completed'],'Embedding windows below minimum')
    seconds=n/16000
    def wall(*keys):return sum(rows[k]['wall_seconds'] for k in keys)
    times=dict(ASR=wall('asr_accept','asr_reset','asr_finish'),D1=wall('diarizer_push','diarizer_finish'),E0=wall('embedding'))
    return dict(status='COMPLETE_TARGETED_CALL_ACCOUNTING_WITH_PARITY_REQUIRED',source_seconds=seconds,
        call_wall_seconds=times,call_wall_RTF={k:v/seconds for k,v in times.items()},
        setup_wall_seconds=dict(combined_ASR_E0_and_stream=wall('model_setup'),D1_load_or_reset=wall('diarizer_setup')),
        calling_thread_cpu_seconds={key:row['calling_thread_cpu_seconds'] for key,row in rows.items()},
        counts=rows,session_elapsed_seconds=result['telemetry']['elapsed_wall_sec'],
        note='Call-boundary wall costs with original 1x pacing; concurrent totals are not session time. No full pipeline CPU/overhead or target speed claim.',
        all_audio_retained=True,complete_pipeline_cost=False,CM5_tested=False)
