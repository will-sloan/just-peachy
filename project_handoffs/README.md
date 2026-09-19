# Project handoffs through PROTO1

Start with `PROTO1_CHATGPT_HANDOFF_20260919T012911Z.zip` for the current prototype
results and `just-peachy-proto1-0.1.2.zip` for its source release. The maintainable
application is also present directly in [`../prototype`](../prototype).

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
