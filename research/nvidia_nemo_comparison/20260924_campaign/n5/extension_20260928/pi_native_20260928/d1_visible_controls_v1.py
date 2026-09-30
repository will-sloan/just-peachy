"""Visible mode chooser and installed preview controls; README_D1_VISIBLE_ENTRY_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import tkinter as tk

LABELS={'streaming':'Streaming','chunk52':'Chunk52 (experimental)','delayed':'Delayed'}
NOTES={'streaming':'Earlier labels; higher compute cost.',
       'chunk52':'Intermediate buffering; field validation pending.',
       'delayed':'Lower compute cost; labels arrive later.'}


def visible(root):
    root.geometry('480x800+0+0');root.attributes('-fullscreen',True)
    root.deiconify();root.lift();root.update()


def check_box(root,widget):
    root.update_idletasks()
    x,y=widget.winfo_rootx()-root.winfo_rootx(),widget.winfo_rooty()-root.winfo_rooty()
    w,h=widget.winfo_width(),widget.winfo_height()
    assert widget.winfo_viewable() and x>=0 and y>=0 and x+w<=480 and y+h<=800,(widget,x,y,w,h)
    return dict(x=x,y=y,width=w,height=h)


class ModePage:
    """UI actions are callbacks; protocol observation is separate from the page."""
    def __init__(self,root,choose,open_selected,close):
        self.root=root;root.configure(bg='#171d1b');root.title('Just Peachy - diarizer modes')
        root.protocol('WM_DELETE_WINDOW',close)
        body=tk.Frame(root,bg='#171d1b');body.pack(fill='both',expand=True,padx=24,pady=24)
        def label(text,size=18,color='#f5f4ec'):
            item=tk.Label(body,text=text,bg='#171d1b',fg=color,font=('DejaVu Sans',-size),justify='left',anchor='w',wraplength=428)
            item.pack(fill='x',pady=(0,12));return item
        label('Just Peachy',27);label('Nemotron diarizer',23)
        label('CONTROLS PREVIEW  |  MICROPHONE OFF',14,'#f4b797')
        self.buttons={}
        for mode in LABELS:
            button=tk.Button(body,text=LABELS[mode]+'\n'+NOTES[mode],command=lambda m=mode:choose(m),
                font=('DejaVu Sans',-18),bg='#293631',fg='#f5f4ec',activebackground='#49604f',
                activeforeground='#ffffff',relief='flat',wraplength=410,justify='left',anchor='w',padx=14,pady=10)
            button.pack(fill='x',pady=(0,10));self.buttons[mode]=button
        self.status=label('Select a mode to inspect its controls.\nLive recording is unavailable in this preview.',17)
        self.open=tk.Button(body,text='Open selected controls',command=open_selected,state='disabled',
            font=('DejaVu Sans',-19),bg='#f4b797',fg='#151a17',relief='flat',pady=12)
        self.open.pack(fill='x',pady=(0,12))
        self.close=tk.Button(body,text='Close preview',command=close,font=('DejaVu Sans',-18),
            bg='#293631',fg='#f5f4ec',relief='flat',pady=12);self.close.pack(fill='x')
    def selected(self,mode,can_open):
        self.status.config(text=LABELS[mode]+' selected.\n'+('Inspect controls only; model Start is disabled.' if can_open else 'Separate saved test passed. This preview opens Streaming only.'))
        self.open.config(state='normal' if can_open else 'disabled')
    def active(self):
        self.open.config(state='disabled')
        for b in self.buttons.values():b.config(state='disabled')
        self.root.withdraw()
    def returned(self):
        self.status.config(text='Controls closed safely.\nThis preview session is complete; microphone remained off.')
        self.open.config(state='disabled');visible(self.root)
    def rectangles(self):
        return {name:check_box(self.root,w) for name,w in {**self.buttons,'status':self.status,'open':self.open,'close':self.close}.items()}


def preview_ui(Base,mode):
    class Preview(Base):
        def _show_status(self):
            super()._show_status()
            self.mode_label.config(text='Nemotron D1 / '+LABELS[mode])
            self.status_label.config(text='Controls preview - microphone off')
            for key in ('start_stop','mode','people','settings','rescue','backend'):
                if key in self.actions:self.actions[key].config(state='disabled')
        def show_preview(self):
            self.page='d1_preview'
            body=self._page('Diarizer controls',scroll=False,back=self.close)
            self.label(body,LABELS[mode],size=23,bold=True).pack(fill='x',padx=12,pady=10)
            self.label(body,NOTES[mode]+'\nSaved native passages passed. Live recording is not enabled.',size=18).pack(fill='x',padx=12,pady=8)
            self.preview_notice=self.label(body,'Inspection only. Model Start requires a separate guarded run.',size=18)
            self.preview_notice.pack(fill='x',padx=12,pady=10)
            self.preview_start=self.button(body,'Start model - unavailable in preview',lambda:None,height=52)
            self.preview_start.pack(fill='x',padx=12,pady=8);self.preview_start.button.config(state='disabled')
            self.preview_close=self.button(body,'Return to mode chooser',self.close,height=56,accent=True)
            self.preview_close.pack(fill='x',padx=12,pady=10)
            self._page_update=lambda:None
    return Preview


def snapshot(root,name,images,metadata):
    """Bound compositor PNG capture; transient grim owner and natural reap recorded."""
    root.update();assert root.winfo_viewable() and root.winfo_geometry()=='480x800+0+0'
    proc=subprocess.Popen(['grim','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    owner=dict(pid=proc.pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        start_ticks=int(Path('/proc',str(proc.pid),'stat').read_text().rsplit(')',1)[1].split()[19]))
    metadata.json(name+'-OWNER.json',owner)
    os.set_blocking(proc.stdout.fileno(),False);os.set_blocking(proc.stderr.fileno(),False)
    data=bytearray();errors=bytearray();began=time.monotonic()
    try:
        while proc.poll() is None:
            data.extend(proc.stdout.read(16384) or b'');errors.extend(proc.stderr.read(4096) or b'')
            if len(data)>256*1024 or len(errors)>4096 or time.monotonic()-began>8:
                raise RuntimeError('Screenshot byte/time ceiling exceeded')
            time.sleep(.005)
        data.extend(proc.stdout.read(256*1024+1-len(data)) or b'');errors.extend(proc.stderr.read(4097-len(errors)) or b'')
        assert proc.returncode==0 and len(data)<=256*1024 and not errors
        assert data[:8]==b'\x89PNG\r\n\x1a\n' and int.from_bytes(data[16:20],'big')==480 and int.from_bytes(data[20:24],'big')==800
        images.write(name+'.png',bytes(data))
        return dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),geometry=root.winfo_geometry(),
            compositor_capture=True,physical_touch=False,owner=owner,returncode=proc.returncode)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=1)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=1)
        proc.stdout.close();proc.stderr.close()
