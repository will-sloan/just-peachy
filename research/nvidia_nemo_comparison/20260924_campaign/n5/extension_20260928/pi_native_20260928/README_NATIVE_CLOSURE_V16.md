# Native closure collector V16

Purpose: retain the V14 read-only accounting and strict typed ownership closure checks while decoding the two actual pinned local-journal launch OWNER envelopes. Only the exact field-local-release-v1 launch01/02 paths, hashes, policy, purpose, slot and owner schema are accepted. Other malformed owners still fail. OWNERSHIP_CLOSURE remains a separate typed nonidentity receipt. The pending3byte journal file is preserved and is not a completed OWNER.json.

New native utility identity is emitted before project-owner scanning. The host saves bounded raw stdout/stderr, phase and early native OWNER even when the scanner fails. CPU14 is set by the host entry before project reads; native CPU3/128MiBAS/1MiBstack/FSIZE0/45s alarm, host60s phase and262144byte streams apply. Source uses the existing strict SSH helper. No source/model/GUI/capture/data writes occur on the Pi.

Inputs: fresh census, unique version and host-owner receipt, exact immutable closed TRANSFER_RESOURCE_POLICY_V2 digest097f0ee8d0cd7459376b793e7c949ed4be046392d0c6a91d8cae8ff1f8b1f9f7. This closed policy is read-only accounting authority only. Outputs: NATIVE_CLOSURE/RESOURCES_Vn plus early native owner/raw phase files. New dispatch still needs a fresh measured admission and ALL later extra-owner/lifetime checks.

PowerShell from this source directory:
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\collect_native_closure_v16.py --version 301 --resource-policy .\TRANSFER_RESOURCE_POLICY_V2.json --policy-sha256 097f0ee8d0cd7459376b793e7c949ed4be046392d0c6a91d8cae8ff1f8b1f9f7 --census G:\PATH\HOST_CENSUS_V243.json --owner-receipt G:\PATH\FRESH_COLLECTOR_OWNER.json

CMD / Anaconda Prompt from this source directory:
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v16.py --version 301 --resource-policy TRANSFER_RESOURCE_POLICY_V2.json --policy-sha256 097f0ee8d0cd7459376b793e7c949ed4be046392d0c6a91d8cae8ff1f8b1f9f7 --census G:\PATH\HOST_CENSUS_V243.json --owner-receipt G:\PATH\FRESH_COLLECTOR_OWNER.json

Use a unique version/output only after all lifetime/event/member files have been inspected. Never overwrite closed outputs. V300 failed in V14 before its utility identity was returned, from KeyError pid on the nested journal schema. Its native PID/start ticks are UNRECORDED; the later successful scan does not invent them or retroactively pass V300. V300 dependent extra scan failed on missing receipt before SSH. No app/capture attempt was involved.

V16 sets CPU14 at module entry before all project imports, including direct CLI use. V15 remains a backed, unexecuted draft; the actual wrapper already set CPU14 but the documented standalone CLI needed this explicit ordering. No native attempt used V15.
