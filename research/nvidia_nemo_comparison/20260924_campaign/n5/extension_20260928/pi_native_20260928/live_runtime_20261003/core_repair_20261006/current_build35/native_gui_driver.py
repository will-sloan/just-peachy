"""Native real-Tk programmatic integration driver. README_NATIVE_GUI_DRIVER.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import time


WORKFLOWS = ('inspect', 'capture-discard', 'capture-save-replay-discard', 'replay-discard')


def validate_plan(selection, workflow, stop_seconds, saved_path=None, saved_session_id=None, *, stop_mode="button", save_raw=False):
    """Pure UI contract validation; imports neither Tk nor a model."""
    if workflow not in WORKFLOWS or type(stop_seconds) not in (int,float) or not 0 < stop_seconds <= 300:
        raise ValueError('Known finite GUI workflow and0-300 second Stop boundary required')
    from profiles import RuntimeSelection
    chosen = RuntimeSelection(**selection).validate()
    if stop_mode not in ('button','policy') or type(save_raw) is not bool:
        raise ValueError('Explicit GUI Stop mode and raw-save flag required')
    if stop_mode=='policy' and (stop_seconds!=300 or chosen['input_source']!='live' or not workflow.startswith('capture-')):
        raise ValueError('Policy autoStop qualification requires actual live300s capture')
    if save_raw and (workflow!='capture-save-replay-discard' or chosen['input_source']!='live'):
        raise ValueError('Save raw requires qualified live capture-save-replay-discard')
    if chosen['provisional_correction'] or chosen['refinement_profile']!='current_delayed' or chosen['refinement_period_seconds']!=5:
        raise ValueError('Only controls exposed by the actual GUI may be selected')
    if chosen['speaker_attribution']=='retained' and not chosen.get('optional_d1_refiner') and chosen['revision_window_seconds']!=30:
        raise ValueError('Retained attribution has no editable revision-window GUI control')
    if workflow.startswith('capture-') and chosen['input_source']=='saved' and not saved_path:
        raise ValueError('Saved-file Start workflow requires the pinned saved WAV')
    if workflow=='replay-discard' and (chosen['input_source']!='saved' or not saved_session_id or saved_path):
        raise ValueError('History replay workflow requires only its selected kept session')
    if chosen['input_source']=='live' and saved_path:
        raise ValueError('Live GUI workflow cannot inject saved-file input')
    return chosen


def require_closed(closure):
    """Disposition cannot be authorized by a merely requested Stop."""
    result = (closure or {}).get('result') or {}
    if (not closure or closure.get('returncode')!=0 or closure.get('direct_child_reaped') is not True
        or closure.get('stdout_reader_joined') is not True or closure.get('output_error')
        or closure.get('receipt_errors') or closure.get('nested_source',{}).get('closed') is not True
        or not result.get('session_id') or result.get('failure')):
        raise RuntimeError('Successful exact worker/source closure required before disposition')
    return result['session_id']


def require_policy_boundary(metadata,driver_stop_calls):
    if (metadata.get('processed_samples')!=300*16000 or driver_stop_calls!=0 or
        metadata.get('status')!='stopped' or metadata.get('spec',{}).get('duration_seconds')!=300):
        raise RuntimeError('AutoStop must prove actual4800000 samples and successful ordinary policy closure, without injected Stop')
    return metadata['processed_samples']


def require_kept_choice(metadata,save_raw):
    if metadata.get('status')!='kept' or metadata.get('include_raw') is not save_raw:
        raise RuntimeError('Actual Save did not retain the explicit raw/processed choice')
    if save_raw:
        raw=metadata.get('spec',{}).get('raw',{})
        if (metadata['spec'].get('mode')!='raw_processed' or raw.get('qualification',{}).get('qualified') is not True or
            metadata.get('raw_samples',0)<=0 or metadata['raw_samples']*metadata['spec']['sample_rate']!=metadata['processed_samples']*raw['sample_rate']):
            raise RuntimeError('Kept raw must be qualified and exactly align with complete processed clock')
    return metadata


def widgets(root):
    pending = [root]; result = []
    while pending:
        widget = pending.pop(0); result.append(widget)
        if len(result)>256:
            raise ValueError('GUI widget inventory bound')
        pending.extend(widget.winfo_children())
    return result


def named_widget(root, text, classes=('TButton',)):
    found = []
    for widget in widgets(root):
        if widget.winfo_class() in classes and str(widget.cget('text'))==text:
            found.append(widget)
    if len(found)!=1:
        raise ValueError('Unique actual GUI widget required: '+text)
    return found[0]


def labeled_control(root, label, kind):
    heading = named_widget(root,label,('TLabel','Label'))
    siblings = heading.master.winfo_children()
    index = siblings.index(heading)
    if index+1==len(siblings) or siblings[index+1].winfo_class()!=kind:
        raise ValueError('Actual label/control relationship changed: '+label)
    return siblings[index+1]


class GuiDriver:
    def __init__(self, manager, plan, workflow, stop_seconds, output, publish, *, saved_path=None,
                 saved_session_id=None, deadline=None, stop_mode="button", save_raw=False):
        self.manager,self.plan,self.workflow = manager,plan,workflow
        self.stop_seconds,self.output,self.publish = stop_seconds,output,publish
        self.saved_path,self.saved_session_id = saved_path,saved_session_id
        self.deadline = deadline
        self.stop_mode,self.save_raw=stop_mode,save_raw
        self.policy_boundary_observed=False
        self.target_boundary_observed=False
        self.replay_completed=False
        self.kept_audio=None
        self.root = None
        self.stage = 'created'
        self.failure = None
        self.actions = 0
        self.sessions = []
        self.original_id = saved_session_id
        self.first_closure = self.replay_closure = None
        self.exited = False
        self.pending_at = None
        self.stop_invoked = False
        self.stop_calls = 0
        self.geometry_samples = []
        self.spatial_started = None
        self.spatial_checked = False

    def record(self, kind, **value):
        self.actions += 1
        if self.actions>256:
            raise ValueError('Finite GUI action receipt allocation exhausted')
        row=dict(kind=kind,monotonic=time.monotonic(),stage=self.stage,programmatic=True,physical_touch=False,**value)
        if len(json.dumps(row,allow_nan=False).encode())>65536:
            raise ValueError('Finite64KiB GUI action receipt required')
        self.publish(self.output/('%03d-%s.json'%(self.actions,kind)),row)

    def invoke(self, text):
        button = named_widget(self.root,text)
        self.reveal(button)
        if 'disabled' in button.state():
            raise RuntimeError('Actual GUI button is disabled: '+text)
        self.record('invoke',text=text,path=str(button),visible=bool(button.winfo_viewable()))
        if text=='Stop':self.stop_calls+=1
        button.invoke()

    def choose(self, label, value, kind='TCombobox'):
        control = labeled_control(self.root,label,kind)
        self.reveal(control)
        if kind=='TCombobox':
            choices = tuple(control.tk.splitlist(control.cget('values')))
            if value not in choices:
                raise ValueError('Requested value absent from actual GUI: '+label)
            before = control.get(); control.set(value)
            control.event_generate('<<ComboboxSelected>>')
        else:
            before = control.get(); control.delete(0,'end'); control.insert(0,str(value))
        self.record('select',label=label,before=before,after=control.get(),path=str(control))

    def reveal(self,widget):
        node=widget;body=None;tab=None
        while node is not None:
            if hasattr(node,'_scroll_viewport'):body=node
            parent=getattr(node,'master',None)
            if parent is not None and parent.winfo_class()=='TNotebook':tab=node;break
            node=parent
        if tab is not None:tab.master.select(tab)
        self.root.update_idletasks()
        if body is not None:
            canvas=body._scroll_viewport
            relative=widget.winfo_rooty()-body.winfo_rooty()
            canvas.yview_moveto(max(0,(relative-canvas.winfo_height()*.25)/max(1,body.winfo_height())))
            self.root.update_idletasks()
            top=widget.winfo_rooty();bottom=top+widget.winfo_height()
            if top<canvas.winfo_rooty() or bottom>canvas.winfo_rooty()+canvas.winfo_height():
                raise RuntimeError('Actual control cannot scroll wholly into the visible tablet viewport')
            self.record('scroll-visible',widget=str(widget),top=top,bottom=bottom,viewport_y=canvas.winfo_rooty(),
                        viewport_height=canvas.winfo_height(),scroll_fraction=list(canvas.yview()))

    def attach(self, root):
        self.root = root
        root.report_callback_exception = lambda typ,value,tb:self.abort(repr(value))
        self.geometry_deadline = time.monotonic()+10
        root.after(150,self.check_geometry)

    def check_geometry(self):
        try:
            self.root.update_idletasks()
            extent=[self.root.winfo_width(),self.root.winfo_height(),self.root.winfo_rootx(),self.root.winfo_rooty()]
            full=bool(self.root.tk.getboolean(self.root.attributes('-fullscreen')))
            stable=extent==[480,800,0,0] and full and bool(self.root.winfo_viewable())
            if stable:
                self.geometry_samples.append(dict(monotonic=time.monotonic(),extent=extent,fullscreen=full))
            else:
                self.geometry_samples=[]
            if len(self.geometry_samples)==10:
                self.record('stable-geometry',samples=self.geometry_samples,interval_seconds=.1,
                    physical_touch_tested=False,visual_quality_qualified=False)
                self.configure()
            elif time.monotonic()>=self.geometry_deadline:
                raise RuntimeError('Actual fullscreen480x800+0+0 did not stabilize for10 consecutive checks')
            else:self.root.after(100,self.check_geometry)
        except BaseException as error:self.abort(repr(error))

    def configure(self):
        try:
            self.root.update_idletasks()
            dimensions=(self.root.winfo_width(),self.root.winfo_height())
            self.record('geometry',geometry=self.root.geometry(),dimensions=dimensions,
                requested=[480,800],screen=[self.root.winfo_screenwidth(),self.root.winfo_screenheight()],
                viewable=bool(self.root.winfo_viewable()))
            if dimensions!=(480,800) or not self.root.winfo_viewable():
                raise RuntimeError('Actual mapped Tk client must measure480x800')
            for label,key in (('Diarizer','diarizer'),('Speaker embedding','embedding'),('Input','input_source')):
                self.choose(label,self.plan[key])
            preset=labeled_control(self.root,'Nemotron preset','TCombobox')
            if self.plan['diarizer']=='nemotron':
                if 'disabled' in preset.state():raise RuntimeError('Selected Nemotron preset is disabled')
                self.choose('Nemotron preset',self.plan['nemotron_profile'])
            elif 'disabled' not in preset.state() or preset.get():
                raise RuntimeError('Pyannote must visibly disable and clear Nemotron preset')
            checkbox=named_widget(self.root,'Enable experimental configurations',('TCheckbutton',))
            if bool(checkbox.instate(('selected',)))!=self.plan['allow_experimental']:
                self.record('invoke',text='Enable experimental configurations',path=str(checkbox));checkbox.invoke()
            self.choose('Named speaker embedding schedule (experimental Nemotron only)',self.plan['embedding_schedule'])
            self.choose('Sparse refresh interval in seconds (0.5-120)',self.plan['embedding_refresh_seconds'],'TEntry')
            self.choose('Speaker attribution (late labels: experimental Nemotron)',self.plan['speaker_attribution'])
            matches=[item for item in widgets(self.root) if item.winfo_class()=='TCheckbutton' and
                str(item.cget('text')).startswith('Optional anonymous CurrentDelayed refiner:')]
            if len(matches)!=1:raise RuntimeError('One explicit optional refiner control required')
            optional=matches[0]
            reviewed='reviewed combined admission available' in str(optional.cget('text'))
            if reviewed != ('disabled' not in optional.state()):raise RuntimeError('Optional control eligibility label/state mismatch')
            if self.plan.get('optional_d1_refiner'):
                if not reviewed:raise RuntimeError('Exact reviewed optional combination remains unavailable')
                if not optional.instate(('selected',)):optional.invoke()
            elif optional.instate(('selected',)):raise RuntimeError('Default optional capture must remain off')
            revision=labeled_control(self.root,'Label revision window in seconds (1-300)','TEntry')
            if self.plan['speaker_attribution']=='single_d1_late_labels' or self.plan.get('optional_d1_refiner'):
                if 'disabled' in revision.state():raise RuntimeError('Late-label revision control is disabled')
                self.choose('Label revision window in seconds (1-300)',self.plan['revision_window_seconds'],'TEntry')
            elif 'disabled' not in revision.state() or int(revision.get())!=self.plan['revision_window_seconds']:
                raise RuntimeError('Unused revision control must be disabled with the requested retained value')
            provisional=named_widget(self.root,'Provisional/correction: native admission pending',('TCheckbutton',))
            if 'disabled' not in provisional.state():
                raise RuntimeError('Unadmitted provisional control is unexpectedly enabled')
            inventory=[]
            for item in widgets(self.root):
                row=dict(path=str(item),kind=item.winfo_class(),viewable=bool(item.winfo_viewable()))
                if item.winfo_class() in ('TButton','TLabel','TCheckbutton'):
                    row['text']=str(item.cget('text'))
                inventory.append(row)
            self.record('widgets',items=inventory)
            if self.workflow=='inspect':
                for name in ('Start','Save processed','Discard audio','Orientation graphic · show / hide'):
                    self.reveal(named_widget(self.root,name))
                self.invoke('Orientation graphic · show / hide')
                self.reveal(named_widget(self.root,'Recenter orientation graphic (visual only)'))
                self.invoke('Recenter orientation graphic (visual only)')
                self.invoke('Orientation graphic · show / hide')
                self.stage='inspection-complete';self.exit();return
            if self.workflow=='replay-discard':
                self.begin_replay()
            else:
                if self.saved_path:self.invoke('Choose saved WAV...')
                self.stage='first-running';self.invoke('Start');self.check_request()
            self.root.after(200,self.tick)
        except BaseException as error:
            self.abort(repr(error))

    def check_request(self):
        if self.manager.process is None:
            raise RuntimeError('Actual Start did not create an authorized worker')
        expected=dict(self.plan)
        if self.stage=='replay-running':expected['input_source']='saved'
        from profiles import SessionPolicy
        if self.manager.request.get('policy')!=SessionPolicy().validate():
            raise RuntimeError('Actual GUI must use unchanged ordinary300s policy')
        if self.manager.request['selection']!=expected:
            raise RuntimeError('Actual GUI request differs from selected controls')
        self.record('worker-started',request=self.manager.request,launch_root=str(self.manager.run_dir))
        self.stop_invoked=False

    def begin_replay(self):
        tree=next(item for item in widgets(self.root) if item.winfo_class()=='Treeview')
        book=next(item for item in widgets(self.root) if item.winfo_class()=='TNotebook')
        tabs=[tab for tab in book.tabs() if book.tab(tab,'text')=='Recordings']
        if len(tabs)!=1:raise ValueError('Actual Recordings tab required')
        book.select(tabs[0]);self.invoke('Refresh')
        for page in range(128):
            if self.original_id in tree.get_children():break
            previous=tree.get_children();self.invoke('Older')
            if not tree.get_children() or tree.get_children()==previous:raise ValueError('Selected kept session is absent from bounded History pages')
        else:raise ValueError('History page bound exceeded')
        metadata=self.manager.store.read(self.original_id)
        if metadata['status']!='kept':raise ValueError('Replay selection is not kept')
        self.replay_frames=metadata['processed_samples']
        tree.selection_set(self.original_id);tree.focus(self.original_id)
        self.record('history-selection',session_id=self.original_id,frames=self.replay_frames,page=page)
        self.stage='replay-running';self.invoke('Replay recording');self.check_request()
        if self.manager.request.get('saved_session_id')!=self.original_id:
            raise RuntimeError('History did not request the full selected recording')

    def tick(self):
        try:
            if self.stage!='aborting' and self.deadline is not None and time.monotonic()>=self.deadline:
                raise TimeoutError('GUI driver deadline reached; external service backstop remains armed')
            closure=self.manager.poll()
            if self.stage=='aborting':
                if self.manager.process is None:self.exit();return
            elif self.stage in ('first-running','replay-running'):
                identifier=self.manager.active_session_id()
                if identifier and self.manager.process is not None:
                    row=self.manager.store.read(identifier)
                    target=self.replay_frames if self.stage=='replay-running' else int(self.stop_seconds*16000)
                    if self.stage=='first-running' and self.plan['input_source']=='live' and row['processed_samples']>=16000 and not self.spatial_checked:
                        if self.spatial_started is None:
                            self.invoke('Orientation graphic · show / hide')
                            self.reveal(named_widget(self.root,'Recenter orientation graphic (visual only)'))
                            self.spatial_started=time.monotonic()
                        snapshot=self.manager.latest_spatial
                        view=(snapshot or {}).get('spatial',{})
                        if view.get('motion',{}).get('valid') is True and view.get('coordinate_frame')=='device' and view.get('arrows'):
                            self.record('live-spatial',snapshot=snapshot,extra_hardware_reads=False,calibration_changed=False)
                            self.invoke('Recenter orientation graphic (visual only)')
                            self.invoke('Orientation graphic · show / hide')
                            self.spatial_checked=True
                        elif time.monotonic()-self.spatial_started>5:
                            raise RuntimeError('Actual cached device direction and valid motion did not reach visible controls')
                    if self.stage=='first-running' and row['processed_samples']>=target and not self.target_boundary_observed:
                        self.record('stop-boundary',session_id=identifier,committed_samples=row['processed_samples'],target_samples=target,stop_mode=self.stop_mode)
                        self.target_boundary_observed=True
                        if self.stop_mode=='button':
                            self.invoke('Stop');self.stop_invoked=True
                if closure is not None and self.manager.process is None:
                    if self.stage=='first-running' and self.stop_mode=='button' and not self.stop_invoked:
                        raise RuntimeError('First source ended before the planned actual Stop invocation')
                    if self.stage=='first-running' and self.plan['input_source']=='live' and not self.spatial_checked:
                        raise RuntimeError('Live GUI workflow ended before direction/orientation controls were verified')
                    identifier=require_closed(closure)
                    actual=self.manager.store.read(identifier)
                    if self.stage=='first-running' and self.stop_mode=='policy':
                        require_policy_boundary(actual,self.stop_calls)
                        self.policy_boundary_observed=True
                        self.record('policy-auto-stop-verified',session_id=identifier,actual_processed_samples=actual['processed_samples'],driver_stop_invocations=self.stop_calls)
                    self.sessions.append(identifier)
                    self.record('closed',session_id=identifier,closure=closure)
                    self.completed_stage=self.stage
                    self.stage='closed-awaiting-ui';self.pending_at=time.monotonic()+.75
            elif self.stage=='closed-awaiting-ui' and time.monotonic()>=self.pending_at:
                # Give the launcher's own500ms observer a turn to render this
                # exact closed session before invoking its disposition button.
                identifier=self.sessions[-1]
                if self.completed_stage=='first-running' and self.workflow=='capture-save-replay-discard':
                    before=self.manager.store.read(identifier)
                    if self.save_raw and (before['spec']['mode']!='raw_processed' or before['spec'].get('raw',{}).get('qualification',{}).get('qualified') is not True):
                        raise RuntimeError('Save raw requires actual qualified raw recording')
                    self.invoke('Save raw + processed' if self.save_raw else 'Save processed')
                    kept=self.manager.store.read(identifier)
                    require_kept_choice(kept,self.save_raw)
                    self.kept_audio={key:kept[key] for key in ('processed_samples','raw_samples','include_raw')}
                    self.record('kept-choice',session_id=identifier,raw_requested=self.save_raw,actual=self.kept_audio)
                    self.original_id=identifier;self.begin_replay()
                else:
                    if self.completed_stage=='replay-running' and self.manager.store.read(identifier)['processed_samples']!=self.replay_frames:
                        raise RuntimeError('GUI replay did not consume the entire original recording')
                    if self.completed_stage=='replay-running':self.replay_completed=True
                    self.invoke('Discard audio')
                    if self.manager.store.read(identifier)['status']!='discarded':raise RuntimeError('Actual Discard did not complete')
                    if self.original_id:
                        original=self.manager.store.read(self.original_id)
                        if original['status']!='kept' or (self.kept_audio is not None and any(original[key]!=value for key,value in self.kept_audio.items())):
                            raise RuntimeError('Replay modified the original kept recording or raw-save choice')
                    self.stage='workflow-complete';self.exit();return
            if not self.exited:self.root.after(200,self.tick)
        except BaseException as error:
            self.abort(repr(error))

    def consent(self, title, message, **kwargs):
        if title!='Temporary audio' or not self.workflow.startswith('capture-') or self.plan['input_source']!='live':
            self.abort('Unexpected consent dialog: '+str(title));return False
        self.record('consent',title=title,message=message,answer=True,
            authorization='existing user authorization for this pinned workflow')
        return True

    def choose_file(self, **kwargs):
        if not self.saved_path:
            self.abort('Unexpected saved-file dialog');return ''
        self.record('file-choice',path=str(self.saved_path));return str(self.saved_path)

    def abort(self, error):
        if self.failure is None:
            self.failure=error;self.record('failure',error=error)
        self.stage='aborting'
        if self.manager.process is not None:
            self.manager.stop();self.root.after(200,self.tick)
        elif self.root is not None and not self.exited:self.exit()

    def exit(self):
        if self.manager.process is not None:
            raise RuntimeError('GUI exit cannot precede worker/source closure')
        self.invoke('Exit to desktop')
        if not self.manager.closed:
            raise RuntimeError('Actual Exit did not close the manager')
        self.exited=True


def display_state(output, name, publish):
    """Read current orientation; never set a transform or desktop property."""
    import subprocess
    command=['wlr-randr']
    result=subprocess.run(command,capture_output=True,text=True,timeout=8)
    if len(result.stdout)+len(result.stderr)>32768:
        raise ValueError('Display inspection output bound')
    row=dict(command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
             read_only=True,display_mutated=False)
    publish(output/name,row)
    if result.returncode or 'Enabled: yes' not in result.stdout or 'Transform: 270' not in result.stdout:
        raise RuntimeError('Existing enabled270-degree desktop must be preserved before GUI work')
    return row


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binding',type=Path,required=True)
    ap.add_argument('--package-manifest-sha256',required=True)
    ap.add_argument('--unit',required=True)
    ap.add_argument('--unit-ownership',type=Path,required=True)
    ap.add_argument('--owner-directory',type=Path,required=True)
    ap.add_argument('--data-root',type=Path,required=True)
    ap.add_argument('--selection',type=Path,required=True)
    ap.add_argument('--selection-sha256',required=True)
    ap.add_argument('--workflow',choices=WORKFLOWS,default='inspect')
    ap.add_argument('--stop-after-seconds',type=float,default=5)
    ap.add_argument('--stop-mode',choices=('button','policy'),default='button')
    ap.add_argument('--save-raw',action='store_true')
    ap.add_argument('--saved-path',type=Path)
    ap.add_argument('--saved-sha256')
    ap.add_argument('--saved-session-id')
    args=ap.parse_args()
    if platform.system()!='Linux' or platform.machine()!='aarch64':
        raise RuntimeError('Native GUI driver cannot open a PC window or construct PC models')
    # Outer owned wrapper must register before reading this entrypoint. This
    # secondary actual owner receipt precedes all further project imports.
    os.sched_setaffinity(0,{3})
    import resource
    for kind,ceiling in ((resource.RLIMIT_AS,768*1024**2),(resource.RLIMIT_STACK,1024**2)):
        soft,hard=resource.getrlimit(kind)
        if soft<=0 or hard<=0 or soft>ceiling or hard>ceiling:
            raise RuntimeError('GUI driver requires the reviewed finite native resource wrapper')
    if resource.getrlimit(resource.RLIMIT_FSIZE)[1] in (0,resource.RLIM_INFINITY):
        raise RuntimeError('GUI driver requires a finite positive per-file allowance')
    args.owner_directory.mkdir(exist_ok=False)
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    with (args.owner_directory/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(owner,stream);stream.flush();os.fsync(stream.fileno())
    sys.dont_write_bytecode=True
    from native_scope import verified_inventory
    from runtime_support import publish,strict,digest,verify_owned_unit
    package=Path(__file__).resolve().parent
    verified_inventory(package,args.package_manifest_sha256)
    if args.binding!=package/'BINDING.json':raise ValueError('Exact package binding required')
    unit=verify_owned_unit(args.unit,args.unit_ownership)
    unit_receipt=strict(args.unit_ownership.read_bytes())
    deadline=unit_receipt.get('deadline_monotonic')
    if type(deadline) not in (int,float) or deadline-time.monotonic()<60:
        raise ValueError('Finite verified GUI unit lifetime required')
    if args.selection.stat().st_size>65536 or digest(args.selection)!=args.selection_sha256:
        raise ValueError('Pinned bounded GUI selection required')
    plan=validate_plan(strict(args.selection.read_bytes()),args.workflow,args.stop_after_seconds,args.saved_path,args.saved_session_id,stop_mode=args.stop_mode,save_raw=args.save_raw)
    if args.saved_path and (not args.saved_sha256 or digest(args.saved_path)!=args.saved_sha256):
        raise ValueError('Exact saved GUI input required')
    before=display_state(args.owner_directory,'DISPLAY_BEFORE.json',publish)
    import tkinter as tk
    from tkinter import filedialog,messagebox
    import launcher
    manager=launcher.Manager(args.binding,args.data_root,args.unit,unit_ownership=args.unit_ownership)
    driver=GuiDriver(manager,plan,args.workflow,args.stop_after_seconds,args.owner_directory,publish,
        saved_path=args.saved_path,saved_session_id=args.saved_session_id,deadline=deadline-30,stop_mode=args.stop_mode,save_raw=args.save_raw)
    original_tk=tk.Tk;dialogs=(messagebox.askokcancel,messagebox.showerror,filedialog.askopenfilename)
    class ObservedTk(original_tk):
        def mainloop(self,*pos,**kw):
            driver.attach(self)
            return super().mainloop(*pos,**kw)
    tk.Tk=ObservedTk
    messagebox.askokcancel=driver.consent
    messagebox.showerror=lambda title,message,**kwargs:driver.abort('Actual GUI error '+str(title)+': '+str(message))
    filedialog.askopenfilename=driver.choose_file
    try:
        launcher.show(manager)
    finally:
        tk.Tk=original_tk
        messagebox.askokcancel,messagebox.showerror,filedialog.askopenfilename=dialogs
        if manager.process is None and not manager.closed:manager.close()
    after=display_state(args.owner_directory,'DISPLAY_AFTER.json',publish)
    result=dict(status='GUI_PROGRAMMATIC_CHECK_PASSED' if driver.exited and not driver.failure else 'GUI_PROGRAMMATIC_CHECK_FAILED',
        owner=owner,unit=unit,workflow=args.workflow,selection=plan,actions=driver.actions,sessions=driver.sessions,
        failure=driver.failure,actual_tk=True,requested_geometry=[480,800],exit_to_desktop_invoked=driver.exited,
        desktop_orientation_preserved=before['stdout']==after['stdout'],physical_touch_tested=False,
        native_model_sessions=len(driver.sessions),inspection_only=args.workflow=='inspect',
        stop_button_invocations=driver.stop_calls,stop_mode=driver.stop_mode,save_raw_requested=driver.save_raw,
        policy_boundary_observed=driver.policy_boundary_observed,kept_audio=driver.kept_audio,
        replay_waited_for_natural_eof=driver.replay_completed,target_boundary_observed=driver.target_boundary_observed,
        stable_fullscreen_geometry_checks=len(driver.geometry_samples),
        live_direction_orientation_checked=driver.spatial_checked,
        screenshot_captured=False,visual_quality_qualified=False)
    publish(args.owner_directory/'GUI_RESULT.json',result)
    return 0 if result['status']=='GUI_PROGRAMMATIC_CHECK_PASSED' and result['desktop_orientation_preserved'] else 1


if __name__=='__main__':raise SystemExit(main())
