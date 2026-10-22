"""거래가 많아지면 어디가 느려지는지 직접 재 보는 스크립트. (테스트가 아니라 측정 도구)

    python tests/benchmark.py                    # 거래 100,000건으로 측정
    python tests/benchmark.py --records 10000    # 건수를 바꿔서 측정

임시 폴더에 가짜 거래 파일을 만들고, 기능마다 걸린 시간과 최대 메모리를 잰다.
시간과 메모리는 따로 잰다 (메모리를 재는 tracemalloc 을 켜면 실행이 몇 배 느려지기 때문).
동료 평가의 "거래가 10만 건으로 늘어나면 병목이 어디인가" 질문에 숫자로 답하기 위한 것이다.
"""

import argparse
import json
import random
import sys
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from budget_app.formatter import display_width  # noqa: E402
from budget_app.models import SearchFilter  # noqa: E402
from budget_app.services import Ledger  # noqa: E402

CATEGORIES = ["food", "transport", "rent", "salary"]


def build_ledger(data_dir: Path, records: int) -> Ledger:
    """카테고리 4개와 거래 records 건이 들어 있는 가계부를 만든다."""
    ledger = Ledger(data_dir)
    ledger.initialize()
    for name in CATEGORIES:
        ledger.categories.add(name)
    random.seed(7)
    with (data_dir / "transactions.jsonl").open("w", encoding="utf-8") as file:
        for number in range(1, records + 1):
            record = {
                "id": f"TX-{number:06d}",
                "type": "income" if number % 20 == 0 else "expense",
                "date": f"{random.randint(2020, 2024)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                "amount": random.randint(1000, 50000),
                "category": random.choice(CATEGORIES),
                "memo": f"메모 {number}",
                "tags": ["a", "b"],
            }
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return ledger


def pad(text: str, width: int) -> str:
    """한글이 섞여도 표가 맞도록 '화면 폭' 기준으로 오른쪽을 공백으로 채운다."""
    return text + " " * (width - display_width(text))


def measure(label: str, func: Callable[[], object]) -> None:
    """func 를 두 번 실행한다: 한 번은 시간만, 한 번은 메모리만 잰다."""
    start = time.perf_counter()
    func()
    seconds = time.perf_counter() - start

    tracemalloc.start()
    func()
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    print(f"{pad(label, 50)} {seconds * 1000:>8.1f} ms {peak / 1024 / 1024:>8.2f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description="가계부 기능별 시간/메모리 측정")
    parser.add_argument("--records", type=int, default=100_000, help="만들 거래 건수 (기본 100000)")
    records = parser.parse_args().records

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        ledger = build_ledger(data_dir, records)
        transactions = ledger.transactions
        repository = transactions.transactions
        size = (data_dir / "transactions.jsonl").stat().st_size
        everything = SearchFilter(date_from="2000-01-01", date_to="2999-12-31")
        one_month = SearchFilter(date_from="2024-05-01", date_to="2024-05-31", category="food")

        print(f"거래 {records:,}건, transactions.jsonl {size / 1024 / 1024:.1f} MB, Python {sys.version.split()[0]}")
        print(f"{pad('기능', 50)} {'시간':>9} {'최대 메모리':>6}")
        print("-" * 74)
        measure("(비교용) 전부 list 로 읽기", lambda: list(repository.stream()))
        measure("list --limit 10", lambda: transactions.list_recent(10))
        measure("search (한 달 + 카테고리), 전부", lambda: transactions.search(one_month))
        measure("search (조건 없음) --limit 10", lambda: transactions.search(SearchFilter(), 10))
        measure("search (조건 없음), 전부  <- 정렬하려고 다 모음", lambda: transactions.search(SearchFilter()))
        measure("summary --month 2024-05", lambda: ledger.budgets.summarize("2024-05", 3))
        measure("export (전체 기간)", lambda: transactions.export_csv(Path(tmp) / "out.csv", everything))
        measure("add 1건  <- id 를 만들려고 전체를 읽음", lambda: transactions.add("2024-06-01", "expense", "food", 1000))
        measure("update 1건  <- 파일 전체를 다시 씀", lambda: transactions.update("TX-000001", memo=str(time.time())))
        victims = iter(range(2, 100))  # 잴 때마다 다른 거래를 지운다
        measure("delete 1건  <- 파일 전체를 다시 씀", lambda: transactions.delete(f"TX-{next(victims):06d}"))
        measure("category remove (사용 중 확인)", lambda: sum(1 for tx in repository.stream() if tx.category == "food"))


if __name__ == "__main__":
    main()
