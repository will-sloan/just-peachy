# Runtime controller and embedding-gallery bindings
Purpose: finish checklist F06/F12 by reusing the installed backend registry, Field controller selectors, PersonalStore initializer and NeMo TitaNet store subclass. This selects the actual model composition rather than changing only its label.

Inputs: exact installed backend catalogue and profile definition from field_runtime_profiles_v1; the existing derived controller_type AST; actual installed application modules; independently pinned gallery snapshot manifests and separate E0/E1 roots. Each snapshot remains within its explicitly reserved <=128MiB,256-file,64-directory bounds. Its actual complete membership, identity and hashes are checked before a store can use it. Empty galleries remain empty; no enrollment, vector conversion, fallback, calibration or quality claim occurs.

Outputs: an in-memory registry row; a controller factory with its exact backend/logical-mode/tap selectors and display label; a PersonalStore subclass whose original initializer uses only the verified read-only gallery roots. The original TitaNet factory still supplies its own preprocessing and namespace/calibration. ReDimNet requires no TitaNet gallery/model dependency. All other installed Field methods remain unchanged. Original source files are never edited.

API:
- bind_registry(module, catalog_raw, definition)
- specialize_factory(derived_factory_node, definition)
- verify_gallery(root, manifest_raw, manifest_sha256, namespace, guard)
- readonly_store_type(people_module, data_root, galleries, namespace, guard)

The caller must pin the application source origins and admission/profile, keep the original physical write guard, prohibit enrollment and gallery mutations during recording, and reserve complete snapshot storage independently. This source will be embedded into the reviewed existing controller capsule to preserve the original module-count cap. The capsule, manager, deployment and native acceptance are still separate required work.

## Changed host check
check_runtime_controller_profile_v1.py uses the actual installed selector methods and original PersonalStore/TitaNet factory with explicit stub controller dependencies and empty host gallery fixtures. It does not import a neural model, construct the complete Controller, touch the Pi, or establish a physical I/O sandbox.

After a fresh bounded host scope and exact source backup/independent restore, run once into a never-used output directory.

PowerShell:
~~~powershell
$python = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $python -B ./check_runtime_controller_profile_v1.py --installed 'G:/verified-installed-release-mirror' --output 'G:/approved-scope/new-profile-check'
~~~
Command Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B check_runtime_controller_profile_v1.py --installed "G:/verified-installed-release-mirror" --output "G:/approved-scope/new-profile-check"
~~~
Anaconda Prompt: activate the existing psutil environment and change to this source directory, then:
~~~bat
python -B check_runtime_controller_profile_v1.py --installed "G:/verified-installed-release-mirror" --output "G:/approved-scope/new-profile-check"
~~~
Outputs are REGISTERED_OWNER.json, small private empty-gallery manifests, and RESULT.json. Preserve failed output; do not rerun a healthy check.

