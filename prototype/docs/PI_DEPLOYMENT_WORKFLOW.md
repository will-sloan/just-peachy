# Desktop edit → CM5 update → rollback

1. Edit the common app/profile/UI source. Run the focused tests and the real 480 × 800 portrait/live check. Use the main prototype report to distinguish user-spoken evidence from replay tests.
2. Build a fresh immutable version using `release_tools/release.py build --source . --output <release directory> --version <new version>`. Save the receipt SHA256. Models remain in the shared content-addressed store; private people/settings/recordings stay in an external data root.
3. Transfer over **wired Ethernet SSH/SCP** using `deploy_pi.ps1` and explicit supplied host/user/key, or copy the identical ZIP/receipt/offline wheels/models to trusted USB media. Preserve SSH host-key verification. PROTO1 has not contacted a Pi.
4. The non-root installer verifies architecture, Python version, archive files/hashes, free space, model integrity and imports. It stages `releases/<version>` and an isolated `runtimes/<version>`. Unchanged models are reused. Staging does not replace the running app.
5. Finish/stop the current session and close the app. Activation atomically acquires the same external `runtime.lock`, validates personal data schema 1, records the previous pointer, then replaces `current.json`. An active app blocks the switch. No implicit migration, person deletion or forced process stop occurs.
6. Run `release.py healthcheck --root <install root> --data-root <data root> --models --imports`. From the ordinary graphical desktop, invoke `launch_current.py` with those roots. It resolves the matching runtime and source. Test Stop/Start, input selection, captions and enrollment before relying on that release.
7. If the new code fails, close it and run `release.py rollback --root <install root> --data-root <data root>`, then healthcheck and relaunch. Rollback changes code/config/runtime only; it never rolls back personal people, photos, notes or recordings. Preserve the previous release and lock file. For support, `collect-diagnostics` writes a small JSON without names, speech, embeddings or credentials.

Exact PowerShell, CMD/Anaconda Prompt and Linux commands, inputs/outputs and prerequisites are in [release_tools/README.md](../release_tools/README.md). The release archive is unsigned: checksums detect corruption, not a malicious publisher.

## Declared Linux target and checked artifacts

Target: Raspberry Pi OS **64-bit Bookworm**, aarch64, CPython 3.11, glibc ≥ 2.36. This is an explicit reproducible target selection, not a claim that the user's future OS image already has that version. Check the eventual CM5-compatible image before provisioning; another OS/Python needs a corresponding wheel lock. Thirteen ARM64/pure-Python wheels were downloaded and SHA256-verified against official PyPI for the selected stack, total 89,968,134 bytes. The checked lock is `release_tools/requirements-arm64.lock`; the external wheelhouse is `G:\Just_Peachy_PROTO1\arm64 cp311 wheels` on the desktop. This is **ARM64_ARTIFACT_PREPARED**, not ARM64 inference executed. The exact ONNX Runtime 1.29.0 and Sherpa-ONNX 1.13.4 publisher packages expose aarch64 wheels. [ONNX Runtime publication](https://pypi.org/project/onnxruntime/1.29.0/), [Sherpa-ONNX publication](https://pypi.org/project/sherpa-onnx/1.13.4/).

