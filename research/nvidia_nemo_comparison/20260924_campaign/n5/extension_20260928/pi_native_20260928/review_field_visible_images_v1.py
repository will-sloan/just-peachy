"""Bounded stdlib PNG pixel comparison; README_FIELD_VISIBLE_REVIEW_V5.md."""
import hashlib,json,struct,zlib
from pathlib import Path
import psutil


def decode(path):
    raw=path.read_bytes();assert len(raw)<4*1024**2 and raw[:8]==b'\x89PNG\r\n\x1a\n'
    pos=8;parts=[];shape=None
    while pos<len(raw):
        n,=struct.unpack('>I',raw[pos:pos+4]);kind=raw[pos+4:pos+8];data=raw[pos+8:pos+8+n]
        assert len(data)==n and zlib.crc32(kind+data)&0xffffffff==struct.unpack('>I',raw[pos+8+n:pos+12+n])[0]
        if kind==b'IHDR':
            w,h,depth,color,comp,filt,interlace=struct.unpack('>IIBBBBB',data)
            assert (w,h)==(480,800) and depth==8 and color in (2,6) and (comp,filt,interlace)==(0,0,0)
            shape=(w,h,3 if color==2 else 4)
        elif kind==b'IDAT':parts.append(data)
        pos+=n+12
        if kind==b'IEND':break
    assert pos==len(raw) and shape
    w,h,bpp=shape;stride=w*bpp
    d=zlib.decompressobj();scan=d.decompress(b''.join(parts),(stride+1)*h+1)
    assert len(scan)==(stride+1)*h and d.eof and not d.unconsumed_tail and not d.unused_data
    pixels=bytearray();previous=bytearray(stride)
    for y in range(h):
        start=y*(stride+1);method=scan[start];assert method in range(5)
        row=bytearray(scan[start+1:start+1+stride])
        for x in range(stride):
            left=row[x-bpp] if x>=bpp else 0;up=previous[x];corner=previous[x-bpp] if x>=bpp else 0
            if method==1:value=left
            elif method==2:value=up
            elif method==3:value=(left+up)//2
            elif method==4:
                p=left+up-corner;da,db,dc=abs(p-left),abs(p-up),abs(p-corner)
                value=left if da<=db and da<=dc else up if db<=dc else corner
            else:value=0
            row[x]=(row[x]+value)&255
        if bpp==3:pixels.extend(row)
        else:
            assert all(row[x]==255 for x in range(3,stride,4))
            for x in range(0,stride,4):pixels.extend(row[x:x+3])
        previous=row
    return raw,bytes(pixels)


def main():
    psutil.Process().cpu_affinity([14])
    from dispatch_geometry_v2 import PRIVATE
    folder=PRIVATE/'field-visible-v4-evidence';root=folder/'target';rows=[]
    for page in ['consent','recipes']:
        raw_a,a=decode(root/(page+'_settled_a.png'));raw_b,b=decode(root/(page+'_settled_b.png'))
        changed=[i//3 for i in range(0,len(a),3) if a[i:i+3]!=b[i:i+3]]
        bbox=[min(i%480 for i in changed),min(i//480 for i in changed),max(i%480 for i in changed)+1,max(i//480 for i in changed)+1] if changed else None
        rows.append(dict(page=page,dimensions=[480,800],png_equal=raw_a==raw_b,decoded_rgb_equal=a==b,
                         decoded_sha256=[hashlib.sha256(x).hexdigest() for x in (a,b)],different_pixels=len(changed),bbox=bbox))
    result=dict(status='DECODED_PIXEL_OBSERVATIONS_ONLY',scope='CRC-checked8bit noninterlaced RGB/opaqueRGBA PNG; no image edits, inference or hardware',pages=rows)
    with (folder/'DECODED_PIXELS_V1.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))


if __name__=='__main__':main()
