"""Three changed strict-type checks only; README_FIELD_LIVE_LAYOUT_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from field_live_layout_v2 import specification, reservation


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation',type=Path,required=True)
    args=parser.parse_args()
    a=json.loads((args.preparation/'ADMISSION_REVIEW_V1.json').read_bytes())
    assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
    result=[]
    for invalid in (True,1.0):
        value=specification();value['maximum_epochs']=invalid
        try:reservation(value)
        except ValueError:result.append(dict(value=repr(invalid),rejected=True))
        else:raise AssertionError('Typed maximum accepted')
    value=specification();assert reservation(value)==value['combined_request_bytes']
    result.append(dict(value='exact integer contract',accepted=True))
    row=dict(status='PASS_THREE_CHANGED_STRICT_TYPE_CASES_ONLY',cases=result,affinity=psutil.Process().cpu_affinity(),
             v2_source_sha256=hashlib.sha256(Path(__file__).with_name('field_live_layout_v2.py').read_bytes()).hexdigest(),
             old_suite_repeated=False,native_execution=False)
    with (args.preparation/'HOST_TYPE_CHECKS_V1.json').open('x',encoding='utf8') as f:json.dump(row,f,indent=2)
    print(row['status'])


if __name__=='__main__':main()
