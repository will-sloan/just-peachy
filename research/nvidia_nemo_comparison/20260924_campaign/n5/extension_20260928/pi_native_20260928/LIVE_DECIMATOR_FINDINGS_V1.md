# Native XVF FIR dependency findings

September 29, 2026 12:56 UTC. Component-only evidence; no microphone capture or playback.

The actual shared-app live path is `LivePipelineSource -> XVFLiveSource -> StreamingDecimator` in app/live_audio.py. It uses a continuous 97-tap causal 48-to-16 kHz FIR, with 1 ms delay and persistent filter/sample-phase state. It imports SciPy when instantiated. The generic vendor microphone resample_poly route is a different path and was not changed.

Two fresh CM5 jobs independently passed six cases: the full constructed source in regular blocks, irregular blocks, a fresh full repeat, impulse/tail, quiet/short input and empty fresh state. All received sample counts, unchanged inputs, phase/count state and finite output were checked. The full diagnostic repeats each original 16 kHz PCM sample three times; it is not real captured 48 kHz audio and carries no speech-quality claim. Original finite-input behavior has no appended FIR tail; that behavior is retained rather than silently changed.

| Native component | Original SciPy FIR | NumPy candidate |
|---|---:|---:|
| Virtual size after construction | 245.125 MiB | 92.203 MiB |
| Peak RSS across cases | 121.438 MiB | 54.234 MiB |
| Full 44.695 s diagnostic conversion work | 0.241 s | 0.136 s |
| Repeat conversion work | 0.236 s | 0.134 s |
| SciPy imported | Yes | No |

The candidate retains the exact original float64 coefficients, causal history and decimation phase. Independent full convolution and original native outputs agree within the predeclared 1e-7 amplitude gate; the largest observed original/candidate discrepancy is approximately 1.32e-23. This is not the separate D1 probability gate. Tests include irregular boundaries and state reset, but do not establish arbitrary-duration stability or broad numerical portability.

The roughly 153 MiB lower construction-time virtual size is promising for B01 live memory headroom. It is not yet a measured combined-application saving. These single-run component timings have the original rc5 app active; no sustained or end-to-end speedup is claimed. The candidate is not installed into the app or exposed in either qualified preview.

Next: bind the coefficients and candidate into a fresh application derivative; feed constructed saved 48 kHz blocks through the actual source conversion boundary; independently check source-time/count mapping, captions/D1/E0 passage, memory, Stop/restart and clean drain. Actual endpoint/rate/channel routing, quiet live capture, user-ready speech and 30/60-minute endurance remain separate. Preserve current B01/B05 previews unchanged.

Read README_LIVE_DECIMATOR_V1.md for purpose, run commands and inputs/outputs. Private live-decimator-reference-v1-evidence and live-decimator-numpy-v1-evidence retain admissions, exact owners, outputs and independent REVIEW.json; CHECK_SUMMARY_V14.json publishes only summaries. No audio/arrays or personal data are in Git.
