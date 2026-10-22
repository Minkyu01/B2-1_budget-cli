"""모델 계층 테스트 — 값 검증 규칙과 dataclass. (파일·화면 없이 순수 함수만 확인한다)

대괄호 번호는 project.md 의 조항 번호다.
"""

import dataclasses
import unittest

import helpers  # noqa: F401  (sys.path 준비)
from budget_app.errors import AppError, ValidationError
from budget_app.models import (
    Budget,
    Category,
    ImportResult,
    MonthlySummary,
    RecurringRule,
    SearchFilter,
    Transaction,
    id_number,
    make_id,
    month_range,
    parse_amount,
    parse_category_name,
    parse_count,
    parse_date,
    parse_day,
    parse_id,
    parse_memo,
    parse_month,
    parse_tags,
    parse_type,
)


def make_tx(**changes: object) -> Transaction:
    fields: dict = {
        "id": "TX-000001",
        "type": "expense",
        "date": "2024-01-15",
        "amount": 15000,
        "category": "food",
        "memo": "점심",
        "tags": ["meal"],
    }
    fields.update(changes)
    return Transaction(**fields)


class ParseFunctionTests(unittest.TestCase):
    def test_parse_date_accepts_only_real_yyyy_mm_dd(self) -> None:
        """[4.2] 날짜는 YYYY-MM-DD 형식이고 달력에 있는 날이어야 한다"""
        self.assertEqual(parse_date("2024-01-15"), "2024-01-15")
        self.assertEqual(parse_date(" 2024-02-29 "), "2024-02-29")  # 앞뒤 공백 허용, 윤년
        for wrong in ["2024-13-40", "2023-02-29", "20240115", "2024-1-5", "2024/01/15", "2024-W03-1", "", "오늘"]:
            with self.subTest(wrong=wrong):
                with self.assertRaises(ValidationError) as caught:
                    parse_date(wrong)
                self.assertTrue(caught.exception.hint)  # 모든 오류는 해결 힌트를 갖는다

    def test_parse_month(self) -> None:
        """[4.8] 월은 YYYY-MM 형식이어야 한다"""
        self.assertEqual(parse_month("2024-01"), "2024-01")
        for wrong in ["2024-13", "2024-00", "2024-1", "202401", "2024-01-15", "0000-01", ""]:
            with self.subTest(wrong=wrong), self.assertRaises(ValidationError):
                parse_month(wrong)

    def test_parse_type(self) -> None:
        """[4.2] type 은 income / expense 만 허용한다"""
        self.assertEqual(parse_type("income"), "income")
        self.assertEqual(parse_type(" Expense "), "expense")
        for wrong in ["spend", "수입", ""]:
            with self.subTest(wrong=wrong), self.assertRaises(ValidationError):
                parse_type(wrong)

    def test_parse_amount_must_be_positive_integer(self) -> None:
        """[4.2] 금액은 양수 — 0 과 음수, 정수가 아닌 값은 거부한다"""
        self.assertEqual(parse_amount("15000"), 15000)
        self.assertEqual(parse_amount("3,000,000"), 3000000)
        self.assertEqual(parse_amount(500), 500)
        for wrong in ["0", "-5", "abc", "12.5", "", "1만원"]:
            with self.subTest(wrong=wrong), self.assertRaises(ValidationError):
                parse_amount(wrong)

    def test_parse_category_name_normalizes(self) -> None:
        """[4.2] 카테고리 이름은 공백을 없애고 소문자로 통일한다"""
        self.assertEqual(parse_category_name("  Food "), "food")
        with self.assertRaises(ValidationError):
            parse_category_name("   ")

    def test_parse_memo_and_tags(self) -> None:
        """[4.2] 메모의 줄바꿈 정리, 태그는 쉼표로 나눈다"""
        self.assertEqual(parse_memo("  점심\n약속\t "), "점심 약속")
        self.assertEqual(parse_tags("meal, lunch ,, "), ["meal", "lunch"])
        self.assertEqual(parse_tags(""), [])

    def test_parse_day_and_count(self) -> None:
        """[4.5] --limit/--top 같은 개수는 1 이상의 정수"""
        self.assertEqual(parse_day("31"), 31)
        for wrong in ["0", "32", "x"]:
            with self.subTest(wrong=wrong), self.assertRaises(ValidationError):
                parse_day(wrong)
        self.assertEqual(parse_count("5", "--limit"), 5)
        for wrong in ["0", "-1", "abc", "1.5"]:
            with self.subTest(wrong=wrong):
                with self.assertRaises(ValidationError) as caught:
                    parse_count(wrong, "--limit")
                self.assertIn("--limit", caught.exception.message)

    def test_id_helpers(self) -> None:
        """[4.2] id 만들기·읽기 (TX-000012)"""
        self.assertEqual(make_id("TX", 12), "TX-000012")
        self.assertEqual(id_number("TX-000012"), 12)
        self.assertEqual(parse_id("tx-12", "TX"), "TX-000012")  # 줄여 써도 맞춰 준다
        self.assertEqual(parse_id(" TX-000012 ", "TX"), "TX-000012")
        self.assertEqual(id_number(make_id("TX", 1234567)), 1234567)  # 6자리를 넘어도 번호는 보존된다
        for wrong in ["12", "RC-000001", "TX-", "TX-1a", "TX-1-2", ""]:
            with self.subTest(wrong=wrong), self.assertRaises(ValidationError):
                parse_id(wrong, "TX")

    def test_month_range(self) -> None:
        """한 달의 첫날과 마지막 날 (윤년 포함)"""
        self.assertEqual(month_range("2024-02"), ("2024-02-01", "2024-02-29"))
        self.assertEqual(month_range("2023-02"), ("2023-02-01", "2023-02-28"))
        self.assertEqual(month_range("2024-12"), ("2024-12-01", "2024-12-31"))


