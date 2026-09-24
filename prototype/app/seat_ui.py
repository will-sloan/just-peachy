"""Draft-only touch seat editor; no audio/device/model ownership. See README_SEATS.md."""
from copy import deepcopy
import math
import tkinter as tk

from .beam_diagnostics import arrow_tip
from .mode_policy import MODE_METADATA
from .seats import DEFAULT_TOLERANCE, collisions


class SeatUI:
    def show_seats(self,mode=None):
        self._seat_mode=mode or (self.snapshot.get('mode') if self.snapshot.get('mode','').startswith('assigned_') else 'assigned_direction')
        saved=self.snapshot.get('seating',{});people={p['id'] for p in self.snapshot.get('people',[])}
        self._seat_draft=[deepcopy(r) for r in saved.get('rows',[]) if r['person_id'] in people]
        self._seat_strength=saved.get('strength','soft') if self._seat_mode=='assigned_hybrid' else 'soft';self._seat_selected=None;self._seat_page=0;self._seat_ack=False;self._seat_placing=False
        self._draw_seat_page()

    def _draw_seat_page(self):
        self.page='seats';frame=self._page('Assigned seats',back=self.show_modes)
        self._paragraph_label(frame,MODE_METADATA[self._seat_mode]['full_name'],True)
        self._paragraph_label(frame,'Draft: tap a name then the arc, or drag a name/point. Front/back share the same bearing. Apply confirms this location only.',True)
        self.seat_canvas=tk.Canvas(frame,height=self.px(195),bg=self.color('surface'),highlightthickness=0)
        self.seat_canvas.pack(fill='x',padx=self.px(8));self.seat_canvas.bind('<Configure>',lambda e:self._paint_seats())
        self.seat_canvas.bind('<ButtonPress-1>',self._seat_arc_press)
        self.seat_canvas.bind('<B1-Motion>',self._seat_arc_drag)
        self.seat_canvas.bind('<ButtonRelease-1>',self._seat_arc_drag)
        self.seat_selected_label=self.label(frame,'',size='small_font_px');self.seat_selected_label.pack(fill='x',padx=self.px(12))
        self._seat_people_frame=tk.Frame(frame,bg=self.color('background'));self._seat_people_frame.pack(fill='x')
        self._paint_seat_people()
        for commands in (
            [('Previous names',lambda:self._seat_names_page(-1),'seat_previous'),('Next names',lambda:self._seat_names_page(1),'seat_next')],
            [('Angle −1°',lambda:self._seat_adjust('angle_deg',-1),'seat_angle_minus'),('Angle +1°',lambda:self._seat_adjust('angle_deg',1),'seat_angle_plus')],
            [('Region −1°',lambda:self._seat_adjust('tolerance_deg',-1),'seat_region_minus'),('Region +1°',lambda:self._seat_adjust('tolerance_deg',1),'seat_region_plus')]):
            line=tk.Frame(frame,bg=self.color('background'));line.pack(fill='x',padx=self.px(8),pady=self.px(2))
            for i,(text,action,key) in enumerate(commands):
                line.columnconfigure(i,weight=1,uniform='seat_controls')
                self.button(line,text,action,key=key,wrap=180).grid(row=0,column=i,sticky='ew',padx=self.px(2))
        self.seat_conflict_label=self.label(frame,'',size='small_font_px');self.seat_conflict_label.pack(fill='x',padx=self.px(12),pady=self.px(4))
        self.button(frame,'Accept ambiguous regions · no direction name there',self._seat_acknowledge,key='seat_ack',height=58).pack(fill='x',padx=self.px(12),pady=self.px(3))
        if self._seat_mode=='assigned_hybrid':
            self.button(frame,'Spatial prior: '+self._seat_strength+' · tap to change',self._seat_toggle_strength,key='seat_strength').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Apply / re-anchor here',self._seat_apply,accent=True,key='seat_apply').pack(fill='x',padx=self.px(12),pady=self.px(5))
        self.button(frame,'Cancel · keep current layout',self.show_modes,key='seat_cancel').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Remove selected seat',self._seat_remove,key='seat_remove').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Clear draft',self._seat_clear,key='seat_clear').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Save reusable template · does not anchor',lambda:self._call('seats_save_template',self._seat_draft,self._seat_strength),key='seat_save_template',height=58).pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Load template into draft',self._seat_load_template,key='seat_load_template').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Tablet moved · invalidate now',self._seat_moved,key='seat_moved').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Live decision / raw score details',self.show_identity_scores).pack(fill='x',padx=self.px(12),pady=self.px(3))
        self._paragraph_label(frame,'No beam steering. Direction-only can misname a visitor or singer. Hybrid keeps an Unknown alternative and releases conflicting seat trust. Clear/Cancel change only this draft. A saved template is never an active physical anchor.',True)
        self._paint_seats()

    def _paint_seat_people(self):
        for child in self._seat_people_frame.winfo_children():child.destroy()
        people=self.snapshot.get('roster_compatibility',self.snapshot.get('people',[]))
        if not people:self._paragraph_label(self._seat_people_frame,'Enroll people before assigning seats.');return
        self._seat_page=max(0,min(self._seat_page,(len(people)-1)//2))
        for p in people[self._seat_page*2:self._seat_page*2+2]:
            pid=p['id'];compatible=self._seat_mode=='assigned_direction' or p.get('compatible_references',1)>0
            text=p['name']+f" · {pid[:6]}"+(' · unavailable on this tap' if not compatible else '')
            control=self.button(self._seat_people_frame,text,lambda key=pid:self._seat_select(key),key='seat_person_'+pid,height=50)
            control.pack(fill='x',padx=self.px(12),pady=self.px(2))
            if not compatible:control.button.configure(state='disabled');continue
            control.button.bind('<ButtonPress-1>',lambda e,key=pid:self._seat_select(key))
            control.button.bind('<B1-Motion>',self._seat_name_drag)
            control.button.bind('<ButtonRelease-1>',self._seat_name_drag)

    def _seat_select(self,pid):
        self._seat_selected=pid;self._seat_placing=True;self._paint_seats();return 'break'

    def _seat_names_page(self,delta):
        self._seat_page+=delta;self._paint_seat_people()

    def _seat_geometry(self):
        return max(self.px(100),self.seat_canvas.winfo_width()/2),self.px(160),self.px(118)

    def _seat_name_drag(self,event):
        x=event.x_root-self.seat_canvas.winfo_rootx();y=event.y_root-self.seat_canvas.winfo_rooty()
        if 0<=x<=self.seat_canvas.winfo_width() and 0<=y<=self.seat_canvas.winfo_height():self._seat_place(x,y)
        return 'break'

    def _seat_arc_press(self,event):
        cx,cy,radius=self._seat_geometry()
        nearby=[r for r in self._seat_draft if math.dist(arrow_tip(r['angle_deg'],cx,cy,radius),(event.x,event.y))<=self.px(24)]
        if nearby and not self._seat_placing:self._seat_selected=nearby[0]['person_id']
        self._seat_place(event.x,event.y);self._seat_placing=False;return 'break'

    def _seat_arc_drag(self,event):self._seat_place(event.x,event.y);return 'break'

    def _seat_place(self,x,y):
        if self._seat_selected is None:return
        cx,cy,radius=self._seat_geometry()
        if y>cy or math.hypot(x-cx,y-cy)<self.px(20):return
        angle=round(math.degrees(math.atan2(cy-y,x-cx)))
        row=next((r for r in self._seat_draft if r['person_id']==self._seat_selected),None)
        if row is None:
            if len(self._seat_draft)>=16:return
            row=dict(person_id=self._seat_selected,tolerance_deg=DEFAULT_TOLERANCE);self._seat_draft.append(row)
        row['angle_deg']=float(angle);self._seat_ack=False;self._paint_seats()

    def _seat_adjust(self,key,delta):
        row=next((r for r in self._seat_draft if r['person_id']==self._seat_selected),None)
        if row:
            lo,hi=(0.,180.) if key=='angle_deg' else (1.,45.)
            row[key]=max(lo,min(hi,row[key]+delta));self._seat_ack=False;self._paint_seats()

    def _paint_seats(self):
        if not hasattr(self,'seat_canvas') or not self.seat_canvas.winfo_exists():return
        canvas=self.seat_canvas;canvas.delete('all');cx,cy,radius=self._seat_geometry()
        canvas.create_arc(cx-radius,cy-radius,cx+radius,cy+radius,start=0,extent=180,style='arc',outline=self.color('muted'),width=2)
        names={p['id']:p['name'] for p in self.snapshot.get('people',[])}
        for angle,label in ((0,'0° MIC3'),(90,'90° front/back fold'),(180,'180° MIC0')):
            x,y=arrow_tip(angle,cx,cy,radius+self.px(20))
            canvas.create_text(x,y,text=label,font=self.font(11),fill=self.color('muted'),anchor='s')
        canvas.create_rectangle(cx-self.px(35),cy,cx+self.px(35),cy+self.px(18),outline=self.color('muted'))
        canvas.create_text(cx,cy+self.px(9),text='Tablet',font=self.font(11),fill=self.color('text'))
        conflict=collisions(self._seat_draft);conflicting={p for row in conflict for p in row['person_ids']};drawn=set()
        for row in self._seat_draft:
            angle=row['angle_deg'];pid=row['person_id'];color=self.color('accent' if pid==self._seat_selected else 'text')
            if pid in conflicting:color=self.color('error')
            lo=max(0.,angle-row['tolerance_deg']);hi=min(180.,angle+row['tolerance_deg'])
            canvas.create_arc(cx-radius,cy-radius,cx+radius,cy+radius,start=lo,extent=hi-lo,style='arc',outline=color,width=5,tags=('seat_region',pid))
            x,y=arrow_tip(angle,cx,cy,radius)
            canvas.create_line(cx,cy,x,y,fill=color,dash=(3,3),tags=('seat_assignment',pid))
            canvas.create_oval(x-self.px(8),y-self.px(8),x+self.px(8),y+self.px(8),fill=color,outline=color,tags=('seat_point',pid))
            group=[r for r in self._seat_draft if abs(r['angle_deg']-angle)<3]
            if not any(r['person_id'] in drawn for r in group):
                title=f'{len(group)} seats · ambiguous' if len(group)>1 else names.get(pid,'Deleted')[:14]
                canvas.create_text(x,y+self.px(16),text=title,fill=color,font=self.font(11),tags=('seat_name',pid))
                drawn.update(r['person_id'] for r in group)
        if conflict:canvas.create_text(cx,self.px(187),text='Overlapping projected regions · no direction-only name',fill=self.color('error'),font=self.font(11),tags=('seat_collision',))
        current=next((r for r in self._seat_draft if r['person_id']==self._seat_selected),None)
        if hasattr(self,'seat_selected_label'):
            self.seat_selected_label.configure(text=(names.get(self._seat_selected,'Choose a name')+ (f" · {current['angle_deg']:.0f}° ±{current['tolerance_deg']:.0f}°" if current else ' · then place on the arc')))
        if hasattr(self,'seat_conflict_label'):
            self.seat_conflict_label.configure(text=(f'{len(conflict)} overlapping projected region(s). '+('Ambiguous outcome accepted.' if self._seat_ack else 'Adjust or accept ambiguity below.') if conflict else 'No overlapping regions. Front/back remains indistinguishable.'))
        if 'seat_apply' in self.actions:
            self.actions['seat_apply'].configure(state='normal' if self._seat_draft and (not conflict or self._seat_ack) else 'disabled')

    def _seat_acknowledge(self):self._seat_ack=True;self._paint_seats()
    def _seat_remove(self):
        self._seat_draft=[r for r in self._seat_draft if r['person_id']!=self._seat_selected];self._seat_ack=False;self._paint_seats()
    def _seat_clear(self):self._seat_draft=[];self._seat_ack=False;self._paint_seats()
    def _seat_toggle_strength(self):
        self._seat_strength='strong' if self._seat_strength=='soft' else 'soft'
        self.actions['seat_strength'].configure(text='Spatial prior: '+self._seat_strength+' · tap to change')
    def _seat_load_template(self):
        saved=self.snapshot.get('seating',{}).get('template',{});people={p['id'] for p in self.snapshot.get('people',[])}
        self._seat_draft=[deepcopy(r) for r in saved.get('rows',[]) if r['person_id'] in people]
        self._seat_strength=saved.get('strength','soft') if self._seat_mode=='assigned_hybrid' else 'soft';self._seat_ack=False;self._paint_seats()
        if self._seat_mode=='assigned_hybrid':self.actions['seat_strength'].configure(text='Spatial prior: '+self._seat_strength+' · tap to change')
    def _seat_apply(self):
        if self._call('seats_apply',self._seat_draft,self._seat_mode,self._seat_strength,self._seat_ack):self.home()
    def _seat_moved(self):
        if self._call('reset_spatial'):
            self._notice='Anchor invalidated immediately. Arrange seats and Apply to re-anchor.';self._show_status()
