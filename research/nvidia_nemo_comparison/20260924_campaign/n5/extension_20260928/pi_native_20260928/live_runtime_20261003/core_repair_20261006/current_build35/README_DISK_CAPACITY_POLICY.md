# Capacity-controlled capture and native output workspace

Purpose: repair ordinary manual-stop recording so disk capacity determines its
source and finite drainage allowance. An accumulated analysis lag alone does not
discard or skip accepted speech. The normal controller explicitly uses
`max_backlog_seconds=None`; timed/headless/developer policies still default to
120 seconds unless the operator explicitly supplies another policy. A finite
backlog policy still stops capture at its boundary. This is not real-time
qualification: actual ASR/speaker lag must remain visible, and larger lane skew
can expire identity evidence and therefore produce Unknown.
Production admission currently permits None/extended capacity drainage only
for reviewed ordinary manual-stop sessions without the optional refiner. A
timed None-backlog endurance experiment needs its own fresh explicit admission.

The native C ABI copies all retained probability rows. This code does not invent
a range API. It starts with an empty workspace and grows only to the current
reported retained row count (`count-base`). Absolute source/final frame counts,
sample ceiling, 10 ms output clock, finite probabilities and immutable emitted
copies retain their checks. Before growth/copy, allocation admission accounts
the old live workspace, new workspace, new emitted float32 rows and two possible
boolean validation masks. Current virtual memory already includes the old
allocation; its additional reservation must fit the effective soft/hard AS
limit and preserve 192 MiB physically available RAM. No AS limit is raised here.
The source endpoint ceiling is checked before a potentially large allocation.

Ordinary policy drainage is a finite source-capacity duration. The engine,
inherited watcher, manager Stop watchdog and session deadline consume the same
policy value. The exact installed profile validator normally caps lane drain
at 3600 seconds. `capacity_drain_profile.py` verifies source hash, origin,
loaded method AST and original class, then changes only that upper bound for
the exact manual-stop policy. A reverse AST check proves every other condition
is unchanged. Installed files/classes are never patched.

Finite load/cleanup deadlines, effective AS, 192 MiB running/850 MiB initial
physical floors, CPU, source continuity, bounded queues, individual I/O sizes,
disk reserve and failure closure remain active. Optional refinement keeps a
separate conservative finite latency admission; disabling the capture lag cutoff
does not admit refinement with growing backlog. If Stop cannot finish within
the admitted finite drain, the recording remains incomplete with evidence
retained. No silent successful-drain or model-quality claim follows from host
fixtures.

Inputs: exact immutable build33 package/PIN
`2889a2bddc9b6cb65c150510e87db978eb5fb24e4ffa22809b1623d45234b61e`,
the seven preserved source pairs in `preserved33`, the current candidate
eight Python runtime files and this README, and the hash-pinned installed
`research_profiles_v3.py` (SHA
`9f27f2c4ff1132a18e011c7e068594c1cb01eefe86350303d1806e8f46400b38`).
The merged `installed_engine.py` additionally contains the separately reviewed
S7 projection helper binding; that helper and visible GUI lag status are supplied
by the caption agent's paired change.

Outputs: one fresh private registered host evidence folder containing exact
source backup and independent restored/readback copies, REGISTERED_OWNER,
SOURCE_CLOSED before tests, SOURCE_UNCHANGED after tests, test output, RESULT and
HOST_EXIT. An independent PowerShell process must verify exact owner absence and
write HOST_CLOSED. These are host fixture results; native Start/Stop/Discard with
the actual capacity policy and native output equivalence remain pending.

Run only when the root coordinator grants one CPU14 host slot. The runner sets
CPU14 and records its process creation FILETIME before reading project source,
sets numerical-library threads to one, verifies the source pins, closes source
backup/restoration, and runs 19 focused cases. It does not load models or run
SSH/native action. Synthetic arrays contain fixture probabilities only.

PowerShell:

```powershell
$base='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/disk_capacity_policy_20261006'
$private='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation'
$out=Join-Path $private ('disk-capacity-host-'+[guid]::NewGuid().ToString('N'))
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' (Join-Path $base 'run_host_disk_capacity_checks.py') --output $out
$exitCode=$LASTEXITCODE
if($exitCode -ne 0){throw "Host checks failed with exit $exitCode"}
```

Command Prompt or Anaconda Prompt (the exact pinned interpreter is intentional;
use a fresh unique output name):

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\disk_capacity_policy_20261006\run_host_disk_capacity_checks.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\disk-capacity-host-UNIQUE"
```

State: HOST19 PASS (19 tests, zero failures/errors/skips) under registered CPU14
PID69496 / creation FILETIME134357967652670898. Exact owner absence and all
461 source/backup/restored pairs were independently checked. Evidence root:
`Q/audit-preparation/disk-capacity-host-39532629e8794413947352f932a4be1d`
where Q is the private local live-runtime-20261003 path in the commands.
The outer invocation did not capture Python's exit code; HOST_CLOSED preserves
`exit_code_observed:false`. Do not call this a naturally observed Python exit0.
The root coordinator accepted the recorded PASS plus exact owner absence without
an identical repeat. Future invocations above capture the code explicitly.
The README evidence update has separate backup/restore pins; the tested runtime,
fixtures and runner remain unchanged. Native validation remains pending.
Frozen build33 is unchanged; do not copy these drafts into an installed release.
