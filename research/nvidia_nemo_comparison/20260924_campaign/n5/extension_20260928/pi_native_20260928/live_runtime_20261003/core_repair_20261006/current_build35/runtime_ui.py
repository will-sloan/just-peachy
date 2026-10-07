"""Scrollable tablet controls and retained-coordinate display; README_RUNTIME_UI.md."""
import datetime
import math
import time


def history_label(row):
    stamp=datetime.datetime.fromtimestamp(row['created']).strftime('%Y-%m-%d %H:%M:%S')
    title=row.get('spec',{}).get('title')
    title=(title.strip()[:64]+' · ') if isinstance(title,str) and title.strip() else ''
    return '%s%s · %.1fs · %s'%(title,stamp,row.get('duration_seconds',0),row['session_id'][:8])


def device_tip(angle,cx,cy,radius):
    """Retained display mapping:0 right,90 front/rear ambiguity,180 left."""
    if isinstance(angle,bool) or not math.isfinite(angle) or not 0<=angle<=180:
        raise ValueError('Display angle must be finite and within0..180 degrees')
    radians=math.radians(angle)
    return cx+radius*math.cos(radians),cy-radius*math.sin(radians)


class ScrollPage:
    def __init__(self,parent):
        import tkinter as tk
        from tkinter import ttk
        self.frame=ttk.Frame(parent)
        self.canvas=tk.Canvas(self.frame,highlightthickness=0,yscrollincrement=24,bg='#142029')
        bar=ttk.Scrollbar(self.frame,orient='vertical',command=self.canvas.yview)
        bar.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.configure(yscrollcommand=bar.set)
        self.body=ttk.Frame(self.canvas,padding=8)
        self.body._scroll_viewport=self.canvas
        self.window=self.canvas.create_window((0,0),window=self.body,anchor='nw')
        self.body.bind('<Configure>',lambda event:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda event:self.canvas.itemconfigure(self.window,width=event.width))
        def wheel(event):
            node=event.widget
            while node is not None and node is not self.body:node=getattr(node,'master',None)
            if node is self.body:
                amount=(-1 if event.num==4 else 1) if event.num in (4,5) else (-1 if event.delta>0 else 1)
                self.canvas.yview_scroll(amount*3,'units');return 'break'
        for pattern in ('<MouseWheel>','<Button-4>','<Button-5>'):self.canvas.bind_all(pattern,wheel,add='+')


