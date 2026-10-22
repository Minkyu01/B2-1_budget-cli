"""서비스 계층 — 가계부의 '업무 규칙'을 담당한다.

업무 규칙의 예
    - 거래의 카테고리는 등록된 것만 쓸 수 있다.
    - 사용 중인 카테고리는 지울 수 없다.
    - 목록은 최신순으로 보여 준다.
    - export 에는 기간 조건이 꼭 있어야 한다.

이 계층은 화면(print/input)도, 파일 문법(JSON/CSV)도 모른다.
    위(cli.py)       : 검증된 값을 넘겨 주고, 결과 객체를 받아 출력한다.
    아래(storage.py) : stream / append / upsert / remove 만 해 준다.

서비스는 서로를 부르지 않는다. 다른 데이터가 필요하면 그 데이터의 '저장소'를 직접 받는다.
    예) CategoryService 는 "이 카테고리를 쓰는 거래가 있나?"를 알아야 해서 거래 저장소도 받는다.
    (서비스끼리 부르게 하면 거래 서비스 ↔ 카테고리 서비스가 서로를 필요로 해서 맞물린다)

구성
    TransactionService  거래 추가·목록·검색·수정·삭제·import·export
    CategoryService     카테고리 추가·목록·삭제
    BudgetService       예산 설정·목록, 월별 요약
    RecurringService    (보너스) 반복 내역
    Ledger              저장 폴더 하나에 대해 위 서비스들을 만들어 이어 주는 조립 담당
"""

import heapq
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

from budget_app.decorators import measure_time
from budget_app.errors import AppError, NotFoundError, ValidationError
from budget_app.models import (
    RULE_PREFIX,
    TX_PREFIX,
    Budget,
    Category,
    ImportResult,
    MonthlySummary,
    RecurringRule,
    SearchFilter,
    Transaction,
    TransactionType,
    id_number,
    make_id,
    parse_amount,
    parse_category_name,
    parse_date,
    parse_id,
    parse_memo,
    parse_month,
    parse_tags,
    parse_type,
)
from budget_app.storage import (
    BudgetRepository,
    CategoryRepository,
    JsonlRepository,
    RecurringRepository,
    TransactionRepository,
    create_backup,
    read_csv_rows,
    write_transactions_csv,
)


# ---------------------------------------------------------------------------
# 여러 서비스가 함께 쓰는 규칙
# ---------------------------------------------------------------------------

def newest_first(transactions: Iterable[Transaction], limit: int | None) -> list[Transaction]:
    """거래들을 최신순으로 고른다. 최신순 = 날짜가 늦은 것 먼저, 같은 날이면 나중에 등록한 것 먼저.

    limit 이 있으면 heapq.nlargest 가 '지금까지 본 것 중 상위 limit 건'만 들고 있는다.
        → transactions 가 10만 건을 흘려보내는 제너레이터여도 메모리에는 limit 건만 남는다.
    limit 이 None 이면 (전부 보여 달라는 뜻) 정렬하려고 조건에 맞은 거래를 모두 모은다.
    """

    def recency(tx: Transaction) -> tuple[str, int]:
        return tx.date, id_number(tx.id)

    if limit is None:
        return sorted(transactions, key=recency, reverse=True)
    return heapq.nlargest(limit, transactions, key=recency)


def category_names(categories: CategoryRepository) -> list[str]:
    """등록된 카테고리 이름들 (가나다순)."""
    return sorted(category.name for category in categories.stream())


def registered_category(name: str, registered: list[str]) -> str:
    """규칙: 거래와 반복 규칙은 등록된 카테고리만 쓸 수 있다. 통과하면 정리된 이름을 돌려준다."""
    name = parse_category_name(name)
    if name not in registered:
        raise ValidationError(
            f"등록되지 않은 카테고리입니다: {name}",
            f"등록된 카테고리: {', '.join(registered) or '(없음)'}. 새로 만들려면 category add 를 실행하세요.",
        )
    return name


