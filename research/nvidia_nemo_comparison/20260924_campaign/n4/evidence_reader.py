"""Read exact Controller evidence from files or verified ZIPs; README_EVIDENCE.md."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
from common import bind
from evidence_archive import verify_archive


class ControllerEvidence:
    def __init__(self, result, archive_binding=None):
        self.root = Path(result['attempt']).resolve()
        self.bindings = {str(Path(row['path']).resolve()): row for row in result['evidence']}
        if len(self.bindings) != len(result['evidence']):
            raise ValueError('Duplicate Controller evidence bindings')
        self.archive = None
        self.members = {}
        if archive_binding is not None:
            path = Path(archive_binding['path'])
            if bind(path) != archive_binding:
                raise ValueError('Archive binding changed')
            manifest = verify_archive(path)
            if manifest.get('schema') != 'n4-lossless-cell-evidence-v1':
                raise ValueError('Unsupported evidence archive')
            source = manifest['execution_result']
            if Path(source['path']).resolve() != self.root/'RESULT.json':
                raise ValueError('Archive belongs to a different execution root')
            self.members = {row['relative_path']:row for row in manifest['files']}
            member = self.members.get('RESULT.json')
            if not member or (member['sha256'], member['bytes']) != (source['sha256'], source['bytes']):
                raise ValueError('Archive lacks the bound execution result')
            archive = zipfile.ZipFile(path)
            try:
                if json.loads(archive.read(member['object'])) != result:
                    raise ValueError('Archive belongs to different result contents')
            except BaseException:
                archive.close()
                raise
            self.archive = archive

    def read_bytes(self, path):
        path = Path(path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Evidence path escapes execution root')
        expected = self.bindings.get(str(path))
        if expected is None:
            raise ValueError('Evidence is not bound to this execution')
        if self.archive is None:
            data = path.read_bytes()
        else:
            member = self.members.get(path.relative_to(self.root).as_posix())
            if not member or (member['sha256'], member['bytes']) != (expected['sha256'], expected['bytes']):
                raise ValueError('Archived member differs from execution binding')
            data = self.archive.read(member['object'])
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError('Required execution evidence changed')
        return data

    def json(self, path):
        return json.loads(self.read_bytes(path))

    def lines(self, path):
        with io.TextIOWrapper(io.BytesIO(self.read_bytes(path)), encoding='utf-8') as stream:
            yield from stream

    def close(self):
        if self.archive is not None:
            self.archive.close()
            self.archive = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
