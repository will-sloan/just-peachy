# Visible image review and preserved stability rejection

Purpose: review the completed V4 screenshots without rerunning Pi jobs. Review V4 required both whole-PNG SHA pairs to match and rejected the recipe pair. The retrospective V5 reader preserves that failed byte-stability gate and verifies closure, installed files, no capture/models and exact private backup; it does not promote it to a stable-pair pass. A PNG hash difference is not by itself a decoded-pixel difference. `review_field_visible_images_v1.py` independently decodes retained480x8008bit noninterlaced RGB/opaqueRGBA PNGs with CRC/length/filter checks and compares RGB pixels, reporting count/bounds/hashes separately. Pillow was unavailable; no download or dependency change was made. No image editing occurs.

Inputs: existing reviewed `field-visible-v4` raw receipts/PNGs and fresh read-only target identity checks for V5. Outputs: private REVIEW/BACKUP/target copies and supplemental DECODED_PIXELS_V1.json. Original reader rejection, screenshots and byte hashes remain unchanged. Manual visual inspection is separate from numeric pair stability and does not establish physical touch. Fixed output files refuse overwrite. Host coordinator usesCPU14, PNG inputs<4MiB each and decoded dimensions exactly480x800; no model/target workload is launched by pixel review.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_visible_v5.py --run field-visible-v4
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_visible_images_v1.py
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_visible_v5.py --run field-visible-v4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_visible_images_v1.py
```

Correction to the immutable V4 README's CMD census path: the private directory is `G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928` (hyphens), as correctly shown in its PowerShell command. The V4 native run is already closed; this correction is not an instruction to rerun it. Preserve earlier bound READMEs and use this addendum.
