"""Opt-in saved-file desktop prototype. See README.md. No live input or audio playback."""
import argparse,hashlib,importlib,json,logging,logging.handlers,os,sys,time,wave
from pathlib import Path

MODES={"caption_only":"M0","open_conversation":"M1","open_with_names":"M2","selected_emphasis":"M3"}
def need(ok,message):
    if not ok:raise ValueError(message)
def binding(p):
    p=Path(p).resolve();h=hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def load_config(path,full_assets=False):
    path=path.resolve();doc=json.loads(path.read_text(encoding="utf-8-sig"))
    need(set(doc)=={"schema","source_root","source_files","assets","profiles","gallery","language","limits"},"Unknown/missing configuration field")
    need(doc["schema"]=="just-peachy.desktop.s7.v1" and doc["language"]=="en","Unsupported schema or language")
    def resolve(value):return (path.parent/Path(value)).resolve()
    doc["source_root"]=str(resolve(doc["source_root"]))
    for row in doc["source_files"]:
        p=(Path(doc["source_root"])/row["relative_path"]).resolve()
        need(p.is_relative_to(Path(doc["source_root"])) and p.is_file(),"Invalid source file")
        need(binding(p)["sha256"]==row["sha256"],"Source integrity mismatch: "+str(p))
    need(len(doc["assets"])==8 and len({a["component_id"] for a in doc["assets"]})==8,"Exactly eight distinct assets required")
    for asset in doc["assets"]:
        asset["path"]=str(resolve(asset["path"]));p=Path(asset["path"])
        need(p.is_file(),"Missing model asset: "+str(p))
        if full_assets:need(binding(p)["sha256"]==asset["sha256"],"Model asset hash mismatch")
    doc["gallery"]=str(resolve(doc["gallery"]))
    need(set(doc["profiles"])=={"C065","C088"},"Exact two supported profile families required")
    need(set(doc["limits"])=={"maximum_file_seconds","diagnostic_file_bytes","diagnostic_backups"},"Invalid limit schema")
    need(doc["limits"]==dict(maximum_file_seconds=3600,diagnostic_file_bytes=1048576,diagnostic_backups=4),"Unsupported bounded diagnostic policy")
    return doc

def imports(doc):
    sys.dont_write_bytecode=True
    for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):os.environ[key]="1"
    sys.path.insert(0,doc["source_root"])
    modules={name:importlib.import_module("edge_speech_pipeline."+name)
             for name in ("config","research_profiles","runtime","research_s6d","research_s7","gui")}
    source=Path(doc["source_root"])/"edge_speech_pipeline"
    for name,module in sys.modules.items():
        if name=="edge_speech_pipeline" or name.startswith("edge_speech_pipeline."):
            if getattr(module,"__file__",None):need(Path(module.__file__).resolve().is_relative_to(source),"Conflicting application imports")
    return modules

def engine(doc,mode,selected,output,allow_fallback=False):
    m=imports(doc);effective=mode;fallback=None
    def create(name):
        candidate="C065" if name in ("caption_only","open_conversation") else "C088"
        profile=m["research_profiles"].ResearchProfile.from_dict(doc["profiles"][candidate])
        need(profile.input.gain==1.0 and profile.input.already_gained,"Saved inputs must use the unity-gain profile")
        cfg=m["config"]
        assets=tuple(cfg.AssetSpec(a["component_id"],Path(a["path"]),a["sha256"],a["deployment_relative_path"]) for a in doc["assets"])
        base=cfg.PipelineConfig(assets=assets,session_root=output/"sessions",profile_root=output/"private_profiles")
        s6=m["research_s6d"].S6DSettings(text_delivery=True,boundary_repair=True,transcript_mode="T0",direction_mode="V0",
                                       selected_profile_ids=tuple(selected) if name=="selected_emphasis" else ())
        s7=m["research_s7"].S7Settings(pacing="absolute",instrumentation="full",mode=MODES[name],
               presentation_enabled=True,availability_clock="observed",ownership_mode="supported_prefix_v2")
        result=m["runtime"].PipelineEngine(base,research_profile=profile,
            research_gallery=doc["gallery"] if candidate=="C088" else None,s6d_settings=s6,s7_settings=s7)
        if selected and name=="selected_emphasis":
            need(set(selected)<=set(result._research_gallery.ids),"Selected ID is absent from the configured gallery")
        return result
    try:obj=create(mode)
    except (ValueError,FileNotFoundError,KeyError) as exc:
        if not allow_fallback or mode not in ("open_with_names","selected_emphasis"):raise
        fallback=repr(exc);effective="caption_only";obj=create(effective)
    return obj,m,effective,fallback

