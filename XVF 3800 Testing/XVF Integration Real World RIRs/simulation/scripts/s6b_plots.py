"""Four compact scientific S6B result figures. See README_S6B_PLOTS.md."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from s6b_common import *


def make(analysis_subdir,profile_ids,output_subdir):
    source=REPORT/analysis_subdir;out=REPORT/output_subdir
    if out.exists():raise ValueError('Use a fresh figure version')
    receipt=read(source/'ANALYSIS_RECEIPT.json')
    if receipt['status']!='COMPLETE_REQUESTED_INDEX':raise ValueError('Require completed scoring')
    with (source/'PROFILE_RESULTS.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
    with (source/'SHORT_REPLY_RESULTS.csv').open(encoding='utf-8') as f:short=list(csv.DictReader(f))
    lookup={(r['profile_id'],r['stream'],r['population']):r for r in rows}
    sl={(r['profile_id'],r['stream']):r for r in short if r['population']=='ALL_COMPLETE_NONEMPTY' and r['duration_bin']=='<1s'}
    for pid in profile_ids:
        for tap in ('O0','O1'):
            for pop,count in [('PRIMARY_NONOVERLAP',156),('COMPLETE_OVERLAP',47),('INCOMPLETE_REFERENCE',26),('STRICT_EMPTY_REFERENCE',11)]:
                if int(lookup[pid,tap,pop]['scenes'])!=count:raise ValueError('Figure profile lacks full240: '+pid)
            if int(sl[pid,tap]['source_turns'])!=40:raise ValueError('Short denominator changed')
    out.mkdir(parents=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,
        'axes.titleweight':'bold','axes.grid':False,'savefig.facecolor':'white'})
    x=np.arange(len(profile_ids));blue='#2678a6';orange='#df8f30';red='#bb4b48';gray='#9ca8b0';green='#418f73'
    figures=[];captions=[]
    def finish(fig,name,caption):
        fig.savefig(out/(name+'.png'),dpi=170,bbox_inches='tight')
        fig.savefig(out/(name+'.svg'),bbox_inches='tight')
        plt.close(fig)
        figures.append(dict(name=name,png=bind(out/(name+'.png')),svg=bind(out/(name+'.svg')),caption=caption))
        captions.append('## '+name+'\n\n'+caption+'\n')
    fig,axes=plt.subplots(1,2,figsize=(12,4.2),layout='constrained')
    for ax,pop,field,title,denom in [(axes[0],'PRIMARY_NONOVERLAP','word_rate','Primary word errors','156 scenes; 4,560 reference words/tap'),
        (axes[1],'ALL_COMPLETE_NONEMPTY','cp_first_final_rate','First-final attributed-text errors','203 complete scenes; 6,016 reference words/tap')]:
        for i,tap in enumerate(('O0','O1')):
            vals=[100*float(lookup[p,tap,pop][field]) for p in profile_ids]
            ax.bar(x+(i-.5)*.36,vals,width=.34,color=blue if i==0 else orange,label=tap)
        ax.set_xticks(x,profile_ids);ax.set_ylabel('Error rate (%)');ax.set_title(title+'\n'+denom,fontsize=11)
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    axes[0].legend(frameon=False,ncol=2)
    finish(fig,'01_words_and_attribution','All plotted profiles have240 scenes on each tap. Left: pooled primary S+D+I /4,560. Right: first-final cpWER /6,016 complete-reference words, including overlap scenes. Lower cpWER alone does not establish better identity: inspect coverage/mixing and the separately tabulated first-display/latest views. B00 retains historical attribution timing; B36 is the common-scheduler original tracker.')
    fig,axes=plt.subplots(1,2,figsize=(12,4.2),sharey=True,layout='constrained')
    for ax,tap in zip(axes,('O0','O1')):
        unknown=[100*float(lookup[p,tap,'ALL_COMPLETE_NONEMPTY']['unknown_fraction']) for p in profile_ids]
        mixed=[100*float(lookup[p,tap,'ALL_COMPLETE_NONEMPTY']['mixed_fraction_all_sole']) for p in profile_ids]
        ax.bar(x,unknown,color=gray,label='Unknown support');ax.bar(x,mixed,bottom=unknown,color=red,label='Mixed identity support')
        ax.set_xticks(x,profile_ids);ax.set_ylim(0,100);ax.set_title(tap+' · same sole-speech denominator')
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    axes[0].set_ylabel('Fraction of sole-reference speech (%)');axes[0].legend(frameon=False,fontsize=9)
    finish(fig,'02_unknown_and_mixing','Unknown and mixed/conflated support use the same complete-reference sole-speech denominator; the two displayed fractions can be added. Mixed support is an offline anonymous-association diagnostic, not enrolled recognition or word-aligned DER. A coverage gain with more mixing is a tradeoff, not an unqualified improvement.')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),sharey=True,layout='constrained')
    for ax,tap in zip(axes,('O0','O1')):
        for i,(key,label,color) in enumerate([('contained_embedding_turns','Contained embedding',blue),('any_known_support_turns','Any label support',orange),('duration_mapped_correct_modal_turns','Correct mapped modal label',green)]):
            vals=[int(sl[p,tap][key]) for p in profile_ids]
            ax.bar(x+(i-1)*.25,vals,width=.23,color=color,label=label)
        ax.set_xticks(x,profile_ids);ax.set_ylim(0,44);ax.axhline(40,color='#444444',ls=':',lw=1)
        ax.set_title(tap+' · all 40 subsecond turns in 9 scenes');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    axes[0].set_ylabel('Source utterance occurrences');axes[0].legend(frameon=False,fontsize=8,loc='upper left',bbox_to_anchor=(0,-.14))
    finish(fig,'03_all_short_replies','All40 complete-reference subsecond source occurrences are retained. A wholly contained admitted waveform, any non-Unknown label support, and a duration-mapped correct modal label are different outcomes. Unknown, unmapped and tied assignments stay in the denominator; the dotted line is40, not40 independent scenes. Tables retain missing/never-successful latency counts.')
    fig,axes=plt.subplots(1,2,figsize=(12,4.2),sharey=True,layout='constrained')
    for ax,tap in zip(axes,('O0','O1')):
        base=np.zeros(len(x))
        for key,label,color in [('return_consistent','Consistent',green),('return_inconsistent','Inconsistent',red),('return_unknown','Unknown',gray)]:
            vals=np.asarray([int(lookup[p,tap,'ALL_COMPLETE_NONEMPTY'][key]) for p in profile_ids])
            ax.bar(x,vals,bottom=base,color=color,label=label);base+=vals
        ax.set_xticks(x,profile_ids);ax.set_title(tap+' · complete-reference return groups')
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    axes[0].set_ylabel('Repeated-source groups');axes[0].legend(frameon=False,ncol=3,fontsize=8,loc='upper left',bbox_to_anchor=(0,-.14))
    finish(fig,'04_return_consistency','Return-group consistency is evaluated separately from pooled cpWER. Consistent anonymous reuse, inconsistent labels and unresolved/Unknown groups are shown together; each profile uses the same complete-reference grouping. Lower Unknown with more inconsistent returns remains an observed harm. Silent-relocation and source/room strata are retained in the tables.')
    (out/'FIGURE_CAPTIONS.md').write_text('# S6B figure captions\n\n'+'\n'.join(captions),encoding='utf-8')
    result=dict(status='COMPLETE',profile_ids=profile_ids,figures=figures,source=bind(source/'PROFILE_RESULTS.csv'),short_source=bind(source/'SHORT_REPLY_RESULTS.csv'),analysis_receipt=bind(source/'ANALYSIS_RECEIPT.json'),code=bind(__file__))
    save(out/'FIGURE_MANIFEST.json',result)
    return dict(status='COMPLETE',figures=len(figures),out=str(out))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--analysis-subdir',required=True);p.add_argument('--profiles',nargs='+',required=True);p.add_argument('--output-subdir',default='figures_v1');a=p.parse_args()
    print(json.dumps(make(a.analysis_subdir,a.profiles,a.output_subdir),indent=2))
