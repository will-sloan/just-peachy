"""Read-only post-soak hardware snapshot. See README_POST_SOAK_BASELINE.md."""
from pathlib import Path
import subprocess
import time


def inspect(payload,baseline):
    if payload!={'expected_boot_id':baseline['boot_id']}:
        raise ValueError('Exact current expected boot required')
    result=dict(observed_epoch=time.time(),boot_id=baseline['boot_id'],
                scope='after_soak_only_not_continuous_thermal_trace')
    path=Path('/usr/bin/vcgencmd')
    if path.is_file():
        try:
            proc=subprocess.run([str(path),'get_throttled'],capture_output=True,timeout=3)
            if len(proc.stdout)+len(proc.stderr)>4096:raise ValueError('Hardware response bound')
            result['firmware_throttle_flags']=dict(returncode=proc.returncode,
                stdout=proc.stdout.decode(errors='replace'),stderr=proc.stderr.decode(errors='replace'))
        except subprocess.TimeoutExpired:
            result['firmware_throttle_flags']=dict(status='unavailable_timeout')
    else:result['firmware_throttle_flags']=dict(status='command_unavailable')
    for name,path in [('temperature_millidegrees','/sys/class/thermal/thermal_zone0/temp'),
                      ('cpu2_frequency_khz','/sys/devices/system/cpu/cpu2/cpufreq/scaling_cur_freq'),
                      ('cpu3_frequency_khz','/sys/devices/system/cpu/cpu3/cpufreq/scaling_cur_freq')]:
        p=Path(path)
        result[name]=p.read_text().strip() if p.is_file() and p.stat().st_size<=4096 else None
    return result


if 'PAYLOAD' in globals():RESULT=inspect(PAYLOAD,BASELINE)
