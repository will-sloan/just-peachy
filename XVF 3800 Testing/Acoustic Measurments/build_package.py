from pathlib import Path
import json, zipfile, time, hashlib, csv
from collections import Counter

STAGE = Path(__file__).resolve().parent
ROOT = Path('C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement')

def build():
    rows = json.loads((STAGE/'inventory.json').read_text(encoding='utf-8'))
    unique = {r['sha256']:r for r in rows}
    manifest = {'format':'XVF lossless deduplicated ZIP v1','files':[{k:r[k] for k in ('path','bytes','mtime_ns','sha256')} for r in rows],
                'directories':['project/'+p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_dir()],
                'logical_bytes':sum(r['bytes'] for r in rows)}
    (STAGE/'RESTORE_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    last = time.monotonic(); processed = 0
    with zipfile.ZipFile(STAGE/'XVF_DATA.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for i,(digest,row) in enumerate(unique.items()):
            path = Path(row['source']); stat = path.stat()
            assert stat.st_size == row['bytes'] and stat.st_mtime_ns == row['mtime_ns'], path
            z.write(path,'objects/'+digest)
            processed += row['bytes']
            if time.monotonic()-last>15:
                print(json.dumps({'compressed_unique_files':i+1,'unique_files':len(unique),'input_bytes':processed,'archive_bytes':z.fp.tell()}),flush=True)
                last = time.monotonic()
    print(json.dumps({'archive_bytes':(STAGE/'XVF_DATA.zip').stat().st_size,'unique_objects':len(unique)}),flush=True)

def index():
    runs = []; rooms = Counter(); statuses = Counter()
    for p in sorted((ROOT/'XVF_MEASUREMENT_WORK/experiments').iterdir()):
        if not p.is_dir() or not (p/'request.json').is_file(): continue
        req = json.loads((p/'request.json').read_text(encoding='utf-8'))
        result = json.loads((p/'result.json').read_text(encoding='utf-8')) if (p/'result.json').is_file() else {}
        s = req.get('setup',{}); source = s.get('source',{}); d = s.get('device',{})
        row = {'run_id':p.name,'recorded_utc':result.get('recorded_utc'),'status':result.get('status','INCOMPLETE'),
               'phase':s.get('pilot_phase'),'trial_label':s.get('trial_label'),'room_table':s.get('room_name'),
               'recorder_position':s.get('position_name'),'distance_m':source.get('distance_to_array_m'),
               'speaker_angle_deg':source.get('azimuth_lab_deg'),'orientation':d.get('orientation'),
               'obstructed':s.get('obstruction',{}).get('present'),'domain':req.get('domain'),
               'software_gain_db':req.get('playback_gain_db'),'excitation_id':req.get('excitation_id'),
               'path':'project/XVF_MEASUREMENT_WORK/experiments/'+p.name}
        runs.append(row); rooms[str(row['room_table'])] += 1; statuses[row['status']] += 1
    with (STAGE/'RECORDINGS_INDEX.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(runs[0]));w.writeheader();w.writerows(runs)
    (STAGE/'DATASET_SUMMARY.json').write_text(json.dumps({'indexed_runs':len(runs),'rooms':dict(rooms),'original_statuses':dict(statuses)},indent=2),encoding='utf-8')
    print(json.dumps({'indexed_runs':len(runs),'rooms':dict(rooms),'statuses':dict(statuses)}),flush=True)

if __name__ == '__main__':
    import sys
    index() if '--index-only' in sys.argv else build()
