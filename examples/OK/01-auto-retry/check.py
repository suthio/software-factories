import subprocess
import sys
from pathlib import Path


CHECK_TIMEOUT = 5
CASES = (
    (("120", "80", "50"), 0, b"250\n"),
    (("7", "0", "19", "4"), 0, b"30\n"),
    (("0",), 0, b"0\n"),
    ((), 2, b""),
    (("10", "-2"), 2, b""),
    (("1.5",), 2, b""),
    (("10", "oops"), 2, b""),
)


def check_output(output_dir):
    program = output_dir / "total.py"
    if program.is_symlink() or not program.is_file():
        return ["出力先に通常のファイル total.py を作ってください。"]

    failures = []
    for arguments, expected_status, expected_stdout in CASES:
        label = "total.py " + (" ".join(arguments) if arguments else "（引数なし）")
        try:
            result = subprocess.run(
                [sys.executable, str(program), *arguments],
                cwd=output_dir,
                capture_output=True,
                timeout=CHECK_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{label}: {CHECK_TIMEOUT}秒以内に終了しなかった")
            continue

        if (result.returncode, result.stdout) != (expected_status, expected_stdout):
            failures.append(
                f"{label}: 期待する終了コードは {expected_status}、"
                f"標準出力は {expected_stdout.decode()!r}。"
                f"実際の終了コードは {result.returncode}。"
            )
    return failures


if __name__ == "__main__":
    failures = check_output(Path(sys.argv[1]).resolve())
    if failures:
        print("\n".join(failures))
    sys.exit(1 if failures else 0)
