# Geometry dispatcher transport V2

Purpose: transmit the already reviewed geometry harness/adapter and fresh admission through strict SSH standard input, avoiding the Windows32767-character process command-line limit. V1 failed locally with WinError206 before any remote staging or numerical execution. Preserve it and its failed receipt. No model, threshold, resource or harness behavior changes.

Inputs/outputs, guards and native job are described in README_GEOMETRY_V2.md. V2 writes a new private evidence directory and stages a new Pi run; it uses the same600second/768MiB/CPU2,3 bounds. Never reuse a populated run ID. The pending1GiB integrated test is unrelated and unapproved.

PowerShell, from this folder:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' dispatch_geometry_v2.py --profile native_v3_streaming --kernel generic --run-id d1-geometry-stream-generic-v2 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V5.json'
```

CMD/Anaconda Prompt use the same arguments with double-quoted paths, omit `&`, and use `cd /d` to this folder first. No activation, installation or download is needed. For A76 use a fresh run ID and a successfully independently reviewed `--reference` as documented in README_GEOMETRY_V2.md. Expired census/admission requires fresh evidence, not bypassing guards.
