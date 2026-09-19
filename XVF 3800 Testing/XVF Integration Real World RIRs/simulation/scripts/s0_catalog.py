"""Bind the explicit audited allowlist only. Does not decode or extract audio."""
import argparse, copy, math, time, wave, zipfile
from xml.etree import ElementTree as ET
from s0_common import *

NEEDED = ['request.json','result.json','00_admin/trial_metadata.json'] + [
    '02_raw/pass_01_amplified/'+n for n in [
        'microphones_4ch.wav','excitation_original.wav','signal_timing.json',
        'playback.json','capture_configuration.json','capture_gain_delay_lock.json',
        'identity.json','quality.json','result.json']]

def angle_interval(center, half_width=5):
    """Closed circular label interval represented in signed degrees; no label edit."""
    lo=(center-half_width+180)%360-180; hi=(center+half_width+180)%360-180
    return {'center_original_deg':center,'half_width_deg':half_width,
            'segments_deg':[[lo,180],[-180,hi]] if lo>hi else [[lo,hi]],
            'wraps':lo>hi}

def corrected_distance(row, request, result, manifest_binding, corrections):
    matches=[c for c in corrections if c['run_id']==row['run_id']]
    if len(matches)>1: raise ValueError('Duplicate correction binding')
    original=request['setup']['source']['distance_to_array_m']
    if original != row['source_distance_m_original']: raise ValueError('Original distance mismatch')
    if not matches:
        if row['source_distance_m_effective'] != original: raise ValueError('Unexplained effective distance')
        value=original; status='NO_CORRECTION'
    else:
        c=matches[0]
        if not (c['recorded_utc']==row['recorded_utc']==result['recorded_utc'] and
                c['parent_manifest_sha256']==row['parent_manifest_sha256']==manifest_binding.get('sha256') and
                manifest_binding['status']=='BOUND' and c['original_value']==original and
                c['effective_value']==row['source_distance_m_effective']):
            raise ValueError('Correction binding mismatch')
        # Assign the original overlay's effective value once; never scale an already corrected field.
        value=c['effective_value']; status='USER_CONFIRMED_BOUND'
    if not (isinstance(value,(int,float)) and math.isfinite(value) and 0<value<=5):
        raise ValueError('Effective distance outside (0,5] m')
    return {'original_m':original,'effective_m':value,'status':status,'correction':matches[0] if matches else None}

