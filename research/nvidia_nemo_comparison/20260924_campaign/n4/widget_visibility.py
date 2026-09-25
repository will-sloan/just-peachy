"""Read-only Tk viewport observations, without inference. README_WIDGET_VISIBILITY.md."""
from copy import deepcopy
import math
import time

MAX_ROWS=512
MAX_SPANS=8192
MAX_VISIBLE_CHARACTER_CHECKS=4096
SCOPE='Tk widget viewport geometry on the admitted desktop; no physical scanout or human visibility claim'


def chars(widget,value):
    return int(widget.tk.call('string','length',value))


def max_index(widget,a,b):return a if widget.compare(a,'>=',b) else b
def min_index(widget,a,b):return a if widget.compare(a,'<=',b) else b


def content_rectangle(widget):
    """Intersect the text widget with every mapped parent, in local coordinates."""
    if not widget.winfo_viewable():return None
    x,y=widget.winfo_rootx(),widget.winfo_rooty()
    left,top,right,bottom=0,0,widget.winfo_width(),widget.winfo_height()
    current=widget
    while current.master is not None:
        current=current.master
        if not current.winfo_viewable():return None
        a,b=current.winfo_rootx()-x,current.winfo_rooty()-y
        left,top=max(left,a),max(top,b)
        right,bottom=min(right,a+current.winfo_width()),min(bottom,b+current.winfo_height())
    inset=int(widget.cget('borderwidth'))+int(widget.cget('highlightthickness'))
    left,top=max(left,inset),max(top,inset)
    right,bottom=min(right,widget.winfo_width()-inset),min(bottom,widget.winfo_height()-inset)
    return (left,top,right,bottom) if right>left and bottom>top else None


def region_visibility(widget,start,end,*,budget):
    """Count nonspace glyph rectangles intersecting the actual text viewport.

    The viewport index limits work to on-screen text; off-screen history and
    elided active rows cannot create positive visibility. Unicode offsets use
    Tcl indices, matching the unchanged application renderer.
    """
    rectangle=content_rectangle(widget)
    result=dict(mapped=rectangle is not None,visible_nonspace_characters=0,checked_characters=0,
        any_visible=False,partially_clipped_characters=0,scope=SCOPE)
    if rectangle is None:return result
    left,top,right,bottom=rectangle
    first=widget.index(f'@{left},{top}');last=widget.index(f'@{right-1},{bottom-1}+1c')
    index=widget.index(max_index(widget,start,first));stop=widget.index(min_index(widget,end,last))
    while widget.compare(index,'<',stop):
        budget[0]-=1
        if budget[0]<0:raise ValueError('Visible-character observation budget exceeded')
        result['checked_characters']+=1
        text=widget.get(index,f'{index}+1c');box=widget.bbox(index)
        if text and not text.isspace() and box is not None:
            x,y,width,height=box
            visible_width=max(0,min(right,x+width)-max(left,x))
            visible_height=max(0,min(bottom,y+height)-max(top,y))
            if width>0 and height>0 and visible_width>0 and visible_height>0:
                result['visible_nonspace_characters']+=1
                result['partially_clipped_characters']+=int(visible_width<width or visible_height<height)
        following=widget.index(f'{index}+1c')
        if not widget.compare(following,'>',index):raise ValueError('Tk character cursor did not advance')
        index=following
    result['any_visible']=result['visible_nonspace_characters']>0
    return result


def pane_row(widget,marks,values,row_id,*,active,budget):
    if row_id not in marks:
        if row_id in values:raise ValueError('Caption cache lacks its widget marks')
        return dict(present_in_widget=False,caption_visible=False,heading_visible=False)
    if row_id not in values:raise ValueError('Widget marks lack a caption cache entry')
    label,caption,_=values[row_id];start,end=marks[row_id]
    prefix=(label+'\n') if label else ''
    expected=prefix+caption+('\n' if active else '\n\n')
    if widget.get(start,end)!=expected:raise ValueError('Actual widget text differs from applied caption cache')
    caption_start=widget.index(f'{start}+{chars(widget,prefix)}c')
    caption_end=widget.index(f'{caption_start}+{chars(widget,caption)}c')
    heading_end=widget.index(f'{start}+{chars(widget,label)}c')
    body=region_visibility(widget,caption_start,caption_end,budget=budget)
    heading=region_visibility(widget,start,heading_end,budget=budget)
    return dict(present_in_widget=True,applied_caption_text=caption,applied_heading_text=label,
        heading_suppressed=not bool(label),caption_visible=body['any_visible'],heading_visible=heading['any_visible'],
        caption_viewport=body,heading_viewport=heading)


