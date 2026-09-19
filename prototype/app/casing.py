"""Cheap display-only partial casing. See prototype/docs/UI_ITERATION.md.

Call with the entire current utterance revision, never just its latest audio
block. The function is stateless so expansion/retraction cannot accumulate text.
Raw ASR, lexical tokens, timing, utterance IDs and final learned text stay outside
this function and are never modified.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

DEFAULT_ACRONYMS = ("AI", "API", "ASR", "CPU", "DSP", "GPU", "ONNX", "PCM", "UI", "USB", "WAV", "XVF3800")
_TOKEN = re.compile(r"\d+(?:[.:/,\-]\d+)*|[^\W\d_]\w*(?:['’][^\W\d_]+)*", re.UNICODE)
_I = re.compile(r"^i(?:['’](?:m|ll|ve|d|re))?$", re.IGNORECASE)


def provisional_case(raw: str, names: Iterable[str] = (), acronyms: Iterable[str] = ()) -> str:
    """Render readable partials without correcting, completing or adding words.

    Genuine mixed-case words and numbers are kept. An explicit name spelling
    wins over sentence capitalization. Ambiguous names/acronyms are necessarily
    limited until the authoritative final punctuation/casing pass arrives.
    """
    if not isinstance(raw, str):
        raise TypeError("raw ASR text must be a string")
    if not raw:
        return raw
    allowed = {x.casefold(): x for x in (*DEFAULT_ACRONYMS, *tuple(acronyms)) if isinstance(x, str) and x}
    sentence_start = True
    previous_end = 0
    output: list[str] = []
    for match in _TOKEN.finditer(raw):
        gap = raw[previous_end:match.start()]
        if any(mark in gap for mark in ".!?"):
            sentence_start = True
        output.append(gap)
        token = match.group()
        word = token
        if any(char.isalpha() for char in token):
            if _I.fullmatch(token):
                word = "I" + token[1:].lower()
            elif token.casefold() in allowed:
                word = allowed[token.casefold()]
            elif token.isupper():
                word = token.lower()
            # Do not corrupt deliberately mixed spellings, e.g. iPhone/eBay.
            if sentence_start and word.islower():
                word = word[:1].upper() + word[1:]
            sentence_start = False
        output.append(word)
        previous_end = match.end()
    output.append(raw[previous_end:])
    result = "".join(output)
    spellings = {name.casefold(): name for name in names if isinstance(name, str) and name.strip()}
    if spellings:
        pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(x) for x in sorted(spellings, key=len, reverse=True)) + r")(?!\w)", re.IGNORECASE)
        result = pattern.sub(lambda match: spellings[match.group().casefold()], result)
    return result
