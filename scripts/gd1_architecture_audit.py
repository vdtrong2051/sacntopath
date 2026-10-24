"""07.10 — deterministic static evidence (AST) for an offline-first modular MVC audit.

This is a REPORT, not a certification that SOLID has been formally proven.
No runtime import, no SQLite access, no code rewrite and no network.
"""
from __future__ import annotations
import argparse
import ast
from collections import defaultdict
import json
from pathlib import Path


def inspect(root: Path) -> dict:
    source = root / "src" / "scantopath"
    if not source.is_dir():
        raise ValueError("Expected src/scantopath in project root")
    files = sorted(source.rglob("*.py"))
    nodes, edges, ui_leaks, concerns = [], set(), [], []
    for filename in files:
        rel = filename.relative_to(source).as_posix()
        module = "scantopath." + ".".join(filename.relative_to(source).with_suffix("").parts)
        tree = ast.parse(filename.read_text(encoding="utf-8"), filename=str(filename))
        lines = len(filename.read_text(encoding="utf-8").splitlines())
        classes = [x for x in tree.body if isinstance(x, ast.ClassDef)]
        class_info = []
        for cls in classes:
            methods = [x for x in cls.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]
            class_info.append({"class": cls.name, "line": cls.lineno, "methods": len(methods)})
            if len(methods) >= 20:
                concerns.append({"type": "many_methods", "path": rel, "class": cls.name,
                                 "line": cls.lineno, "count": len(methods)})
        if lines >= 500:
            concerns.append({"type": "long_module", "path": rel, "lines": lines})
        imports = []
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            if isinstance(node, ast.ImportFrom):
                if node.level and node.module is not None:
                    # Resolve relative import against current module package.
                    parts = module.split(".")[:-1]
                    base = parts[:len(parts) - (node.level - 1)]
                    targets = [".".join(base + [node.module])]
                elif node.module:
                    targets = [node.module]
            for target in targets:
                if target.startswith("scantopath."):
                    imports.append({"module": target, "line": node.lineno})
                    src_layer = module.split(".")[1]
                    dst_layer = target.split(".")[1]
                    edges.add((src_layer, dst_layer))
                    if src_layer in ("domain", "metadata", "storage", "application", "acquisition") and dst_layer == "ui":
                        ui_leaks.append({"path": rel, "line": node.lineno, "module": target})
        nodes.append({"path": rel, "module": module, "lines": lines, "classes": class_info,
                      "imports": imports})
    projects = [n for n in nodes if n["path"].startswith(("ui/projects/", "application/projects/", "metadata/", "storage/"))]
    return {"version": "07.10", "files": len(nodes), "python_lines": sum(n["lines"] for n in nodes),
            "layer_edges": [list(e) for e in sorted(edges)], "forbidden_ui_imports": ui_leaks,
            "concerns": concerns, "modules": nodes,
            "project_related_files": [p["path"] for p in projects]}


def render(report: dict) -> str:
    lines = ["# 07.10 — Automated architecture evidence", "",
             "This is a reproducible AST inventory, not automatic SOLID compliance certification.", "",
             f"- Python files inspected: {report['files']}",
             f"- Python source lines: {report['python_lines']}",
             f"- Illegal inward-to-UI imports found: {len(report['forbidden_ui_imports'])}", "",
             "## Layer dependencies (source -> imported layer)", ""]
    for a,b in report["layer_edges"]:
        lines.append(f"- `{a}` → `{b}`")
    lines += ["", "## Structural hotspots (review manually)", ""]
    for c in report["concerns"]:
        lines.append(f"- `{c['path']}`: {c['type']} — {c.get('class', '')} {c.get('count', c.get('lines'))}")
    lines += ["", "## Forbidden import evidence", ""]
    for c in report["forbidden_ui_imports"]:
        lines.append(f"- `{c['path']}:{c['line']}` imports `{c['module']}`")
    if not report["forbidden_ui_imports"]:lines.append("- None detected by AST (does not prove dependency inversion).")
    return "\n".join(lines)+"\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Collect ScanToPath static architecture evidence")
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args(argv)
    result = inspect(args.project_root)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    (args.out_dir / "ARCH_AUDIT.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (args.out_dir / "ARCH_AUDIT.md").write_text(render(result),encoding="utf-8")
    print(f"Architecture scan: {result['files']} files, {len(result['concerns'])} structural hotspots, "
          f"{len(result['forbidden_ui_imports'])} inward-UI imports")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
