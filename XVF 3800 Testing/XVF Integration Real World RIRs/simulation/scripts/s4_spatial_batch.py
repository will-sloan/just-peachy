"""Run the frozen spatial scorer over completed S4 cases. README_S4.md."""
import argparse
from s4_common import *
from s4_spatial_analysis import analyze_case, S4_SPATIAL_POLICY
from s4_capture_selection import accepted_cases

def run(batch):
    manifest=read(BANK/'SCENE_MANIFEST.json');scenes={s['case_id']:s for s in manifest['scenes']}
    folders=[r['folder'] for r in accepted_cases().values()] if batch=='final' else sorted(p.parent for p in (REPORT/'hardware'/batch).glob('S4_*/case_result.json'))
    results=[]
    assert read(REPORT/'SPATIAL_SCORING_POLICY.json')==S4_SPATIAL_POLICY
    with Progress('spatial_analysis_'+batch,len(folders)) as progress:
        for folder in folders:
            if read(folder/'case_result.json')['status']!='PASS':continue
            audio=read(folder/'audio_metrics.json') if (folder/'audio_metrics.json').exists() else None
            delays={s:r['relative_delay_median_samples'] for s,r in audio['streams'].items()} if audio else None
            result=analyze_case(folder,scenes[folder.name],manifest['selected_rirs'],delays)
            save(folder/'spatial_metrics.json',result);results.append(result);progress.case=folder.name;progress.done+=1
    save(REPORT/('spatial_analysis_'+batch+'.json'),{'batch':batch,'cases':results,'count':len(results),'scorer':bind(SIM/'scripts/s4_spatial_analysis.py')})
    print(json.dumps({'batch':batch,'analyzed':len(results)},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);a=p.parse_args();run(a.batch)
