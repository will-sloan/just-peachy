# S4 offline spatial analysis

`s4_spatial_analysis.py` analyzes saved physical S4 capture folders. It opens no USB device, audio endpoint or model. It preserves root ownership of the XVF and does not alter historical S3 code or captures.

Inputs are a saved case folder, the frozen S4 scene manifest with selected RIR geometry, and optionally separately measured output-versus-recaptured-MIC0 delay samples. Outputs are JSON metrics for selected processed direction, selected auto direction, raw auto, focused beams 1/2 and scanning direction. Raw logs remain local.

PowerShell — offline regressions:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_spatial_analysis.py' --self-test
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_spatial_analysis.py" --self-test
```

Analyze a physical case after the root finishes capture and restoration. Replace BATCH with the actual saved batch name and use a new output path:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_spatial_analysis.py' --case-folder 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S4\20260909T002140Z\hardware\BATCH\S4_01' --scene-manifest 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scene_bank\s4_v2_20260909T002140Z\SCENE_MANIFEST.json' --output 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S4\20260909T002140Z\S4_01_spatial.json'
```

```bat
"C:\Users\amiri\anaconda3\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_spatial_analysis.py" --case-folder "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S4\20260909T002140Z\hardware\BATCH\S4_01" --scene-manifest "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scene_bank\s4_v2_20260909T002140Z\SCENE_MANIFEST.json" --output "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S4\20260909T002140Z\S4_01_spatial.json"
```

The owner can call the library directly:

```python
from s4_spatial_analysis import analyze_case, S4_SPATIAL_POLICY
metrics = analyze_case(case_folder, scene, manifest["selected_rirs"],
                       output_delay_samples={"O0": measured_O0_delay_samples,
                                             "O1": measured_O1_delay_samples})
```

Omit `output_delay_samples` when no independently measured relative waveform delay is available. The CLI accepts the same object in `--output-delays-json PATH`. The values are samples at 16 kHz, not milliseconds. Correlation estimates describe processed output relative to recaptured MIC0; they are not absolute device latency.

The operative pre-scoring contract is `S4_SPATIAL_POLICY`, version `jp_s4_spatial_metrics_v2`. The root requested this definition before physical-output inspection. It supersedes the early 0.5-second contiguous metric placeholder in the telemetry helper; the live causal freshness limits remain unchanged.

- Sectors are right <60°, central/ambiguous 60–120°, left >120° in native linear-array coordinates.
- First hit records the first usable matching causal sector in the estimated activity envelope. A matching cue already present at onset is flagged.
- Sustained acquisition requires at least 80% matching occupancy in the trailing one second, checked at actual matching angle receipts. Angle/energy receipt gaps must remain ≤250 ms. Long gaps straddling the window boundary retain their actual preceding receipt.
- Coverage is integrated by duration over the quantized estimated activity support. Angle-only and speech-energy-gated coverage remain separate.
- AEC streams require their corresponding latest causal energy >0 and fresh. Selected processed index 0 uses its documented speech/NaN semantics. Selected auto also requires fresh raw-auto energy.
- Off-delay runs from the last estimated activity availability to the first unavailable/no-speech/wrong sector, censored at the next utterance or capture end. Ongoing overlapping speech censors it immediately.
- Never-acquired, unavailable and censored observations stay in the result. No beam is treated as a person ID.
- Noise-only indication metrics remain separate from speech-plus-noise windows; the latter are not false-positive measurements.

The scorer selects only the last observation actually received by each decision time. It never interpolates future telemetry or shifts angles/energies to fit the known source schedule. It uses the tested strict normalizer and the existing ≤250 ms transaction, line-delivery and receipt-age limits. Repeated equal angles are descriptive held values, not proof of a stale or newly computed DSP frame.

Timing remains qualified. Source activity is estimated, not exact word timing. The scene bank already includes the retained 800 samples/50 ms RIR convention in its absolute estimated activity ranges. The scorer uses those ranges directly and adds the convention only when falling back to dry-file boundaries. The verified recaptured-input offset then maps activity into native callback ranges. Each callback containing active samples contributes a scoring interval from host copy completion to the next callback copy completion. A terminal block uses its native duration. This may expand a short activity region to one callback block; the result reports maximum block/gap granularity. Historical callback timestamps are used only when a copy-completion field is absent. No earlier intra-block availability is invented.

Primary metrics use recaptured-input availability. Optional processed-output views shift audio support by the separately measured relative waveform delay and preserve telemetry timestamps unchanged. Dry scheduling, RIR pre-onset, input offset, output waveform delay and host metadata availability remain separate. Silent input has no identifiable sample offset, so no source alignment is fabricated; whole nonspeech callback availability can still be summarized.

The source geometry remains nominal with manual ±5° label uncertainty, front/rear ambiguity and separate nominal/interval errors. Manual uncertainty is never the device's allowed error. Overlap scenes retain per-source diagnostics as `LIMITED_MULTISPEAKER_TRUTH`; one selected cue cannot represent both simultaneous talkers uniquely. Scanner comparisons do not establish a production default, S5 output winner or S6 cue benefit.

Outputs are written with exclusive creation to preserve prior analysis. Resume by analyzing remaining complete case folders with new per-case outputs or by having the root aggregate returned dictionaries. The scorer never repeats hardware captures.
