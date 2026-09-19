# Shared policy comparison on actual neural observations

Purpose: run the frozen v3 incremental policy with registered candidate settings over compatible actual native S6C evidence. This makes no neural-model or audio-playback calls. New evidence, ASR, routing or decoder settings must have their own compatible native source; state-dependent cadence requires the exact full policy, cue and gallery dependencies.

Inputs: frozen epoch, ordered completed native result indices, challenge/all panel, optional explicit candidate IDs, and new output label. The first compatible receipt in supplied index order is chosen before predictions. Hashes, canonical paired audio, frontend settings and all identities are checked. No reference transcripts/person IDs enter the policy. Diagnostic nominal-angle packets remain explicitly oracle-like.

Outputs: an immutable policy plan, progress and final prediction indices under the S6C epoch report; compressed per-candidate predictions under G:\Just_Peachy_S6C. Naming uses the exact registered isolated manifest. Gallery condition/tier and the exact manifest binding are included for separate scorer-only identity mapping. Existing outputs are admitted only with unchanged complete metadata; changed code/dependencies require a new label/epoch as applicable.

PowerShell from the repository root, after recipes and split native indices are COMPLETE:

```powershell
$sim = Join-Path (Get-Location) 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r = "$sim\reports\S6C\20260910T123540Z"
& '.\.edge-speech-env\python.exe' "$sim\scripts\s6c_policy_matrix_v2.py" --epoch epoch1 --indices "$r\jobs\epoch1\recipes_v1_RESULTS.json" "$r\jobs\epoch1\split_v1_RESULTS.json" --label component_panel_v1 --candidates C065 C066 C067 C068 C069 C070 C071 C072 C073 C074 C075 C076 C077 C078 C079 C080 C081 C082 C083 C084 C085 C086
```

Anaconda Prompt / CMD, same working directory:

```bat
set "SIM=%CD%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6C\20260910T123540Z"
".edge-speech-env\python.exe" "%SIM%\scripts\s6c_policy_matrix_v2.py" --epoch epoch1 --indices "%R%\jobs\epoch1\recipes_v1_RESULTS.json" "%R%\jobs\epoch1\split_v1_RESULTS.json" --label component_panel_v1 --candidates C065 C066 C067 C068 C069 C070 C071 C072 C073 C074 C075 C076 C077 C078 C079 C080 C081 C082 C083 C084 C085 C086
```

Omitting candidate IDs includes all new-neural profiles and therefore requires a later frozen epoch containing the prepared enrollment gallery index. N00 legacy sources use `s6c_replay.py` and its separate documented support reconstruction. Cached policy timing is not paced native latency.

When no completed index exists after interruption, every resumed semantic payload is compared with fresh shared-policy output. An existing completed index instead supplies the exact payload byte binding. Gallery limits are rechecked for every requesting profile, including resident cache hits.

V2 can accept explicitly supplied --source-epochs absolute manifest paths. Every additional source epoch must have byte-identical application Python files, model asset bindings, Python/package versions and canonical input index. Source extraction semantics are AST-identical; no unlisted epoch is accepted. The declared source epoch bindings are included in the plan and every prediction identity. This permits new policy-only candidates to use unchanged prior genuine neural observations; full state-dependent cadence still requires exact profile/cues/gallery.
