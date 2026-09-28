"""Make separate user launchers for the reviewed GUI repair. README_PREVIEW_V2.md."""
from pathlib import Path
import ast
import hashlib
import json

HERE=Path(__file__).resolve().parent


def main():
    parent=HERE.parent/'prepi_20260928/start_preview_v1.py'
    text=parent.read_text(encoding='utf-8')
    text=text.replace('README_PREVIEW.md','README_PREVIEW_V2.md')
    text=text.replace("RUNS={'A0':'a0-e0-runtime-v1','A2':'a2-e0-runtime-v1'}","RUNS={'A0':'a0-controls-v3','A2':'a2-controls-v3'}")
    text=text.replace("if review['status']!='PASS_PREPI_E0_RUNTIME_WINDOWS_SHADOW_ONLY':raise ValueError('E0 runtime lifecycle not reviewed')",
        "if review['status']!='PASS_WINDOWS_CONTROLS_STARTUP_RECOVERY_ONLY':raise ValueError('Repaired-source controls not reviewed')")
    text=text.replace("(review['admission'],review['terminal'],review['source_receipt'])","(review['admission'],review['terminal'])")
    text=text.replace("    if load(a['source_receipt']['path'])['schema']!='prepi-e0-runtime-derivative-v1':raise ValueError('Wrong source derivative')",
        "    verify(a['source_receipt']);derivative=load(a['source_receipt']['path'])\n"
        "    if derivative['schema']!='extended-ui-error-priority-v1' or derivative['changed_code']!=['app/ui.py']:raise ValueError('Wrong source derivative')\n"
        "    verify(derivative['parent_source_receipt'])\n"
        "    prior=load(base/(('a0' if args.backend=='A0' else 'a2')+'-e0-runtime-v1-REVIEW.json'))\n"
        "    if prior['status']!='PASS_PREPI_E0_RUNTIME_WINDOWS_SHADOW_ONLY' or prior['source_receipt']!=derivative['parent_source_receipt']:raise ValueError('Full-file parent lifecycle missing')\n"
        "    for b in (prior['admission'],prior['terminal'],prior['source_receipt']):verify(b)\n"
        "    for phase in prior['phases']:verify(phase['result']);verify(phase['lifetime'])")
    text=text.replace("for phase in review['phases']:","for phase in [review['phase']]:")
    text=text.replace("'-preview')/'data'","'-ui-error-v1-preview')/'data'")
    text=text.replace('files and scoped lifecycle evidence verified','files, parent lifecycle and repaired-source controls verified')
    ast.parse(text);outputs={'start_preview_v2.py':text}
    for name,backend in [('Start-SHERPA-NEMOTRON-REDIMNET.cmd','A0'),('Start-NEMOTRON-NEMOTRON-REDIMNET.cmd','A2')]:
        outputs[name]='@echo off\nrem User-operated saved-file preview; README_PREVIEW_V2.md.\n"C:\\Users\\amiri\\Documents\\GitHub\\just-peachy\\.edge-speech-env\\python.exe" -B "%~dp0start_preview_v2.py" --backend '+backend+' %*\nexit /b %ERRORLEVEL%\n'
    for name,value in outputs.items():
        with (HERE/name).open('x',encoding='utf-8',newline='\n') as f:f.write(value)
    receipt=dict(parent=dict(path=str(parent),sha256=hashlib.sha256(parent.read_bytes()).hexdigest()),
        outputs={name:dict(sha256=hashlib.sha256((HERE/name).read_bytes()).hexdigest(),bytes=(HERE/name).stat().st_size) for name in outputs})
    with (HERE/'PREVIEW_DERIVATION_V2.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2)
    print(dict(status='PREPARED_REQUIRES_REVIEWS_AND_CHECK_ONLY',outputs=list(outputs)))


if __name__=='__main__':main()