class DataclassTests(unittest.TestCase):
    def test_transaction_is_dataclass_with_required_fields(self) -> None:
        """[4.2] Transaction 은 dataclass 이고 id/type/date/amount/category/memo/tags 를 가진다"""
        self.assertTrue(dataclasses.is_dataclass(Transaction))
        names = [f.name for f in dataclasses.fields(Transaction)]
        self.assertEqual(names, ["id", "type", "date", "amount", "category", "memo", "tags"])

    def test_memo_and_tags_are_optional(self) -> None:
        """[4.2] memo, tags 는 선택"""
        tx = Transaction(id="TX-000001", type="income", date="2024-01-14", amount=100, category="salary")
        self.assertEqual((tx.memo, tx.tags), ("", []))

    def test_transaction_validates_itself(self) -> None:
        """[4.2] 어떤 경로로 만들어도 잘못된 값을 가진 거래는 생길 수 없다"""
        self.assertEqual(make_tx(category=" Food ").category, "food")
        self.assertEqual(make_tx(id="tx-7").id, "TX-000007")
        self.assertEqual(make_tx(amount="15,000").amount, 15000)
        for field, wrong in [("date", "2024-13-40"), ("amount", 0), ("amount", -1), ("type", "spend"),
                             ("category", ""), ("id", "abc")]:
            with self.subTest(field=field, wrong=wrong), self.assertRaises(ValidationError):
                make_tx(**{field: wrong})

    def test_transaction_month(self) -> None:
        """거래 날짜에서 월을 뽑는다"""
        self.assertEqual(make_tx(date="2024-03-09").month, "2024-03")

    def test_category_and_budget_validate(self) -> None:
        """[4.2] Category, Budget 도 만들어질 때 스스로 검증한다"""
        self.assertEqual(Category(" Rent ").name, "rent")
        self.assertEqual(Budget(month="2024-01", amount="500,000").amount, 500000)  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            Budget(month="2024-1", amount=1)
        with self.assertRaises(ValidationError):
            Budget(month="2024-01", amount=0)

    def test_recurring_rule_date_in(self) -> None:
        """[5-2] 31일 규칙은 그 달의 말일로 맞춘다"""
        rule = RecurringRule(id="RC-000001", day=31, type="expense", category="rent", amount=500000)
        self.assertEqual(rule.date_in("2024-01"), "2024-01-31")
        self.assertEqual(rule.date_in("2024-02"), "2024-02-29")
        self.assertEqual(rule.date_in("2024-04"), "2024-04-30")
        early = RecurringRule(id="RC-000002", day=5, type="income", category="salary", amount=1)
        self.assertEqual(early.date_in("2024-02"), "2024-02-05")

    def test_validation_error_is_app_error_with_hint(self) -> None:
        """[4.13] 검증 오류는 원인(message)과 해결 힌트(hint)를 함께 갖는다"""
        with self.assertRaises(AppError) as caught:
            parse_date("2024-13-40")
        self.assertIn("날짜 형식", caught.exception.message)
        self.assertIn("2024-01-15", caught.exception.hint)


