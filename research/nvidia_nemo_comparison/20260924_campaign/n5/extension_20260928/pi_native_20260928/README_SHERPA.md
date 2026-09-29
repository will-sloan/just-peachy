# Saved-file Sherpa passage on native CM5

Purpose: verify the existing ASR model can accept every sample of a saved 44.6954375-second file at original 1x pacing, emit text, reset endpoints and drain. This is not ASR/WER accuracy scoring, an integrated GUI/speaker test, a new complete baseline acceptance or independent real-life audio validation. No reference transcript is loaded. The existing autostart app remains active; resource observations are conditional, not an isolated benchmark.

Inputs: unchanged installed hash-addressed encoder/decoder/joiner/tokens; unchanged source.wav in the first D1 stage; fresh script, README and ADMISSION.json in `~/JustPeachy/research/nemotron-20260928/sherpa-paced-v1`. The code verifies all model/source SHA256 values, sample count/rate/shape, target boot ID, input hashes, expiry and storage/RAM floors. Decoding/endpoint settings match the existing wrapper with one thread under the initial native admission. Punctuation and speakers are deliberately outside this component check.

Outputs: private OWNER.json and RESULT.json with caption events (text, source availability clock, endpoint), sample coverage, decode wall time/RTF, process CPU/RSS, largest processing lag and EOF drain. EOF explicitly uses the existing wrapper's 0.66 seconds of zero padding, kept outside the original-source denominator. No output text is published to Git. A closed independent review must verify actual nonempty output, all source samples, finite timing, owner termination and unchanged install before crediting functional passage.

## PowerShell / Anaconda PowerShell

Transfer these two files plus a fresh admission to the fresh stage using the key/host arguments in README.md. Run only with the following bounds:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-sherpa-paced-v1 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=180 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/sherpa-paced-v1/sherpa_paced_v1.py'
```

## CMD / Anaconda Prompt

Use the same ssh/scp commands, replacing single quotes around the remote command with double quotes. No Windows activation/install is required. The script imposes a 768 MiB hard virtual-address limit, CPUs 2/3, one model thread, GPU off, 850 MiB pre-run available RAM and 5 GiB disk floor. It never opens a microphone, changes the current app, downloads assets or enrolls a person. Do not remove limits to make a failure pass; preserve the result and use a fresh admitted derivative for a bounded repair.
