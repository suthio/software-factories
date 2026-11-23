import sys
from pathlib import Path

from check import load_game, move, validate


def play(game):
    state = (game["start"], False)
    print(game["title"])
    while True:
        room_id, has_key = state
        room = game["rooms"][room_id]
        print("\n" + room["description"])
        if room_id == game["goal"]:
            print("脱出成功！")
            return

        commands = ", ".join(room["exits"]) or "なし"
        while True:
            print(f"移動: {commands} / quit")
            try:
                command = input("> ").strip()
            except EOFError:
                return
            if command == "quit":
                return
            next_state = move(game, state, command)
            if next_state is None:
                print("その方向には進めません。")
                continue
            if next_state[1] and not has_key:
                print("鍵を見つけた！")
            state = next_state
            break


if __name__ == "__main__":
    try:
        game = load_game(Path(sys.argv[1]))
        validate(game)
    except (OSError, ValueError) as error:
        sys.exit(str(error))
    play(game)
