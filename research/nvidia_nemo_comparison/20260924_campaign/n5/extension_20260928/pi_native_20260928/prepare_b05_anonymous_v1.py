"""Reapply the preserved anonymous-mode patch to the latest native source. See README_B05_ANONYMOUS_V1.md."""
import argparse
import ast
import hashlib
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    assert hashlib.sha256(args.parent.read_bytes()).hexdigest()=='6b6e797c418ed44babd9ced367ab8e05db940714e0918a925b4de5d5352625e7'
    assert hashlib.sha256(args.reference.read_bytes()).hexdigest()=='67426652a4dd66649fed87c28e21b843451ca73fe71629a283337bdd955a20c0'
    source=args.parent.read_text(encoding='utf-8');reference=args.reference.read_text(encoding='utf-8')
    insert=reference[reference.index('    def _anonymous_native_only'):reference.index('    def _admit_research_gallery')]
    anchor='class N2Engine(PrototypeEngine):\n'
    assert source.count(anchor)==1
    source=source.replace(anchor,anchor+insert)
    for before,after in [
        ('candidates=self._n2_timeline.exclusive_windows(self._n2_last_query)',
         'candidates=[] if self._anonymous_native_only() else self._n2_timeline.exclusive_windows(self._n2_last_query)'),
        ("unavailable_reason='BELOW_EMBEDDING_MINIMUM' if short else None,",
         "unavailable_reason=('EMBEDDING_DISABLED_ANONYMOUS_MODE' if self._anonymous_native_only()\n                        else 'BELOW_EMBEDDING_MINIMUM' if short else None),")]:
        assert source.count(before)==1
        source=source.replace(before,after)
    ast.parse(source)
    data=source.encode('utf-8')
    assert hashlib.sha256(data).hexdigest()=='6312c12f80b67183faf93b6ca83502b47f0e7bca62d124a170a58a6a51000491'
    args.out.mkdir()
    with (args.out/'n2_pipeline.py').open('xb') as stream:stream.write(data)
    print('Prepared anonymous-mode derivative; not executed or accepted.')
if __name__=='__main__':main()
