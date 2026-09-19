"""Local XVF acquisition application; analysis and calibration remain explicit."""
from pathlib import Path
import sys
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'tools/xvf321/python_deps'))
