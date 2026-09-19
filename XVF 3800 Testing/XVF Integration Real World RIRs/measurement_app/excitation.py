from pathlib import Path
import zipfile,json,hashlib
from .core import BASE,sha,write_json

ASSETS=BASE/'measurement_app/assets/excitation_v2'
ZIP=Path('C:/Users/amiri/Downloads/Just_Peachy_XVF3800_Excitation_and_Logging_Pack_V2.zip')

def ensure_assets():
    manifest=ASSETS/'manifest.json'
    if not manifest.exists():
        ASSETS.mkdir(parents=True,exist_ok=False)
        with zipfile.ZipFile(ZIP) as z:
            entries={Path(n).name:n for n in z.namelist() if not n.endswith('/')}
            m=json.loads(z.read(entries['manifest.json']))
            for row in m['files']:
                name=row['name']
                if Path(name).name!=name:raise RuntimeError('Invalid excitation manifest path')
                payload=z.read(entries[name])
                if len(payload)!=row['bytes'] or hashlib.sha256(payload).hexdigest()!=row['sha256']:raise RuntimeError('Excitation hash mismatch: '+name)
                (ASSETS/name).write_bytes(payload)
            (ASSETS/'manifest.json').write_bytes(z.read(entries['manifest.json']))
            write_json(ASSETS/'archive_provenance.json',{'archive':str(ZIP),'archive_sha256':sha(ZIP)})
    m=json.loads(manifest.read_text())
    for row in m['files']:
        if sha(ASSETS/row['name'])!=row['sha256']:raise RuntimeError('Excitation asset was changed: '+row['name'])
    return m

def list_excitations():
    m=ensure_assets()
    return [{'id':r['name'],'label':r['name'].replace('JP_XVF_','').replace('_48k_PCM16.wav',''),
             'duration_seconds':r['duration_sec'],'path':str(ASSETS/r['name']),'sha256':r['sha256']}
            for r in m['files'] if r['name'].endswith('48k_PCM16.wav') and 'GAP_PLUS_ESS' in r['name']]

def get_excitation(name):
    choices={e['id']:e for e in list_excitations()}
    if name not in choices:raise ValueError('Select an excitation from the verified V2 pack')
    return choices[name]
