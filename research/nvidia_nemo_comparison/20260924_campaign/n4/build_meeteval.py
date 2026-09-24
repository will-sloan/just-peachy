"""Build the reviewed MeetEval source on Windows; see README_METRICS.md."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
from common import sha, bind, freeze

EXPECTED = '02d3a359f375d39c67dfb8fe1c061e7dac19d6fc1fb89ee72d793a5813dafeb2'


def main(args):
    import psutil
    psutil.Process().cpu_affinity([4])
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    if sha(args.archive) != EXPECTED:
        raise ValueError('Only the reviewed official MeetEval 0.4.3 source is admitted')
    args.output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               MAX_JOBS='1', CL='/std:c++20')
    command = [str(args.python), '-m', 'pip', 'install', '--no-build-isolation', '--no-deps',
               '--report', str(args.output/'install.json'), str(args.archive)]
    with (args.output/'build.log').open('x', encoding='utf-8') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env,
                                creationflags=subprocess.CREATE_NO_WINDOW, timeout=900)
    receipt = dict(status='BUILT' if result.returncode == 0 else 'FAILED', exit_code=result.returncode,
        input=bind(args.archive), python=bind(args.python), command=command,
        build_flags={'CL':'/std:c++20', 'MAX_JOBS':'1'}, code_changes=[],
        reason='Unmodified source uses C++ designated initializers; MSVC default rejected them (C7555).',
        prior_attempt='Default flags failed; preserved tool output. No metric algorithm changes.',
        log=bind(args.output/'build.log'))
    freeze(args.output/'BUILD_RECEIPT.json', receipt)
    print(json.dumps(receipt, indent=2))
    return result.returncode


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--python', type=Path, required=True)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    sys.exit(main(p.parse_args()))
