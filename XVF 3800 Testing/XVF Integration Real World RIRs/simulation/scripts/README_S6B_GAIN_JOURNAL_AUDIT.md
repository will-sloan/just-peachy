# Independent R6 gain-input/native-journal audit

`s6b_gain_journal_audit.py` closes a narrow validation gap in the frozen campaign:
gain-index WAVs have exact file hashes but no PCM-body hash in the original
index. The frozen runner verifies those WAV bytes and final journal length.
This separate read-only audit decodes each prepared mono16k FLOAT WAV to float32
and derives its journal bytes using the frozen AudioJournal conversion:
`round(clip(values, -1.0, 0.999969) * 32768.0).astype('<i2')`.
It compares those bytes via SHA256 and length against each completed
native journal. It does not modify the runner, inputs, model state or receipts,
and never reapplies gain, renders new scenes or launches inference. Tiny
synthetic PCM16/FLOAT conversion fixtures exercise the actual frozen
WavSource/AudioJournal on each invocation, including the107sample tail.

Inputs are the frozen epoch manifest, bound gain input index, actual prepared
gain WAVs, and COMPLETE native receipts/journals for R6 recipes. The immutable
expected PCM index and its separate binding are stored under
REPORT/independent_review. Each invocation writes a new timestamped audit plus
a latest pointer. Missing jobs are explicitly PARTIAL_PASS; any mismatch is FAIL
and returns a nonzero exit status. COMPLETE_PASS requires every requested recipe,
scene and both taps in the chosen panel. An empty or incomplete recipe is never
treated as complete. Historical attempts are retained.

## PowerShell

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6b_gain_journal_audit.py' --report 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6B\20260909T230840Z' --epoch epoch2 --panel challenge --recipes R6 R6_FULL_RMS
```

## Anaconda Prompt / CMD

```bat
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6b_gain_journal_audit.py" --report "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6B\20260909T230840Z" --epoch epoch2 --panel challenge --recipes R6 R6_FULL_RMS
```

After an explicitly retained all-bank gain recipe finishes, use `--panel all`
and exactly its retained recipe IDs. The first invocation hashes all480prepared
gain WAVs and derives their PCM16 journal hashes; subsequent audits reuse their externally bound immutable index
and validate current completed journal bytes. This relies on the frozen input
contract after initial admission; each native receipt's exact input binding must
still match the expected index. No prediction or accuracy claim is inferred from
PCM equality.

The first attempted direct PCM-body helper failed on FLOAT encoding before
writing an index or modifying any native artifact. The corrected v2 expected
index records its exact source subtype, conversion fixture results and frozen
audio module binding. The audit rejects channels/rates outside this prepared
mono16k scope rather than pretending to validate a resampling path.

If Windows temporarily denies replacement of the convenience LATEST pointer,
the timestamped audit may already be complete. Inspect that immutable audit and
the staged pointer before repeating work. Verify the staged pointer's referenced
audit SHA256, then atomically move only that invocation's existing temporary
pointer over LATEST with bounded retries. Do not rewrite the completed audit or
rerun inference. On2026-09-10 the176-journal COMPLETE_PASS audit was preserved
before this narrow pointer failure; its staged pointer was committed afterward
without repeating the audit.
