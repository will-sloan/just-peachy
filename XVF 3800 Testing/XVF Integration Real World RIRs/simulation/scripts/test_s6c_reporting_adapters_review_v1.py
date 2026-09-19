"""Independent model-free adapter review; README_TEST_S6C_REPORTING_ADAPTERS_REVIEW_V1.md."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
import s6c_common_duration_results_v2 as duration
import test_s6c_cadence_scorer_admission as cadence

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'

def bind(path):
 p=Path(path);raw=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def run():
 names=['s6c_common_duration_results.py','s6c_common_duration_results_v2.py','README_S6C_COMMON_DURATION_RESULTS_V2.md',
   'test_s6c_cadence_scorer_admission.py','README_TEST_S6C_CADENCE_SCORER_ADMISSION.md',*cadence.core.CODES]
 sources=[bind(SIM/'scripts'/n) for n in dict.fromkeys(names)];checks=[]
 def ok(value,label):
  if not value:raise AssertionError(label)
  checks.append(label)
 old=ast.parse((SIM/'scripts/s6c_common_duration_results.py').read_bytes())
 new=ast.parse((SIM/'scripts/s6c_common_duration_results_v2.py').read_bytes())
 def function(tree,name):return ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
 for name in ['val','corpus','aggregate','turn_key','paired','fixtures']:
  ok(function(old,name)==function(new,name),'duration original function exact: '+name)
 original=duration.fixtures();buffers=duration.buffer_fixtures()
 ok(original['status']==buffers['status']=='PASS','all5 original and4 exact-buffer fixtures pass')
 priorpath=REPORT/'independent_review/CADENCE_SCORER_ADMISSION_V1.json'
 priorraw=priorpath.read_bytes();prior=json.loads(priorraw)
 ok(hashlib.sha256(priorraw).hexdigest()=='fc49bc76f6473bd662982c182bfc6bc09285919f44da88a9c00344df4b68cb23','exact cadence238 admission receipt')
 for b in prior['sources']:
  actual=bind(b['path']);ok(all(actual[k]==b[k] for k in ('bytes','sha256')),'held cadence source '+Path(b['path']).name)
 captured=[]
 def capture(path,value):
  ok(Path(path).resolve()==priorpath.resolve(),'only expected cadence receipt publication intercepted')
  captured.append(value)
 # The actual admission routine executes; only its final receipt write is
 # intercepted. All fixture inputs are metadata or temporary synthetic values.
 with patch.object(cadence.core,'save',capture):cadence.run()
 ok(len(captured)==1,'one actual admission result captured without overwriting original')
 actual=captured[0]
 for field in ['checks','core_fixtures','registered_labels','added_labels','registered_routes','registry','registry_sources','command_registry_arguments']:
  ok(actual[field]==prior[field],'actual cadence admission reproduces '+field)
 ok(priorpath.read_bytes()==priorraw,'original cadence receipt unchanged')
 ok([bind(row['path']) for row in sources]==sources,'all active scoring/helper source bytes unchanged')
 result=dict(status='PASS_BOUNDED_REPORTING_ADAPTER_REVIEW',created_utc=datetime.now(timezone.utc).isoformat(),checks=checks,
   source_bindings=sources,original_cadence_admission=bind(priorpath),duration_fixtures=original,duration_buffer_fixtures=buffers,
   cadence_actual_checks=actual['checks'],cadence_core_fixtures=actual['core_fixtures'],
   scope='Read-only source/formula/metadata admission and model-free fixtures. Common-duration V2 full result collection and prediction scoring were not executed. No native/model/hardware calls. Original cadence receipt publication was intercepted and exact source bytes rechecked.',
   interpretation=['Full common-duration collector keeps exact777 source occurrence keys and support/roster denominators across tiers; both-observed waits exclude censored missing instead of substituting zero.',
    'Retained transcript-row exposure and live sole-active speech samples remain separate. No new metric formulas or uncertainty intervals.',
    'Existing append-only V3 contract admits238 labels with original234 preserved. Four new no-gallery floor-only settings add declaration identity; old outputs retain their original cache identities.'],
   limitations=['This is prospective source-level admission, not independent numerical review of future2880-output common-duration results.',
    'The collector trusts the explicitly bound completed scorer tables; it does not rerun full source/prediction support scoring.'],
   reviewer_code=bind(__file__),reviewer_readme=bind(Path(__file__).with_name('README_TEST_S6C_REPORTING_ADAPTERS_REVIEW_V1.md')))
 out=REPORT/'independent_review/REPORTING_ADAPTERS_COMPONENT_REVIEW_V1.json'
 with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps(dict(status=result['status'],checks=len(checks),receipt=bind(out))))

if __name__=='__main__':run()
