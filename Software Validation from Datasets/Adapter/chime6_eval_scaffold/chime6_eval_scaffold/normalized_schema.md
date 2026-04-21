# CHiME-6 Normalized Schema

This document defines the normalized output files produced by `normalize_chime6.py`.

## Transcript normalization

The raw transcript text is preserved exactly in `text_original`.

Bracketed events such as `[laughs]`, `[noise]`, and `[inaudible ...]` are preserved in `text_original` but removed from `text_norm`.

`text_norm` is created using:
- bracketed-event removal
- lowercasing
- punctuation removal
- repeated whitespace collapse
- trimming leading/trailing whitespace
