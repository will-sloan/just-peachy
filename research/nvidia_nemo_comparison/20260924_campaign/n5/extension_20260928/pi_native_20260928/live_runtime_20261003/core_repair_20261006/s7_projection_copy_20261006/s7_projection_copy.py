"""Remove only discarded pinned S7 copies; README_S7_PROJECTION_COPY.md."""
import ast
from copy import deepcopy
import hashlib
import inspect
from pathlib import Path
import stat
import textwrap
from types import MethodType


S7_SOURCE_SHA256 = 'a6229a1cc1f967012de2b79780ab92029e63dc3a64e52bf56b563d7e44f18f10'
OWNER = 'S7PresentationState'
METHOD = 'project'
INITIAL = "result = {k: deepcopy(v) for k, v in row.items() if not k.startswith('_')}"
REPLACEMENT = """result = {k: (None if self.ownership_mode in {
    'supported_prefix_v2', 'timestamped_spans_v3'} and k in {
    'segments', 'accepted_identity_snapshot'} else deepcopy(v))
    for k, v in row.items() if not k.startswith('_')}"""


def _same(left, right):
    return ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)


def _method_node(raw, filename):
    tree = ast.parse(raw.decode('utf-8'), filename=filename)
    owners = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == OWNER]
    if len(owners) != 1:
        raise ValueError('Exactly one admitted S7 presentation class required')
    methods = [node for node in owners[0].body if isinstance(node, ast.FunctionDef) and node.name == METHOD]
    if len(methods) != 1 or methods[0].decorator_list:
        raise ValueError('Exactly one undecorated admitted S7 project method required')
    return methods[0]


def _derive(method):
    """Change one initial assignment, then reverse it to prove other AST equality."""
    original = deepcopy(method)
    result = deepcopy(method)
    expected = ast.parse(INITIAL).body[0]
    replacement = ast.parse(REPLACEMENT).body[0]
    matches = [node for node in ast.walk(result) if isinstance(node, ast.Assign) and _same(node, expected)]
    if len(matches) != 1:
        raise ValueError('Pinned initial S7 copy expression differs')
    matches[0].value = deepcopy(replacement.value)
    restored = deepcopy(result)
    reverse = [node for node in ast.walk(restored) if isinstance(node, ast.Assign) and _same(node, replacement)]
    if len(reverse) != 1:
        raise ValueError('Exactly one initial-copy substitution required')
    reverse[0].value = deepcopy(expected.value)
    if not _same(restored, original):
        raise ValueError('Unapproved S7 project AST change')
    return ast.fix_missing_locations(result)


def _read_source(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or path.is_symlink()
            or getattr(info, 'st_file_attributes', 0) & 0x400
            or any(parent.is_symlink() or getattr(parent.lstat(), 'st_file_attributes', 0) & 0x400
                   for parent in path.parents)):
        raise ValueError('Ordinary single-link pinned S7 source required')
    if info.st_size > 1024**2:
        raise ValueError('Finite source-input allowance exceeded')
    with path.open('rb') as stream:
        raw = stream.read(1024**2 + 1)
    if len(raw) > 1024**2:
        raise ValueError('Pinned source grew beyond its input allowance')
    return raw


def bind_project(Presentation, expected_source_path, expected_sha256):
    """Return a hash/origin/AST-bound project(self,row), without importing models.

    Only the two initial values that are overwritten in the supported ownership
    modes become placeholders. Their keys retain exact original insertion order.
    Final per-segment and accepted-snapshot deepcopy calls remain unchanged.
    """
    if expected_sha256 != S7_SOURCE_SHA256:
        raise ValueError('Only the exact admitted S7 source pin is supported')
    path = Path(expected_source_path)
    raw = _read_source(path)
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Pinned S7 source SHA differs')
    method = Presentation.__dict__.get(METHOD)
    if (Presentation.__name__ != OWNER or method is None
            or method.__qualname__ != OWNER + '.' + METHOD):
        raise ValueError('Exact admitted S7 class project method required')
    origin = inspect.getsourcefile(method)
    if origin is None or Path(origin).resolve() != path.resolve():
        raise ValueError('Loaded S7 project origin differs from pinned source')
    original = _method_node(raw, str(path))
    inspected = ast.parse(textwrap.dedent(inspect.getsource(method))).body[0]
    if not _same(inspected, original) or _read_source(path) != raw:
        raise ValueError('Loaded S7 project AST or source changed')
    derived = _derive(original)
    namespace = dict(method.__globals__)
    exec(compile(ast.Module(body=[derived], type_ignores=[]), str(path), 'exec'), namespace)
    result = namespace[METHOD]
    result.__qualname__ = method.__qualname__
    result.__module__ = method.__module__
    result.s7_projection_type = Presentation
    result.s7_projection_original = method
    result.s7_projection_provenance = dict(
        source_sha256=expected_sha256, class_name=OWNER, method=METHOD,
        first_line=original.lineno, last_line=original.end_lineno,
        initial_assignments_replaced=1, overwritten_keys=['segments', 'accepted_identity_snapshot'],
        other_ast_unchanged=True, dictionary_order_unchanged=True,
        final_deepcopy_ownership_unchanged=True, native_math_changed=False)
    return result


def install_project(presentation, project):
    """Install on one exact S7 instance under its existing RLock, before workers.

    Does not change the vendor class or any other presentation instance. A repeat
    with the same derived callable is idempotent; a different instance override
    is rejected instead of silently replacing somebody else's hook.
    """
    if type(presentation) is not getattr(project, 's7_projection_type', None):
        raise ValueError('Exact bound S7 presentation instance required')
    with presentation._lock:
        current = presentation.__dict__.get(METHOD)
        if current is not None:
            if (getattr(current, '__func__', None) is project
                    and getattr(current, '__self__', None) is presentation):
                return dict(project.s7_projection_provenance)
            raise ValueError('Existing per-instance presentation project override differs')
        if type(presentation).__dict__.get(METHOD) is not project.s7_projection_original:
            raise ValueError('Admitted S7 class project changed before installation')
        presentation.project = MethodType(project, presentation)
        return dict(project.s7_projection_provenance)
