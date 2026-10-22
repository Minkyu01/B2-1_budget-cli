"""CLI 계층 — 사용자와 대화하는 일만 한다.

하는 일 3가지
    1. 명령줄을 읽는다          argparse : `list --limit 5` → args.limit == "5"
    2. 필요한 값을 입력받는다    input()  : add 의 날짜·타입·카테고리·금액 ...
    3. 서비스를 부르고 결과를 출력한다

하지 않는 일
    - 업무 규칙 판단 (서비스가 한다)
    - 파일 읽기/쓰기 (저장소가 한다 — 이 파일은 storage 를 import 하지도 않는다)

입력 방식
    대화형 : add, category add, category remove, recurring add
    옵션   : 나머지 전부 (update 도 옵션 방식으로 고정)

읽는 순서: 맨 아래 main → build_parser → 위쪽의 cmd_* 함수들
"""

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, NoReturn, TypeVar

from budget_app.decorators import EXIT_OK, EXIT_USAGE, handle_errors, log_command, setup_logging
from budget_app.errors import ValidationError
from budget_app.formatter import (
    format_budgets,
    format_categories,
    format_rules,
    format_summary,
    format_transactions,
    money,
    print_error,
)
from budget_app.models import (
    SearchFilter,
    Transaction,
    parse_amount,
    parse_category_name,
    parse_count,
    parse_date,
    parse_day,
    parse_memo,
    parse_month,
    parse_tags,
    parse_type,
)
from budget_app.services import Ledger

PROG = "python -m budget_app"
DEFAULT_DATA_DIR = Path("data")
LOG_FILE = "app.log"
DEFAULT_LIMIT = 10  # list 가 보여 주는 기본 건수
DEFAULT_TOP = 3     # summary 가 보여 주는 지출 상위 카테고리 수

T = TypeVar("T")
Handler = Callable[[Ledger, argparse.Namespace], None]  # 모든 cmd_* 함수의 모양


# ---------------------------------------------------------------------------
# 1. 입력·출력 도우미
# ---------------------------------------------------------------------------

def ask(prompt: str, parse: Callable[[str], T]) -> T:
    """올바른 값이 들어올 때까지 같은 질문을 되풀이한다. (대화형 입력의 '재입력 요구')

    parse 는 '문자열 → 검증된 값' 함수다. 값이 틀리면 ValidationError 를 내는데,
    그러면 원인과 힌트를 보여 주고 다시 묻는다.
    """
    while True:
        try:
            return parse(input(prompt))
        except ValidationError as error:
            print_error(error.message, error.hint)


def optional(value: str | None, parse: Callable[[str], T]) -> T | None:
    """옵션을 주지 않았으면 None 그대로, 줬으면 검증한 값으로 바꾼다."""
    return None if value is None else parse(value)


def category_prompt(ledger: Ledger) -> str:
    """'카테고리(food, transport): ' — 고를 수 있는 이름을 질문에 함께 보여 준다."""
    names = ", ".join(category.name for category in ledger.categories.list_all())
    return f"카테고리({names}): "


def print_transactions(transactions: list[Transaction], empty_message: str) -> None:
    """거래 목록을 표로 출력한다. 한 건도 없으면 empty_message 를 대신 보여 준다."""
    if not transactions:
        print(empty_message)
        return
    print(format_transactions(transactions))
    print(f"({len(transactions)}건)")


# ---------------------------------------------------------------------------
# 2. 명령 함수 — 명령 1개 = 함수 1개. (입력 받기 → 서비스 호출 → 출력)
# ---------------------------------------------------------------------------

@log_command
def cmd_add(ledger: Ledger, args: argparse.Namespace) -> None:
    """add : 대화형으로 한 항목씩 입력받아 거래를 추가한다."""
    ledger.transactions.require_categories()  # 카테고리가 없으면 질문을 시작하기 전에 막는다
    date = ask("날짜(YYYY-MM-DD): ", parse_date)
    tx_type = ask("타입(income/expense): ", parse_type)
    category = ask(category_prompt(ledger), ledger.transactions.check_category)
    amount = ask("금액(양수): ", parse_amount)
    memo = input("메모(선택): ")
    tags = parse_tags(input("태그(쉼표로 구분, 없으면 엔터): "))

    tx = ledger.transactions.add(date, tx_type, category, amount, memo, tags)
    print(f"[저장 완료] id={tx.id}")