# ---------------------------------------------------------------------------
# 거래
# ---------------------------------------------------------------------------

class TransactionService:
    """거래 추가·목록·검색·수정·삭제, 그리고 CSV 가져오기/내보내기."""

    def __init__(self, transactions: TransactionRepository, categories: CategoryRepository) -> None:
        self.transactions = transactions
        self.categories = categories

    # ---- 카테고리 규칙 ---------------------------------------------------

    def require_categories(self) -> None:
        """카테고리가 하나도 없으면 거래를 추가할 수 없다. (정책: category add 를 먼저 하게 한다)"""
        if not category_names(self.categories):
            raise AppError(
                "등록된 카테고리가 없어 거래를 추가할 수 없습니다.",
                "먼저 python -m budget_app category add 로 카테고리를 등록하세요.",
            )

    def check_category(self, name: str) -> str:
        """등록된 카테고리인지 확인한다. (대화형 입력에서 틀리면 다시 묻는 데에도 쓴다)"""
        return registered_category(name, category_names(self.categories))

    # ---- 추가 ------------------------------------------------------------

    def add(
        self,
        date: str,
        type: TransactionType,
        category: str,
        amount: int,
        memo: str = "",
        tags: list[str] | None = None,
    ) -> Transaction:
        """새 거래를 파일 끝에 추가한다. id 는 '지금까지 가장 큰 번호 + 1'."""
        self.require_categories()
        tx = Transaction(
            id=make_id(TX_PREFIX, self.transactions.last_number() + 1),
            date=date,
            type=type,
            category=self.check_category(category),
            amount=amount,
            memo=parse_memo(memo),
            tags=tags or [],
        )
        self.transactions.append([tx])
        return tx

    # ---- 조회 ------------------------------------------------------------

    @measure_time
    def list_recent(self, limit: int) -> list[Transaction]:
        """최신순으로 limit 건. 파일은 한 줄씩 흘려 읽고, 메모리에는 limit 건만 남는다."""
        return newest_first(self.transactions.stream(), limit)

    def matching(self, condition: SearchFilter) -> Iterator[Transaction]:
        """조건에 맞는 거래를 파일에 적힌 순서대로 하나씩 흘려보낸다. (제너레이터)"""
        return (tx for tx in self.transactions.stream() if condition.matches(tx))

    @measure_time
    def search(self, condition: SearchFilter, limit: int | None = None) -> list[Transaction]:
        """조건에 맞는 거래를 최신순으로. '읽기 → 거르기 → 고르기'가 한 건씩 흐른다."""
        return newest_first(self.matching(condition), limit)

    def get(self, tx_id: str) -> Transaction:
        """id 로 거래 1건을 찾는다. 없으면 NotFoundError."""
        tx_id = parse_id(tx_id, TX_PREFIX)
        tx = self.transactions.find(tx_id)
        if tx is None:
            raise NotFoundError(
                f"없는 데이터입니다: id 가 {tx_id} 인 거래를 찾을 수 없습니다.",
                "list 또는 search 명령으로 id 를 확인하세요.",
            )
        return tx

    # ---- 수정 / 삭제 -----------------------------------------------------

    def update(
        self,
        tx_id: str,
        *,
        date: str | None = None,
        type: TransactionType | None = None,
        category: str | None = None,
        amount: int | None = None,
        memo: str | None = None,
        tags: list[str] | None = None,
    ) -> Transaction:
        """id 로 거래를 찾아, None 이 아닌 항목만 새 값으로 바꿔 저장한다."""
        old = self.get(tx_id)
        new = Transaction(  # 새 객체를 만들면서 __post_init__ 검증을 다시 통과한다
            id=old.id,
            date=old.date if date is None else date,
            type=old.type if type is None else type,
            category=old.category if category is None else self.check_category(category),
            amount=old.amount if amount is None else amount,
            memo=old.memo if memo is None else parse_memo(memo),
            tags=old.tags if tags is None else tags,
        )
        if new == old:
            raise ValidationError(
                "바뀐 내용이 없습니다.",
                f"바꿀 항목을 기존과 다른 값으로 하나 이상 주세요. 예: update --id {old.id} --amount 20000",
            )
        self.transactions.upsert(new)
        return new

    def delete(self, tx_id: str) -> Transaction:
        """id 로 거래를 찾아 지우고, 지운 거래를 돌려준다."""
        tx = self.get(tx_id)
        self.transactions.remove(tx.id)
        return tx

    # ---- CSV 가져오기 / 내보내기 -----------------------------------------

    @measure_time
    def import_csv(self, path: Path) -> ImportResult:
        """CSV 의 각 행을 검증해서 통과한 행만 저장한다. (부분 성공 + 건너뛴 줄 보고)

        1단계: 끝까지 읽으며 검증만 한다. 이 동안에는 아무것도 저장하지 않는다.
               → CSV 자체를 읽다가 오류가 나면 '한 건도 들어가지 않은 상태'로 끝난다.
        2단계: 통과한 행들을 한 번에 파일 끝에 추가한다.
        """
        self.require_categories()
        registered = category_names(self.categories)  # 행마다 파일을 다시 읽지 않도록 한 번만 읽는다
        last_number = self.transactions.last_number()

        valid: list[Transaction] = []
        skipped: list[tuple[int, str]] = []
        for line_no, row in read_csv_rows(path):
            try:
                new_id = make_id(TX_PREFIX, last_number + len(valid) + 1)
                valid.append(self._from_csv_row(row, new_id, registered))
            except ValidationError as error:
                skipped.append((line_no, error.message))

        self.transactions.append(valid)
        return ImportResult(imported=len(valid), skipped=skipped)

    @staticmethod
    def _from_csv_row(row: dict[str, str | None], tx_id: str, registered: list[str]) -> Transaction:
        """CSV 한 행 → 거래. 값이 하나라도 틀리면 ValidationError."""
        return Transaction(
            id=tx_id,
            date=parse_date(row.get("date") or ""),
            type=parse_type(row.get("type") or ""),
            category=registered_category(row.get("category") or "", registered),
            amount=parse_amount(row.get("amount") or ""),
            memo=parse_memo(row.get("memo") or ""),
            tags=parse_tags(row.get("tags") or ""),
        )

    @measure_time
    def export_csv(self, path: Path, condition: SearchFilter) -> int:
        """조건에 맞는 거래를 CSV 로 내보내고 건수를 돌려준다.

        정렬이 필요 없어서 '읽기 → 거르기 → 쓰기'가 처음부터 끝까지 한 건씩 흐른다.
        """
        if not condition.has_period:
            raise ValidationError(
                "export 에는 기간 조건이 필요합니다.",
                "--month 2024-01 또는 --from 2024-01-01 --to 2024-01-31 을 붙이세요.",
            )
        if path.suffix.lower() != ".csv":  # 실수로 transactions.jsonl 같은 저장 파일을 덮어쓰지 않도록
            raise ValidationError(
                f"내보낼 파일 이름은 .csv 로 끝나야 합니다: {path}", "예: --out export.csv"
            )
        return write_transactions_csv(path, self.matching(condition))


