import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class TodoPage(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.items = {}
        self.forms = set()
        self.links = set()
        self.remaining_counts = []
        self.title_input = False
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "li" and "data-task-id" in values:
            self.items[values["data-task-id"]] = values.get("data-done")
        if tag == "form" and (values.get("method") or "").lower() == "post":
            self.forms.add(values.get("action"))
        if tag == "input" and values.get("name") == "title":
            self.title_input = True
        if tag == "a":
            self.links.add(values.get("href"))
        if "data-remaining-count" in values:
            self.remaining_counts.append(values["data-remaining-count"])


def require(condition, message):
    if not condition:
        raise ValueError(message)


@contextlib.contextmanager
def serve(program, state):
    ready = state / "ready"
    ready.unlink(missing_ok=True)
    with (state / "server.log").open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, str(program), "--port", "0", "--data", str(state / "todos.json"),
             "--ready-file", str(ready)],
            cwd=state, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            env={"PATH": os.defpath, "HOME": str(state), "TMPDIR": str(state)},
        )
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                require(process.poll() is None, "サーバーが起動前に終了しました。起動引数を確認してください。")
                if ready.is_file():
                    content = ready.read_bytes()[:16].strip()
                    if content.isdigit() and 1 <= int(content) <= 65535:
                        yield f"http://127.0.0.1:{int(content)}"
                        return
                time.sleep(0.05)
            raise ValueError("5秒以内に --ready-file へポート番号が書き込まれませんでした。")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)


def request(base, path, data=None):
    encoded = None if data is None else urlencode(data).encode("ascii")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        response = opener.open(base + path, data=encoded, timeout=2)
    except HTTPError as error:
        response = error
    except (URLError, TimeoutError):
        raise ValueError(f"{path} に2秒以内に接続できませんでした。") from None
    with response:
        return response.code, response.headers, response.read(1_048_576).decode("utf-8")


def page(base, path="/"):
    status, headers, body = request(base, path)
    require(status == 200 and headers.get_content_type() == "text/html", f"GET {path} はHTMLをHTTP 200で返してください。")
    return TodoPage(body), body


def update(base, path, data):
    status, headers, _ = request(base, path, data)
    require(status == 303 and headers.get("Location") == "/", f"POST {path} は303と Location: / を返してください。")


def verify(program, state):
    with serve(program, state) as base:
        initial, _ = page(base)
        require(not initial.items and "/tasks" in initial.forms and initial.title_input,
                "新規画面には title 入力と POST /tasks のフォームが必要です。")
        status, _, _ = request(base, "/tasks", {"title": "   "})
        require(status == 400 and not page(base)[0].items, "空白のTODOは追加せず400を返してください。")
        update(base, "/tasks", {"title": "買い物 <牛乳> & パン"})
        created, body = page(base)
        require(len(created.items) == 1 and "買い物 &lt;牛乳&gt; &amp; パン" in body and "<牛乳>" not in body,
                "追加したタイトルを一覧に出し、< や & はHTML用にエスケープしてください。")
        task_id, done = next(iter(created.items.items()))
        require(task_id is not None and task_id.isascii() and task_id.isdigit() and task_id.lstrip("0") and done == "false",
                "追加直後は正の整数IDと data-done=false が必要です。")
        toggle, delete = f"/tasks/{task_id}/toggle", f"/tasks/{task_id}/delete"
        require({toggle, delete} <= created.forms, "画面にこのTODOの切り替え・削除フォームがありません。")
        update(base, "/tasks", {"title": "図書館に本を返す"})
        with_second, body = page(base)
        require(len(with_second.items) == 2 and task_id in with_second.items and "図書館に本を返す" in body,
                "二件目は一件目を置き換えず、別のIDで追加してください。")
        other_id = next(item_id for item_id in with_second.items if item_id != task_id)
        update(base, toggle, {})
        require(page(base)[0].items == {task_id: "true", other_id: "false"},
                "切り替えたTODOだけを完了にし、もう一件は未完了のままにしてください。")
    with serve(program, state) as base:
        saved, body = page(base)
        require(saved.items.get(task_id) == "true" and "買い物 &lt;牛乳&gt; &amp; パン" in body,
                "再起動後もタイトルと完了状態を残してください。")
        update(base, toggle, {})
        require(page(base)[0].items.get(task_id) == "false", "完了から未完了にも切り替えられる必要があります。")
        update(base, delete, {})
        require(page(base)[0].items == {other_id: "false"}, "一覧から指定したTODOだけを削除してください。")
    with serve(program, state) as base:
        require(page(base)[0].items == {other_id: "false"}, "再起動後も削除していないTODOだけを残してください。")


