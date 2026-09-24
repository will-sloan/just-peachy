"""Static wheel/ELF dependency audit; never loads a model. See README_ARM64.md."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zipfile

SYSTEM = {'libc.so.6', 'libm.so.6', 'libdl.so.2', 'librt.so.1', 'libpthread.so.0',
          'libstdc++.so.6', 'libgcc_s.so.1', 'libgomp.so.1', 'libutil.so.1',
          'libresolv.so.2', 'libz.so.1', 'ld-linux-aarch64.so.1'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def elf(data, name, temp):
    if data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError('Expected little-endian ELF64 AArch64: ' + name)
    temp.write_bytes(data)
    out = subprocess.check_output(['readelf', '--wide', '-d', '-V', str(temp)], text=True)
    needed = re.findall(r'\(NEEDED\).*?\[(.*?)\]', out)
    soname = re.findall(r'\(SONAME\).*?\[(.*?)\]', out)
    versions = sorted(set(re.findall(r'\b(?:GLIBC|GLIBCXX|CXXABI)_[0-9.]+', out)))
    limits = {'GLIBC': (2, 36), 'GLIBCXX': (3, 4, 30), 'CXXABI': (1, 3, 13)}
    for v in versions:
        family, value = v.split('_')
        if tuple(map(int, value.split('.'))) > limits[family]:
            raise ValueError('Newer-than-Bookworm ABI: ' + name + ' ' + v)
    return dict(path=name, bytes=len(data), sha256=digest(data), machine='AArch64', bits=64,
                needed=needed, soname=soname, symbol_versions=versions,
                rpath=re.findall(r'\((?:RPATH|RUNPATH)\).*?\[(.*?)\]', out))


def main(a):
    if a.output.exists():
        raise ValueError('Fresh audit output required')
    rows, wheels = [], []
    with tempfile.TemporaryDirectory(prefix='jp-n5-elf-') as tmp:
        temp = Path(tmp) / 'binary'
        if a.wheelhouse:
            expected = json.loads(a.publisher_receipt.read_text())['files']
            if set(p.name for p in a.wheelhouse.glob('*.whl')) != set(r['filename'] for r in expected):
                raise ValueError('Wheel inventory changed')
            for r in expected:
                p = a.wheelhouse / r['filename']
                data = p.read_bytes()
                if digest(data) != r['sha256']:
                    raise ValueError('Wheel differs from published hash: ' + p.name)
                wheels.append(dict(filename=p.name, bytes=len(data), sha256=digest(data)))
                with zipfile.ZipFile(p) as z:
                    for n in z.namelist():
                        if n.endswith('/'):
                            continue
                        content = z.read(n)
                        if content[:4] == b'\x7fELF':
                            rows.append(elf(content, p.name + '/' + n, temp))
                        elif n.endswith(('.so', '.dll', '.pyd', '.dylib')) or content[:2] == b'MZ':
                            raise ValueError('Unexpected non-AArch64 executable: ' + n)
        if a.native:
            for p in sorted(a.native.iterdir()):
                if p.is_file() and not p.is_symlink() and p.read_bytes()[:4] == b'\x7fELF':
                    rows.append(elf(p.read_bytes(), p.name, temp))
    names = {Path(r['path']).name for r in rows} | {s for r in rows for s in r['soname']}
    unresolved = sorted({n for r in rows for n in r['needed']} - names - SYSTEM)
    if not rows or unresolved:
        raise ValueError('No binaries or undeclared dependencies: ' + str(unresolved))
    result = dict(status='ARM64_BUILD_VERIFIED_STATIC_ONLY', target='Bookworm aarch64 CPython 3.11',
                  checks=['ELF64 little-endian AArch64', 'publisher wheel SHA256', 'NEEDED inventory',
                          'Bookworm symbol-version ceilings'], wheels=wheels, binaries=rows,
                  system_needed=sorted({n for r in rows for n in r['needed']} & SYSTEM),
                  loader_resolution='NOT_EXECUTED', model_load='NOT_TESTED',
                  functional_smoke='NOT_TESTED', hardware='CM5_HARDWARE_NOT_TESTED',
                  limitations=['Static NEEDED inventory does not prove loader search paths or optional dlopen dependencies',
                               'No instruction disassembly or CM5 CPU/2GB capacity qualification'])
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(status=result['status'], wheels=len(wheels), binaries=len(rows))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wheelhouse', type=Path)
    p.add_argument('--publisher-receipt', type=Path)
    p.add_argument('--native', type=Path)
    p.add_argument('--output', type=Path, required=True)
    main(p.parse_args())
