"""테스트가 함께 쓰는 도구.

- run_cli      : 진짜 프로그램을 새 프로세스로 실행한다 (`python -m budget_app ...`).
                 종료 코드, 화면 출력(stdout), 오류 출력(stderr)을 그대로 확인할 수 있다.
- CliCase      : 테스트마다 빈 임시 저장 폴더를 만들어 주는 기반 클래스.
- seed         : 명세 예시와 비슷한 카테고리 4개 + 거래 7건을 미리 넣는다.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # inner/B2_1
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # 어느 폴더에서 실행해도 budget_app 을 import 할 수 있게

from budget_app.services import Ledger  # noqa: E402  (sys.path 를 고친 뒤에 import 해야 한다)

CATEGORIES = ["food", "transport", "salary", "rent"]

# (날짜, 타입, 카테고리, 금액, 메모, 태그) — 등록 순서대로 TX-000001 ~ TX-000007
TRANSACTIONS = [
    ("2024-01-05", "expense", "rent", 150000, "월세", ["home", "fixed"]),
    ("2024-01-12", "expense", "transport", 20000, "버스 카드", []),
    ("2024-01-14", "income", "salary", 3000000, "월급", []),
    ("2024-01-15", "expense", "food", 15000, "점심", ["meal"]),
    ("2024-01-20", "expense", "food", 30000, "저녁 회식", ["meal", "team"]),
    ("2024-02-01", "expense", "food", 8000, "커피", ["cafe"]),
    ("2024-01-15", "expense", "transport", 5000, "택시", []),  # TX-000004 와 같은 날, 더 늦게 등록
]
# 2024-01 합계: 수입 3,000,000 / 지출 220,000 (rent 150,000 · food 45,000 · transport 25,000)


def run_cli(
    *args: str,
    data_dir: Path | None = None,
    stdin: str = "",
    cwd: Path = ROOT,
) -> "subprocess.CompletedProcess[str]":
    """`python -m budget_app [--data-dir 폴더] <args>` 를 새 프로세스로 실행한다."""
    command = [sys.executable, "-m", "budget_app"]
    if data_dir is not None:
        command += ["--data-dir", str(data_dir)]
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        command + list(args),
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        env=env,
        timeout=60,
    )


def seed(data_dir: Path) -> Ledger:
    """카테고리 4개와 거래 7건을 넣은 가계부를 만든다. (서비스를 직접 불러 빠르게 준비)"""
    ledger = Ledger(data_dir)
    ledger.initialize()
    for name in CATEGORIES:
        ledger.categories.add(name)
    for date, tx_type, category, amount, memo, tags in TRANSACTIONS:
        ledger.transactions.add(date, tx_type, category, amount, memo, tags)  # type: ignore[arg-type]
    return ledger


def read_jsonl(path: Path) -> list[dict]:
    """JSONL 파일을 dict 목록으로 읽는다. (한 줄이라도 JSON 이 아니면 여기서 실패한다)"""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class TempDirCase(unittest.TestCase):
    """테스트마다 새 임시 폴더(self.tmp)와 저장 폴더 경로(self.data)를 준비한다."""

    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = Path(holder.name)
        self.data = self.tmp / "data"


class CliCase(TempDirCase):
    """진짜 프로그램을 실행해 확인하는 테스트의 기반."""

    def cli(self, *args: str, stdin: str = "") -> "subprocess.CompletedProcess[str]":
        return run_cli(*args, data_dir=self.data, stdin=stdin)

    def records(self, name: str = "transactions") -> list[dict]:
        return read_jsonl(self.data / f"{name}.jsonl")

    def assert_ok(self, result: "subprocess.CompletedProcess[str]") -> None:
        """정상 종료: 종료 코드 0, 오류 출력 없음."""
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stderr, "")

    def assert_error(self, result: "subprocess.CompletedProcess[str]", *fragments: str, code: int = 1) -> None:
        """오류 종료: 종료 코드가 0이 아니고, 스택트레이스 없이 [오류]+[힌트]가 stderr 에 나온다."""
        self.assertEqual(result.returncode, code, msg=result.stdout + result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("[오류]", result.stderr)
        self.assertIn("[힌트]", result.stderr)
        self.assertNotIn("Traceback", result.stderr + result.stdout)
        for fragment in fragments:
            self.assertIn(fragment, result.stderr)
