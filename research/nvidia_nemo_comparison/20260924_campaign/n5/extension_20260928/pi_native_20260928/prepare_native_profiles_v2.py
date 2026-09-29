"""Prepare explicit delayed preset binding. See README_GEOMETRY_V2.md."""
import hashlib,json
from pathlib import Path
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
def main():
    parent=LOCAL/'native-profiles-v1/nemotron_diarization.py'
    assert hashlib.sha256(parent.read_bytes()).hexdigest()=='bf4bbe5746e9797ac72b04b6031ff41ee1c87331d67910d7ba1a9fc8f94c6845'
    original=parent.read_text(encoding='utf-8')
    old="self.gpu, b'v3-streaming',"
    new="self.gpu, (b'v3-offline' if self.profile.name == 'native_v3_delayed' else b'v3-streaming'),"
    assert original.count(old)==1
    output=LOCAL/'native-profiles-v2';output.mkdir()
    child=output/'nemotron_diarization.py'
    child.write_text(original.replace(old,new),encoding='utf-8',newline='\n')
    compile(child.read_text(encoding='utf-8'),str(child),'exec')
    receipt=dict(status='SOURCE_PREPARED_NOT_EXECUTED',parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),sha256=hashlib.sha256(child.read_bytes()).hexdigest(),change='Choose v3-offline preset for native_v3_delayed because pinned C ABI ignores fifo_frames=0 override; preserves zero FIFO from preset. Other profiles unchanged.',c_api_sha256='d031ee096eefc0d5ed597bd8897fe05d0fe538fbe4f2119d2533a606400862fe',geometry_header_sha256='c14f4e0ee44d27951a2be5d7798d8606ab01a96fda91872776e0ff204b76da85')
    (output/'DERIVATIVE.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps(receipt))
if __name__=='__main__':main()
