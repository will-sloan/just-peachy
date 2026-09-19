# Final narrative copies and one encoding correction

Purpose: preserve the bound V1 documents and create the final V2 document set.
Inputs: the13 exact V1 preparation outputs, OPERATING_COMMANDS.md and the
independently checked PACED_NATIVE_RESULTS.md. The only text change replaces
a valid en dash with plain 'to' in the1.98 to2.29-second startup range. No metric,
experiment or acceptance status is changed.

Outputs:15 Markdown copies and NARRATIVE_COPY_RECEIPT.json in handoff_final_v2.
Existing output rejects. All original V1 input hashes are checked and preserved.
Final independent acceptance and packaging remain separate.

PowerShell:

~~~powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& "$s6cRepo\.edge-speech-env\python.exe" -B "$s6cSim\scripts\s6c_final_narrative_copy_v2.py"
~~~

Anaconda Prompt / CMD:

~~~bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%S6C_REPO%\.edge-speech-env\python.exe" -B "%S6C_SIM%\scripts\s6c_final_narrative_copy_v2.py"
~~~

The actual copy validates the unique correction and absence of invalid
replacement characters in all resulting documents; it runs no models or scorers.

The original UTF-8 was valid. An initial read-only check incorrectly attributed a
console replacement glyph to the file; the first pre-write attempt rejected that
assumption and produced no output. The actual byte-level check established U+2013,
and the resulting change is only plain-text range wording for portability.