@log_command
def cmd_list(ledger: Ledger, args: argparse.Namespace) -> None:
    """list : 최신순으로 --limit 건."""
    limit = parse_count(args.limit, "--limit")
    print_transactions(
        ledger.transactions.list_recent(limit),
        "기록된 거래가 없습니다. add 명령으로 추가하세요.",
    )


@log_command
def cmd_search(ledger: Ledger, args: argparse.Namespace) -> None:
    """search : 준 조건을 모두 만족하는 거래를 최신순으로."""
    condition = SearchFilter(
        date_from=args.date_from,
        date_to=args.date_to,
        category=args.category,
        type=args.type,
        keyword=args.q,
        tag=args.tag,
    )
    limit = None if args.limit is None else parse_count(args.limit, "--limit")
    print_transactions(ledger.transactions.search(condition, limit), "조건에 맞는 거래가 없습니다.")


@log_command
def cmd_summary(ledger: Ledger, args: argparse.Namespace) -> None:
    """summary : 한 달의 수입·지출·잔액, 예산 사용률, 지출 상위 카테고리."""
    month = parse_month(args.month)
    top = parse_count(args.top, "--top")
    print(format_summary(ledger.budgets.summarize(month, top), top))


@log_command
def cmd_budget_set(ledger: Ledger, args: argparse.Namespace) -> None:
    budget = ledger.budgets.set_budget(parse_month(args.month), parse_amount(args.amount))
    print(f"[저장 완료] {budget.month} 예산 {money(budget.amount)}")


@log_command
def cmd_budget_list(ledger: Ledger, args: argparse.Namespace) -> None:
    budgets = ledger.budgets.list_all()
    if not budgets:
        print("설정된 예산이 없습니다. budget set --month YYYY-MM --amount 금액 으로 설정하세요.")
        return
    print(format_budgets(budgets))


@log_command
def cmd_category_add(ledger: Ledger, args: argparse.Namespace) -> None:
    name = ask("카테고리명: ", parse_category_name)
    category = ledger.categories.add(name)
    print(f"[저장 완료] category={category.name}")


@log_command
def cmd_category_list(ledger: Ledger, args: argparse.Namespace) -> None:
    categories = ledger.categories.list_all()
    if not categories:
        print("등록된 카테고리가 없습니다. category add 로 먼저 등록하세요.")
        return
    print(format_categories(categories))


@log_command
def cmd_category_remove(ledger: Ledger, args: argparse.Namespace) -> None:
    name = ask("삭제할 카테고리명: ", parse_category_name)
    category = ledger.categories.remove(name)
    print(f"[삭제 완료] category={category.name}")


@log_command
def cmd_update(ledger: Ledger, args: argparse.Namespace) -> None:
    """update : --id 로 고른 거래에서, 옵션으로 준 항목만 바꾼다. (옵션 방식으로 고정)"""
    tx = ledger.transactions.update(
        args.id,
        date=optional(args.date, parse_date),
        type=optional(args.type, parse_type),
        category=optional(args.category, parse_category_name),
        amount=optional(args.amount, parse_amount),
        memo=optional(args.memo, parse_memo),
        tags=optional(args.tags, parse_tags),
    )
    print(f"[수정 완료] id={tx.id}")
    print(format_transactions([tx]))


@log_command
def cmd_delete(ledger: Ledger, args: argparse.Namespace) -> None:
    tx = ledger.transactions.delete(args.id)
    print(f"[삭제 완료] id={tx.id}")
    print(format_transactions([tx]))


@log_command
def cmd_import(ledger: Ledger, args: argparse.Namespace) -> None:
    """import : CSV 의 거래를 한꺼번에 등록한다. 틀린 줄은 건너뛰고 이유를 알려 준다."""
    result = ledger.transactions.import_csv(Path(args.source))
    print(f"[완료] imported={result.imported}, skipped={len(result.skipped)}")
    for line_no, reason in result.skipped:
        print(f"  - {line_no}번째 줄 건너뜀: {reason}")
    if result.skipped:
        print("[안내] 건너뛴 줄만 고쳐서 새 CSV 로 다시 import 하세요.")
        print("       (같은 파일을 그대로 다시 넣으면 이미 들어간 거래가 중복됩니다)")


