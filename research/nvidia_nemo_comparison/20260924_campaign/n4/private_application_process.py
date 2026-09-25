"""Owned Windows private-desktop process lifetime. README_PRIVATE_APPLICATION_PROCESS.md."""
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import time
import uuid

import psutil
from common import fingerprint, freeze, verify
from metric_process import identity


class STARTUPINFO(C.Structure):
    _fields_ = [('cb', W.DWORD), ('lpReserved', W.LPWSTR), ('lpDesktop', W.LPWSTR),
        ('lpTitle', W.LPWSTR), ('dwX', W.DWORD), ('dwY', W.DWORD), ('dwXSize', W.DWORD),
        ('dwYSize', W.DWORD), ('dwXCountChars', W.DWORD), ('dwYCountChars', W.DWORD),
        ('dwFillAttribute', W.DWORD), ('dwFlags', W.DWORD), ('wShowWindow', W.WORD),
        ('cbReserved2', W.WORD), ('lpReserved2', C.POINTER(C.c_byte)),
        ('hStdInput', W.HANDLE), ('hStdOutput', W.HANDLE), ('hStdError', W.HANDLE)]


class PROCESS_INFORMATION(C.Structure):
    _fields_ = [('hProcess', W.HANDLE), ('hThread', W.HANDLE), ('dwProcessId', W.DWORD), ('dwThreadId', W.DWORD)]


class BASIC_LIMIT(C.Structure):
    _fields_ = [('PerProcessUserTimeLimit', C.c_int64), ('PerJobUserTimeLimit', C.c_int64),
        ('LimitFlags', W.DWORD), ('MinimumWorkingSetSize', C.c_size_t), ('MaximumWorkingSetSize', C.c_size_t),
        ('ActiveProcessLimit', W.DWORD), ('Affinity', C.c_size_t), ('PriorityClass', W.DWORD), ('SchedulingClass', W.DWORD)]


