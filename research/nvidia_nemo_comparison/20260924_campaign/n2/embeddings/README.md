# N2 official TitaNet-Large export and reference

Purpose: make the pinned NVIDIA TitaNet-Large checkpoint runnable in the shared Windows application on CPU, then compare real waveform embeddings and pairwise cosine scores against official NeMo. This is a representation/export check, not a threshold-calibration study. It performs no training, recording, playback, or personal-data reads.

Inputs: pinned `.nemo` (SHA256 `e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3`), the frozen `WINDOW_MANIFEST.json`, its permitted saved mono 16 kHz C waveforms, and the runtime source. E0/E1 must receive exactly those manifest waveform spans. The script never selects Q. Outputs: `titanet_embedding.onnx`, official `titanet_frontend.npz` buffers, hash-bound `titanet_manifest.json`, and `parity_receipt.json`. Large assets and logs remain outside Git.

The application runtime has no PyTorch/NeMo dependency. The isolated reference/export environment is native Windows Python 3.12.7 at `G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312`. CPU PyTorch 2.8.0 is used with one thread and BelowNormal priority. The existing `.edge-speech-env` is unchanged.

The official NeMo source is pinned to `cf724ac337d1ebc7d0dda1e23fb80916f52927a5` from NVIDIA-NeMo/Speech. Its ZIP SHA256 is `b7484ac574876f3f5ce990c8d3f5335780ac7f002c1534ea73fcf3bcdad521ce`. Reviewed setup.py uses setuptools and defines only optional style-check commands; pyproject declares normal dependency/build metadata. Python model loading uses the local hash-verified checkpoint, without remote model code or default ASR downloads. The NVIDIA code is Apache-2.0; the older TitaNet checkpoint is CC BY 4.0 and requires NVIDIA attribution. Environment installation receipts pin all resolved transitive packages and source URLs under `local/n2/logs`.

PowerShell export:

```powershell
$root='G:\Just_Peachy_N1\20260924_campaign'
& "$root\local\n2\nemo-py312\Scripts\python.exe" "$root\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\embeddings\export_titanet.py" --checkpoint "$root\local\assets\sha256\e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3\speakerverification_en_titanet_large.nemo" --window-manifest "$root\local\n2\evaluation\WINDOW_MANIFEST.json" --output "$root\local\n2\titanet\export" --vendor "$root\worktree\prototype\vendor"
```

Anaconda Prompt or Command Prompt:

```bat
set ROOT=G:\Just_Peachy_N1\20260924_campaign
"%ROOT%\local\n2\nemo-py312\Scripts\python.exe" "%ROOT%\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\embeddings\export_titanet.py" --checkpoint "%ROOT%\local\assets\sha256\e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3\speakerverification_en_titanet_large.nemo" --window-manifest "%ROOT%\local\n2\evaluation\WINDOW_MANIFEST.json" --output "%ROOT%\local\n2\titanet\export" --vendor "%ROOT%\worktree\prototype\vendor"
```

`--panel-size` defaults to six distinct C windows. Additional tests check an actual 0.5-second prefix, a non-hop-aligned prefix, constants, and input rejection. These prefixes are export controls only and never enter enrollment or calibration. The supported application minimum is 0.5 seconds; vendor speaker accuracy on short replies is not asserted.

The official export interface excludes waveform preprocessing. The adapter therefore uses stored official mel/window buffers with a NumPy frontend: 16 kHz, preemphasis 0.97, centered constant-padded 512-point STFT, symmetric 400-point Hann, hop 160, 80 mel bands, log guard 2^-24, per-feature unbiased standard deviation plus 1e-5, masked valid lengths, padding to 16 frames, and no eval-time dither. Actual reference parity is required. No waveform gain or resampling is hidden here.

Environment recreation commands and the final observed result are recorded in `ENVIRONMENT.md` and `E1_RECEIPT.json` after validation. An ONNX export is not an ARM64 benchmark; CM5 execution and the 2 GB system budget remain separately untested.

The unchanged application's runtime check reads the shortest/longest eligible E/C saved windows, embeds each twice, checks normalized 192-D output, rejects a mismatched namespace, and records Windows process memory. It uses no Q labels. PowerShell:

```powershell
$root='G:\Just_Peachy_N1\20260924_campaign'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$root\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\embeddings\check_runtime.py" --vendor "$root\worktree\prototype\vendor" --bundle "$root\local\n2\titanet\export" --windows "$root\local\n2\evaluation\WINDOW_MANIFEST.json" --receipt "$root\local\n2\titanet\export\application_runtime_receipt.json"
```

CMD / Anaconda Prompt:

