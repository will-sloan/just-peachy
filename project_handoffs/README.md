# Project handoffs through PROTO1

The latest source release is `just-peachy-proto1-0.1.4.zip`, adding two selectable
experimental spatial modes, evidence badges and a compact optional live display.
Read the [mode guide](../prototype/MODE_GUIDE.md) and
[verification](../prototype/docs/SPATIAL_FIELD_UPDATE.md). All 146 software
checks passed, plus bounded native and physical checks with separate scopes.
The ZIP passed all 121 payload hashes, Windows imports and relocated
configuration/model validation. CM5 hardware remains untested.

The previous `just-peachy-proto1-0.1.3.zip` remains unchanged and contains the
Windows timing fix and developer beam diagnostics.

`PROTO1_CHATGPT_HANDOFF_20260919T012911Z.zip` and `just-peachy-proto1-0.1.2.zip`
retain the earlier source-bound prototype results. The maintainable current
application is directly in [`../prototype`](../prototype).

`MANIFEST.json` records every archive's source, size and SHA-256. Archives labeled
`TEXT_ONLY` omit audio or binary payloads; their internal `GITHUB_SNAPSHOT.json`
records exactly what was omitted. All other handoff ZIPs are unchanged originals.
Original historical manifests inside filtered snapshots still describe the full
local handoff, so use the added snapshot manifest when checking GitHub contents.

These archives preserve context, results, configuration bindings, source excerpts
and figures. Raw capture/RIR audio, model weights, speaker vectors, private voice
profiles, virtual environments and full execution logs are stored separately on
the desktop/external drive. This repository does not back up those data volumes.

See [`../maintenance/README.md`](../maintenance/README.md) for snapshot inputs,
outputs and PowerShell/CMD commands. No experiment is run while making a snapshot.
