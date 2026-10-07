"""Ten source/AST capacity checks; run only via the registered runner in the README."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import posixpath
from types import SimpleNamespace
import unittest


PIN = '55f449d563b3011a0793cef174921a215cd9aeb0dbbaa597b228ae4ba889fbbf'
ORIGINALS = {
    'worker.py': '89cb348aa6701f2324e33dba647263a823c52cb2c1a57d483ac85d2c2a7330a6',
    'native_scope.py': '2960069e42f0890bdd16f573d2c65946a422389f2bf19714cb17fdc89428caaa',
    'launch_raw_qualification_action.py': 'be42aa3dd44c01420a097a3aa6997545fa8b4b85138e18a160b32cac8b0c60e0',
}
GIB = 1024**3
MIB = 1024**2


def dump(node):
    return ast.dump(node, include_attributes=False)


def function(tree, name):
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(matches) != 1:
        raise AssertionError('One exact function required: '+name)
    return matches[0]


def assigned(tree, name):
    matches = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and
               len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == name]
    if name == 'unit_receipt':
        matches = [n for n in matches if isinstance(n.value, ast.Call) and
                   isinstance(n.value.func, ast.Name) and n.value.func.id == 'dict']
    if len(matches) != 1:
        raise AssertionError('One assignment required: '+name)
    return matches[0]


def scalar(node, scope=None):
    return eval(compile(ast.Expression(copy.deepcopy(node)), '<scalar-source-check>', 'eval'),
                {} if scope is None else dict(scope))


def as_pair(tree):
    pairs = [n for n in ast.walk(tree) if isinstance(n, ast.Tuple) and len(n.elts) == 2 and
             isinstance(n.elts[0], ast.Attribute) and n.elts[0].attr == 'RLIMIT_AS']
    if len(pairs) != 1:
        raise AssertionError('One early AS tuple required')
    return pairs[0]


def without_doc(tree):
    result = copy.deepcopy(tree)
    if result.body and isinstance(result.body[0], ast.Expr) and isinstance(result.body[0].value, ast.Constant):
        result.body.pop(0)
    return result


def envelope_dict(tree):
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'publish' and len(n.args) == 2 and
             isinstance(n.args[0], ast.BinOp) and isinstance(n.args[0].right, ast.Constant)
             and n.args[0].right.value == 'ENVELOPE.json']
    if len(calls) != 1 or not isinstance(calls[0].args[1], ast.Call):
        raise AssertionError('One actual worker envelope required')
    return calls[0].args[1]


class ModelAddressSpaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('JP_AS_REGISTERED_OWNER'):
            raise RuntimeError('The registered source-backup runner is required')
        cls.base = Path(os.environ['JP_AS_TEST_BASE'])
        cls.here = Path(__file__).resolve().parent
        cls.old = {name: ast.parse((cls.base/name).read_bytes()) for name in ORIGINALS}
        cls.new = {name: ast.parse((cls.here/name).read_bytes()) for name in ORIGINALS}
        cls.wrapper_old = ast.parse(assigned(function(cls.old['launch_raw_qualification_action.py'], 'wrapper_source'), 'body').value.value)
        cls.wrapper_new = ast.parse(assigned(function(cls.new['launch_raw_qualification_action.py'], 'wrapper_source'), 'body').value.value)

    def test_01_pinned_sources_and_preservation(self):
        self.assertEqual(hashlib.sha256((self.base/'PACKAGE_MANIFEST.json').read_bytes()).hexdigest(), PIN)
        manifest = {r['path']: r for r in json.loads((self.base/'PACKAGE_MANIFEST.json').read_bytes())['files']}
        for name, expected in ORIGINALS.items():
            self.assertEqual(hashlib.sha256((self.base/name).read_bytes()).hexdigest(), expected)
            self.assertEqual(manifest[name]['sha256'], expected)
            for suffix in ('backup', 'restore'):
                self.assertEqual((self.here/'preserved32'/(name+'.'+suffix)).read_bytes(), (self.base/name).read_bytes())

    def test_02_worker_ast_reverse_only_capacity_and_receipts(self):
        old = without_doc(self.old['worker.py']); new = without_doc(self.new['worker.py'])
        before = as_pair(function(old, 'bootstrap')); changed = as_pair(function(new, 'bootstrap'))
        self.assertEqual(scalar(before.elts[1]), 768*MIB)
        self.assertEqual(scalar(changed.elts[1]), GIB)
        changed.elts[1] = copy.deepcopy(before.elts[1])
        old_main = function(old, 'main'); new_main = function(new, 'main')
        env = envelope_dict(new_main)
        extra = {'address_space', 'stack', 'model_address_space_scope'}
        self.assertEqual(extra & {k.arg for k in env.keywords}, extra)
        env.keywords = [k for k in env.keywords if k.arg not in extra]
        imports = [n for n in new_main.body if isinstance(n, ast.Import) and
                   len(n.names) == 1 and n.names[0].name == 'resource']
        self.assertEqual(len(imports), 1)
        new_main.body.remove(imports[0])
        positions = [i for i, n in enumerate(old_main.body) if isinstance(n, ast.Import) and
                     len(n.names) == 1 and n.names[0].name == 'resource']
        self.assertEqual(len(positions), 1)
        new_main.body.insert(positions[0], imports[0])
        self.assertEqual(dump(new), dump(old))

    def test_03_frontend_ast_reverse_only_inherited_hard(self):
        old = without_doc(self.old['native_scope.py']); new = without_doc(self.new['native_scope.py'])
        before = assigned(function(old, 'bootstrap'), 'memory').value
        changed = assigned(function(new, 'bootstrap'), 'memory').value
        self.assertIsInstance(changed, ast.IfExp)
        self.assertEqual(scalar(changed.body.elts[1]), GIB)
        changed.body.elts[1] = copy.deepcopy(before.body.elts[1])
        self.assertEqual(dump(new), dump(old))

    def test_04_shared_wrapper_ast_reverse_exact_regions(self):
        old_outer = without_doc(self.old['launch_raw_qualification_action.py'])
        new_outer = without_doc(self.new['launch_raw_qualification_action.py'])
        old_body = copy.deepcopy(self.wrapper_old); new_body = copy.deepcopy(self.wrapper_new)
        policy = assigned(new_body, 'recording_model_scope')
        cap = assigned(new_body, 'model_address_space_bytes')
        self.assertEqual(scalar(cap.value.body), GIB)
        self.assertEqual(scalar(cap.value.orelse), 768*MIB)
        new_body.body.remove(policy); new_body.body.remove(cap)
        self.assertEqual(dump(as_pair(new_body).elts[1]), dump(ast.Name(id='model_address_space_bytes', ctx=ast.Load())))
        as_pair(new_body).elts[1] = copy.deepcopy(as_pair(old_body).elts[1])
        receipt = assigned(new_body, 'unit_receipt').value
        extra = {'address_space', 'stack', 'qualification_kind', 'recording_model_scope'}
        self.assertEqual(extra & {k.arg for k in receipt.keywords}, extra)
        receipt.keywords = [k for k in receipt.keywords if k.arg not in extra]
        self.assertEqual(dump(new_body), dump(old_body))
        assigned(function(new_outer, 'wrapper_source'), 'body').value = copy.deepcopy(
            assigned(function(old_outer, 'wrapper_source'), 'body').value)
        self.assertEqual(dump(new_outer), dump(old_outer))

    def test_05_worker_both_limits_are_finite(self):
        bootstrap = function(self.new['worker.py'], 'bootstrap')
        self.assertEqual(scalar(as_pair(bootstrap).elts[1]), GIB)
        setters = [n for n in ast.walk(bootstrap) if isinstance(n, ast.Call) and
                   isinstance(n.func, ast.Attribute) and n.func.attr == 'setrlimit' and
                   n.args and isinstance(n.args[0], ast.Name) and n.args[0].id == 'kind']
        self.assertEqual(len(setters), 1)
        self.assertEqual(dump(setters[0].args[1]), dump(ast.parse('(value,value)', mode='eval').body))

    def test_06_frontend_and_outside_effective_limits(self):
        expression = assigned(function(self.new['native_scope.py'], 'bootstrap'), 'memory').value
        self.assertEqual(scalar(expression, {'inside_service': True}), (256*MIB, GIB))
        self.assertEqual(scalar(expression, {'inside_service': False}), (128*MIB, 128*MIB))

    def wrapper_limit(self, settings):
        policy = assigned(self.wrapper_new, 'recording_model_scope').value
        cap = assigned(self.wrapper_new, 'model_address_space_bytes').value
        active = scalar(policy, {'SETTINGS': settings, 'os': SimpleNamespace(path=posixpath)})
        self.assertIs(type(active), bool)
        return scalar(cap, {'recording_model_scope': active})

    def test_07_hour_and_modern_named_live_saved_parent(self):
        self.assertEqual(self.wrapper_limit({'kind': 'full_app_hour'}), GIB)
        for source in ('live', 'saved'):
            for embedding in ('redimnet', 'titanet'):
                with self.subTest(source=source, embedding=embedding):
                    self.assertEqual(self.wrapper_limit(dict(kind='gui', output='/fresh', argv=['/fresh/classic_driver.py', '/fresh/settings.json'],
                        selection=dict(input_source=source, embedding=embedding))), GIB)

    def test_08_other_parents_preserve_original_cap(self):
        cases = [dict(kind=k) for k in ('raw', 'pipeline', 'storage', 'backup')]
        valid = dict(input_source='live', embedding='redimnet')
        cases.extend((dict(kind='gui'), dict(kind='gui', argv=[], selection=valid),
                      dict(kind='gui', argv=['/fresh/native_gui_driver.py'], selection=valid),
                      dict(kind='gui', output='/fresh', argv=['/fresh/classic_driver.py']),
                      dict(kind='gui', output='/fresh', argv=['/fresh/classic_driver.py'], selection=dict(input_source='live', embedding='anonymous')),
                      dict(kind='gui', output='/fresh', argv=['/fresh/classic_driver.py'], selection=dict(input_source='other', embedding='redimnet')),
                      dict(kind='gui', output='/fresh', argv=['/foreign/classic_driver.py'], selection=valid)))
        for settings in cases:
            with self.subTest(settings=settings):
                self.assertEqual(self.wrapper_limit(settings), 768*MIB)

    def test_09_receipts_read_actual_limits_not_declared_constants(self):
        actual = {11: (123456, 234567), 12: (345678, 456789)}
        resource = SimpleNamespace(RLIMIT_AS=11, RLIMIT_STACK=12, getrlimit=lambda kind: actual[kind])
        for receipt in (envelope_dict(function(self.new['worker.py'], 'main')),
                        assigned(self.wrapper_new, 'unit_receipt').value):
            fields = {k.arg: k.value for k in receipt.keywords}
            self.assertEqual(scalar(fields['address_space'], {'resource': resource}), list(actual[11]))
            self.assertEqual(scalar(fields['stack'], {'resource': resource}), list(actual[12]))

    def test_10_inherited_hard_and_other_safety_guards(self):
        def child_limit(hard, requested):
            if requested > hard:
                raise ValueError('Unprivileged child cannot raise inherited hard AS')
            return requested, requested
        with self.assertRaises(ValueError):
            child_limit(768*MIB, GIB)
        self.assertEqual(child_limit(GIB, GIB), (GIB, GIB))
        self.assertEqual(child_limit(GIB, 768*MIB), (768*MIB, 768*MIB))
        gallery = ast.parse((self.base/'gallery_worker.py').read_bytes())
        self.assertEqual(scalar(as_pair(function(gallery, 'early_owner')).elts[1]), 768*MIB)
        source = ast.parse((self.base/'installed_source.py').read_bytes())
        calls = [n for n in ast.walk(source) if isinstance(n, ast.Call) and
                 isinstance(n.func, ast.Attribute) and n.func.attr == 'setrlimit' and
                 n.args and isinstance(n.args[0], ast.Attribute) and n.args[0].attr == 'RLIMIT_AS']
        self.assertEqual(len(calls), 1)
        self.assertEqual(scalar(calls[0].args[1]), (256*MIB, 256*MIB))
        main = function(self.new['worker.py'], 'main')
        comparisons = [n for n in ast.walk(main) if isinstance(n, ast.Compare) and
                       any(isinstance(v, ast.Constant) and v.value == 'available_ram' for v in ast.walk(n.left))]
        self.assertEqual(len(comparisons), 1)
        self.assertEqual(scalar(comparisons[0].comparators[0]), 850*MIB)
        engine = ast.parse((self.base/'installed_engine.py').read_bytes())
        floors = [n for n in ast.walk(engine) if isinstance(n, ast.Compare) and
                  any(isinstance(v, ast.Constant) and v.value == 'available_ram' for v in ast.walk(n.left))]
        self.assertTrue(any(scalar(n.comparators[0]) == 192*MIB for n in floors))


if __name__ == '__main__':
    raise SystemExit('Use run_host_model_address_space_checks.py after root assigns the host slot; see README_MODEL_ADDRESS_SPACE.md')
