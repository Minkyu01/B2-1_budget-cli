"""모델 계층 — 데이터의 '모양'과 '값 검증 규칙'만 담당한다.

파일이 어디 있는지, 화면에 어떻게 찍히는지는 전혀 모른다.
(그래서 저장 방식이나 화면이 바뀌어도 이 파일은 바뀌지 않는다.)

구성
1. parse_* 함수 : 문자열 입력을 검증해서 올바른 타입의 값으로 바꾼다.
                  대화형 입력, 명령 옵션, CSV import 가 모두 같은 함수를 쓰므로
                  "검증 규칙은 한 곳에만" 존재한다.
2. dataclass    : Transaction / Category / Budget / RecurringRule
                  만들어질 때(__post_init__) 스스로 검증하므로
                  잘못된 값을 가진 객체는 아예 생길 수 없다.
3. 결과 객체    : SearchFilter(검색 조건), MonthlySummary(월별 요약 결과), ImportResult(가져오기 결과)
"""

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from budget_app.errors import ValidationError

TransactionType = Literal["income", "expense"]
VALID_TYPES: tuple[TransactionType, ...] = ("income", "expense")

TX_PREFIX = "TX"    # 거래 id      예: TX-000012
RULE_PREFIX = "RC"  # 반복 규칙 id 예: RC-000003

DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")  # 숫자4-숫자2-숫자2
MONTH_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}")          # 숫자4-숫자2


# ---------------------------------------------------------------------------
# 1. 값 검증 함수 (문자열 → 검증된 값)
# ---------------------------------------------------------------------------

def parse_date(text: str) -> str:
    """'YYYY-MM-DD' 형식인지, 실제로 있는 날짜인지 검사한다. (2024-13-40 → 오류)"""
    text = text.strip()
    try:
        if not DATE_PATTERN.fullmatch(text):  # 모양 검사: 20240115, 2024-1-5 는 여기서 걸린다
            raise ValueError
        date.fromisoformat(text)  # 달력 검사: 13월, 2월 30일은 여기서 ValueError
    except ValueError:
        raise ValidationError(
            "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).", "예: 2024-01-15"
        ) from None
    return text


def parse_month(text: str) -> str:
    """'YYYY-MM' 형식인지, 실제로 있는 달인지 검사한다. (2024-13 → 오류)"""
    text = text.strip()
    try:
        if not MONTH_PATTERN.fullmatch(text):
            raise ValueError
        date(int(text[:4]), int(text[5:]), 1)  # 1~12월이 아니면 ValueError
    except ValueError:
        raise ValidationError(
            "월 형식이 올바르지 않습니다 (YYYY-MM).", "예: 2024-01"
        ) from None
    return text


def parse_type(text: str) -> TransactionType:
    """income / expense 둘 중 하나만 허용한다. (대소문자 무시)"""
    value = text.strip().lower()
    for valid in VALID_TYPES:
        if value == valid:
            return valid
    raise ValidationError(
        "타입은 income 또는 expense 중 하나여야 합니다.",
        "수입이면 income, 지출이면 expense 를 입력하세요.",
    )


def parse_amount(text: str | int) -> int:
    """양의 정수 금액만 허용한다. '15,000' 처럼 쉼표가 있어도 된다."""
    try:
        value = int(str(text).strip().replace(",", ""))
    except ValueError:
        raise ValidationError(
            "금액은 정수여야 합니다.", "예: 15000 (소수점, 문자 없이)"
        ) from None
    if value <= 0:
        raise ValidationError(
            "금액은 0보다 커야 합니다.",
            "지출도 양수로 입력하세요. 수입/지출은 타입으로 구분합니다.",
        )
    return value


def parse_category_name(text: str) -> str:
    """카테고리 이름: 앞뒤 공백 제거 + 소문자로 통일 (Food 와 food 를 같은 것으로)."""
    name = text.strip().lower()
    if not name:
        raise ValidationError("카테고리 이름이 비어 있습니다.", "예: food")
    return name


