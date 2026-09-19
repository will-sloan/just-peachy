"""Short real-controller, saved-file Tk check. See docs/UI_ITERATION.md.

Explicitly no microphone/enrollment. This opt-in script is not unittest discovery.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PROTOTYPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROTOTYPE)); sys.path.insert(0, str(PROTOTYPE / "vendor"))
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(name, "1")


def capture(root, path):
    """Windows screen read only; native PNG writer avoids model-env dependencies."""
    root.update_idletasks()
    x, y, width, height = root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height()
    literal = str(path).replace("'", "''")
    command = ("Add-Type -AssemblyName System.Drawing; "
        f"$bitmap = New-Object System.Drawing.Bitmap({width},{height}); "
        "$graphics = [System.Drawing.Graphics]::FromImage($bitmap); "
        f"try {{ $graphics.CopyFromScreen({x},{y},0,0,$bitmap.Size); "
        f"$bitmap.Save('{literal}',[System.Drawing.Imaging.ImageFormat]::Png) }} "
        "finally { $graphics.Dispose(); $bitmap.Dispose() }")
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=20)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wav", required=True, type=Path)
    p.add_argument("--data-root", required=True, type=Path)
    p.add_argument("--models", type=Path)
    p.add_argument("--mode", default="anonymous_conversation")
    p.add_argument("--recipe", default="balanced")
    p.add_argument("--timeout-sec", type=float, default=180)
    args = p.parse_args()
    from app.paths import default_models_root, atomic_json
    from app.controller import Controller
    from app.ui import PrototypeUI, prepare_dpi_awareness
    import tkinter as tk
    if (args.data_root / "NATIVE_UI_RESULT.json").exists():
        raise ValueError("Choose a fresh evidence data root; do not overwrite a prior native check")
    prepare_dpi_awareness()
    controller = Controller(args.data_root, args.models or default_models_root())
    root = tk.Tk(); ui = PrototypeUI(root, controller)
    root.title("Just Peachy · native saved-file UI check · no microphone")
    root.geometry("+25+25"); root.attributes("-topmost", True)
    evidence = args.data_root / "ui_evidence"; evidence.mkdir(parents=True, exist_ok=True)
    begun = time.perf_counter()
    result = dict(kind="NATIVE SAVED-FILE UI; no microphone or real enrollment", started_utc=datetime.now(timezone.utc).isoformat(),
        wav=str(args.wav.resolve()), recipe=args.recipe, mode=args.mode, client=ui.measure_client(),
        observed_revisions={}, observed_labels=[], screenshots=[], pages_reachable=[], failures=[], close_waited=False)
    started = False; finishing = False; screenshot_done = False; snapshot_before_close = None

    def tick():
        nonlocal started, finishing, screenshot_done, snapshot_before_close
        try:
            snapshot = controller.snapshot()
            state = snapshot["state"]
            if state in ("STARTING", "RUNNING"): started = True
            for row in snapshot["rows"]:
                rid = row["id"]
                value = {key: row.get(key) for key in ("raw_asr_text", "provisional_display_text", "final_punctuated_display_text", "label", "final")}
                revisions = result["observed_revisions"].setdefault(rid, [])
                if not revisions or revisions[-1] != value: revisions.append(value)
                if row["label"] not in result["observed_labels"]: result["observed_labels"].append(row["label"])
            if snapshot["rows"] and not screenshot_done:
                ui.snapshot = snapshot; ui._show_status(); ui._render_rows(snapshot["rows"]); root.update_idletasks()
                path = evidence / "01_native_partial.png"; capture(root, path)
                result["screenshots"].append(str(path)); screenshot_done = True
            if snapshot.get("error") and not finishing:
                result["failures"].append(snapshot["error"]); finishing = True
            if time.perf_counter() - begun > args.timeout_sec and not finishing:
                result["failures"].append("Native UI check deadline reached"); finishing = True
            if started and state in ("STOPPED", "ERROR") and not finishing:
                finishing = True
            if finishing and not ui._closing:
                snapshot_before_close = snapshot
                ui.snapshot = snapshot; ui._show_status(); ui._render_rows(snapshot["rows"]); root.update_idletasks()
                result["displayed_text"] = ui.caption_text.get("1.0", "end-1c")
                result["display_row_ids"] = list(ui._render_order)
                if result["display_row_ids"] != [row["id"] for row in snapshot["rows"]]:
                    result["failures"].append("Display row IDs do not equal backend row IDs")
                for row in snapshot["rows"]:
                    expected = ui._display_row(row)[1]
                    if expected not in result["displayed_text"]:
                        result["failures"].append("Displayed caption differs: " + row["id"])
                path = evidence / "02_native_final.png"; capture(root, path); result["screenshots"].append(str(path))
                for name, show in (("modes", ui.show_modes), ("people", ui.show_people), ("settings", ui.show_settings)):
                    show(); root.update_idletasks()
                    if ui.page != name: result["failures"].append("Page not reachable: " + name)
                    else: result["pages_reachable"].append(name)
                ui.home(); ui.close(); result["close_waited"] = bool(root.winfo_exists())
            if not ui._closed: root.after(100, tick)
        except Exception as exc:
            result["failures"].append(type(exc).__name__ + ": " + str(exc))
            if not ui._closing: ui.close()

    try:
        controller.switch(mode=args.mode, recipe=args.recipe, tap="O0")
        controller.start_file(args.wav)
        root.after(100, tick); root.mainloop()
    finally:
        if not controller.closed: controller.close()
        controller.commands.join(); controller.worker.join(10)
        result.update(closed=controller.closed, worker_alive=controller.worker.is_alive(), elapsed_sec=time.perf_counter()-begun,
                      completed_utc=datetime.now(timezone.utc).isoformat(), final_snapshot=snapshot_before_close,
                      output_default_observations=controller.output_defaults)
        if not controller.closed or controller.worker.is_alive(): result["failures"].append("Controller did not close completely")
        if not result["observed_revisions"]: result["failures"].append("No native rows observed")
        if (result["client"].get("physical_width"), result["client"].get("physical_height")) != (480,800):
            result["failures"].append("Client was not measured at 480x800 physical pixels")
        result["source_sha256"] = {str(path.relative_to(PROTOTYPE)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), PROTOTYPE/"app/ui.py", PROTOTYPE/"app/controller.py", PROTOTYPE/"app/casing.py", PROTOTYPE/"config/ui.json")}
        result["status"] = "PASS_NATIVE_FILE_UI" if not result["failures"] else "FAIL_NATIVE_FILE_UI"
        atomic_json(args.data_root / "NATIVE_UI_RESULT.json", result)
    print(json.dumps({key:result[key] for key in ("status","elapsed_sec","closed","worker_alive","pages_reachable","failures")}))
    return bool(result["failures"])


if __name__ == "__main__": raise SystemExit(main())
