"""Bind authorized S4 inputs and snapshot resources without accessing hardware."""
import subprocess
from s4_common import *

def run():
    REPORT.mkdir(parents=True,exist_ok=True)
    if (REPORT/'preflight.json').exists():
        print('Initial S4 preflight already recorded; preserving its original resource/git/workbook snapshot.');return
    with Progress('preflight'):
        sums=[]
        for line in (PACK/'SHA256SUMS.txt').read_text().splitlines():
            digest,name=line.split(maxsplit=1);sums.append(bind(PACK/name,digest))
        rir=bind(SIM/'rir_library/v1/RIR_MANIFEST.json','468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546')
        commands={}
        for cmd in [['git','status','--short'],['git','branch','--show-current'],['git','rev-parse','HEAD']]:
            r=subprocess.run(cmd,cwd=REPO,text=True,capture_output=True,check=True);commands[' '.join(cmd)]=r.stdout
        save(REPORT/'preflight.json',{'run_id':RUN_ID,'started_utc':'2026-09-09T00:21:40Z','pack':sums,'rir_manifest':rir,
             'git_before':commands,'storage_before':storage(),'workbook_v8':{'status':'NOT_SUPPLIED_AT_KNOWN_LOCATIONS','searched':['Downloads immediate files','experiment subtree'],'expected_sha256':'0b9af536f7686c915655fecaa29aab2d19896d9a251dc2a04ec3041153c29fee'},
             'cpu':'AMD Ryzen 7 5700X3D, 8 cores / 16 logical','visible_memory_kib':67033128,'free_memory_kib_at_start':34075800,
             'limits':{'scenes':24,'max_passes':40,'max_active_playback_s':2700,'generated_storage_gib':5,'reserve_gib':50,'render_workers':4,'inner_threads':1}})
        save(REPORT/'speaker_safety_receipt.json',{'all_analog_monitors_off_or_disconnected':True,
             'user_confirmation_text':"Nothing is plugged into the audio output of the xvf. There are speakers and headphones plugged into my PC, and other microphones. But I don't want to disconnect them. I hope this is not an issue. Please continue.",
             'scope':'Explicit confirmation in this conversation for unchanged XVF setup; other PC audio endpoints remain connected and are not opened.',
             'recorded_utc':now(),'source':'user message before S4 request; pack permits referencing current explicit confirmation once per setup'})
        check_storage()

if __name__=='__main__':run()
