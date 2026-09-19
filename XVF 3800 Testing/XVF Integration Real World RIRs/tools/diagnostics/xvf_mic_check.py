"""Finite XVF microphone qualification. No firmware changes or production logger.

Run without arguments for the operator-guided check. --unattended (or --phone)
performs three short probes while an independent speaker plays speech. Every run
is new. WDM-KS duplex uses silent USB playback to maintain the device clock.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, re, signal, subprocess, sys, threading, time, traceback

WORKSPACE = Path(__file__).resolve().parents[2]
TOOLS = WORKSPACE / 'tools/xvf321'
HOST = TOOLS / 'binary/host_v3.0.0/win32/xvf_host.exe'
sys.path.insert(0, str(TOOLS / 'python_deps'))
import numpy as np
import sounddevice as sd
import soundfile as sf

def now(): return datetime.now(timezone.utc).isoformat()
def write_json(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write('\n')

class Check:
    def __init__(self, mode, seconds, source_note):
        self.root = WORKSPACE / 'XVF_MEASUREMENT_WORK'
        self.id = 'MICCHECK_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
        self.paths = {name:self.root/name/self.id for name in ['device_inventory','logs','configs','raw_audio','telemetry']}
        for path in self.paths.values(): path.mkdir(parents=True, exist_ok=False)
        self.mode, self.seconds = mode, seconds
        self.source_note = source_note
        self.lock = threading.Lock()
        self.count = 0
        self.captures = []
        self.telemetry = []
        self.initial = {}
        self.restored = {}
        self.pending = threading.Event()
        self.thread = None

    def query(self, name, *values):
        with self.lock:
            self.count += 1
            tag = f'{self.count:04d}_{name}'
            argv = [str(HOST), name, *map(str,values)]
            start_utc, start_ns = now(), time.perf_counter_ns()
            exception = None
            try:
                p = subprocess.run(argv, cwd=HOST.parent, capture_output=True, timeout=10,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                out, err, code = p.stdout, p.stderr, p.returncode
            except subprocess.TimeoutExpired as e:
                out, err, code, exception = e.stdout or b'', e.stderr or b'', None, 'timeout'
            except OSError as e:
                out, err, code, exception = b'', b'', None, repr(e)
            end_ns, end_utc = time.perf_counter_ns(), now()
            for key, raw in [('stdout',out),('stderr',err)]:
                (self.paths['logs']/(tag+'.'+key+'.bin')).write_bytes(raw)
            row = dict(command=name,arguments=list(values),argv=argv,start_utc=start_utc,end_utc=end_utc,
                       start_monotonic_ns=start_ns,end_monotonic_ns=end_ns,duration_seconds=(end_ns-start_ns)/1e9,
                       stdout=out.decode('utf-8-sig',errors='replace'),stderr=err.decode('utf-8-sig',errors='replace'),
                       exit_code=code,exception=exception,raw_stdout=tag+'.stdout.bin',raw_stderr=tag+'.stderr.bin')
            with (self.paths['logs']/'commands.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(row)+'\n')
            if code != 0 or exception or row['stderr'].strip():
                raise RuntimeError(f'{name} failed: {row}')
            return row

    def read_values(self, name):
        row = self.query(name)
        lines = [s for s in row['stdout'].splitlines() if s.startswith(name+' ')]
        if len(lines)!=1: raise RuntimeError(f'Missing/ambiguous {name} response')
        values = lines[0].split()[1:]
        return [int(re.search(r'\[(\d+)\]',v).group(1)) if '[' in v else int(v) for v in values]

    def route(self, category, left, right_category, right):
        self.query('AUDIO_MGR_OP_L', category, left)
        self.query('AUDIO_MGR_OP_R', right_category, right)
        expected = [('AUDIO_MGR_OP_L',[category,left]),('AUDIO_MGR_OP_R',[right_category,right])]
        for name, values in expected:
            if self.read_values(name)!=values: raise RuntimeError('Route readback mismatch')

    def poll(self, label):
        while not self.pending.is_set():
            for cmd in ['AEC_AZIMUTH_VALUES','AEC_SPENERGY_VALUES','AUDIO_MGR_SELECTED_AZIMUTHS']:
                if self.pending.is_set(): break
                try:
                    row=self.query(cmd)
                    row['capture_label']=label
                    self.telemetry.append(row)
                except Exception as e:
                    self.telemetry.append(dict(capture_label=label,command=cmd,error=str(e),utc=now()))
            self.pending.wait(0.1)

    def capture(self, label, seconds, channels, intended_source=None):
        path = self.paths['raw_audio']/(label+'.wav')
        metadata = dict(label=label,channels=channels,intended_source=intended_source,
                        physical_identity_verified=False,source_level_calibrated=False,
                        duration_requested_seconds=seconds,sample_rate_hz=48000,pcm_bits=16,
                        mode='WDM-KS duplex; silent XVF USB playback',device=self.device,
                        playback_device=self.output_device,source_note=self.source_note,
                        start_utc=now(),start_monotonic_ns=time.perf_counter_ns())
        print(f'RECORDING {label}: {seconds:g} seconds', flush=True)
        self.pending.clear()
        self.thread=threading.Thread(target=self.poll,args=(label,),daemon=True)
        self.thread.start()
        try:
            silence=np.zeros((round(seconds*48000),2),dtype=np.int16)
            data=sd.playrec(silence,samplerate=48000,channels=2,dtype='int16',
                           device=(self.device['index'],self.output_device['index']),
                           blocking=True,dither_off=True)
            status=sd.get_status()
            sf.write(path,data,48000,subtype='PCM_16')
            peak=np.max(np.abs(data.astype(np.int32)),axis=0)
            rms=np.sqrt(np.mean((data.astype(np.float64)/32768)**2,axis=0))
            metadata.update(frames=len(data),channel_peak_counts=peak.tolist(),
                            channel_rms_dbfs=[None if v==0 else float(20*np.log10(v)) for v in rms],
                            all_zero_per_channel=[bool(v==0) for v in peak],
                            rail_samples=np.count_nonzero((data==-32768)|(data==32767),axis=0).tolist(),
                            callback_flags={key:bool(getattr(status,key)) for key in ['input_overflow','input_underflow','output_overflow','output_underflow','priming_output']},
                            wav_path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            print('  Peak PCM counts L/R:',peak.tolist(),flush=True)
        except BaseException as e:
            metadata['error']=repr(e)
            raise
        finally:
            sd.stop()
            metadata.update(end_utc=now(),end_monotonic_ns=time.perf_counter_ns(),audio_to_host_time_calibrated=False)
            self.pending.set()
            if self.thread:self.thread.join(timeout=35)
            metadata['telemetry_thread_finished']=self.thread is None or not self.thread.is_alive()
            write_json(self.paths['raw_audio']/(label+'.json'),metadata)
            self.captures.append(metadata)
        self.query('USB_D2H_BUFFER_STABLE')
        self.query('USB_H2D_BUFFER_STABLE')

    @staticmethod
    def prompt(message):
        print('\n'+message,flush=True)
        input('Press Enter when ready. ')
        for n in [3,2,1]:
            print(n,flush=True);time.sleep(1)

    def execute(self):
        print('Evidence session:', self.id, flush=True)
        print('This test briefly changes output routes and restores them. No flashing, reboot, gain or DSP changes.',flush=True)
        error=None
        changed=False
        try:
            write_json(self.paths['device_inventory']/'session.json',dict(id=self.id,created_utc=now(),mode=self.mode,operator_context=self.source_note,backend='Windows WDM-KS',playback='silent stereo PCM16 to XVF only; independent acoustic source unchanged',script_path=str(Path(__file__).resolve()),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
            for name in ['VERSION','BLD_MSG','AEC_NUM_MICS','AEC_MIC_ARRAY_TYPE','AEC_MIC_ARRAY_GEO','USB_BIT_DEPTH','AEC_AECCONVERGED','AEC_AECPATHCHANGE','AEC_RT60']:
                row=self.query(name)
                for line in row['stdout'].splitlines():
                    if line.startswith(name+' '):print(line.rstrip('\x00 '),flush=True)
            self.topology=self.read_values('AEC_MIC_ARRAY_TYPE')[0]
            if self.read_values('USB_BIT_DEPTH')!=[16,16]:raise RuntimeError('This diagnostic requires the existing 16/16 USB setting; it will not reset the board to change it.')
            if self.read_values('AEC_NUM_MICS')!=[4]:raise RuntimeError('Expected four configured microphones')
            self.device=dict(sd.query_devices(device='XVF38 WDM',kind='input'))
            self.output_device=dict(sd.query_devices(device='XVF38 WDM',kind='output'))
            for endpoint in [self.device,self.output_device]:
                if sd.query_hostapis(endpoint['hostapi'])['name']!='Windows WDM-KS':
                    raise RuntimeError('Expected the verified WDM-KS backend')
            sd.check_input_settings(device=self.device['index'],channels=2,dtype='int16',samplerate=48000)
            sd.check_output_settings(device=self.output_device['index'],channels=2,dtype='int16',samplerate=48000)
            for name in ['AUDIO_MGR_OP_ALL','AUDIO_MGR_OP_PACKED','AUDIO_MGR_OP_UPSAMPLE']:
                self.initial[name]=self.read_values(name)
            write_json(self.paths['configs']/'initial_output_configuration.json',self.initial)
            if self.mode=='guided':
                print('\nActive physical labels expected for stock board:', ['MIC0','MIC1','MIC2','MIC3'] if self.topology==1 else ['MIC1','MIC4','MIC5','MIC3'],flush=True)
                input('Pause acoustic playback. Do not touch or blow into microphone openings. Press Enter to proceed. ')
            changed=True
            self.query('AUDIO_MGR_OP_PACKED',0,0)
            self.query('AUDIO_MGR_OP_UPSAMPLE',1,1)
            if self.read_values('AUDIO_MGR_OP_PACKED')!=[0,0] or self.read_values('AUDIO_MGR_OP_UPSAMPLE')!=[1,1]:raise RuntimeError('Packing/upsample readback mismatch')
            physical={1:['MIC0','MIC1','MIC2','MIC3'],2:['MIC1','MIC4','MIC5','MIC3']}.get(self.topology)
            if physical is None:raise RuntimeError('Unsupported geometry: label mapping requires inspection')
            for pair in [(0,1),(2,3)]:
                self.route(1,pair[0],1,pair[1])
                channel_names=[f'raw_MIC{v}' for v in pair]
                if self.mode=='phone':
                    self.capture(f'RAW{pair[0]}{pair[1]}_SPEAKER',self.seconds,channel_names,self.source_note)
                else:
                    for mic in pair:
                        self.prompt(f'Find physical PCB label {physical[mic]} (expected logical MIC{mic}).\nAfter the countdown, gently rub fingers 1-2 cm BESIDE that opening for {self.seconds:g} seconds. Do not touch it.')
                        self.capture(f'PAIR{pair[0]}{pair[1]}_NEAR_{physical[mic]}',self.seconds,channel_names,f'Operator instructed near physical {physical[mic]}; expected logical MIC{mic}, not automatically verified')
            self.route(6,3,0,0)
            if self.mode=='guided':
                self.prompt('Resume speech on the independent speaker at a fixed position about 30-50 cm from the array. Leave it there through the recording.')
            self.capture('PROCESSED_AUTO_SPEAKER',self.seconds,['postprocessed_auto_select','intentional_silence'],self.source_note)
        except BaseException as e:
            error=repr(e);traceback.print_exc()
        finally:
            self.pending.set()
            if self.thread:self.thread.join(timeout=35)
            previous_signal=signal.signal(signal.SIGINT,signal.SIG_IGN)
            try:
                if changed:
                    for cmd in ['AUDIO_MGR_OP_PACKED','AUDIO_MGR_OP_ALL','AUDIO_MGR_OP_UPSAMPLE']:
                        try:
                            self.query(cmd,*self.initial[cmd])
                            self.restored[cmd]=self.read_values(cmd)==self.initial[cmd]
                        except Exception as e:self.restored[cmd]=str(e)
            finally:signal.signal(signal.SIGINT,previous_signal)
            with (self.paths['telemetry']/'raw_telemetry.jsonl').open('x',encoding='utf-8') as f:
                for row in self.telemetry:f.write(json.dumps(row)+'\n')
            raw_peaks={f'raw_MIC{i}':None for i in range(4)}
            for take in self.captures:
                for name,peak in zip(take.get('channels',[]),take.get('channel_peak_counts',[])):
                    if name in raw_peaks:raw_peaks[name]=max(raw_peaks[name] or 0,peak)
            if error or any(v is None for v in raw_peaks.values()):signal_status='INCOMPLETE'
            elif not any(raw_peaks.values()):signal_status='NO_MIC_SIGNAL'
            elif not all(raw_peaks.values()):signal_status='PARTIAL_MIC_SIGNAL'
            else:signal_status='SIGNAL_PRESENT_REVIEW_REQUIRED'
            result=dict(id=self.id,error=error,mode=self.mode,firmware_topology=getattr(self,'topology',None),captures=self.captures,
                        output_settings_restored=self.restored,physical_mapping_verified=False,
                        signal_status=signal_status,raw_channel_peak_counts=raw_peaks,
                        conclusion='Review raw signal and labelled clips. Nonzero samples alone do not certify mapping, speech quality, direction accuracy or sample continuity.')
            write_json(self.paths['device_inventory']/'result.json',result)
            write_json(self.paths['configs']/'restoration.json',self.restored)
            files=sorted(p for base in self.paths.values() for p in base.rglob('*') if p.is_file())
            with (self.paths['device_inventory']/'SHA256SUMS.txt').open('x',encoding='ascii',newline='\n') as f:
                for path in files:f.write(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.relative_to(self.root).as_posix()+'\n')
            print('\nSaved:',self.paths['device_inventory']/'result.json',flush=True)
            print('Restored:',self.restored,flush=True)
            print('Signal check:',signal_status,raw_peaks,flush=True)
        if error or any(v is not True for v in self.restored.values()):return 1
        return 0 if signal_status=='SIGNAL_PRESENT_REVIEW_REQUIRED' else 2

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phone','--unattended',dest='phone',action='store_true',help='Noninteractive three-take check while independent acoustic playback is already running')
    parser.add_argument('--source-note',default='Independent speech source; position and acoustic level unmeasured. Active firmware topology is read separately.',help='Operator description of acoustic source and relevant hardware state, saved with the evidence')
    parser.add_argument('--seconds',type=float,default=5,help='Duration per clip, 2-30 seconds; default 5')
    parser.add_argument('--plan',action='store_true',help='Print test sequence without device access or recording')
    args=parser.parse_args()
    if not 2<=args.seconds<=30:parser.error('--seconds must be between 2 and 30')
    if args.plan:
        print('Read firmware/geometry; snapshot output state; use verified WDM-KS duplex with silent USB playback; record raw 0/1 then 2/3; record Category 6 auto-select; restore and read back output state; hash new evidence. Guided mode waits for Enter at each physical-label prompt. Unattended mode captures three clips without prompts. Exit2 indicates missing microphone signal; exit0 means signal present but still requires physical mapping/QC.')
        return 0
    return Check('phone' if args.phone else 'guided',args.seconds,args.source_note).execute()

if __name__=='__main__':sys.exit(main())
