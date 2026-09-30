# Candidate GUI availability and close fix

Purpose: build/stage one fresh offline `b01-offline-20260930-v2` release and qualify its actual GUI entry on the Pi480x800 display. `field_entry_v2.py` preserves the qualified B01/source/model code, adds fullscreen presentation, disables unsupported mode/backend/recipe/tap buttons, makes enrollment explicitly unavailable, and avoids a duplicate controller close after normal UI closure. Other compositions including B05 and sequential refinement remain unavailable in this candidate. Original rc5 installation/data and older candidates are preserved. No pointer activation or baseline replacement occurs.

V1 and V2 visible diagnostics remain immutable. V1 failed the four-raw-versus40-display assertion before opening Tk. V2 reached seven visible control actions, then its copied-archive assertion incorrectly compared caption links with raw utterances. The production entrypoint's finally block raised `Application closed` on duplicate close and masked that error. V3 compares raw records, caption links and the original40display rows separately, records callback failures before cleanup, and tests the fresh close fix. V2 scrot images are black Xwayland-root captures: they are not visual confirmation. V3 uses already installed `grim` on the actual Wayland compositor; images must be inspected before visual credit. No download or Windows interaction.

Inputs: current WINDOW_V5 admission/census, prior independent failure backups, reviewed installed V55 release and exact V50 saved conversation/reference. Original asset paths and hashes remain pinned; models/runtime are shared without copying. New code/config/README ZIP excludes audio/models/profiles. Diagnostic constructor scheduling uses inherited production UI actions; actual field entry adds its production availability/fullscreen behavior. Start opens consent then Cancel only; no microphone, model inference, playback, training or enrollment. Delete applies only to the fresh private copied conversation after a full private ZIP backup.

Outputs: fresh private `field-visible-v3`, release archive and staged release, source copy, GUI launch manifest binding, per-screen geometry/control receipts and Wayland PNGs, action log, exact40widget rows, archive Save/Open/Rename/textExport/copiedDelete evidence and private backup. Existing V1/V2 reader artifacts/failures and six reader-generated CPython caches are retained as explained in README_FIELD_VISIBLE_V2.md. Reader V3 independently verifies sources, manifests, screenshots, archive content, actual envelope, closure and backup. Conversations have no import action; no import/live/physicaltouch/endurance/fieldrelease acceptance is claimed.

Limits:64MiB combined existing-plus-new run reservation split32MiB target/32MiB host under WINDOW_V5; main768MiBAS,1MiBstacks,CPU2/3 shared200%,Tasks64,300s runtime/60sStop,8MiBfile cap, sampled640MiBaggregateRSS/192MiBavailable stops. Fixed32GBPi retains>=5GiBfree. GUI admission expires180s, and no direct unsupervised launch is supported. Preserve all accepted evidence and refuse overwrite. Fresh census must be younger than15minutes.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_visible_v3.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V122.json
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_visible_v3.py --run field-visible-v3
```

CMD / Anaconda Prompt (explicit interpreter, no activation required):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_visible_v3.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V122.json
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_visible_v3.py --run field-visible-v3
```

Reader V3 also accepts the already reviewed V1/V2 failures solely to document their distinct scope. Do not rerun completed output roots. Relevant new changes are in the versioned entrypoint; no repair is applied to bound older files.
