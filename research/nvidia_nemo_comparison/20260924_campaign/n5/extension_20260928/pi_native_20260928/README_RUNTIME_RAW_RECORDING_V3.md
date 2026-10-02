# Optional physical raw microphone recording
Purpose: derive the existing candidate19 runtime capsule with a consented Raw MIC0-MIC3 + Processed choice. Reuses unchanged model implementations/assets. Raw is four physical pre-gain firmware taps at16kHz signed PCM32, alongside exact processed model-input audio. This is not48kHz ADC capture or equal acoustic-delay qualification.

Inputs: exact backed candidate19 COMMON_BUNDLE bytes and manager module map. Outputs: new pinned capsule/manager modules, explicit independent raw allocations and derivation review. No network/native action in these pure APIs.
API: derive(common_bytes), derive_manager(manager_files), raw_allocation(recordings,launches), validate_policy(policy).
Native integration remains unexecuted until the fresh installation/recording receipts pass.

PowerShell from this directory:
    & 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); import field_runtime_raw_recording_v3; print(field_runtime_raw_recording_v3.RAW_EXTRA)"
Command Prompt / Anaconda Prompt:
    "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import field_runtime_raw_recording_v3; print(field_runtime_raw_recording_v3.RAW_EXTRA)"
Use the backed installer for actual deployment; do not manually import a capsule on the Pi. Old releases remain immutable.

Physical slots: data/RAW_MICROPHONES.s32le33280000B; source/RAW_CAPTURE.json65536B; config/RAW_SELECTION.json65536B. Each is independently reserved in source/local/PC copies, including when Off or Processed is selected. Original file/module/resource guards remain.

Callback uses the existing bounded ring plus a preallocated two-frame packing carry; prefix0..2 transport frames and final incomplete0..2 transport frames are explicitly accounted, no complete six-channel sample is silently discarded. Strict0,1,1 markers must agree on both channels. Model input is firmware16k tap O0/O1 with existing host gain, no host FIR decimator on packed input. Stop restores all routing while capture clock is active; final raw hash/count readback follows complete source drain. Raw/processed have a common sample clock, not proven identical DSP latency.

Raw files are in full recording PC offload. Conversation ZIP remains text/events/selected processed audio; it must not be advertised as a raw export. Saved-file modes do not expose physical raw capture.

V2 fixes the exact spaced transfer allocation assignment and uses an exact AST literal check for the installed route dictionary. V1 host derivation failed before native work; preserve it.

V3 corrects raw storage to an independently reserved audio artifact under the existing PhysicalFiles interceptor. The12MiB sidecar ceiling remains unchanged. Exact whole allocation stays33411072B extra per copy. Candidate20 installed successfully but NO recording was attempted: pre-recording review found V2 wrongly put33.28MB in a12MiB sidecar group. Old source/install remains immutable.
