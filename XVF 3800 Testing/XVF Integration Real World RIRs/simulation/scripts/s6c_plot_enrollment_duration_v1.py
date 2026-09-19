"""Plot exact existing naming aggregates; see README_S6C_PLOT_ENROLLMENT_DURATION_V1.md."""
from __future__ import annotations
import argparse,csv,hashlib,io,json
from datetime import datetime,timezone
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
AUTH=REPORT/'full_n01_common_duration_names_v3/NAME_ANALYSIS_RECEIPT.json'
AUTH_SHA='1da2a2dd1c9f50a9aefb89a0e024de03975c629914ecb8aac673cf817366118b'
TABLE_SHA='496f81c7c9cb191a47e7cb456b3049afa522c7107cba3cabf52ede46c7e22318'
MAP={'A':{5:'C141',15:'C142',30:'C143'},'B':{5:'C144',15:'C145',30:'C146'}}
STATUSES={'ALL','ENROLLED','INTENDED_BUT_UNAVAILABLE','WITHHELD_OR_UNSELECTED','NO_GALLERY_CONTROL'}
def binding(p,raw=None):
    p=Path(p).resolve();raw=p.read_bytes() if raw is None else raw
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(p,sha):
    raw=Path(p).read_bytes();b=binding(p,raw);assert b['sha256']==sha;return raw,b
