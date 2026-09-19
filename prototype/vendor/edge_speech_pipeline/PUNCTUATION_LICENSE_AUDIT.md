# Punctuation Model License and Provenance Audit

Status: `COMMERCIAL_USE_COMPATIBLE_WITH_APACHE_2_0_CONDITIONS`

Model: `sherpa-onnx-online-punct-en-2024-08-06`, INT8 ONNX variant.

## Evidence chain

1. The official Sherpa ONNX release package says its files came from the model author's `frankyoujian/Edge-Punct-Casing` Hugging Face repository.
2. That Hugging Face model card declares `license: apache-2.0` for the pretrained model repository.
3. The author's Edge-Punct-Casing source repository is also licensed under Apache License 2.0.
4. The Sherpa ONNX runtime is licensed under Apache License 2.0.

Authoritative references:

- <https://huggingface.co/frankyoujian/Edge-Punct-Casing>
- <https://github.com/frankyoujian/Edge-Punct-Casing>
- <https://k2-fsa.github.io/sherpa/onnx/punctuation/pretrained_models.html>
- <https://github.com/k2-fsa/sherpa-onnx>

The packaged files are checksum-bound as follows:

| File | SHA-256 |
|---|---|
| `model.int8.onnx` | `9d611f445fe4a46186080fe161be6059d87d72eb88d3a8cb00c1a06e83a6067e` |
| `bpe.vocab` | `e118b7ad88c54db562517df49e1cffd4836d166c34fb190fd311d7f34eb238f5` |

## Commercial-device conclusion

Apache-2.0 is a permissive open-source license. Its copyright and patent grants permit commercial use, reproduction, modification, distribution, sublicensing, sale, and inclusion in a commercial device, subject to its conditions. Distribution must include a copy of the license, preserve applicable attribution and notices, identify modified licensed files, and honor the license's patent-termination and trademark limitations.

`EDGE_PUNCT_CASING_LICENSE.md` is shipped with the Windows source package and Raspberry Pi bundle to satisfy the license-copy requirement. The model and vocabulary are distributed unmodified. Product release documentation should retain this audit and the license file.

This audit establishes the declared upstream license and the exact binary provenance used by this project. It is an engineering compliance record, not a substitute for final counsel review of the complete commercial product and all of its other model assets. In particular, this conclusion applies only to the punctuation model; Pyannote and the other pipeline components retain their separately documented provenance requirements.
