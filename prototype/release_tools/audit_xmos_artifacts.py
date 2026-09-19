"""Inspect supplied XMOS ZIP ELF headers without extraction or hardware access."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary-zip', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
rows = []
with zipfile.ZipFile(a.binary_zip) as z:
    for name in z.namelist():
        if '/rpi/' in name.lower() and Path(name).name in {'xvf_host', 'libcommand_map.so', 'libdevice_usb.so'}:
            data = z.read(name)
            if data[:4] != b'\x7fELF':
                raise ValueError(f'Expected ELF: {name}')
            machine = struct.unpack('<H' if data[5] == 1 else '>H', data[18:20])[0]
            rows.append(dict(member=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                elf_bits={1:32, 2:64}[data[4]], machine_id=machine, architecture={40:'ARM32',183:'AARCH64',62:'X86_64'}.get(machine,'UNKNOWN')))
receipt = dict(status='PASS_HEADER_INSPECTION_ONLY', input=str(a.binary_zip), files=rows,
    arm64_compatible=bool(rows) and all(r['architecture']=='AARCH64' for r in rows),
    live_execution='NOT_TESTED', action='Build matched host and generated firmware command map natively for ARM64; do not run ARM32 rpi binaries as if qualified.')
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
print(json.dumps(receipt, indent=2))
