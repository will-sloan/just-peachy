# Native ASR-guided shadow findings V1

September29 14:59UTC. Native online cue observation plus post-session causal policy replay; no applied skipping, online buffer/controller or measured inference saving.

The fresh B01 harness observed real Sherpa positive partial/final publications after their normal caption publication, with source revision intervals and actual arrival times. Converted-source20ms RMS supplied positive energy support at -55dBFS. ASR support received the user's proposed1second pre/post margin; energy used0.2s pre/0.4s post. Decisions were reconstructed with a declared2second delay and only then-available cues. Every sample still went to one unchanged ordered D1 stream.

| Full44.695s constructed-source diagnostic | Result |
|---|---:|
| Positive ASR publications | 41 |
| ASR-only negative-control proposed omission | 22.095s |
| ASR+energy fine20ms proposed omission | 22.095s (49.4%) |
| Rounded21.12s whole-chunk proposed omission | 2.455s (5.5%), final partial chunk only |
| Full-size21.12s chunks proposed for omission | 0 |
| Late positive ASR rescues after this decision deadline | 0 |
| Maximum observed cue-arrival minus revision end | 72ms |
| Online observer work | 0.129s |
| Post-session policy computation | 0.547s |
| Audio actually skipped / compute saving measured | 0 / no |

The72ms number is relative to hypothesis revision ends, not speech-onset/word alignment or missed-speech coverage. The128000byte proposed2second float32 buffer is a lower bound, not allocated/qualified buffering. ASR progress/health watermark is unavailable; missing/uncertain health would retain audio. Energy here is a threshold diagnostic, not validated VAD. ASR-only absence remains a negative control.

This input is sparse: only6.08s(13.6%) of converted20ms frames exceed -55dBFS, and its final below-threshold run is19.895s. Those are energy statistics, not annotated speech duty cycle, silence truth or accuracy. The49.4% figure must not be extrapolated to dense real conversations. Long delayed chunks absorb most fine-grained opportunities. Even the final2.455s is not safely skippable yet: EOF flushing may emit buffered context and state. Rounded source support is a proposal, not proven avoided graph work. Smaller previously tested chunks incurred higher native cost; no Cartesian sweep or automatic recipe change is justified.

Independent reader rebuilt energy/support/availability decisions from exact filtered input and native events. EarlyStop130560samples drained2.726s; fullrestart retained715127source/ASR/D1samples,4470x8D1 and20E0windows exactly matching qualified filtered references at1e-5.40withdrawnTkrows,oneASR/E0load,all queues/archives/controller/Tk/process closed naturally. Full firsttext5.654s includes silence,D1output25.583s,EOFdrain12.534s. PeakRSS543.859MiB,virtual720.609MiB under768MiB. Timing differences against prior runs are conditional with rc5active, not an overhead benchmark. EarlyStop numeric repeat was not requalified for its different cutoff; its lifecycle/count gates pass.

Next: keep this candidate for frozen dense/quiet/overlap/returning-speaker real-world validation; implement an explicit causal progress watermark and bounded buffer before any online gate. Inspect state/cache/whole-chunk/EOF preservation before applied skips. Measure actual D1 work, gate/IPC/context costs and backlog against a matched ungated control; proposed skip ratios are not speedups. Continue user-ready live routing alongside this optimization research.

Read README_ASR_SHADOW_V1.md for commands/inputs/outputs. Private b01-asr-shadow-v1-evidence/REVIEW.json binds the actual native evidence. Existing B01/B05 user previews remain unchanged. No capture/playback, names/enrollment or quality scoring occurred.
