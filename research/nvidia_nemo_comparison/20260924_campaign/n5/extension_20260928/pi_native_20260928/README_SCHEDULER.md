# Bounded scheduler-memory repair on CM5

The first native V2 D1 push aborted while requesting 1262.52 MB in `ggml_backend_sched_split_graph`. Its retained source reserves 65,536 graph nodes; ggml allocates split tensor metadata proportional to this maximum. This is not evidence that 100M model weights alone consume 1.26 GB. The fresh candidate changes only the session capacity to 8,192 and retains the existing 95%-capacity failure guard. Model weights, feature extraction, chunk/cache recipe and native thread count remain unchanged. Correctness, actual node count and memory must be retested. This is a D1 candidate, not automatic acceptance for all ASR graph sizes.

`prepare_scheduler_bundle_v1.py` runs in the existing WSL tool workspace, reads the retained source and ARM64 objects, checks the known session source hash, and packages them with per-file hashes. It performs no download or build. Inputs are the original pinned source, 28 ASR objects, static libraries and three ggml shared libraries. Outputs are a private fresh bundle.tar.gz and bundle.tar.json. Source modifications only occur later in a fresh extracted copy on the Pi.

`build_scheduler_v1.py` runs natively on CM5 using its installed GCC 12.2 and binutils. It checks boot ID, admission/input hashes, CPUs 2/3, 850 MiB available RAM and 5 GiB free disk. It enforces a 768 MiB hard virtual-address limit inherited by compiler/linker children and disables core dumps. Under a bounded systemd unit it extracts at most 96 MiB of hash-checked regular inputs, compiles the single modified session translation unit, replaces that member of a copied runtime archive, and relinks with the retained ARM64 objects. This is a native partial rebuild using original cross-compiled objects, not a clean full native rebuild or Cortex-A76 kernel optimization. The installed CMake is 3.25 while the project requires 3.26; direct compile/archive/link uses the original recorded flags and avoids changing that requirement or installing software.

Outputs: BUILD_OWNER.json, BUILD_RESULT.json, individual command logs, fresh inputs/output directories and libnemo_speech_asr.so. All raw build files stay private. A successful build is not a functioning diarizer. Load the candidate only in a fresh derivative with input/library hashes, the original resource cap, full output coverage, repeat/EOF/reset checks and measured graph node count. Preserve original runtime and failure evidence.

## PowerShell / Anaconda PowerShell

From this code directory, package retained inputs into a fresh private output path:

```powershell
Get-Content -Raw .\prepare_scheduler_bundle_v1.py | wsl.exe -d Ubuntu -- python3 - /mnt/g/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/bundle.tar.gz
```

Copy the bundle, its manifest, builder, this README and a fresh BUILD_ADMISSION.json to the fresh target `~/JustPeachy/research/nemotron-20260928/scheduler-native-v1` using the verified SSH key/host arguments in README.md. The admission binds every transferred input hash, boot ID, expiry and output/resource bounds. Then:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-scheduler-build-v1 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 python3 -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/scheduler-native-v1/build_scheduler_v1.py'
```

## CMD / Anaconda Prompt

Use `type prepare_scheduler_bundle_v1.py | wsl.exe -d Ubuntu -- python3 - FULL_WSL_PRIVATE_OUTPUT_PATH` for packaging. Use the same scp/ssh commands, with the entire remote command in double quotes. No Windows environment activation or downloads are needed.

The host's combined 1 GiB output allowance includes these files. Fresh target build admission caps retained bundle/expanded source/outputs at 160 MiB; this is additional to the first 160 MiB model stage. After every run verify exact PID/start-tick/boot-ID closure, service exit status, file hashes and storage usage. Do not reuse a terminal PASS as stage acceptance or overwrite a previous attempt.
