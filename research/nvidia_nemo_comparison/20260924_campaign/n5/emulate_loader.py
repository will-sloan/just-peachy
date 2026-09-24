"""QEMU ARM64 CLI/C-ABI loader smoke without models/devices. README_ARM64.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

URL = 'https://archive.ubuntu.com/ubuntu/pool/universe/q/qemu/qemu-user_10.2.1+ds-1ubuntu3.2_amd64.deb'
SHA = 'f0585a9676a039f46607f185b3657c1e78c1ba4187595724cc567fcc1ae0d1b9'


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main(a):
    if a.output.exists():
        raise ValueError('Fresh loader-smoke directory required')
    a.output.mkdir(parents=True)
    os.nice(10)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    archive = a.output / 'qemu-user.deb'
    with urllib.request.urlopen(URL, timeout=60) as f:
        archive.write_bytes(f.read())
    if sha(archive) != SHA:
        raise ValueError('Ubuntu apt-index SHA256 mismatch')
    subprocess.run(['dpkg-deb', '--extract', str(archive), str(a.output/'qemu')], check=True)
    qemu = a.output / 'qemu/usr/bin/qemu-aarch64'
    arm = a.build / 'tools/arm-gnu-toolchain-12.3.rel1-x86_64-aarch64-none-linux-gnu'
    sysroot = arm / 'aarch64-none-linux-gnu/libc'
    source = a.output / 'loader.c'
    source.write_text('''#include <dlfcn.h>
#include <stdio.h>
int main(int argc, char **argv) {
  if (argc != 2) return 2;
  void *lib = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
  if (!lib) { fprintf(stderr, "%s\\n", dlerror()); return 3; }
  const char *(*version)(void) = (const char *(*)(void))dlsym(lib, "nemo_speech_asr_version");
  if (!version) return 4;
  printf("C ABI version: %s\\n", version());
  dlclose(lib);
  return 0;
}
''')
    probe = a.output / 'loader'
    commands = [[str(arm/'bin/aarch64-none-linux-gnu-gcc'), '-march=armv8-a', str(source), '-ldl', '-o', str(probe)],
                [str(qemu), '--version'],
                [str(qemu), '-L', str(sysroot), str(a.runtime/'bin/nemo-speech'), '--version'],
                [str(qemu), '-L', str(sysroot), str(a.runtime/'bin/nemo-speech'), '--help'],
                [str(qemu), '-L', str(sysroot), str(probe), str(a.runtime/'lib/libnemo_speech_asr_c.so')]]
    results = []
    for i, argv in enumerate(commands):
        tick = time.monotonic()
        result = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        log = a.output/f'{i}.log'
        log.write_text(result.stdout+result.stderr)
        results.append(dict(argv=argv, returncode=result.returncode, log=log.name,
                            sha256=sha(log), elapsed_seconds=time.monotonic()-tick))
        if result.returncode:
            break
    receipt = dict(status='EMULATED_LOADER_SMOKE_PASS' if len(results)==5 and all(r['returncode']==0 for r in results) else 'FAILED',
                   package_url=URL, package_sha256=SHA, package_source='Ubuntu apt signed-index pin; unpacked only, no package installation',
                   commands=results, models_loaded=False, microphones_opened=False,
                   functional_model_wav_smoke='NOT_TESTED', hardware='CM5_HARDWARE_NOT_TESTED',
                   timing_scope='Build/loader engineering evidence only, not inference or target latency')
    (a.output/'EMULATED_LOADER.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(dict(status=receipt['status'], output=str(a.output))))
    if receipt['status']=='FAILED':
        raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    main(p.parse_args())
