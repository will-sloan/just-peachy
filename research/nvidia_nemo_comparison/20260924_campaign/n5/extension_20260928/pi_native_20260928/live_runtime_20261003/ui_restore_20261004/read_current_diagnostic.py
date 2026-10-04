"""Read current failures before historical admission checks; README_DIAGNOSTIC.md."""
import psutil
psutil.Process().cpu_affinity([14])
import sys
from pathlib import Path

# The existing driver persists both actual host and native identities, source
# backups, raw streams and independent post-exit check. Only read-only evidence
# is emitted early; the historical ownership verifier still executes unchanged.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import host_operations_v6 as driver

original = driver.bind_native_owner_references
def bind(native, new_owners, unit_owners):
    native = original(native, new_owners, unit_owners)
    boundary = 'owner_hash=hashlib.sha256();count=0;typed=0;all_ids=set()'
    if native.count(boundary) != 1:
        raise ValueError('Exact historical decoder boundary required')
    evidence = """
assert OPERATION_WRITES is False
diagnostic_namespace=dict(__name__='current_readonly_diagnostic',PAYLOAD=ACTION_PAYLOAD)
exec(compile(ACTION_SOURCE,'<pinned-current-diagnostic>','exec'),diagnostic_namespace)
diagnostic=json.dumps(diagnostic_namespace['RESULT'],sort_keys=True,allow_nan=False)
assert len(diagnostic.encode())<=2*1024**2
print('CURRENT_DIAGNOSTIC='+diagnostic,flush=True)
"""
    return native.replace(boundary, evidence+'\n'+boundary)
driver.bind_native_owner_references = bind
driver.main()
