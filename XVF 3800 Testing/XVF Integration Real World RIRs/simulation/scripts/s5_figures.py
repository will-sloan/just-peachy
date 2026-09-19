"""Four final-only S5 scientific figures and exact plotted CSV. README_S5_FIGURES.md."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S5/20260909T130308Z'
PREVIEW=SIM/'staging/s5_figures_preview'
COLORS={'O0':'#2166AC','O1':'#C66B18'}
OUTS=('O0','O1')
FAMILY_SHORT={'F01':'Isolated / level','F02':'Sequential returns','F03':'Short replies','F04':'Overlap',
              'F05':'Folded spatial contrast','F06':'Silent relocation / pause','F07':'Flat / upright',
              'F08':'Clear / obstructed','F09':'Near / distant talker','F10':'Localized noise',
              'F11':'Multipoint ambience','F12':'Controls / speech + noise'}
ROOM_SHORT={'Arise 5th floor low table':'Arise 5th-floor low table','Arise Floor 2 Kitchen':'Arise floor 2 kitchen',
            'Arise Kitchen Main Table':'Arise kitchen main table','Library Conference Room':'Library conference room'}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def binding(path):
    path=Path(path);return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8');temp.replace(path)


def require_final(summary,paired):
    if summary.get('status')!='COMPLETE_PANEL':raise ValueError('Final figures refuse partial/integration summaries')
    if (summary.get('requested_scenes'),summary.get('requested_outputs'),summary.get('analyzed_outputs'))!=(180,360,360):
        raise ValueError('Final figure panel must contain180 scenes and360 analyzed outputs')
    reliability=summary['reliability']
    if reliability.get('complete')!=360 or reliability.get('reserve_task_evaluations')!=0:raise ValueError('Completion/reserve proof incomplete')
    if paired.get('scope')!='development' or len(paired.get('rows',[]))!=180:raise ValueError('Paired figure population is not180 development scenes')
    ids=[r['case_id'] for r in paired['rows']]
    if len(set(ids))!=180 or any(not r.get('O0') or not r.get('O1') for r in paired['rows']):raise ValueError('Missing/duplicate paired scene')
    if summary['populations']!={'primary_nonoverlap':117,'overlap_complete':36,'ambient_incomplete':19,'strict_empty':8}:
        raise ValueError('Unexpected primary/overlap/ambient/control populations')
    if dict(collections.Counter(r['population'] for r in paired['rows']))!=summary['populations']:
        raise ValueError('Paired rows do not reconcile to declared metric populations')


def load_final():
    # Reject partial status before opening any per-scene performance aggregate.
    summary=read(REPORT/'SUMMARY_METRICS.json')
    if summary.get('status')!='COMPLETE_PANEL':raise ValueError('Wait for root final COMPLETE_PANEL; partial results cannot render here')
    paired=read(REPORT/'PAIRED_METRICS.json');require_final(summary,paired)
    run=read(REPORT/'run_manifest.json');jobs=read(REPORT/'JOB_MANIFEST.json')
    if binding(REPORT/'JOB_MANIFEST.json')['sha256']!=run['jobs']['sha256']:raise ValueError('Frozen job manifest changed')
    from s5_common import manifest,DevelopmentGuard
    bank=manifest();guard=DevelopmentGuard(bank['scenes'],'figures')
    if set(jobs['development_ids'])!={r['case_id'] for r in paired['rows']}:raise ValueError('Plot rows differ from exact development allowlist')
    for row in paired['rows']:guard.require(row['case_id'],'plot_existing_development_aggregate')
    if binding(REPORT/'SCORING_PROTOCOL.json')['sha256']!=summary['scoring_protocol']['sha256']:raise ValueError('Summary protocol changed')
    with (REPORT/'SHORT_TURN_SUMMARY.csv').open(encoding='utf-8',newline='') as f:
        short=list(csv.DictReader(f))
    numeric={'turn_instances','source_clips','speakers','observed_turns','positive_supported_flags','no_positive_on_observed_support',
             'fully_observed_misses','timing_or_attribution_unknown','turns_without_contained_embedding','support_samples','observed_samples','speech_flag_samples'}
    for row in short:
        for key in numeric:row[key]=int(row[key])
    rep_path=REPORT/'representation/SUMMARY_COMPACT.json'
    representation=read(rep_path) if rep_path.exists() else None
    if representation and (representation.get('reserve_task_accesses')!=0 or not representation.get('status','').startswith('COMPLETE')):
        raise ValueError('Representation summary is not completed protected-development evidence')
    inputs=[binding(REPORT/name) for name in ['SUMMARY_METRICS.json','PAIRED_METRICS.json','SHORT_TURN_SUMMARY.csv','SCORING_PROTOCOL.json','JOB_MANIFEST.json']]
    if representation:inputs.append(binding(rep_path))
    return {'summary':summary,'paired':paired['rows'],'short':short,'representation':representation,'inputs':inputs,'access':guard.flush()}


def short_label(text):
    replacements={'self_reported_60plus_real_recording':'CV self-reported 60+', 'studio_project_design':'CMU studio/design',
                  'CMU ARCTIC':'CMU ARCTIC','Common Voice':'Common Voice','clean':'HiFi clean','other':'HiFi other'}
    if text in replacements:return replacements[text]
    if text.startswith('MIXED: '):
        return 'MIXED: '+' + '.join(replacements.get(t,t) for t in text[7:].split(' + '))
    return text


class Figures:
    def __init__(self,data,dest,preview=False):
        self.data=data;self.dest=Path(dest);self.dest.mkdir(parents=True,exist_ok=True)
        self.preview=preview;self.records=[];self.files=[];self.captions=[];self.layout_warnings=[]
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11,'axes.labelsize':10,
             'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9,'figure.dpi':150,'savefig.dpi':150,
             'axes.spines.top':False,'axes.spines.right':False,'axes.grid':False})

    def add(self,figure,panel,group,output,metric,value,**extra):
        self.records.append({'figure':figure,'panel':panel,'group':group,'output':output,'metric':metric,'value':value,**extra})

    def finish(self,fig,name,title,caption):
        if self.preview:title='SYNTHETIC FIXTURE — '+title
        fig.suptitle(title,x=.025,ha='left',fontsize=15,fontweight='bold',y=.98)
        wrapped='\n'.join(textwrap.wrap(caption,width=160 if fig.get_figwidth()>14 else 135))
        fig.text(.025,.015,wrapped,ha='left',va='bottom',fontsize=9,color='#333333')
        fig.canvas.draw();renderer=fig.canvas.get_renderer();width,height=fig.canvas.get_width_height()
        for artist in fig.findobj(matplotlib.text.Text):
            if not artist.get_visible() or not artist.get_text():continue
            box=artist.get_window_extent(renderer)
            if box.width and box.height and (box.x0 < -2 or box.y0 < -2 or box.x1 > width+2 or box.y1 > height+2):
                self.layout_warnings.append({'figure':name,'text':artist.get_text(),'bounds_px':[box.x0,box.y0,box.x1,box.y1]})
        fig.savefig(self.dest/name,dpi=150,facecolor='white');plt.close(fig)
        self.files.append(binding(self.dest/name));self.captions.append({'file':name,'title':title,'caption':caption})

    def pair_bars(self,ax,metrics,labels,name,panel,*,ylabel='Word error rate (%)'):
        positions=np.arange(len(metrics));width=.34;top=0
        for oi,out in enumerate(OUTS):
            values=[100*m[out]['wer'] if m[out]['wer'] is not None else np.nan for m in metrics]
            ax.bar(positions+(oi-.5)*width,values,width,color=COLORS[out],label=out)
            top=max(top,max((v for v in values if np.isfinite(v)),default=0))
            for i,(m,v) in enumerate(zip(metrics,values)):
                count=m[out];self.add(name,panel,labels[i],out,'pooled_wer_percent',None if not np.isfinite(v) else v,
                    numerator=count['errors'],denominator=count['reference_words'],n=m['paired_scenes'],unit='scene pairs')
                if np.isfinite(v):ax.text(positions[i]+(oi-.5)*width,v+max(1,top*.025),f"{v:.1f}%\n{count['errors']:,}/\n{count['reference_words']:,}",ha='center',va='bottom',fontsize=9)
        ax.set_xticks(positions,[f'{label}\nn={m["paired_scenes"]} pairs' for label,m in zip(labels,metrics)])
        ax.set_ylabel(ylabel);ax.set_ylim(0,max(12,top*1.35+4));ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)

    def words(self):
        name='01_words_and_paired_scenes.png';s=self.data['summary']
        fig,axes=plt.subplots(1,2,figsize=(13.5,5.8));fig.subplots_adjust(left=.07,right=.97,top=.84,bottom=.24,wspace=.26)
        self.pair_bars(axes[0],[s['primary'],s['overlap_mimo']],['Primary non-overlap','Overlap MIMO'],name,'pooled')
        axes[0].set_title('Summed errors / summed reference words',loc='left');axes[0].legend(frameon=False,loc='upper left')
        rows=[r for r in self.data['paired'] if r['population']=='primary_nonoverlap'];rooms=sorted({r['room'] for r in rows})
        palette=['#2166AC','#C66B18','#33816D','#8B5E9E'];maximum=0
        for ri,room in enumerate(rooms):
            rs=[r for r in rows if r['room']==room]
            xs=[100*r['O0']['text']['word_counts']['errors']/r['O0']['text']['word_counts']['reference_words'] for r in rs]
            ys=[100*r['O1']['text']['word_counts']['errors']/r['O1']['text']['word_counts']['reference_words'] for r in rs]
            axes[1].scatter(xs,ys,s=32,color=palette[ri%4],alpha=.8,edgecolors='white',linewidths=.5,label=ROOM_SHORT.get(room,room))
            maximum=max(maximum,max(xs+ys,default=0))
            for r,x,y in zip(rs,xs,ys):self.add(name,'paired_scatter',r['case_id'],'O1_vs_O0','scene_wer_percent',y,
                x_O0_wer_percent=x,y_O1_wer_percent=y,O0_errors=r['O0']['text']['word_counts']['errors'],O1_errors=r['O1']['text']['word_counts']['errors'],
                denominator=r['O0']['text']['word_counts']['reference_words'],room=room,n=1,unit='scene pair')
        lim=max(10,maximum*1.06);axes[1].plot([0,lim],[0,lim],color='#666666',linestyle='--',linewidth=1)
        axes[1].set(xlim=(-lim*.03,lim),ylim=(-lim*.03,lim),xlabel='O0 scene WER (%)',ylabel='O1 scene WER (%)')
        axes[1].set_title(f'Paired primary scenes (n={len(rows)})',loc='left');axes[1].set_aspect('equal',adjustable='box')
        axes[1].legend(loc='upper left',frameon=False,fontsize=9);axes[1].grid(alpha=.15)
        axes[1].text(.98,.04,'Below diagonal: fewer O1 errors',transform=axes[1].transAxes,ha='right',fontsize=9)
        caption='Development only. O0 = recorded ASR output with fixed +3 dB host gain; O1 = postprocessed auto output at unity. Primary and MIMO use different populations and are not pooled together. MIMO permits reference-utterance serialization, not separated-stream or timed-overlap recall. Scene points share people, text and measured room paths.'
        self.finish(fig,name,'Word accuracy of the two fixed output recipes',caption)

    def delta_axis(self,ax,rows,labels,name,panel,*,overall=None):
        y=np.arange(len(labels));points=[]
        ax.axvspan(-1,1,color='#EBEFF2',zorder=0);ax.axvline(0,color='#555555',linewidth=.8)
        for i,(r,label) in enumerate(zip(rows,labels)):
            value=r.get('O1_minus_O0_wer_pp') if r else None;n=r.get('paired_scenes',0) if r else 0
            self.add(name,panel,label,'O1_minus_O0','pooled_wer_difference_pp',value,n=n,unit='paired primary scenes',
                     numerator=r.get('O1_minus_O0_errors') if r else None,denominator=r['O0']['reference_words'] if r else 0)
            if value is None:ax.text(0,i,'unavailable',ha='center',va='center',fontsize=9,color='#777777',bbox={'facecolor':'white','edgecolor':'none','pad':1})
            else:
                points.append(value);ax.plot(value,i,'o',color='#666666' if value==0 else COLORS['O1'] if value<0 else COLORS['O0'],markersize=6)
                ax.annotate(f'{value:+.2f}',(value,i),xytext=(6,6),textcoords='offset points',fontsize=9)
        if overall is not None:
            lo,hi=overall['paired_O1_minus_O0_wer_pp_percentile95'];i=len(rows)-1
            ax.hlines(i,lo,hi,color='#202020',linewidth=2);points.extend([lo,hi])
            for metric,v in [('conditional_percentile95_lower_pp',lo),('conditional_percentile95_upper_pp',hi)]:self.add(name,panel,labels[i],'O1_minus_O0',metric,v,n=overall['primary']['paired_scenes'],unit='conditional matched-block interval')
        lo=min([-2]+points);hi=max([2]+points);pad=max(1,(hi-lo)*.24)
        ax.set_xlim(lo-pad,hi+pad);ax.set_yticks(y,[textwrap.fill(f'{label}  (n={r.get("paired_scenes",0) if r else 0})',32) for r,label in zip(rows,labels)])
        ax.invert_yaxis();ax.set_xlabel('O1 − O0 WER (percentage points)');ax.grid(axis='x',alpha=.15)

    def conditions(self):
        name='02_primary_condition_differences.png';s=self.data['summary'];strata=s['strata']
        fig,axes=plt.subplots(1,3,figsize=(17,8.8));fig.subplots_adjust(left=.15,right=.97,top=.85,bottom=.2,wspace=.9)
        rooms=[r for r in strata if r['population']=='primary' and r['dimension']=='room']
        room_labels=[ROOM_SHORT.get(r['level'],r['level']) for r in rooms]
        rooms.append(s['primary']);room_labels.append('Overall: conditional 95% interval')
        self.delta_axis(axes[0],rooms,room_labels,name,'rooms',overall=s.get('uncertainty') if 'paired_O1_minus_O0_wer_pp_percentile95' in s.get('uncertainty',{}) else None)
        axes[0].set_title('Four observed rooms',loc='left')
        source=[r for r in strata if r['population']=='primary' and r['dimension'] in ['corpus','quality_partition']]
        source_labels=[('Corpus: ' if r['dimension']=='corpus' else 'Quality: ')+short_label(r['level']) for r in source]
        self.delta_axis(axes[1],source,source_labels,name,'source_quality');axes[1].set_title('Corpus and source quality',loc='left')
        familymap={r['level']:r for r in strata if r['population']=='primary' and r['dimension']=='family_id'}
        fids=[f'F{i:02}' for i in range(1,13)]
        self.delta_axis(axes[2],[familymap.get(fid) for fid in fids],[fid+' '+FAMILY_SHORT[fid] for fid in fids],name,'families')
        axes[2].set_title('All 12 scenario families',loc='left')
        caption='Negative differences favor O1; positive favor O0. Points are descriptive pooled primary-WER differences, with explicit paired-scene counts. Only the overall line is a 2,000-replicate room-stratified matched-block percentile interval; remaining dependencies can make it optimistic. Grey ±1-point band is a planning reference, not equivalence. Family n=0 means no eligible primary scenes. MIXED source groups remain mixed; corpus contrasts are not causal age/accent effects.'
        self.finish(fig,name,'Primary word differences by observed condition',caption)

    def speaker_and_short(self):
        name='03_attribution_returns_and_short_turns.png';s=self.data['summary']
        fig,axes=plt.subplots(1,3,figsize=(17,6.2),gridspec_kw={'width_ratios':[1,1.1,1.5]});fig.subplots_adjust(left=.055,right=.98,top=.83,bottom=.28,wspace=.4)
        self.pair_bars(axes[0],[s['cpwer_primary'],s['cpwer_overlap']],['Primary','Overlap'],name,'cpwer',ylabel='Final-label cpWER (%)')
        axes[0].set_title('Final transcript-label snapshots',loc='left');axes[0].legend(frameon=False)
        keys=['consistent','inconsistent','unknown'];colors=['#39856D','#C66B18','#A9ADB3']
        return_rows=[]
        for group in ['all_repeated','after_other']:
            for out in OUTS:
                cont=s['support'][out]['continuity_by_population']['primary_nonoverlap']
                counts=cont['return_classifications'] if group=='all_repeated' else cont['return_strata'].get('return_after_other_speaker',{})
                return_rows.append((group,out,counts))
        for i,(group,out,counts) in enumerate(return_rows):
            total=sum(counts.values());left=0
            for key,color in zip(keys,colors):
                n=counts.get(key,0);value=100*n/total if total else 0
                axes[1].barh(i,value,left=left,color=color,height=.7,label=key if i==0 else None)
                if value>=12:axes[1].text(left+value/2,i,str(n),ha='center',va='center',fontsize=9,color='white' if key!='unknown' else '#222222')
                self.add(name,'return_groups',group,out,key+'_percent',value if total else None,numerator=n,denominator=total,n=total,unit='primary repeated-participant groups')
                left+=value
            axes[1].text(102,i,f'n={total}',ha='left',va='center',fontsize=9)
        axes[1].set_yticks(range(4),[('All repeated' if group=='all_repeated' else 'After other talker')+' / '+out for group,out,c in return_rows])
        axes[1].set(xlim=(0,130),xticks=[0,25,50,75,100],xlabel='Group classification (%)');axes[1].invert_yaxis()
        axes[1].set_title('Primary temporal continuity proxy',loc='left');axes[1].legend(loc='lower center',bbox_to_anchor=(.5,-.31),ncol=1,frameon=False)
        groups=[(clock,bucket) for clock in ['whole_clip_bin','active_duration_bin'] for bucket in ['<1s','1-<2s','>=2s']]
        short=[r for r in self.data['short'] if r['scope']=='single_source_attributable' and r['corpus']=='ALL']
        for oi,out in enumerate(OUTS):
            for i,(clock,bucket) in enumerate(groups):
                found=[r for r in short if r['stream']==out and r['duration_definition']==clock and r['duration_bin']==bucket]
                if len(found)!=1:raise ValueError('Short-turn summary does not have unique required rows')
                r=found[0];n=r['observed_turns'];hits=r['positive_supported_flags'];value=100*hits/n if n else None
                if hits>n:raise ValueError('More supported positive turns than observed turns')
                x=i+(oi-.5)*.3
                if value is not None:axes[2].plot(x,value,'o',color=COLORS[out],markersize=6,label=out if i==0 else None)
                axes[2].text(i,109+oi*12,f'{hits}/{n}' if n else 'n=0',ha='center',va='bottom',fontsize=9,color=COLORS[out])
                self.add(name,'short_turn_flags',clock+':'+bucket,out,'positive_supported_flag_percent',value,
                         numerator=hits,denominator=n,n=r['turn_instances'],source_clips=r['source_clips'],speakers=r['speakers'],unit='observed single-source turn instances')
        axes[2].set_xticks(range(6),[('Clip' if clock=='whole_clip_bin' else 'Active')+'\n'+bucket.replace('1-<2','1–<2') for clock,bucket in groups])
        axes[2].set(ylim=(0,143),yticks=[0,25,50,75,100],ylabel='Turns with supported positive flag (%)')
        axes[2].set_title('Native speech flags by duration',loc='left');axes[2].grid(axis='y',alpha=.15)
        axes[2].text(.02,.03,'Counts = positive / observed',transform=axes[2].transAxes,fontsize=9)
        caption='cpWER bars show percent and errors/reference words under one global final-label assignment; this is not DER or reconciled identity. Primary continuity retains consistent/inconsistent/unknown; after-other groups are a subset of all repeated participants. Short-turn flags use single-known-source temporal support, not recognized replies. Clip and estimated-active bins differ; windows are coarse and correlated. Unknown ambient and scheduled-overlap attribution are excluded from source-specific flag percentages.'
        self.finish(fig,name,'Attribution, repeated-participant continuity and speech support',caption)

    def workload(self):
        name='04_evidence_headroom_and_oracle.png';s=self.data['summary'];rep=self.data.get('representation')
        fig,axes=plt.subplots(2,2,figsize=(13.8,9.2));fig.subplots_adjust(left=.075,right=.97,top=.87,bottom=.16,wspace=.46,hspace=.72)
        ax=axes[0,0]
        for i,out in enumerate(OUTS):
            r=s['support'][out];value=r['embedding_calls_per_decoded_minute'];ax.bar(i,value,color=COLORS[out],width=.55)
            ax.text(i,value+max(1,value*.035),f'{value:.1f}/min\n{r["successful_embedding_calls"]:,} calls',ha='center',va='bottom',fontsize=9)
            self.add(name,'workload','all_development',out,'successful_embedding_calls_per_decoded_minute',value,
                     numerator=r['successful_embedding_calls'],denominator=r['decoded_s']/60,n=r['outputs'],unit='native output jobs')
        top=max(s['support'][o]['embedding_calls_per_decoded_minute'] for o in OUTS);ax.set(xticks=[0,1],xticklabels=OUTS,ylabel='Successful calls / decoded minute',ylim=(0,max(10,top*1.32)))
        ax.set_title('Native embedding workload',loc='left');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
        ax=axes[0,1];keys=['unique_evidence_audio_s','total_processed_window_s']
        for oi,out in enumerate(OUTS):
            r=s['support'][out]
            for i,key in enumerate(keys):
                value=r[key];ax.bar(i+(oi-.5)*.34,value/60,width=.34,color=COLORS[out],label=out if i==0 else None)
                ax.text(i+(oi-.5)*.34,value/60+max(.5,value/60*.035),f'{value/60:.1f}',ha='center',va='bottom',fontsize=9)
                self.add(name,'evidence_duration','all_development',out,key,value,n=r['outputs'],unit='seconds summed over native jobs')
        maxvalue=max(s['support'][o][k]/60 for o in OUTS for k in keys)
        ax.set(xticks=[0,1],xticklabels=['Union of evidence audio','Sum of overlapping windows'],ylabel='Minutes',ylim=(0,max(3,maxvalue*1.22)))
        ax.set_title('Evidence duration is not window count',loc='left');ax.legend(frameon=False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
        ax=axes[1,0];headrooms=[]
        for i,out in enumerate(OUTS):
            r=s['support'][out]['raw_levels'];peak=r['peak_fs'];headroom=-20*math.log10(peak) if peak and peak>0 else None
            headrooms.append(headroom or 0);ax.bar(i,headroom or 0,color=COLORS[out],width=.55)
            if headroom is not None:ax.plot(i,headroom,'o',color=COLORS[out],markersize=5)
            display_headroom=0. if headroom is not None and abs(headroom)<.0005 else headroom
            detail=(f'{display_headroom:.2f} dB\n' if headroom is not None else 'silent\n')+f"{r['rail_samples']:,} / {r['samples']:,}\nraw samples at rails\n{r['scenes_with_rails']}/{s['support'][out]['outputs']} outputs\nlongest run {r['longest_rail_run_samples']} samples"
            ax.text(i,(headroom or 0)+max(.2,max(headrooms)*.035),detail,ha='center',va='bottom',fontsize=9)
            self.add(name,'raw_headroom','all_development',out,'minimum_raw_headroom_db',headroom,peak_fs=peak,n=s['support'][out]['outputs'],unit='raw PCM24 outputs')
            self.add(name,'raw_headroom','all_development',out,'raw_rail_samples',r['rail_samples'],numerator=r['rail_samples'],denominator=r['samples'],n=s['support'][out]['outputs'],scenes_with_rails=r['scenes_with_rails'],longest_run_samples=r['longest_rail_run_samples'],unit='raw PCM24 samples')
        ax.set(xticks=[0,1],xticklabels=OUTS,ylabel='Headroom at largest raw peak (dB)',ylim=(0,max(4,max(headrooms)*1.8+1)))
        ax.set_title('Raw output rails remain in the evidence',loc='left');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
        ax=axes[1,1]
        if rep is None:
            ax.axis('off');ax.text(.05,.55,'Oracle-window representation unavailable',transform=ax.transAxes,fontsize=11)
        else:
            rows=[r for r in rep['distributions'] if r['stratum']=='ALL' and r['value']=='ALL'];labels=[];i=0
            for kind in ['genuine','impostor']:
                matches=[r for r in rows if r['kind']==kind]
                if len(matches)!=1:raise ValueError('Oracle compact distribution is ambiguous')
                r=matches[0]
                for out in OUTS:
                    q=r[out];ax.hlines(i,q['p10'],q['p90'],color=COLORS[out],linewidth=3);ax.plot(q['median'],i,'o',color=COLORS[out],markersize=7)
                    labels.append(('Same person' if kind=='genuine' else 'Different person')+' / '+out+f"\nn={r['paired_comparisons']}")
                    for key in ['p10','median','p90']:self.add(name,'oracle_cosine',kind,out,'cosine_'+key,q[key],n=r['paired_comparisons'],unit='paired oracle comparisons',paired_windows=rep['completed_paired_windows'])
                    i+=1
            ax.set_yticks(range(i),labels);ax.invert_yaxis();ax.set_xlabel('Cosine similarity; marker median, line p10–p90')
            ax.xaxis.set_major_locator(MaxNLocator(nbins=5,prune='both'))
            ax.set_title(f"Oracle representation: {rep['completed_paired_windows']} paired windows",loc='left');ax.grid(axis='x',alpha=.15)
        caption='All native development jobs; overlapping windows and reused people are dependent. Successful calls are observed; rejected calls are not fully logged. Union duration counts each sample once within a job. Raw PCM24 positive rail uses the retained packed-payload criterion; host attenuation cannot repair clipping. Oracle source-selected windows use unchanged embeddings, not online identity/enrollment accuracy; quantile lines are distributions, not confidence intervals or tuned thresholds.'
        self.finish(fig,name,'Evidence workload, raw headroom and bounded representation',caption)

    def run(self):
        self.words();self.conditions();self.speaker_and_short();self.workload()
        if len(self.files)!=4:raise AssertionError('Exactly four scientific figures')
        path=self.dest/'plotdata.csv';fields=list(dict.fromkeys(k for r in self.records for k in r))
        with path.open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(self.records)
        captions=self.dest/'CAPTIONS.md'
        captions.write_text('\n\n'.join(f"**{c['file']}**\n\n{c['caption']}" for c in self.captions)+'\n',encoding='utf-8')
        receipt={'schema':'jp_s5_figures_v1','status':'SYNTHETIC_PREVIEW_ONLY' if self.preview else 'FINAL_COMPLETE_PANEL_FIGURES',
                 'input_bindings':self.data.get('inputs',[]),'code':binding(__file__),'figures':self.files,
                 'plotdata':binding(path),'captions':binding(captions),'plotdata_rows':len(self.records),
                 'minimum_font_size_points':9,'dpi':150,'figure_count':4,'layout_warnings':self.layout_warnings,
                 'reserve_task_audio_or_native_logs_opened':0,'total_png_bytes':sum(f['bytes'] for f in self.files)}
        save(self.dest/'FIGURE_RECEIPT.json',receipt)
        return receipt


def synthetic_fixture():
    """Deterministic fictional values; never load partial or final task predictions."""
    def pair(n=12,ref=600,e0=60,e1=48):
        a={'errors':e0,'reference_words':ref,'wer':e0/ref,'scenes':n};b={'errors':e1,'reference_words':ref,'wer':e1/ref,'scenes':n}
        return {'paired_scenes':n,'O0':a,'O1':b,'O1_minus_O0_errors':e1-e0,'O1_minus_O0_wer_pp':100*(e1-e0)/ref}
    primary=pair(117,6000,720,650);overlap=pair(36,1500,550,500)
    s={'status':'SYNTHETIC_FIXTURE','primary':primary,'overlap_mimo':overlap,'cpwer_primary':pair(117,6000,5000,5400),
       'cpwer_overlap':pair(36,1500,1800,1700),'strata':[],'support':{},
       'uncertainty':{'paired_O1_minus_O0_wer_pp_percentile95':[-2.8,.4],'primary':primary}}
    rooms=list(ROOM_SHORT)
    for i,room in enumerate(rooms):s['strata'].append({'population':'primary','dimension':'room','level':room,**pair(20+i,1000,100+10*i,105+4*i)})
    for dimension,levels in [('corpus',['CMU ARCTIC','Common Voice','HiFiTTS','MIXED: Common Voice + HiFiTTS']),
                             ('quality_partition',['clean','other','self_reported_60plus_real_recording','studio_project_design','MIXED: clean + other'])]:
        for i,label in enumerate(levels):s['strata'].append({'population':'primary','dimension':dimension,'level':label,**pair(10+i,1000,100+10*i,80+15*i)})
    for i in range(1,13):
        if i not in [4,9,10]:s['strata'].append({'population':'primary','dimension':'family_id','level':f'F{i:02}',**pair(8+i,700,90+i,72+3*i)})
    rows=[]
    for i in range(117):
        a=(i*7)%81;b=max(0,a+((i%9)-4)*3);ref=100
        rows.append({'case_id':f'FIXTURE_{i:03}','population':'primary_nonoverlap','room':rooms[i%4],
                     'O0':{'text':{'word_counts':{'errors':a,'reference_words':ref}}},'O1':{'text':{'word_counts':{'errors':b,'reference_words':ref}}}})
    short=[]
    for oi,out in enumerate(OUTS):
        s['support'][out]={'outputs':180,'decoded_s':8260,'successful_embedding_calls':8000+oi*1300,
           'embedding_calls_per_decoded_minute':(8000+oi*1300)/(8260/60),'unique_evidence_audio_s':2800+oi*200,'total_processed_window_s':4000+oi*650,
           'raw_levels':{'peak_fs':.45 if oi==0 else 1.,'rail_samples':0 if oi==0 else 747,'samples':132000000,
                         'scenes_with_rails':0 if oi==0 else 67,'longest_rail_run_samples':0 if oi==0 else 7},
           'continuity_by_population':{'primary_nonoverlap':{'return_classifications':{'consistent':40+oi*4,'inconsistent':30+oi*2,'unknown':45-oi*6},
              'return_strata':{'return_after_other_speaker':{'consistent':25+oi*2,'inconsistent':24+oi*2,'unknown':26-oi*4}}}}}
        for clock in ['whole_clip_bin','active_duration_bin']:
            for i,bucket in enumerate(['<1s','1-<2s','>=2s']):
                n=[34,32,490][i]+(7 if clock=='active_duration_bin' else 0);hits=n-[4,2,8][i]+oi
                short.append({'scope':'single_source_attributable','corpus':'ALL','duration_definition':clock,'duration_bin':bucket,
                              'stream':out,'observed_turns':n,'positive_supported_flags':hits,'turn_instances':n+1,'source_clips':n//2,'speakers':min(34,n)})
    distributions=[]
    for kind,center in [('genuine',.23),('impostor',.09)]:
        distributions.append({'stratum':'ALL','value':'ALL','kind':kind,'paired_comparisons':104,
            'O0':{'p10':center-.14,'median':center,'p90':center+.13},'O1':{'p10':center-.16,'median':center-.01,'p90':center+.11}})
    return {'summary':s,'paired':rows,'short':short,'representation':{'completed_paired_windows':222,'distributions':distributions},'inputs':[]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview-fixtures',action='store_true')
    args=parser.parse_args()
    data=synthetic_fixture() if args.preview_fixtures else load_final()
    receipt=Figures(data,PREVIEW if args.preview_fixtures else REPORT/'figures',args.preview_fixtures).run()
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['figures','input_bindings','code']},indent=2))
    if receipt['layout_warnings']:raise SystemExit('Layout warning: inspect preview before accepting final figures')


if __name__=='__main__':main()
