"""Check delivered S0 contracts and optionally every file in its compact ZIP."""
import argparse, hashlib, zipfile
from s0_common import *

def verify(report, archive=None):
    report=Path(report);c=read(report/'input_catalog.json');p=read(report/'resolved_pilot.json')
    b=read(report/'baseline_manifest.json');o=read(report/'user_context_overlay.v2.json');rows=c['recordings']
    checks={
        '127_unique_eligible':len(rows)==len({r['run_id'] for r in rows})==127,
        '52_disjoint_excluded':len(c['excluded_recordings'])==52 and not ({r['run_id'] for r in rows}&{r['run_id'] for r in c['excluded_recordings']}),
        'all_local_inputs_bound':all(r['local_file_binding_status']=='BOUND' and all(f['status']=='BOUND' for f in r['file_bindings']) for r in rows),
        'all_original_review_formal':all(r['original_status']=='REVIEW' and r['trial_label']=='KRK_FORMAL_RIR' for r in rows),
        'positive_distances_at_most_5m':all(0<r['distance_binding']['effective_m']<=5 for r in rows),
        'exact_two_distance_corrections':sum(r['distance_binding']['status']=='USER_CONFIRMED_BOUND' and r['distance_binding']['original_m']==100 and r['distance_binding']['effective_m']==1 for r in rows)==2,
        'central_angles_unchanged':all(r['speaker_angle_deg_original']==r['speaker_angle_deg_effective']==r['angle_label_interval']['center_original_deg'] for r in rows),
        'degree_uncertainty_uncalibrated':o['angle_uncertainty']['units']=='degrees' and o['angle_uncertainty']['conservative_half_width_deg']==5 and o['angle_uncertainty']['independently_calibrated'] is False,
        'all_wav_headers_match':all(r['local_wav_header']=={'channels':4,'sample_rate_hz':16000,'sample_width_bytes':3,'frames':350647} for r in rows),
        'no_rir_or_simulation_claim':all(not r['simulation_ready'] and not r['qualified_rir_available'] and not r['precise_angle_ground_truth_verified'] and r['rir_qualification']=='NOT_EXTRACTED' for r in rows),
        '12_exact_pilot_subset':len(p['recordings'])==len({r['run_id'] for r in p['recordings']})==12 and {r['run_id'] for r in p['recordings']}<={r['run_id'] for r in rows},
        'separate_clock_minus6db_preserved':all(r['playback']['same_clock_as_capture'] is False and r['playback']['requested_gain_db']==-6 for r in rows),
        'h2_offline_smoke_completed':b['smoke']['status']=='COMPLETED' and b['smoke']['exit_code']==0,
        'h2_eight_assets_validated':len(b['assets'])==8 and all(a['status']=='FRESH_RUNTIME_CHECKSUM_VALIDATED' for a in b['assets']),
        'h2_no_drops_complete_cursors':b['smoke']['session_summary']['telemetry']['audio_frames_dropped']==0 and all(b['smoke']['session_summary']['telemetry'][k]==b['smoke']['fixture_duration_sec'] for k in ['asr_cursor_sec','speaker_cursor_sec']),
    }
    if archive:
        with zipfile.ZipFile(archive) as z:
            sums=json.loads(z.read('FILE_LIST_AND_HASHES.json'))
            checks['zip_crc_ok']=z.testzip() is None
            checks['zip_all_listed_hashes_match']=all(hashlib.sha256(z.read(r['archive_path'])).hexdigest()==r['sha256'] for r in sums)
            checks['zip_exact_file_list']=set(z.namelist())=={r['archive_path'] for r in sums}|{'FILE_LIST_AND_HASHES.json','SHA256SUMS.txt'}
            checks['zip_no_audio_models_cache']=not any(Path(n).suffix.lower() in ['.wav','.flac','.onnx','.pt','.npy','.pcm16','.pyc'] or '/cache/' in n or '/smoke_data/' in n for n in z.namelist())
    return {'passed':all(checks.values()),'passed_checks':sum(checks.values()),'total_checks':len(checks),'checks':checks}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--zip');a=p.parse_args()
    result=verify(a.report,a.zip);print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 2)
