import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ATTEMPT_LIMIT = 3
AGENT_TIMEOUT = 300
CHECK_TIMEOUT = 60


def build_prompt(example_dir, brief_path):
    builder = example_dir / "agents" / "builder.md"
    default_brief = example_dir / "brief.md"
    sections = [("共通仕様", example_dir / "spec.md")]
    if builder.is_file():
        sections.insert(0, ("生成エージェントの役割", builder))
    if brief_path is not None or default_brief.is_file():
        sections.append(("今回の入力", brief_path or default_brief))
    return "\n\n".join(
        f"## {title}\n\n{path.read_text(encoding='utf-8').strip()}"
        for title, path in sections
    ) + "\n\n説明だけで終わらず、作業ディレクトリに成果物を作ってください。\n"


def run_factory(example_dir, output_dir, brief_path, *, check_args=()):
    codex = shutil.which("codex")
    if codex is None:
        print("PATH に Codex CLI が見つかりません。", file=sys.stderr)
        return 2

    spec_path = example_dir / "spec.md"
    checker = example_dir / "check.py"
    if not checker.is_file() or not spec_path.is_file():
        print("作例のディレクトリに spec.md と check.py が必要です。", file=sys.stderr)
        return 2

    try:
        prompt_base = build_prompt(example_dir, brief_path)
    except (OSError, UnicodeError) as error:
        print(f"入力を読み込めませんでした: {error}", file=sys.stderr)
        return 2

    print(f"出力先: {output_dir}", flush=True)
    feedback = ""
    for attempt in range(1, ATTEMPT_LIMIT + 1):
        print(f"試行 {attempt}/{ATTEMPT_LIMIT}", flush=True)
        prompt = prompt_base
        if feedback:
            prompt += "\n前回の自動検査で失敗した条件:\n" + feedback

        try:
            generation = subprocess.run(
                [
                    codex, "-a", "never", "exec", "--skip-git-repo-check",
                    "--sandbox", "workspace-write", "-",
                ],
                cwd=output_dir,
                input=prompt,
                text=True,
                encoding="utf-8",
                timeout=AGENT_TIMEOUT,
            )
            if generation.returncode != 0:
                print(f"Codexが終了コード {generation.returncode} を返しました。", file=sys.stderr)
                return 2

            check = subprocess.run(
                [sys.executable, str(checker), str(output_dir), *check_args],
                stdout=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                timeout=CHECK_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f"生成または検査を実行できませんでした: {error}", file=sys.stderr)
            return 2

        if check.returncode == 0:
            if check.stdout.strip():
                print(check.stdout.strip(), flush=True)
            print("自動検査に合格", flush=True)
            return 0
        if check.returncode != 1 or not check.stdout.strip():
            print("検査器が異常終了しました。", file=sys.stderr)
            return 2

        feedback = check.stdout.strip()
        print("自動検査に失敗:\n" + feedback, flush=True)

    print("試行上限に到達しました。合格した成果物はありません。", file=sys.stderr)
    return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("example_dir", type=Path)
    parser.add_argument("--brief", type=Path, help="今回の題材を記したUTF-8 Markdown")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--seed-file", type=Path, help="生成前に作業先へコピーする既存ファイル")
    parser.add_argument("--check-arg", action="append", default=[], help="検査器へ渡す引数（繰り返し可）")
    args = parser.parse_args()
    try:
        if args.output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="software-factory-")).resolve()
        else:
            output_dir = args.output_dir.resolve()
            output_dir.mkdir()
        if args.seed_file is not None:
            shutil.copyfile(args.seed_file, output_dir / args.seed_file.name)
    except OSError as error:
        print(f"出力先を作成できませんでした: {error}", file=sys.stderr)
        return 2
    return run_factory(args.example_dir.resolve(), output_dir, args.brief, check_args=args.check_arg)


if __name__ == "__main__":
    sys.exit(main())
