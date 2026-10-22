"""스트리밍 테스트 — "파일 전체를 한 번에 로드하지 않는다"를 메모리 사용량으로 직접 확인한다.

거래 20,000건(약 3MB)짜리 파일을 만들어 놓고, 각 기능이 쓰는 최대 메모리(peak)를 tracemalloc 으로 잰다.
    - 전부 list 로 읽으면            : 10MB 이상
    - list / search --limit / summary : 0.5MB 미만  (파일 크기와 상관없이 일정)

대괄호 번호는 project.md 의 조항 번호다.
"""

import json
import random
import tracemalloc
import unittest
from collections.abc import Callable
from pathlib import Path

from helpers import TempDirCase
from budget_app.models import SearchFilter
from budget_app.services import Ledger

RECORDS = 20_000
SMALL = 512 * 1024        # 0.5MB
LOAD_ALL_AT_LEAST = 5 * 1024 * 1024  # 5MB


def peak_memory(func: Callable[[], object]) -> int:
    """func 를 실행하는 동안 파이썬이 새로 잡은 메모리의 최대치(바이트)."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class StreamingMemoryTests(TempDirCase):
    ledger: Ledger

    def setUp(self) -> None:
        super().setUp()
        self.ledger = Ledger(self.data)
        self.ledger.initialize()
        for name in ["food", "transport", "rent"]:
            self.ledger.categories.add(name)
        random.seed(7)
        with (self.data / "transactions.jsonl").open("w", encoding="utf-8") as file:
            for number in range(1, RECORDS + 1):
                record = {
                    "id": f"TX-{number:06d}",
                    "type": "expense",
                    "date": f"2023-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                    "amount": random.randint(1000, 50000),
                    "category": random.choice(["food", "transport", "rent"]),
                    "memo": f"메모 {number}",
                    "tags": ["a", "b"],
                }
                file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def test_loading_everything_is_expensive(self) -> None:
        """비교 기준: 전부 list 로 읽으면 파일 크기에 비례해 메모리를 쓴다"""
        repository = self.ledger.transactions.transactions
        self.assertGreater(peak_memory(lambda: list(repository.stream())), LOAD_ALL_AT_LEAST)

    def test_list_keeps_only_limit_records(self) -> None:
        """[4.5] list 는 파일 전체를 올리지 않는다 — 메모리에는 --limit 건만 남는다"""
        result: list = []
        peak = peak_memory(lambda: result.extend(self.ledger.transactions.list_recent(10)))
        self.assertEqual(len(result), 10)
        self.assertLess(peak, SMALL)
        dates = [tx.date for tx in result]
        self.assertEqual(dates, sorted(dates, reverse=True))  # 그러면서도 최신순은 정확하다

    def test_search_with_limit_is_bounded(self) -> None:
        """[4.7] search 도 스트리밍을 유지한다"""
        condition = SearchFilter(category="food", date_from="2023-03-01")
        peak = peak_memory(lambda: self.ledger.transactions.search(condition, 10))
        self.assertLess(peak, SMALL)

    def test_search_without_limit_holds_only_matches(self) -> None:
        """[4.7] --limit 이 없으면 '조건에 맞은 거래'만 모은다 (파일 전체가 아니다)"""
        one_day = SearchFilter(date_from="2023-05-10", date_to="2023-05-10")
        found: list = []
        peak = peak_memory(lambda: found.extend(self.ledger.transactions.search(one_day)))
        self.assertGreater(len(found), 10)
        self.assertLess(len(found), RECORDS // 100)
        self.assertLess(peak, SMALL)

    def test_summary_is_bounded(self) -> None:
        """[4.8] summary 는 합계와 카테고리별 소계만 들고 있는다"""
        self.assertLess(peak_memory(lambda: self.ledger.budgets.summarize("2023-05", 3)), SMALL)

    def test_export_streams_to_the_file(self) -> None:
        """[4.11] export 는 읽기 → 거르기 → 쓰기가 한 건씩 흐른다"""
        out = Path(self.tmp) / "all.csv"
        everything = SearchFilter(date_from="2023-01-01", date_to="2023-12-31")
        count: list[int] = []
        peak = peak_memory(lambda: count.append(self.ledger.transactions.export_csv(out, everything)))
        self.assertEqual(count, [RECORDS])
        self.assertLess(peak, 2 * SMALL)


if __name__ == "__main__":
    unittest.main()
