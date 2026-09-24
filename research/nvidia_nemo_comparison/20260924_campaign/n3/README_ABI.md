# Native ABI cross-check

`check_abi.cpp` independently verifies the Python ctypes structure sizes and
alignment against the pinned NVIDIA C header. Input is the source header at
97a15afa5caa9bce5baaa86c1184103877af4101. Output is a compile-only object (or an
error); no executable, neural inference, GPU or hardware access is involved.

In an x64 Visual Studio Native Tools command prompt (or an Anaconda Prompt after
running the installed Visual Studio `VC\Auxiliary\Build\vcvars64.bat`):

```bat
cl /nologo /c /std:c++17 /I G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\native-cpu1\source\include research\nvidia_nemo_comparison\20260924_campaign\n3\check_abi.cpp /FoG:\Just_Peachy_N1\20260924_campaign\local\n3\check_abi.obj
```

In PowerShell, use the same initialized compiler environment and prefix the
command with `& cl.exe`. No compiler/toolchain installation is required on this
machine. This checks the host C ABI, not ARM64 build or runtime behavior.
