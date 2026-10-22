"""타입 힌트가 무엇을 잡아 주는지 직접 보는 파일. (실행하는 파일이 아니다)

프로젝트 폴더(inner/B2_1)에서 검사기를 돌린다.

    uvx mypy docs/type_demo.py          # uv 가 있을 때
    mypy docs/type_demo.py              # pip install mypy 로 설치했을 때

아래에는 '약속을 어기는 코드'를 일부러 적어 두었다. 검사기는 코드를 실행하지 않고 읽기만 해서
그 줄들을 찾아낸다. reveal_type(x) 는 "x 의 타입을 무엇으로 알고 있는지 알려 달라"는 표시다.

mypy 는 개발할 때 쓰는 도구다. 프로그램(budget_app)은 여전히 표준 라이브러리만 쓴다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 어디서 열어도 budget_app 을 찾을 수 있게

from budget_app.cli import ask  # noqa: E402
from budget_app.models import Transaction, parse_amount, parse_date, parse_type  # noqa: E402
from budget_app.services import Ledger  # noqa: E402
from budget_app.storage import TransactionRepository  # noqa: E402


def examples(ledger: Ledger, repository: TransactionRepository) -> None:
    # 1. 없을 수도 있다는 약속 — find 는 `Transaction | None` 을 돌려준다.
    #    None 인지 확인하지 않고 바로 쓰면 잡힌다. (services.py 의 get 이 `if tx is None:` 을 두는 이유)
    found = repository.find("TX-000001")
    print(found.amount)

    # 2. 허용 값 제한 — type 은 "income" / "expense" 둘 중 하나라고 적어 두었다. (Literal)
    Transaction(id="TX-000001", type="spend", date="2024-01-15", amount=1, category="food")

    # 3. 데코레이터를 거쳐도 그대로 — list_recent 에는 @measure_time 이 붙어 있지만
    #    매개변수와 반환 타입이 원래대로 보인다. (ParamSpec)
    reveal_type(ledger.transactions.list_recent)
    ledger.transactions.list_recent("10")

    # 4. 넘겨준 함수에 따라 결과 타입이 정해진다 — ask 는 검증 함수가 돌려주는 타입을 그대로 돌려준다. (TypeVar)
    reveal_type(ask("금액: ", parse_amount))
    reveal_type(ask("날짜: ", parse_date))
    reveal_type(ask("타입: ", parse_type))

    # 5. 금액은 int 라는 약속 — 문자열 "15000" 을 넘기면 잡힌다.
    ledger.transactions.add("2024-01-15", "expense", "food", "15000")

    # 6. 저장소마다 다루는 모델이 정해져 있다 — TransactionRepository 의 stream 은 Transaction 을 준다. (Generic)
    #    그래서 오타(amout)도 잡힌다.
    for tx in repository.stream():
        reveal_type(tx)
        print(tx.amout)


if __name__ == "__main__":
    print("이 파일은 실행하는 파일이 아닙니다. 프로젝트 폴더에서 아래처럼 검사해 보세요.")
    print("    uvx mypy docs/type_demo.py")
