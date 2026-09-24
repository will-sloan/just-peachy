# Read-only host resource sampling

`resources.py` observes one exact PID plus creation timestamp and its children.
It starts no model and never signals a target. A reused PID stops collection.
Use only an owned campaign process. Outputs are private per-sample JSONL and a
peak/limitation receipt. It records Windows RSS, USS, private commit, process
CPU and thread counts separately; Linux PSS is separate if exposed. RSS sums
are explicitly not unique physical totals. Exit observation is not proof that
all external workers released resources. WSL/cgroup workers need their own data.

Optional `--gpu` invokes the installed `nvidia-smi` read-only query. Device-wide
usage is not per-model allocator memory; WDDM N/A and allocated/reserved remain
unavailable. Sampling can miss peaks. This probe alone establishes neither an
isolated model benchmark nor a complete GUI stack's 2-GB fit.

PowerShell example (replace the two identity values with the owned process's
verified receipt, and choose a fresh output directory):

```powershell
& 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\resources.py --pid 12345 --created 1790280000.0 --seconds 60 --interval 1 --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\resource-observation-v1'
```

CMD/Anaconda Prompt:

```bat
"G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\resources.py --pid 12345 --created 1790280000.0 --seconds 60 --interval 1 --output G:\Just_Peachy_N1\20260924_campaign\local\n4\resource-observation-v1
```

Arguments `--pid`, `--created` and `--output` are required; values above are
illustrations and do not identify a live process. Duration is bounded to one
hour, interval to 0.1–10 seconds. The observer uses CPU4/BelowNormal. For true
controlled measurements stop overlapping campaign model work through its owning
supervisor, then bind cold/warm start, gallery, GUI, worker, cache, logging and
teardown phases. Do not terminate unrelated processes.

`planning_tier()` is a conservative reporting helper. It needs an accounted
whole-application byte count and explicit controlled-scope flag. Under 1.5 GiB
leaves 0.5 GiB of a 2-GiB system for OS/display/audio; larger rows remain visible.
The function never claims Pi qualification or deployment readiness. Missing
memory stays UNKNOWN, and CPU pacing remains a separate condition.
