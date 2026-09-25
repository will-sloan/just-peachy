# Proposed workbook update — master workbook unchanged

N3: ACCEPTED for offline component comparison/N4 inputs, September 25, 2026.
N1/N2 are accepted in their agreed offline scopes. N4/N5 remain incomplete.

Actually run: 384 matched screen files, 32 regressions, 20 paced files, nine
accepted native/new-service GUI cases, actual CPU/CUDA/reference contrasts,
full A1 ONNX service parity and 454 final-source tests (452 pass, two skips).
The A1 eight-file paced census has a separate verified correction; its original
four-expected coordinator failure remains. A3's single-core GUI failure remains;
three functional two-core cases passed without model/timeout changes.

Primary combined-tap lexical WER: A0 12.00%, A1 14.90%, A2 10.21%, A3 15.63%.
Each total uses 1,792 complete-nonoverlap reference words. No final winner is
selected from the small screen. P0 preserved normalized lexical output in 1,289
inputs; isolated-clip punctuation F1 0.7273 is not conversation reconstruction.
Finite licensed ITN remains off by default with traceable optional transforms.

Accepted source: local/releases/n3-common-a1controllerv2/SOURCE_RECEIPT.json.
N3_ACCEPTED_CONFIGS.json binds this source and exact model/catalog manifests.
Git release tag: n3-accepted-20260925-v1; backup and package receipts verify it.

Remaining: N4 full-bank/caching/calibration, common-GUI usability and resource
selection; N5 Windows/ARM64 software validation/releases. P2, optional usable
CTC alignment and multitalker gaps stay explicit. Live CM5 checks are deferred
until the user reconnects the Pi. Keep packaging reserve/deadline unchanged.
