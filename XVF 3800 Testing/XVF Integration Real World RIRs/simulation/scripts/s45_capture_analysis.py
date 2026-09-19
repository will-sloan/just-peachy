"""Accepted capture analysis with a hard reserve task-score gate. README_S45_ANALYSIS.md."""
import argparse, numpy as np, soundfile as sf
from s45_common import *
from s4_h2_analysis import rail_metrics, audit_converter
from s4_audio_analysis import analyze_case as development_audio
from s4_spatial_analysis import analyze_case as development_spatial, S4_SPATIAL_POLICY

def run(development_spatial_enabled=True,reference=False):
    manifest=read(BANK/('REFERENCE_SCENE_MANIFEST.json' if reference else 'SCENE_MANIFEST.json'));scenes={s['case_id']:s for s in manifest['scenes']}
    selection_path=REPORT/('REFERENCE_CAPTURES.json' if reference else 'ACCEPTED_CAPTURES.json')
    selected=read(selection_path);results=[]
    code=bind(Path(__file__))
    assert read(REPORT/'SPATIAL_SCORING_POLICY.json')==S4_SPATIAL_POLICY
    with Progress('reference_capture_analysis' if reference else 'capture_analysis',selected['accepted_count']) as progress:
        for item in selected['accepted']:
            folder=Path(item['folder']);scene=scenes[item['case_id']];receipt=read(folder/'case_result.json')
            bind(item['case_result']['path'],item['case_result']['sha256']);assert receipt['status']=='PASS'
            out=folder/'s45_analysis_receipt.json'
            if out.exists():
                old=read(out);assert old['case_result']['sha256']==item['case_result']['sha256'] and old['analysis_code']['sha256']==code['sha256'],'Analysis cache code/input mismatch; preserve prior receipt'
                results.append(old);progress.done+=1;continue
            if scene['split']=='reserve' or reference:
                # Read only output level/conversion/transport/telemetry health.
                # No truth-matched delay, direction, transcription or identity score.
                x,fs=sf.read(folder/'decoded_six.wav',dtype='int32',always_2d=True);x>>=8;assert fs==16000
                audio={'case_id':scene['case_id'],'split':scene['split'],'streams':{name:rail_metrics(x[:,ch]) for name,ch in [('O0',4),('O1',5)]},'converter':audit_converter(folder),'task_scoring':'PROHIBITED_REFERENCE' if reference else 'PROHIBITED_RESERVE','output_alignment':None}
                save(folder/'audio_metrics.json',audio);spatial_binding=None
            else:
                audio=development_audio(folder,scene)
                if development_spatial_enabled:
                    delays={s:r['relative_delay_median_samples'] for s,r in audio['streams'].items()}
                    spatial=development_spatial(folder,scene,manifest['selected_rirs'],delays)
                    save(folder/'spatial_metrics.json',spatial);spatial_binding=bind(folder/'spatial_metrics.json')
                else:spatial_binding=None
            row={'case_id':scene['case_id'],'split':scene['split'],'case_result':item['case_result'],'audio_metrics':bind(folder/'audio_metrics.json'),'spatial_metrics':spatial_binding,'analysis_code':code,'excluded_from_240':reference,'task_scoring_allowed':False if reference else scene['split']=='development','reserve_task_scored':False,'task_use_by_output':{name:('QUARANTINED_GROSS_SATURATION' if metrics['maximum_contiguous_rail_run_samples']>=1600 or metrics['rail_samples']/max(1,metrics['sample_count'])>=.01 else 'LIMITED_RESIDUAL_RAILS' if metrics['rail_samples'] else 'LEVEL_GATE_NO_RAILS') for name,metrics in audio['streams'].items()}}
            save(out,row);results.append(row);progress.done+=1;progress.case=scene['case_id']
    save(REPORT/('REFERENCE_CAPTURE_ANALYSIS.json' if reference else 'CAPTURE_ANALYSIS.json'),{'count':len(results),'cases':results,'reserve_task_scored':False,'selected_manifest':bind(selection_path),'excluded_from_240':reference})
    print(json.dumps({'analyzed':len(results),'reserve_task_scored':False}))

if __name__=='__main__':
    run()
    if (REPORT/'REFERENCE_CAPTURES.json').exists():run(reference=True)
