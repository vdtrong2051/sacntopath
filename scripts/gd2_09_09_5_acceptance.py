"""GD2-09.09.5 offline-first, read-only acceptance orchestrator.

Usage (from repo root):
 python -u -X utf8 -m scripts.gd2_09_09_5_acceptance

Runs every collected pytest test, targeted offline E2E, architecture, syntax,
read-only operator-store inspection, and configured CTest tests (if present).
Writes evidence OUTSIDE the repository. No SDK, camera, Git writes or migrations.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

E2E = Path("tests/integration/end_to_end/test_gd2_09_09_5_offline_e2e.py")
EXPECTED_BRANCH = "feat/gd2-mvpb-20261104"


def _inside(path: Path, folder: Path) -> bool:
    return path == folder or folder in path.parents


def _run(label, argv, *, repo, out, env, timeout=1800):
    log = out / f"{label.lower()}.log"
    print(f"\n[{label}] RUN: {' '.join(map(str, argv))}", flush=True)
    start = time.monotonic()
    try:
        with log.open("w", encoding="utf-8", newline="\n") as stream:
            proc = subprocess.run(argv, cwd=repo, env=env,
                                  stdout=stream, stderr=subprocess.STDOUT,
                                  check=False, timeout=timeout)
        code = proc.returncode
        status = "PASS" if code == 0 else "FAIL"
    except subprocess.TimeoutExpired:
        code = 124
        status = "TIMEOUT"
        with log.open("a", encoding="utf-8") as stream:
            stream.write(f"\nTIMEOUT after {timeout} seconds\n")
    except OSError as exc:
        code = 127
        status = "ERROR"
        log.write_text(f"Failed to start: {type(exc).__name__}: {exc}\n", encoding="utf-8")
    secs = round(time.monotonic() - start, 2)
    print(f"[{label}] {status} | exit={code} | {secs}s | {log}", flush=True)
    if status != "PASS":
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-35:]
        print("\n".join(tail), flush=True)
    return {"name": label, "status": status, "exit_code": code,
            "elapsed_seconds": secs, "log": str(log)}


def _xml_counts(path):
    if not path.is_file():
        return None
    root = ET.parse(path).getroot()
    suites = ([root] if root.tag == "testsuite" else root.findall(".//testsuite"))
    if not suites:
        return None
    return {k: sum(int(el.attrib.get(k, 0)) for el in suites)
            for k in ("tests", "errors", "failures", "skipped")}


def _store_sentinel(root: Path) -> dict:
    # Read-only: only metadata. The validation script performs all deep checks.
    p = root / "metadata.sqlite3"
    return {"exists": root.exists(), "sqlite_exists": p.is_file(),
            "sqlite_size": p.stat().st_size if p.is_file() else None}


def _write_report(out, result):
    (out / "summary.json").write_text(json.dumps(result, ensure_ascii=False,
                                               indent=2) + "\n", encoding="utf-8")
    lines = ["# GD2-09.09.5 — Offline Acceptance Evidence", "",
             f"- Executed (UTC): `{result['timestamp_utc']}`",
             f"- Git branch: `{result['branch']}`",
             f"- Git HEAD: `{result['git_head']}`",
             f"- Python: `{result['python']}`",
             f"- Data root: `{result['operator_store']}` (READ ONLY)",
             f"- Result: **{result['decision']}**", "",
             "| Gate | Status | Exit | Tests / failures / errors / skips |",
             "|---|---|---:|---|",
             ]
    for phase in result["gates"]:
        m = phase.get("pytest_counts")
        d = (" / ".join(str(m[k]) for k in ("tests", "failures", "errors", "skipped"))
             if m else "—")
        lines.append(f"| {phase['name']} | {phase['status']} | {phase.get('exit_code', '—')} | {d} |")
    lines += ["", "## Decision semantics", "",
              "PASS: all required gates passed. Test skips are disclosed, never treated as executed checks.",
              "INCOMPLETE: a required gate was not executed. FAIL: one or more required gates failed.",
              "CTest is recorded independently: NOT_CONFIGURED is not a native PASS.",
              "Camera Gemini 2 hardware and manual UX acceptance are NOT covered by offline tests.",
              "No files in the operator store were opened for writing by this runner.", "",
              "## Operator-only final steps", "",
              "1. Review the complete pytest logs and skipped-case list.",
              "2. Verify UI at target resolutions and perform manual camera test if hardware acceptance is required.",
              "3. Commit 09.09.5 only after reviewing results, never automatically.", "",
             ]
    (out / "ACCEPTANCE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--evidence-dir", type=Path, default=None)
    ap.add_argument("--store-root", type=Path, default=None)
    ap.add_argument("--require-store", action="store_true", help="Fail if actual store is missing")
    ap.add_argument("--ctest", choices=("auto", "required", "skip"), default="auto")
    ap.add_argument("--ctest-config", choices=("Release", "Debug", "RelWithDebInfo", "MinSizeRel"), default="Release")
    ap.add_argument("--timeout-seconds", type=int, default=1800)
    args = ap.parse_args(argv)
    repo = args.repo.resolve()
    if not (repo / "pyproject.toml").is_file() or not (repo / E2E).is_file():
        ap.error("Run after installing the 09.09.5 package inside the ScanToPath repo")
    if sys.version_info < (3, 12):
        ap.error("Python 3.12+ required")
    branch_proc = subprocess.run(["git", "branch", "--show-current"], cwd=repo,
                                 text=True, capture_output=True, check=False)
    if branch_proc.returncode or branch_proc.stdout.strip() != EXPECTED_BRANCH:
        ap.error(f"Expected branch {EXPECTED_BRANCH}; got {branch_proc.stdout.strip()!r}")
    sha_proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                              text=True, capture_output=True, check=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    evidence = (args.evidence_dir or
                repo.parent / "_setup" / "GD2_09_09_5_RESULTS" / stamp).resolve()
    if _inside(evidence, repo):
        ap.error("Evidence directory MUST be outside repository (to prevent tracking artifacts)")
    evidence.mkdir(parents=True, exist_ok=False)
    store = (args.store_root or repo / "scantopath-data").resolve()
    if not _inside(store, repo) and not args.store_root:
        ap.error("Unexpected default data workspace path")
    if _inside(evidence, store):
        ap.error("Evidence path must not be inside operator data workspace")

    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONUTF8"] = "1"
    gates = []
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.splitlines()[0],
        "branch": branch_proc.stdout.strip(),
        "git_head": sha_proc.stdout.strip(),
        "operator_store": str(store),
        "store_sentinel_before": _store_sentinel(store),
        "gates": gates,
    }
    try:
        e2e_xml = evidence / "e2e.xml"
        g = _run("OFFLINE_E2E", [sys.executable, "-X", "utf8", "-m", "pytest",
                                 "-q", "-ra", str(E2E), f"--junitxml={e2e_xml}"],
                 repo=repo, out=evidence, env=env, timeout=min(600, args.timeout_seconds))
        g["pytest_counts"] = _xml_counts(e2e_xml)
        counts = g["pytest_counts"]
        # A skipped E2E is NOT evidence of successful lifecycle verification.
        if g["status"] == "PASS" and (
            counts is None or counts["tests"] < 2 or counts["skipped"] != 0
        ):
            g["status"] = "FAIL"
            g["exit_code"] = 3
            g["reason"] = "E2E skipped or fewer than two cases collected"
            print("[OFFLINE_E2E] FAIL: missing/skip-only E2E cases", flush=True)
        gates.append(g)

        full_xml = evidence / "all_pytest.xml"
        g = _run("ALL_PYTEST", [sys.executable, "-X", "utf8", "-m", "pytest",
                                 "-q", "-ra", "tests", f"--junitxml={full_xml}"],
                 repo=repo, out=evidence, env=env, timeout=args.timeout_seconds)
        g["pytest_counts"] = _xml_counts(full_xml)
        counts = g["pytest_counts"]
        if g["status"] == "PASS" and (counts is None or counts["tests"] < 2):
            g["status"] = "FAIL"
            g["exit_code"] = 3
            g["reason"] = "Full suite collected fewer than two test cases"
        gates.append(g)

        gates.append(_run("ARCHITECTURE", [sys.executable, "-X", "utf8",
                                            "scripts/check_architecture_boundaries.py"],
                          repo=repo, out=evidence, env=env, timeout=180))

        gates.append(_run("COMPILEALL", [sys.executable, "-X", "utf8", "-m", "compileall",
                                         "-q", "src/scantopath", "tests", "scripts"],
                          repo=repo, out=evidence, env=env, timeout=180))

        if store.is_dir() and (store / "metadata.sqlite3").is_file():
            gates.append(_run("OPERATOR_STORE_READ_ONLY", [sys.executable, "-X", "utf8", "-m",
                                                        "scripts.gd2_09_09_1_inspect_store",
                                                        "--root", str(store)],
                              repo=repo, out=evidence, env=env, timeout=120))
        else:
            st = "FAIL" if args.require_store else "NOT_RUN"
            gates.append({"name": "OPERATOR_STORE_READ_ONLY", "status": st,
                          "exit_code": 2 if args.require_store else None,
                          "reason": "Store missing; no automatic initialization"})
            print(f"[OPERATOR_STORE_READ_ONLY] {st}: no existing SQLite store")

        build_dirs = (repo / "build", repo / "build" / "Release", repo / "out" / "build")
        configured = next((p for p in build_dirs if (p / "CTestTestfile.cmake").is_file()), None)
        if args.ctest == "skip":
            gates.append({"name": "CTEST", "status": "NOT_RUN", "reason": "operator opted out"})
        elif configured is not None and shutil.which("ctest"):
            ctest_result = _run("CTEST", ["ctest", "--test-dir", str(configured),
                                         "-C", args.ctest_config, "--output-on-failure"], repo=repo, out=evidence,
                                env=env, timeout=args.timeout_seconds)
            # CTest returns zero even when a configured directory contains no tests.
            ctest_text = Path(ctest_result["log"]).read_text(encoding="utf-8", errors="replace")
            if ctest_result["status"] == "PASS" and (
                "No tests were found" in ctest_text or "Total Tests: 0" in ctest_text
            ):
                ctest_result["status"] = "NOT_CONFIGURED"
                ctest_result["reason"] = "Configured CTest directory contains zero tests"
                print("[CTEST] NOT_CONFIGURED: zero tests executed", flush=True)
            gates.append(ctest_result)
        else:
            st = "FAIL" if args.ctest == "required" else "NOT_CONFIGURED"
            gates.append({"name": "CTEST", "status": st,
                          "reason": "No CTestTestfile.cmake or ctest executable found"})
            print(f"[CTEST] {st}: no available configured CTest build")
    except KeyboardInterrupt:
        gates.append({"name": "INTERRUPTED", "status": "FAIL", "reason": "Operator interrupted run"})
    finally:
        result["store_sentinel_after"] = _store_sentinel(store)
        must = {"OFFLINE_E2E", "ALL_PYTEST", "ARCHITECTURE", "COMPILEALL"}
        if args.require_store:
            must.add("OPERATOR_STORE_READ_ONLY")
        if args.ctest == "required":
            must.add("CTEST")
        by_name = {x["name"]: x for x in gates}
        result["decision"] = (
            "FAIL" if any(x["status"] in ("FAIL", "ERROR", "TIMEOUT") for x in gates)
            else "INCOMPLETE" if any(by_name.get(n, {}).get("status") != "PASS" for n in must)
            else "PASS_OFFLINE_SOFTWARE"
        )
        _write_report(evidence, result)
        print(f"\nGD2_09_09_5={result['decision']}", flush=True)
        print(f"EVIDENCE={evidence}", flush=True)
        print(f"REPORT={evidence / 'ACCEPTANCE_REPORT.md'}", flush=True)
    return 0 if result["decision"] == "PASS_OFFLINE_SOFTWARE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
