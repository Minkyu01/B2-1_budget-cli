"""서비스 계층 테스트 — 업무 규칙. (화면 없이 서비스를 직접 부른다)

대괄호 번호는 project.md 의 조항 번호다.
"""

import csv
import unittest
import zipfile
from pathlib import Path

from helpers import CATEGORIES, TRANSACTIONS, TempDirCase, read_jsonl, seed
from budget_app.errors import AppError, NotFoundError, ValidationError
from budget_app.models import SearchFilter, Transaction
from budget_app.services import Ledger, newest_first


class SeededCase(TempDirCase):
    def setUp(self) -> None:
        super().setUp()
        self.ledger = seed(self.data)

    def ids(self, transactions: list[Transaction]) -> list[str]:
        return [tx.id for tx in transactions]


class LedgerTests(TempDirCase):
    def test_initialize_creates_three_or_more_files(self) -> None:
        """[4.3] 저장 파일은 3개 이상 — transactions / categories / budgets"""
        ledger = Ledger(self.data)
        created = ledger.initialize()
        names = sorted(path.name for path in created)
        self.assertEqual(names, ["budgets.jsonl", "categories.jsonl", "recurring.jsonl", "transactions.jsonl"])
        self.assertGreaterEqual(len(list(self.data.glob("*.jsonl"))), 3)
        self.assertEqual(ledger.initialize(), [])  # 두 번째 실행에서는 새로 만드는 것이 없다

    def test_data_survives_a_new_ledger_object(self) -> None:
        """[4.3] 프로그램을 다시 실행해도(새 객체) 데이터가 유지된다"""
        seed(self.data).budgets.set_budget("2024-01", 500000)
        again = Ledger(self.data)
        self.assertEqual(len(again.transactions.list_recent(100)), len(TRANSACTIONS))
        self.assertEqual([c.name for c in again.categories.list_all()], sorted(CATEGORIES))
        self.assertEqual(again.budgets.list_all()[0].amount, 500000)

    def test_backup(self) -> None:
        """[5-1] backup 은 저장 파일 전체를 zip 하나로 묶는다"""
        ledger = seed(self.data)
        path = ledger.backup()
        self.assertEqual(path.parent, self.data / "backups")
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(
                sorted(archive.namelist()),
                ["budgets.jsonl", "categories.jsonl", "recurring.jsonl", "transactions.jsonl"],
            )
            self.assertEqual(archive.read("transactions.jsonl"), (self.data / "transactions.jsonl").read_bytes())


class AddTests(TempDirCase):
    def test_add_is_blocked_without_categories(self) -> None:
        """[4.3] 카테고리가 비어 있으면 category add 를 안내하고 add 를 막는다 (안 B)"""
        ledger = Ledger(self.data)
        ledger.initialize()
        with self.assertRaises(AppError) as caught:
            ledger.transactions.add("2024-01-15", "expense", "food", 15000)
        self.assertIn("category add", caught.exception.hint)
        self.assertEqual(read_jsonl(self.data / "transactions.jsonl"), [])
        self.assertEqual(read_jsonl(self.data / "categories.jsonl"), [])  # 기본 카테고리를 몰래 만들지 않는다

    def test_add_assigns_unique_sequential_ids(self) -> None:
        """[4.2][4.4] id 는 유일하고, 저장 후 돌려준다"""
        ledger = seed(self.data)
        ids = [tx["id"] for tx in read_jsonl(self.data / "transactions.jsonl")]
        self.assertEqual(ids, [f"TX-{n:06d}" for n in range(1, 8)])
        new = ledger.transactions.add("2024-03-01", "expense", "food", 1000)
        self.assertEqual(new.id, "TX-000008")
        self.assertEqual(len(set(ids + [new.id])), 8)

    def test_add_rejects_unregistered_category(self) -> None:
        """[4.4] category 는 등록된 목록에 있어야 한다"""
        ledger = seed(self.data)
        with self.assertRaises(ValidationError) as caught:
            ledger.transactions.add("2024-01-15", "expense", "cafe", 4500)
        self.assertIn("cafe", caught.exception.message)
        self.assertIn("food", caught.exception.hint)  # 등록된 카테고리를 알려 준다
        self.assertEqual(len(read_jsonl(self.data / "transactions.jsonl")), len(TRANSACTIONS))

    def test_add_rejects_invalid_values(self) -> None:
        """[4.2] 서비스로 직접 잘못된 값을 넘겨도 저장되지 않는다"""
        ledger = seed(self.data)
        for args in [("2024-13-40", "expense", "food", 1), ("2024-01-15", "spend", "food", 1),
                     ("2024-01-15", "expense", "food", 0), ("2024-01-15", "expense", "food", -5)]:
            with self.subTest(args=args), self.assertRaises(ValidationError):
                ledger.transactions.add(*args)  # type: ignore[arg-type]
        self.assertEqual(len(read_jsonl(self.data / "transactions.jsonl")), len(TRANSACTIONS))