Install system Tk/PortAudio/libsndfile/libusb/libgomp prerequisites separately as documented; application installers make no system-wide changes. PortAudio is an OS library on Linux. [sounddevice installation](https://python-sounddevice.readthedocs.io/en/0.5.5/installation.html).

## XMOS ARM64 control remains a bring-up requirement

Actual ELF inspection of the supplied `XVF3800-Binary_v3_2_1 (3).zip` found **32-bit ARM** `rpi/xvf_host`, `libdevice_usb.so` and `libcommand_map.so`. Their paths/hashes are in `release_tools/evidence/XMOS_ARCHITECTURE.json`. They are not qualified 64-bit CM5 libraries.

Use the **matched v3.0.0 host-control source supplied with the v3.2.1 firmware family**, retaining its submodules, and the v3.2.1 software source/generated command-map definitions. The official host project documents CMake builds (`cmake -B build`, then build with the native compiler); its supported binary list identifies Raspberry Pi as arm7l. Building source with an ARM64 compiler must be checked rather than assumed supported. The firmware-matched command map is built separately from the YAML-generated definitions under `sources/app_xvf3800/autogeneration/yaml_files/control_commands` using the vendor `fwk_xvf/modules/host_cmd_map` build. Preserve the firmware command IDs; do not pair an arbitrary latest map with the board. [Official host source/build instructions](https://github.com/xmos/host_xvf_control), [v3.2.1 command-map build guide](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/programming_guide/03_working_with_the_build_system.html).

On the real ARM64 target, verify all three produced files with `file`/`readelf` (ELF64/AArch64), resolve shared libraries with `ldd`, run `xvf_host --help`, then perform read-only version/device/routing queries before granting the prototype control. Record hashes and configure the prototype's Linux control helper explicitly. A build failure is a vendor/source portability issue to resolve before Linux live activation; do not switch to root, copy Windows DLLs, silently use PC microphones, or flash firmware. PROTO1 contains no ARM64 XMOS build/execution claim.

## First boot and hardware still pending

Initial eMMC imaging/rpiboot is separate from ordinary application updates. No eMMC image, XVF firmware, GPIO overlay or network service was changed in this task. Use official CM5 provisioning and wired remote-access instructions when the actual board is available. [Compute Module documentation](https://www.raspberrypi.com/documentation/computers/compute-module.html), [SSH and file transfer](https://www.raspberrypi.com/documentation/computers/remote-access.html).

- Confirm the CM5 2 GB/32 GB/no-wireless module, CM5IO and extender routing physically.
- Supply the 480 × 800 panel/controller/interface and supported driver; verify orientation, physical client/framebuffer size and the matching touch transform. Fullscreen is a UI choice, not a driver guess.
- Confirm XVF USB identity, capture format, actual output routing and normal live gain/delay. Grant only the necessary capture/control permission to the ordinary user. Verify no default render-endpoint changes.
- Leave BMI270 bus/address/pins/axes, camera CSI/driver and optional button pins null/disabled until confirmed. Disabled/mock adapters cannot produce live sensor evidence. Cameras do not run continuously and are not used for face recognition.
- Execute native captions/enrollment/restart/update/rollback tests, then sustained memory/CPU/thermal/storage checks on the **complete 2 GB CM5 system**. Windows RSS and x86 Linux packaging tests do not establish Pi capacity or latency.

`HARDWARE_PENDING.json` is the explicit unknown-field inventory. Linux source/release tests are labelled separately from **CM5_HARDWARE_NOT_TESTED** throughout.
# Task08 consolidation

Use `proto1-0.2.0` for accepted iterations01–08. Exact launch/transfer commands:
[CM5_RELEASE_QUICKSTART.md](CM5_RELEASE_QUICKSTART.md). Physical plan and arrival
checks: [CM5_WIRING_AND_BRINGUP.md](CM5_WIRING_AND_BRINGUP.md). Disabled/null
[HARDWARE_PENDING.json](HARDWARE_PENDING.json) is a planning template, not an
automatic device configuration.

**Rollback compatibility:** schema1 alone is insufficient for paragraph
references. The current updater reads per-person `capture_mode` and the
release's `data_features_supported`. An incompatible older reader is refused
before changing pointers; profiles, photos, vocabulary and sessions remain.
No migration is needed between task08-compatible releases. Never use an old
updater to bypass this check. Save a private backup before deliberate schema
migrations in a future release; none run here.

Local matching sources were rechecked: v3.2.1 User Guide (PDF pages20/48/58/60–63),
Programming Guide host-map section (PDF pages46–47), v3.0.0 host source README,
and the supplied v3.2.1 binary ZIP. The host README lists Raspberry Pi arm7l
32-bit. Native host source requires its submodules and CMake≥3.13; command-map
generation uses the **firmware-matched** source requirements and YAML. The
firmware's XTC toolchain is a different build from the Linux host helper. No
native ARM64 host or firmware build ran during task08. The rechecked source
hashes and artifact ledger are in `UIITER2_08_DEPENDENCIES.json`.

## Local source additions through task12

The preserved task08 ZIP contains tasks01–08. Current source adds09–12; tasks11–12
add no dependency/model or hardware driver. Carry the same source to a future
Windows/CM5 export; do not label the old ZIP as containing these extensions.
Collection/matching default Off. ARM64/native CM5 RAM and live field validation
remain NOT_TESTED; desktop tests do not qualify the target.

Task11 adds bounded environment references and Undo transactions inline in
person.json, separately from original anchors. First explicit promotion/import
requires DATA_SCHEMA feature `session-reference-enrichment-v1`, supported by
the current capability manifest. Generic release/data-reader checks must retain
this requirement. Undo keeps the conservative feature marker; never force old
code to read it. Use current code with bank matching Off, or a separate compatible
data root when rolling source back. Rename/import/export/delete preserve the
new bank/transaction semantics. See ../app/README_ADAPTATION.md for exact bounds,
domain tags, privacy, commands and immutable-anchor behavior.

Task12 adds optional Windows AMD64 selected-excerpt transcript review, default
Off. The control explicitly refuses ARM64/CM5 until combined target resource and
latency tests qualify it; ordinary offline speech remains available without it.
No Qwen/llama.cpp artifact or ARM64 helper is included. Reviews/corrections add
fields to conversation-v1 archives only; no new personal-profile schema feature.
Source rollback to task11 preserves those annotations and ordinary corrections.
See UIITER2_12_HANDOFF.md. The task08 export was not rebuilt or relabelled.
