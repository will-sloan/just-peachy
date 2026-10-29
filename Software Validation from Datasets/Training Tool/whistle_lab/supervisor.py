"""Token-free Windows supervisor and localhost progress server; see README.md."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import ctypes
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
from common import CONFIG, CONFIG_DIGEST, ROOT, RUN, atomic_json, read_json, status

CHILD = None
SHUTDOWN = threading.Event()


def wsl_path(path):
    path = Path(path).absolute().as_posix()
    return "/mnt/" + path[0].lower() + path[2:]


def payload():
    data = read_json(RUN / "status.json", {"phase": "setup", "message": "Preparing local training"})
    data.update(control=read_json(RUN / "control.json"), gpu=read_json(RUN / "gpu.json"), benchmark=read_json(RUN / "benchmark.json"), checkpoint=read_json(RUN / "checkpoint.json"), data_audit=read_json(RUN / "data_audit.json"), evaluation=read_json(RUN / "evaluation_summary.json"), supervisor_pid=os.getpid(), worker_running=CHILD is not None and CHILD.poll() is None, server_time=time.time())
    history = RUN / "history.jsonl"
    values = []
    if history.exists():
        with history.open("rb") as handle:
            handle.seek(max(0, history.stat().st_size - 350000))
            if handle.tell():
                handle.readline()
            for line in handle:
                try:
                    values.append(json.loads(line))
                except ValueError:
                    pass
    data["history"] = values[-500:]
    return data


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, data, code=200, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/status":
            self.respond(json.dumps(payload(), allow_nan=False).encode())
        elif self.path in ("/", "/index.html"):
            self.respond((ROOT / "dist/index.html").read_bytes(), content_type="text/html")
        else:
            self.respond(b'{"error":"not found"}', 404)

    def do_POST(self):
        origin = self.headers.get("Origin")
        allowed = {f"http://127.0.0.1:{CONFIG['dashboard_port']}", f"http://localhost:{CONFIG['dashboard_port']}"}
        if self.path != "/api/control" or (origin and origin not in allowed) or self.headers.get("X-Whistle-Control") != "local" or int(self.headers.get("Content-Length", "0")) > 1024:
            self.respond(b'{"error":"rejected"}', 403)
            return
        try:
            value = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            action = value["action"]
            if action not in ("pause", "resume"):
                raise ValueError("Unknown action")
            control = read_json(RUN / "control.json")
            control.update(paused=action == "pause", changed_at=time.time())
            if action == "resume":
                control.update(run_enabled=True, retry_requested=time.time())
            atomic_json(RUN / "control.json", control)
            self.respond(json.dumps(control).encode())
        except (ValueError, KeyError):
            self.respond(b'{"error":"invalid control"}', 400)


def gpu_monitor():
    while not SHUTDOWN.is_set():
        try:
            current = read_json(RUN / "status.json")
            active = current.get("phase") in {"benchmarking", "initializing", "training", "evaluating", "exporting", "preparing"}
            active = active and not read_json(RUN / "control.json").get("paused", False)
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if active else 0x80000000)
            output = subprocess.check_output(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw", "--format=csv,noheader,nounits"], creationflags=subprocess.CREATE_NO_WINDOW, text=True, timeout=8)
            parts = [s.strip() for s in output.splitlines()[0].split(",")]
            atomic_json(RUN / "gpu.json", dict(zip(("name", "utilization", "memory_used_mb", "memory_total_mb", "temperature_c", "power_w"), [parts[0], *[float(x) for x in parts[1:]]]), updated_at=time.time()))
        except Exception:
            pass
        SHUTDOWN.wait(10)
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def run_stage(script, args=(), native=False):
    global CHILD
    log_path = RUN / (Path(script).stem + ".log")
    command = ["wsl.exe", "-d", CONFIG["wsl_distribution"], "--", CONFIG["wsl_python"], "-u", wsl_path(ROOT / script), *args]
    if native:
        command = [sys.executable, "-u", str(ROOT / script), *args]
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n=== launched {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        log.flush()
        CHILD = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        atomic_json(RUN / "worker.json", {"windows_pid": CHILD.pid, "script": script, "started_at": time.time()})
        return CHILD.wait()


def supervise():
    failures = 0
    last_retry = 0
    while not SHUTDOWN.wait(5):
        control = read_json(RUN / "control.json")
        if control.get("retry_requested", 0) > last_retry:
            failures = 0
            last_retry = control["retry_requested"]
        if control.get("paused") or not control.get("run_enabled") or failures >= 3:
            continue
        current = read_json(RUN / "status.json").get("phase")
        if current == "complete":
            continue
        try:
            if not (RUN / "assets.json").exists():
                code = run_stage("bootstrap_assets.py")
            elif not (RUN / "data_audit.json").exists():
                code = run_stage("prepare.py")
            elif read_json(RUN / "audio_header_audit.json").get("invalid_segments", -1) != 0 or read_json(RUN / "audio_header_audit.json").get("manifest_sha256") != {split: read_json(RUN / "data_audit.json")["splits"][split]["sha256"] for split in ("train", "dev")}:
                status("preparing", message="Verifying actual audio lengths for every train/dev segment")
                code = run_stage("audit_audio.py", native=True)
            elif not read_json(RUN / "benchmark.json").get("complete") or read_json(RUN / "benchmark.json").get("config_digest") != CONFIG_DIGEST or not read_json(RUN / "resume_verification.json").get("passed"):
                code = run_stage("train.py", ["--benchmark"])
            elif not (RUN / "whistle.final.cact").exists() or not (RUN / "whistle.best.cact").exists():
                code = run_stage("train.py")
            else:
                code = run_stage("evaluate.py")
            if code == 75:
                continue
            if code == 73:
                # A surviving WSL worker still owns the job after supervisor restart.
                SHUTDOWN.wait(60)
                continue
            if code:
                failures += 1
                status("failed", message=f"Worker exited with code {code}; retry {failures}/3 after 60 seconds. See worker log.")
                SHUTDOWN.wait(60)
            else:
                failures = 0
        except Exception as error:
            failures += 1
            status("failed", message=str(error), traceback=traceback.format_exc())


def main():
    RUN.mkdir(parents=True, exist_ok=True)
    # The kernel releases this exclusive lock on a process or machine crash.
    lock = (RUN / "supervisor.lock").open("a+b")
    lock.seek(0)
    if lock.read(1) == b"":
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return 0
    atomic_json(RUN / "supervisor.json", {"pid": os.getpid(), "started_at": time.time(), "url": f"http://127.0.0.1:{CONFIG['dashboard_port']}"})
    server = ThreadingHTTPServer(("127.0.0.1", CONFIG["dashboard_port"]), Handler)
    threading.Thread(target=gpu_monitor, daemon=True).start()
    threading.Thread(target=supervise, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        SHUTDOWN.set()
        server.server_close()
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
