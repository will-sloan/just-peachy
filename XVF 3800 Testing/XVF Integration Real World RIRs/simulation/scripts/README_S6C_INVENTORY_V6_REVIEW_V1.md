# Independent inventory V6 review

Purpose: reproduce the held V6 source/metadata admission guards without collecting actual execution results. Inputs are the exact V6 helper, its V3 62-check receipt, original V4 and cross coordinator code, actual frozen epoch4/panel metadata, and the preserved synthetic missing-closure finding. Outputs are an immutable independent PASS receipt and a separately bound reproduction of the 62 owner fixtures. No actual cross manifest is prepared; no native logs, PCM, models, sessions or whole inventory are read/run.

The script independently reconstructs nine V4 functions using only the three admitted literal replacements and compares recursive Python code signatures; it verifies three exact selection/grid guards. It repeats the earlier-good/later-missing-closure counterexample for both missing OUTCOME and missing CLOSURE. Successful Popen remains physical evidence while uncertain creation/native/quiet closure remains unavailable.

PowerShell, using the existing EDGE environment:

    $s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
    $s6cPy = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
    & $s6cPy -B "$s6cSim\scripts\test_s6c_inventory_v6_review_v1.py" --output "$s6cSim\reports\S6C\20260910T123540Z\independent_review\INVENTORY_V6_DESIGN_REVIEW_V1.json"

Anaconda Prompt or Windows CMD; no environment installation/activation needed:

    cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B scripts\test_s6c_inventory_v6_review_v1.py --output reports\S6C\20260910T123540Z\independent_review\INVENTORY_V6_DESIGN_REVIEW_V1.json

Use a fresh output filename if the requested receipt or its _REPRODUCED_FIXTURES sibling already exists. Source pins intentionally reject a later revision; admit it separately. A source/metadata PASS does not authorize native execution or claim actual payload hashes were checked.

