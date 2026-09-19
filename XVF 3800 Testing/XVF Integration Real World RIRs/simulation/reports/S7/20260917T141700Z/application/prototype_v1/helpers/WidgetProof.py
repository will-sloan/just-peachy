"""Read actual widgets after application; no input/model/evidence mutation. README.md."""
import hashlib
import time

def startup(window, mode):
    if not all(hasattr(window,"_s7_"+n+"_var") for n in ("mode","selection","display")):
        raise RuntimeError("Actual S7 startup controls absent")
    columns=window._s7_columns
    if not columns or set(columns)!={"left","right","other"}:
        raise RuntimeError("Actual S7 startup column widgets absent")
    if window._s7_mode_var.get()!=mode or not all(w.winfo_exists() for w in columns.values()):
        raise RuntimeError("Actual S7 startup widgets invalid")
    return dict(status="ACTUAL_CONTROLS_AND_THREE_COLUMNS_PRESENT_BEFORE_SOURCE",
                mode=mode,columns=sorted(columns),observed_monotonic_sec=time.perf_counter())

def capture(window, row):
    if row["kind"]!="s7_gui_applied":return row
    begin=time.perf_counter()
    mode=row["mode"]
    columns=window._s7_columns
    if not columns or set(columns)!={"left","right","other"}:
        raise RuntimeError("Actual column widgets missing")
    active=columns if mode=="M5" else {"all":window.transcript}
    # This check reads actual Tk widget text. Projection metadata alone cannot satisfy it.
    expected={name:"" for name in active}
    for projected in window._s7_last_rendered_rows.values():
        for piece in projected["segments"]:
            if not piece.get("rendered"):continue
            name=(piece["column"] if piece["column"] in ("left","right") else "other") if mode=="M5" else "all"
            prefix=f'[{projected.get("source_start_sec",0):.2f}s; tokens {piece.get("token_range")}] ' if mode=="M5" else ""
            expected[name]+=prefix+piece["label"]+": "+piece["display_text"]+(" …" if not projected.get("final") else "")+"\n\n"
    actual={name:widget.get("1.0","end-1c") for name,widget in active.items()}
    if actual!=expected:raise RuntimeError("Actual widget text differs from rendered projection")
    if mode=="M5":
        if window.transcript.winfo_manager() or window._s7_columns_frame.winfo_manager()!="pack":
            raise RuntimeError("M5 actual column frame not active")
    elif window.transcript.winfo_manager()!="pack" or window._s7_columns_frame.winfo_manager():
        raise RuntimeError("Actual transcript frame not active")
    return dict(row,widget_text_proof=dict(status="EXACT_ACTUAL_WIDGET_TEXT_MATCH",
        mode=mode,active_widgets=list(active),actual_text=actual,
        sha256={k:hashlib.sha256(v.encode("utf-8")).hexdigest() for k,v in actual.items()},
        observed_started_monotonic_sec=begin,observed_finished_monotonic_sec=time.perf_counter(),
        scope="Actual Tk text and geometry manager; not physical display scanout"))

def sink(window, writer):
    def submit(row):
        writer(capture(window,row))
    return submit