class ListSearchTests(SeededCase):
    def test_list_recent_is_newest_first(self) -> None:
        """[4.5] 최신순 = 날짜가 늦은 것 먼저, 같은 날이면 나중에 등록한 것 먼저"""
        self.assertEqual(
            self.ids(self.ledger.transactions.list_recent(100)),
            ["TX-000006", "TX-000005", "TX-000007", "TX-000004", "TX-000003", "TX-000002", "TX-000001"],
        )

    def test_list_recent_limit(self) -> None:
        """[4.5] --limit N"""
        self.assertEqual(self.ids(self.ledger.transactions.list_recent(3)), ["TX-000006", "TX-000005", "TX-000007"])
        self.assertEqual(len(self.ledger.transactions.list_recent(1)), 1)

    def test_newest_first_orders_by_number_not_by_text(self) -> None:
        """같은 날짜에서는 id 의 '번호'로 비교한다 (TX-1000000 이 TX-999999 보다 나중)"""
        older = Transaction(id="TX-999999", type="expense", date="2024-01-15", amount=1, category="food")
        newer = Transaction(id="TX-1000000", type="expense", date="2024-01-15", amount=1, category="food")
        self.assertEqual(self.ids(newest_first(iter([newer, older]), 2)), ["TX-1000000", "TX-999999"])
        self.assertEqual(self.ids(newest_first(iter([older, newer]), None)), ["TX-1000000", "TX-999999"])

    def test_matching_is_a_generator(self) -> None:
        """[4.7] 검색도 제너레이터로 흘려보낸다"""
        matched = self.ledger.transactions.matching(SearchFilter(category="food"))
        self.assertNotIsInstance(matched, (list, tuple))
        self.assertEqual(next(matched).id, "TX-000004")  # 파일에 적힌 순서대로 하나씩

    def test_search_conditions(self) -> None:
        """[4.7] 기간 / 카테고리 / 타입 / 메모 키워드 / 태그 — 결과는 최신순"""
        search = self.ledger.transactions.search
        cases = [
            (SearchFilter(date_from="2024-01-13", date_to="2024-01-15"), ["TX-000007", "TX-000004", "TX-000003"]),
            (SearchFilter(date_from="2024-01-20"), ["TX-000006", "TX-000005"]),
            (SearchFilter(date_to="2024-01-05"), ["TX-000001"]),
            (SearchFilter(category="food"), ["TX-000006", "TX-000005", "TX-000004"]),
            (SearchFilter(type="income"), ["TX-000003"]),
            (SearchFilter(keyword="회식"), ["TX-000005"]),
            (SearchFilter(tag="meal"), ["TX-000005", "TX-000004"]),
            (SearchFilter(category="food", tag="meal", date_to="2024-01-15"), ["TX-000004"]),
            (SearchFilter(category="rent", type="income"), []),
        ]
        for condition, expected in cases:
            with self.subTest(condition=condition):
                self.assertEqual(self.ids(search(condition)), expected)

    def test_search_limit(self) -> None:
        """[4.7] search 에 limit 을 주면 최신순으로 그만큼만"""
        self.assertEqual(self.ids(self.ledger.transactions.search(SearchFilter(category="food"), 2)),
                         ["TX-000006", "TX-000005"])