# ---------------------------------------------------------------------------
# 카테고리
# ---------------------------------------------------------------------------

class CategoryService:
    """카테고리 추가·목록·삭제."""

    def __init__(
        self,
        categories: CategoryRepository,
        transactions: TransactionRepository,
        rules: RecurringRepository,
    ) -> None:
        self.categories = categories
        self.transactions = transactions  # '사용 중인가'를 확인하려고 읽기만 한다
        self.rules = rules                # 〃

    def add(self, name: str) -> Category:
        category = Category(name)
        if self.categories.exists(category.name):
            raise AppError(
                f"이미 등록된 카테고리입니다: {category.name}", "category list 로 목록을 확인하세요."
            )
        self.categories.append([category])
        return category

    def list_all(self) -> list[Category]:
        """등록된 카테고리 전체 (가나다순)."""
        return sorted(self.categories.stream(), key=lambda category: category.name)

    def remove(self, name: str) -> Category:
        """카테고리를 지운다. 단, 사용 중이면 막는다. (거래는 남았는데 카테고리만 사라지는 모순 방지)"""
        category = Category(name)
        if not self.categories.exists(category.name):
            raise NotFoundError(
                f"없는 데이터입니다: 카테고리 {category.name} 을(를) 찾을 수 없습니다.",
                "category list 로 이름을 확인하세요.",
            )
        used_by_transactions = sum(1 for tx in self.transactions.stream() if tx.category == category.name)
        used_by_rules = sum(1 for rule in self.rules.stream() if rule.category == category.name)
        if used_by_transactions or used_by_rules:
            raise AppError(
                f"사용 중인 카테고리는 삭제할 수 없습니다: {category.name} "
                f"(거래 {used_by_transactions}건, 반복 규칙 {used_by_rules}건)",
                f"search --category {category.name} 로 찾아 update 로 카테고리를 바꾸거나 delete 한 뒤 다시 시도하세요.",
            )
        self.categories.remove(category.name)
        return category


