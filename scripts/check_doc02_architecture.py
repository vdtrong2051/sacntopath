"""DOC-02 architecture lock gate. Static only; does not edit source or resolve hardware truth.

All CSVs are UTF-8 SIG/UTF-8 and are treated as a snapshot of the R8.5 baseline.
This gate intentionally checks *baseline Git* rather than current old paths, so
DOC-03/04/05 can migrate documents without making the frozen DOC-02 audit fail.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

BASELINE = "493a24d2ab62cd34e5968cbcb60d5f9857c3c4b8"
DIR = Path("docs/standardization")
MAP = DIR / "DOC02_BAN_DO_65.csv"
TRACE = DIR / "DOC02_TRUY_VET_43.csv"
ISSUES = DIR / "DOC02_QUYET_DINH_20.csv"
SPEC = DIR / "DOC02_KIEN_TRUC_TAI_LIEU.md"
TEMPLATE = DIR / "DOC02_KHUON_MAU_VA_TIEU_CHI.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def safe_target(path: str) -> bool:
    if not path or "\\" in path or path.strip() != path or ":" in path or "//" in path:
        return False
    parts = PurePosixPath(path).parts
    if not parts or any(p in (".", "..", "") for p in parts):
        return False
    return path in ("README.md", "docs/README.md") or (parts[0] == "docs" and len(parts) >= 3 and path.endswith((".md", ".csv")))


def baseline_files(root: Path) -> set[str]:
    p = subprocess.run(["git", "ls-tree", "-r", "--name-only", BASELINE],
                       cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=30)
    if p.returncode:
        raise RuntimeError("DOC02_BASELINE_UNAVAILABLE:" + p.stderr[-150:])
    return set(p.stdout.splitlines())


def validate(mapping: list[dict[str, str]], trace: list[dict[str, str]],
             issues: list[dict[str, str]], baseline: set[str],
             spec: str, template: str) -> list[str]:
    errors: list[str] = []
    expected = {"README.md"} | {p for p in baseline if p.startswith("docs/") and p.endswith((".md", ".csv"))}
    olds = [r.get("old_path", "") for r in mapping]
    mids = [r.get("id", "") for r in mapping]
    if len(mapping) != 65 or len(set(olds)) != 65 or set(olds) != expected:
        errors.append("DOC02_65_SOURCE_MAPPING_INCOMPLETE")
    if len(set(mids)) != 65 or set(mids) != {f"DOC-{x:03d}" for x in range(1, 66)}:
        errors.append("DOC02_MAPPING_IDS_INVALID")
    if not all(safe_target(r.get("primary_target", "")) for r in mapping):
        errors.append("DOC02_UNSAFE_DESTINATION")
    if not all(r.get("stage") in {"DOC-03A", "DOC-03B", "DOC-03C", "DOC-04", "DOC-05"} for r in mapping):
        errors.append("DOC02_INVALID_STAGE")
    if any(not r.get("target_owner", "").strip() for r in mapping):
        errors.append("DOC02_OWNER_NOT_ASSIGNED")
    owner_by_target = {}
    for r in mapping:
        target = r.get("primary_target", "")
        role = r.get("target_owner", "")
        if target in owner_by_target and owner_by_target[target] != role:
            errors.append("DOC02_MULTIPLE_OWNERS_FOR_ONE_TARGET:" + target)
        owner_by_target[target] = role
    aliases = [r for r in mapping if r.get("doc02_role") == "ALIAS"]
    if len(aliases) != 7 or any(r.get("compatibility_or_preservation") != "NO_DELETE_UNTIL_DOC05" for r in aliases):
        errors.append("DOC02_ALIAS_POLICY_NOT_LOCKED")
    archives = [r for r in mapping if r.get("old_path", "").startswith("docs/archive/") and
                r.get("old_path") != "docs/archive/README.md"]
    if len(archives) != 12 or any(not r["primary_target"].startswith("docs/99-lich-su/ARCHIVE/") for r in archives):
        errors.append("DOC02_ARCHIVE_PRESERVATION_INCOMPLETE")
    if {r.get("type") for r in trace} != {"CONTENT", "CONTRACT"} or len(trace) != 43:
        errors.append("DOC02_43_TRACE_INCOMPLETE")
    tids = [r.get("id", "") for r in trace]
    if len(set(tids)) != 43 or set(tids) != ({f"CW-{x:02d}" for x in range(1, 28)} | {f"CT-{x:02d}" for x in range(1, 17)}):
        errors.append("DOC02_TRACE_IDS_INVALID")
    if any(not r.get("target_documents") or not r.get("mandatory_content") for r in trace):
        errors.append("DOC02_TRACE_EMPTY_CONTRACT")
    iids = [r.get("issue_id", "") for r in issues]
    if len(issues) != 20 or len(set(iids)) != 20 or set(iids) != {f"DOC01-{x:02d}" for x in range(1, 21)}:
        errors.append("DOC02_20_ISSUES_INCOMPLETE")
    hard = next((r for r in issues if r.get("issue_id") == "DOC01-07"), None)
    if not hard or hard.get("decision") != "OPEN_REQUIRED_SOURCE_DECISION":
        errors.append("DOC02_HARDWARE_DECISION_FABRICATED")
    if any(r.get("implementation_status") != "NOT_IMPLEMENTED_DOC02" for r in issues):
        errors.append("DOC02_ISSUE_STATUS_PREMATURE")
    if "DESIGN_LOCKED / CONTENT_MIGRATION_NOT_STARTED" not in spec or "R6_OVERALL_PENDING" not in spec:
        errors.append("DOC02_SCOPE_OR_ACCEPTANCE_MISSING")
    for required in ("Mẫu MODULE", "Rubric nghiệm thu", "TASK REGISTER", "STATE LEDGER", "Mẫu ACCEPTANCE"):
        if required not in template:
            errors.append("DOC02_TEMPLATE_SECTION_MISSING:" + required)
    return errors


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    files = baseline_files(root)
    mapping, trace, issues = (read_csv(root / p) for p in (MAP, TRACE, ISSUES))
    spec = (root / SPEC).read_text(encoding="utf-8-sig")
    template = (root / TEMPLATE).read_text(encoding="utf-8-sig")
    errors = validate(mapping, trace, issues, files, spec, template)
    return {
        "schema": "scantopath-doc02-architecture-lock-v1", "baseline": BASELINE,
        "status": "PASS" if not errors else "FAIL", "design_status": "DESIGN_LOCKED",
        "content_status": "NOT_MIGRATED", "manual_hmi_status": "NOT_TESTED",
        "count": {"documents": len(mapping), "contents": sum(r['type'] == 'CONTENT' for r in trace),
                  "contracts": sum(r['type'] == 'CONTRACT' for r in trace), "issues": len(issues)},
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        output = args.out_dir.resolve()
        if output == root or output.is_relative_to(root):
            raise ValueError("EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY")
        result = verify(root)
        output.mkdir(parents=True, exist_ok=True)
        (output / "DOC02_GATE.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("DOC02", result['status'], result['count'], "issues", len(result['errors']))
        for error in result['errors']:
            print("DOC02 ERROR", error)
        return 0 if result['status'] == 'PASS' else 1
    except (OSError, ValueError, RuntimeError, KeyError, csv.Error) as exc:
        print("DOC02 GATE FAILED:", repr(exc), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