def run(report, workbook):
    report=Path(report); cache=HashCache(); started=time.monotonic()
    old_metrics=report/'catalogue_metrics.json'
    if old_metrics.exists():
        save(report/('catalogue_attempt_'+str(time.time_ns())+'.json'),read(old_metrics))
    source_names=['README_START_HERE.md','CONTEXT.md','SOURCE_REGISTER.json','phase_briefs/S0.md',
        'reference/audit/CHATGPT_SIMULATION_HANDOFF.md','reference/audit/audit_summary.json',
        'reference/audit/eligible_recordings.json','reference/audit/excluded_recordings.json',
        'reference/audit/metadata_corrections.json','planning/user_context_overlay.proposed.json',
        'COMPUTE_AND_MONITORING.md','templates/PHASE_HANDOFF_TEMPLATE.md',
        'templates/phase_result.schema.json','phase_briefs/S1.md','RIR_AND_NOISE_PROTOCOL.md',
        'planning/proposed_rir_pilot.json']
    sums=parse_sums(PACK/'SHA256SUMS.txt')
    sources=[cache.bind(PACK/n,sums.get(n)) for n in source_names]
    if any(x['status']!='BOUND' for x in sources): raise ValueError('Reference pack binding failure')
    sources.append(cache.bind(PACK/'SHA256SUMS.txt'))
    sources.append(cache.bind(workbook))
    sources.append(cache.bind(Path(r'C:\Users\amiri\.codex\attachments\9d8eac4e-a664-4bfc-bb71-7ccfc872db00\pasted-text.txt')))
    save(report/'source_bindings.json',sources)
    with zipfile.ZipFile(workbook) as z:
        tree=ET.fromstring(z.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs=[''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in tree.findall('.//w:p',ns)]
    (report/'workbook_V5_extracted.txt').write_text('\n'.join(paragraphs),encoding='utf-8')
    eligible=read(PACK/'reference/audit/eligible_recordings.json')['recordings']
    excluded=read(PACK/'reference/audit/excluded_recordings.json')['recordings']
    corrections=read(PACK/'reference/audit/metadata_corrections.json')['corrections']
    ids=[x['run_id'] for x in eligible]; exids=[x['run_id'] for x in excluded]
    if len(ids)!=127 or len(set(ids))!=127 or len(exids)!=52 or len(set(exids))!=52 or set(ids)&set(exids):
        raise ValueError('Allowlist/exclusion population does not reconcile')
    overlay=read(PACK/'planning/user_context_overlay.proposed.json')
    overlay['schema_version']='jp_user_context_v2'
    overlay['status']='ACTIVE_USER_CONTEXT_NOT_MEASURED_GEOMETRY'
    overlay['angle_uncertainty_superseded']=copy.deepcopy(overlay['angle_uncertainty'])
    overlay['angle_uncertainty']={'reported_text':'approximately ±4–5 degrees or less',
        'units':'degrees','conservative_half_width_deg':5,'authority':'user_clarification',
        'independently_calibrated':False,'precise_angle_ground_truth_verified':False,
        'scope':'All 127 manual source-angle labels; no explicitly smaller per-record uncertainty found',
        'not_equivalent_to':['measured XVF DoA accuracy','standard deviation','calibrated confidence interval','hard algorithm-error bound'],
        'native_radians_separate':True,'linear_array_front_rear_ambiguity_retained':True,
        'do_not_change_entered_angles':True,'supersedes_percent_denominator_question':True,
        'future_artificial_robustness_test_half_widths_deg':[10,20]}
    overlay['provenance']={'clarification':sources[-1],'base_overlay':next(x for x in sources if x['path'].endswith('user_context_overlay.proposed.json'))}
    save(report/'user_context_overlay.v2.json',overlay); save(SIM/'config/user_context_overlay.v2.json',overlay)
    save(report/'metadata_corrections.json',read(PACK/'reference/audit/metadata_corrections.json'))
    rows=[]; newer=[]
    with Progress(report,'catalogue',127) as progress:
        for row in eligible:
            out=copy.deepcopy(row); errors=[]; runroot=safe_child(ROOT,row['path'])
            out['absolute_run_path']=str(runroot); bindings=[]
            try:
                mb=cache.bind(runroot/'SHA256SUMS.txt',row['parent_manifest_sha256']); bindings.append(mb)
                if mb['status']!='BOUND': errors.append('PARENT_MANIFEST_'+mb['status']); manifest={}
                else: manifest=parse_sums(runroot/'SHA256SUMS.txt')
                for rel in NEEDED:
                    expected=manifest.get(rel)
                    b=cache.bind(safe_child(runroot,rel),expected)
                    b['role']=rel
                    if expected is None: b['status']='NO_SAVED_HASH'
                    bindings.append(b)
                    if b['status']!='BOUND':errors.append(rel+':'+b['status'])
                canonical=next(x for x in bindings if x.get('role','').endswith('microphones_4ch.wav'))
                excitation=next(x for x in bindings if x.get('role','').endswith('excitation_original.wav'))
                if canonical.get('sha256')!=row['canonical_audio_sha256']: errors.append('CANONICAL_ALLOWLIST_HASH_MISMATCH')
                if excitation.get('sha256')!=row['excitation_sha256']: errors.append('EXCITATION_ALLOWLIST_HASH_MISMATCH')
                request=read(runroot/'request.json'); result=read(runroot/'result.json')
                if row['original_status']!='REVIEW' or row['trial_label']!='KRK_FORMAL_RIR' or result['status']!='REVIEW' or request['setup']['trial_label']!='KRK_FORMAL_RIR':
                    errors.append('FORMAL_REVIEW_METADATA_MISMATCH')
                if result['recorded_utc']!=row['recorded_utc'] or result['run_id']!=row['run_id']: errors.append('RECORD_IDENTITY_MISMATCH')
                out['distance_binding']=corrected_distance(row,request,result,mb,corrections)
                if request['setup']['source']['azimuth_lab_deg']!=row['speaker_angle_deg_original'] or row['speaker_angle_deg_effective']!=row['speaker_angle_deg_original']:
                    errors.append('ANGLE_CENTER_MISMATCH')
                out['angle_label_interval']=angle_interval(row['speaker_angle_deg_original'])
                out['unmeasured_geometry']={k:request['setup'].get(k) for k in ['source','device','photo_references','coordinate_frame','imu']}
                with wave.open(canonical['path'],'rb') as w:
                    fmt={'channels':w.getnchannels(),'sample_rate_hz':w.getframerate(),'sample_width_bytes':w.getsampwidth(),'frames':w.getnframes()}
                out['local_wav_header']=fmt
                if fmt!={'channels':4,'sample_rate_hz':16000,'sample_width_bytes':3,'frames':350647}: errors.append('WAV_HEADER_MISMATCH')
                playback=read(runroot/'02_raw/pass_01_amplified/playback.json')
                out['playback']={k:playback.get(k) for k in ['route','same_clock_as_capture','completed','cancelled',
                    'drained','sample_rate_hz','channels','channel','requested_gain_db','source_frames','source_duration_s',
                    'callback_count','callback_status_limitation','timing_scope']}
                timing=read(runroot/'02_raw/pass_01_amplified/signal_timing.json')
                out['signal_timing']={'excitation_id':request['excitation_id'],'timing':timing['signals'][request['excitation_id']],
                    'full_reference':'See hash-bound signal_timing.json; alternate waveforms not selected'}
                # Inspect only derivative locations of allowlisted records, without hashing or decoding copies.
                for folder in ['03_derived','04_hil_exports','05_analysis']:
                    for f in (runroot/folder).rglob('*'):
                        if f.is_file() and f.relative_to(runroot).as_posix() not in manifest:
                            newer.append({'path':str(f),'bytes':f.stat().st_size,'qualification':'UNVERIFIED_NEWER_FILE'})
            except Exception as exc:
                errors.append(type(exc).__name__+': '+str(exc))
            out.update(file_bindings=bindings,local_file_binding_status='BOUND' if not errors else 'FAILED',
                       binding_errors=errors,rir_qualification='NOT_EXTRACTED',simulation_ready=False)
            rows.append(out); progress.done+=1;progress.detail=row['run_id'];cache.flush()
            if progress.done%25==0: print(f'Bound {progress.done}/127; elapsed {time.monotonic()-started:.1f}s',flush=True)
    proposed=read(PACK/'planning/proposed_rir_pilot.json'); byid={r['run_id']:r for r in rows}; pilot=[]
    for choice in proposed['recordings']:
        r=byid.get(choice['run_id'])
        if not r or r['canonical_audio_sha256']!=choice['canonical_audio_sha256'] or r['recorded_utc']!=choice['recorded_utc']:
            raise ValueError('Pilot is not an exact allowlist subset')
        pilot.append({**r,'proposal_reason':choice.get('proposal_reason'),'selection_role':choice.get('selection_role')})
    if len(pilot)!=12 or len({r['run_id'] for r in pilot})!=12: raise ValueError('Pilot count/duplicate failure')
    catalog={'schema_version':'jp_s0_catalog_v1','root':str(ROOT),'eligibility_authority':sources[6],
        'counts':{'eligible':len(rows),'excluded':len(excluded),'bound':sum(r['local_file_binding_status']=='BOUND' for r in rows)},
        'capture_audit_reused':'2026-09-08 audit: manifest/packed decode/continuity checks not repeated; header and needed files rebound here',
        'capture_domain':{'category':3,'microphone_gain':10,'system_delay_samples':-32,'acoustic_playback_clock':'separate Realtek'},
        'recordings':rows,'excluded_recordings':excluded,'newer_derivative_candidates':newer}
    save(report/'input_catalog.json',catalog)
    save(report/'resolved_pilot.json',{'schema_version':'jp_s0_resolved_pilot_v1','source_proposal':next(x for x in sources if x['path'].endswith('proposed_rir_pilot.json')),'count':12,'selection_unchanged':True,'recordings':pilot})
    save(report/'catalogue_metrics.json',{'elapsed_sec':time.monotonic()-started,'unique_files_hashed':cache.fresh,'cached_files_reused':cache.hits,'bytes_hashed':cache.bytes,'counts':catalog['counts'],'newer_derivative_candidates':len(newer)})
    cache.flush(); print(catalog['counts'])
    return 0 if catalog['counts']['bound']==127 else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--workbook',required=True)
    a=p.parse_args();raise SystemExit(run(a.report,a.workbook))
