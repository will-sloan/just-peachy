"""Two standalone scientific plots from final S6A profile totals. README_S6A_PROBE_FIGURES.md."""
from __future__ import annotations
import csv
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from s6a_common import *

ORDER=['P0X0','P0X1','P1X0','P1X1','SEG_X0','SEG_X1','EMBED_LONG','EMBED_CADENCE_QUALITY','ENDPOINT_X0','ENDPOINT_X1']
LABELS=['Original / cue off','Original / advisory','Joint / cue off','Joint / advisory',
        'Segmentation / off','Segmentation / energy','Long embedding','Cadence + RMS','Endpoint / off','Endpoint / advisory']

def main():
    source=REPORT/'COMPONENT_PROBE_SUMMARY.json';summary=read(source)
    assert summary['status']=='COMPLETE' and summary['complete']==720
    values={(r['profile_id'],r['stream']):r for r in summary['profiles']}
    assert len(values)==20 and all(r['complete_panel'] for r in values.values())
    folder=REPORT/'figures';folder.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    y=np.arange(10);width=.35;colors={'O0':'#0072B2','O1':'#D55E00'}
    fig,axes=plt.subplots(1,2,figsize=(13.5,6.5),sharey=True)
    for ax,key,title in zip(axes,['primary_wer','cpwer'],['Primary non-overlap WER (23 scenes/tap)','Final-label cpWER (29 complete-reference scenes/tap)']):
        for i,out in enumerate(('O0','O1')):
            data=np.asarray([values[(pid,out)][key]*100 for pid in ORDER])
            bars=ax.barh(y+(i-.5)*width,data,height=width,label=out,color=colors[out])
            ax.bar_label(bars,fmt='%.1f',padding=2,fontsize=8)
        ax.set_title(title);ax.set_xlabel('Pooled word errors / reference words (%)')
        ax.set_yticks(y,LABELS);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
        ax.set_xlim(0,ax.get_xlim()[1]*1.15)
    axes[0].invert_yaxis()
    fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.55,.935),ncol=2,frameon=False)
    fig.suptitle('S6A: 36-scene paired screening panel, 720 native runs',fontsize=14)
    fig.text(.02,.022,'O0 historical +3 dB once; O1 unity. Same scenes per profile. Incomplete ambient and empty controls excluded from these rates.\ncpWER uses actual final display labels; it is not DER or revision-corrected identity. No full-bank candidate winner is established.',fontsize=9)
    fig.tight_layout(rect=(0,.085,1,.94));p1=folder/'S6A_COMPONENT_ACCURACY.png';fig.savefig(p1,dpi=150);plt.close(fig)
    costs=[('asr_compute_s','ASR incl. EOF','#0072B2'),('segmentation_compute_s','Segmentation','#009E73'),
           ('embedding_compute_s','Embedding','#E69F00'),('punctuation_compute_s','Punctuation','#CC79A7')]
    fig,axes=plt.subplots(1,2,figsize=(13.5,6.5),sharey=True)
    for ax,out in zip(axes,('O0','O1')):
        left=np.zeros(10)
        for key,label,color in costs:
            data=np.asarray([values[(pid,out)][key] for pid in ORDER])
            ax.barh(y,data,left=left,label=label,color=color,height=.7);left+=data
        ax.set_title(out);ax.set_xlabel('Instrumented call elapsed sum (s) / 36 scenes')
        ax.set_yticks(y,LABELS);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
    axes[0].invert_yaxis()
    fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.55,.935),ncol=4,frameon=False,fontsize=9)
    fig.suptitle('Instrumented model-call elapsed sums across parallel lanes',fontsize=14)
    fig.text(.02,.022,'CPU only, concurrent study load. Excludes model loading, wrapper/postprocessing, tracker/gates, advisory/reset and process overhead.\nThese incomplete cost sums are neither wall time nor steady-state real-time factor, and cannot establish CM5 performance.',fontsize=9)
    fig.tight_layout(rect=(0,.085,1,.94));p2=folder/'S6A_COMPONENT_COMPUTE.png';fig.savefig(p2,dpi=150);plt.close(fig)
    keys=['profile_id','stream','primary_errors','primary_reference_words','primary_wer','cpwer_errors','cpwer_reference_words','cpwer',
          'asr_compute_s','segmentation_compute_s','embedding_compute_s','punctuation_compute_s','model_load_elapsed_s','model_wall_s']
    table=folder/'S6A_COMPONENT_PLOT_DATA.csv'
    with table.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        for pid in ORDER:
            for out in ('O0','O1'):writer.writerow({k:values[(pid,out)][k] for k in keys})
    save(folder/'PROBE_FIGURES_RECEIPT.json',{'status':'COMPLETE','source':bind(source),'code':bind(__file__),
         'outputs':[bind(p) for p in (p1,p2,table)],'utc':now(),'visual_qa':'Pending explicit image inspection by root'})
    print(str(p1));print(str(p2))

if __name__=='__main__':main()
