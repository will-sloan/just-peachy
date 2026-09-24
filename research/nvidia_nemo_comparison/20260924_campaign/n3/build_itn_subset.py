"""Compile and exhaustively verify a finite NeMo-derived English ITN subset."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

REVISION='ddadfb2a38d2bc6b8cc6232c4f915eb60f500688'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if subprocess.check_output(['git','-C',str(args.source),'rev-parse','HEAD'],text=True).strip()!=REVISION:
        raise ValueError('NeMo text grammar revision changed')
    if subprocess.check_output(['git','-C',str(args.source),'status','--porcelain'],text=True).strip():
        raise ValueError('NeMo grammar source is modified')
    import pynini
    from pynini.lib import pynutil
    data=args.source/'nemo_text_processing/inverse_text_normalization/en/data'
    files=[data/'numbers'/name for name in ('zero.tsv','digit.tsv','teen.tsv','ties.tsv')]
    def rows(path):return [line.split('\t') for line in path.read_text().splitlines() if line.strip()]
    zero,digit,teen,ties=[dict(rows(path)) for path in files]
    # Finite restriction of NVIDIA CardinalFst's graph_two_digit (Apache-2.0).
    # Original Copyright 2021 NVIDIA; Copyright 2015 onwards Google.
    graph_digit=pynini.string_file(str(files[1]))
    graph_teen=pynini.string_file(str(files[2]))
    graph_ties=pynini.string_file(str(files[3]))
    delete_space=pynutil.delete(pynini.closure(pynini.accep(' ')))
    graph_two_digit=graph_teen | (graph_ties+delete_space+(graph_digit|pynutil.insert('0')))
    graph=pynini.string_file(str(files[0])) | graph_digit | graph_two_digit
    numbers={**zero,**digit,**teen}
    for word,tens in ties.items():
        numbers[word]=tens+'0'
        for unit,n in digit.items():numbers[word+' '+unit]=tens+n
    for phrase,expected in numbers.items():
        output=pynini.compose(phrase,graph).project('output').rmepsilon()
        actual=set(output.paths().ostrings())
        if actual!={expected}:raise AssertionError((phrase,actual,expected))
    allowed={'centimeter','millimeter','kilometer','meter','milligram','kilogram','percent','hertz','kilowatt'}
    unit_rows=rows(data/'measurements.tsv')
    units={spoken:written for written,spoken in unit_rows if spoken in allowed}
    if set(units)!=allowed:raise ValueError('Requested measurement subset no longer matches reviewed TSV')
    for spoken,written in list(units.items()):
        if spoken not in {'percent','hertz'}:units[spoken+'s']=written
    finite=pynini.string_map(list(numbers.items())).optimize()
    args.output.mkdir(parents=True,exist_ok=True)
    finite.write(str(args.output/'cardinal_0_99.fst'))
    bound=files+[data/'measurements.tsv',args.source/'nemo_text_processing/inverse_text_normalization/en/taggers/cardinal.py',args.source/'LICENSE']
    result=dict(schema='just-peachy.n3.itn-subset.v1',status='COMPILED_EXHAUSTIVE_NUMERIC_PARITY_PASSED',
        source_repository='NVIDIA/NeMo-text-processing',source_revision=REVISION,
        source_files={p.relative_to(args.source).as_posix():sha(p) for p in bound},
        license='Apache-2.0',changes='Finite 0..99 numeric projection; selected measurement spellings and regular plurals; portable JSON lookup; no full grammar or clinical suitability claim',
        number_forms_checked=len(numbers),numbers=numbers,units=units,
        standalone_minimum=13,unsupported=['hundreds and larger','fractions','decimals','dates','times','currency','automatic name correction'],
        compiled_fst_sha256=sha(args.output/'cardinal_0_99.fst'),
        build_runtime=dict(pynini=pynini.__version__,platform='WSL x86_64; build only'),
        compiled_utc=datetime.now(timezone.utc).isoformat())
    (args.output/'itn_subset.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Verified',len(numbers),'numeric forms;',len(units),'measurement forms')


if __name__=='__main__':main()
