"""Saved-WAV Windows reference, explicit one-thread component; README_BASELINE_ARM64_ASR_V1.md."""
import argparse
import gc
import json
from pathlib import Path
import sys
import wave

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'n4'))
from common import bind,freeze,load,verify
from metric_process import identity,exact_process
from baseline_arm64_asr_review_v1 import CONFIG,CASES,require,review


def run(admission,output):
    require(not output.exists(),'Fresh reference output required');a=load(admission)
    import psutil
    own=identity(psutil.Process())
    require(psutil.Process().ppid()==a['owner']['pid'] and exact_process(a['owner']) is not None
        and psutil.Process().cpu_affinity()==[4],'Not admitted reference child')
    require(load(output.parent/'REFERENCE_OWNER.json')['owner']==own,'Reference identity mismatch')
    for b in a['code']+[a['audio']]+[r['asset'] for r in a['models']]:verify(b)
    import numpy as np
    import sherpa_onnx
    require(sherpa_onnx.__version__=='1.13.4','Sherpa reference version differs')
    with wave.open(a['audio']['path'],'rb') as wav:
        require((wav.getnchannels(),wav.getframerate(),wav.getsampwidth())==(1,16000,2),'Expected prepared mono16k PCM16')
        audio=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768
    require(len(audio)==a['frames'],'Reference frame count differs')
    models={r['component_id']:r['asset']['path'] for r in a['models']}
    recognizer=sherpa_onnx.OnlineRecognizer.from_transducer(encoder=models['encoder'],decoder=models['decoder'],
        joiner=models['joiner'],tokens=models['tokens'],num_threads=1,provider='cpu',sample_rate=16000,feature_dim=80,
        decoding_method='greedy_search',max_active_paths=4,blank_penalty=0.,enable_endpoint_detection=True,
        rule1_min_trailing_silence=2.4,rule2_min_trailing_silence=1.2,rule3_min_utterance_length=20.)
    output.mkdir();lines=output/'events.jsonl'
    with lines.open('x',encoding='utf-8',newline='\n') as f:
        def emit(row):f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
        def drain(stream):
            count=0
            while recognizer.is_ready(stream):
                recognizer.decode_stream(stream);count+=1;require(count<=100000,'Reference drain bound')
        emit(CONFIG)
        for name,source in zip(CASES,(audio[:0],audio[:1281],audio,audio)):
            stream=recognizer.create_stream();emit(dict(kind='case_start',case=name,frames=len(source)))
            sent=resets=0;finals=[]
            def final(phase):
                value=recognizer.get_result(stream)
                text=(value if isinstance(value,str) else value.text).strip()
                if text:finals.append(dict(text=text,sent_frames=sent,phase=phase))
            for offset in range(0,len(source),1600):
                chunk=source[offset:offset+1600];stream.accept_waveform(16000,chunk);sent+=len(chunk);drain(stream)
                if recognizer.is_endpoint(stream):final('endpoint');recognizer.reset(stream);resets+=1
            stream.accept_waveform(16000,np.zeros(10560,np.float32));stream.input_finished();drain(stream);final('finish')
            del stream;gc.collect()
            emit(dict(kind='case_closed',case=name,frames=len(source),sent_frames=sent,padding_frames=10560,
                endpoint_resets=resets,stream_closed=True,finals=finals))
        del recognizer;gc.collect();emit(dict(kind='complete',recognizer_closed=True,state_parity=True,CM5_tested=False,GUI_validated=False))
    result=review(lines,a['frames']);freeze(output/'RESULT.json',dict(status=result['status'],owner=own,
        events=bind(lines),review=result,sherpa_version=sherpa_onnx.__version__,module=bind(sherpa_onnx.__file__),CM5_tested=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--admission',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:run(a.admission,a.output)
    except Exception as exc:
        import traceback
        a.output.mkdir(exist_ok=True);freeze(a.output/'ERROR.json',dict(error=repr(exc),traceback=traceback.format_exc()));raise
