"""Model-free build-reuse boundaries; README_BASELINE_ASR_DIAGNOSTIC_V3.md."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from run_baseline_asr_diagnostic_v3 import binding, verified_build


class BuildReuse(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        def put(name,data):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return binding(p)
        self.put=put
        sources=[put('source/'+n,b'// fixture\n') for n in ('diagnostic.cpp','CMakeLists.txt','baseline_arm64_asr_v1.cpp')]
        compiler=put('cl.exe',b'fixture compiler')
        config=put('build/CMakeFiles/compiler.cmake',('set(CMAKE_CXX_COMPILER "'+compiler['path'].replace('\\','/')+'")\n').encode())
        pe=bytearray(80);pe[:2]=b'MZ';pe[60:64]=(64).to_bytes(4,'little');pe[64:70]=b'PE\0\0\x64\x86'
        binary=put('build/Release/baseline_asr_diagnostic_v2.exe',pe)
        log=put('log.txt',b'fixture\n');base=dict(returncode=0,cancelled=None,stdout=log,stderr=log)
        c=dict(base,argv=['cmake','-S',str(self.root/'source'),'-B',str(self.root/'build')])
        b=dict(base,argv=['cmake','--build',str(self.root/'build'),'--config','Release','--parallel','1'])
        self.proof=dict(source=sources,binary=binary,compiler_configuration=config,actual_compiler=compiler,
            configure_command=put('configure.json',json.dumps(c).encode()),compile_command=put('compile.json',json.dumps(b).encode()))

    def test_verified_retained_build(self):
        self.assertEqual(verified_build(self.proof),Path(self.proof['binary']['path']))

    def test_compiler_or_source_mismatch(self):
        for key in ('actual_compiler','source'):
            p=deepcopy(self.proof)
            if key=='actual_compiler':p[key]=self.put('other-cl.exe',b'other')
            else:p[key]=p[key][:2]
            with self.assertRaises(ValueError):verified_build(p)

    def test_failed_build_or_changed_log(self):
        record=json.loads(Path(self.proof['compile_command']['path']).read_text());record['returncode']=1
        p=deepcopy(self.proof);p['compile_command']=self.put('failed.json',json.dumps(record).encode())
        with self.assertRaises(ValueError):verified_build(p)
        Path(record['stdout']['path']).write_text('changed')
        with self.assertRaises(ValueError):verified_build(self.proof)

    def test_wrong_pe_and_wrong_build_path(self):
        p=deepcopy(self.proof);p['binary']=self.put('wrong.exe',b'not a PE')
        with self.assertRaises(ValueError):verified_build(p)
        record=json.loads(Path(self.proof['compile_command']['path']).read_text());record['argv'][2]=str(self.root/'foreign')
        p=deepcopy(self.proof);p['compile_command']=self.put('foreign.json',json.dumps(record).encode())
        with self.assertRaises(ValueError):verified_build(p)


if __name__=='__main__':unittest.main()
