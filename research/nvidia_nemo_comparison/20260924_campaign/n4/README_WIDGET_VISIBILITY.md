# Observe actual Tk viewport geometry

Purpose: `widget_visibility.py` distinguishes captions applied to widgets from
caption/name glyphs that intersect their current viewport. The common UI hides
active captions in its history Text widget and shows them in a separate active
pane. A marked text range, final-state flag or record_presentation receipt alone
does not demonstrate viewport visibility. This observer checks both actual
widgets, verifies cached text against their exact marked ranges and measures
nonspace character rectangles within mapped parent/widget boundaries. Elided
or scrolled-off text cannot supply positive visibility. Suppressed repeated
headings are not recorded as visible repeated names.

Inputs: the actual PrototypeUI and Controller rows after rendering, optional
explicit actual source monotonic origin. It reads no truth or hardware and
does not call the stateful identity-label function, change clocks, force labels,
scroll, render, inject input or alter any application data. Tcl character offsets
match the existing renderer. Scanning is bounded to visible text, 4,096 character
checks and 512 rows per sample. Mismatched widget/cache text fails closed.

Outputs: snapshot dictionaries with per-pane applied text, heading presence,
visible-character counts, source identifiers and actual observation timestamps.
VisibilityHistory retains first-visible, first-final-visible and latest observed
span states, including row removal, heading changes and maximum sample interval.
History is bounded at 8,192 spans. Strict selection retains explicitly filtered
rows and their raw text. A final flag can be observed without fabricating a new
Tk rewrite. Point observations do not prove continuous exposure between polls.
The source-relative timing field requires an actual clock contract; the library
alone never qualifies end-to-end latency, correct names or physical scanout.

`probe_widget_visibility.py` runs seven regression tests on the existing private
Windows desktop launcher. It verifies frozen source/inputs and renders the 160
saved final Controller outputs (16 compositions x five modes x both taps) into
the unchanged 480x800 Tk frontend. These reuse the same two smoke sources. Actual
render timestamps describe this offline rendering only; no modeled source time
is reinterpreted as a live measurement. This loads no neural models or audio and
does not run the saved audio, take over input, change desktop, or read the user's
screen. No window appears on the user's input desktop. Synthetic test cases
cover elision, clipped headings, scroll, strict recovery, finality without rewrite,
Unicode and corrupt-widget rejection; they are not additional audio scenes.

The helper uses CPU14/below-normal priority and single-thread math. It creates
a fresh private ADMISSION.json, isolation/tests logs, saved observation JSONs
and RESULT.json. The existing 128-MiB output bound, C50/G75-GiB floors, shared
allowance with 6-GiB reservations and packaging cutoff apply. The private launcher
has a 180-second process timeout. Failed attempts remain intact; repair in a fresh
derivative rather than changing already bound code. Do not run during controlled
model/resource timing. No N4 integrated acceptance credit follows from this probe.

PowerShell from the campaign worktree:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_widget_visibility.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\widget-visibility-v1'
```

Command Prompt / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_widget_visibility.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\widget-visibility-v1"
```

Do not launch the unittest module directly on the user's desktop. The child
requires the bound admission and verifies its private desktop before creating Tk.
For later paced applications call snapshot on the Tk thread after rendering and
periodically after layout/scroll changes, then VisibilityHistory.add. Keep full
private evidence and report instrumentation cost/sampling limits; do not subtract
overhead or pacing failures to manufacture a latency pass.
