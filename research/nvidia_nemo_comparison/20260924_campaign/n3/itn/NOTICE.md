# ITN subset attribution and changes

Derived from NVIDIA/NeMo-text-processing revision
ddadfb2a38d2bc6b8cc6232c4f915eb60f500688, licensed under Apache-2.0.
The complete license accompanies this artifact as LICENSE_NEMO_TEXT.txt.
Original cardinal source identifies Copyright 2021 NVIDIA Corporation and
Copyright 2015 onwards Google, Inc. Preserve those notices with derivatives.

Changes: finite English cardinal projection for 0..99, selected unit forms and
regular plurals, portable JSON lookup, conservative application rules and
explicit transformation trace. This is a subset, not the entire NeMo grammar.
No source reference/expected captions or personal names appear in the artifact.

Build dependency Pynini uses Apache-2.0; the verified PyPI distribution is 2.1.7,
wheel SHA aaf2171cf5d744961d1080a680f1725807b4d179588a6ad3135596c2e0e06bc0.
The wheel's runtime `__version__` reports 2.1.6.post1; both observations are
preserved. No Pynini binary is redistributed here. Runtime Windows/ARM64 code
uses only the hash-bound JSON and Python standard library. Native ARM64 execution
and full caption-system resource qualification remain untested.
