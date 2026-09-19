"""Bound source-clock diagnostic figure. See README_S6C_PLOT_ARRIVAL_BOUNDARY_V1.md."""
from pathlib import Path
import argparse,hashlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

SOURCE_SHA='e9c17810b25452eb7d41df236424a11bbfde9b653062412526776cefefb96e56'
REVIEW_SHA='4d25412a0777e805b352d9271b3291390cb284800dad86bbe093cdf8da37b0a8'
SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
def exact(path,sha=None):
 p=Path(path).resolve();raw=p.read_bytes();b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 if sha is not None and b['sha256']!=sha:raise ValueError('Changed admitted figure source')
 return json.loads(raw),b
def save(path,value):
 with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def binding(path):
 p=Path(path).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def run(output):
 if output.exists():raise ValueError('Fresh figure output directory required')
 source,sb=exact(REPORT/'native_timing_diagnosis_v1/RESULT.json',SOURCE_SHA)
 review,rb=exact(REPORT/'independent_review/NATIVE_TIMING_ROOT_REVIEW_V1.json',REVIEW_SHA)
 if source['status']!='COMPLETE_BOUNDED_DIAGNOSIS' or source['key']!=['C105','O0','O0','S45_08_07'] or not source['vectors_byte_equal'] or source['discrete_choice_changes']:
  raise ValueError('Expected bounded timing diagnosis differs')
 rows=[]
 for clock in source['clocks']:
  asr=clock['asr:00000016']['available_at_sec']
  rows.append(dict(source=clock['source_label'],asr_available_sec=asr,
   short_available_sec=clock['embedding:00000015']['available_at_sec'],
   mature_available_sec=clock['embedding:00000016']['available_at_sec'],
   short_relative_ms=1000*(clock['embedding:00000015']['available_at_sec']-asr),
   mature_relative_ms=1000*(clock['embedding:00000016']['available_at_sec']-asr),
   final_label=clock['first_final']['speaker'],revision_age_sec=clock['mature_age_since_first_display_sec'],
   revision_horizon_sec=clock['revision_horizon_sec'],final_evidence_age_sec=clock['final_age_since_mature_source_end_sec'],
   evidence_expiry_sec=clock['evidence_expiry_sec']))
 assert [r['source'] for r in rows]==['cached_source_C065','native_source_C105']
 assert abs(rows[0]['mature_relative_ms']+24.1741)<1e-6 and abs(rows[1]['mature_relative_ms']-1.1398)<1e-6
 assert [r['final_label'] for r in rows]==['Speaker_2','Speaker_4']
 output.mkdir(parents=True)
 save(output/'PLOT_DATA.json',dict(source=sb,independent_source_review=rb,rows=rows,
  scope='Each row is centered on its own ASR observation 16 modeled availability. No common UTC alignment or GUI/hardware latency is implied. One selected counterexample, not a population result.'))
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.edgecolor':'#8894a6','axes.labelcolor':'#243148','text.color':'#18243a','xtick.color':'#41516a','ytick.color':'#41516a','svg.fonttype':'none'})
 fig,ax=plt.subplots(figsize=(12,6.8),dpi=160)
 fig.subplots_adjust(left=.27,right=.94,top=.74,bottom=.33)
 ax.set_xlim(-70,12);ax.set_ylim(-.6,1.5)
 ax.axvspan(0,12,color='#fbe8e5',zorder=0)
 ax.axvline(0,color='#7564b3',linestyle='--',linewidth=1.4,zorder=1)
 colors={'short':'#778599','mature':'#087f72','asr':'#7656b5'}
 labels=['C105 policy using\ncached C065 evidence','Fresh C105 native\nrun']
 for y,row,label in zip([1,0],rows,labels):
  ax.hlines(y,-68,10,color='#d7dfe8',linewidth=1,zorder=1)
  ax.scatter(row['short_relative_ms'],y,c=colors['short'],s=65,marker='o',zorder=3)
  ax.scatter(row['mature_relative_ms'],y,c=colors['mature'],s=85,marker='D',zorder=4)
  ax.scatter(0,y,c=colors['asr'],s=210,marker='|',linewidths=3,zorder=5)
  before=row['mature_relative_ms']<0
  label_text=('Mature first: 24.1741 ms earlier' if before else 'ASR first: mature evidence 1.1398 ms later')
  x=-39 if before else -34
  ax.annotate(label_text,xy=(row['mature_relative_ms'],y),xytext=(x,y+.35),
   fontsize=11,fontweight='bold',arrowprops=dict(arrowstyle='-',color=colors['mature'],linewidth=1),color=colors['mature'])
  ax.text(-68,y-.24,'Retained final label: '+row['final_label'],fontsize=10,color='#344760')
 ax.set_yticks([1,0],labels);ax.tick_params(axis='y',length=0,pad=14)
 ax.set_xticks([-60,-40,-20,0,10]);ax.set_xlabel('Modeled availability relative to that run’s ASR observation 16 (ms)',labelpad=11)
 ax.spines[['top','right','left']].set_visible(False)
 fig.text(.06,.94,'A small ordering change can persist in the transcript',fontsize=19,fontweight='bold')
 fig.text(.06,.889,'C105 · O0 ASR / O0 identity · S45_08_07 · selected native/cache counterexample',fontsize=11,color='#526178')
 handles=[Line2D([],[],marker='o',linestyle='',color=colors['short'],label='Short evidence'),
  Line2D([],[],marker='D',linestyle='',color=colors['mature'],label='Mature evidence'),
  Line2D([],[],marker='|',markersize=13,linestyle='',color=colors['asr'],label='ASR observation 16')]
 fig.legend(handles=handles,loc='upper left',bbox_to_anchor=(.26,.85),frameon=False,ncol=3,fontsize=10)
 fig.text(.06,.20,'Why the fresh run kept Speaker_4',fontsize=12,fontweight='bold')
 fig.text(.06,.153,'Mature evidence arrived4.7997 s after the row’s first display, beyond the2.0 s revision horizon.'.replace('arrived4','arrived 4').replace('the2','the 2'),fontsize=10)
 fig.text(.06,.114,'At finalization, evidence age was1.4302 s, beyond the0.75 s freshness rule; the prior label was retained.'.replace('was1','was 1').replace('the0','the 0'),fontsize=10)
 fig.text(.06,.055,'Exact vectors and 39 discrete tracker/name choices match. Measured execution costs differ.\nThis figure shows modeled source availability, not actual GUI, phonetic or hardware latency.'.replace('and 39','and 39'),fontsize=9,color='#526178')
 outputs=[]
 for suffix in ('png','svg'):
  p=output/('ARRIVAL_BOUNDARY.'+suffix);fig.savefig(p,facecolor='white');outputs.append(binding(p))
 plt.close(fig)
 caption='One selected C105/O0 native-cache pair has matching exact embedding vectors and 39 listed discrete tracker/name choices, yet measured-cost availability puts mature evidence 24.1741 ms before ASR16 in the cached source and 1.1398 ms after it in the fresh native source. Current revision and freshness rules retain different final anonymous labels. Each row is centered on its own modeled ASR availability; this is not actual display, phonetic or hardware latency. The machine-level cause of the measured duration differences is not established.'
 (output/'CAPTION.md').write_text(caption+'\n',encoding='utf-8')
 receipt=dict(status='COMPLETE_BOUND_DIAGNOSTIC_FIGURE',source=sb,independent_source_review=rb,
  helper=binding(__file__),readme=binding(Path(__file__).with_name('README_S6C_PLOT_ARRIVAL_BOUNDARY_V1.md')),
  matplotlib_version=matplotlib.__version__,plot_data=binding(output/'PLOT_DATA.json'),figures=outputs,caption=binding(output/'CAPTION.md'),
  new_models=0,new_policy_replays=0,actual_paced_cells=0,visual_review='PENDING_ROOT_RENDER_INSPECTION')
 save(output/'FIGURE_RECEIPT.json',receipt);print(json.dumps(binding(output/'FIGURE_RECEIPT.json')))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)