def snapshot(ui,rows,*,observed_at=None,source_origin=None,source_clock='UNAVAILABLE'):
    """Call after actual render/update_idletasks, on the Tk thread only.

    Does not call _display_row: that function advances GUI identity state.
    Does not scroll, force a render, change labels, query hardware, or read truth.
    """
    now=time.perf_counter() if observed_at is None else observed_at
    if type(now) not in (int,float) or not math.isfinite(now):raise ValueError('Finite observation time required')
    if source_origin is not None:
        if (source_clock!='ACTUAL_SOURCE_MONOTONIC' or type(source_origin) not in (int,float)
                or not math.isfinite(source_origin) or source_origin>now):raise ValueError('Actual source origin required; modeled clock forbidden')
    if len(rows)>MAX_ROWS or len({str(r['id']) for r in rows})!=len(rows):raise ValueError('Bounded unique Controller rows required')
    budget=[MAX_VISIBLE_CHARACTER_CHECKS];result=[];strict=bool(ui.snapshot.get('strict'))
    for row in rows:
        rid=str(row['id']);filtered=strict and not row.get('selected')
        if filtered:
            if rid in ui._marks or rid in ui._active_pane.marks:raise ValueError('Strict-filtered row remains in a widget')
            panes={k:dict(present_in_widget=False,caption_visible=False,heading_visible=False) for k in ('history','active')}
        else:
            panes=dict(history=pane_row(ui.caption_text,ui._marks,ui._row_cache,rid,active=False,budget=budget),
                active=pane_row(ui.active_text,ui._active_pane.marks,ui._active_pane.values,rid,active=True,budget=budget))
            if not panes['history']['present_in_widget']:raise ValueError('Unfiltered Controller row missing from full-caption widget')
        result.append(dict(row_id=rid,caption_key=row.get('caption_key'),span_ids=[str(s) for s in row.get('span_ids') or [rid]],
            final=bool(row.get('final')),raw_asr_text=row.get('raw_asr_text'),source_start_sec=row.get('source_start_sec'),
            source_end_sec=row.get('source_end_sec'),timing_kind=row.get('timing_kind'),speaker_revision=row.get('speaker_revision'),
            verified_profile_id=row.get('profile_id'),display_profile_id=row.get('display_profile_id'),
            naming_state=row.get('naming_state'),identity_assignment=row.get('identity_assignment'),
            strictly_filtered=bool(filtered),caption_visible=any(p['caption_visible'] for p in panes.values()),
            heading_visible=any(p['heading_visible'] for p in panes.values()),panes=panes))
    return dict(schema='n4-tk-viewport-observation-v1',observed_monotonic_sec=now,
        source_origin_monotonic_sec=source_origin,source_elapsed_sec=now-source_origin if source_origin is not None else None,
        source_clock=source_clock,scope=SCOPE,physical_scanout_measured=False,
        source_relative_times_available=source_origin is not None,source_to_widget_latency_qualified=False,rows=result,
        character_checks=MAX_VISIBLE_CHARACTER_CHECKS-budget[0])


class VisibilityHistory:
    """Retain first/final/latest observed states and explicit sampling intervals.

    A sample is a point observation, not proof of continuous visibility between
    polls. Header suppression is not an observed repeated name. No identity is
    inferred from a label string or a closed-roster assumption.
    """
    def __init__(self):self.previous=None;self.spans={};self.samples=0;self.max_interval=0.;self.last_rows={}
    def add(self,observation):
        if observation['schema']!='n4-tk-viewport-observation-v1':raise ValueError('Unknown viewport contract')
        at=observation['observed_monotonic_sec']
        if self.previous is not None and at<self.previous:raise ValueError('Viewport clock moved backwards')
        if self.previous is not None:self.max_interval=max(self.max_interval,at-self.previous)
        self.previous=at;self.samples+=1;delta=[]
        live={r['row_id'] for r in observation['rows']}
        current_spans={s for r in observation['rows'] for s in r['span_ids']}
        if len(set(self.spans)|current_spans)>MAX_SPANS:raise ValueError('Viewport span-history bound exceeded')
        for rid in set(self.last_rows)-live:
            removed=deepcopy(self.last_rows.pop(rid));removed.update(caption_visible=False,heading_visible=False,removed_from_controller=True)
            removed['panes']={k:dict(present_in_widget=False,caption_visible=False,heading_visible=False) for k in ('history','active')}
            delta.append(removed)
            for span in set(removed['span_ids'])-current_spans:
                self.spans[span]['latest']=dict(observed_monotonic_sec=at,source_elapsed_sec=observation['source_elapsed_sec'],row=deepcopy(removed))
        for row in observation['rows']:
            rid=row['row_id'];old=self.last_rows.get(rid)
            if old!=row:delta.append(deepcopy(row))
            self.last_rows[rid]=deepcopy(row)
            state=dict(observed_monotonic_sec=at,source_elapsed_sec=observation['source_elapsed_sec'],row=deepcopy(row))
            for span in row['span_ids']:
                record=self.spans.setdefault(span,dict(first_visible=None,first_final_visible=None,latest=None,
                    observed_heading_changes=0,observed_visible_heading_changes=0))
                if row['caption_visible'] and record['first_visible'] is None:record['first_visible']=deepcopy(state)
                if row['caption_visible'] and row['final'] and record['first_final_visible'] is None:
                    record['first_final_visible']=deepcopy(state)
                previous=record['latest']
                def headings(v):return {k:p.get('applied_heading_text') for k,p in v['row']['panes'].items()}
                if previous is not None and headings(previous)!=headings(state):
                    record['observed_heading_changes']+=1
                    if row['heading_visible']:record['observed_visible_heading_changes']+=1
                record['latest']=deepcopy(state)
        return dict(observed_monotonic_sec=at,source_elapsed_sec=observation['source_elapsed_sec'],changed_rows=delta,
            scope='Point observations; intervals do not establish continuous exposure')
    def summary(self):
        return dict(samples=self.samples,maximum_observation_interval_seconds=self.max_interval,spans=deepcopy(self.spans),
            continuous_exposure_measured=False,physical_scanout_measured=False)
