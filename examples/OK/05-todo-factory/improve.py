import argparse
import fcntl
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from build.check import ACCEPTANCE
from factory import HERE, RUNNER, save_report


def promote(state, release, manifest):
    save_report(release / "manifest.json", manifest)
    pending = state / ".next"
    pending.unlink(missing_ok=True)
    pending.symlink_to(release.relative_to(state), target_is_directory=True)
    pending.replace(state / "current")


def initialize(state, app):
    if (state / "current").is_symlink():
        raise ValueError("初期版は登録済みです。")
    release = Path(tempfile.mkdtemp(prefix="initial-", dir=state / "runs"))
    shutil.copyfile(app, release / "app.py")
    result = subprocess.run([sys.executable, str(HERE / "build/check.py"), str(release)],
                            stdin=subprocess.DEVNULL, timeout=60)
    if result.returncode:
        raise ValueError("初期版が検査に合格しませんでした。")
    promote(state, release, {"tickets": [], "acceptance": []})


def load_ticket(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"request", "acceptance"}:
        raise ValueError("チケットには request と acceptance が必要です。")
    request, acceptance = data["request"], data["acceptance"]
    if not isinstance(request, str) or not request.strip():
        raise ValueError("request に何を改善したいかを書いてください。")
    if not isinstance(acceptance, str) or acceptance not in ACCEPTANCE:
        raise ValueError(f"acceptance は登録済みの検査から選んでください: {', '.join(ACCEPTANCE)}")
    return request.strip(), acceptance


def process_ticket(state, path):
    ticket_id = path.stem
    current = (state / "current").resolve(strict=True)
    manifest = json.loads((current / "manifest.json").read_text(encoding="utf-8"))
    receipt = state / "results" / path.name
    if ticket_id in manifest["tickets"]:
        return "passed"
    if receipt.exists():
        return json.loads(receipt.read_text(encoding="utf-8"))["status"]

    work = Path(tempfile.mkdtemp(prefix="ticket-", dir=state / "runs"))
    report = {"ticket": ticket_id, "base": str(current.relative_to(state)),
              "run": str(work.relative_to(state)), "status": "error"}
    try:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", ticket_id):
            raise ValueError("チケットIDは64文字以内の英数字・ハイフン・アンダースコアにしてください。")
        snapshot = work / "ticket.json"
        shutil.copyfile(path, snapshot)
        request, acceptance = load_ticket(snapshot)
        if acceptance in manifest["acceptance"]:
            raise ValueError("合格済みの検査だけでは新しい変更を判定できません。新しい受け入れ検査を追加してください。")
        checks = [*manifest["acceptance"], acceptance]
        report["acceptance"] = checks
        contracts = "\n\n".join((HERE / f"acceptance/{key}.md").read_text(encoding="utf-8").strip()
                                for key in checks)
        brief = work / "input.md"
        brief.write_text(
            f"## 今回の変更依頼\n\n{request}\n\n"
            "作業先の既存 app.py を起点に、依頼に必要な箇所だけを変更してください。"
            "基本仕様と以下の受け入れ条件をすべて維持し、既存の保存形式を壊さないでください。\n\n"
            f"{contracts}\n", encoding="utf-8",
        )
        with (work / "build.log").open("w", encoding="utf-8") as log:
            command = [sys.executable, str(RUNNER), str(HERE / "build"), "--brief", str(brief),
                       "--output-dir", str(work / "candidate"), "--seed-file", str(current / "app.py")]
            for key in checks:
                command.extend(["--check-arg", key])
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode == 0:
            release = work / "release"
            release.mkdir()
            shutil.copyfile(work / "candidate/app.py", release / "app.py")
            promote(state, release, {"tickets": [*manifest["tickets"], ticket_id], "acceptance": checks})
            report["status"] = "passed"
        elif result.returncode == 1:
            report["status"] = "rejected"
    except (OSError, ValueError) as error:
        report["error"] = str(error)

    pending = work / "result.json"
    save_report(pending, report)
    pending.replace(receipt)
    print(f"{ticket_id}: {report['status']}（{work}）", flush=True)
    return report["status"]


def main():
    parser = argparse.ArgumentParser(description="チケットを読んでTODOアプリを更新する")
    parser.add_argument("state", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--init", type=Path, metavar="APP_PY")
    mode.add_argument("--ticket", type=Path, metavar="JSON", help="指定したチケット1枚だけを処理する")
    mode.add_argument("--once", action="store_true", help="現在のキューを1回確認する")
    mode.add_argument("--watch", action="store_true", help="チケットを5秒ごとに確認する")
    args = parser.parse_args()
    state = args.state.resolve()
    try:
        if shutil.which("uvx") is None:
            raise ValueError("Ruffの実行に必要な uvx が見つかりません。")
        for name in ("inbox", "runs", "results"):
            (state / name).mkdir(parents=True, exist_ok=True)
        with (state / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.init is not None:
                initialize(state, args.init.resolve())
                print(f"初期アプリ: {state / 'current/app.py'}")
                return 0
            if not (state / "current/app.py").is_file():
                raise ValueError("先に --init で app.py を登録してください。")
            if args.ticket is not None:
                status = process_ticket(state, args.ticket)
                return {"passed": 0, "rejected": 1}.get(status, 2)
            while True:
                for path in sorted((state / "inbox").glob("*.json")):
                    process_ticket(state, path)
                if args.once:
                    return 0
                time.sleep(5)
    except BlockingIOError:
        print("この状態ディレクトリでは別のワーカーが動いています。", file=sys.stderr)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(error, file=sys.stderr)
    except KeyboardInterrupt:
        return 130
    return 2


if __name__ == "__main__":
    sys.exit(main())
