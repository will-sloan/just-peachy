# N3 traceable text layers

`n3_text.py` supplies an independently toggleable, finite ITN layer. Input is
formatted text, a hash-bound compiled grammar JSON, a Boolean toggle and optional
explicit contextual mappings. Output contains the untouched original, transformed
text, original/output character ranges for every edit and a separate empty manual
correction list. Actual user corrections remain in the existing review store.

The runtime uses Python's standard library only. It does not rewrite missing
words, replace similar names globally or infer a spoken name from speaker identity.
The grammar build, notices, accepted coverage and PowerShell/CMD/Anaconda commands
are documented in the campaign `n3/README_ITN.md`.

Syntax check from the worktree in PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -m py_compile prototype/app/n3_text.py
```

CMD or Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m py_compile prototype/app/n3_text.py
```

ITN defaults off. Explicit mappings are separate from that switch. No personal
mapping is created by the campaign; test fixture approvals apply only to fixture
text. The original ASR archive is never overwritten by a normalization result.
