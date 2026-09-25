"""Model-free child lifetime fixtures; run only through the private probe."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil
from common import bind
from private_application_process import PrivateApplicationProcess, api, checked


def write(path, **record):
    with Path(path).open('x', encoding='utf-8') as stream: json.dump(record, stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', required=True, choices=['normal', 'cooperative', 'error', 'tree', 'orphan', 'leaf', 'owner_death'])
    parser.add_argument('--evidence', type=Path, required=True); parser.add_argument('--cancel', type=Path, required=True)
    args = parser.parse_args(); process = psutil.Process()
    write(args.evidence/'started.json', pid=os.getpid(), create_time=process.create_time(), affinity=process.cpu_affinity())
    if args.mode == 'leaf':
        # Independent upper bound keeps a failed fixture from becoming a stray helper.
        time.sleep(15); return
    if args.mode == 'error': raise RuntimeError('Intentional model-free fixture failure')
    if args.mode in ('tree', 'orphan'):
        leaf = args.evidence/'leaf'; leaf.mkdir()
        child = subprocess.Popen([sys.executable, '-B', __file__, '--mode', 'leaf', '--evidence', str(leaf), '--cancel', str(args.cancel)],
            creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
        until = time.monotonic()+5
        while not (leaf/'started.json').exists() and time.monotonic() < until: time.sleep(.02)
        if not (leaf/'started.json').exists(): raise RuntimeError('Leaf did not start')
        if args.mode == 'orphan': return
        child.wait(timeout=20); return
    if args.mode == 'owner_death':
        leaf = args.evidence/'leaf'; leaf.mkdir()
        owned = PrivateApplicationProcess(args.evidence/'inner-owner', executable_binding=bind(sys.executable),
            script_binding=bind(__file__), arguments=['--mode', 'leaf', '--evidence', str(leaf), '--cancel', str(args.cancel)], cpu=14)
        owned.spawn_suspended(); owned.resume(lambda *a, **kw: None)
        until = time.monotonic()+5
        while not (leaf/'started.json').exists() and time.monotonic() < until: time.sleep(.02)
        if not (leaf/'started.json').exists(): owned.close(grace_seconds=0); raise RuntimeError('Nested leaf did not start')
        os._exit(23)  # No Python cleanup: Windows must close the sole inner job handle.
    if args.mode == 'cooperative':
        until = time.monotonic()+15
        while not args.cancel.exists() and time.monotonic() < until: time.sleep(.02)
        write(args.evidence/'cancelled.json', observed=args.cancel.exists()); return
    # Real Tk on the non-input desktop; no focus/input injection or devices.
    import tkinter as tk
    kernel, user = api()
    kernel.GetCurrentThreadId.argtypes = []; kernel.GetCurrentThreadId.restype = W.DWORD
    user.GetThreadDesktop.argtypes = [W.DWORD]; user.GetThreadDesktop.restype = W.HANDLE
    handle = checked(user.GetThreadDesktop(kernel.GetCurrentThreadId()))
    buffer = C.create_unicode_buffer(512); needed = W.DWORD()
    checked(user.GetUserObjectInformationW(handle, 2, buffer, C.sizeof(buffer), C.byref(needed)))
    root = tk.Tk(); root.geometry('480x800'); tk.Label(root, text='Private lifetime fixture').pack()
    root.update(); root.destroy()
    write(args.evidence/'tk.json', desktop=buffer.value, created_and_destroyed=True)


if __name__ == '__main__': main()
