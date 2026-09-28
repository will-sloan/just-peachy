# ASR support for diarization: offline empty-control diagnostic

Purpose: test whether already-computed Sherpa A0 or Nemotron English A2 output
provides a useful filter for D1 false activity on all 11 existing empty-control
scenes, both taps. This is an exploratory negative-control calculation, not an
implemented pipeline, trained model or accepted improvement in overall DER.

Inputs: the accepted N4 main plan and its bound ASR/D1 component reviews,
catalogue reference classes, 22 D1/E0 and 44 A0/A2 result/event bindings. Every
selected result and compressed event is rehashed. Model inference only saw
audio in these retained runs; reference classes select the evaluation subset.
No waveform is decoded, model loaded, audio played or recorded, device queried,
download made, source release changed or personal profile accessed.

Method: construct native >=0.5 per-channel activity within observed source
audio and intersect it with the union of nonempty final ASR utterance intervals.
Report all fixed 0, 0.25, 0.5 and 1.0-second padding settings; select none. Sum
speaker-seconds, including simultaneous channels. On known empty controls all
such activity is false. Final transcripts use future information and their
intervals are coarse; this diagnostic must not be called causal real-time
filtering or exact word alignment. It measures no loss of real speech. Missed
words, overlap, short replies and ASR hallucinations require separate validation.
Postprocessing these outputs cannot reduce native inference computation.

Output: fresh aggregate JSON and per-file counts, no transcript/audio/vector.
The process uses CPU14 below normal with no parallel workers. It is safe to run
as bounded read-only analysis while a separate admitted numerical child uses
CPU4. It never updates the shared campaign ledger or launches another model.

PowerShell:

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B assess_asr_activity_support_v1.py --output ASR_ACTIVITY_SUPPORT_EMPTY_CONTROLS_V1.json
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B assess_asr_activity_support_v1.py --output ASR_ACTIVITY_SUPPORT_EMPTY_CONTROLS_V1.json
```

The explicit existing interpreter requires no installation or activation.
