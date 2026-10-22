"""출력 포맷터 — 데이터를 '화면에 찍을 문자열'로 바꾸는 일만 한다. (보너스 3: 표 정렬)

외부 라이브러리 없이 표를 맞추려면 '글자 수'가 아니라 '화면에서 차지하는 폭'을 알아야 한다.
한글은 한 글자가 영문 두 글자만큼 넓기 때문에 len("점심") == 2 지만 화면 폭은 4칸이다.
→ unicodedata.east_asian_width 로 넓은 글자(W/F)는 2칸으로 계산한다.
"""

import sys
import unicodedata
from collections.abc import Sequence

from budget_app.models import Budget, Category, MonthlySummary, RecurringRule, Transaction


# ---- 공통 --------------------------------------------------------------------

def print_error(message: str, hint: str = "") -> None:
    """오류는 표준 에러(stderr)로 '[오류] 원인 / [힌트] 해결책' 형태로 출력한다."""
    print(f"[오류] {message}", file=sys.stderr)
    if hint:
        print(f"[힌트] {hint}", file=sys.stderr)


def money(amount: int) -> str:
    """15000 → '15,000원'"""
    return f"{amount:,}원"


def display_width(text: str) -> int:
    """화면 폭. 한글·한자 같은 넓은 글자는 2칸, 나머지는 1칸."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, width: int, align: str) -> str:
    """화면 폭 기준으로 공백을 채운다. align: 'left' 또는 'right'"""
    spaces = " " * (width - display_width(text))
    return spaces + text if align == "right" else text + spaces


def render_table(headers: Sequence[str], rows: Sequence[Sequence[str]], aligns: Sequence[str]) -> str:
    """헤더 + 구분선 + 행들을 칸 맞춤한 문자열로 만든다.

    ID        | 날짜       | 금액
    ----------+------------+--------
    TX-000001 | 2024-01-15 | 15,000원
    """
    # 각 열의 폭 = 그 열(헤더 포함)에서 가장 넓은 칸의 폭
    widths = [max(display_width(cell) for cell in column) for column in zip(headers, *rows)]
    lines = [" | ".join(_pad(h, w, "left") for h, w in zip(headers, widths)).rstrip()]
    lines.append("-+-".join("-" * w for w in widths))
    for row in rows:
        cells = (_pad(cell, w, a) for cell, w, a in zip(row, widths, aligns))
        lines.append(" | ".join(cells).rstrip())
    return "\n".join(lines)


# ---- 명령별 출력 -------------------------------------------------------------

def format_transactions(transactions: Sequence[Transaction]) -> str:
    headers = ["ID", "날짜", "타입", "카테고리", "금액", "메모", "태그"]
    aligns = ["left", "left", "left", "left", "right", "left", "left"]
    rows = [
        [tx.id, tx.date, tx.type, tx.category, money(tx.amount), tx.memo, ",".join(tx.tags)]
        for tx in transactions
    ]
    return render_table(headers, rows, aligns)


def format_categories(categories: Sequence[Category]) -> str:
    return "\n".join(f"- {category.name}" for category in categories)


def format_budgets(budgets: Sequence[Budget]) -> str:
    rows = [[b.month, money(b.amount)] for b in budgets]
    return render_table(["월", "예산"], rows, ["left", "right"])


def format_rules(rules: Sequence[RecurringRule]) -> str:
    headers = ["ID", "매월", "타입", "카테고리", "금액", "메모", "생성한 달"]
    aligns = ["left", "right", "left", "left", "right", "left", "left"]
    rows = [
        [r.id, f"{r.day}일", r.type, r.category, money(r.amount), r.memo, ",".join(r.applied_months)]
        for r in rules
    ]
    return render_table(headers, rows, aligns)


def format_summary(summary: MonthlySummary, top: int) -> str:
    lines = [f"[{summary.month} 월별 요약]"]
    if summary.count == 0:
        lines.append("데이터 없음: 이 달에 기록된 거래가 없습니다.")
    else:
        lines += [
            f"총 수입: {money(summary.income)}",
            f"총 지출: {money(summary.expense)}",
            f"잔액: {money(summary.balance)}",
        ]

    usage = summary.usage_percent
    if summary.budget is None or usage is None:
        lines.append(f"예산: 미설정 (설정: budget set --month {summary.month} --amount 금액)")
    else:
        lines.append(f"예산: {money(summary.budget)} (사용률 {usage:.1f}%)")
        if summary.over_budget:
            lines.append(f"초과 여부: 초과 - [경고] 예산보다 {money(summary.over_budget)} 더 썼습니다!")
        else:
            lines.append(f"초과 여부: 초과 아님 (남은 예산 {money(summary.budget - summary.expense)})")

    if summary.count:
        lines.append("")
        lines.append(f"지출 TOP {top}")
        if not summary.top_categories:
            lines.append("(지출 내역 없음)")
        for rank, (category, amount) in enumerate(summary.top_categories, start=1):
            lines.append(f"{rank}) {category} {money(amount)}")
    return "\n".join(lines)