class UpdateDeleteTests(SeededCase):
    def test_update_changes_only_given_fields(self) -> None:
        """[4.6] update: 준 항목만 바뀌고 나머지와 줄 순서는 그대로"""
        updated = self.ledger.transactions.update("TX-000004", amount=18000, memo="점심 + 커피")
        self.assertEqual((updated.amount, updated.memo), (18000, "점심 + 커피"))
        self.assertEqual((updated.date, updated.type, updated.category, updated.tags),
                         ("2024-01-15", "expense", "food", ["meal"]))
        records = read_jsonl(self.data / "transactions.jsonl")
        self.assertEqual([r["id"] for r in records], [f"TX-{n:06d}" for n in range(1, 8)])
        self.assertEqual(records[3]["amount"], 18000)

    def test_update_every_field(self) -> None:
        """[4.6] 모든 항목을 한 번에 수정 (id 는 줄여 써도 된다)"""
        updated = self.ledger.transactions.update(
            "tx-4", date="2024-02-10", type="income", category="salary", amount=5, memo="", tags=[]
        )
        self.assertEqual(
            updated,
            Transaction(id="TX-000004", type="income", date="2024-02-10", amount=5, category="salary"),
        )

    def test_update_missing_id(self) -> None:
        """[4.6] 없는 id 는 '없는 데이터'로 처리한다"""
        with self.assertRaises(NotFoundError) as caught:
            self.ledger.transactions.update("TX-000099", amount=1)
        self.assertIn("없는 데이터", caught.exception.message)

    def test_update_rejects_bad_values_and_keeps_file(self) -> None:
        """[4.6] 잘못된 수정은 거부하고 파일은 한 바이트도 바뀌지 않는다"""
        before = (self.data / "transactions.jsonl").read_bytes()
        with self.assertRaises(ValidationError):
            self.ledger.transactions.update("TX-000004", category="cafe")  # 등록되지 않은 카테고리
        with self.assertRaises(ValidationError):
            self.ledger.transactions.update("TX-000004", amount=-1)
        with self.assertRaises(ValidationError):
            self.ledger.transactions.update("TX-000004", date="2024-02-30")
        with self.assertRaises(ValidationError):
            self.ledger.transactions.update("TX-000004")  # 바꿀 것이 없음
        with self.assertRaises(ValidationError):
            self.ledger.transactions.update("TX-000004", amount=15000)  # 기존과 같은 값
        self.assertEqual((self.data / "transactions.jsonl").read_bytes(), before)

    def test_delete(self) -> None:
        """[4.6] delete --id"""
        deleted = self.ledger.transactions.delete("TX-000002")
        self.assertEqual(deleted.memo, "버스 카드")
        self.assertNotIn("TX-000002", [r["id"] for r in read_jsonl(self.data / "transactions.jsonl")])
        self.assertEqual(len(read_jsonl(self.data / "transactions.jsonl")), len(TRANSACTIONS) - 1)

    def test_delete_missing_id(self) -> None:
        """[4.6] 없는 id 는 '없는 데이터'로 처리한다"""
        before = (self.data / "transactions.jsonl").read_bytes()
        with self.assertRaises(NotFoundError) as caught:
            self.ledger.transactions.delete("TX-000099")
        self.assertIn("없는 데이터", caught.exception.message)
        self.assertEqual((self.data / "transactions.jsonl").read_bytes(), before)

    def test_malformed_id(self) -> None:
        """[4.6] id 모양이 아니면 검증 오류"""
        with self.assertRaises(ValidationError):
            self.ledger.transactions.delete("12")


class CategoryTests(SeededCase):
    def test_add_and_list(self) -> None:
        """[4.10] category add / list"""
        self.ledger.categories.add(" Cafe ")
        self.assertEqual([c.name for c in self.ledger.categories.list_all()],
                         ["cafe", "food", "rent", "salary", "transport"])

    def test_add_duplicate(self) -> None:
        """[4.10] 이미 있는 카테고리는 다시 추가할 수 없다 (대소문자 무시)"""
        with self.assertRaises(AppError) as caught:
            self.ledger.categories.add("FOOD")
        self.assertIn("이미 등록", caught.exception.message)
        self.assertEqual(len(read_jsonl(self.data / "categories.jsonl")), len(CATEGORIES))

    def test_remove_is_blocked_while_in_use(self) -> None:
        """[4.10] 사용 중인 카테고리는 삭제를 막는다"""
        with self.assertRaises(AppError) as caught:
            self.ledger.categories.remove("food")
        self.assertIn("사용 중", caught.exception.message)
        self.assertIn("거래 3건", caught.exception.message)
        self.assertIn("food", [c.name for c in self.ledger.categories.list_all()])

    def test_remove_unused(self) -> None:
        """[4.10] category remove"""
        self.ledger.categories.add("cafe")
        self.assertEqual(self.ledger.categories.remove("cafe").name, "cafe")
        self.assertNotIn("cafe", [c.name for c in self.ledger.categories.list_all()])

    def test_remove_after_transactions_are_gone(self) -> None:
        """[4.10] 쓰던 거래를 지우고 나면 카테고리도 지울 수 있다"""
        self.ledger.transactions.delete("TX-000001")  # rent 를 쓰는 유일한 거래
        self.ledger.categories.remove("rent")
        self.assertNotIn("rent", [c.name for c in self.ledger.categories.list_all()])

    def test_remove_missing(self) -> None:
        """[4.10] 없는 카테고리 삭제는 '없는 데이터'"""
        with self.assertRaises(NotFoundError):
            self.ledger.categories.remove("nothing")

    def test_remove_is_blocked_by_recurring_rule(self) -> None:
        """[4.10][5-2] 반복 규칙이 쓰는 카테고리도 삭제를 막는다"""
        self.ledger.categories.add("gym")
        self.ledger.recurring.add(10, "expense", "gym", 50000)
        with self.assertRaises(AppError) as caught:
            self.ledger.categories.remove("gym")
        self.assertIn("반복 규칙 1건", caught.exception.message)


