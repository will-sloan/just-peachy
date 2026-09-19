"""Local-only measurement server. One device owner and immutable take folders."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,unquote
from pathlib import Path
import argparse,json,threading,time,uuid,mimetypes,webbrowser,msvcrt,traceback,http.client,sys
from .core import *
from .acquisition import acquire,validate_request
from .trial import reserve_trial,acquire_trial
from .reference import reference_endpoint_problem
from .reference_calibration import acquire_calibration,validate_calibration_request
from .speaker_reference import acquire_speaker_reference,validate_speaker_reference
from .excitation import list_excitations
from .recovery import RecoveryMonitor
from .recordings import latest_recording,recycle_latest

APP=BASE/'measurement_app';PROFILES=APP/'profiles';PROFILES.mkdir(exist_ok=True)
APP_ID='just-peachy-xvf-measurement'
STATE={'app_id':APP_ID,'api_version':3,'busy':False,'state':'idle','message':'Ready to inspect the connected board','progress':0,'last_telemetry':{},'result':None,'device':None}
LOCK=threading.RLock();STOP=threading.Event();PORT=8767
RECOVERY=None
LEASE=open(APP/'hardware.lock','a+b');LEASE.seek(0,2)
if LEASE.tell()==0:LEASE.write(b'0');LEASE.flush()

def update(**kw):
    with LOCK:
        row=kw.pop('last_telemetry',None)
        if row is not None:STATE['last_telemetry'][row['command']]=clean_json(row)
        STATE.update(clean_json(kw))

def claim():
    with LOCK:
        if STATE['busy']:raise RuntimeError('A measurement or board check is already running')
        LEASE.seek(0)
        try:msvcrt.locking(LEASE.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RuntimeError('Another measurement application owns the XVF device')
        STATE['busy']=True

def release():
    with LOCK:
        LEASE.seek(0);msvcrt.locking(LEASE.fileno(),msvcrt.LK_UNLCK,1);STATE['busy']=False

def recovery_update(value):
    with LOCK:
        STATE['recovery']=value
        if value.get('identity'):
            d=value['identity']
            STATE['device']={'version':'.'.join(map(str,d['VERSION'])),'build':'ua-io48-lin',
                'usb_bit_depth':d['USB_BIT_DEPTH'],'native_sample_rate_hz':48000,
                'microphone_sample_rate_hz':16000,'payload_bits':23,
                'mic_gain':d['AUDIO_MGR_MIC_GAIN'][0],'system_delay_samples':d['AUDIO_MGR_SYS_DELAY'][0],
                'observed_utc':value['checked_utc'],'precision_note':'23 payload bits'}
        elif not value['ready']:
            STATE['device']=None

def inspect():
    claim()
    try:
        p=RUNS/('INSPECT_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));p.mkdir(parents=True)
        c=Control(p/'commands');d=c.identify();write_json(p/'identity.json',d);freeze(p)
        bits=d['USB_BIT_DEPTH'][0]
        summary={'version':'.'.join(map(str,d['VERSION'])),'build':'ua-io48-lin','usb_bit_depth':d['USB_BIT_DEPTH'],
          'native_sample_rate_hz':48000,'microphone_sample_rate_hz':16000,'payload_bits':bits-1,
          'mic_gain':d['AUDIO_MGR_MIC_GAIN'][0],'system_delay_samples':d['AUDIO_MGR_SYS_DELAY'][0],
          'observed_utc':now(),'precision_note':'23payloadbits' if bits==24 else '16-bit USB; 15 payload bits. Re-prepare24-bit after a cold restart.'}
        update(device=summary,message='Board readback complete',state='idle')
    finally:release()

def worker(req,folder):
    runid=folder.name
    try:
        if req.get('mode')=='reference_calibration':result=acquire_calibration(req,folder,STOP,update)
        elif req.get('mode')=='speaker_reference':result=acquire_speaker_reference(req,folder,STOP,update)
        else:result=acquire_trial(req,folder,STOP,update,capture=acquire)
        result['url']='/runs/'+runid+'/REPORT.txt';result['json_url']='/runs/'+runid+'/result.json'
        update(state='complete',progress=1,result=result,message=result['message'])
        if result.get('hardware_logger_still_active'):
            update(state='fault',message='A control or playback writer did not stop. Device lease retained; do not start another recording.');return
        if RECOVERY and any(not p.get('capture_integrity_pass', False) for p in result.get('passes', [])):
            RECOVERY.request_check()
    except BaseException as e:
        # folder was reserved by this worker before dispatch. Never adopt an
        # existing folder or modify a frozen trial to record another failure.
        if not (folder/'SHA256SUMS.txt').exists():
            try:
                with (folder/'server_failure.txt').open('x',encoding='utf-8') as handle:handle.write(traceback.format_exc())
            except OSError:pass
        update(state='error',message=str(e),result={'run_id':runid,'status':'INVESTIGATE','error':repr(e),'url':'/runs/'+runid+'/server_failure.txt'})
        if RECOVERY:RECOVERY.request_check()
    release()


def list_completed_runs(limit=100):
    """Read terminal run summaries; manifest presence is not a new hash audit."""
    base=RUNS.resolve();rows=[];read_errors=[]
    for folder in sorted((p for p in base.iterdir() if p.name.startswith(('TAKE_','JPXVF_','REFERENCE_CAL_','SPEAKER_REF_'))),key=lambda p:p.stat().st_mtime,reverse=True):
        if len(rows)>=limit:break
        if not folder.is_dir() or not folder.resolve().is_relative_to(base):continue
        paths=[folder/name for name in ['request.json','result.json','SHA256SUMS.txt']]
        if not all(p.is_file() and p.resolve().is_relative_to(folder.resolve()) for p in paths):continue
        try:
            if any(p.stat().st_size>2097152 for p in paths[:2]):raise ValueError('Run metadata exceeds listing size limit')
            request=json.loads(paths[0].read_text(encoding='utf-8'));result=json.loads(paths[1].read_text(encoding='utf-8'))
            setup=request.get('setup',{});setup=setup if isinstance(setup,dict) else {}
            pose=setup.get('device',{});pose=pose if isinstance(pose,dict) else {}
            stamp=re.match(r'TAKE_(\d{8}T\d{6})_(\d{6})Z',folder.name)
            date=result.get('recorded_utc') or (datetime.strptime(stamp[1]+stamp[2],'%Y%m%dT%H%M%S%f').replace(tzinfo=timezone.utc).isoformat() if stamp else None)
            rows.append({'id':folder.name,'trial_label':setup.get('trial_label'),'domain':request.get('domain'),
                'status':result.get('status','UNKNOWN'),'recorded_utc':date,'room_id':setup.get('room_id'),
                'placement_id':setup.get('placement_id'),'repeat_number':setup.get('repeat_number'),
                'room_name':setup.get('room_name'),'position_name':setup.get('position_name'),
                'distance_m':setup.get('source',{}).get('distance_to_array_m'),'angle_deg':setup.get('source',{}).get('azimuth_lab_deg'),
                'obstruction':setup.get('obstruction',{}).get('present'),'passes':result.get('passes',[]),
                'array_pose':{key:pose.get(key) for key in ['orientation','yaw_deg','pitch_deg','roll_deg','height_above_floor_m']},
                'manifest_present':True,'manifest_verified_by_listing':False,
                'report_url':'/runs/'+folder.name+'/REPORT.txt','json_url':'/runs/'+folder.name+'/result.json'})
        except (OSError,ValueError,TypeError,AttributeError) as error:read_errors.append({'id':folder.name,'error':str(error)})
    return {'runs':rows,'limit':limit,'read_errors':read_errors}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):pass
    def reply(self,obj,code=200):
        b=json.dumps(clean_json(obj),allow_nan=False).encode('utf-8');self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def allowed(self):
        return self.headers.get('Host') in [f'127.0.0.1:{PORT}',f'localhost:{PORT}']
    def do_GET(self):
        try:
            if not self.allowed():return self.reply({'error':'Invalid local Host'},403)
            path=urlsplit(self.path).path
            if path=='/api/status':
                with LOCK:return self.reply(STATE)
            if path=='/api/devices':
                # Hardware inspection occurs only on explicit refresh while idle.
                if RECOVERY is None and not STATE['busy']:
                    try:inspect()
                    except Exception as e:update(message='Device inspection: '+str(e))
                inventory=list(RECOVERY.inventory) if RECOVERY else devices();visible=[]
                for device in inventory:
                    approved=playback_endpoint_problem(device,inventory) is None
                    if device.get('max_output_channels',0)>0 and not approved:continue
                    visible.append({**device,'approved_for_playback':approved,'approved_for_reference':reference_endpoint_problem(device,inventory) is None})
                return self.reply({'devices':visible,**({'recovery':STATE.get('recovery')} if RECOVERY else {})})
            if path=='/api/excitations':return self.reply({'excitations':list_excitations()})
            if path=='/api/profiles':return self.reply({'profiles':[json.loads(p.read_text()) for p in sorted(PROFILES.glob('*.json'))]})
            if path=='/api/runs':return self.reply(list_completed_runs())
            if path=='/api/latest-recording':return self.reply({'recording':latest_recording(RUNS)})
            if path=='/guide':
                base=BASE.resolve();p=base/'MEASUREMENT_GUI_GUIDE.md'
            elif path=='/reference-guide':
                base=BASE.resolve();p=base/'planning/REFERENCE_MICROPHONE_CALIBRATION_PLAN.md'
            elif path.startswith('/runs/'):
                base=RUNS.resolve();p=(base/unquote(path[6:])).resolve()
            else:
                base=(APP/'static').resolve();p=(base/('index.html' if path=='/' else unquote(path.lstrip('/')))).resolve()
            if not p.is_relative_to(base) or not p.is_file():return self.reply({'error':'File not found'},404)
            mime=mimetypes.guess_type(str(p))[0] or 'application/octet-stream'
            self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8' if mime.startswith('text/') else mime)
            self.send_header('Content-Length',str(p.stat().st_size));self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            with p.open('rb') as f:
                for b in iter(lambda:f.read(65536),b''):self.wfile.write(b)
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as e:self.reply({'error':str(e)},500)
    def do_POST(self):
        try:
            if not self.allowed():return self.reply({'error':'Invalid local Host'},403)
            origin=self.headers.get('Origin')
            if origin and origin not in [f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}']:return self.reply({'error':'Local origin required'},403)
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply({'error':'JSON required'},415)
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<=262144:return self.reply({'error':'Invalid request length'},400)
            body=json.loads(self.rfile.read(length),parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Non-finite JSON number')))
            if not isinstance(body,dict):raise ValueError('JSON request must be an object')
            json.dumps(body,allow_nan=False)  # Also rejects overflowed numeric exponents recursively.
            path=urlsplit(self.path).path
            if path=='/api/delete-last-recording':
                claim()
                try:
                    deleted=recycle_latest(RUNS,body.get('run_id'),body.get('token'))
                    if (STATE.get('result') or {}).get('run_id')==deleted['id']:
                        update(result=None,progress=0,state='idle',message=deleted['message'])
                        with LOCK:STATE['last_telemetry']={}
                    return self.reply(deleted)
                finally:release()
            if path=='/api/profiles':
                if not isinstance(body.get('data'),dict):raise ValueError('Profile data must be an object')
                name=str(body.get('name','')).strip()[:120]
                if not name:raise ValueError('Name the setup')
                pid=uuid.uuid4().hex;row={'id':pid,'name':name,'data':body['data'],'saved_utc':now()}
                write_json(PROFILES/(pid+'.json'),row);return self.reply(row,201)
            if path in ['/api/reference-calibration','/api/speaker-reference']:
                if RECOVERY and not RECOVERY.ready:raise RuntimeError('Automatic USB recovery is pending. Wait for XVF ready before recording.')
                req=validate_calibration_request(body) if path=='/api/reference-calibration' else validate_speaker_reference(body)
                prefix='REFERENCE_CAL_' if path=='/api/reference-calibration' else 'SPEAKER_REF_'
                claim();STOP.clear()
                folder=RUNS/(prefix+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'_'+uuid.uuid4().hex[:6])
                try:
                    folder.mkdir(parents=True,exist_ok=False)
                    update(state='preflight',message='Preparing '+('reference microphone calibration' if prefix=='REFERENCE_CAL_' else 'one-time speaker reference'),result=None,progress=0)
                    threading.Thread(target=worker,args=(req,folder),daemon=True).start()
                except BaseException:
                    release();raise
                return self.reply({'accepted':True,'run_id':folder.name},202)
            if path=='/api/run':
                if RECOVERY and not RECOVERY.ready:raise RuntimeError('Automatic USB recovery is pending. Wait for XVF ready before recording.')
                if body.get('schema_version')!=3:raise ValueError('Reload the updated recorder: request schema_version 3 is required')
                if isinstance(body.get('reference'),dict) and body['reference'].get('enabled'):
                    raise ValueError('Use the separate one-time speaker-reference action; routine XVF recordings do not use the reference microphone')
                req=validate_request(body,require_metadata=True);claim();STOP.clear()
                try:folder=reserve_trial(req,RUNS)
                except BaseException:
                    release();raise
                runid=folder.name
                update(state='preflight',message='Checking device and reserving a new take',result=None,progress=0,last_telemetry=None)
                with LOCK:STATE['last_telemetry']={}
                try:threading.Thread(target=worker,args=(req,folder),daemon=True).start()
                except BaseException:
                    release();raise
                return self.reply({'accepted':True,'run_id':runid},202)
            if path=='/api/stop':STOP.set();return self.reply({'stop_requested':True})
            return self.reply({'error':'Unknown operation'},404)
        except (ValueError,TypeError,KeyError) as e:self.reply({'error':str(e)},400)
        except RuntimeError as e:self.reply({'error':str(e)},409)
        except Exception as e:self.reply({'error':str(e)},500)

def identify_existing_instance(port,timeout=1.0):
    """Identify this loopback app without board inspection or device control.

    Older running builds have no app_id. Accept them only when both the full
    known status shape/device signature and the exact HTML title agree.
    No redirects, proxy environment, /api/devices calls or process operations.
    """
    url=f'http://127.0.0.1:{port}'
    def read(path,limit):
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=timeout)
        try:
            connection.request('GET',path,headers={'Accept':'application/json' if path=='/api/status' else 'text/html'})
            response=connection.getresponse();payload=response.read(limit+1)
            if response.status!=200 or len(payload)>limit:return None
            return payload.decode('utf-8')
        finally:connection.close()
    try:
        payload=read('/api/status',262144)
        if payload is None:return None
        status=json.loads(payload)
        expected={'busy','state','message','progress','last_telemetry','result','device'}
        if not isinstance(status,dict) or not expected.issubset(status):return None
        if not isinstance(status['busy'],bool) or not isinstance(status['state'],str) or not isinstance(status['last_telemetry'],dict):return None
        if status.get('app_id')==APP_ID and status.get('api_version')==3:
            return {'url':url,'identification':'app_id'}
        if status.get('app_id')==APP_ID:return {'url':url,'identification':'incompatible_version'}
        if status.get('app_id') is not None:return None
        device=status['device']
        if not isinstance(device,dict):return None
        if (device.get('version')!='3.2.1' or device.get('build')!='ua-io48-lin'
            or device.get('native_sample_rate_hz')!=48000 or device.get('microphone_sample_rate_hz')!=16000
            or device.get('usb_bit_depth') not in [[16,16],[24,24]]):return None
        if device.get('payload_bits')!=device['usb_bit_depth'][0]-1:return None
        page=read('/',131072)
        if page is None or '<title>Just Peachy · XVF Measurement</title>' not in page:return None
        return {'url':url,'identification':'legacy_status_and_title'}
    except (OSError,http.client.HTTPException,UnicodeError,ValueError,TypeError):return None

def reuse_existing_instance(port,open_browser):
    existing=identify_existing_instance(port)
    if existing is None:return False
    if existing['identification']!='app_id':
        raise RuntimeError('An older recorder is running at '+existing['url']+'. Close its recorder terminal with Ctrl+C while idle, then launch again; the reference-microphone GUI requires backend version 3.')
    print(f"XVF measurement is already running: {existing['url']}",flush=True)
    if existing['identification']=='legacy_status_and_title':
        print('Existing build verified by XVF status and page title; its loaded backend stays in use.',flush=True)
    if open_browser:webbrowser.open(existing['url'])
    return True

def main():
    global PORT,RECOVERY
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8767);parser.add_argument('--open-browser',action='store_true');a=parser.parse_args();PORT=a.port
    if not 1<=PORT<=65535:parser.error('port must be between 1 and 65535')
    if reuse_existing_instance(PORT,a.open_browser):return 0
    try:server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    except OSError as error:
        # Another invocation may have bound the port after the first probe.
        if reuse_existing_instance(PORT,a.open_browser):return 0
        print(f'Cannot listen at http://127.0.0.1:{PORT}: {error}. No matching XVF application was identified. Choose another port with --port.',file=sys.stderr,flush=True)
        return 1
    print(f'XVF measurement ready: http://127.0.0.1:{PORT}',flush=True)
    RECOVERY=RecoveryMonitor(RUNS,claim,release,recovery_update,refresh_audio_backend)
    RECOVERY.start()
    if a.open_browser:threading.Timer(.5,lambda:webbrowser.open(f'http://127.0.0.1:{PORT}')).start()
    try:server.serve_forever()
    except KeyboardInterrupt:
        RECOVERY.close()
        STOP.set()
        until=time.monotonic()+30
        while STATE['busy'] and time.monotonic()<until:time.sleep(.1)
    finally:
        RECOVERY.close()
        server.server_close()
    return 0

if __name__=='__main__':raise SystemExit(main())
