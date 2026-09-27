"""Complete producer manifest for diagnostics; README_GUARDED_METADATA_PROBE_V1.md."""
from pathlib import Path
import sys

from common import bind, freeze, load, verify
import guarded_execution_v1 as resource
from metric_process import identity, pin
from reservation_budget_v1 import require

HERE = Path(__file__).resolve().parent
SCHEMA = 'just-peachy.guarded-metadata-probe.v1'
OWN = ('guarded_metadata_probe_v1.py', 'test_guarded_metadata_probe_v1.py',
       'README_GUARDED_METADATA_PROBE_V1.md')
ENTRIES = {'reader': 'probe_panel_scoring_guarded_v2.py',
           'planner': 'probe_paced_panel_plan_guarded_v2.py'}
CAP = 8*1024**2
SECONDS = 1200


def validate_manifest(code, resource_code, entry):
    """Require the exact entry and every resource dependency; no list truncation."""
    require(isinstance(code, list) and 0 < len(code) <= 512, 'Invalid producer source census')
    require(isinstance(resource_code, list) and bool(resource_code), 'Missing resource sources')
    entries = {}
    for b in code:
        require(isinstance(b, dict) and set(b) == {'path', 'sha256', 'bytes'}, 'Invalid source binding')
        require(isinstance(b['path'], str) and Path(b['path']).is_absolute()
                and isinstance(b['sha256'], str) and len(b['sha256']) == 64
                and all(c in '0123456789abcdef' for c in b['sha256'])
                and type(b['bytes']) is int and b['bytes'] >= 0, 'Invalid source metadata')
        require(b['path'] not in entries, 'Duplicate producer source')
        entries[b['path']] = b
    require(entries.get(entry['path']) == entry, 'Exact entry script must be a producer source')
    require(all(entries.get(b['path']) == b for b in resource_code), 'Resource dependency omitted or changed')


def code_bindings(base, role):
    require(role in ENTRIES, 'Unknown metadata probe role')
    values = list(base) + [bind(HERE/n) for n in OWN+(ENTRIES[role],)]
    unique = {}
    for b in values:
        require(b['path'] not in unique or unique[b['path']] == b, 'Conflicting metadata dependency')
        unique[b['path']] = b
    code = [b for _, b in sorted(unique.items())]
    validate_manifest(code, resource.code_bindings(), bind(HERE/ENTRIES[role]))
    return code


def start_output(output, plan_binding, code, role, extra):
    """Resource-gated diagnostics only; cannot grant application execution."""
    p = pin()
    require(role in ENTRIES, 'Unknown metadata probe role')
    entry = bind(HERE/ENTRIES[role]); resource_code = resource.code_bindings()
    require(Path(sys.argv[0]).resolve() == Path(entry['path']), 'Different running probe entrypoint')
    validate_manifest(code, resource_code, entry)
    for b in code+[plan_binding]: verify(b)
    plan = load(plan_binding['path'])
    require(plan['scope'] == 'modes-panel' and plan['required'] == 1536, 'Exact original modes scope required')
    local = Path(plan['context']['source_receipt']['path']).parents[2].resolve(strict=True)
    output = Path(output).resolve()
    require(not output.exists() and output.is_relative_to(local/'n4') and output != local/'n4',
            'Fresh private diagnostic output required')
    envelope = dict(schema=SCHEMA, kind='metadata-probe', role=role, entry_script=entry,
        code=code, resource_code=resource_code, resource_qualification=resource.qualification(),
        original_plan=plan_binding, allocation_bytes=CAP, maximum_seconds=SECONDS,
        development_only=True, models_loaded=0, application_execution_authorized=False,
        N4_accepted=False, N5_complete=False)
    admission = dict(owner=identity(p), plan=plan_binding, code=code, resource_code=resource_code,
        entry_script=entry, allocation_bytes=CAP, maximum_seconds=SECONDS,
        cpu_affinity=p.cpu_affinity(), models_loaded=0, integrated_N4_cells=0)
    require(not set(extra).intersection(set(admission)|{'execution_plan'}), 'Extra metadata replaces provenance')
    freeze(output/'EXECUTION_PLAN.json', envelope)
    admission.update(extra); admission['execution_plan'] = bind(output/'EXECUTION_PLAN.json')
    freeze(output/'ADMISSION.json', admission)
    main_plan = load(local/'n4/integrated-main-v3/RESULT.json')['plan']
    # The original resource guard, full census, exact owner and production
    # allocation checks stay unchanged. Its producer code is now complete.
    return resource.Guard(local, output, code, main_plan, SECONDS, production=True)
