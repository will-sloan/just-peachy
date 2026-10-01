"""Native early-owner bootstrap; README_FIELD_LOCAL_BOOTSTRAP_V1.md."""
import os,sys,resource,signal,json,struct,hashlib
from pathlib import Path

def main():
    os.sched_setaffinity(0,{3})
    resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
    resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    signal.alarm(80)
    sys.dont_write_bytecode=True
    pid=os.getpid()
    owner=dict(pid=pid,start_ticks=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19]),
               boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    raw=json.dumps(dict(early_owner=owner),separators=(',',':')).encode()
    if len(raw)>512:raise ValueError('Early owner bound')
    sys.stdout.buffer.write(struct.pack('!I',len(raw))+raw);sys.stdout.buffer.flush()
    # This actual owner is emitted before input reads or project code execution.
    def exact(size):
        parts=[];left=size
        while left:
            block=sys.stdin.buffer.read(min(left,16384))
            if not block:raise EOFError('Truncated bootstrap payload')
            parts.append(block);left-=len(block)
        return b''.join(parts)
    size=struct.unpack('!I',exact(4))[0]
    if not 0<size<=262144:raise ValueError('Original framed request limit')
    raw=exact(size)
    if len(sys.argv)!=2 or hashlib.sha256(raw).hexdigest()!=sys.argv[1]:
        raise ValueError('Command-bound whole payload digest')
    def pairs(rows):
        out={}
        for key,value in rows:
            if key in out:raise ValueError('Duplicate JSON key')
            out[key]=value
        return out
    value=json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda s:(_ for _ in ()).throw(ValueError(s)))
    if type(value) is not dict or set(value)!={'request','modules','loader'}:
        raise ValueError('Exact bootstrap envelope')
    source=value['loader']
    if type(source) is not str or not 0<len(source.encode())<=131072:
        raise ValueError('Loader source bound')
    # Whole payload hash above pins this loader before it can execute.
    namespace={'__name__':'manager_bootstrap_contract','__file__':'<manager-bootstrap-contract>'}
    exec(compile(source,namespace['__file__'],'exec'),namespace)
    modules=value['modules'];request=value['request']
    exporter,review=namespace['install'](modules,request['admission']['module_sha256'])
    exporter.run(request,modules)

if __name__=='__main__':main()

