# S5 complete paired output comparison

Purpose: execute and analyze the existing 180 development scenes on O0 and O1,
reuse compatible native S4.5 jobs, and package one S5 operating-default decision.
The 60 reserve scenes are metadata-only. No device, audio endpoint, firmware,
scientific H2 configuration, RIR or scene generation is involved.

Inputs: immutable S4.5 scene manifest, accepted captures, output gain policy,
native S4.5 receipts, S0/H2 baseline and validated lifecycle repair. V10 is
read-only context. Outputs: simulation/reports/S5/20260909T130308Z and new
adapters/journals in G:\Just_Peachy_S5\20260909T130308Z. Old payloads are linked.

Gain is applied only when adapting original PCM24 output: O0 uses
1.4125375446227544 once and O1 uses unity. Saved FLOAT adapters and native
PCM16 journals already contain that gain; read those at unity downstream.

## PowerShell

~~~powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s5_runner -v
& 'C:\Users\amiri\anaconda3\python.exe' s5_prepare.py
& 'C:\Users\amiri\anaconda3\python.exe' s5_runner.py
~~~

## Anaconda Prompt or CMD

~~~bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s5_runner -v
"C:\Users\amiri\anaconda3\python.exe" s5_prepare.py
"C:\Users\amiri\anaconda3\python.exe" s5_runner.py
~~~

Preparation freezes protocol and recipes before new full-panel scoring. One
fresh independent H2 subprocess per new output uses .edge-speech-env Python.
The runner resumes compatible completed receipts, preserves failed attempts,
and allows at most one identical retry. Never launch the old S4.5 resume.
The fresh S5 deadline is 2026-09-09 21:03:08 UTC; launch cutoff 20:33:08 UTC.

status.json and heartbeat.jsonl update every 20 seconds. STOP_REQUEST.json in
the report directory prevents the next launch. Interrupted attempts require a
confirmed exited owned process before a retry. Only an exact PID plus process
creation-time match may be terminated. Scorers have separate READMEs/tests.

## Score text and verify every consumed native journal

The pinned MeetEval scorer is isolated from H2. It rechecks each original raw
output hash, existing fixed-gain adapter, full exact native PCM16 journal,
completion events and actual final text. It uses bounded analysis threads with
inner numerical-library threads capped at one. It can run while inference is
ongoing and later resume; add --require-complete for final360-output closure.

PowerShell (from the scripts directory above):

~~~powershell
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s5_text_panel.py --workers 3 --require-complete
~~~

Anaconda Prompt / CMD:

~~~bat
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s5_text_panel.py --workers 3 --require-complete
~~~

Inputs are JOB_MANIFEST.json and bound native receipts; outputs are
text_metrics/CASE/O0.json and O1.json plus TEXT_PANEL_RECEIPT.json and an access
receipt. Native failures remain visible pending/failed and are never scored as
successful zero-error outputs. s5_text_metrics.py has its own fixture README.

For final concurrent scoring, use three text workers and three support workers
(s5_support_panel.py score --workers 3), after the canonical model runner exits.
Keep total analysis worker slots at six or fewer. EXECUTION_NOTES.json records
one earlier brief integration overlap of two four-thread pools as a deviation.

Text-panel boundary fixtures: run the same isolated Python with
-m unittest test_s5_text_panel -v (PowerShell use the & prefix shown above;
Anaconda/CMD use the quoted executable directly).

## Paired statistics

s5_statistics.py sums S/D/I and reference counts before pooled WER. It keeps
matched families intact in the 2,000-replicate within-room paired bootstrap,
with equal-room, leave-one-room and speaker-component deletion sensitivities.
Input: development paired metric dictionaries and DEPENDENCY_BLOCKS.json.
Output: numerical summaries used by the S5 report; it has no file/model side
effects and never treats missing jobs as zero-error observations.

Run numerical fixtures in either shell using the Anaconda Python command
above followed by -m unittest test_s5_statistics -v.

## Aggregate the completed panel

After native inference and both text/support scorers finish, run Anaconda
Python with s5_results.py. PowerShell:

~~~powershell
& 'C:\Users\amiri\anaconda3\python.exe' s5_results.py
~~~

Anaconda Prompt / CMD:

~~~bat
"C:\Users\amiri\anaconda3\python.exe" s5_results.py
~~~

