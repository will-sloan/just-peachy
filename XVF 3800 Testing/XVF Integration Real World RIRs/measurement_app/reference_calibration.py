"""Optional acoustic-calibrator recording; never drives a speaker or the XVF."""
from pathlib import Path
import json
import math
import shutil
import time
import traceback
import soundfile as sf
from .core import BASE,now,write_json,freeze,sha
from .reference import ReferenceCapture,validate_reference,estimate_sensitivity


def validate_calibration_request(body):
    if body.get('schema_version')!=3:raise ValueError('Reload the current recorder before calibrating')
    if body.get('operator_confirmed') is not True:raise ValueError('Fit the calibrator and confirm its stated level and frequency first')
    for key,low,high in [('known_spl_db',40,140),('frequency_hz',20,20000)]:
        value=body.get(key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError('Enter a valid '+key.replace('_',' '))
    ref=validate_reference(body.get('reference',{}))
    if not ref['enabled']:raise ValueError('Enable and select the external reference microphone')
    return {**body,'reference':ref,'mode':'reference_calibration','domain':'reference','duration_seconds':10,
            'setup':{},'recorded_utc':now()}


def acquire_calibration(request,folder,stop,update,capture_factory=ReferenceCapture):
    """folder is exclusively reserved by the server; all outputs are new."""
    folder=Path(folder)
    if (folder/'SHA256SUMS.txt').exists():raise FileExistsError('Calibration already frozen')
    write_json(folder/'request.json',request)
    (folder/'source').mkdir()
    for name in ['reference.py','reference_calibration.py','core.py','playback.py']:
        shutil.copy2(BASE/'measurement_app'/name,folder/'source'/name)
    recorder=None;receipt={'status':'FAIL','stream_closed':True};calibration=None;error=None
    try:
        update(state='recording',progress=0,message='Recording the fitted acoustic calibrator for 10 seconds; speaker output is silent')
        recorder=capture_factory(folder/'reference',{**request['reference'],'duration_seconds':15},stop)
        recorder.start()
        if not recorder.wait_ready(timeout=3):raise RuntimeError('Reference microphone produced no input frames')
        began=time.monotonic()
        while time.monotonic()-began<10:
            if stop.wait(.1):break
            update(progress=min((time.monotonic()-began)/10,.99))
    except BaseException as exc:
        error=repr(exc);(folder/'error_trace.txt').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        if recorder:
            try:receipt=recorder.finish()
            except BaseException as exc:receipt={'status':'FAIL','stream_closed':False,'error':repr(exc)};error=error or repr(exc)
    try:
        if not stop.is_set() and error is None and receipt.get('status')=='PASS' and receipt.get('stream_closed'):
            path=folder/'reference/selected_reference.wav';samples,rate=sf.read(path,dtype='float64')
            if len(samples)<8*rate:raise RuntimeError('Calibration recording did not contain the full analysis window')
            calibration=estimate_sensitivity(samples[2*rate:8*rate],rate,request['known_spl_db'],request['frequency_hz'])
            calibration.update(source_wav_sha256=sha(path),analysis_start_s=2,analysis_end_s=8,
                input_configuration=request['reference'],known_spl_db=request['known_spl_db'],frequency_hz=request['frequency_hz'],
                recorded_utc=request['recorded_utc'],operator_confirmed=True,
                source='operator-fitted acoustic calibrator with entered level; calibration certificate not independently verified',
                frequency_response_correction_applied=False,valid_only_at_same_microphone_interface_and_input_gain=True)
            write_json(folder/'calibration.json',calibration)
    except BaseException as exc:error=repr(exc)
    passed=bool(calibration and not error and not stop.is_set() and receipt.get('stream_closed'))
    status='PASS' if passed else 'RETAKE' if stop.is_set() else 'INVESTIGATE'
    message='Calibrator recording passed. A pressure scale is available for this exact microphone/input gain; frequency response is not corrected.' if passed else 'Reference calibration not accepted. '+str(error or receipt.get('error') or 'Check the recording and calibrator fit; retain this attempt.')
    result={'kind':'reference_calibration','run_id':folder.name,'status':status,'message':message,
        'capture_integrity_pass':receipt.get('status')=='PASS' and receipt.get('stream_closed',False),
        'scientific_measurement_qualified':False,'reference':receipt,'calibration':calibration,'error':error,
        'calibration_record':str((folder/'calibration.json').resolve()) if passed else None,
        'hardware_logger_still_active':not receipt.get('stream_closed',False),'stopped':stop.is_set(),
        'recorded_utc':request['recorded_utc']}
    write_json(folder/'result.json',result)
    (folder/'REPORT.txt').write_text('Reference calibration '+folder.name+'\n\n'+status+'\n'+message+
        '\n\nNo speaker or XVF control was used. Original reference WAVs and input/timing receipts are in reference/.\n'+
        (json.dumps(calibration,indent=2) if calibration else '')+'\n',encoding='utf-8')
    if receipt.get('stream_closed'):result['seal']=freeze(folder)
    return result
