import random
import subprocess
import sys
from pathlib import Path


def cases():
    yield [(0, 8), (13, 0), (3, 4)], None
    yield [], None
    generator = random.Random(413858)
    for _ in range(16):
        rows = [(generator.randint(0, 100_000), generator.randint(0, 500))
                for _ in range(generator.randint(1, 15))]
        yield rows, None
    for invalid in ("price,quantity\n-1,3\n", "price,quantity\n1.5,3\n",
                    "price,quantity\n1,2,3\n", "cost,quantity\n1,2\n"):
        yield [], invalid


def check(output):
    program = output / "invoice.py"
    if not program.is_file() or program.is_symlink():
        return "通常のファイル invoice.py が必要です。"
    for rows, invalid in cases():
        csv_text = invalid or "price,quantity\n" + "".join(f"{price},{count}\n" for price, count in rows)
        expected = (2, b"") if invalid else (0, f"{sum(price * count for price, count in rows)}\n".encode())
        try:
            result = subprocess.run([sys.executable, str(program)], input=csv_text.encode(),
                                    cwd=output, capture_output=True, timeout=2)
        except subprocess.TimeoutExpired:
            return "invoice.py が2秒以内に終了しませんでした。"
        if (result.returncode, result.stdout) != expected:
            return f"反例: 入力CSV={csv_text!r}。期待する終了コードと標準出力は {expected!r} です。"
    return None


if __name__ == "__main__":
    failure = check(Path(sys.argv[1]).resolve())
    print(failure or "検査用の参照計算と全ケースで一致しました。")
    sys.exit(int(failure is not None))