class BudgetSummaryTests(SeededCase):
    def test_summary_totals(self) -> None:
        """[4.8] 총수입 / 총지출 / 잔액 / 카테고리별 지출 TOP N"""
        summary = self.ledger.budgets.summarize("2024-01", top=3)
        self.assertEqual((summary.income, summary.expense, summary.balance), (3000000, 220000, 2780000))
        self.assertEqual(summary.count, 6)
        self.assertEqual(summary.top_categories, [("rent", 150000), ("food", 45000), ("transport", 25000)])
        self.assertIsNone(summary.budget)

    def test_summary_top_n(self) -> None:
        """[4.8] --top"""
        self.assertEqual(self.ledger.budgets.summarize("2024-01", top=1).top_categories, [("rent", 150000)])
        self.assertEqual(len(self.ledger.budgets.summarize("2024-01", top=10).top_categories), 3)

    def test_summary_tie_is_ordered_by_name(self) -> None:
        """[4.8] 지출 금액이 같으면 이름순 (실행할 때마다 같은 순서)"""
        self.ledger.transactions.add("2024-05-01", "expense", "transport", 100)
        self.ledger.transactions.add("2024-05-02", "expense", "food", 100)
        self.assertEqual(self.ledger.budgets.summarize("2024-05", top=3).top_categories,
                         [("food", 100), ("transport", 100)])

    def test_summary_of_empty_month(self) -> None:
        """[4.8] 데이터가 없는 달"""
        summary = self.ledger.budgets.summarize("2023-05", top=3)
        self.assertEqual((summary.count, summary.income, summary.expense, summary.top_categories), (0, 0, 0, []))

    def test_budget_set_is_persisted_and_replaced(self) -> None:
        """[4.9] 예산은 영구 저장되고, 같은 달에 다시 설정하면 바뀐다"""
        self.ledger.budgets.set_budget("2024-01", 500000)
        self.ledger.budgets.set_budget("2024-02", 300000)
        self.ledger.budgets.set_budget("2024-01", 200000)
        self.assertEqual(read_jsonl(self.data / "budgets.jsonl"),
                         [{"month": "2024-01", "amount": 200000}, {"month": "2024-02", "amount": 300000}])
        self.assertEqual([b.month for b in self.ledger.budgets.list_all()], ["2024-02", "2024-01"])

    def test_summary_with_budget(self) -> None:
        """[4.9] 예산이 있으면 사용률과 초과 여부를 계산한다"""
        self.ledger.budgets.set_budget("2024-01", 500000)
        under = self.ledger.budgets.summarize("2024-01", top=3)
        self.assertEqual(under.budget, 500000)
        self.assertAlmostEqual(under.usage_percent or 0, 44.0)
        self.assertEqual(under.over_budget, 0)

        self.ledger.budgets.set_budget("2024-01", 200000)
        over = self.ledger.budgets.summarize("2024-01", top=3)
        self.assertAlmostEqual(over.usage_percent or 0, 110.0)
        self.assertEqual(over.over_budget, 20000)


