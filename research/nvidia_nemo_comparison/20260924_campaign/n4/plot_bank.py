"""Small engineering-bank coverage figures, never model-quality plots. README.md."""
import argparse
from collections import Counter
from pathlib import Path
from common import load,bind,freeze


def main(args):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=load(args.strata)['scenes']
    args.output.mkdir(parents=True,exist_ok=False)
    labels=['complete_nonoverlap','complete_overlap','incomplete_ambient_reference','empty_control']
    counts=Counter(r['reference_class'] for r in rows)
    groups=sorted(Counter(r['dependency_cluster'] for r in rows).values(),reverse=True)
    fig,axes=plt.subplots(1,2,figsize=(10.4,4.2),layout='constrained')
    values=[counts[k] for k in labels]
    bars=axes[0].barh(['Non-overlap','Overlap','Incomplete ambient','Empty control'],values,color=['#246b86','#458f96','#c99b3d','#879096'])
    axes[0].bar_label(bars,padding=4);axes[0].invert_yaxis();axes[0].set_xlim(0,180)
    axes[0].set_xlabel('Scenes (each has both O0 and O1)')
    axes[0].set_title('Reference capability: 240 scenes')
    bars=axes[1].bar(range(1,len(groups)+1),groups,color='#246b86')
    axes[1].bar_label(bars,padding=3,fontsize=8)
    axes[1].set_xticks(range(1,len(groups)+1));axes[1].set_xlabel('Connected dependency group, sorted by size')
    axes[1].set_ylabel('Scenes');axes[1].set_ylim(0,max(groups)*1.18)
    axes[1].set_title('Shared voices / text / noise: 9 groups')
    fig.suptitle('N4 preparation — seen engineering bank, no N4 model results',fontsize=12)
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
    fig.savefig(args.output/'BANK_COVERAGE.png',dpi=150)
    fig.savefig(args.output/'BANK_COVERAGE.svg')
    plt.close(fig)
    freeze(args.output/'PLOT_RECEIPT.json',dict(status='GENERATED_FROM_AUDITED_METADATA',
        input=bind(args.strata),code=bind(__file__),scene_counts=dict(counts),dependency_group_sizes=groups,
        output=[bind(args.output/'BANK_COVERAGE.png'),bind(args.output/'BANK_COVERAGE.svg')],
        inference_results_plotted=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--strata',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
