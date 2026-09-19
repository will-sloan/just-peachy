"""Portable release/data/model paths and exclusive update boundary."""
import hashlib
import json
import os
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]


def default_data_root():
    # Outside AppData: packaged Windows hosts can transparently redirect AppData
    # writes into a package-only cache invisible to an Explorer-launched Python.
    return Path(os.environ.get('JUST_PEACHY_DATA', Path.home()/'JustPeachy/data')).expanduser().resolve()


def default_models_root():
    return Path(os.environ.get('JUST_PEACHY_MODELS', default_data_root().parent/'shared/models')).expanduser().resolve()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with tmp.open('x', encoding='utf-8', newline='\n') as f:
            json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def sha256(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


class ApplicationLock:
    def __init__(self, root):
        self.root = Path(root).resolve()
        if self.root == ROOT or ROOT in self.root.parents:
            raise ValueError('Private data must be outside the application/release directory')
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root/'runtime.lock'
        self.token = uuid.uuid4().hex
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump({'pid':os.getpid(), 'token':self.token, 'purpose':'application'}, f)
            schema = self.root/'DATA_SCHEMA.json'
            if schema.exists() and read_json(schema).get('schema_version') != 1:
                raise ValueError('Unsupported personal data schema; no migration was attempted')
            if not schema.exists():
                atomic_json(schema, {'schema_version':1})
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.path.exists() and read_json(self.path).get('token') == self.token:
            self.path.unlink()


def pipeline_config(data, models):
    from edge_speech_pipeline.config import AssetSpec, PipelineConfig
    rows = read_json(ROOT/'config/assets.json')
    assets = tuple(AssetSpec(r['component_id'], Path(models)/r['sha256']/r['filename'],
                            r['sha256'], r['deployment_relative_path']) for r in rows)
    return PipelineConfig(assets=assets, session_root=Path(data)/'sessions', profile_root=Path(data)/'people')
