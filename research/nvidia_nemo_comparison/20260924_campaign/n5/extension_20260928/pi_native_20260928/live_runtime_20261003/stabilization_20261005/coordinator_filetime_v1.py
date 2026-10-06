"""Exact current-coordinator FILETIME source binding; README_HOST_STABILIZATION_OPERATIONS_V5.md."""

def bind(raw):
    """Modify only decoder self-exclusion; preserve exact typed-owner provenance."""
    text=raw.decode('utf-8')
    replacements=(
      ('    me=psutil.Process()\n', '''    me=psutil.Process()
    import ctypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    process_times=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(),*(ctypes.byref(item) for item in process_times)):
        raise ctypes.WinError(ctypes.get_last_error())
    current_creation_filetime=process_times[0].value
'''),
      ('                    host[(pid,float(created))]=None\n', '''                    key=(pid,float(created))
                    if key not in host:host[key]=set()
                    if (pk=='pid' and relative.startswith('live-runtime-20261003/audit-preparation/')
                        and path.name=='REGISTERED_OWNER.json' and 'creation_filetime' in value):
                        host[key].add(value['creation_filetime'])
'''),
      ('    for pid,created in host:\n        if pid==me.pid and created==me.create_time():continue\n', '''    for (pid,created),filetimes in host.items():
        if pid==me.pid and ((filetimes and filetimes=={current_creation_filetime})
            or (not filetimes and created==me.create_time())):continue
'''))
    for before,after in replacements:
        if text.count(before)!=1:raise ValueError('Exact current-coordinator decoder boundary required')
        text=text.replace(before,after)
    restored=text
    for before,after in reversed(replacements):
        if restored.count(after)!=1:raise ValueError('Exact reversible current-coordinator boundary required')
        restored=restored.replace(after,before)
    if restored!=raw.decode('utf-8'):raise ValueError('Unrelated decoder change')
    compile(text,'<exact-current-coordinator-filetime-decoder>','exec')
    return text.encode('utf-8')
