"""Aggregate-only main comparison figure; README_MAIN_SCORE_PLOT_V1.md."""
import argparse
from pathlib import Path

from common import load, verify
from metric_process import pin


def run(acceptance, output):
    pin()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a=load(acceptance);verify(a['review']);verify(a['report']);r=load(a['report']['path'])
    review=load(a['review']['path'])
    if (a['status']!='ACCEPTED_REVIEWED_MAIN_MODELED_SCORING_ONLY' or review['reviewed']!=7680
            or review['required']!=7680 or review['report']!=a['report'] or r['required_cells']!=7680):raise ValueError('Accepted full main report required')
    c={(x['composition'],x['tap']):x['counts']['word_metrics'] for x in r['cohorts']}
    names=sorted({key[0] for key in c});assert len(names)==16 and len(c)==32
    if output.exists():raise ValueError('Use a fresh figure destination')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,(left,right)=plt.subplots(1,2,figsize=(12,7),gridspec_kw={'width_ratios':[1,1.5]})
    colors={'O0':'#26577c','O1':'#ce6c22'}
    for index,variant in enumerate(['A0','A1','A2','A3']):
        for tap,offset in [('O0',-.16),('O1',.16)]:
            values=[c[(n,tap)]['primary_wer'] for n in names if n.startswith(variant+'_')]
            assert all(v==values[0] for v in values)
            value=values[0];pct=100*value['errors']/value['words']
            left.barh(index+offset,pct,height=.28,color=colors[tap],label=tap if index==0 else None)
            left.text(pct+.25,index+offset,f'{pct:.2f}%',va='center',fontsize=9)
    left.set(yticks=range(4),yticklabels=['A0','A1','A2','A3'],xlim=(0,23),xlabel='Primary WER (%) — lower is better',title='Words on complete non-overlap references')
    left.invert_yaxis();left.legend(frameon=False,loc='lower right');left.grid(axis='x',alpha=.15);left.set_axisbelow(True)
    for index,name in enumerate(names):
        x,y=c[(name,'O0')]['cpwer'],c[(name,'O1')]['cpwer'];pct=100*(x['errors']+y['errors'])/(x['words']+y['words'])
        right.barh(index,pct,height=.68,color='#ce6c22' if '_D1_' in name else '#617c91')
        right.text(pct+.8,index,f'{pct:.1f}%',va='center',fontsize=9)
    right.set(yticks=range(16),yticklabels=names,xlim=(0,122),xlabel='Pooled cpWER (%) — lower is better',title='Speaker-assigned words, both taps pooled')
    right.invert_yaxis();right.grid(axis='x',alpha=.15);right.set_axisbelow(True)
    fig.suptitle('Accepted main modeled bank: word and speaker errors',fontsize=16,x=.08,ha='left',y=.98)
    fig.text(.08,.065,'Primary WER: 156 scenes per tap; 4,560 words per tap. cpWER: 203 scenes per tap; 12,032 pooled words.',fontsize=9)
    fig.text(.08,.04,'7,680 completed cases. 832 incomplete-reference cases remain target-only. GUI, naming visibility and hardware feasibility are unvalidated.',fontsize=9)
    fig.text(.08,.015,'Descriptive seen-bank results; no deployment winner promoted. Source: MAIN_MODELED_SCORING_ACCEPTANCE_V1.json.',fontsize=9,color='#444444')
    fig.subplots_adjust(left=.08,right=.98,top=.87,bottom=.16,wspace=.4)
    fig.savefig(output,dpi=160,facecolor='white',metadata={'Title':'Main modeled scoring comparison'});plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--acceptance',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.acceptance,a.output)
