"""Install offline desktop/autostart launchers as the Pi user; see README_STARTUP.md."""
import argparse
import json
from pathlib import Path
import shlex


def install(home, root, data):
    home, root, data = map(lambda p: Path(p).resolve(), (home, root, data))
    anchor = Path(__file__).resolve().with_name('launch_current.py')
    launcher = home/'JustPeachy/start-prototype.sh'
    log = home/'JustPeachy/startup.log'
    launcher.parent.mkdir(parents=True, exist_ok=True)
    command = shlex.join(['/usr/bin/python3.11', str(anchor), '--root', str(root),
                         '--data-root', str(data), '--', '--fullscreen'])
    launcher.write_text('#!/bin/sh\n# Local models only; no network wait or download.\n'
                        'export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1\n'
                        'exec '+command+' >> '+shlex.quote(str(log))+' 2>&1\n', encoding='utf-8')
    launcher.chmod(0o755)
    desktop = ('[Desktop Entry]\nType=Application\nName=Just Peachy\n'
               'Comment=Offline portrait captions\nExec='+json.dumps(str(launcher))+'\n'
               'Icon=audio-input-microphone\nTerminal=false\nX-GNOME-Autostart-enabled=true\n')
    for target in (home/'.config/autostart/just-peachy.desktop', home/'Desktop/Just Peachy.desktop'):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(desktop, encoding='utf-8'); target.chmod(0o755)
    return {'launcher':str(launcher), 'log':str(log), 'network_required':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--data-root', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(install(Path.home(), args.root, args.data_root)))
