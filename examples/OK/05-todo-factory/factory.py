import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER = HERE.parent / "factory.py"


def save_report(path, report):
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_stage(name, brief, work, report):
    log_path = work / f"{name}.log"
    print(f"工程: {name}（ログ: {log_path}）", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(
            [sys.executable, str(RUNNER), str(HERE / name), "--brief", str(brief),
             "--output-dir", str(work / name)],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        )
    status = {0: "passed", 1: "rejected"}.get(result.returncode, "error")
    report["stages"].append({"name": name, "status": status, "log": log_path.name})
    return result.returncode if result.returncode in (0, 1) else 2


def run(brief, work):
    report_path = work / "report.json"
    report = {"stages": [], "artifact": None}
    print(f"出力先: {work}", flush=True)
    try:
        if shutil.which("uvx") is None:
            raise ValueError("Ruffの実行に必要な uvx が見つかりません。")
        original = brief.read_text(encoding="utf-8").strip()
        if not original:
            raise ValueError("題材メモが空です。")
        input_path = work / "brief.md"
        input_path.write_text(original + "\n", encoding="utf-8")
        status = run_stage("plan", input_path, work, report)
        if status:
            return status

        plan = (work / "plan/plan.json").read_text(encoding="utf-8")
        handoff = work / "build-input.md"
        handoff.write_text(f"### 元の題材\n\n{original}\n\n### 計画エージェントの案（参考）\n\n{plan}",
                           encoding="utf-8")
        status = run_stage("build", handoff, work, report)
        if status:
            return status

        release = work / "release"
        release.mkdir()
        app = release / "app.py"
        shutil.copyfile(work / "build/app.py", app)
        report["artifact"] = {"path": "release/app.py", "sha256": hashlib.sha256(app.read_bytes()).hexdigest()}
        print(f"成果物: {app}", flush=True)
        return 0
    except (OSError, UnicodeError, ValueError) as error:
        report["error"] = str(error)
        print(f"工場を実行できませんでした: {error}", file=sys.stderr)
        return 2
    finally:
        save_report(report_path, report)
        print(f"結果: {report_path}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", type=Path, default=HERE / "brief.md")
    args = parser.parse_args()
    sys.exit(run(args.brief, Path(tempfile.mkdtemp(prefix="todo-factory-")).resolve()))
