# Exact current-traversal storage admission candidate

`s6c_admission_fast_v1.py` offers a drop-in `tree_bytes(root)` callable and
model-free tests/benchmark. It uses recursive `os.scandir` and each current
`DirEntry.stat().st_size` instead of discarding enumeration metadata and doing a
separate `Path.stat` on every file. Windows can supply ordinary-file metadata
from the current directory enumeration. No file lists, byte counts or timestamps
are cached between calls. It sums the observed file sizes, without rounding,
sampling, estimates or a timed admission cache.

Directory symlinks are skipped and file symlinks follow their targets, matching
the original os.walk default. Hardlinks count once per directory entry, also
matching the original cap. Broken file links reject. Unreadable directories fail
closed rather than accepting the original os.walk silent-skip behavior. Optional
symlink fixture inability is recorded; it is never reported as a tested pass.

A traversal of a changing filesystem is not an atomic snapshot. Concurrent
writers can change files between entries under both implementations. The proposed
coordinator must keep the existing pending-job reservations and repeat the full
scan at every admission, along with exact free-space, RAM, stop/deadline and cap
checks. No assumption that other report writers stopped is introduced.

Inputs: REPORT, STAGING and PAYLOAD paths from the unchanged common helper;
stable temporary files for fixtures; the preserved original scan receipt for
benchmark context. Outputs: versioned SCANDIR_FIXTURES and SCANDIR_BENCHMARK JSON
receipts under the current S6C report's `orchestration_review` directory, with
exact source bindings, byte/entry counts, elapsed and observer CPU time.

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' s6c_admission_fast_v1.py --test --version v1
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' s6c_admission_fast_v1.py --benchmark --version v1
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_admission_fast_v1.py --test --version v1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_admission_fast_v1.py --benchmark --version v1
```

This helper is a prospective optimization candidate. It does not patch or launch
the active coordinator, a frozen source or a native worker. After independent
review, a separately bound orchestration overlay may substitute this callable
for coordinator storage enumeration while keeping the original frozen epoch2
worker, job identities, hash validation, output reservations and process
accounting. Such a launch must record its distinct orchestration source/receipt;
it must not claim the original coordinator bytes executed unchanged.
