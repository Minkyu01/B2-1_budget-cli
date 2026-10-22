"""budget_app 의 함수·클래스·상수 정의 줄 번호를 lines.js 로 만든다.

흐름 탐색기의 코드 칩이 VS Code 에서 그 줄을 바로 열 수 있게 하려는 것이다.
메서드는 'TransactionService.add' 처럼 클래스 이름을 붙여서도 찾을 수 있다.
FX.kinds 에는 종류(def · prop · class · const)를 적어, 코드 칩이 함수에만 () 를 붙이게 한다.
코드가 바뀌면 다시 돌린다:  python3 tools/gen_lines.py
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # docs/flow-explorer
ROOT = HERE.parent.parent                      # inner/B2_1

DEF = re.compile(r"^(\s*)(?:async\s+)?def\s+(\w+)")
CLASS = re.compile(r"^class\s+(\w+)")
CONST = re.compile(r"^([A-Z][A-Za-z0-9_]*)\s*(?::[^=]+)?=\s*")


def main() -> None:
    lines: dict[str, int] = {}
    kinds: dict[str, str] = {}

    def put(key: str, number: int, kind: str) -> None:
        if key not in lines:
            lines[key] = number
            kinds[key] = kind
    for folder in ("budget_app", "tests", "docs"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            current_class = None
            previous = ""
            for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if match := CLASS.match(text):
                    current_class = match.group(1)
                    put(f"{rel}#{current_class}", number, "class")
                elif match := DEF.match(text):
                    indent, name = match.groups()
                    kind = "prop" if previous.strip() == "@property" else "def"
                    if not indent:
                        current_class = None
                    elif current_class:
                        put(f"{rel}#{current_class}.{name}", number, kind)
                    put(f"{rel}#{name}", number, kind)
                elif match := CONST.match(text):
                    current_class = None
                    put(f"{rel}#{match.group(1)}", number, "const")
                elif text and not text[0].isspace() and not text.startswith(("#", "@", ")")):
                    current_class = None
                if text.strip():
                    previous = text
    body = json.dumps(lines, ensure_ascii=False, indent=0, sort_keys=True)
    out = HERE / "lines.js"
    out.write_text(
        "/* tools/gen_lines.py 가 만든 파일 — 직접 고치지 않는다 */\n"
        "window.FX = window.FX || {};\n"
        f"FX.repoRoot = {json.dumps(str(ROOT))};\n"
        f"FX.lines = {body};\n"
        f"FX.kinds = {json.dumps(kinds, ensure_ascii=False, sort_keys=True)};\n",
        encoding="utf-8",
    )
    print(f"{len(lines)} definitions → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