def check_http(program, verify_behavior):
    with tempfile.TemporaryDirectory(prefix="todo-check-") as temporary:
        state = Path(temporary)
        candidate = state / "app.py"
        shutil.copyfile(program, candidate)
        verify_behavior(candidate, state)


def verify_filter(program, state):
    with serve(program, state) as base:
        update(base, "/tasks", {"title": "牛乳を買う"})
        created, _ = page(base)
        require(len(created.items) == 1, "絞り込みの検査には追加したTODOが一覧に必要です。")
        done_id = next(iter(created.items))
        update(base, f"/tasks/{done_id}/toggle", {})
        update(base, "/tasks", {"title": "本を返す"})
        all_items, _ = page(base)
        require(len(all_items.items) == 2 and done_id in all_items.items,
                "すべての一覧には完了と未完了の両方を表示してください。")
        pending_id = next(task_id for task_id in all_items.items if task_id != done_id)
        require({"/", "/?status=active", "/?status=completed"} <= all_items.links,
                "一覧に「すべて」「未完了」「完了」のリンクを用意してください。")
        require(page(base, "/?status=active")[0].items == {pending_id: "false"},
                "未完了の絞り込みには未完了のTODOだけを表示してください。")
        require(page(base, "/?status=completed")[0].items == {done_id: "true"},
                "完了の絞り込みには完了したTODOだけを表示してください。")


def verify_remaining(program, state):
    with serve(program, state) as base:
        require(page(base)[0].remaining_counts == ["0"], "空の一覧の未完了件数は0です。")
        update(base, "/tasks", {"title": "牛乳を買う"})
        created, _ = page(base)
        require(len(created.items) == 1, "件数の検査には追加したTODOが一覧に必要です。")
        first_id = next(iter(created.items))
        update(base, "/tasks", {"title": "本を返す"})
        require(page(base)[0].remaining_counts == ["2"], "2件追加したあとの未完了件数は2です。")
        update(base, f"/tasks/{first_id}/toggle", {})
        require(page(base)[0].remaining_counts == ["1"], "1件を完了にしたあとの未完了件数は1です。")
        update(base, f"/tasks/{first_id}/toggle", {})
        require(page(base)[0].remaining_counts == ["2"], "未完了に戻したあとの未完了件数は2です。")
        update(base, f"/tasks/{first_id}/delete", {})
        require(page(base)[0].remaining_counts == ["1"], "未完了の1件を削除したあとの未完了件数は1です。")


ACCEPTANCE = {"status-filter": verify_filter, "remaining-count": verify_remaining}


def main():
    program = Path(sys.argv[1]).resolve() / "app.py"
    try:
        require(program.is_file() and not program.is_symlink(), "通常のファイル app.py が必要です。")
    except ValueError as error:
        print(error)
        return 1

    lint = subprocess.run(
        ["uvx", "ruff@0.15.0", "check", "--isolated", "--ignore-noqa", "--no-cache",
         "--select", "E4,E7,E9,F", "--output-format", "concise", "--stdin-filename", "app.py", "-"],
        input=program.read_bytes(), stdout=subprocess.PIPE, check=False,
    )
    if lint.returncode == 1 and lint.stdout.strip():
        print("コード検査 Ruff: 不合格\n" + lint.stdout.decode("utf-8"))
        print("HTTP検査: スキップ（コード検査を通ってから実行）")
        return 1
    if lint.returncode != 0:
        print("Ruffを実行できませんでした。", file=sys.stderr)
        return 2
    print("コード検査 Ruff: 合格")

    failed = False
    for label, verifier in [("基本動作", verify), *((key, ACCEPTANCE[key]) for key in sys.argv[2:])]:
        try:
            check_http(program, verifier)
        except ValueError as error:
            print(f"HTTP検査 {label}: 不合格 — {error}")
            failed = True
        else:
            print(f"HTTP検査 {label}: 合格")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
