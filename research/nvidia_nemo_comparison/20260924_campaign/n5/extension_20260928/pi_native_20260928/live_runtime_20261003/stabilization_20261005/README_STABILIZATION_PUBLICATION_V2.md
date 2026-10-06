# Prepare the final build26 publication plan, V2

Purpose: extend the immutable490-source build21 handoff plan with the explicitly
selected current stabilization sources,16 updated tracked guides, and the minimum
existing local historical source/README references needed to interpret them.
The tool prepares an **unapproved** plan and an explicit Git path list. It neither
stages/commits/pushes Git, contacts the Pi, changes a runtime nor builds a ZIP.
Run only after Live30/31, build26 activation and final documentation are closed;
an earlier plan would become stale as those source/doc hashes change.

Inputs: exact prior reviewed plan SHA804819723754a73be4a718a98ec0b237ff9906888e743ece0cdaf08283978556,
the SELECTED list and current documentation inside the worktree. Only ordinary
UTF8 source/doc files are permitted; no private evidence tree,media,caption text,
personal galleries,vectors,weights or credentials are selected. The locked old
StartHere is preserved; only its archive member alias uses START_HERE_CURRENT.
Unrelated untracked paths outside stabilization are neither added nor changed.
Historical linked helpers remain explanatory provenance; their consumed native
commands are not current operator instructions.

Outputs: fresh private CPU14/FILETIME owner,16MiB/600s scope including64KiB per
created directory, independently backed/restored changed sources, unapproved
proposed plan, GIT_WHITELIST, PLAN_REVIEW, unresolved-current-link list and
SOURCE_CLOSED. C50/G75GiB floors and source20MiB/member2MiB/4096 limits remain.
An extension/type check is not a personal-data review. Root must inspect the
actual content,doc outcomes/limitations,links,source/backup hashes and Git diff
before writing a fresh reviewed copy with reviewed_publication=true. The original
proposed plan remains immutable. No approval or ready status is synthesized.

PowerShell from this directory:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B './prepare_stabilization_publication_v2.py' --label final-build26-publication-plan
```

CMD and Anaconda Prompt (existing interpreter; no activation/download):

```bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B prepare_stabilization_publication_v2.py --label final-build26-publication-plan
```

Verify exact host-owner absence after preparation. Refresh via a new label if
sources change; never rewrite a closed plan or backup. After the separate final
review, use frozen runtime_handoff_tools/build_handoff_v2.py once with the fresh
reviewed plan and unused output directory. It enforces20MiB ZIP/source and96MiB
full independent ZIP/expanded-restore allocation. The explanatory handoff does
not bundle the separate deployable package or model assets. Keep the old build21
handoff and all recordings/evidence intact.

V1's first run stopped before plan creation because START_HERE.md and
START_HERE_CURRENT.md intentionally name the same real current source. V1 and
its failed private scope remain unchanged. V2 only backs/restores each exact real
input once, requiring the identical SHA for an alias, while retaining both archive
member entries and the independent final source-hash recheck. All original limits,
explicit selection and unapproved-review rules remain. The old helper
prepare_stabilization_publication_v1.py and README_STABILIZATION_PUBLICATION_V1.md
are historical provenance, not current commands.