# ---------------------------------------------------------------------------
# 예산 + 월별 요약
# ---------------------------------------------------------------------------

class BudgetService:
    """월 예산 설정·목록과, 예산을 곁들인 월별 요약."""

    def __init__(self, budgets: BudgetRepository, transactions: TransactionRepository) -> None:
        self.budgets = budgets
        self.transactions = transactions  # 요약을 계산하려고 읽기만 한다

    def set_budget(self, month: str, amount: int) -> Budget:
        """그 달의 예산을 저장한다. 이미 있으면 새 금액으로 바꾼다."""
        budget = Budget(month=month, amount=amount)
        self.budgets.upsert(budget)
        return budget

    def list_all(self) -> list[Budget]:
        """설정된 예산 전체 (최근 달 먼저)."""
        return sorted(self.budgets.stream(), key=lambda budget: budget.month, reverse=True)

    @measure_time
    def summarize(self, month: str, top: int) -> MonthlySummary:
        """month 의 거래를 한 번 훑으며 더한다. 메모리에는 합계와 카테고리별 소계만 남는다."""
        month = parse_month(month)
        income = expense = count = 0
        by_category: defaultdict[str, int] = defaultdict(int)  # 카테고리 → 지출 합계
        for tx in self.transactions.stream():
            if tx.month != month:
                continue
            count += 1
            if tx.type == "income":
                income += tx.amount
            else:
                expense += tx.amount
                by_category[tx.category] += tx.amount

        # 많이 쓴 순서. 금액이 같으면 이름순으로 해서 실행할 때마다 순서가 같게 한다.
        ranked = sorted(by_category.items(), key=lambda pair: (-pair[1], pair[0]))
        budget = self.budgets.find(month)
        return MonthlySummary(
            month=month,
            income=income,
            expense=expense,
            count=count,
            top_categories=ranked[:top],
            budget=budget.amount if budget else None,
        )


# ---------------------------------------------------------------------------
# (보너스 2) 반복 내역
# ---------------------------------------------------------------------------

