"""Assemble normal configuration and existing execution adapters. README.md."""
import ast,json,shutil,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;R7=HERE.parents[1]
def bind(p):
    p=Path(p).resolve();b=p.read_bytes()
    return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def main():
    assert not (HERE/"CONFIG.json").exists() and not (HERE/"PREPARATION.json").exists()
    mp=R7/"application/mode_panel_v2/MANIFEST.json";m=json.loads(mp.read_text())
    for b in m["execution_files"]+m["gui_helper_files"]:assert bind(b["path"])==b
    helpers=HERE/"helpers";helpers.mkdir()
    native=R7/"application/observed_presentation_pilot_v1/helpers/Native.py"
    assert bind(native)["sha256"]=="9f426e18dbc88ff61d0f63f85b635e4f5a1ad17f8c7a4c86161c465d7b136cb6"
    shutil.copy2(native,helpers/"Native.py")
    predecessors=[bind(native)]
    for name in ("GuiExecution.py","WidgetProof.py"):
        old=next(b for b in m["gui_helper_files"] if Path(b["path"]).name==name)
        shutil.copy2(old["path"],helpers/name);predecessors.append(old)
    authority=m["closure_authority"];assert bind(authority["path"])==authority
    tree=ast.parse(Path(authority["path"]).read_text(encoding="utf-8-sig"))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="completion_errors")
    closure=ast.unparse(ast.Module(body=[fn],type_ignores=[]))+"\n"
    (helpers/"Closure.py").write_text(closure,encoding="utf-8")
    assert ast.dump(ast.parse(closure),include_attributes=False)==ast.dump(ast.Module(body=[fn],type_ignores=[]),include_attributes=False)
    shutil.copy2(HERE/"README.md",helpers/"README.md")
    source=Path(m["source_root"])
    config=dict(schema="just-peachy.desktop.s7.v1",source_root=str(source),
        source_files=[dict(relative_path=Path(b["path"]).relative_to(source).as_posix(),sha256=b["sha256"]) for b in m["execution_files"]],
        assets=[{k:a[k] for k in ("component_id","path","sha256","deployment_relative_path")} for a in m["assets"]],
        profiles={c:next(j["profile"] for j in m["jobs"] if j["candidate"]==c) for c in ("C065","C088")},
        gallery=next(j["gallery"]["path"] for j in m["jobs"] if j["gallery"]),language="en",
        limits=dict(maximum_file_seconds=3600,diagnostic_file_bytes=1048576,diagnostic_backups=4))
    (HERE/"CONFIG.json").write_text(json.dumps(config,indent=2)+"\n")
    receipt=dict(status="PREPARED_ORDINARY_CONFIG_LAUNCHER_NATIVE_SMOKES_PENDING",config=bind(HERE/"CONFIG.json"),
        source_manifest=bind(mp),script=bind(__file__),launcher=bind(HERE/"App.py"),readme=bind(HERE/"README.md"),
        execution_adapters=[bind(helpers/n) for n in ("Native.py","GuiExecution.py","WidgetProof.py","Closure.py")],
        adapter_predecessors=predecessors,closure_authority=authority,closure_AST_identical=True,
        native_jobs=0,models_loaded=0,default_changed=False,portability_smoke="PENDING")
    (HERE/"PREPARATION.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(dict(status=receipt["status"],assets=len(config["assets"]),modes=4)))
if __name__=="__main__":main()