class ImportExportTests(SeededCase):
    HEADER = "date,type,category,amount,memo,tags\n"

    def write_csv(self, body: str, name: str = "in.csv") -> Path:
        path = self.tmp / name
        path.write_text(self.HEADER + body, encoding="utf-8")
        return path

    def test_import_all_valid(self) -> None:
        """[4.11] import --from <csv> 로 거래를 일괄 등록한다"""
        path = self.write_csv('2024-03-01,expense,food,12000,김밥,"meal,lunch"\n2024-03-02,income,salary,"3,000,000",월급,\n')
        result = self.ledger.transactions.import_csv(path)
        self.assertEqual((result.imported, result.skipped), (2, []))
        records = read_jsonl(self.data / "transactions.jsonl")
        self.assertEqual(records[-2], {"id": "TX-000008", "type": "expense", "date": "2024-03-01", "amount": 12000,
                                       "category": "food", "memo": "김밥", "tags": ["meal", "lunch"]})
        self.assertEqual((records[-1]["id"], records[-1]["amount"]), ("TX-000009", 3000000))

    def test_import_skips_bad_rows_and_reports_them(self) -> None:
        """[4.11] 깨진 행은 건너뛰고(부분 성공) 줄 번호와 이유를 보고한다"""
        path = self.write_csv(
            "2024-03-01,expense,food,12000,정상,\n"      # 2번째 줄
            "2024-03-32,expense,food,1000,날짜 오류,\n"   # 3
            "2024-03-03,expense,cafe,4500,미등록,\n"      # 4
            "2024-03-04,expense,food,-100,음수,\n"        # 5
            "2024-03-05,refund,food,100,타입 오류,\n"     # 6
            "2024-03-06,expense,transport,1500\n"         # 7 (memo, tags 칸이 없어도 된다)
            ",,,,,\n"                                     # 8 (빈 값)
        )
        result = self.ledger.transactions.import_csv(path)
        self.assertEqual(result.imported, 2)
        self.assertEqual([line_no for line_no, _ in result.skipped], [3, 4, 5, 6, 8])
        reasons = dict(result.skipped)
        self.assertIn("날짜", reasons[3])
        self.assertIn("cafe", reasons[4])
        self.assertIn("금액", reasons[5])
        self.assertIn("타입", reasons[6])
        ids = [r["id"] for r in read_jsonl(self.data / "transactions.jsonl")]
        self.assertEqual(ids[-2:], ["TX-000008", "TX-000009"])  # 건너뛴 행 때문에 번호가 비지 않는다

    def test_import_unreadable_file_saves_nothing(self) -> None:
        """[4.11] 파일 자체를 읽다가 실패하면 한 건도 들어가지 않는다 (전부 취소)"""
        path = self.tmp / "cp949.csv"
        path.write_bytes(self.HEADER.encode() + b"2024-03-01,expense,food,100,ok,\n" + "2024-03-02,expense,food,100,점심,\n".encode("cp949"))
        before = (self.data / "transactions.jsonl").read_bytes()
        with self.assertRaises(AppError):
            self.ledger.transactions.import_csv(path)
        self.assertEqual((self.data / "transactions.jsonl").read_bytes(), before)

    def test_import_missing_file_or_header(self) -> None:
        """[4.11] 없는 파일, 헤더가 틀린 파일"""
        with self.assertRaises(NotFoundError):
            self.ledger.transactions.import_csv(self.tmp / "nope.csv")
        bad = self.tmp / "bad.csv"
        bad.write_text("a,b\n1,2\n", encoding="utf-8")
        with self.assertRaises(AppError):
            self.ledger.transactions.import_csv(bad)

    def test_export_requires_period(self) -> None:
        """[4.11] export 는 --month 또는 --from/--to 중 하나 이상이 필수"""
        out = self.tmp / "out.csv"
        for condition in [SearchFilter(), SearchFilter(date_from="2024-01-01"), SearchFilter(date_to="2024-01-31")]:
            with self.subTest(condition=condition), self.assertRaises(ValidationError):
                self.ledger.transactions.export_csv(out, condition)
        self.assertFalse(out.exists())

    def test_export_by_month(self) -> None:
        """[4.11] export --out <csv> --month"""
        out = self.tmp / "out.csv"
        self.assertEqual(self.ledger.transactions.export_csv(out, SearchFilter(month="2024-01")), 6)
        with out.open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(list(rows[0].keys()), ["date", "type", "category", "amount", "memo", "tags"])
        self.assertEqual(rows[0], {"date": "2024-01-05", "type": "expense", "category": "rent",
                                   "amount": "150000", "memo": "월세", "tags": "home,fixed"})
        self.assertNotIn("2024-02-01", [row["date"] for row in rows])

    def test_export_by_range_and_both(self) -> None:
        """[4.11] export --from --to, 그리고 --month 와 함께 주면 둘 다 만족하는 거래만"""
        out = self.tmp / "out.csv"
        export = self.ledger.transactions.export_csv
        self.assertEqual(export(out, SearchFilter(date_from="2024-01-12", date_to="2024-01-15")), 4)
        self.assertEqual(export(out, SearchFilter(month="2024-01", date_from="2024-01-15")), 3)
        self.assertEqual(export(out, SearchFilter(month="2023-01")), 0)
        self.assertEqual(out.read_text(encoding="utf-8").strip(), "date,type,category,amount,memo,tags")

    def test_export_refuses_non_csv_name(self) -> None:
        """실수로 저장 파일(transactions.jsonl)을 덮어쓰는 일을 막는다"""
        target = self.data / "transactions.jsonl"
        before = target.read_bytes()
        with self.assertRaises(ValidationError):
            self.ledger.transactions.export_csv(target, SearchFilter(month="2024-01"))
        self.assertEqual(target.read_bytes(), before)

    def test_export_then_import_round_trip(self) -> None:
        """[4.11] export 한 파일을 다른 가계부에 import 하면 같은 거래가 된다"""
        out = self.tmp / "all.csv"
        self.ledger.transactions.export_csv(out, SearchFilter(date_from="2000-01-01", date_to="2999-12-31"))

        other = Ledger(self.tmp / "other")
        other.initialize()
        for name in CATEGORIES:
            other.categories.add(name)
        result = other.transactions.import_csv(out)
        self.assertEqual((result.imported, result.skipped), (len(TRANSACTIONS), []))
        self.assertEqual(read_jsonl(self.tmp / "other" / "transactions.jsonl"),
                         read_jsonl(self.data / "transactions.jsonl"))


