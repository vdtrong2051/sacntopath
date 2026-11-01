"""HS-01.1: safe, focused preflight for the existing handheld Gemini 2 live stack.

Offline by design: never opens the camera, imports Orbbec SDK, writes RAW or
modifies SQLite/Git. Real hardware evidence uses existing explicit probes.
Run from any working directory with the ScanToPath virtualenv Python.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FOCUSED_TESTS = (
    "tests/unit/capture/test_gd2_09_05_live.py",
    "tests/ui/capture/test_gd2_09_05_worker.py",
    "tests/ui/capture/test_gd2_09_06_controller.py",
    "tests/unit/capture/test_gd2_09_08_1_keyframe.py",
    "tests/unit/capture/test_hs_01_1_preflight.py",
)
REQUIRED_FILES = (
    "src/scantopath/modules/capture/application/live_stream.py",
    "src/scantopath/modules/capture/presentation/live_worker.py",
    "src/scantopath/modules/capture/presentation/live_controller.py",
    "src/scantopath/modules/capture/infrastructure/process_camera.py",
    "src/scantopath/modules/capture/application/capture_pipeline.py",
    "scripts/gd2_09_05_live_probe.py",
    "scripts/gd2_09_07_3_hardware_probe.py",
    "scripts/gd2_09_08_3_hardware_probe.py",
    *FOCUSED_TESTS,
)
REQUIRED_IMPORTS = {"numpy": "numpy", "PySide6": "PySide6", "Pillow": "PIL", "pytest": "pytest"}


def command(argv: list[str], *, root: Path = ROOT, timeout: int = 20) -> dict:
    try:
        p = subprocess.run(
            argv, cwd=root, text=True, encoding="utf-8", errors="replace",
            capture_output=True, check=False, timeout=timeout,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
                 "QT_QPA_PLATFORM": "offscreen"},
        )
        return {"status": "PASS" if p.returncode == 0 else "FAIL",
                "exit_code": p.returncode, "output_tail": (p.stdout + "\n" + p.stderr)[-3200:]}
    except subprocess.TimeoutExpired:
        return {"status": "FAIL", "reason": f"TIMEOUT_{timeout}S"}
    except OSError as exc:
        return {"status": "FAIL", "reason": type(exc).__name__}


def sdk_diagnostic(env: dict[str, str] | None = None) -> dict:
    values = os.environ if env is None else env
    sdk_bin = values.get("SCANTOPATH_ORBBEC_SDK_BIN", "").strip()
    if not sdk_bin:
        return {"status": "UNVERIFIED", "reason": "SDK_BIN_NOT_SET; loader may use other DLL search paths"}
    location = Path(sdk_bin).expanduser()
    if not location.is_dir():
        return {"status": "FAIL", "reason": "SDK_BIN_DIRECTORY_MISSING"}
    if not (location / "OrbbecSDK.dll").is_file():
        return {"status": "FAIL", "reason": "ORBBEC_SDK_DLL_MISSING"}
    return {"status": "PASS", "reason": "ORBBEC_SDK_DLL_FOUND"}


def native_diagnostic() -> dict:
    try:
        found = importlib.util.find_spec("scantopath._scantopath_native")
    except (ImportError, ValueError):
        found = None
    return {"status": "PASS" if found else "UNVERIFIED",
            "reason": "EXTENSION_SPEC_FOUND_NOT_LOADED" if found else "NATIVE_EXTENSION_NOT_FOUND"}


def write_report(path: Path, report: dict, *, root: Path = ROOT) -> None:
    target = path.expanduser().resolve()
    repo = root.resolve()
    if target == repo or repo in target.parents:
        raise ValueError("EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY")
    if path.is_symlink():
        raise ValueError("EVIDENCE_SYMLINK_NOT_ALLOWED")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: never replace an existing acceptance receipt.
    with target.open("x", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
        fp.write("\n")


def check_baseline(*, root: Path = ROOT, smoke: bool = False) -> dict:
    checks: dict[str, dict] = {}
    checks["python"] = {
        "status": "PASS" if sys.version_info >= (3, 12) else "FAIL",
        "version": sys.version.split()[0], "executable": sys.executable,
    }
    checks["platform"] = {"status": "PASS" if os.name == "nt" else "UNVERIFIED",
                          "system": platform.system(), "architecture": platform.machine()}
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    checks["sources"] = {"status": "PASS" if not missing else "FAIL", "missing": missing}
    for key, module in REQUIRED_IMPORTS.items():
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            found = False
        checks[f"dependency.{key}"] = {"status": "PASS" if found else "FAIL"}
    checks["sdk_bin"] = sdk_diagnostic()
    checks["native_extension"] = native_diagnostic()

    head = command(["git", "rev-parse", "HEAD"], root=root)
    branch = command(["git", "branch", "--show-current"], root=root)
    dirty = command(["git", "status", "--porcelain"], root=root)
    checks["git"] = {
        "status": "PASS" if all(v["status"] == "PASS" for v in (head, branch, dirty)) else "FAIL",
        "head": head.get("output_tail", "").strip() if head["status"] == "PASS" else None,
        "branch": branch.get("output_tail", "").strip() if branch["status"] == "PASS" else None,
        "worktree_dirty": bool(dirty.get("output_tail", "").strip()) if dirty["status"] == "PASS" else None,
    }

    if smoke:
        if any(checks[f"dependency.{name}"]["status"] != "PASS"
               for name in ("pytest", "numpy", "PySide6")) or missing:
            checks["focused_tests"] = {"status": "NOT_RUN", "reason": "MISSING_PREREQUISITES"}
        else:
            checks["focused_tests"] = command(
                [sys.executable, "-X", "utf8", "-m", "pytest", "-q", *FOCUSED_TESTS],
                root=root, timeout=150,
            )
    else:
        checks["focused_tests"] = {"status": "NOT_RUN", "reason": "USE_--smoke"}

    required = ("python", "sources", "git", *(f"dependency.{key}" for key in REQUIRED_IMPORTS))
    fails = [key for key in required if checks[key]["status"] != "PASS"]
    if checks["focused_tests"]["status"] == "FAIL":
        fails.append("focused_tests")
    result = "FAIL" if fails else "PASS_OFFLINE" if smoke and checks["focused_tests"]["status"] == "PASS" else "READY_FOR_SMOKE"
    return {
        "schema": "scantopath-hs-01-1-preflight-v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "decision": result,
        "required_failures": fails,
        "checks": checks,
        "hardware": {"status": "NOT_TESTED", "reason": "NO_CAMERA_OPENED_BY_PREFLIGHT"},
        "camera_capture_saved": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--smoke", action="store_true", help="Run only the focused offline live/capture tests")
    p.add_argument("--json-out", type=Path, help="Optional new evidence file OUTSIDE the repository")
    args = p.parse_args(argv)
    report = check_baseline(smoke=args.smoke)
    for name, result in report["checks"].items():
        print(f"{name}: {result['status']}")
    print("hardware: NOT_TESTED (explicit operator probe required)")
    print("HS_01_1_PREFLIGHT=" + report["decision"])
    if args.json_out is not None:
        try:
            write_report(args.json_out, report)
        except (OSError, ValueError) as exc:
            p.error(f"Cannot create evidence: {exc}")
        print("evidence=" + str(args.json_out.resolve()))
    return 0 if report["decision"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
