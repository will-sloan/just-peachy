# Production source and transport preparation

Purpose: connect the actual installed XVF microphone source to fixed source, transport and TRACE writers for the forthcoming live Nemotron diarizer entry. These are fresh production adapters. **They have not been executed on the Pi and do not make the field app capturable.** The former qualification-only launchers remain unchanged. No new source, model, GUI or audio job ran in this preparation.

The selected chain is `isolated_pipeline_source_v5` → `isolated_live_facade_v3` → `isolated_live_transport_v1` → `field_live_source_factory_v1` → `field_live_source_bridge_v1`. Pipeline V3 and V4 are retained preparation history, not selectable alternatives. V4 corrects post-journal TRACE-failure accounting and enforces the 2,080,000-sample ceiling before journal acceptance; V5 also signals the actual pipeline Stop Event before timing/limit diagnostics. A TRACE failure after journal acceptance remains a run failure but does not double-count that accepted block as discarded. These paths have source review only, not runtime evidence.

`field_live_source_outputs_v1.load(config_path, expected_sha256, role=...)` reads bounded finite JSON and requires a fresh quiet-capture admission, exact file identities, installed release, source factory, paths, layout, one active child, process-local ALSA configuration, CPU/AS/stack limits, Pi free-space floor, and shared boot-bound absolute deadline. Child lifetime plus 60 seconds of outer cleanup must fit the admission expiry and the October 1 17:42:44UTC hard boundary. The loader validates source prerequisites; it is not proof that the complete entry has enforced every other writer.

Inputs are precreated real directories under one run root; `config/CONFIG.json`, `control/ADMISSION.json`, `control/LAYOUT.json`, `data/live_config.json`; the retained quiet authorization; the exact v12 installed manifest/live source and admitted code pins. The complete entry must create and independently verify these under a fresh measured admission. Config fields and validation are explicit in `load`; no command in this README fabricates an admission. Source configuration points to the existing hardware lease, with evidence output routed into reserved files rather than random folders.

`field_live_source_factory_v1.create(config)` reloads that admission in the source child, verifies the actual imported `app.live_audio` origin, and delegates Start to the installed XVF implementation. It reuses the retained PRE-before-route backup and POST-after-restore readers and the bounded actual Stop derivative. Source-side write faults halt acceptance before diagnostics; physical route/stream/lease cleanup still belongs to actual Stop. Parent-side TRACE faults signal the actual pipeline source Event. Neither source Stop branch has new native evidence. Archive-thread callbacks must remain nonblocking and must never join their own worker.

The transport retains the actual owner registration/ACK before factory construction, packet ordering, accepted-byte digest, bounded outstanding blocks/bytes, backpressure, concurrent deadline watcher, shared child alarm, terminal ACK, natural reaping, and failure-latched physical Close. Parent transport, child transport and source each have separate diagnostic/closure slots. First failures and partials are preserved; no failed writer is retried. The process-local latch is not crash recovery. The source has a 120-second Stop boundary with a separate 130-second accepted-frame ceiling; neither duration alone proves all writer maxima fit.

`field_live_layout_v3.specification()` adds child-transport raw 65,536B, failure JSON 8,192B and closure 32,768B slots to the retained selected layout: **80,106,028B target + 84,300,332B host = 164,406,360B**. The host amount includes a complete target mirror and 4MiB metadata. This is still **unadmitted and incomplete as a production binding**. No policy allowance changed. Actual FieldController backend/mode/assets/artifact/reservation checks, config path/cardinality and replacement accounting, archive composition, bounded streamed host mirror, full transitive path census, visible operator actions, native source/model/Stop/save/reopen and offline acceptance remain required.

The review command below reads and compiles source without importing installed modules or opening audio. It verifies four complete derivations, retained source cleanup methods, the changed source accounting/Stop ordering, and the actual installed live-source pin/signature. Output is one immutable private `SOURCE_REVIEW_V1.json`; an existing receipt or expired review continuation rejects. It is source review, not a mocked source test or a native passage.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B review_field_live_source_v1.py --preparation 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-source-v1-preparation' --installed-mirror 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12'
```

CMD or Anaconda Prompt (existing explicit interpreter; no installation required):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_live_source_v1.py --preparation "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-source-v1-preparation" --installed-mirror "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12"
```

Do not replay this closed review. Changed future work needs fresh scope and receipts. Host review pins CPU14 before project reads. No general capture launcher is provided until the complete entry, measured allowance and genuine admission exist. Preserve the original app, display270, physical32GB/5GiB floor, prior failures and immutable receipts.
