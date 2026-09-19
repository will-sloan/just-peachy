# C105 historical ownership regression

`check_c105.py` scores the exact C105 / S45_08_07 / O0 return-speaker sentinel against the pinned S7/S6D scorer and complete41-word reference. It verifies lexical output, anonymous attribution, unique token partition, preserved casing/raw words, first/third return ownership, and byte-identical S7 policy/presentation source. Reference truth is read only by the post-hoc scorer, never passed into runtime inference.

The initial six-scene panel retained final projected rows but its rolling journal had discarded early token events. One targeted final-source replay therefore preserves complete `Controller.rows` and projected rows before closure. This is actual native controller evidence, not a claim that a new Tk widget acknowledged those rows. A separate GUI soak runs concurrently, so elapsed time is not an isolated hardware benchmark.

## Run once from PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\prototype'
& '..\.edge-speech-env\python.exe' tests/check_c105.py --native-replay
```

CMD/Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\prototype"
"..\.edge-speech-env\python.exe" tests\check_c105.py --native-replay
```

Inputs: the already prepared, gained O0 WAV, existing model store, source/config files and immutable historical reference/scorer. No microphone, new scene, training or research gallery is used. The native replay is source paced (~45seconds); its model process then invokes the existing pinned text-analysis interpreter. The default new run folder is `G:\Just_Peachy_PROTO1\acceptance\c105_final_v1`; an existing folder is refused rather than overwritten. If an authorized follow-up truly requires another replay, supply a new `--run-dir`.

## Repeat analysis without inference

```powershell
& '..\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe' tests/check_c105.py --capture 'G:\Just_Peachy_PROTO1\acceptance\c105_final_v1\CAPTURE.json'
```

For CMD/Anaconda Prompt omit the initial `&` and use the same quoted interpreter/path. Output is `tests/evidence/C105_REGRESSION.json`, with compact scores, token/owner checks, source/scorer/reference hashes and limitations. Full controller snapshots and native journals remain under the external run directory. Analysis starts zero models. Expected corrected regression is one error /41 reference words for lexical and anonymous attribution; failed assertions return nonzero rather than silently adjusting thresholds or labels.

The completed final-source replay passed: lexical1/41, anonymous attribution1/41 (2.439%), owner sequence2→8→2, all41 words and unique token partitions preserved. All app/vendor/config hashes stayed unchanged during that replay. Of52 shared vendor files,51 match the accepted S7 epoch byte for byte; only `runtime.py` contains the prototype orchestration hooks. This is one sentinel correctness result, not a broader identity-performance estimate.
