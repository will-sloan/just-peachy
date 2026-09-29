"""Environment-only wrapper; see README_B01_LIVE_TRIAL_V2.md."""
import os,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
config=root/'alsa_hw_only_v1.conf'
assert os.environ.get('ALSA_CONFIG_PATH')==str(config)
digest=hashlib.sha256(config.read_bytes()).hexdigest()
assert digest=='d81bc353dcab14d172e78b26c6116bfc8462b96e45e44b1a93ac3f217898564d'
with (root/'ALSA_ENVIRONMENT.json').open('x') as f:json.dump({'path':str(config),'sha256':digest,'process_local':True},f)
from b01_live_trial_v1 import main
if __name__=='__main__':raise SystemExit(main())
