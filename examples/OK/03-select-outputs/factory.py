import json
import subprocess
import sys
import tempfile
from pathlib import Path


CANDIDATE_COUNT = 3
EXAMPLES_DIR = Path(__file__).resolve().parents[1]


def main():
    output_dir = Path(tempfile.mkdtemp(prefix="factory-candidates-")).resolve()
    print(f"候補一覧の出力先: {output_dir}", flush=True)
    statuses = {0: "passed", 1: "rejected", 2: "error"}
    candidates = []
    for index in range(1, CANDIDATE_COUNT + 1):
        work_dir = output_dir / f"candidate-{index}"
        log_path = output_dir / f"candidate-{index}.log"
        print(f"候補 {index}/{CANDIDATE_COUNT}: {log_path}", flush=True)
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(
                [sys.executable, str(EXAMPLES_DIR / "factory.py"),
                 str(EXAMPLES_DIR / "02-escape-room"), "--output-dir", str(work_dir)],
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
        candidates.append({
            "status": statuses.get(result.returncode, "error"),
            "output_dir": work_dir.name,
            "log": log_path.name,
        })
        if candidates[-1]["status"] == "error":
            break

    manifest = output_dir / "candidates.json"
    manifest.write_text(json.dumps(candidates, indent=2) + "\n", encoding="utf-8")
    print(f"結果: {manifest}", flush=True)
    if candidates[-1]["status"] == "error":
        return 2
    return 0 if any(candidate["status"] == "passed" for candidate in candidates) else 1


if __name__ == "__main__":
    sys.exit(main())