@log_command
def cmd_export(ledger: Ledger, args: argparse.Namespace) -> None:
    """export : 기간 조건에 맞는 거래를 CSV 파일로 저장한다."""
    condition = SearchFilter(month=args.month, date_from=args.date_from, date_to=args.date_to)
    count = ledger.transactions.export_csv(Path(args.out), condition)
    print(f"[완료] {args.out} ({count} records)")


@log_command
def cmd_backup(ledger: Ledger, args: argparse.Namespace) -> None:
    print(f"[백업 완료] {ledger.backup()}")


@log_command
def cmd_recurring_add(ledger: Ledger, args: argparse.Namespace) -> None:
    """recurring add : 대화형으로 반복 규칙을 등록한다. (날짜 대신 '매월 며칠'을 묻는 것만 add 와 다르다)"""
    ledger.transactions.require_categories()
    day = ask("매월 며칠(1~31): ", parse_day)
    tx_type = ask("타입(income/expense): ", parse_type)
    category = ask(category_prompt(ledger), ledger.transactions.check_category)
    amount = ask("금액(양수): ", parse_amount)
    memo = input("메모(선택): ")
    tags = parse_tags(input("태그(쉼표로 구분, 없으면 엔터): "))

    rule = ledger.recurring.add(day, tx_type, category, amount, memo, tags)
    print(f"[저장 완료] id={rule.id}")


@log_command
def cmd_recurring_list(ledger: Ledger, args: argparse.Namespace) -> None:
    rules = ledger.recurring.list_all()
    if not rules:
        print("등록된 반복 규칙이 없습니다. recurring add 로 등록하세요.")
        return
    print(format_rules(rules))


@log_command
def cmd_recurring_remove(ledger: Ledger, args: argparse.Namespace) -> None:
    rule = ledger.recurring.remove(args.id)
    print(f"[삭제 완료] id={rule.id}")


@log_command
def cmd_recurring_apply(ledger: Ledger, args: argparse.Namespace) -> None:
    month = parse_month(args.month)
    created = ledger.recurring.apply(month)
    print(f"[완료] {month} 반복 내역 {len(created)}건 생성")
    print_transactions(created, "새로 만들 것이 없습니다. (규칙이 없거나, 이 달은 이미 만들었습니다)")


# ---------------------------------------------------------------------------
# 3. 명령줄 문법 (argparse)
# ---------------------------------------------------------------------------

class Parser(argparse.ArgumentParser):
    """이 앱의 규칙 3가지를 입힌 ArgumentParser.

    1. 도움말 옵션은 --help 하나만 둔다. (짧은 -h 는 만들지 않는다 — 옵션 표기는 -- 로 통일)
    2. 어느 명령에서든 --data-dir 로 저장 폴더를 바꿀 수 있다.
    3. 명령 형식이 틀리면 [오류]/[힌트] 형식으로 알리고 종료 코드 2로 끝낸다.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)  # 예시 줄을 접지 않는다
        super().__init__(add_help=False, allow_abbrev=False, **kwargs)
        self.add_argument("--help", action="help", help="도움말을 보여 주고 끝냅니다.")
        self.add_argument(
            "--data-dir",
            type=Path,
            default=argparse.SUPPRESS,  # 주지 않으면 args 에 아예 넣지 않는다 → main 이 기본값을 쓴다
            metavar="DIR",
            help=f"저장 폴더 (기본: ./{DEFAULT_DATA_DIR})",
        )

    def error(self, message: str) -> NoReturn:
        print_error(f"명령 형식이 올바르지 않습니다: {message}", f"사용법 보기: {self.prog} --help")
        raise SystemExit(EXIT_USAGE)


def add_command(
    commands: "argparse._SubParsersAction[Parser]",
    name: str,
    handler: Handler | None,
    summary: str,
    example: str = "",
) -> Parser:
    """하위 명령 1개를 등록한다.

    handler : 이 명령을 처리할 cmd_* 함수. (budget 처럼 하위 명령을 또 갖는 묶음이면 None)
    summary : 명령 목록과 그 명령의 --help 양쪽에 나오는 한 줄 설명
    example : --help 맨 아래에 보여 줄 사용 예
    """
    parser = commands.add_parser(
        name,
        help=summary,
        description=summary,
        epilog=f"예: {PROG} {example}" if example else None,
    )
    if handler is not None:
        parser.set_defaults(handler=handler)  # main 이 args.handler 로 꺼내 실행한다
    return parser


HELP_EPILOG = f"""\
처음 쓰는 순서
  {PROG} category add              카테고리부터 등록한다 (예: food)
  {PROG} add                       거래를 추가한다 (질문에 차례로 답한다)
  {PROG} list --limit 5            최근 5건을 본다
  {PROG} summary --month 2024-01   한 달을 요약한다

