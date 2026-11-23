import json
import sys
from pathlib import Path


def load_plan(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError("通常のファイル plan.json が必要です。")
    with path.open("rb") as file:
        content = file.read(16 * 1024 + 1)
    if len(content) > 16 * 1024:
        raise ValueError("plan.json は16 KiB以下にしてください。")
    try:
        plan = json.loads(content.decode("utf-8"))
    except (ValueError, RecursionError):
        raise ValueError("plan.json はUTF-8のJSONにしてください。") from None
    if not isinstance(plan, dict) or set(plan) != {"workflow", "storage", "interface"}:
        raise ValueError("workflow・storage・interface の3項目が必要です。")
    if not all(isinstance(value, str) and value.strip() for value in plan.values()):
        raise ValueError("各項目には空でない文字列を書いてください。")
    return plan


if __name__ == "__main__":
    try:
        load_plan(Path(sys.argv[1]) / "plan.json")
    except ValueError as error:
        print(error)
        sys.exit(1)
