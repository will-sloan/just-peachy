"""One compact scientific reference-tracking figure. See README_S6A_CUES.md."""
from __future__ import annotations
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from s6a_cues import read, save, binding, write_csv, DEFAULT_REPORT, now


LABELS = {
    'B0': 'B0 exact native',
    'R1_voice_time': 'R1 voice/time',
    'R2_angle_diagnostic': 'R2 angle association',
    'R3_sustained_angle': 'R3 sustained angle',
    'R4_decaying_memory': 'R4 decaying memory',
    'R5_reliability_adaptive': 'R5 reliability adaptive',
    'CONTROL_ONE_PERSON': 'One-person control',
    'CONTROL_ALL_UNKNOWN': 'All-unknown control',
}


def build(report=DEFAULT_REPORT):
    report=Path(report)
    source=report/'REFERENCE_PROFILE_RECEIPT.json'
    result=read(source)
    if result['status']!='COMPLETE' or result['outputs']!=3840:
        raise ValueError('The plot requires all 3840 reference/control outputs.')
    selected=[r for r in result['summary'] if r['population']=='ALL_COMPLETE_NONEMPTY']
    lookup={(r['profile'],r['stream']):r for r in selected}
    rows=[]
    for stream in ('O0','O1'):
        expected=lookup[('B0',stream)]['sole_active_samples']
        for profile in LABELS:
            row=lookup[(profile,stream)]
            if row['scenes']!=203 or row['alignment_unavailable'] or row['sole_active_samples']!=expected:
                raise ValueError('Incomplete population or mismatched denominator in plotted reference comparison.')
            if row['unknown_samples']+row['known_samples']!=expected:
                raise ValueError('Unknown and known support do not partition the denominator.')
            if not 0<=row['false_merge_samples']<=row['known_samples']:
                raise ValueError('Mixed-identity support must be a subset of known support.')
            rows.append(dict(profile=profile,label=LABELS[profile],stream=stream,
                             population=row['population'],scenes=row['scenes'],
                             source_turns=row['source_turns'],sole_active_samples=expected,
                             sole_active_sec=expected/16000,unknown_samples=row['unknown_samples'],
                             mixed_identity_samples=row['false_merge_samples'],
                             unknown_fraction=row['unknown_samples']/expected,
                             mixed_identity_fraction=row['false_merge_samples']/expected,
                             mixed_identity_definition='Known sole-speech support outside each predicted label dominant reference identity'))
    table=report/'CUE_REFERENCE_DIAGNOSTIC_PLOT_DATA.csv';write_csv(table,rows)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'axes.spines.left':False})
    fig,axes=plt.subplots(1,2,figsize=(12.4,6.8),sharex=True,sharey=True)
    for ax,stream in zip(axes,('O0','O1')):
        group=[r for r in rows if r['stream']==stream]
        unknown=[r['unknown_fraction']*100 for r in group]
        mixed=[r['mixed_identity_fraction']*100 for r in group]
        positions=list(range(len(group)))
        ax.barh(positions,unknown,color='#626f81',height=.62,label='Unknown / expired')
        ax.barh(positions,mixed,left=unknown,color='#d97832',height=.62,label='Mixed identity')
        for y,u,m in zip(positions,unknown,mixed):
            ax.text(min(u+m+1.2,99),y,f'{u:.1f}% / {m:.1f}%',va='center',
                    ha='right' if u+m>78 else 'left',fontsize=8.5,
                    bbox=dict(facecolor='white',edgecolor='none',alpha=.8,pad=.8))
        ax.set_title(f'{stream}  |  {group[0]["sole_active_sec"]:,.1f} s sole support',loc='left',pad=14,fontweight='bold')
        ax.set_xlim(0,101);ax.set_xticks([0,20,40,60,80,100])
        ax.set_xlabel('Fraction of the same sole-speech support (%)')
        ax.set_yticks(positions,labels=[r['label'] for r in group])
        ax.xaxis.grid(True,color='#dce1e5',linewidth=.7);ax.set_axisbelow(True)
        ax.tick_params(axis='y',length=0,pad=8)
    axes[0].invert_yaxis()
    fig.suptitle('Unknown and mixed-identity support across reference trackers',x=.04,y=.96,ha='left',fontsize=15,fontweight='bold')
    fig.text(.04,.907,'203 complete-reference nonempty scenes per tap; six fixed-ASR references plus two diagnostic controls.',ha='left',fontsize=10.2)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower left',bbox_to_anchor=(.035,.055),ncol=2,frameon=False)
    fig.text(.04,.035,'Mixed identity is support outside each predicted label’s dominant reference identity. Numbers show unknown / mixed identity.',fontsize=8.7)
    fig.text(.04,.011,'Approximate support, not DER. B0 uses source cursors; R1-R5 use modeled compute availability. Unfilled support does not prove correctness.',fontsize=8.7)
    fig.subplots_adjust(left=.205,right=.97,top=.835,bottom=.18,wspace=.18)
    image=report/'CUE_REFERENCE_DIAGNOSTIC.png';fig.savefig(image,dpi=180,facecolor='white');plt.close(fig)
    receipt=dict(status='COMPLETE',plot_count=1,rows=len(rows),population='ALL_COMPLETE_NONEMPTY',
                 scenes_per_tap=203,common_denominator='All estimated sole-speech source support, separately per output tap',
                 source=binding(source),table=binding(table),image=binding(image),code=binding(__file__),
                 matplotlib_version=matplotlib.__version__,created_utc=now())
    save(report/'CUE_PLOT_RECEIPT.json',receipt);return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=DEFAULT_REPORT)
    import json
    print(json.dumps(build(parser.parse_args().report),indent=2))
