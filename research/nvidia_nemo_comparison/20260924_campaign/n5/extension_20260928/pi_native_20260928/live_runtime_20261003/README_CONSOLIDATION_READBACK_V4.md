# Consolidation01 host readback repair

`readback_desktop_consolidation_v4.py` restores and verifies the completed actual01 desktop archive. It does not SSH, consolidate again, activate, start models or modify Desktop. V3's first host readback restored46 archive files, then failed copying the147,524-byte outer result because its write readback default was65,536bytes. Failed readback01 and the executed V3 source remain unchanged.

The new host reader loads only the exact executed V3 source SHA1a9291504bc94a219a29de4691456bdddd4845c7c1e39ed4b0519c78ebd7d5d0. Its original archive decoder, membership/hash/owned-shortcut checks, natural owner closure and ordinary65,536-byte archive write/readback remain unchanged. Only the two exact top-level `RESULT.json.backup` and `RESULT.json.restore` copies permit262,144bytes, matching the existing bounded outer input. Other destinations or larger copies are refused before writing.

Inputs: exact private `operation-desktop-consolidation-01` executed source/backups, actual result and closure. Output: fresh `desktop-consolidation-01-readback-02`, complete archive files, independent result/source copies and VERIFY. C50GiB/G75GiB plus16MiB reserves stay in force. Python pins CPU14 and publishes its actual owner before project reads.

PowerShell (set `$N` and `$Q` to the canonical runtime-source/private-evidence directories):

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$N/readback_desktop_consolidation_v4.py" --operation "$Q/operation-desktop-consolidation-01" --output "$Q/desktop-consolidation-01-readback-02"
```

Command Prompt / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%\readback_desktop_consolidation_v4.py" --operation "%Q%\operation-desktop-consolidation-01" --output "%Q%\desktop-consolidation-01-readback-02"
```

This exact-scope reader refuses reused output or another operation. The changed-boundary checks cover the real outer result larger than64KiB and refuse a different destination or262,145bytes; no additional native run is required.