def save(p,value):
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    return binding(p)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    out=args.output.resolve();assert out.parent==REPORT/'figures' and not out.exists()
    raw,ab=read(AUTH,AUTH_SHA);authority=json.loads(raw)
    assert authority['status']=='COMPLETE_REQUESTED_NAME_INDEX'
    table=authority['tables'][6];assert Path(table['path']).name=='PROFILE_NAME_RESULTS.csv' and table['sha256']==TABLE_SHA
    raw,tb=read(table['path'],TABLE_SHA);assert tb==table
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    keyed={(r['profile_id'],r['stream'],r['roster_status']):r for r in rows}
    assert len(keyed)==len(rows)==60
    assert set(keyed)=={(p,s,z) for values in MAP.values() for p in values.values() for s in ('O0','O1') for z in STATUSES}
    data=[]
    for roster,mapping in MAP.items():
        denominators=set()
        for tier,profile in mapping.items():
            for stream in ('O0','O1'):
                groups={z:keyed[profile,stream,z] for z in STATUSES}
                integer_fields=('source_turns','sole_active_samples','correct_name_samples','wrong_known_name_samples','unknown_name_samples')
                values={z:{k:int(r[k]) for k in integer_fields} for z,r in groups.items()}
                assert all(r['identity_tap']==stream and int(r['scored_scenes'])==240 and int(r['unmapped_turns'])==0 for r in groups.values())
                for z,v in values.items():
                    assert min(v.values())>=0 and v['correct_name_samples']+v['wrong_known_name_samples']+v['unknown_name_samples']==v['sole_active_samples']
                for k in integer_fields:assert values['ALL'][k]==sum(v[k] for z,v in values.items() if z!='ALL')
                assert values['ALL']['source_turns']==777 and values['ALL']['sole_active_samples']==28612432
                assert all(values[z]['source_turns']==0 and values[z]['sole_active_samples']==0 for z in ('NO_GALLERY_CONTROL','INTENDED_BUT_UNAVAILABLE'))
                e,w=values['ENROLLED'],values['WITHHELD_OR_UNSELECTED']
                denominators.add((e['source_turns'],e['sole_active_samples'],w['source_turns'],w['sole_active_samples']))
                data.append(dict(roster=roster,tier_sec=tier,profile_id=profile,stream=stream,original_integer_counts=values,correctly_named_enrolled_speech_percent=100*e['correct_name_samples']/e['sole_active_samples'],withheld_wrong_known_source_seconds=w['wrong_known_name_samples']/16000))
        assert len(denominators)==1
    out.mkdir()
    db=save(out/'PLOT_DATA.json',dict(authority=ab,table=tb,sample_rate=16000,rows=data,conversion_scope='Existing integer source-support samples converted to percent of enrolled sole speech or seconds; no new scoring or aggregation across routes.'))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axs=plt.subplots(1,2,figsize=(12,6.9))
    colors={'A':'#1D658F','B':'#C76C25'}
    for roster in MAP:
        for stream in ('O0','O1'):
            chosen=[d for d in data if d['roster']==roster and d['stream']==stream]
            for ax,key in zip(axs,('correctly_named_enrolled_speech_percent','withheld_wrong_known_source_seconds')):
                ax.plot([d['tier_sec'] for d in chosen],[d[key] for d in chosen],color=colors[roster],ls='-' if stream=='O0' else '--',marker='o' if stream=='O0' else 's',lw=2,ms=6,label=f'Roster {roster} / {stream}')
    axs[0].set(title='Correct name on enrolled speech',ylabel='Enrolled sole speech assigned correctly (%)',ylim=(0,40))
    axs[1].set(title='Wrong known name on withheld speech',ylabel='Total source-supported exposure (seconds)',ylim=(0,9))
    for ax in axs:
        ax.set_xticks([5,15,30]);ax.set_xlabel('Target enrollment tier (usable seconds)')
        ax.grid(axis='y',color='#D9E0E5',lw=.7);ax.set_axisbelow(True);ax.margins(x=.10)
    fig.suptitle('More enrollment evidence improves coverage,\nwith uneven costs for withheld voices',fontsize=17,fontweight='bold',y=.97)
    handles,labels=axs[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.84),ncol=4,frameon=False,fontsize=10)
    fig.subplots_adjust(left=.085,right=.965,bottom=.26,top=.72,wspace=.27)
    fig.text(.085,.155,'Same eligible people within each roster across 5 / 15 / 30 s; all 240 scenes and all 777 probe occurrences retained.',fontsize=10)
    fig.text(.085,.118,'Enrolled sole speech: A = 553.88 s; B = 525.75 s. Withheld sole speech: A = 1,234.40 s; B = 1,262.53 s.',fontsize=10)
    fig.text(.085,.081,'C141–C146, clean-source templates, fixed gates. Source-support naming metrics; no wall-clock display or device-domain claim.',fontsize=9.5,color='#374957')
    for ext in ('png','svg'):fig.savefig(out/f'enrollment_duration.{ext}',dpi=160,facecolor='white')
    plt.close(fig)
    caption='Across the fixed eligible people in each roster, longer clean-source enrollment increased correctly named enrolled speech. Wrong-known exposure on withheld speech was not monotonic or uniform across the four roster/output combinations. The plot retains both outputs separately and uses the exact all-240 aggregate sample counts. Names are resolver assignments, not necessarily confirmed/stable names. Missing name assignments remain in the denominator. The three targets are estimated usable-speech tiers, not identical measured durations for every person. Whole-clip material, native evidence-window counts and resulting templates change alongside estimated duration, so this is not a duration-only intervention. Each frozen roster contains 14 people: 9 CMU ARCTIC and 5 HiFiTTS identities; the two disjoint rosters contain 28 people combined. Other probe voices remain in scoring as appropriate to the frozen rosters. This is exploratory source-to-XVF testing on shared scenes, not independent population validation, actual wall-clock name exposure or device-matched enrollment.'
    with (out/'CAPTION.md').open('x',encoding='utf-8') as f:f.write(caption+'\n')
    outputs=[db]+[binding(out/n) for n in ('enrollment_duration.png','enrollment_duration.svg','CAPTION.md')]
    receipt=dict(status='COMPLETE_EXACT_SOURCE_FIGURE_PENDING_VISUAL_REVIEW',created_utc=datetime.now(timezone.utc).isoformat(),authority=ab,table=tb,source=binding(__file__),readme=binding(HERE/'README_S6C_PLOT_ENROLLMENT_DURATION_V1.md'),matplotlib_version=matplotlib.__version__,outputs=outputs,series=4,points_per_series=3,panels=2,new_model_calls=0,new_scoring=False)
    print(json.dumps(save(out/'FIGURE_RECEIPT.json',receipt)))
if __name__=='__main__':main()
