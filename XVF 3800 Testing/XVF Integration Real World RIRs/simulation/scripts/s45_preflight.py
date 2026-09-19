"""Read-only input binding and new S4.5 run initialization; README_S45.md."""
import subprocess, zipfile, xml.etree.ElementTree as ET
from s45_common import *

def run():
    REPORT.mkdir(parents=True,exist_ok=True);BANK.mkdir(parents=True,exist_ok=True);PAYLOAD.mkdir(parents=True,exist_ok=True)
    target=REPORT/'preflight.json'
    if target.exists():
        p=read(target);bind(p['workbook']['path'],p['workbook']['sha256']);print('Existing preflight preserved');return
    pack=[]
    for line in (PACK/'SHA256SUMS.txt').read_text().splitlines():
        sha,name=line.split(maxsplit=1);pack.append(bind(PACK/name,sha))
    workbook=Path('C:/Users/amiri/Downloads/XVF_Measurement_V9.docx')
    with zipfile.ZipFile(workbook) as z:
        doc=ET.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs=[''.join(p.itertext()) for p in doc.findall('.//w:p',ns)]
    (REPORT/'workbook_v9_text.txt').write_text('\n'.join(paragraphs),encoding='utf-8')
    prior_names=['S4_REPORT.md','NEXT_PHASE_INPUTS.md','ACCEPTED_FINAL_CAPTURES.json','SOURCE_AND_SPLIT_MANIFEST.json','SOURCE_LEVEL_POLICY.json','OUTPUT_LEVEL_POLICY.json','INITIALIZATION_POLICY.json','TIMING_TELEMETRY_POLICY.json','SPATIAL_SCORING_POLICY.json','S3_ISSUE_CLOSURE.json','package_receipt.json']
    policy_names=['SOURCE_LEVEL_POLICY.json','OUTPUT_LEVEL_POLICY.json','INITIALIZATION_POLICY.json','TIMING_TELEMETRY_POLICY.json','SPATIAL_SCORING_POLICY.json','ANGLE_LABEL_POLICY.json','CALIBRATION_DECISION.json']
    for name in policy_names:shutil.copy2(S4_REPORT/name,REPORT/name)
    git={}
    for args in [['git','status','--short'],['git','rev-parse','HEAD']]:git[' '.join(args)]=subprocess.run(args,cwd=REPO,capture_output=True,text=True,check=True).stdout
    p={'schema':'jp_s45_preflight_v1','run_id':RUN_ID,'started_utc':START_UTC.isoformat(),'start_basis':'Conservative minute before first clock reading, includes initial document inspection','deadline_utc':DEADLINE.isoformat(),'new_long_work_cutoff_utc':LAUNCH_CUTOFF.isoformat(),'pack':pack,'workbook':bind(workbook),'prior_S4':[bind(S4_REPORT/n) for n in prior_names],'rir_manifest':bind(SIM/'rir_library/v1/RIR_MANIFEST.json','468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546'),'git_before':git,'storage_before':storage(),'limits':LIMITS,'user_override':{'speech_corpora':['CMU_ARCTIC','HiFiTTS','Common_Voice'],'L2_ARCTIC':'EXCLUDED_BY_USER_REQUEST'},'payload_mapping':{'drive':'G:','model':'KINGSTON SNVS2000G','physical_drive':3,'method':'Win32_LogicalDiskToPartition then Win32_DiskDriveToDiskPartition; tool observed','status':'OK','volume_health':'Healthy'},'resources':{'cpu':'AMD Ryzen 7 5700X3D','cores':8,'logical_processors':16,'memory_kib':67033128,'free_memory_kib_observed':35541144}}
    save(target,p)
    save(REPORT/'speaker_safety_receipt.json',{'all_analog_monitors_off_or_disconnected':True,'user_confirmation_text':'Yes, XVF analog outputs are disconnected','recorded_utc':now(),'scope':'Fresh S4.5 user confirmation in current turn. Other PC audio devices may remain connected; explicit XVF endpoints only.'})
    save(REPORT/'status.json',{'stage':'PREFLIGHT_COMPLETE','status':'RUNNING','run_id':RUN_ID,'deadline_utc':DEADLINE.isoformat(),'user_corpora':p['user_override']})
    check_storage();print(json.dumps({'status':'PASS','workbook':p['workbook'],'storage':p['storage_before'],'deadline':p['deadline_utc']},indent=2))

if __name__=='__main__':run()
