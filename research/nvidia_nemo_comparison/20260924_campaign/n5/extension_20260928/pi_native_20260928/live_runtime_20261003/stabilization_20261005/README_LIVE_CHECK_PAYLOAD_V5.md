# Fresh build28 first Start payload

Purpose: freeze the actual new package and V6 native test helper before the literal Pi microphone check. The actual existing failed source is preserved. Inputs: actual build28 package/manifest, current independently observed boot, Pyannote + ReDimNet (check32) or Nemotron Delayed + ReDimNet (check33), exact selection JSON. Output: private CPU14 early owner, finite 2MiB/600s preparation, source/payload independent backup/restore and original full storage plan, 256MiB independently reserved on Pi and PC, fresh bounded launch payload. It starts no capture itself.

PowerShell:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$source/prepare_stabilization_live_check_v5.py" --package "$package/package" --manifest-sha256 $manifest --boot-id $boot --label classic-ui-check-32 --chooser-label 'Pyannote + ReDimNet' --selection-file "$selection"
```

CMD / Anaconda Prompt:
```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%SOURCE%/prepare_stabilization_live_check_v5.py" --package "%PACKAGE%/package" --manifest-sha256 "%MANIFEST%" --boot-id "%BOOT%" --label classic-ui-check-32 --chooser-label "Pyannote + ReDimNet" --selection-file "%SELECTION%"
```

Set the variables to the actual backed source/package/selection paths and printed manifest SHA/current boot. V5 preserves V4 and changes only the helper pin, fresh target/labels/current boot/12s Stop request for build28. It retains live-only selection validation, full independent original allocation, floors, finite source/session deadlines and record preservation. Follow README_NATIVE_STABILIZATION_CHECK_V6.md to dispatch/monitor/finalize. No listening checkbox is invoked. Transcript/audio content remains private.
