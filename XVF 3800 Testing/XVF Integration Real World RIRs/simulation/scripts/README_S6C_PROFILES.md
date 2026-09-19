# Compile real S6C profiles

`s6c_profiles.py` translates the previously registered design through the actual
application `ResearchProfile.from_dict` v3 branch. Its purpose is to reject
unknown/inactive parameters before new model execution. Inputs are the immutable
registered design and current reviewed application schema. Outputs are exact
JSON profiles, their hashes/active field maps and
`reports/S6C/20260910T123540Z/EFFECTIVE_PROFILE_REGISTRY_V1.json`.

SAME routes expand into O0/O0 and O1/O1; explicit split routes keep ASR and
identity tap declarations. Already prepared O0 +3 dB and O1 unity inputs are
consumed at unity. This compiler does not create galleries, load models, play
audio or claim a registered condition has executed. A naming profile must later
receive an admitted isolated research gallery. Legacy N00 uses .5 s single-lane
R0 evidence in the mature API role for matched prototype updating; this is not
the new long-mature/dual evidence condition.

Run only after source review and before freezing an inference epoch. Existing
compiled profiles are immutable; a code/setting correction requires a named
revision, not overwriting results or a running source tree.

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' .\s6c_profiles.py
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_profiles.py
```

Successful output gives validated candidate/route counts and registry path. No
success is inferred after validation exceptions. The same command resumes by
returning the completed immutable registry. Resource/stop/rollback conventions
are in README_S6C.md; full run/resume commands belong to the execution entry.
