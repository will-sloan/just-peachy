# ChatGPT handoff — current mounted-motion runtime

Read START_HERE, MODE_GUIDE and MOTION_GUIDE first. Current release is v27; the following v23 completion account is retained history. The new shared mounted motion path was deployed, checked with one5.25s live recording and two independent complete PC copies, and left idle with three slots remaining. All ten profile pins share the same common code. IMU thread cost was1.21% of one core at50.29samples/s; not total pipeline or battery cost.

Use microphone-array-centered geometry and distinguish raw device-relative beam arrows from trusted relative-anchor location logic. BMI270 has no absolute heading/position reference: yaw can drift; detected translation/gaps suspend location assumptions. Current live pose is excluded from plain saved WAVs. Source in mounted-source/runtime is exact deployed code for reading, not a bare standalone launcher. The prior prepared-device kit and refresh wrapper omit this addition. See the new motion renewal command and MOTION_* receipts. No noisy-world accuracy, battery or physical-touch claim is added.

The mounted-motion source commit ed27d04b6131106c400bda828a64d00274095c56 is now verified on the existing GitHub branch. MOTION_REMOTE.json supersedes the earlier approval hold. Current acceptance, hardware capability and checklist files incorporate this addition; historical deadline and FINAL_* receipts remain history.

## Earlier runtime/model completion (v23 history)

The user requested a working offline runtime for real-world testing, then restored NeMo TitaNet alongside ReDimNet with one shortcut for each supported combination. Reused the prior ONNX model/frontend and native runtime work; no new research campaign, download, training, enrollment, solicited speech or playback.

Current release is field-runtime-v23 on the prepared2GB CM5/32GB device. One480×800 frontend starts idle, display270, Sherpa ONNX ASR/PnC. Six microphone profiles combine Pyannote or Nemotron-3 Delayed with ReDimNet/TitaNet/explicit anonymous handling. Four saved-input profiles combine Nemotron Streaming/Chunk52 with either encoder. MODE_GUIDE is the executable choice table.

Actual functional evidence:
- All ten compositions executed. Both saved Chunk52 encoders completed8.22s; TitaNet made seven real embedding queries. Saved Streaming with both encoders completed8.22s, including Audio off and Processed cases.
- Four successive independent recordings, complete source/model/archive closure and verified local backup before the next slot passed. Actual saved history, nonempty captions, full export/readback/disposable-copy delete/import/reopen passed.
- Candidate22 recorded85919paired samples5.3699375s: physicalMIC0–MIC3 PCM32LE16kHz plus exact processed model input. Zero marker/drop/callback errors; route restoration and physical capture closure passed. Original and independent Pi-local copies each203files4872052B were copied/read back independently onPC.
- IPv4/IPv6 socket creation is denied in actual broker/child processes. All assets are local. Automatic rollback and real shortcut/startup-command restarts passed.
- Complete candidate22 batch preservation/rollback and generic fresh23 provisioning passed. Current manager40612/start5055076 has fourunused slots;66obsolete icons were independently backed and archived, leaving ten current profiles plusrollback.

Finite limits remain: four recordings,16total launch/helper slots,24h per idle launch,120s microphone/Chunk52,30s savedStreaming. CPU2/3/shared200%/64tasks/one model thread/GPUoff/1MiB stacks/default768MiB AS; initial850MiB/stop192MiB availableRAM. Pi5GiB/C50GiB/G75GiB free floors. Full rawruntime2988319424B and freshinstall3307886087B reserve independent copies; no failed/unused/deleted credit.

The PowerShell refresh wrapper plans/preserves/inspects/provisions a new higher version on the prepared PC/CM5. The underlying sequence actually renewed22→23; its combined wrapper passed syntax and PC-only plan. It retains finite owner bounds and fails explicitly rather than erasing history. The runtime kit91554957B/SHA684abe51500f47a6c444c1905783d8acb043d46887b9cd0a8a50388b83b27533 has2586members, separate archive copy and full expanded restore readback. Existing baseline/Nemotron dependencies remain required; this is not an OS image.

Separate galleries protect existing personal ReDimNet data. TitaNet remains separately empty/Unknown until future explicit enrollment. No embedding-quality gain or noisy-human WER/DER is inferred. Physical touch, cable-disconnected coldboot, battery tests and real-world noisy validation are planned, not observed. The full34-method/N1–N5 denominator and incomplete240-cell N4 remain in FINAL_COVERAGE. All prior failures/identity gaps/closed admissions are preserved and are never retroactively passed.

Use START_HERE, MODE_GUIDE, INSTALL_HEALTH_AND_RECOVERY, FIELD_VALIDATION, FINISH_CHECKLIST and final artifact/Git/handoff receipts. Keep recordings, transcripts, vectors, weights and credentials outside Git and this documentation ZIP.
