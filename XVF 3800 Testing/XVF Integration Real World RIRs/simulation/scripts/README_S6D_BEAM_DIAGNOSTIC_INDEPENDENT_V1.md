# Independent diagnostic closure probes

`s6d_beam_diagnostic_independent_checks_v1.py` adds five focused model-free checks for frozen diagnostic runner5b391754 and queue builder40199ae6. It checks joint input/proof relabeling against the actual admitted stream, duplicate streams and boolean frame declarations, an identity spool aliasing the ASR path, open finalizer handles, and C/core rejection before process/dependency/queue work. Every paired-spool case first passes the positive validator.

Inputs are a reviewed source directory containing the frozen seven-file diagnostic closure source graph and a fresh G review-fixture directory. It reads only source files, the existing pure completion-dictionary constructor and its own deterministic32kB byte fixtures. It launches no model, native audio session, process query, UI, device, queue or approval. Outputs are small synthetic source/spool bytes and `RECEIPT.json`. All new files stay under the chosen G output. The original three-beam tests are not rerun.

PowerShell:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_beam_diagnostic_independent_checks_v1.py" --source-root 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_diagnostic_v2_independent\source' --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_diagnostic_v2_independent\independent5'
```

Anaconda Prompt / Windows CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_beam_diagnostic_independent_checks_v1.py" --source-root "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_diagnostic_v2_independent\source" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_diagnostic_v2_independent\independent5"
```

Use a new output suffix if occupied. A PASS supports only these source/fixture gates; it does not accept actual528 capture inputs,48-control reuse, four-worker allocation, a future80GiB protocol migration or production execution.