def parse_memo(text: str) -> str:
    """메모: 앞뒤 공백을 없애고, 줄바꿈·탭은 공백 하나로 바꾼다. (목록 표가 깨지지 않게)"""
    return " ".join(text.split())


def parse_tags(text: str) -> list[str]:
    """'meal, lunch' → ['meal', 'lunch']. 비어 있으면 빈 리스트."""
    return [tag.strip() for tag in text.split(",") if tag.strip()]


def parse_day(text: str | int) -> int:
    """반복 내역의 '매월 며칠' (1~31)."""
    try:
        day = int(str(text).strip())
    except ValueError:
        day = 0
    if not 1 <= day <= 31:
        raise ValidationError(
            "날짜(일)는 1~31 사이 숫자여야 합니다.",
            "31을 넣으면 30일까지 있는 달에는 말일(30일)로 생성됩니다.",
        )
    return day


def parse_count(text: str | int, option: str) -> int:
    """--limit, --top 같은 '개수' 옵션: 1 이상의 정수만 허용한다."""
    try:
        value = int(str(text).strip())
    except ValueError:
        value = 0
    if value <= 0:
        raise ValidationError(f"{option} 값은 1 이상의 정수여야 합니다.", f"예: {option} 5")
    return value


def make_id(prefix: str, number: int) -> str:
    """('TX', 12) → 'TX-000012'. 6자리로 0을 채워서 목록에서 줄이 맞는다."""
    return f"{prefix}-{number:06d}"


def parse_id(text: str, prefix: str) -> str:
    """'tx-12' 처럼 줄여 입력해도 'TX-000012' 로 맞춰 준다. 모양이 다르면 오류."""
    head, _, digits = text.strip().upper().partition("-")
    if head != prefix or not digits.isdecimal():
        raise ValidationError(
            f"id 형식이 올바르지 않습니다: {text}", f"예: {make_id(prefix, 12)}"
        )
    return make_id(prefix, int(digits))


def id_number(item_id: str) -> int:
    """'TX-000012' → 12. 다음 id 를 만들거나 등록 순서를 비교할 때 쓴다."""
    return int(item_id.split("-")[1])


def month_range(month: str) -> tuple[str, str]:
    """'2024-02' → ('2024-02-01', '2024-02-29'). 그 달의 첫날과 마지막 날."""
    year, mon = int(month[:4]), int(month[5:7])
    last_day = calendar.monthrange(year, mon)[1]
    return date(year, mon, 1).isoformat(), date(year, mon, last_day).isoformat()


# ---------------------------------------------------------------------------
# 2. 저장되는 데이터 (dataclass) — 파일 한 줄 = 객체 하나
# ---------------------------------------------------------------------------

@dataclass
class Transaction:
    """거래 1건. transactions.jsonl 의 한 줄이 이 객체 하나다."""

    id: str
    type: TransactionType
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # add, import, update, 파일 읽기 — 어떤 경로로 만들어져도 같은 검증을 통과해야 한다.
        self.id = parse_id(self.id, TX_PREFIX)
        self.type = parse_type(self.type)
        self.date = parse_date(self.date)
        self.amount = parse_amount(self.amount)
        self.category = parse_category_name(self.category)

    @property
    def month(self) -> str:
        """'2024-01-15' → '2024-01'"""
        return self.date[:7]


@dataclass
class Category:
    """카테고리 1개. 이름 자체가 식별자다."""

    name: str

    def __post_init__(self) -> None:
        self.name = parse_category_name(self.name)


@dataclass
class Budget:
    """월 예산. 한 달(month)에 하나만 존재한다."""

    month: str
    amount: int

    def __post_init__(self) -> None:
        self.month = parse_month(self.month)
        self.amount = parse_amount(self.amount)