class IO_COUNTERS(C.Structure):
    _fields_ = [(name, C.c_uint64) for name in ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
        'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class EXTENDED_LIMIT(C.Structure):
    _fields_ = [('BasicLimitInformation', BASIC_LIMIT), ('IoInfo', IO_COUNTERS),
        ('ProcessMemoryLimit', C.c_size_t), ('JobMemoryLimit', C.c_size_t),
        ('PeakProcessMemoryUsed', C.c_size_t), ('PeakJobMemoryUsed', C.c_size_t)]


class ACCOUNTING(C.Structure):
    _fields_ = [(name, C.c_int64) for name in ('TotalUserTime', 'TotalKernelTime',
        'ThisPeriodTotalUserTime', 'ThisPeriodTotalKernelTime')] + [(name, W.DWORD) for name in
        ('TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses', 'TotalTerminatedProcesses')]


def require(condition, message):
    if not condition: raise ValueError(message)


def api():
    require(os.name == 'nt', 'Windows private desktop required')
    kernel = C.WinDLL('kernel32', use_last_error=True); user = C.WinDLL('user32', use_last_error=True)
    declarations = [
        (kernel, 'CreateJobObjectW', [C.c_void_p, W.LPCWSTR], W.HANDLE),
        (kernel, 'SetInformationJobObject', [W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
        (kernel, 'QueryInformationJobObject', [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
        (kernel, 'AssignProcessToJobObject', [W.HANDLE, W.HANDLE], W.BOOL),
        (kernel, 'IsProcessInJob', [W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL),
        (kernel, 'CreateProcessW', [W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD,
            C.c_void_p, W.LPCWSTR, C.POINTER(STARTUPINFO), C.POINTER(PROCESS_INFORMATION)], W.BOOL),
        (kernel, 'ResumeThread', [W.HANDLE], W.DWORD),
        (kernel, 'TerminateJobObject', [W.HANDLE, W.UINT], W.BOOL),
        (kernel, 'TerminateProcess', [W.HANDLE, W.UINT], W.BOOL),
        (kernel, 'WaitForSingleObject', [W.HANDLE, W.DWORD], W.DWORD),
        (kernel, 'GetExitCodeProcess', [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
        (kernel, 'CloseHandle', [W.HANDLE], W.BOOL),
        (user, 'CreateDesktopW', [W.LPCWSTR, W.LPCWSTR, C.c_void_p, W.DWORD, W.DWORD, C.c_void_p], W.HANDLE),
        (user, 'OpenInputDesktop', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
        (user, 'CloseDesktop', [W.HANDLE], W.BOOL),
        (user, 'GetUserObjectInformationW', [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)], W.BOOL),
    ]
    for library, name, args, result in declarations:
        function = getattr(library, name); function.argtypes = args; function.restype = result
    return kernel, user


def checked(result):
    if not result: raise C.WinError(C.get_last_error())
    return result


def input_desktop(user):
    handle = checked(user.OpenInputDesktop(0, False, 1))
    try:
        needed = W.DWORD(); user.GetUserObjectInformationW(handle, 2, None, 0, C.byref(needed))
        require(0 < needed.value <= 8192, 'Input desktop name unavailable')
        buffer = C.create_unicode_buffer(needed.value // C.sizeof(C.c_wchar) + 1)
        checked(user.GetUserObjectInformationW(handle, 2, buffer, C.sizeof(buffer), C.byref(needed)))
        return buffer.value
    finally: checked(user.CloseDesktop(handle))


class PrivateApplicationProcess:
    """Suspended direct child, private desktop and owned job; no model admission.

    Only a caller that separately admits a production plan/slot may supply the
    registration callback and resume actual application code. This primitive
    never discovers or terminates processes by name or a caller-provided PID.
    """
    def __init__(self, output, *, executable_binding, script_binding, arguments=(), cpu=14):
        self.output = Path(output).resolve()
        require(not self.output.exists(), 'Fresh lifetime evidence directory required')
        require(cpu in (4, 14), 'Only campaign CPU4 or CPU14 allowed')
        require(all(type(v) is str and '\0' not in v for v in arguments), 'Invalid child arguments')
        verify(executable_binding); verify(script_binding)
        self.executable = executable_binding; self.script = script_binding
        self.argv = [executable_binding['path'], '-B', script_binding['path'], *arguments]
        require(len(subprocess.list2cmdline(self.argv)) < 30000, 'Command exceeds process command bound')
        self.cpu = cpu; self.kernel, self.user = api()
        self.desktop_name = 'codex-n1-n4-' + uuid.uuid4().hex
        self.before = input_desktop(self.user)
        self.job = self.desktop = None; self.info = PROCESS_INFORMATION(); self.owner = None
        self.assigned = self.resumed = self.closed = False; self.events = []
        self.output.mkdir(parents=True); self.cancel_path = self.output/'CANCEL'

    def _event(self, kind, **values):
        self.events.append(dict(kind=kind, monotonic=time.monotonic(), **values))

    def spawn_suspended(self):
        require(not self.closed and not self.job and not self.info.hProcess, 'Fresh process lifetime required')
        try:
            verify(self.executable); verify(self.script)
            self.desktop = checked(self.user.CreateDesktopW(self.desktop_name, None, None, 0, 0x83, None))
            self.job = checked(self.kernel.CreateJobObjectW(None, None))
            limits = EXTENDED_LIMIT()
            limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x10 | 0x8  # Kill on close, affinity, count.
            limits.BasicLimitInformation.Affinity = 1 << self.cpu
            limits.BasicLimitInformation.ActiveProcessLimit = 16
            checked(self.kernel.SetInformationJobObject(self.job, 9, C.byref(limits), C.sizeof(limits)))
            startup = STARTUPINFO(); startup.cb = C.sizeof(startup); startup.lpDesktop = self.desktop_name
            startup.dwFlags = 1; startup.wShowWindow = 0
            environment = dict(os.environ)
            environment.update({name: '1' for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')})
            environment.update(CUDA_VISIBLE_DEVICES='-1', PYTHONUTF8='1')
            block = C.create_unicode_buffer('\0'.join(k+'='+v for k, v in sorted(environment.items(), key=lambda kv: kv[0].upper()))+'\0\0')
            # Suspended, no console window, below normal priority, Unicode environment.
            checked(self.kernel.CreateProcessW(self.executable['path'], C.create_unicode_buffer(subprocess.list2cmdline(self.argv)),
                None, None, False, 0x4 | 0x08000000 | 0x4000 | 0x400, block,
                str(Path(self.script['path']).parent), C.byref(startup), C.byref(self.info)))
            checked(self.kernel.AssignProcessToJobObject(self.job, self.info.hProcess)); self.assigned = True
            member = W.BOOL(); checked(self.kernel.IsProcessInJob(self.info.hProcess, self.job, C.byref(member)))
            require(bool(member.value), 'New direct child did not join owned job')
            process = psutil.Process(self.info.dwProcessId); self.owner = identity(process)
            require(process.ppid() == os.getpid() and process.cpu_affinity() == [self.cpu], 'Suspended child parent/affinity mismatch')
            require(Path(process.exe()).resolve() == Path(self.executable['path']).resolve(), 'Suspended executable mismatch')
            require(process.cmdline() == self.argv, 'Suspended command mismatch')
            self._event('spawned_suspended_and_assigned', owner=self.owner, affinity=process.cpu_affinity(),
                argv_sha256=fingerprint(self.argv), job=self.accounting())
            return dict(self.owner)
        except BaseException:
            self.close(grace_seconds=0)
            raise

    def resume(self, register):
        require(self.assigned and not self.resumed and not self.closed and callable(register), 'Suspended registration required')
        try:
            verify(self.executable); verify(self.script)
            register(dict(self.owner), executable_binding=self.executable, argv_sha256=fingerprint(self.argv))
            verify(self.executable); verify(self.script)
            require(input_desktop(self.user) == self.before, 'Input desktop changed before resume')
            previous = self.kernel.ResumeThread(self.info.hThread)
            require(previous == 1, 'Unexpected initial thread suspension state')
            self.resumed = True; self._event('resumed_after_registration')
        except BaseException:
            self.close(grace_seconds=0)
            raise

    def accounting(self):
        require(self.job is not None and not self.closed, 'Owned open job required')
        row = ACCOUNTING()
        checked(self.kernel.QueryInformationJobObject(self.job, 1, C.byref(row), C.sizeof(row), None))
        return dict(active=int(row.ActiveProcesses), total=int(row.TotalProcesses), terminated=int(row.TotalTerminatedProcesses))

    def root_exited(self):
        require(bool(self.info.hProcess), 'Root process handle required')
        status = self.kernel.WaitForSingleObject(self.info.hProcess, 0)
        require(status in (0, 258), 'Root wait failed')
        return status == 0

    def wait_empty(self, timeout):
        require(0 <= timeout <= 150, 'Bounded job wait required')
        until = time.monotonic()+timeout
        while True:
            if self.accounting()['active'] == 0: return True
            if time.monotonic() >= until: return False
            time.sleep(min(0.05, max(0, until-time.monotonic())))

    def close(self, *, grace_seconds=2, force_seconds=10):
        require(0 <= grace_seconds <= 150 and 0 < force_seconds <= 30, 'Bounded cleanup required')
        if self.closed: return self.receipt
        forced = False; empty = False; error = None; final_job = None; exit_code = None
        try:
            self.cancel_path.touch(exist_ok=True); self._event('cancel_requested')
            if self.info.hProcess:
                if self.assigned:
                    if not self.wait_empty(grace_seconds):
                        forced = True; checked(self.kernel.TerminateJobObject(self.job, 125))
                        self._event('owned_job_terminated')
                        require(self.wait_empty(force_seconds), 'Owned job did not become empty after termination')
                    final_job = self.accounting(); empty = final_job['active'] == 0
                else:
                    # Only our newly created suspended child, via its retained handle.
                    forced = True; checked(self.kernel.TerminateProcess(self.info.hProcess, 125))
                    require(self.kernel.WaitForSingleObject(self.info.hProcess, int(force_seconds*1000)) == 0, 'Unassigned suspended root did not exit')
                    empty = True
                require(self.kernel.WaitForSingleObject(self.info.hProcess, int(force_seconds*1000)) == 0, 'Root exit not established')
                code = W.DWORD(); checked(self.kernel.GetExitCodeProcess(self.info.hProcess, C.byref(code))); exit_code = code.value
            else: empty = True
        except BaseException as exc:
            error = type(exc).__name__+': '+str(exc)
        finally:
            cleanup_errors = []
            # The non-inherited job handle is closed even on observation failure;
            # kill-on-close is a final containment action, not an exit proof.
            for field in ('hThread', 'hProcess'):
                handle = getattr(self.info, field)
                if handle:
                    if not self.kernel.CloseHandle(handle): cleanup_errors.append(field)
                    setattr(self.info, field, None)
            if self.job:
                if not self.kernel.CloseHandle(self.job): cleanup_errors.append('job')
                self.job = None
            if self.desktop:
                if not self.user.CloseDesktop(self.desktop): cleanup_errors.append('desktop')
                self.desktop = None
            self.closed = True
            try: after = input_desktop(self.user)
            except BaseException as exc:
                after = None; cleanup_errors.append('input_desktop:'+type(exc).__name__)
            okay = empty and error is None and not cleanup_errors and after == self.before
            self.receipt = dict(status='OWNED_PROCESS_LIFETIME_CLOSED' if okay else 'FAILED_LIFETIME_PRESERVED',
                owner=self.owner, executable=self.executable, script=self.script, argv_sha256=fingerprint(self.argv),
                desktop=self.desktop_name, input_desktop_before=self.before, input_desktop_after=after,
                source_execution_authorized=False, resumed=self.resumed, forced=forced,
                job_empty_verified=empty, final_job=final_job, root_exit_code=exit_code,
                events=self.events, error=error, cleanup_errors=cleanup_errors)
            freeze(self.output/'LIFETIME.json', self.receipt)
        require(okay, 'Owned process cleanup or desktop observation failed; evidence preserved')
        return self.receipt

    def __enter__(self): return self

    def __exit__(self, exc_type, exc, traceback):
        self.close(grace_seconds=0 if exc_type else 2)