class SearchFilterTests(unittest.TestCase):
    def test_empty_filter_matches_everything(self) -> None:
        """[4.7] 조건을 하나도 안 주면 전부 맞는다"""
        self.assertTrue(SearchFilter().matches(make_tx()))

    def test_each_condition(self) -> None:
        """[4.7] 기간·카테고리·타입·메모 키워드·태그 조건"""
        tx = make_tx(date="2024-01-15", category="food", type="expense", memo="저녁 회식", tags=["meal", "team"])
        cases = [
            (SearchFilter(date_from="2024-01-15"), True),
            (SearchFilter(date_from="2024-01-16"), False),
            (SearchFilter(date_to="2024-01-15"), True),
            (SearchFilter(date_to="2024-01-14"), False),
            (SearchFilter(month="2024-01"), True),
            (SearchFilter(month="2024-02"), False),
            (SearchFilter(category="FOOD"), True),  # 카테고리 이름은 소문자로 통일된다
            (SearchFilter(category="rent"), False),
            (SearchFilter(type="expense"), True),
            (SearchFilter(type="income"), False),
            (SearchFilter(keyword="회식"), True),
            (SearchFilter(keyword="점심"), False),
            (SearchFilter(tag="team"), True),
            (SearchFilter(tag="tea"), False),  # 태그는 부분 일치가 아니라 정확히 일치
        ]
        for condition, expected in cases:
            with self.subTest(condition=condition):
                self.assertEqual(condition.matches(tx), expected)

    def test_conditions_are_combined_with_and(self) -> None:
        """[4.7] 조건을 여러 개 주면 모두 만족해야 한다"""
        tx = make_tx(category="food", type="expense")
        self.assertTrue(SearchFilter(category="food", type="expense").matches(tx))
        self.assertFalse(SearchFilter(category="food", type="income").matches(tx))

    def test_keyword_ignores_case(self) -> None:
        """[4.7] 메모 키워드는 대소문자를 구분하지 않는다"""
        self.assertTrue(SearchFilter(keyword="LUNCH").matches(make_tx(memo="team lunch")))

    def test_filter_validates_its_values(self) -> None:
        """[4.7] 잘못된 검색 옵션은 오류 메시지로 처리한다"""
        for kwargs in [{"date_from": "2024-13-01"}, {"date_to": "어제"}, {"type": "xx"}, {"month": "2024-1"},
                       {"date_from": "2024-02-01", "date_to": "2024-01-01"}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                SearchFilter(**kwargs)  # type: ignore[arg-type]

    def test_has_period(self) -> None:
        """[4.11] export 는 --month 또는 --from/--to 가 있어야 한다"""
        self.assertTrue(SearchFilter(month="2024-01").has_period)
        self.assertTrue(SearchFilter(date_from="2024-01-01", date_to="2024-01-31").has_period)
        self.assertFalse(SearchFilter().has_period)
        self.assertFalse(SearchFilter(date_from="2024-01-01").has_period)
        self.assertFalse(SearchFilter(category="food").has_period)


class SummaryTests(unittest.TestCase):
    def make(self, expense: int, budget: "int | None") -> MonthlySummary:
        return MonthlySummary(month="2024-01", income=1000, expense=expense, count=3, top_categories=[], budget=budget)

    def test_balance(self) -> None:
        """[4.8] 잔액 = 총수입 - 총지출"""
        self.assertEqual(self.make(expense=300, budget=None).balance, 700)
        self.assertEqual(self.make(expense=1500, budget=None).balance, -500)

    def test_usage_and_over_budget(self) -> None:
        """[4.9] 예산 대비 사용률(%)과 초과 여부"""
        under = self.make(expense=215000, budget=500000)
        self.assertAlmostEqual(under.usage_percent or 0, 43.0)
        self.assertEqual(under.over_budget, 0)
        over = self.make(expense=215000, budget=200000)
        self.assertAlmostEqual(over.usage_percent or 0, 107.5)
        self.assertEqual(over.over_budget, 15000)
        exact = self.make(expense=200000, budget=200000)
        self.assertEqual(exact.over_budget, 0)  # 딱 맞게 쓴 것은 초과가 아니다

    def test_no_budget(self) -> None:
        """[4.9] 예산이 없으면 사용률은 None, 초과 금액은 0"""
        summary = self.make(expense=100, budget=None)
        self.assertIsNone(summary.usage_percent)
        self.assertEqual(summary.over_budget, 0)

    def test_import_result(self) -> None:
        """[4.11] import 결과는 넣은 건수와 건너뛴 줄 목록"""
        result = ImportResult(imported=3, skipped=[(4, "날짜 형식")])
        self.assertEqual((result.imported, len(result.skipped)), (3, 1))


if __name__ == "__main__":
    unittest.main()
