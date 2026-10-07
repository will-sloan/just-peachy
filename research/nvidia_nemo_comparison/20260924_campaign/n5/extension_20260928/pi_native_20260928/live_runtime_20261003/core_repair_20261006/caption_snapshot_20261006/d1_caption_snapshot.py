"""Pinned D1 identity snapshots; see README_D1_CAPTION_SNAPSHOT.md."""
import ast
from copy import deepcopy
import hashlib
import inspect
from pathlib import Path
import stat
import textwrap


N2_SOURCE_SHA256 = '6312c12f80b67183faf93b6ca83502b47f0e7bca62d124a170a58a6a51000491'
ROW_FIELDS = ('utterance_id', 'text_revision_id', 'source_start_sec', 'source_end_sec')
SPAN_FIELDS = ('id', 'source_start_sec', 'source_end_sec')
METHOD = '_revise_supported_spans'


def selected_identity_rows(presentation, utterance_id=None):
    """Copy canonical identity inputs under the existing presentation lock.

    S7 project() leaves these fields unchanged. Display labels, nested segment
    copies, token-owner histories and text are not inputs to the pinned method.
    Preserve row order and exact supplied source coordinates, without alignment.
    """
    with presentation._lock:
        if utterance_id is None:
            rows = presentation.rows.values()
        else:
            row = presentation.rows.get(utterance_id)
            rows = () if row is None else (row,)
        result = []
        for row in rows:
            item = {field: deepcopy(row[field]) for field in ROW_FIELDS if field in row}
            item['word_spans'] = [
                {field: deepcopy(span[field]) for field in SPAN_FIELDS if field in span}
                for span in row.get('word_spans', [])]
            result.append(item)
        return result


def _node(source):
    return ast.parse(source).body[0]


def _same(left, right):
    return ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)


def _method_node(raw, filename):
    module = ast.parse(raw.decode('utf-8'), filename=filename)
    owners = [item for item in module.body if isinstance(item, ast.ClassDef) and item.name == 'N2Engine']
    if len(owners) != 1:
        raise ValueError('Exactly one pinned N2Engine required')
    methods = [item for item in owners[0].body if isinstance(item, ast.FunctionDef) and item.name == METHOD]
    if len(methods) != 1 or methods[0].decorator_list:
        raise ValueError('Exactly one undecorated pinned revision method required')
    return methods[0]


def _derive(method):
    """Change two snapshot calls and the paired obsolete-revision cleanup only."""
    original = deepcopy(method)
    result = deepcopy(method)
    first_expected = _node("for row in self._s6d_presentation.snapshot_rows():\n    pass")
    cleanup_expected = _node("retained={s['id'] for r in self._s6d_presentation.snapshot_rows() for s in r.get('word_spans',[])}")
    filter_expected = _node("self._n2_span_signatures={k:v for k,v in self._n2_span_signatures.items() if k[0] in retained}")
    first_replacement = _node("for row in selected_identity_rows(self._s6d_presentation,utterance_id):\n    pass")
    cleanup_replacement = _node("retained={(s['id'],r['text_revision_id']) for r in selected_identity_rows(self._s6d_presentation) for s in r.get('word_spans',[])}")
    filter_replacement = _node("self._n2_span_signatures={k:v for k,v in self._n2_span_signatures.items() if k in retained}")
    changes = []
    for item in ast.walk(result):
        if isinstance(item, ast.For) and _same(item.target, first_expected.target) and _same(item.iter, first_expected.iter):
            changes.append((item, 'iter', deepcopy(item.iter)))
            item.iter = deepcopy(first_replacement.iter)
        elif isinstance(item, ast.Assign) and _same(item, cleanup_expected):
            changes.append((item, 'value', deepcopy(item.value)))
            item.value = deepcopy(cleanup_replacement.value)
        elif isinstance(item, ast.Assign) and _same(item, filter_expected):
            changes.append((item, 'value', deepcopy(item.value)))
            item.value = deepcopy(filter_replacement.value)
    if len(changes) != 3:
        raise ValueError('Pinned snapshot/cleanup AST regions differ')
    calls = [item for item in ast.walk(result) if isinstance(item, ast.Call) and
             isinstance(item.func, ast.Name) and item.func.id == 'selected_identity_rows']
    if len(calls) != 2:
        raise ValueError('Exactly two identity snapshot substitutions required')
    # Restore the three permitted regions in a separate tree and prove that
    # every other AST node, including gates, labels and event payloads, is equal.
    restored = deepcopy(result)
    reverse = []
    for item in ast.walk(restored):
        if isinstance(item, ast.For) and _same(item.target, first_replacement.target) and _same(item.iter, first_replacement.iter):
            reverse.append('selected_snapshot')
            item.iter = deepcopy(first_expected.iter)
        elif isinstance(item, ast.Assign) and _same(item, cleanup_replacement):
            reverse.append('cleanup_snapshot_and_pairs')
            item.value = deepcopy(cleanup_expected.value)
        elif isinstance(item, ast.Assign) and _same(item, filter_replacement):
            reverse.append('cleanup_membership')
            item.value = deepcopy(filter_expected.value)
    if len(reverse) != 3 or not _same(restored, original):
        raise ValueError('Unapproved revision AST change')
    return ast.fix_missing_locations(result)


def bind_revision(Parent, expected_source_path, expected_sha256):
    """Return callable(engine,key=None,blocking=True), bound once at construction.

    The caller supplies the already admitted native class and exact source path.
    No native module/model import, disk database or worker is created here.
    """
    if expected_sha256 != N2_SOURCE_SHA256:
        raise ValueError('This derivation admits only its exact original N2 pin')
    path = Path(expected_source_path)
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1024**2:
        raise ValueError('Bounded regular single-link pinned N2 source required')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Pinned N2 source hash differs')
    method = getattr(Parent, METHOD)
    if method.__qualname__ != 'N2Engine.'+METHOD:
        raise ValueError('Admitted N2Engine revision method required')
    if Path(inspect.getsourcefile(method)).resolve() != path.resolve():
        raise ValueError('Native method origin differs from pinned source')
    original = _method_node(raw, str(path))
    # inspect reads the admitted method's declared region in the same hash-bound
    # file. An unexpected origin/region fails before any wrapper is installed.
    inspected = ast.parse(textwrap.dedent(inspect.getsource(method))).body[0]
    if not _same(inspected, original):
        raise ValueError('Loaded native method AST differs from admitted region')
    derived = _derive(original)
    namespace = dict(method.__globals__)
    namespace['selected_identity_rows'] = selected_identity_rows
    exec(compile(ast.Module(body=[derived], type_ignores=[]), str(path), 'exec'), namespace)
    result = namespace[METHOD]
    result.__qualname__ = method.__qualname__
    result.__module__ = method.__module__
    result.caption_snapshot_provenance = dict(
        source_sha256=expected_sha256, class_name='N2Engine', method=METHOD,
        first_line=original.lineno, last_line=original.end_lineno,
        snapshot_calls_replaced=2, cleanup_pairs_replaced=True,
        other_ast_unchanged=True, word_timing_unchanged=True)
    return result
