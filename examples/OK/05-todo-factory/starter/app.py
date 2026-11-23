import argparse
import html
import json
import re
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def render(tasks):
    rows = []
    for task in tasks:
        task_id = task["id"]
        done = str(task["done"]).lower()
        title = html.escape(task["title"])
        action = "未完了に戻す" if task["done"] else "完了にする"
        label = "完了" if task["done"] else "未完了"
        rows.append(f"""
<li data-task-id="{task_id}" data-done="{done}">
  {title}（{label}）
  <form method="post" action="/tasks/{task_id}/toggle"><button>{action}</button></form>
  <form method="post" action="/tasks/{task_id}/delete"><button>削除</button></form>
</li>""")
    return f"""<!doctype html>
<html lang="ja">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>今日やること</title>
<style>
body {{ max-width: 40rem; margin: 2rem auto; padding: 0 1rem; font: 1rem/1.6 system-ui, sans-serif; }}
li {{ margin: .75rem 0; }}
li form {{ display: inline-block; }}
</style>
<main>
  <h1>今日やること</h1>
  <form method="post" action="/tasks">
    <label>タスク <input name="title" required></label>
    <button>追加</button>
  </form>
  <ul>{"".join(rows)}</ul>
</main>
</html>""".encode("utf-8")


class TodoHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, data_file, **kwargs):
        self.data_file = data_file
        super().__init__(*args, **kwargs)

    def load_tasks(self):
        if not self.data_file.exists():
            return []
        return json.loads(self.data_file.read_text(encoding="utf-8"))

    def do_GET(self):
        if urlsplit(self.path).path != "/":
            self.send_error(404)
            return
        body = render(self.load_tasks())
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlsplit(self.path).path
        tasks = self.load_tasks()
        if path == "/tasks":
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 8192:
                self.send_error(400)
                return
            form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            title = form.get("title", [""])[0].strip()
            if not title:
                self.send_error(400)
                return
            task_id = max((task["id"] for task in tasks), default=0) + 1
            tasks.append({"id": task_id, "title": title, "done": False})
        else:
            match = re.fullmatch(r"/tasks/([0-9]+)/(toggle|delete)", path)
            if not match:
                self.send_error(404)
                return
            task = next((item for item in tasks if str(item["id"]) == match[1]), None)
            if task is None:
                self.send_error(404)
                return
            if match[2] == "toggle":
                task["done"] = not task["done"]
            else:
                tasks.remove(task)
        temporary = self.data_file.with_name(self.data_file.name + ".tmp")
        temporary.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.data_file)
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data", type=Path, default=Path("todos.json"))
    parser.add_argument("--ready-file", type=Path)
    args = parser.parse_args()
    handler = partial(TodoHandler, data_file=args.data)
    with HTTPServer(("127.0.0.1", args.port), handler) as server:
        if args.ready_file:
            args.ready_file.write_text(str(server.server_port), encoding="ascii")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
