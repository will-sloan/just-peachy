"""Prepare a fresh D1 anonymous-mode derivative; see README_D1_ANONYMOUS_V1.md."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def patch_engine(raw):
    text = raw.decode('utf-8')
    newline = '\r\n' if '\r\n' in text else '\n'
    text = text.replace('\r\n', '\n')
    edits = [
        ('class N2Engine(PrototypeEngine):\n', '''class N2Engine(PrototypeEngine):
    def _anonymous_native_only(self):
        # Research observers retain E0/E1 evidence for their frozen comparisons.
        return (getattr(self,'n2_diarization',None)=='D1'
                and getattr(self,'mode',None)=='anonymous_conversation'
                and getattr(self,'n2_observer_factory',None) is None)

    def _prepare_native_models(self,caption_only):
        native_only=self._anonymous_native_only()
        self._telemetry['n2_embedding_policy']=('BYPASSED_ANONYMOUS_NATIVE_SLOTS'
            if native_only else 'UNCHANGED_NAMING_OR_RESEARCH')
        # Keep the D1 lane active; only request the resident's ASR-only bundle.
        # The native diarizer is acquired separately by _speaker_loop.
        return super()._prepare_native_models(caption_only or native_only)

'''),
        ('            candidates=self._n2_timeline.exclusive_windows(self._n2_last_query)\n',
         '            candidates=[] if self._anonymous_native_only() else self._n2_timeline.exclusive_windows(self._n2_last_query)\n'),
        ("                    unavailable_reason='BELOW_EMBEDDING_MINIMUM' if short else None,\n",
         "                    unavailable_reason=('EMBEDDING_DISABLED_ANONYMOUS_MODE' if self._anonymous_native_only()\n"
         "                        else 'BELOW_EMBEDDING_MINIMUM' if short else None),\n")]
    for old, new in edits:
        if text.count(old) != 1:
            raise ValueError('Source differs from reviewed patch anchor')
        text = text.replace(old, new)
    compile(text, 'app/n2_pipeline.py', 'exec')
    return text.replace('\n', newline).encode('utf-8')


def prepare(output):
    accepted_path = HERE.parent/'n3/N3_ACCEPTED_CONFIGS.json'
    accepted = json.loads(accepted_path.read_text())
    parent_binding = accepted['source_receipt']
    parent_path = Path(parent_binding['path'])
    raw = parent_path.read_bytes()
    if len(raw) != parent_binding['bytes'] or sha(raw) != parent_binding['sha256']:
        raise ValueError('Accepted parent receipt changed')
    parent = json.loads(raw)
    source = Path(parent['prototype'])
    if output.exists():
        raise FileExistsError('Fresh derivative output required')
    # Verify before creating output; no model/audio/profile copying.
    payloads = {}
    for relative, binding in parent['files'].items():
        candidate = (source/relative).resolve()
        if not candidate.is_relative_to(source.resolve()):
            raise ValueError('Source escapes release')
        data = candidate.read_bytes()
        if len(data) != binding['bytes'] or sha(data) != binding['sha256']:
            raise ValueError('Parent source changed: '+relative)
        payloads[relative] = data
    original = payloads['app/n2_pipeline.py']
    modified = patch_engine(original)
    payloads['app/n2_pipeline.py'] = modified
    payloads['README_D1_ANONYMOUS_V1.md'] = (HERE/'README_D1_ANONYMOUS_V1.md').read_bytes()
    output.mkdir()
    bindings = {}
    for relative, data in payloads.items():
        destination = output/'prototype'/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(data)
        bindings[relative] = dict(bytes=len(data), sha256=sha(data))
    diff = ''.join(difflib.unified_diff(original.decode().splitlines(True),
                    modified.decode().splitlines(True), fromfile='parent/app/n2_pipeline.py',
                    tofile='derivative/app/n2_pipeline.py'))
    (output/'CHANGES.patch').write_text(diff, encoding='utf-8')
    receipt = dict(schema='d1-anonymous-derivative-v1', status='PREPARED_NOT_RELEASE_ACCEPTED',
                   parent_source_receipt=parent_binding, prototype=str(output/'prototype'),
                   files=bindings, builder_sha256=sha(Path(__file__).read_bytes()),
                   changed_code=['app/n2_pipeline.py'], numerical_retests=0,
                   scope='D1 anonymous mode only, without research observer. Named/D0/research paths unchanged. No GUI acceptance or memory/speed claim.')
    (output/'DERIVATIVE.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status=receipt['status'], files=len(bindings), output=str(output))))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    prepare(p.parse_args().output)
