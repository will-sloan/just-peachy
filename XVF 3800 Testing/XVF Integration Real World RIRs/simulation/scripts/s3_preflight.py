"""S3 read-only evidence binding and exclusive live snapshot. Never opens audio."""
from pathlib import Path
import argparse, hashlib, json, msvcrt, socket, sys, zipfile
import xml.etree.ElementTree as ET
from s0_common import ROOT, SIM, HashCache, save, now

def run(report):
    report=Path(report); report.mkdir(parents=True,exist_ok=True)
    cache=HashCache(); pack=ROOT/'Just_Peachy_S3_Codex_Pack'
    checks=[]
    for line in (pack/'SHA256SUMS.txt').read_text().splitlines():
        if not line.strip(): continue
        expected,rel=line.split(maxsplit=1); p=pack/rel.strip().lstrip('*')
        binding=cache.bind(p); checks.append({**binding,'expected_sha256':expected,'match':binding['sha256']==expected})
    assert all(c['match'] for c in checks)
    workbook=Path('C:/Users/amiri/Downloads/Just_Peachy_Master_Workbook_Progress_Through_S2_V6.docx')
    wb=cache.bind(workbook)
    assert wb['sha256']=='df9bc6e8159f2980d9d8a7924999fb3229a8e78e8019fc54b698c3ad31b5ea17'
    with zipfile.ZipFile(workbook) as z:
        tree=ET.fromstring(z.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs=[''.join(p.itertext()) for p in []]
        paragraphs=[''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in tree.findall('.//w:p',ns)]
    (report/'workbook_V6_extracted.txt').write_text('\n'.join(paragraphs),encoding='utf-8')
    context=json.loads((pack/'S3_INPUT_CONTEXT.json').read_text(encoding='utf-8-sig'))
    save(report/'input_bindings.json',{'observed_utc':now(),'pack_files':checks,'workbook':wb,'pack_context':context})
    sys.path.insert(0,str(ROOT)); import measurement_app
    from measurement_app.core import Control, devices, HOST
    live={'observed_utc':now(),'scope':'read-only; no audio stream or setters','errors':[]}
    lock=None; owned=False
    try:
        for port in [8765,8766,8767]:
            with socket.socket() as s:
                s.settimeout(.3)
                if s.connect_ex(('127.0.0.1',port))==0: raise RuntimeError(f'Recorder server present on {port}; ownership not assumed')
        lock=(ROOT/'measurement_app/hardware.lock').open('r+b');lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True
        live['endpoints']=[d for d in devices() if any(v in d['name'].lower() for v in ['xvf','xmos'])]
        c=Control(report/'preflight_commands')
        live['identity']=c.identify()
        dump=c.query('--dump-params');(report/'initial_params_dump.txt').write_text(dump,encoding='utf-8')
        names=['AUDIO_MGR_OP_ALL','AUDIO_MGR_OP_PACKED','AUDIO_MGR_OP_UPSAMPLE','AEC_ASROUTONOFF','AEC_ASROUTGAIN','GPO_PORT_PIN_INDEX']
        live['settings']={n:c.values(n) for n in names}
        try:live['optional_selected_azimuth_probe']=c.query('AUDIO_MGR_SELECTED_AZIMUTHS')
        except Exception as e:live['optional_selected_azimuth_probe_error']=str(e)
        live['host_executable']=cache.bind(HOST)
        live['status']='READ_ONLY_SNAPSHOT_COMPLETE'
    except Exception as e:
        live['errors'].append(repr(e));live['status']='READ_ONLY_SNAPSHOT_BLOCKED'
    finally:
        if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        if lock:lock.close()
        live['hardware_lease_released']=True;live['audio_streams_opened']=0;live['setters_issued']=0
        save(report/'preflight.json',live);cache.flush()
    print(json.dumps(live,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args();run(a.report)