def wav_info(path,maximum):
    with wave.open(str(path),"rb") as f:
        need((f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getcomptype())==(1,2,16000,"NONE"),
             "Use a mono16kHz signed16-bit PCM WAV; no implicit resampling or mixing")
        frames=f.getnframes();need(0<frames<=maximum*16000,"WAV duration must be positive and at most one hour")
    return frames

def desktop_class(base):
    class Desktop(base):
        def _refresh_devices(self):
            self.devices=[];self.device_box["values"]=[]
        def _start_live(self):raise RuntimeError("This prototype accepts saved WAV files; live hardware is outside this stage")
        def _start_enrollment_recording(self):raise RuntimeError("Use the existing explicit gallery; no recording in this prototype")
        def _enroll_file(self):raise RuntimeError("Enrollment mutation is outside this prototype")
        def _remove_profile(self):raise RuntimeError("Configured gallery is read-only")
        def _choose_wav(self):raise RuntimeError("Choose the WAV with --wav at launch")
        def _build(self):
            super()._build()
            from tkinter import ttk
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            for widget in list(descendants(self.root)):
                if isinstance(widget,ttk.Notebook):
                    for tab in widget.tabs():
                        label=widget.tab(tab,"text")
                        if label in ("Live microphone","Speaker enrollment"):widget.tab(tab,state="disabled")
                        elif label=="WAV simulation":widget.select(tab)
                if isinstance(widget,ttk.Button) and widget.cget("text") in ("Choose WAV","Process file"):
                    widget.configure(state="disabled")
                if isinstance(widget,ttk.Checkbutton) and "1.0" in str(widget.cget("text")):
                    widget.configure(text="Source-paced file processing",state="disabled")
                if isinstance(widget,ttk.Combobox) and widget.cget("textvariable")==str(self._s7_mode_var):
                    # The launcher selects the actual model workload. View switching cannot change M0 compute.
                    widget.configure(state="disabled")
            self.root.title("Just Peachy — opt-in saved-file prototype")
    return Desktop

class Protocol:
    def __init__(self,output,logger):self.output=output;self.logger=logger;self.last=None
    def check(self):
        if (self.output/"STOP_REQUEST").exists():raise InterruptedError("Explicit local STOP_REQUEST")
    def advance(self,stage,units=1):
        if stage!=self.last:self.logger.info("stage=%s",stage);self.last=stage