class RecurringTests(SeededCase):
    def test_add_list_remove(self) -> None:
        """[5-2] 반복 내역 등록"""
        rule = self.ledger.recurring.add(25, "income", "salary", 3000000, "월급")
        self.assertEqual(rule.id, "RC-000001")
        self.assertEqual(self.ledger.recurring.add(31, "expense", "rent", 500000).id, "RC-000002")
        self.assertEqual([r.id for r in self.ledger.recurring.list_all()], ["RC-000001", "RC-000002"])
        self.ledger.recurring.remove("rc-1")
        self.assertEqual([r.id for r in self.ledger.recurring.list_all()], ["RC-000002"])
        with self.assertRaises(NotFoundError):
            self.ledger.recurring.remove("RC-000009")

    def test_add_requires_registered_category(self) -> None:
        """[5-2] 반복 규칙도 등록된 카테고리만 쓸 수 있다"""
        with self.assertRaises(ValidationError):
            self.ledger.recurring.add(1, "expense", "gym", 50000)

    def test_apply_creates_transactions_once_per_month(self) -> None:
        """[5-2] 특정 월에 자동 생성 — 같은 달에 두 번 실행해도 중복되지 않는다"""
        self.ledger.recurring.add(25, "income", "salary", 3000000, "월급")
        self.ledger.recurring.add(31, "expense", "rent", 500000, "월세", ["fixed"])

        created = self.ledger.recurring.apply("2024-02")
        self.assertEqual([(tx.id, tx.date, tx.type, tx.category, tx.amount, tx.memo, tx.tags) for tx in created], [
            ("TX-000008", "2024-02-25", "income", "salary", 3000000, "월급", []),
            ("TX-000009", "2024-02-29", "expense", "rent", 500000, "월세", ["fixed"]),  # 31일 → 2월 말일
        ])
        self.assertEqual(len(read_jsonl(self.data / "transactions.jsonl")), len(TRANSACTIONS) + 2)

        self.assertEqual(self.ledger.recurring.apply("2024-02"), [])  # 이미 만든 달
        self.assertEqual(len(read_jsonl(self.data / "transactions.jsonl")), len(TRANSACTIONS) + 2)

        self.assertEqual(len(self.ledger.recurring.apply("2024-03")), 2)  # 다른 달은 새로 만든다
        self.assertEqual([r.applied_months for r in self.ledger.recurring.list_all()],
                         [["2024-02", "2024-03"], ["2024-02", "2024-03"]])

    def test_apply_with_no_rules(self) -> None:
        """[5-2] 규칙이 없으면 만들 것도 없다"""
        self.assertEqual(self.ledger.recurring.apply("2024-02"), [])

    def test_apply_rejects_bad_month(self) -> None:
        """[5-2] 잘못된 월은 검증 오류"""
        with self.assertRaises(ValidationError):
            self.ledger.recurring.apply("2024-2")


if __name__ == "__main__":
    unittest.main()
