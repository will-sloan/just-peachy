# Nemotron anonymous mode without an external speaker encoder

Purpose: prepare a fresh derivative of the accepted N3 application that uses
native D1 slots directly in ordinary anonymous-conversation mode. It skips
ReDimNet/TitaNet model loading for a fresh resident and skips embedding calls.
The D1 speaker lane, all eight activity channels, overlap, caption association,
session reset and original raw ASR remain active. A previously used named-mode
resident may still retain its encoder weights; no automatic unloading is claimed.

The patch leaves D0, named modes, caption-only mode and explicit N2 research
observers on their existing paths. It is not a speaker-name recognizer. It does
not change the application's global asset/catalog requirements or remove model
files from packages. It is a candidate derivative requiring separate saved-file
Controller/GUI and resource qualification before deployment.

Inputs: the accepted N3 source receipt referenced by N3_ACCEPTED_CONFIGS.json,
all its hash-bound source files, this README, and a fresh output directory.
Outputs: a source-only prototype copy, exact CHANGES.patch and DERIVATIVE.json.
There is no model download/load, inference, microphone, GUI, Pi connection,
training or modification of the parent release. Requires existing Python 3.10+;
the CPU-pinned commands also use the installed psutil package.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$d1Py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$d1Script='research\nvidia_nemo_comparison\20260924_campaign\n5\prepare_d1_anonymous_v1.py'
& $d1Py -B -c "import psutil,runpy,sys; p=psutil.Process(); p.cpu_affinity([14]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" $d1Script --output 'G:\Just_Peachy_N1\20260924_campaign\local\releases\d1-anonymous-v1'
```

CMD or Anaconda Prompt:

```bat
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree"
set "D1_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%D1_PY%" -B -c "import psutil,runpy,sys; p=psutil.Process(); p.cpu_affinity([14]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" research\nvidia_nemo_comparison\20260924_campaign\n5\prepare_d1_anonymous_v1.py --output "G:\Just_Peachy_N1\20260924_campaign\local\releases\d1-anonymous-v1"
```

Use a new output suffix for another reproduction; existing outputs are refused.
To run model-free regression tests, set `JP_D1_ANONYMOUS_SOURCE` to the derivative
prototype directory. Then, using the same explicit Python, run:

```text
python -B -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n5 -p test_d1_anonymous_v1.py -v
```

PowerShell environment input: `$env:JP_D1_ANONYMOUS_SOURCE='G:\Just_Peachy_N1\20260924_campaign\local\releases\d1-anonymous-v1\prototype'`.
CMD/Anaconda environment input: `set "JP_D1_ANONYMOUS_SOURCE=G:\Just_Peachy_N1\20260924_campaign\local\releases\d1-anonymous-v1\prototype"`.
Replace `python` above with the absolute interpreter or `& $d1Py` in PowerShell.
Tests use synthetic activity and stub model acquisition, print results and do
not run neural models. Passing tests are not an actual saved-audio GUI pass.
