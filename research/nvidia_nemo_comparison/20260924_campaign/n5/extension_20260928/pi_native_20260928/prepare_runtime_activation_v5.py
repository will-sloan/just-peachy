"""Render pinned activation assets; README_RUNTIME_OFFLINE_ACTIVATION_V1.md."""
import re
import shlex

HOME='/home/peachyprototype'
CAMPAIGN=HOME+'/JustPeachy/research/nemotron-20260928'
PYTHON=HOME+'/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python'
PROFILES=('baseline','baseline-titanet','d1-delayed','d1-delayed-titanet','d1-streaming-saved','d1-streaming-titanet-saved','d1-chunk52-saved','d1-chunk52-titanet-saved','d1-anonymous','baseline-anonymous')

def render(release_id,policy_sha256,rollback_sha256,profiles=PROFILES):
    """Return {relative_path: bytes}; caller reserves, backs up and installs exactly.

    The returned paths live in the separate release-profiles tree. systemd/
    contains a shared slice plus a rollback service copied to the user unit
    directory. bin/launch-profile is executable. desktop/ entries are copied to
    the user's desktop/applications directories; autostart is backed up first.
    Neither rendering nor the default profile implies native qualification.
    """
    if type(release_id) is not str or not re.fullmatch('field-runtime-v[1-9][0-9]*',release_id):raise ValueError('Versioned root')
    for pin in (policy_sha256,rollback_sha256):
        if type(pin) is not str or not re.fullmatch('[0-9a-f]{64}',pin) or pin=='0'*64:raise ValueError('Actual nonzero pinned policy/binding')
    if tuple(profiles)!=PROFILES:raise ValueError('Complete ten explicit microphone/saved profiles')
    root=CAMPAIGN+'/'+release_id;activation=root+'-activation';wrapper=root+'-profiles/bin/launch-profile'
    manager='jp-'+release_id;rollback='jp-rollback-'+release_id+'.service'
    slice_name='jpfield'+release_id.replace('-','')+'.slice'
    command=['systemd-run','--user','--quiet','--collect','--unit='+manager,'--slice='+slice_name,
        '--property=Description=JustPeachyOfflineRuntime','--property=OnFailure='+rollback,
        '--property=LimitAS=134217728','--property=LimitSTACK=1048576',
        '--property=LimitFSIZE=33554432','--property=TasksMax=64',
        '--property=RestrictAddressFamilies=AF_UNIX AF_NETLINK','--property=NoNewPrivileges=yes','--property=SystemCallArchitectures=native',
        '--property=RuntimeMaxSec=86400','--property=TimeoutStopSec=45',
        '--setenv=DISPLAY=:0','--setenv=XAUTHORITY='+HOME+'/.Xauthority',
        '--setenv=XDG_RUNTIME_DIR=/run/user/1000','--setenv=WAYLAND_DISPLAY=wayland-0',
        '--setenv=HF_HUB_OFFLINE=1','--setenv=TRANSFORMERS_OFFLINE=1',
        '--setenv=PYTHONDONTWRITEBYTECODE=1','--setenv=OMP_NUM_THREADS=1',
        '--setenv=OPENBLAS_NUM_THREADS=1','--setenv=MKL_NUM_THREADS=1',
        PYTHON,'-B',root+'/code/field_runtime_manager_v8.py','--root',root,
        '--policy-sha256',policy_sha256]
    shell=('#!/bin/sh\nset -eu\n[ "$#" -eq 2 ] && [ "$1" = --profile ] || exit 64\n'
        'case "$2" in '+'|'.join(PROFILES)+') ;; *) exit 64 ;; esac\n'
        'exec '+shlex.join(command)+' --profile "$2"\n')
    rollback_exec=shlex.join([PYTHON,'-B',activation+'/field_runtime_activation_v2.py',
        '--root',activation,'--binding-sha256',rollback_sha256])
    rollback_unit=('[Unit]\nDescription=Restore preserved Just Peachy idle baseline\n'
        'After=jp-install-'+release_id+'.service '+manager+'.service\n'
        '[Service]\nType=exec\nExecStart='+rollback_exec+'\n'
        'AllowedCPUs=2-3\nCPUQuota=200%\nTasksMax=64\nLimitAS=134217728\n'
        'LimitSTACK=1048576\nLimitFSIZE=33554432\nRuntimeMaxSec=60\nTimeoutStopSec=10\n'
        'Environment=PYTHONDONTWRITEBYTECODE=1\n')
    files={'bin/launch-profile':shell.encode(),
        'systemd/'+slice_name:('[Unit]\nDescription=Just Peachy shared runtime resources\n'
            '[Slice]\nCPUQuota=200%\nAllowedCPUs=2-3\nTasksMax=64\n').encode(),
        'systemd/'+rollback:rollback_unit.encode()}
    for profile in PROFILES:
        encoder='TitaNet' if 'titanet' in profile else 'ReDimNet'
        mode='Streaming' if 'streaming' in profile else 'Chunk52' if 'chunk52' in profile else 'Delayed'
        diarizer='Nemotron-3 '+mode if profile.startswith('d1-') else 'Baseline diarization'
        label='Sherpa + '+diarizer+' + '+encoder
        if profile.endswith('-anonymous'):label+=' - Anonymous'
        if profile.endswith('-saved'):label+=' - Saved WAV'
        files['desktop/'+profile+'.desktop']=('[Desktop Entry]\nType=Application\n'
            'Name=Just Peachy - '+label+'\nComment=Opens idle. New and Start begin a recording.\n'
            'Exec='+wrapper+' --profile '+profile+'\nIcon=audio-input-microphone\n'
            'Terminal=false\nCategories=AudioVideo;Audio;\nX-JustPeachy-CaptureOnLaunch=false\n').encode()
    files['autostart/just-peachy.desktop']=files['desktop/d1-delayed.desktop']
    files['desktop/rollback.desktop']=('[Desktop Entry]\nType=Application\n'
        'Name=Just Peachy - Restore original idle app\n'
        'Comment=Close the candidate first. Restores its backed-up startup setting.\n'
        'Exec=systemctl --user start '+rollback+'\nIcon=edit-undo\nTerminal=false\n').encode()
    if len(files)>16 or sum(map(len,files.values()))>65536:raise ValueError('Finite launch asset allocation')
    return files

def installer_properties(release_id):
    if type(release_id) is not str or not re.fullmatch('field-runtime-v[1-9][0-9]*',release_id):raise ValueError('Versioned root')
    return dict(Description='JustPeachyControlledRuntimeInstallation',
        OnFailure='jp-rollback-'+release_id+'.service',AllowedCPUs='2-3',CPUQuota='200%',
        TasksMax='64',LimitAS='134217728',LimitSTACK='1048576',LimitFSIZE='94371840',
        RuntimeMaxSec='180',TimeoutStopSec='10')
