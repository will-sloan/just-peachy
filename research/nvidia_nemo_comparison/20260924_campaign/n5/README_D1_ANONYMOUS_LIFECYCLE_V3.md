# D1 anonymous candidate: two-CPU qualification

Purpose: test the unchanged d1-anonymous-v1 application derivative with ASR
and native D1 allowed to execute concurrently on exactly CPUs 4 and 14. Each
model retains one numerical thread, GPU off. The coordinator/supervisor share
CPU14, so at most two distinct CPU logical processors are admitted. This is a
resource-configuration experiment, not a one-core speed comparison or a model
change. The candidate V2 one-core attempt hit the existing 60-second ASR drain
gate and remains FAILED_PRESERVED; its unforced process exit does not mean pass.

Inputs/outputs, source/model/audio hashes, 600-second/128-MiB admission, drive
reserves, fixed packaging cutoff and acceptance gates are the same as described
in README_D1_ANONYMOUS_LIFECYCLE_V2.md. The paired parent V2 provides complete
one-core semantic reference evidence; reusing it avoids another unchanged neural
run. Candidate captions/activity must match it, but timings are not a paired
speed benchmark because the affinity differs. The 60-second drain is unchanged.

The fresh private_application_two_cpu_v1.py is derived from the existing N4 V3
private-desktop/job helper. Its only functional change restricts the owned job
to the exact [4,14] mask and verifies that affinity before resume. Process
creation identities, suspended registration, descendant cleanup, input-desktop
checks and fail-closed behavior are retained. It has no standalone launcher;
only the admitted runner may supply a verified executable/script and resume
the job. No visible GUI, mouse/keyboard use, microphone, playback, training,
personal data or Pi access occurs. No earlier helper or release is modified.

PowerShell:

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$d1Py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $d1Py -B -m unittest test_d1_anonymous_lifecycle_v3 -v
& $d1Py -B prepare_d1_anonymous_lifecycle_v3.py --name d1-anonymous-lifecycle-candidate-v3 --arm candidate --reference-result 'G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-anonymous-lifecycle-parent-v2\RESULT.json'
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "D1_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%D1_PY%" -B -m unittest test_d1_anonymous_lifecycle_v3 -v
"%D1_PY%" -B prepare_d1_anonymous_lifecycle_v3.py --name d1-anonymous-lifecycle-candidate-v3 --arm candidate --reference-result "G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-anonymous-lifecycle-parent-v2\RESULT.json"
```

No installation/activation is needed. Use fresh names; active ownership blocks
admission. Thirteen model-free gates include concurrent-deletion accounting,
encoder bypass/parity refusals and inherited lifecycle closure checks. Actual
two-CPU admission still requires separate saved-file GUI evidence. Passing this
one-file smoke does not complete N4/N5 or establish sustained real-time speed.
