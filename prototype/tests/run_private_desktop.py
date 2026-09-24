"""Run Tk test modules on a private Windows desktop without switching input.

No microphone/model/device calls; no mouse/keyboard injection. README_N1_FRONTEND.md.
"""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
import uuid


def desktop_name(handle):
    size = wintypes.DWORD()
    ctypes.windll.user32.GetUserObjectInformationW(handle, 2, None, 0, ctypes.byref(size))
    buffer = ctypes.create_unicode_buffer(max(256, size.value))
    if not ctypes.windll.user32.GetUserObjectInformationW(handle, 2, buffer, ctypes.sizeof(buffer), ctypes.byref(size)):
        raise ctypes.WinError()
    return buffer.value


def setup_api():
    user32 = ctypes.windll.user32
    user32.GetThreadDesktop.argtypes = [wintypes.DWORD]; user32.GetThreadDesktop.restype = wintypes.HANDLE
    user32.OpenInputDesktop.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]; user32.OpenInputDesktop.restype = wintypes.HANDLE
    user32.GetUserObjectInformationW.argtypes = [wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]; user32.CloseDesktop.restype = wintypes.BOOL
    return user32


def input_desktop_name():
    user32 = setup_api()
    handle = user32.OpenInputDesktop(0, False, 0x0001)
    if not handle: raise ctypes.WinError()
    try: return desktop_name(handle)
    finally: user32.CloseDesktop(handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt-dir', required=True)
    parser.add_argument('--child-desktop')
    parser.add_argument('--timeout-seconds', type=float, default=240)
    parser.add_argument('modules', nargs='+')
    args = parser.parse_args()
    if os.name != 'nt': raise SystemExit('This isolation launcher requires Windows; use Xvfb separately on Linux.')
    folder = Path(args.receipt_dir).resolve(); folder.mkdir(parents=True, exist_ok=True)
    user32 = setup_api()
    if args.child_desktop:
        current = desktop_name(user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId()))
        if current != args.child_desktop or not current.startswith('codex-n1-'):
            raise SystemExit('Refusing GUI tests outside the expected isolated desktop')
        prototype = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(prototype / 'vendor'))
        sys.path.insert(0, str(prototype))
        os.environ['N1_UI_RECEIPT_DIR'] = str(folder)
        with (folder/'unittest.txt').open('w',encoding='utf-8') as stream:
            suite = unittest.defaultTestLoader.loadTestsFromNames(args.modules)
            result = unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        receipt = dict(schema='just-peachy.private-desktop-test.v1',desktop=current,
            tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
            successful=result.wasSuccessful(),modules=args.modules,
            visible_on_input_desktop=False,input_injection=False,hardware_access=False)
        (folder/'tests.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
        return 0 if result.wasSuccessful() else 1
    before = input_desktop_name()
    desktop = 'codex-n1-'+uuid.uuid4().hex
    user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR,wintypes.LPCWSTR,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
    user32.CreateDesktopW.restype = wintypes.HANDLE
    handle = user32.CreateDesktopW(desktop,None,None,0,0x0001|0x0002|0x0080,None)
    if not handle: raise ctypes.WinError()
    class STARTUPINFO(ctypes.Structure):
        _fields_ = [('cb',wintypes.DWORD),('lpReserved',wintypes.LPWSTR),('lpDesktop',wintypes.LPWSTR),
            ('lpTitle',wintypes.LPWSTR),('dwX',wintypes.DWORD),('dwY',wintypes.DWORD),('dwXSize',wintypes.DWORD),
            ('dwYSize',wintypes.DWORD),('dwXCountChars',wintypes.DWORD),('dwYCountChars',wintypes.DWORD),
            ('dwFillAttribute',wintypes.DWORD),('dwFlags',wintypes.DWORD),('wShowWindow',wintypes.WORD),
            ('cbReserved2',wintypes.WORD),('lpReserved2',ctypes.POINTER(ctypes.c_byte)),
            ('hStdInput',wintypes.HANDLE),('hStdOutput',wintypes.HANDLE),('hStdError',wintypes.HANDLE)]
    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [('hProcess',wintypes.HANDLE),('hThread',wintypes.HANDLE),('dwProcessId',wintypes.DWORD),('dwThreadId',wintypes.DWORD)]
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR,wintypes.LPWSTR,ctypes.c_void_p,ctypes.c_void_p,wintypes.BOOL,
        wintypes.DWORD,ctypes.c_void_p,wintypes.LPCWSTR,ctypes.POINTER(STARTUPINFO),ctypes.POINTER(PROCESS_INFORMATION)]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE,wintypes.DWORD]
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE,wintypes.UINT]
    startup = STARTUPINFO(); startup.cb = ctypes.sizeof(startup); startup.lpDesktop = desktop
    startup.dwFlags = 1; startup.wShowWindow = 0
    process = PROCESS_INFORMATION()
    command = [sys.executable,'-m','prototype.tests.run_private_desktop','--receipt-dir',str(folder),
        '--child-desktop',desktop,*args.modules]
    started = time.monotonic(); exit_code = None; timed_out = False
    try:
        if not kernel32.CreateProcessW(sys.executable,ctypes.create_unicode_buffer(subprocess.list2cmdline(command)),
            None,None,False,0x08000000,None,str(Path(__file__).resolve().parents[2]),ctypes.byref(startup),ctypes.byref(process)):
            raise ctypes.WinError()
        while kernel32.WaitForSingleObject(process.hProcess,200) == 258:
            if time.monotonic()-started > args.timeout_seconds:
                timed_out = True
                kernel32.TerminateProcess(process.hProcess,124)
                kernel32.WaitForSingleObject(process.hProcess,5000)
                break
        code = wintypes.DWORD(); kernel32.GetExitCodeProcess(process.hProcess,ctypes.byref(code)); exit_code = code.value
    finally:
        if process.hThread: kernel32.CloseHandle(process.hThread)
        if process.hProcess: kernel32.CloseHandle(process.hProcess)
        user32.CloseDesktop(handle)
        after = input_desktop_name()
        receipt = dict(schema='just-peachy.private-desktop-launch.v1',desktop=desktop,
            input_desktop_before=before,input_desktop_after=after,input_desktop_unchanged=before==after,
            switch_desktop_called=False,input_injection=False,exit_code=exit_code,timed_out=timed_out,
            elapsed_seconds=round(time.monotonic()-started,3),desktop_handle_closed=True)
        (folder/'isolation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))
    if (folder/'unittest.txt').exists(): print((folder/'unittest.txt').read_text(encoding='utf-8'))
    return exit_code if exit_code is not None else 1


if __name__ == '__main__': raise SystemExit(main())
