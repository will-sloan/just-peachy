# Archive metadata partition within the existing64KiB control slot
Purpose: F06/F12/F15 allow ReDimNet's existing personal-gallery reference provenance to fit the initial archive metadata. The candidate7 TitaNet archive plus the actual private ReDimNet gallery projects a37367-byte complete record. The old32768-byte initial partition rejected startup before model/capture.

The new explicit partition uses39936bytes initial +24576bytes unchanged runtime reserve +1024bytes join reserve =65536bytes, exactly the original complete control-file cap. The primary/pending allocations,2MiB auxiliary reserve,16MiB event budget,64code members,128KiB member cap, all writer/validator function bodies and every metadata field remain unchanged. Old source/policies/failures remain immutable. New admitted runtime policies pin this new capsule; no historical allowance is changed.

Inputs: exact candidate7 COMMON_BUNDLE bytes. Output: new capsule plus explicit partition/hash receipt. API: derive(raw). The installer supplies the returned bytes and creates a fresh root. No direct model/device action.

PowerShell focused check:
~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\check_runtime_archive_partition_v1.py --private PRIVATE_ROOT --output FRESH_OUTPUT
~~~
CMD / Anaconda Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B check_runtime_archive_partition_v1.py --private PRIVATE_ROOT --output FRESH_OUTPUT
~~~
The check reuses actual private archive/gallery metadata, preserves their bytes, measures the new lossless projection and verifies exact overflow/finalization bounds. It does not construct a model, start capture or establish identity accuracy. Full native ReDimNet acceptance follows in a fresh slot.
