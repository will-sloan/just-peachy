# ARM64 build and static audit

These tools prepare Linux aarch64 artifacts while the CM5 is offline. They do
not open audio, USB or GPIO, start the GUI, load models, or measure CM5 resources.
The inputs are the pinned official Arm compiler archive, PyPI host tool wheels,
the existing 13 publisher-verified target wheels, and reviewed native sources.
Outputs are private build tools, immutable audit receipts and build artifacts.
No personal data is used. N4 selection and final software acceptance are pending.

Use PowerShell (no Anaconda activation needed):

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
wsl.exe -d Ubuntu -- python3 /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/fetch_build_tools.py --output /mnt/g/Just_Peachy_N1/20260924_campaign/local/n5/downloads
wsl.exe -d Ubuntu -- python3 /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/audit_arm64.py --wheelhouse '/mnt/g/Just_Peachy_PROTO1/arm64 cp311 wheels' --publisher-receipt /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/ARM64_WHEEL_PUBLISHER.json --output /mnt/g/Just_Peachy_N1/20260924_campaign/local/n5/ARM64_WHEELS_AUDIT_v2.json
```

CMD or Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
wsl.exe -d Ubuntu -- python3 /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/fetch_build_tools.py --output /mnt/g/Just_Peachy_N1/20260924_campaign/local/n5/downloads
wsl.exe -d Ubuntu -- python3 /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/audit_arm64.py --wheelhouse "/mnt/g/Just_Peachy_PROTO1/arm64 cp311 wheels" --publisher-receipt /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/ARM64_WHEEL_PUBLISHER.json --output /mnt/g/Just_Peachy_N1/20260924_campaign/local/n5/ARM64_WHEELS_AUDIT_v2.json
```

Use a new output filename for a rerun; audits refuse to replace evidence. The
audit accepts `--native DIRECTORY` instead of wheel arguments for built ELF
libraries. It checks architecture, direct dependency inventory and required
GLIBC/GLIBCXX/CXXABI versions against Bookworm ceilings. Static success is not a
dynamic loader/model smoke, instruction-set proof, or measured 2GB readiness.
`fetch_build_tools.py` reuses exact verified files; hash changes fail closed.
The compiler stays private and is not included in deployment archives.

## Native build, package and emulated loader

`build_native_arm64.py` consumes verified downloads and the three pinned source
archives in ../assets/runtime_receipt.json. It reconstructs sources in a fresh
private WSL folder, applies the same single-thread scheduler change as N2, uses
Arm GNU 12.3.rel1 / CMake 3.30.5 / Ninja 1.11.1.1, and builds one worker at nice10.
ISA is generic armv8-a. CUDA, OpenMP, KleidiAI, microphone, servers, TTS/NMT and
training dependencies are disabled. Linux CPU affinity is one logical CPU; it
does not assert an exact physical-core mapping to the Windows host. This is
build evidence, never an isolated inference resource measurement.

The following commands work identically in PowerShell and CMD/Anaconda Prompt.
Use fresh v2 output paths for a rerun; the actual first build is v1.

```text
wsl.exe -d Ubuntu -- python3 /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/build_native_arm64.py --downloads /mnt/g/Just_Peachy_N1/20260924_campaign/local/n5/downloads --assets /mnt/g/Just_Peachy_N1/20260924_campaign/local/assets --source-receipt /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/assets/runtime_receipt.json --output /home/amiri/jp-n5-native-v2
wsl.exe -d Ubuntu -- python3 /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/package_native.py --build /home/amiri/jp-n5-native-v2 --stage /home/amiri/jp-n5-runtime-v2 --archive /mnt/g/Just_Peachy_N1/20260924_campaign/local/n5/releases/nemo-speech-arm64-engineering-v2.tar.gz
wsl.exe -d Ubuntu -- python3 /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/emulate_loader.py --build /home/amiri/jp-n5-native-v2 --runtime /home/amiri/jp-n5-runtime-v2 --output /home/amiri/jp-n5-loader-v3
```

`package_native.py` preserves SONAME symlinks and uses the CLI's required
bin/../lib layout, includes source/patch receipts and 12 license/notice files,
and excludes models, sysroot and compiler. `emulate_loader.py` downloads the
Ubuntu apt-index-hash-pinned QEMU package into its output folder and unpacks it
without installing packages or binfmt. It compiles a tiny ARM64 dlopen/version
probe, runs only CLI help/version and that probe through the toolchain sysroot.
Outputs are command logs plus EMULATED_LOADER.json. No model, WAV or device is
opened. Success is EMULATED_LOADER_SMOKE_PASS, not ARM64_FUNCTIONAL_SMOKE.

The first Windows HTTPS downloader failed certificate verification. WSL's normal
verified HTTPS succeeded; certificate validation was never disabled. The first
static inventory found undeclared libz.so.1, now an explicit OS prerequisite.
The first QEMU attempt used the build output's flat layout and failed library
resolution; v2 successfully uses the packaged bin/lib layout. Original failure
receipts remain. A Python 3.14 WSL environment is a build host, not the target's
CPython 3.11 interpreter or evidence of wheel imports on ARM64.