class SpatialPanel:
    """Device arrows use provider angles; visual zero changes only debug drawing."""
    def __init__(self,parent,manager):
        import tkinter as tk
        from tkinter import ttk
        self.manager=manager;self.snapshot={};self.zero=0.;self.debug=False
        self.frame=ttk.Frame(parent);self.frame.pack(fill='x',pady=8)
        ttk.Label(self.frame,text='Sound direction · device-relative',font=('Sans',12,'bold')).pack(anchor='w')
        self.canvas=tk.Canvas(self.frame,height=180,bg='#142029',highlightthickness=0)
        self.canvas.pack(fill='x')
        self.message=ttk.Label(self.frame,text='Start live input to view direction.',wraplength=410)
        self.message.pack(fill='x')
        ttk.Button(self.frame,text='Orientation graphic · show / hide',command=self.toggle).pack(fill='x')
        self.debug_canvas=tk.Canvas(self.frame,height=110,bg='#20242a',highlightthickness=0)
        self.debug_canvas.bind('<Button-1>',lambda event:self.recenter())
        self.zero_button=ttk.Button(self.frame,text='Recenter orientation graphic (visual only)',command=self.recenter)
        ttk.Label(self.frame,text='Beam direction is relative to this device. Speaker names remain voice matches; locations are estimates.',wraplength=410).pack(fill='x')

    def visible(self):
        if not self.canvas.winfo_viewable():return False
        viewport=getattr(self.frame.master,'_scroll_viewport',None)
        if viewport is None:return True
        top=self.frame.winfo_rooty();bottom=top+self.frame.winfo_height()
        return bottom>viewport.winfo_rooty() and top<viewport.winfo_rooty()+viewport.winfo_height()

    def toggle(self):
        self.debug=not self.debug
        if self.debug:self.debug_canvas.pack(fill='x');self.zero_button.pack(fill='x')
        else:self.debug_canvas.pack_forget();self.zero_button.pack_forget()
        self.draw_debug()

    def recenter(self):
        motion=self.snapshot.get('motion') or {}
        if motion.get('valid') is True and isinstance(motion.get('yaw_deg'),(int,float)):
            self.zero=motion['yaw_deg']
        self.draw_debug()

    def update(self,row,live):
        fresh=bool(live and row and time.monotonic()-row.get('published_monotonic',0)<1.5)
        self.snapshot=row['spatial'] if fresh else {}
        value=self.snapshot;canvas=self.canvas;canvas.delete('all')
        width=max(200,canvas.winfo_width());cx,cy=width/2,88;r=65
        canvas.create_arc(cx-r,cy-r,cx+r,cy+r,start=0,extent=180,style='arc',outline='#64717a')
        canvas.create_line(cx-r,cy,cx+r,cy,fill='#64717a')
        canvas.create_text(cx,8,text='90° front / rear ambiguity',fill='#e5e9ef')
        canvas.create_text(cx-r-18,cy,text='180°',fill='#e5e9ef')
        canvas.create_text(cx+r+18,cy,text='0°',fill='#e5e9ef')
        canvas.create_rectangle(cx-9,cy-14,cx+9,cy+14,outline='#e5e9ef')
        # Provider angles already implement the retained mounting/calibration.
        # The retained linear-array view maps0 right,90 front/rear,180 left.
        if value.get('coordinate_frame')=='device':
            for arrow in value.get('arrows',[]):
                angle=arrow.get('angle_deg')
                if not isinstance(angle,(int,float)) or not math.isfinite(angle) or not 0<=angle<=180:continue
                color='#70d7ac' if arrow.get('fresh') else '#66717a'
                canvas.create_line(cx,cy,*device_tip(angle,cx,cy,r),fill=color,
                    width=3 if arrow.get('selected') else 1,arrow='last',dash=() if arrow.get('fresh') else (3,3))
            for association in value.get('associations',[]):
                angle=association.get('angle_deg')
                if value.get('association_reference_frame')=='device' and isinstance(angle,(int,float)) and math.isfinite(angle) and 0<=angle<=180:
                    canvas.create_text(*device_tip(angle,cx,cy,r+14),
                        text='≈ '+str(association.get('label') or 'Speaker')[:24],fill='#e5bf74',font=('Sans',9))
            if value.get('association_reference_frame')!='device' and value.get('associations'):
                labels=', '.join(str(row.get('label') or 'Speaker')[:24] for row in value['associations'][:4])
                canvas.create_text(cx,140,text='Voice matches: '+labels+'\nLocations estimated in the relative anchor frame',
                    width=width-20,fill='#e5bf74',font=('Sans',9))
        message=value.get('message') if fresh else ('Direction unavailable or waiting for live source.' if live else 'Saved/idle: current motion does not change recorded directions.')
        self.message.configure(text=message or 'Direction state unavailable.')
        self.draw_debug()

    def draw_debug(self):
        if not self.debug:return
        canvas=self.debug_canvas;canvas.delete('all');motion=self.snapshot.get('motion') or {}
        valid=motion.get('valid') is True and isinstance(motion.get('yaw_deg'),(int,float))
        angle=math.radians(-(motion.get('yaw_deg',0)-self.zero)) if valid else 0
        c,s=math.cos(angle),math.sin(angle);cx=max(200,canvas.winfo_width())/2
        def point(x,y):return cx+x*c-y*s,40+x*s+y*c
        corners=[point(x,y) for x,y in ((-14,-23),(14,-23),(14,23),(-14,23))]
        color='#70d7ac' if valid else '#999999'
        canvas.create_polygon(*[v for pair in corners for v in pair],outline=color,fill='',width=2)
        if valid:canvas.create_line(*point(0,14),*point(0,-17),fill=color,width=2,arrow='last')
        canvas.create_text(cx,83,text=str(motion.get('state','WAITING')) if valid else 'NOT READY',fill=color)
        canvas.create_text(cx,100,text='Tap: visual zero only',fill='#dddddd')
