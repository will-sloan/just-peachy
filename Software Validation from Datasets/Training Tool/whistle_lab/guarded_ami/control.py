"""Windows entry point: owned hidden WSL process with bounded restart recovery."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import time
import psutil
from runtime import *

TASK_NAME = "JustPeachy Whistle Exploratory Monitor"

if os.name == "nt":
    ctypes.windll.kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    ctypes.windll.kernel32.CreateMutexW.restype = wintypes.HANDLE
    ctypes.windll.kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    ctypes.windll.kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
    ctypes.windll.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def wsl_path(path):
    value = Path(path).resolve().as_posix()
    return "/mnt/" + value[0].lower() + value[2:]


def owned(saved):
    try:
        process = psutil.Process(saved["pid"])
        command = process.cmdline()
        if abs(process.create_time()-saved["created_at"]) < 1 and wsl_path(SOURCE/"supervise.py") in command:
            return process
    except (KeyError, psutil.Error):
        pass
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "status", "pause", "resume", "monitor"])
    args = parser.parse_args()
    if args.action == "status":
        print(json.dumps({"status": read_json(RUN/"status.json"), "checkpoint": read_json(RUN/"checkpoint.json"),
                          "scoring": read_json(RUN/"scoring_status.json")}, indent=2))
        return 0
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\JustPeachyWhistleExploratoryV1")
    if not mutex or ctypes.windll.kernel32.WaitForSingleObject(mutex, 0) not in (0, 128):
        return 73
    try:
        if args.action in ("pause", "resume"):
            control = read_json(RUN/"control.json")
            control.update(paused=args.action=="pause", changed_at=time.time())
            atomic_json(RUN/"control.json", control)
            if args.action == "pause":
                print("Pause requested; worker will save at its next safe boundary.")
                return 0
        if read_json(RUN/"summary.json").get("complete"):
            if args.action == "monitor":
                subprocess.run(["schtasks.exe", "/Change", "/TN", TASK_NAME, "/DISABLE"],
                               creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)
            return 0
        if paused():
            print("A user pause is active; no worker launched.")
            return 75
        if not (RUN/"config.json").exists():
            raise RuntimeError("Run preparation must complete before launch")
        saved = read_json(RUN/"launcher.json")
        if owned(saved):
            print("Existing owned worker is available.")
            return 0
        recovery = read_json(RUN/"launcher_recovery.json")
        count = recovery.get("restarts", 0)
        if saved:
            if read_json(RUN/"status.json").get("phase") == "failed":
                print("Worker failed; inspect its saved error. No automatic restart beyond the supervisor retry limit.")
                return 1
            if args.action == "monitor":
                if count >= 2:
                    status("failed", message="Two bounded supervisor recoveries exhausted; inspect owned process and log")
                    return 1
                count += 1
                recovery.setdefault("history", []).append({"time": time.time(), "previous_pid": saved.get("pid"),
                                                          "reason": "Owned launcher absent; exact continuation only"})
                recovery["restarts"] = count
                atomic_json(RUN/"launcher_recovery.json", recovery)
        config = read_json(LAB/"config.json")
        command = ["wsl.exe", "-d", config["wsl_distribution"], "--", config["wsl_python"],
                   "-u", wsl_path(SOURCE/"supervise.py")]
        with (RUN/"worker.log").open("a", encoding="utf-8") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
        atomic_json(RUN/"launcher.json", {"pid": process.pid, "created_at": psutil.Process(process.pid).create_time(),
                                          "command": command})
        print(json.dumps({"launched": True, "pid": process.pid, "run_directory": str(RUN)}))
        return 0
    finally:
        ctypes.windll.kernel32.ReleaseMutex(mutex)
        ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    raise SystemExit(main())
