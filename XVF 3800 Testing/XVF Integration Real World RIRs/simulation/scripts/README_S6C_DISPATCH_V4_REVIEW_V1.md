# Dispatcher V4 independent source and proof review

Purpose: verify the exact dispatcher V4 source differs from held V3 only through its explicit new B36 schema/source/preparation/closure branch and maintained README references. This does not run the dispatcher, admit a real queue, scan scientific data, inspect actual runtime owners or launch models.

Inputs: exact pinned s6c_paced_dispatch_v3.py, s6c_paced_dispatch_v4.py and reviewed s6c_paced_b36_fast_v2.py in this scripts directory, plus their source dependencies when the metadata-only B36 module is imported. The test uses private temporary launch/proof JSON objects. It checks successful proof delegation and rejects mismatched status, manifest, count, parent identity/argv, quiet authority, plan, helper and active/unknown owner state. It reverses only the declared source changes and compares the whole module AST against V3, preserving heartbeat, deadlines, launches, failure outcomes and other original completion branches.

Output: a new REVIEW_RECEIPT.json with exact source/README bindings, individual check names and scope. The output directory must not exist; private temporary files are removed by the test. No original source is edited. This README covers s6c_dispatch_v4_review_v1.py.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B s6c_dispatch_v4_review_v1.py --output '..\reports\S6C\20260910T123540Z\independent_review\dispatch_v4_design_v1'
```

Anaconda Prompt / CMD (uses the existing interpreter directly; no environment install):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_dispatch_v4_review_v1.py --output "..\reports\S6C\20260910T123540Z\independent_review\dispatch_v4_design_v1"
```

For a repeat verification choose a fresh output directory. A changed pinned production source requires a separately reviewed version, not a relaxed hash check. The helper does not substitute its synthetic proof for the actual reviewed B36 batch admission API.