def run(args):
    need(args.language=="en","This configured prototype accepts English; no implicit language-model substitution")
    need(args.device is None,"Live device input is unavailable in this saved-file prototype; use --wav")
    doc=load_config(args.config,full_assets=args.command in ("file","gui"))
    selected=args.selected or [];need(len(selected)==len(set(selected)),"Selected IDs must be unique")
    if args.command=="profiles":
        gallery=json.loads(Path(doc["gallery"]).read_text())
        print(json.dumps([dict(id=p["profile_id"],name=p["display_name"]) for p in gallery["profiles"]],indent=2));return 0
    output=args.output.resolve() if args.output else Path(__file__).parent/"unused_validation"
    obj,m,effective,fallback=engine(doc,args.mode,selected,output,args.allow_caption_fallback)
    admission=dict(schema="just-peachy.desktop-receipt.v1",requested_mode=args.mode,effective_mode=effective,
                   fallback_reason=fallback,config=binding(args.config),native_started=False,hardware_started=False,
                   neural_weights_changed=False,default_promoted=False)
    if args.command=="validate":
        need(obj._speaker_models is None and obj._source is None and not obj._threads,"Unexpected model startup")
        print(json.dumps(dict(admission,status="CONFIGURATION_AND_CONSTRUCTOR_VALID",asset_validation="PATHS_ONLY"),indent=2));return 0
    if args.command=="gui-check":
        import tkinter as tk
        root=tk.Tk();root.withdraw()
        try:
            window=desktop_class(m["gui"].EdgeSpeechWindow)(root,obj.config,engine=obj);root.update_idletasks()
            need(window._s7_columns and set(window._s7_columns)=={"left","right","other"},"Missing actual widgets")
            need(window._s7_mode_var.get()==MODES[effective],"Wrong configured GUI mode")
            print(json.dumps(dict(admission,status="ACTUAL_GUI_CONSTRUCTOR_VALID_NO_SOURCE"),indent=2))
        finally:
            for handle in root.tk.call("after","info"):root.after_cancel(handle)
            root.destroy()
        return 0
    need(args.wav is not None and args.output is not None,"file/gui require --wav and a fresh --output directory")
    frames=wav_info(args.wav,doc["limits"]["maximum_file_seconds"])
    need(not output.exists(),"Output exists; select a fresh run folder to preserve evidence")
    output.mkdir(parents=True)
    logger=logging.getLogger("just_peachy_s7");logger.setLevel(logging.INFO)
    handler=logging.handlers.RotatingFileHandler(output/"application.log",maxBytes=1048576,backupCount=4,encoding="utf-8")
    logger.addHandler(handler)
    try:
        sys.path.insert(0,str(Path(__file__).parent/"helpers"))
        import Native,GuiExecution,Closure
        audio=binding(args.wav)
        job=dict(audio=audio,expected_pcm=Native.pcm_info(args.wav),s7_settings=obj._s7.receipt(),gui_actions=[])
        (output/"LAUNCH.json").write_text(json.dumps(dict(admission,input=audio,frames=frames),indent=2)+"\n")
        protocol=Protocol(output,logger)
        if args.command=="gui":
            m["gui"].EdgeSpeechWindow=desktop_class(m["gui"].EdgeSpeechWindow)
            result=GuiExecution.execute_gui(Native,obj,job,output,protocol,Closure.completion_errors,frames/16000+180)
        else:result=Native.execute_cell(obj,job,output,protocol,Closure.completion_errors,frames/16000+180)
        result["source_audit"]=Native.audit_pcm(job,Path(result["session_dir"]))
        need(binding(args.wav)==audio,"Input changed during run")
        value=dict(admission,status="COMPLETE" if result["failure"] is None and not result["completion_errors"] else "FAILED",
                   native_started=True,input=audio,execution=result,diagnostics=dict(max_file_bytes=1048576,backups=4,
                   retention="Only application.log rotates; full session/consumer/scientific evidence is preserved"))
        (output/"RESULT.json").write_text(json.dumps(value,indent=2)+"\n")
        print(json.dumps(dict(status=value["status"],effective_mode=effective,fallback_reason=fallback,output=str(output))))
        return 0 if value["status"]=="COMPLETE" else 2
    finally:
        handler.close();logger.removeHandler(handler)

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=["validate","profiles","gui-check","file","gui"])
    p.add_argument("--config",type=Path,required=True);p.add_argument("--mode",choices=MODES,default="caption_only")
    p.add_argument("--wav",type=Path);p.add_argument("--output",type=Path)
    p.add_argument("--selected",nargs="*",default=[]);p.add_argument("--allow-caption-fallback",action="store_true")
    p.add_argument("--language",default="en");p.add_argument("--device")
    return p
if __name__=="__main__":
    try:raise SystemExit(run(parser().parse_args()))
    except (ValueError,FileNotFoundError,KeyError,wave.Error) as exc:
        print(json.dumps(dict(status="ERROR",message=str(exc))),file=sys.stderr);raise SystemExit(2)

