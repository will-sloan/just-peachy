"""Non-neural config/actual-GUI/error/fallback checks. README_CHECKS.md."""
import copy,json,wave
from pathlib import Path
import App as A
HERE=Path(__file__).resolve().parent
def main():
    out=HERE/"CHECKS.json";A.need(not out.exists(),"Fresh checks required")
    doc=A.load_config(HERE/"CONFIG.json")
    gallery=json.loads(Path(doc["gallery"]).read_text());ids=[p["profile_id"] for p in gallery["profiles"][:2]]
    checks=[];constructed=[];fixtures=HERE/"check_fixtures";fixtures.mkdir()
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    def reject(name,fn):
        try:fn()
        except (ValueError,FileNotFoundError,KeyError,wave.Error):checks.append(name)
        else:raise AssertionError("Invalid input accepted: "+name)
    def forbidden(*a,**kw):raise AssertionError("Unexpected model/source/hardware startup in fixture")
    import tkinter as tk
    from tkinter import ttk
    for mode,code in A.MODES.items():
        selected=ids if mode=="selected_emphasis" else []
        engine,m,effective,fallback=A.engine(doc,mode,selected,fixtures/mode)
        m["runtime"].SpeakerModels=m["runtime"].SherpaStream=forbidden
        m["runtime"].MicrophoneSource=m["runtime"].WavSource=forbidden
        check(mode+"/actual_profile_config",effective==mode and fallback is None and engine._s7.mode==code)
        check(mode+"/gallery_scope",bool(engine._research_gallery)==(mode in ("open_with_names","selected_emphasis")))
        root=tk.Tk();root.withdraw()
        try:
            window=A.desktop_class(m["gui"].EdgeSpeechWindow)(root,engine.config,engine=engine)
            root.update_idletasks()
            check(mode+"/actual_controls",window._s7_mode_var.get()==code and set(window._s7_columns)=={"left","right","other"})
            def descend(w):
                for child in w.winfo_children():yield child;yield from descend(child)
            widgets=list(descend(root))
            books=[w for w in widgets if isinstance(w,ttk.Notebook)]
            check(mode+"/live_enrollment_disabled",len(books)==1 and all(books[0].tab(t,"state")=="disabled" for t in books[0].tabs() if books[0].tab(t,"text") in ("Live microphone","Speaker enrollment")))
            modebox=[w for w in widgets if isinstance(w,ttk.Combobox) and str(w.cget("textvariable"))==str(window._s7_mode_var)]
            check(mode+"/workload_switch_disabled",len(modebox)==1 and str(modebox[0].cget("state"))=="disabled")
            check(mode+"/selected_roster_exact",window._s7_selection_var.get()==",".join(selected))
            check(mode+"/zero_neural_source_start",engine._speaker_models is None and engine._source is None and not engine._threads and engine.session_dir is None)
            constructed.append(dict(mode=mode,engine_mode=code,actual_GUI_constructed=True,model_instances=0))
        finally:
            for handle in root.tk.call("after","info"):root.after_cancel(handle)
            root.destroy()
    missing=copy.deepcopy(doc);missing["gallery"]=str(fixtures/"missing-gallery.json")
    reject("missing_gallery_explicit_error",lambda:A.engine(missing,"open_with_names",[],fixtures/"missing"))
    engine,_,mode,reason=A.engine(missing,"open_with_names",[],fixtures/"fallback",True)
    check("explicit_caption_fallback_records_reason",mode=="caption_only" and bool(reason) and engine._s7.mode=="M0" and engine._research_gallery is None)
    reject("unknown_selected_id",lambda:A.engine(doc,"selected_emphasis",["not_in_gallery"],fixtures/"bad_id"))
    for name,change in (
        ("bad_schema",lambda c:c.update(schema="unsupported")),
        ("extra_field",lambda c:c.update(unknown=True)),
        ("missing_asset",lambda c:c["assets"][0].update(path=str(fixtures/"missing.onnx"))),
        ("modified_source_pin",lambda c:c["source_files"][0].update(sha256="0"*64)),
        ("wrong_language_config",lambda c:c.update(language="unsupported"))):
        value=copy.deepcopy(doc);change(value);path=fixtures/(name+".json");path.write_text(json.dumps(value))
        reject(name,lambda p=path:A.load_config(p))
    for name,channels,width,rate in (("stereo",2,2,16000),("wrong_rate",1,2,48000),("wrong_width",1,1,16000),("valid",1,2,16000)):
        path=fixtures/(name+".wav")
        with wave.open(str(path),"wb") as f:f.setnchannels(channels);f.setsampwidth(width);f.setframerate(rate);f.writeframes(b"\0"*width*channels*160)
        if name=="valid":check("valid_PCM_header",A.wav_info(path,3600)==160)
        else:reject(name,lambda p=path:A.wav_info(p,3600))
    for name,argv in (("wrong_language",["--language","fr"]),("device_not_supported",["--device","1"]),("duplicate_selection",["--selected",ids[0],ids[0]])):
        args=A.parser().parse_args(["validate","--config",str(HERE/"CONFIG.json")]+argv)
        reject(name,lambda a=args:A.run(a))
    value=dict(status="PASS_ORDINARY_CONFIG_CONSTRUCTOR_GUI_AND_ERROR_HANDLING_ONLY",checks_passed=len(checks),checks=checks,
        modes=constructed,script=A.binding(__file__),launcher=A.binding(A.__file__),config=A.binding(HERE/"CONFIG.json"),
        native_runs=0,model_instances=0,hardware_started=False,portability_smoke="PENDING")
    out.write_text(json.dumps(value,indent=2)+"\n")
    print(json.dumps(dict(status=value["status"],checks_passed=len(checks),native_runs=0)))
if __name__=="__main__":main()

