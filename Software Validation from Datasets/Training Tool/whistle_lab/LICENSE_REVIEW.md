# Whistle product and dataset review

Checked on 22 October 2026 for Just Peachy's local English ASR experiment.

## Whistle and the local runtime

The [Whistle model card](https://huggingface.co/Cactus-Compute/whistle) declares
Apache-2.0. The downloaded model revision is
`741118687e1f008f06d1351a402a731274789790`, and its LICENSE is retained in the run's
assets directory. The [official Needle repository license](https://github.com/cactus-compute/needle/blob/main/LICENSE)
is also Apache-2.0; source commit `b4fc11b04f1852888d375c8c6dfbaca44572d014`
was installed locally. The native inference runtime comes from
[Cactus-Compute/needle3](https://huggingface.co/Cactus-Compute/needle3), whose
Apache-2.0 LICENSE has also been retained as `needle-engine-LICENSE`.

These grants permit commercial use, modification and redistribution. Shipping the
app/model requires the applicable license text, retained attribution and NOTICE
material where supplied, and notices identifying modifications. Apache-2.0 does
not require the surrounding proprietary app to be open-sourced, grant trademark
rights, or provide a warranty of third-party rights. This review establishes a
documented license basis, not a legal guarantee of all product uses.

The local fine-tuning path is public and ungated. This installation downloaded its
weights, tokenizer and runtime without an API key or account. Cactus's paid cloud
fine-tuning service and its account terms are not part of this run. No datasets
are uploaded. The base model is 16.9 MB; local attention LoRA training exports W4A8
weights, so the tuned file will be larger than that shipped mixed-bit base.

The installed Python package has usage telemetry enabled by default. Every local
entry point sets `NEEDLE_TELEMETRY=0`, `DO_NOT_TRACK=1`, and
`HF_HUB_DISABLE_TELEMETRY=1`. Training and inference also use
`HF_HUB_OFFLINE=1` with explicit local asset paths. Public asset downloads happen
only during setup. Retain these settings in product integration.

## Selected training data

| Dataset | Effective license / condition | Consequence |
|---|---|---|
| Common Voice English 26, age 60+ | CC0-1.0 plus Mozilla acquisition conditions preserved in the project | ASR training allowed by the existing acquisition record; do not redistribute the dataset or use it to identify speakers |
| AMI core corpus | CC BY 4.0, relicensed by the maintainers in 2017 | Attribution; the older local NC-SA text is historical provenance |
| CHiME-6 | CC BY-SA 4.0 | Licensing resolved for this project by user confirmation on 23 October 2026; retain attribution |
| VOiCES | CC BY 4.0 in the existing source registry | Attribution and provenance retention |

The [current AMI license](https://groups.inf.ed.ac.uk/ami/corpus/license.shtml)
supports the project's corrected effective license. The
[official CHiME-6 resource](https://openslr.org/150/) explicitly identifies
CC BY-SA 4.0. ShareAlike is not a noncommercial restriction.

On 23 October 2026, the user explicitly confirmed: "The chime6 licensing is
resolved and good to go." The previous project release-review flag is therefore
cleared for this run. `release_review.json` records that confirmation and its
source. This is the user's project-specific licensing resolution; the underlying
CC BY-SA license and attribution records remain intact.

Creative Commons' [AI-training guidance](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)
explains the distinction between conservative compliance and legal requirements,
and the [BY-SA 4.0 deed](https://creativecommons.org/licenses/by-sa/4.0/)
expressly allows commercial use. Apply the project's resolved distribution terms
when shipping the model.

CMU's exploratory branch, full LibriSpeech, HiFiTTS and raw GigaSpeech are not
added to the requested first training mix. Existing frozen benchmark material is
used only for evaluation. The imported Sherpa GigaSpeech predictions are comparison
artifacts, not a new download or training source.

## Streaming and embeddings

Whistle's live API uses repeated window decoding and commits words agreed by two
passes. That supports local live captions but is different from a causal streaming
encoder with a fixed incremental-state cost. Test end-to-end latency on the target
Pi when available; desktop timings are not Pi measurements.

`Whistle.embed(audio)` returns encoder frames (one per approximately 80 ms), useful
for acoustic matching/retrieval. The API smoke test confirms finite frame vectors.
It does not establish speaker verification, identity persistence or diarization
accuracy. Keep the existing Nemotron and speaker-embedding components until a
separate permitted dataset test measures DER, speaker verification EER, overlap
behavior, latency and power. Do not use Common Voice for speaker identification.
