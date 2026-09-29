"""Create a fresh controller repair for thread-exhausted startup. See README_STARTUP_CLEANUP_V1.md."""
import argparse
import ast
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    raw=a.parent.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='5c1bde56289b48da6100b123291c4e82628564ea2d1de52196f6d6be11cf7a20':
        raise ValueError('Unreviewed controller source')
    text=raw.decode('utf-8');newline='\r\n' if '\r\n' in text else '\n'
    old="""        if engine._finalization_thread is None and engine._journal is not None:
            try:engine._fail('Partial startup cancelled before capture')
            except Exception as exc:failures.append(repr(exc))
            engine._finalization_thread=threading.Thread(target=engine._watch_session,name='proto-startup-cleanup',daemon=True)
            engine._finalization_thread.start()""".replace('\n',newline)
    new="""        finalizer=engine._finalization_thread
        if (finalizer is None or finalizer.ident is None) and engine._journal is not None:
            try:engine._fail('Partial startup cancelled before capture')
            except Exception as exc:failures.append(repr(exc))
            # Thread allocation can fail during startup and again while trying
            # to launch its cleanup thread. Finalize on this command worker;
            # never join Thread objects that have not actually been started.
            engine._threads=[thread for thread in engine._threads if thread.ident is not None]
            engine._finalization_thread=None
            try:engine._watch_session()
            except Exception as exc:failures.append(repr(exc))""".replace('\n',newline)
    if text.count(old)!=1:raise ValueError('Startup cleanup anchor changed')
    out=text.replace(old,new);ast.parse(out)
    a.output.mkdir()
    with (a.output/'controller.py').open('xb') as f:f.write(out.encode('utf-8'))
    result=dict(schema='native-startup-cleanup-patch.v1',parent_sha256=hashlib.sha256(raw).hexdigest(),
                output_sha256=hashlib.sha256(out.encode('utf-8')).hexdigest(),changed_file='app/controller.py',
                application_accepted=False,change='Synchronous failed-start finalization when cleanup Thread never started; preserve all live workers and original gates')
    with (a.output/'PATCH.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))


if __name__=='__main__':main()
