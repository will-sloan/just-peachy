# XVF3800 listening examples

Purpose: give the user private, playable examples of competing voices, cooking noise and transient impacts captured through XVF hardware, plus a limited actual cafeteria ambient excerpt. This does not run inference, capture audio, contact hardware or start playback. It grants no stage acceptance or subjective listening score.

Inputs are the existing S4.5 scene manifest, S6D same-pass mono references and the annotated Loeb Caf run `JPXVF_P1_R04_T01_D01_S01_UPR_NAT_CU_R06`. The script verifies selected capture hashes, sizes and mono 16 kHz PCM24 headers. Source scene descriptions and noise credits are included. The three synthetic-scene pairs are byte-exact copies of Auto ASR and Auto postprocessed outputs, both processed signals. They are not an untreated-versus-clean comparison. All source pauses remain; silence-heavy scenes are not representative of real-world processing load.

The real cafeteria snippet is samples 4000:16000 (0.25–1.00 s), the previously annotated conservative pre-excitation background window. It produces separate MIC0/processed_auto excerpts at original level and with identical +24 dB listening gain. It rejects clipping and checks the written samples. No loop, denoising, timing shift or independent normalization is applied. The RETAKE status and lack of scientific qualification remain. This 0.75-second excerpt cannot establish restaurant speech/noise performance. Amplified MIC0 and processed output have different device gain/processing and unaligned processing delay; RMS differences are not calibrated suppression.

Outputs: a private `index.html`, six byte-exact simulated-scene mono WAVs, four small cafeteria excerpts, and `PROVENANCE.json` with input/output hashes and transformations. Approximately 15 MB. Source files and existing listening libraries are unchanged. No private audio is added to Git. The builder refuses an existing destination; choose a fresh suffix to rerun. Dependencies are existing NumPy and SoundFile in `.edge-speech-env`; no installation is needed.

Delivered 2026-09-28: `local/n5/listening-examples-v1/index.html`. All ten audio-file hashes and local links were independently checked after generation; eight embedded players have no autoplay. The generated payload before the provenance receipt was 14,192,696 bytes. Actual browser playback and human listening judgments were not performed. The two taps are paired within each scene; different scene categories have different speech/geometry and are examples, not a controlled ranking of noise-removal efficacy.

PowerShell / Anaconda PowerShell, from any directory:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\listening_examples_v1\build_examples.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\listening-examples-v1'
```

Command Prompt / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\listening_examples_v1\build_examples.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\listening-examples-v1"
```

After the command succeeds, the user can open the output `index.html` or an individual WAV. Start with low playback volume. There is no autoplay; the page pauses other players when one starts. Within each synthetic pair, the sync button pauses and aligns the stored output positions. If browser playback is blocked, use Open WAV. Do not open packed carrier or injected multichannel files as listening material.

Future real-location capture remains pending reconnection. Capture simultaneous microphone reference, ASR and postprocessed output with fixed settings and uncut chronology. Compare restaurant babble separately from steady appliance/ventilation noise and brief impacts; include speech during noise, quiet replies, overlap and natural pauses. Avoid collecting unrelated private conversations deliberately. Keep real-world validation separate from the simulated bank and freeze candidate settings before testing. This builder does not authorize or initiate new device operation.