Inputs: completed text/support receipts, native event bindings, frozen scene
and dependency manifests. Outputs: SUMMARY_METRICS, PAIRED_METRICS, completion
ledger, uncertainty/draws, condition/turn/return/region/timing tables and a
deterministic failure catalogue. --allow-partial is for labelled integration
diagnostics only and cannot be used for the final S5 operating decision.

Aggregation fixtures: Anaconda Python -m unittest test_s5_results -v verifies
energy pooling, strict-empty rates, and separation of folded spatial contrasts,
actual speech overlap, adjacent repeats and returns after another speaker.
The inherited support tag close_or_overlap_family is retained as provenance
but refined from frozen scene metadata in RETURN_GROUPS.csv, so sequential F05
spatial contrasts are never reported as overlapping speech.

## Final reports and ZIP

s5_package.py requires a finished numerical panel, qualified FINAL_AUDIT.json,
and a reviewed OUTPUT_DECISION.json bound to the exact SUMMARY_METRICS hash.
It also requires exactly four final PNGs and their current FIGURE_RECEIPT.json,
CAPTIONS.md and plotdata.csv under reports/S5/20260909T130308Z/figures. The
receipt must bind the final numeric inputs, representation summary and renderer;
synthetic preview figures, missing captions and stale hashes are refused.
It will not choose an output from incomplete results. It creates the detailed
report, V10 insertion proposal, next-phase context and local artifact index,
then verifies one ZIP by CRC and every member SHA256. It refuses audio,
vectors, weights, master Word documents and nested ZIPs.

The report embeds all four images with portable relative paths. Resource and
runtime tables use FINAL_AUDIT observations: sampled model RAM, OS RAM, mapped
C:/G: SSD health/free space, bounded new logical bytes and separate fresh versus
historical child-wall sums. They are audit snapshots, not continuous peaks or a
CM5 qualification. Gate counts and support/quiet raw versus native-adapter RMS
distributions keep missing timing and zero-RMS support explicit.

Both commands below also create RESERVE_PROTECTION.json. It joins the final
audit's bound execution guards with the current aggregate, package and figure
guards, checks the exact 180-case development allowlist and zero recorded reserve
task accesses, and distinguishes allowed parsing of all 240 metadata rows. This
is recorded application evidence, not an OS-wide file-access trace. Missing
guard receipts never imply zero. LOCAL_ARTIFACT_INDEX includes selected shallow
staging/s5_* setup/test/review receipts and logs, including numbered review
folders; it does not traverse the isolated dependency environment.

Run in PowerShell:

~~~powershell
& 'C:\Users\amiri\anaconda3\python.exe' s5_package.py --reports-only
& 'C:\Users\amiri\anaconda3\python.exe' s5_package.py
~~~

Run in Anaconda Prompt/CMD:

~~~bat
"C:\Users\amiri\anaconda3\python.exe" s5_package.py --reports-only
"C:\Users\amiri\anaconda3\python.exe" s5_package.py
~~~

Complete the final figure renderer, its visual review, final audit and consolidated
test receipt first. The first command supports report QA before packaging; it
does not produce the ZIP. Output ZIP:
simulation/handoffs/S5_CHATGPT_HANDOFF_20260909T130308Z.zip, target10MiB and
hard cap20MiB. PACKAGE_RECEIPT.json records the actual size/hash/wall duration.
Package fixtures use temporary files and synthetic resource/guard/figure
receipts only, without report generation, models, task audio or hardware.
They also check that prose spacing preserves model IDs, paths, timestamps,
thousands separators and hashes. These formatting checks do not change scores.

~~~powershell
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s5_package -v
& 'C:\Users\amiri\anaconda3\python.exe' -m py_compile s5_package.py test_s5_package.py
~~~

~~~bat
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s5_package -v
"C:\Users\amiri\anaconda3\python.exe" -m py_compile s5_package.py test_s5_package.py
~~~

Final status is published atomically only after
the ZIP passes validation. The initial run_manifest stays frozen; final status
and audit/decision/reserve bindings are in RUN_MANIFEST_FINAL.json. Its elapsed
time ends at package assembly start so the ZIP contains an honest end-to-end
timing boundary; PACKAGE_RECEIPT.json extends the elapsed time through completed
ZIP verification. New bytes/free space remain explicitly at the audit boundary.
