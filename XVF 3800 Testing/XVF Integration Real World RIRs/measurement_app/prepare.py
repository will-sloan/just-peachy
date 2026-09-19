"""Prepare documented USB24 mode while no acquisition owns the device."""
import msvcrt,time
from .core import *

def main():
    lease=open(BASE/'measurement_app/hardware.lock','a+b');lease.seek(0,2)
    if not lease.tell():lease.write(b'0');lease.flush()
    lease.seek(0)
    try:msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:raise RuntimeError('Stop the active recording and wait for restoration before preparing USB24')
    folder=RUNS/('PREPARE24_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));folder.mkdir(parents=True)
    c=Control(folder/'commands');before=c.identify();write_json(folder/'before.json',before)
    (folder/'before_params.txt').write_text(c.query('--dump-params'),encoding='utf-8')
    changed=before['USB_BIT_DEPTH']!=[24,24]
    if changed:
        print('Setting documented USB24 mode. Firmware restarts and other runtime DSP parameters reset. Snapshot retained.',flush=True)
        c.query('USB_BIT_DEPTH',24,24);time.sleep(4)
        for n in ['AUDIO_MGR_MIC_GAIN','AUDIO_MGR_REF_GAIN','AUDIO_MGR_SYS_DELAY']:c.set(n,before[n])
    after=c.identify();write_json(folder/'after.json',after)
    if after['USB_BIT_DEPTH']!=[24,24]:raise RuntimeError('USB24 readback failed')
    write_json(folder/'result.json',{'status':'PASS','usb_bit_depth':[24,24],'rebooted':changed,'flash_written':False,
      'gain_delay_restored':True,'other_runtime_settings_reset_to_defaults':changed,
      'next':'Start/restart the recorder to refresh Windows audio endpoints. Verify your configuration after any reset.'})
    freeze(folder);lease.close()
    print('Ready: USB24/24, 23 packed audio payload bits, 16kHz per microphone. '+str(folder),flush=True)

if __name__=='__main__':main()
