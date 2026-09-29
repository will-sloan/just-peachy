"""Prepare one intermediate experimental native recipe. See README_CM5_CHUNK52_V1.md."""
from pathlib import Path
import hashlib,json
P=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
def main():
    parent=P/'native-profiles-v2/nemotron_diarization.py'
    assert hashlib.sha256(parent.read_bytes()).hexdigest()=='2537162df8ac8ccdd89c45c3f26fa12ef48519867a0474bf4be39e4667d75e37'
    source=parent.read_text(encoding='utf-8')
    needle="    StreamingProfile('native_v3_streaming', chunk_frames=13, right_context_frames=1,"
    assert source.count(needle)==1
    addition="    StreamingProfile('native_cm5_chunk52', chunk_frames=52, right_context_frames=1,\n                     left_context_frames=0, fifo_frames=80, spkcache_frames=264,\n                     update_period_frames=40),\n"
    dest=P/'native-profiles-v3';dest.mkdir()
    file=dest/'nemotron_diarization.py'
    file.write_text(source.replace(needle,addition+needle),encoding='utf-8',newline='\n')
    compile(file.read_text(encoding='utf-8'),str(file),'exec')
    receipt=dict(status='SOURCE_PREPARED_NOT_EXECUTED',parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),recipe=[52,1,0,80,264,40],grid_seconds=.08,official_named_preset=False,change='Experimental center chunk52 versus native streaming13; all other whole-recipe values explicit and unchanged. Subject to native validation and full checks.',quality_qualified=False)
    (dest/'DERIVATIVE.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps(receipt))
if __name__=='__main__':main()
