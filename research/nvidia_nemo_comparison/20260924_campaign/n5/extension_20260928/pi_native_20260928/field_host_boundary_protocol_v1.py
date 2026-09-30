"""Changed affinity/finite boundary only; README_FIELD_HOST_BOUNDARY_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
EARLY_AFFINITY = psutil.Process().cpu_affinity()
assert EARLY_AFFINITY == [14], 'CPU14 required before evidence reads'
import argparse
import json
from pathlib import Path
import time
import field_host_finite_v1 as h


def main(root):
    assert psutil.Process().cpu_affinity() == [14]
    start = time.monotonic()
    main_store = h.HostStore(root/'host')
    a = json.loads((root/'host/metadata/ADMISSION.json').read_bytes())
    for row in a['bindings']:
        assert h.digest(Path(row['path']).read_bytes()) == row['sha256']
    assert a['affinity'] == a['job_affinity'] == [14]
    fixtures = root/'fixtures'; fixtures.mkdir()
    cases = []
    bad = [('positive',b'{"x":1e400}'), ('negative-nested',b'{"x":[-1e400]}'),
           ('overwritten-key',b'{"x":1e400,"x":0}')]
    for name, raw in bad:
        dst = fixtures/name
        try:
            h.HostStore(dst).create({'RESULT.json':raw})
        except ValueError as exc:
            assert not dst.exists()
            cases.append({'case':name,'before_directory':True,'input':raw.decode('ascii'),
                          'error':str(exc)})
        else:
            raise AssertionError('Overflow accepted')
    s = h.HostStore(fixtures/'first-write').create({})
    try:
        s.write('RESULT.json',bad[0][1])
    except ValueError as exc:
        assert not list((s.root/'metadata').iterdir())
        cases.append({'case':'first-write-overflow','no_pending_or_final':True,'error':str(exc)})
    else:
        raise AssertionError('Overflow file published')
    # One positive at the finite upper boundary; not the old generic writer suite.
    finite = b'{"maximum":1.7976931348623157e308,"minimum":-1.7976931348623157e308,"tiny":1e-400}'
    s.write('RESULT.json',finite)
    assert (s.root/'metadata/RESULT.json').read_bytes() == finite
    cases.append({'case':'finite-boundary-bytes-exact','bytes':len(finite),'sha256':h.digest(finite)})
    end_affinity = psutil.Process().cpu_affinity()
    assert end_affinity == [14]
    main_store.json('RESULT.json',{'status':'PASS_CHANGED_HOST_AFFINITY_AND_FINITE_BOUNDARY',
        'case_count':5,'cases':cases,'early_affinity':EARLY_AFFINITY,'end_affinity':end_affinity,
        'seconds':time.monotonic()-start,'rss_bytes':psutil.Process().memory_info().rss,
        'old_19_cases_rerun':False,'capture':False,'native_compute':False})
    main_store.json('worker-closure.json',{'logical_success':True,'protocol_returned':True,'affinity':[14]})
    return 0


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    try:
        raise SystemExit(main(a.root))
    except Exception as exc:
        s=h.HostStore(a.root/'host')
        failure=s.failure('worker',repr(exc).encode('utf-8'),exc)
        s.json('worker-closure.json',failure)
        raise