명령마다 자세한 사용법: {PROG} <명령> --help
"""


def build_parser() -> Parser:
    """명령줄 문법 전체. 명령마다 (1) 처리할 함수 (2) 설명 (3) 옵션을 적는다.

    옵션 값은 전부 문자열로 받는다. 숫자·날짜 검사는 argparse 가 아니라 models 의 parse_* 가 한다.
    (그래야 오류가 항상 [오류]/[힌트] 한국어 문구로 나온다)
    """
    parser = Parser(
        prog=PROG,
        description="파일 기반 가계부: 거래를 JSONL 파일에 저장하고 조회·검색·요약한다.",
        epilog=HELP_EPILOG,
    )
    commands = parser.add_subparsers(title="명령", metavar="<명령>", required=True)

    # ---- add ----
    add_command(
        commands, "add", cmd_add,
        "거래 추가 (대화형: 날짜·타입·카테고리·금액·메모·태그를 차례로 입력)",
        example="add",
    )

    # ---- list ----
    list_ = add_command(commands, "list", cmd_list, "거래 목록 (최신순)", example="list --limit 5")
    list_.add_argument(
        "--limit", default=str(DEFAULT_LIMIT), metavar="N", help=f"보여 줄 건수 (기본 {DEFAULT_LIMIT})"
    )

    # ---- search ----
    search = add_command(
        commands, "search", cmd_search,
        "거래 검색 (준 조건을 모두 만족하는 거래, 최신순)",
        example="search --from 2024-01-01 --to 2024-01-31 --category food",
    )
    search.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="이 날짜부터")
    search.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="이 날짜까지")
    search.add_argument("--category", metavar="NAME", help="카테고리")
    search.add_argument("--type", metavar="TYPE", help="income 또는 expense")
    search.add_argument("--q", metavar="WORD", help="메모에 들어 있는 단어")
    search.add_argument("--tag", metavar="TAG", help="태그")
    search.add_argument("--limit", metavar="N", help="보여 줄 건수 (기본: 전부)")

    # ---- summary ----
    summary = add_command(
        commands, "summary", cmd_summary,
        "월별 요약 (수입·지출·잔액, 예산 사용률, 지출 상위 카테고리)",
        example="summary --month 2024-01 --top 3",
    )
    summary.add_argument("--month", required=True, metavar="YYYY-MM", help="요약할 달")
    summary.add_argument(
        "--top", default=str(DEFAULT_TOP), metavar="N", help=f"지출 상위 카테고리 수 (기본 {DEFAULT_TOP})"
    )

    # ---- budget set / list ----
    budget = add_command(commands, "budget", None, "예산 설정/조회")
    budget_actions = budget.add_subparsers(title="하위 명령", metavar="<set|list>", required=True)
    budget_set = add_command(
        budget_actions, "set", cmd_budget_set,
        "월 예산 설정 (같은 달에 다시 하면 금액을 바꾼다)",
        example="budget set --month 2024-01 --amount 500000",
    )
    budget_set.add_argument("--month", required=True, metavar="YYYY-MM", help="예산을 정할 달")
    budget_set.add_argument("--amount", required=True, metavar="AMOUNT", help="예산 금액 (양수)")
    add_command(budget_actions, "list", cmd_budget_list, "설정된 예산 목록", example="budget list")

    # ---- category add / list / remove ----
    category = add_command(commands, "category", None, "카테고리 관리")
    category_actions = category.add_subparsers(title="하위 명령", metavar="<add|list|remove>", required=True)
    add_command(
        category_actions, "add", cmd_category_add,
        "카테고리 추가 (대화형: 이름 입력)",
        example="category add",
    )
    add_command(category_actions, "list", cmd_category_list, "카테고리 목록", example="category list")
    add_command(
        category_actions, "remove", cmd_category_remove,
        "카테고리 삭제 (대화형: 이름 입력. 사용 중이면 삭제를 막는다)",
        example="category remove",
    )

    # ---- update ----
    update = add_command(
        commands, "update", cmd_update,
        "거래 수정 (옵션으로 준 항목만 바꾼다)",
        example="update --id TX-000001 --amount 20000 --memo 저녁",
    )
    update.add_argument("--id", required=True, metavar="ID", help="수정할 거래 id (예: TX-000001)")
    update.add_argument("--date", metavar="YYYY-MM-DD", help="새 날짜")
    update.add_argument("--type", metavar="TYPE", help="새 타입 (income/expense)")
    update.add_argument("--category", metavar="NAME", help="새 카테고리 (등록된 것만)")
    update.add_argument("--amount", metavar="AMOUNT", help="새 금액 (양수)")
    update.add_argument("--memo", metavar="MEMO", help='새 메모 (지우려면 --memo "")')
    update.add_argument("--tags", metavar="TAGS", help='새 태그, 쉼표로 구분 (지우려면 --tags "")')

    # ---- delete ----
    delete = add_command(commands, "delete", cmd_delete, "거래 삭제", example="delete --id TX-000001")
    delete.add_argument("--id", required=True, metavar="ID", help="삭제할 거래 id (예: TX-000001)")

    # ---- import ----
    import_ = add_command(
        commands, "import", cmd_import,
        "CSV 가져오기 (헤더: date,type,category,amount,memo,tags)",
        example="import --from import.csv",
    )
    import_.add_argument("--from", dest="source", required=True, metavar="CSV", help="가져올 CSV 파일 (UTF-8)")

    # ---- export ----
    export = add_command(
        commands, "export", cmd_export,
        "CSV 내보내기 (--month 또는 --from 과 --to 가 꼭 있어야 한다)",
        example="export --out export.csv --month 2024-01",
    )
    export.add_argument("--out", required=True, metavar="CSV", help="만들 CSV 파일 (.csv)")
    export.add_argument("--month", metavar="YYYY-MM", help="이 달의 거래만")
    export.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="이 날짜부터")
    export.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="이 날짜까지")

    # ---- backup (보너스 1) ----
    add_command(
        commands, "backup", cmd_backup,
        "저장 파일 전체를 날짜·시각이 붙은 zip 으로 백업",
        example="backup",
    )

    # ---- recurring add / list / remove / apply (보너스 2) ----
    recurring = add_command(commands, "recurring", None, "반복 내역 (월급·월세처럼 매월 반복되는 거래)")
    recurring_actions = recurring.add_subparsers(
        title="하위 명령", metavar="<add|list|remove|apply>", required=True
    )
    add_command(recurring_actions, "add", cmd_recurring_add, "반복 규칙 등록 (대화형)", example="recurring add")
    add_command(recurring_actions, "list", cmd_recurring_list, "반복 규칙 목록", example="recurring list")
    recurring_remove = add_command(
        recurring_actions, "remove", cmd_recurring_remove,
        "반복 규칙 삭제",
        example="recurring remove --id RC-000001",
    )
    recurring_remove.add_argument("--id", required=True, metavar="ID", help="삭제할 규칙 id (예: RC-000001)")
    recurring_apply = add_command(
        recurring_actions, "apply", cmd_recurring_apply,
        "그 달의 반복 거래를 만든다 (이미 만든 달은 건너뛴다)",
        example="recurring apply --month 2024-02",
    )
    recurring_apply.add_argument("--month", required=True, metavar="YYYY-MM", help="거래를 만들 달")

    return parser


# ---------------------------------------------------------------------------
# 4. 실행
# ---------------------------------------------------------------------------

@handle_errors
def main(argv: Sequence[str] | None = None) -> int:
    """프로그램의 시작점. 반환값이 곧 종료 코드다. (0 = 정상, 그 외 = 오류)

    명령줄 해석 → 저장 폴더 준비 → 명령 함수 실행. 도중에 나는 예외는 handle_errors 가 받는다.
    """
    args = build_parser().parse_args(argv)
    data_dir: Path = getattr(args, "data_dir", DEFAULT_DATA_DIR)

    ledger = Ledger(data_dir)
    created = ledger.initialize()  # 저장 폴더·파일이 없으면 만든다 (처음 실행)
    setup_logging(data_dir / LOG_FILE)
    if created:
        print(f"[안내] 저장 파일을 새로 만들었습니다: {data_dir} ({', '.join(path.name for path in created)})")
        print("[안내] 거래를 추가하려면 먼저 category add 로 카테고리를 등록하세요.")

    handler: Handler = args.handler
    handler(ledger, args)
    return EXIT_OK