@dataclass
class RecurringRule:
    """(보너스) 매월 반복되는 거래 규칙. 예: 매월 25일 salary 3,000,000원."""

    id: str
    day: int
    type: TransactionType
    category: str
    amount: int
    memo: str = ""
    tags: list[str] = field(default_factory=list)
    applied_months: list[str] = field(default_factory=list)  # 이미 거래를 만든 달 (중복 방지)

    def __post_init__(self) -> None:
        self.id = parse_id(self.id, RULE_PREFIX)
        self.day = parse_day(self.day)
        self.type = parse_type(self.type)
        self.amount = parse_amount(self.amount)
        self.category = parse_category_name(self.category)

    def date_in(self, month: str) -> str:
        """이 규칙이 month 에 만들 거래의 날짜. 31일 규칙이면 2월에는 말일로 맞춘다."""
        last_day = month_range(month)[1]
        return min(f"{month}-{self.day:02d}", last_day)


# ---------------------------------------------------------------------------
# 3. 서비스가 주고받는 값 객체 (파일에 저장하지 않는다)
# ---------------------------------------------------------------------------

@dataclass
class SearchFilter:
    """search / export 의 조건. None 인 조건은 검사하지 않는다.

    옵션으로 받은 문자열을 그대로 넣으면 만들어질 때 검증한다.
    """

    month: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    category: str | None = None
    type: TransactionType | None = None
    keyword: str | None = None
    tag: str | None = None

    def __post_init__(self) -> None:
        if self.month is not None:
            self.month = parse_month(self.month)
        if self.date_from is not None:
            self.date_from = parse_date(self.date_from)
        if self.date_to is not None:
            self.date_to = parse_date(self.date_to)
        if self.category is not None:
            self.category = parse_category_name(self.category)
        if self.type is not None:
            self.type = parse_type(self.type)
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError(
                "시작일(--from)이 종료일(--to)보다 늦습니다.",
                "--from 에 더 이른 날짜를, --to 에 더 늦은 날짜를 넣으세요.",
            )

    @property
    def has_period(self) -> bool:
        """기간 조건(월, 또는 시작일과 종료일)이 있는가. export 는 이것이 필수다."""
        return self.month is not None or (self.date_from is not None and self.date_to is not None)

    def matches(self, tx: Transaction) -> bool:
        """거래 1건이 모든 조건을 만족하면 True."""
        if self.month and tx.month != self.month:
            return False
        if self.date_from and tx.date < self.date_from:  # 'YYYY-MM-DD' 는 문자열 비교 = 날짜 비교
            return False
        if self.date_to and tx.date > self.date_to:
            return False
        if self.category and tx.category != self.category:
            return False
        if self.type and tx.type != self.type:
            return False
        if self.keyword and self.keyword.lower() not in tx.memo.lower():
            return False
        if self.tag and self.tag not in tx.tags:
            return False
        return True


@dataclass
class MonthlySummary:
    """summary 명령의 결과. 계산은 서비스가, 출력은 formatter 가 한다."""

    month: str
    income: int
    expense: int
    count: int
    top_categories: list[tuple[str, int]]  # [(카테고리, 지출 합계), ...] 많이 쓴 순
    budget: int | None  # 예산을 설정하지 않았으면 None

    @property
    def balance(self) -> int:
        return self.income - self.expense

    @property
    def usage_percent(self) -> float | None:
        if self.budget is None:
            return None
        return self.expense / self.budget * 100

    @property
    def over_budget(self) -> int:
        """예산을 초과한 금액. 초과하지 않았거나 예산이 없으면 0."""
        if self.budget is None:
            return 0
        return max(0, self.expense - self.budget)


@dataclass
class ImportResult:
    """import 명령의 결과: 몇 건을 넣었고, 어느 줄을 왜 건너뛰었는지."""

    imported: int
    skipped: list[tuple[int, str]]  # [(CSV 파일의 줄 번호, 건너뛴 이유), ...]
