# Separate-process source transport V2

Purpose: implement an explicit Linux source/consumer process boundary so a future capture source need not share the model process's Python interpreter. This version is an unintegrated transport with a saved-input fixture, not a microphone adapter or live repair. No PortAudio, hardware control, model, GUI or playback is imported. Baseline app/config and all bound earlier sources remain unchanged.

Inputs: original private715127sample16k PCM16 WAV, fresh V5 host census and target owners/resources; source-bound factory/config. The fixture converts exact power-of-two PCM16 values to float32, emits160sample blocks with original sample offsets and constructed48k frame counters. Fixture clocks are constructed, not acoustic/native device evidence. Source/module are fixed by the admission; no arbitrary user module selection is exposed.

`isolated_source_transport_v2.py` uses a Unix SOCK_SEQPACKET pair and a fresh subprocess, never forks a loaded model. Each record has a fixed binary header, float32 audio bytes and bounded JSON metadata. Sequence, offset, byte count, complete packet and terminal rolling hash are checked. Each received block acknowledges one outstanding record. Limits:64 outstanding blocks AND65536 encoded bytes,8192 audio bytes/2048 metadata bytes per block; kernel socket buffers are requested262144bytes and actual returned values recorded separately. Kernel overhead is not counted as logical payload. The child pauses reading on exhausted credits and faults on its bounded deadline, rather than allocating an unbounded queue. A kernel send failure is explicit. Metadata/offset/payload faults stop the stream; queued accepted blocks precede the terminal fault.

Parent Stop tells the source to stop and drains queued accepted records through the terminal hash. The saved-file fixture marks unread file samples as never captured/accepted. **This does not qualify drainage of a real driver's pending raw ring.** A future live adapter must preserve that source's accepted raw audio, lease, exact native/model clocks and restoration. On terminal-delivery failure or abrupt child exit the parent reports failure, never a clean EOF. Timeout termination is an explicit failed-close escalation; all passing cases must show natural child closure without it.

The native protocol covers full/repeat/reset,empty,1281sample tail,2s paced fixture with200ms parent Python stall,Stop/accepted-prefix drainage,backpressure timeout,source fault with exact flag2/rejected480frames/unknown upstream loss,discontinuity,malformed bytes,metadata quota,startup failure and abrupt child exit. Expected negative cases must fail explicitly while preserving the accepted prefix. Per-block hashes/metadata and complete child identities are private. No WER/DER, silence label, speaker quality or live performance follows from these cases.

Bounds: actual main service768MiB hard virtual,CPU2/3,total200%,Tasks64,1MiB stack,300s/290alarm/10s stop,8MiBfile. Each sequential child lowers its own hard virtual cap to128MiB,keeps1MiBstack/CPU2/3/same unit CPU/tasks and25s alarm. One child at a time. Parent plus child virtual/RSS is not one768MiB aggregate hard limit; child limits and process peaks are recorded separately. Initial850MiB available RAM and5GiB disk; sampled main640MiB RSS/192MiB available stops.32MiB combined admission16target+16host with sampled aggregate target guard. No inference or long endurance.

Outputs: fresh `isolated-source-v2` admission/source hashes/main/gate/13 child identities/live envelope,private per-case config/trace/result and aggregate RESULT,including every failure. Store only hashes/metadata,not a duplicate audio file. Independent reader must rebuild prefix hashes from immutable WAV bytes,verify every frame/clock/count/terminal/fault/owner/envelope and output bounds. Source/fixture/protocol/dispatcher remain immutable once admitted.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/isolated_source_dispatch_v2.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V76.json
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\isolated_source_dispatch_v2.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V76.json
```
Use a fresh unused census younger than15minutes. The transport child CLI is internal and requires inherited socket descriptors. Never reuse this run ID or invoke it as capture. Failure is preserved; any repair uses a fresh version.

V2 preserves V1 failure: the sender published a full terminal but closed with unread acknowledgements, causing parent ConnectionResetError before protocol acceptance. V2 adds an explicit terminal ACK, verifies all outstanding data acknowledgements were consumed before closing and records terminal_acknowledged. The receiver sends terminal ACK only after exact sequence/sample/hash verification. Both success and handled-fault cases require this handshake. V1 source/admission/output remain immutable.