class RecurringService:
    """월급·월세처럼 매월 반복되는 거래를 규칙으로 등록해 두고, 원하는 달에 한꺼번에 만든다."""

    def __init__(
        self,
        rules: RecurringRepository,
        transactions: TransactionRepository,
        categories: CategoryRepository,
    ) -> None:
        self.rules = rules
        self.transactions = transactions
        self.categories = categories

    def add(
        self,
        day: int,
        type: TransactionType,
        category: str,
        amount: int,
        memo: str = "",
        tags: list[str] | None = None,
    ) -> RecurringRule:
        rule = RecurringRule(
            id=make_id(RULE_PREFIX, self.rules.last_number() + 1),
            day=day,
            type=type,
            category=registered_category(category, category_names(self.categories)),
            amount=amount,
            memo=parse_memo(memo),
            tags=tags or [],
        )
        self.rules.append([rule])
        return rule

    def list_all(self) -> list[RecurringRule]:
        return list(self.rules.stream())

    def remove(self, rule_id: str) -> RecurringRule:
        rule_id = parse_id(rule_id, RULE_PREFIX)
        rule = self.rules.find(rule_id)
        if rule is None:
            raise NotFoundError(
                f"없는 데이터입니다: id 가 {rule_id} 인 반복 규칙을 찾을 수 없습니다.",
                "recurring list 로 id 를 확인하세요.",
            )
        self.rules.remove(rule.id)
        return rule

    def apply(self, month: str) -> list[Transaction]:
        """month 에 아직 거래를 만들지 않은 규칙마다 거래를 1건씩 만든다.

        만든 달은 규칙의 applied_months 에 적어 두므로 같은 달에 두 번 실행해도 중복되지 않는다.
        """
        month = parse_month(month)
        number = self.transactions.last_number()
        created: list[Transaction] = []
        applied_rules: list[RecurringRule] = []
        for rule in self.rules.stream():
            if month in rule.applied_months:
                continue
            number += 1
            created.append(
                Transaction(
                    id=make_id(TX_PREFIX, number),
                    date=rule.date_in(month),
                    type=rule.type,
                    category=rule.category,
                    amount=rule.amount,
                    memo=rule.memo,
                    tags=list(rule.tags),
                )
            )
            applied_rules.append(replace(rule, applied_months=[*rule.applied_months, month]))

        # 거래를 먼저 저장하고, 그다음에 '이 달은 만들었다'고 표시한다.
        # (반대 순서면 중간에 꺼졌을 때 표시만 남고 거래는 없는 상태가 된다 — 조용히 사라지는 쪽이 더 나쁘다)
        self.transactions.append(created)
        for rule in applied_rules:
            self.rules.upsert(rule)
        return created


# ---------------------------------------------------------------------------
# 조립
# ---------------------------------------------------------------------------

class Ledger:
    """가계부 하나 = 저장 폴더 하나. 저장소 4개를 만들고 서비스 4개에 나눠 준다(조립).

    업무 규칙은 여기에 없다. '어떤 서비스가 어떤 파일을 쓰는지'만 이곳에서 정한다.
    CLI 는 이 객체의 서비스만 부르므로 cli.py 는 storage.py 를 import 할 필요가 없다.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        transactions = TransactionRepository(data_dir / "transactions.jsonl")
        categories = CategoryRepository(data_dir / "categories.jsonl")
        budgets = BudgetRepository(data_dir / "budgets.jsonl")
        rules = RecurringRepository(data_dir / "recurring.jsonl")
        self._repositories: list[JsonlRepository[Any]] = [transactions, categories, budgets, rules]

        self.transactions = TransactionService(transactions, categories)
        self.categories = CategoryService(categories, transactions, rules)
        self.budgets = BudgetService(budgets, transactions)
        self.recurring = RecurringService(rules, transactions, categories)

    def initialize(self) -> list[Path]:
        """저장 폴더와 파일이 없으면 빈 파일로 만든다. 새로 만든 파일들을 돌려준다."""
        return [repository.path for repository in self._repositories if repository.ensure_file()]

    def backup(self) -> Path:
        """(보너스 1) 저장 파일 전체를 <저장 폴더>/backups/backup-날짜-시각.zip 하나로 묶는다."""
        return create_backup(
            self.data_dir / "backups", [repository.path for repository in self._repositories]
        )
