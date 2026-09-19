# Fixed48 capture predeclaration and static listening checks

Purpose: check the published listening files statically and select a metadata-only P_SCAN6 panel before new beam model performance. It preserves all240 P_MAIN6 IDs and original source seconds; selects four cases per original family and four matched repeat IDs for low/normal/overlap/music conditions. It cannot access the device, play audio or run models. No capture is marked passed. The initial hearing-independent anchors include S45_08_07 solely because the V2 contract declares its previous C105 ordering failure.

Inputs: the completed all240 listening index/validation and the authoritative RIR v1 manifest. NumPy/soundfile are not used by this helper; it imports the shared binding functions from s6d_listening_v1.py. Outputs in report/listening: LISTENING_STATIC_QA_V1.json and HARDWARE_CASE_PREDECLARATION_V1.json. Existing output files are not overwritten. The script validates480 local mono players,240 scene cards,777 transcript timing rows, both exact ordered playlists, empty human notes, musical starter coverage, all12families, no autoplay/network URLs and source hashes. Browser rendering remains unverified because Browser Use rejected the local file URL under its security policy; no workaround is attempted.

Selection: seven transparent anchors, then family-order rounds. Candidate score sums2 for each metadata feature not represented within that family plus1/(1+global selection count of the feature). Features include room, pose, obstruction, corpus/quality, actor count, short clips, noise category, reference limitations, source level, angle and half-meter distance bins. Lexical case ID resolves ties. The actual selections, features, reasons and achieved coverage are saved. Four repeat cases are additional P_SCAN6 passes, not extra unique scenes; all attempts count toward the root's global hardware budget. Physical qualification, enrollment and long runs remain root-owned work.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\s6d_listening_predeclare_v1.py" --sim "$sim" --output "$sim\listening\S45_all240_v1" --report "$sim\reports\S6D\20260913T195357Z"
```

Anaconda Prompt or Command Prompt (no conda activation):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\s6d_listening_predeclare_v1.py" --sim "%SIM%" --output "%SIM%\listening\S45_all240_v1" --report "%SIM%\reports\S6D\20260913T195357Z"
```

On a deliberate rerun choose a new report directory containing the appropriate original listening validation and use the corresponding listening output. Do not overwrite immutable receipts or treat metadata selection as hardware evidence.
