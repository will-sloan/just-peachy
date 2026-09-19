"""Independent inventory adapter guard review. README_S6C_INVENTORY_ADAPTER_REVIEW_V3.md."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

SIM=Path(__file__).resolve().parents[1];REPORT=SIM/'reports/S6C/20260910T123540Z'
def bind(path):
    p=Path(path).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def main(output):
    if output.exists():raise ValueError('Preserve prior review')
    path=REPORT/'execution_inventory/ADAPTER_V3_CHECKS_V2.json';receipt=json.loads(path.read_text(encoding='utf-8-sig'));rb=bind(path)
    assert rb['sha256']=='74128457b29dd92097fcb0141ee6965c02b3ceef0e03210e1081639bec296d52';count=1
    for b in receipt['sources']+[receipt['base_collector'],receipt['prior_check_receipt']]:assert bind(b['path'])==b;count+=1
    for row in receipt['preserved_prior_sources']:
        assert bind(row['snapshot']['path'])==row['snapshot'];count+=1
        assert all(row['source'][k]==row['snapshot'][k] for k in ('bytes','sha256'));count+=1
    source=next(b for b in receipt['sources'] if Path(b['path']).suffix=='.py')
    spec=importlib.util.spec_from_file_location('inventory_v3_independent_review',source['path']);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    pure=module.checks();assert pure==receipt['checks'];count+=1
    with patch.object(module.psutil,'Process',return_value=SimpleNamespace(create_time=lambda:float('nan'))):
        assert module.process_state(1,1)['alive'] is None;count+=1
    original=(module.base.collect_auxiliary,module.base.process_state,module.base.validate_native)
    try:
        with module.patched_base():raise RuntimeError('injected review failure')
    except RuntimeError:pass
    assert original==(module.base.collect_auxiliary,module.base.process_state,module.base.validate_native);count+=1
    with tempfile.TemporaryDirectory(prefix='s6c_inventory_adapter_review_') as temporary:
        root=Path(temporary);report=root/'report';report.mkdir();output_root=root/'snapshot';(output_root/'source_snapshots').mkdir(parents=True)
        reader=module.base.MetadataReader(output_root);declared=SimpleNamespace(add=lambda *a:None);rows=[];issues=[]
        original_aux=lambda *a:dict(owner_observations=[])
        with patch.object(module,'REPORT',report):
            value=module.auxiliary_adapter(original_aux,reader,declared,issues,rows,{},[])
        assert rows==[] and issues==[] and value['execution_inventory_adapter']['long_lineage_records']==[];count+=1
        # An invalid outer admission alone cannot create a physical model run,
        # yet must prevent a false all-closed interpretation.
        bad=report/'long_native_epoch4/epoch4_fixture/invocations/id/ADMISSION.json';bad.parent.mkdir(parents=True);bad.write_text('{"status":"INVALID"}',encoding='utf-8')
        second=root/'snapshot2';(second/'source_snapshots').mkdir(parents=True);reader=module.base.MetadataReader(second);rows=[];issues=[]
        with patch.object(module,'REPORT',report):
            value=module.auxiliary_adapter(original_aux,reader,declared,issues,rows,{},[])
        assert rows==[] and len(issues)==1;count+=1
        owners=value['owner_observations'];assert len(owners)==1 and owners[0]['process_state']['alive'] is None;count+=1
        assert module.base.closure_scope(owners)['status']=='CLOSURE_UNVERIFIED';count+=1
    result=dict(schema='s6c_inventory_adapter_independent_review.v3',status='PASS_SOURCE_AND_MODEL_FREE_LINEAGE_GUARDS',checks=count,adapter_pure_checks=pure,
        admitted_receipt=rb,sources=receipt['sources'],base_collector=receipt['base_collector'],reviewer=bind(__file__),readme=bind(Path(__file__).with_name('README_S6C_INVENTORY_ADAPTER_REVIEW_V3.md')),
        resolved_findings=['Standalone complete outer chain now requires native COMPLETE schema/status, exact source duration/gallery fields, and successful pending-release native outcome.'],
        scope='Exact source/README/receipt preservation, read-only code review and constructed metadata/owner failures only. No live inventory collection, physical receipt census, waveform/model/vector/prediction/event read or native/model launch. Actual future chain admission requires its later saved snapshot.',
        boundaries=['Outer admission remains owner lineage, not a model session.','Unavailable or invalid closure stays null/unverified; current physical inference totals remain separate from references.','Actual epoch4 execution and original epoch2 source composition remain distinct.','Unchanged base collector retains its interval-snapshot and metadata-only payload-binding limits.'])
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(bind(output),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