```bat
set ROOT=G:\Just_Peachy_N1\20260924_campaign
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%ROOT%\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\embeddings\check_runtime.py" --vendor "%ROOT%\worktree\prototype\vendor" --bundle "%ROOT%\local\n2\titanet\export" --windows "%ROOT%\local\n2\evaluation\WINDOW_MANIFEST.json" --receipt "%ROOT%\local\n2\titanet\export\application_runtime_receipt.json"
```

Observed 2026-09-24: official NeMo versus ONNX+NumPy parity passed on six C clips (three identities), actual 0.5-second/non-hop-aligned prefixes, and constant controls. Pairwise cosine maximum absolute error was 2.55e-6; minimum embedding cosine was 0.99999988. The unchanged application environment also passed repeatability and namespace rejection, including the longest 35.835-second E/C capture. That adapter-only process peaked at 730,906,624 bytes of working set; this is not a full-application or CM5 memory guarantee. Its verified BelowNormal priority class was 16384. The first reference/export run's priority call had an instrumentation bug fixed afterward; its priority is not retrospectively claimed as verified. Both passes used CPU-only inference with one configured numerical thread.

The integration regressions in `prototype/tests/test_n2_integration.py` use synthetic vectors and fake timelines by default. They check namespace isolation, explicit Unknown and closed-roster assumptions, C/Q separation, unique evidence, contradiction reset, short/overlap/mixed coarse spans, exact caption span targeting, unchanged words, and a nonblocking caption producer. Setting `N2_TEST_E1=1` also uses a real E waveform to exercise actual E1 extraction, temporary personal-store save/reload, gallery scoring and isolated model namespaces. Its supplied quality record is explicitly a store-contract fixture, not a claim that a live enrollment quality gate admitted the corpus audio. No test modifies the actual personal-data root. Temporary voiceprints are removed at completion.

PowerShell (including the optional actual E1 model test):

```powershell
$env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'; $env:OPENBLAS_NUM_THREADS='1'
$env:N2_TEST_E1='1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'G:\Just_Peachy_N1\20260924_campaign\worktree\prototype\tests\test_n2_integration.py'
Remove-Item Env:N2_TEST_E1
```

Anaconda Prompt / CMD:

```bat
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set N2_TEST_E1=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "G:\Just_Peachy_N1\20260924_campaign\worktree\prototype\tests\test_n2_integration.py"
set N2_TEST_E1=
```

Optional inputs `N2_E1_BUNDLE` and `N2_WINDOWS` override the exported bundle and frozen manifest paths. Results print to the terminal; the actual run is preserved as `INTEGRATION_TEST_RECEIPT.json` and private `local/n2/logs/integration-tests.log`. Default tests skip only the real-model case. The original store regressions can be run by replacing `test_n2_integration.py` with `test_people.py` in the same interpreter command.

The D1 integration tests also cover all contiguous single-channel runs inside native chunks, fixed 0.5-second query hops with at most two seconds of genuine waveform support, overlap boundaries, and short-run coverage denominators. Temporal name support prevents later observations from relabelling unrelated old captions. Retiring the 120-second evidence buffer preserves already published older labels. Evaluator callbacks receive the stamped serialized event after the ordinary journal writer; they do not receive the raw unstamped producer payload or run on the ASR producer thread.

The expanded suite also verifies closed UUID display metadata remains unverified,
the N2 settings page exposes its fixed calibration policy without unused baseline
threshold controls, baseline controls remain available, and the Controller
reports N2's unsupported-span Unknown behavior. The latest model-free run
discovered 44 tests: 43 passed and the actual-model case was intentionally
skipped. The earlier actual E1 receipt remains evidence for that earlier run;
it is not a claim that newly added tests executed with the neural model.

Five constructor-level regressions now pass actual application configuration,
effective profiles, resident model wrappers and gallery objects through
`N2Engine.__init__`. They include an E1 research gallery, an E1 personal gallery
created by the real isolated store, namespace/count rejection, legacy E0
preprocessing validation, and baseline rejection of E1. These use explicit
synthetic vector fixtures and assert no model acquisition occurs. They test
engine admission beyond the earlier save/reload/query check; actual GUI/model
execution remains separately reported by the private panel receipts.

For future calibrated research galleries, `N2Gallery(document, namespace, expected_query_domain='the_actual_input_domain')` now requires a `just-peachy.n2.calibrated-gate.v1` gate with C fit role, exact namespace/roster UUIDs, `gallery_profiles_sha256`, domain/duration/roster provenance, calibration-row and window-manifest SHA256s, finite thresholds and `gate_sha256`. Both the gallery and gate must declare the caller-supplied query domain. A self-declared `CALIBRATED` string is rejected. Current campaign galleries remain `UNCALIBRATED_REJECT_ALL` for processed queries; closed-roster labels are explicitly assumptions. No threshold in the synthetic test fixtures is a deployable threshold. Confirmed matches use the common UI's `confirmed` naming state.
