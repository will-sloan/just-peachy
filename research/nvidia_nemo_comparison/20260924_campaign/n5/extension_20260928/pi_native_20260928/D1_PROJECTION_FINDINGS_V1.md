# Alternate D1 mismatch localized to the preencoder projection

September 30, 01:33 UTC. Independent review: `REVIEWED_NATURAL_FEATURE_MATMUL_MISMATCH_LOCALIZED_ONLY`. A focused host diagnostic established a discrepancy in the original eight-frame stacking plus linear projection, before the speaker-cache update. This does not qualify a repaired runtime.

The original checkpoint projection weights, full ONNX graph initializer and extracted graph initializer match exactly. Stacked inputs, zero padding, lengths and repeat outputs are exact. Original PyTorch FeatureStacking reproduces the retained original first speaker cache exactly for the short tail and first full-file chunk. The extracted ORT tail output also reproduces the earlier failed tail cache exactly. These observations locate that failure at the projection arithmetic rather than the waveform frontend or frame mapping.

| Retained natural feature case | Frames | ORT versus PyTorch maximum absolute difference |
|---|---:|---:|
| Short tail | 8 | 0.0001639128 |
| First full-file chunk | 2120 | 0.0002336502 |
| Middle chunk | 2128 | 0.0002346039 |
| Final chunk | 253 | 0.0001398325 |

Every case still fails the unchanged 0.00001 state gate. BASIC and disabled ONNX graph optimization produce identical outputs, so that toggle does not repair the discrepancy. Float64 accumulation was used only as a diagnostic, with independent scalar dot-product checks; it is not an applied replacement or a relaxed reference. Output magnitudes reach about 137.5. These results establish a projection arithmetic difference, not the particular CPU reduction implementation or that every downstream state difference has the same cause. Probability and state gates remain unchanged.

The diagnostic took 12.484 seconds in the admitted CPU4/14, one-thread, GPU-off host Job with a 6 GiB hard commit bound. The compact graph is 2,105,077 bytes. The checkpoint tensor was read in memory; no checkpoint files were extracted and the full 400 MB graph was not re-exported or copied to the Pi. Private output plus its verified backup remain under the 32 MiB reservation. All 29 backup files (15,182,093 bytes) match hashes; originals remain intact. No model or microphone ran on the Pi.

Closure V86 confirms all 195 Pi and 48 isolated host identities closed, original app/config/install unchanged, capture closed and both leases free. Combined output is 4,372,651,061/5 GiB. The fixed 32 GB Pi has 17,893,818,368 bytes free and 1,592,360,960 bytes available RAM. Closure temperature 52.9 C, throttled=0x0; global swap 3057 in/35519 out is context only, not per-job attribution.

Next, use a fresh small target admission to check these natural-feature projections on ARM before selecting a justified arithmetic change. No new large graph export is warranted yet. Continue actual source startup/controller isolation and sequential-ASR GUI integration alongside this branch. Full waveform/native alternate-runtime, speedup, quality, endurance, field release and N4/N5 acceptance remain open.

Execution: [projection README](README_D1_PROJECTION_V1.md); [independent reader](README_REVIEW_D1_PROJECTION_V1.md). Private d1-onnx-projection-v1/REVIEW.json and D1_PROJECTION_BACKUP_V1.json retain evidence. Previous waveform, extraction and state failures remain immutable.
