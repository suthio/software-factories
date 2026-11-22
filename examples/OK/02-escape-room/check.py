import json
import re
import sys
from collections import deque
from pathlib import Path


IDENTIFIER = re.compile(r"[a-z][a-z0-9-]*")
MAX_BYTES = 64 * 1024
MIN_MOVES = 4


def require(condition, message):
    if not condition:
        raise ValueError(message)


def is_text(value):
    return isinstance(value, str) and bool(value.strip())


def is_identifier(value):
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def load_game(path):
    require(path.is_file() and not path.is_symlink(), "通常のファイル game.json が必要です。")
    with path.open("rb") as file:
        content = file.read(MAX_BYTES + 1)
    require(len(content) <= MAX_BYTES, "game.json は64 KiB以下にしてください。")
    try:
        game = json.loads(content.decode("utf-8"))
    except (ValueError, RecursionError):
        raise ValueError("game.json をUTF-8のJSONとして読み込めません。") from None

    require(isinstance(game, dict), "JSONのトップレベルはオブジェクトにしてください。")
    require(is_text(game.get("title")), "title にタイトルを設定してください。")
    rooms = game.get("rooms")
    require(isinstance(rooms, dict) and 5 <= len(rooms) <= 9, "rooms は5〜9部屋にしてください。")

    special_rooms = [game.get(field) for field in ("start", "goal", "key_room")]
    require(all(is_identifier(room) and room in rooms for room in special_rooms),
            "start、goal、key_room には実在する部屋IDを指定してください。")
    require(len(set(special_rooms)) == 3, "開始地点・出口・鍵は別の部屋にしてください。")

    for room_id, room in rooms.items():
        require(is_identifier(room_id), "部屋IDの形式が仕様と違います。")
        require(isinstance(room, dict) and is_text(room.get("description")),
                f"{room_id}: description が必要です。")
        exits = room.get("exits")
        require(isinstance(exits, dict) and len(exits) <= 4,
                f"{room_id}: exits は最大4件のオブジェクトにしてください。")
        for command, edge in exits.items():
            require(is_identifier(command) and command != "quit", f"{room_id}: 移動コマンドが不正です。")
            require(isinstance(edge, dict), f"{room_id}/{command}: 移動先がオブジェクトではありません。")
            target = edge.get("to")
            require(is_identifier(target) and target in rooms, f"{room_id}/{command}: 移動先が存在しません。")
            require(isinstance(edge.get("requires_key"), bool),
                    f"{room_id}/{command}: requires_key は true または false にしてください。")
    return game


def move(game, state, command, collect_key=True):
    room_id, has_key = state
    edge = game["rooms"][room_id]["exits"].get(command)
    if edge is None or (edge["requires_key"] and not has_key):
        return None
    target = edge["to"]
    return target, has_key or (collect_key and target == game["key_room"])


def shortest_escape(game, collect_key=True):
    start = (game["start"], False)
    queue = deque([(start, 0)])
    visited = {start}
    while queue:
        state, distance = queue.popleft()
        if state[0] == game["goal"]:
            return distance
        for command in game["rooms"][state[0]]["exits"]:
            next_state = move(game, state, command, collect_key)
            if next_state is not None and next_state not in visited:
                queue.append((next_state, distance + 1))
                visited.add(next_state)
    return None


def validate(game):
    distance = shortest_escape(game)
    require(distance is not None, "鍵を拾っても出口にたどり着けません。")
    require(shortest_escape(game, collect_key=False) is None, "鍵を拾わずに出口へ行ける経路があります。")
    require(distance >= MIN_MOVES, f"最短{distance}手で脱出できます。{MIN_MOVES}手以上にしてください。")


if __name__ == "__main__":
    try:
        validate(load_game(Path(sys.argv[1]) / "game.json"))
    except ValueError as error:
        print(error)
        sys.exit(1)
    except OSError as error:
        print(error, file=sys.stderr)
        sys.exit(2)
