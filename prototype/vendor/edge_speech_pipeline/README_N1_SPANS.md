# N1 caption span ownership

`research_n1_spans.py` implements `timestamped_spans_v3`, selected by the N1
prototype. Historical `supported_prefix_v2` remains available for reproducible
baseline comparisons. Inputs are ASR revision events and admitted identity
events; outputs are stable token/span IDs, revision source windows, independently
owned display segments and speaker revision history. No audio/model execution or
file writes occur in this module.

The current recognizer does not supply phonetic word timing. Each newly appended
token records the source interval observed between hypothesis revisions; rewritten
suffixes record the full uncertain caption interval. `timing_kind` explicitly says
these are revision windows. Exact word start/end remain null. Never score these
windows as exact acoustic alignment or physical latency.

A new speaker labels only currently unowned supported spans, or matures naming
on the same track. Relabeling committed earlier words requires explicit
`target_span_ids` (or `target_token_ids`), the exact current text revision and
intersecting source evidence. Duplicate/older per-span revisions are ignored.
Stable IDs survive naming. A/B/A within one paragraph cannot collapse to A/A/A.
First committed labels remain immutable; corrections append to separate history.
The in-memory history retains first plus latest 31 changes; native append-only
event journals retain the complete published sequence.

ASR rewrites create new suffix hypotheses, so replaced IDs never regain old
ownership. `retired_spans_delta` contains the removed spans and their histories
on that revision; the append-only display journal preserves each delta. Only
the latest delta remains in memory. Identity events must have a valid serial.

Run the source EVENT fixtures from the campaign worktree in PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m unittest prototype.tests.test_n1_spans -v
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m unittest prototype.tests.test_n1_spans -v
```

Inputs are embedded synthetic EVENT fixtures, never generated acoustic scenes.
Output is the unittest report. No microphone, personal gallery or GUI is opened.
