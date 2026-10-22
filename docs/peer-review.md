# 동료 평가 대비 — 평가 질문 16문항 답변

동료 평가 질문은 **4개 항목, 16문항**이다. 이 문서는 그 **순서와 번호(1-1 … 4-3)를 그대로** 따라 문항마다 ① 말로 할 답 ② 시연 방법 ③ 코드 위치 ④ 실제로 확인한 결과를 적었다. 발표할 때 이 문서를 열어 두고 위에서 아래로 따라가면 된다. 질문은 원문을 옮기지 않고 줄여 썼다. 코드 링크의 줄 번호는 2026-09-30 기준이다.

| 평가 항목 | 문항 수 | 이 문서 |
| --- | ---: | --- |
| 항목 1. 기능 동작 검증 | 7 | 1-1 ~ 1-7 |
| 항목 2. 코드 구조 및 설계 | 3 | 2-1 ~ 2-3 |
| 항목 3. 핵심 기술 원리 적용 | 3 | 3-1 ~ 3-3 |
| 항목 4. 심층 인터뷰 | 3 | 4-1 ~ 4-3 |

명세 3장 "과제 목표"의 다섯 가지(스스로 설명할 수 있어야 하는 것)는 [부록 A](#부록-a-과제-목표-5가지와-문항)에서 문항과 이어 놓았다.

## 어떻게 확인했나 (2026-09-30)

- **자동 테스트**: `python3 -m unittest discover -s tests` — 205개 전부 통과. Python 3.10.20, 3.11.16, 3.14.7 세 버전에서 돌렸다.
- **시연 순서 그대로 실행**: 아래 [시연 준비](#시연-준비)부터 각 문항의 시연 명령을 빈 폴더에서 차례로 실행했고, 이 문서의 출력은 그때 나온 것이다.
- **10만 건 측정**: `python3 tests/benchmark.py --records 100000` (3-1, 4-2 의 수치).
- **타입 검사**: `uvx mypy budget_app --strict` (mypy 2.3.1) → `Success: no issues found in 9 source files`. 3-3 의 출력은 이때 나온 것이다.

## 한눈에 보기

| 문항 | 질문 (줄임) | 결과 | 핵심 |
| --- | --- | --- | --- |
| 1-1 | 8개 명령이 요구대로 동작하나 | 충족 | add 는 대화형, 나머지는 옵션. 목록·검색은 최신순 |
| 1-2 | 다시 실행해도 데이터가 남나 (파일 3개 이상) | 충족 | 명령 하나가 프로세스 하나. `data/` 에 jsonl 4개 |
| 1-3 | category add/list/remove, 사용 중 삭제 처리 | 충족 | 사용 중이면 삭제를 막는다 |
| 1-4 | budget set 저장, summary 에 사용률/초과 여부 | 충족 | `사용률 105.0%`, `초과 여부: 초과 - [경고]` |
| 1-5 | import/export 가 CSV 스키마대로 | 충족 | UTF-8, 헤더, 6개 컬럼. export 한 파일을 그대로 import 가능 |
| 1-6 | 오류에서 스택트레이스 없이 메시지 + 힌트 | **충족 · 주의** | 명령 형식 오류의 원인 부분은 argparse 의 영어 문구가 그대로 나온다 |
| 1-7 | 오류일 때 종료 코드가 0이 아닌가 | 충족 | 오류 1, 형식 오류 2, 중단 130 |
| 2-1 | 모듈 분리와 각 모듈의 책임 | 충족 | 바뀌는 이유가 다른 것끼리 나눔. 방향은 위 → 아래 |
| 2-2 | 클래스의 책임 경계 | 충족 | 모양(모델) / 파일(저장소) / 규칙(서비스) |
| 2-3 | 파일 기반 update/delete 를 안전하게 | 충족 | 임시 파일에 전부 쓰고 `os.replace` |
| 3-1 | list/search 의 제너레이터 스트리밍 | **충족 · 주의** | 10만 건에서 0.05MB. 단 search 에 `--limit` 이 없으면 맞은 거래를 모은다 |
| 3-2 | 데코레이터로 분리한 공통 기능 | 충족 | 오류 처리 / 실행 기록 / 시간 측정 |
| 3-3 | 타입 힌트의 이점을 실제 코드로 확인 | 충족 | mypy `--strict` 통과. 약속을 어긴 코드 5가지를 검사기가 잡아내는 것을 시연 |
| 4-1 | JSONL 과 CSV 비교, 선택 근거 | 충족 | 내부 JSONL, 외부 CSV |
| 4-2 | 10만 건이면 병목과 개선 | 충족 | 조회 0.35초, 수정·삭제 1.3초 (측정) |
| 4-3 | import 에 깨진 행이 섞이면 | 충족 | 부분 성공 + 줄 번호·이유 보고. 파일을 못 읽으면 전부 취소 |

**시연 전에 알아 둘 다섯 가지**

1. 이 맥에는 `python` 명령이 없다. `python3` 로 실행한다 (`python3 --version` → 3.10.20).
2. 카테고리가 없으면 `add` 가 막힌다. 시연은 `category add` 부터 한다.
3. 종료 코드는 명령 바로 다음에 `echo $?` 로 본다. 사이에 다른 명령을 치면 값이 바뀐다.
4. **3-3** 타입 힌트 시연은 `uvx mypy ...` 로 한다. mypy 는 이 맥에 받아 두어서 인터넷 없이도 된다. 다른 컴퓨터에서는 `pip install mypy` 가 먼저 필요하다.
5. **1-6** `delete` 처럼 필수 옵션을 빼먹으면 `the following arguments are required: --id` 처럼 영어가 섞여 나온다. 형식(`[오류]` + `[힌트]`, 종료 코드 2)은 같다.

## 시연 준비

`inner/B2_1` 에서 실행한다. `data` 폴더가 이미 있으면 지우고 시작하면 아래 출력과 id 가 똑같이 나온다.

```bash
cd inner/B2_1
rm -rf data                                  # 처음 상태로 (시연용 데이터만 있을 때)

python3 -m budget_app category add           # food 입력
python3 -m budget_app category add           # transport
python3 -m budget_app category add           # salary
python3 -m budget_app category add           # rent
python3 -m budget_app import --from docs/sample-import.csv
```

마지막 명령의 출력은 이렇다. [docs/sample-import.csv](sample-import.csv) 에는 정상 6줄과 일부러 틀린 2줄이 들어 있다.

```text
[완료] imported=6, skipped=2
  - 8번째 줄 건너뜀: 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
  - 9번째 줄 건너뜀: 등록되지 않은 카테고리입니다: cafe
[안내] 건너뛴 줄만 고쳐서 새 CSV 로 다시 import 하세요.
       (같은 파일을 그대로 다시 넣으면 이미 들어간 거래가 중복됩니다)
```

---

## 항목 1. 기능 동작 검증

### 1-1. add / list / search / summary / export / import / update / delete 가 요구대로 동작하는가 — 충족

> 여덟 명령이 모두 동작합니다. `add` 는 질문에 하나씩 답하는 대화형이고, 나머지는 `--옵션` 으로 받습니다. `update` 는 옵션 방식으로 고정했습니다. 목록과 검색 결과는 최신순, 즉 날짜가 늦은 것부터이고 같은 날이면 나중에 등록한 것이 먼저 나옵니다.

- **시연**

  ```bash
  python3 -m budget_app add                                   # 2024-01-25 / expense / food / 12000 / 김밥 / meal
  python3 -m budget_app list --limit 3
  python3 -m budget_app search --category food --tag meal
  python3 -m budget_app summary --month 2024-01
  python3 -m budget_app update --id TX-000004 --amount 18000 --memo "점심 + 커피"
  python3 -m budget_app delete --id TX-000002
  python3 -m budget_app export --out out.csv --month 2024-01
  ```

  `add` 에서 날짜를 `2024-13-40` 으로 한 번 틀리게 넣어 보면 다시 묻는 것까지 보여 줄 수 있다.
- **근거**: 명령마다 함수가 하나다. [`cmd_add`](../budget_app/cli.py#L102), [`cmd_list`](../budget_app/cli.py#L117), [`cmd_search`](../budget_app/cli.py#L127), [`cmd_summary`](../budget_app/cli.py#L142), [`cmd_update`](../budget_app/cli.py#L188), [`cmd_delete`](../budget_app/cli.py#L204), [`cmd_import`](../budget_app/cli.py#L211), [`cmd_export`](../budget_app/cli.py#L223). 규칙은 [`TransactionService`](../budget_app/services.py#L108) 에 있다.
- **확인 결과** (시연 준비 직후, `add` 를 하기 전의 출력)

  ```text
  $ python3 -m budget_app list --limit 3
  ID        | 날짜       | 타입    | 카테고리 | 금액     | 메모      | 태그
  ----------+------------+---------+----------+----------+-----------+----------
  TX-000006 | 2024-02-01 | expense | food     |  8,000원 | 커피      | cafe
  TX-000005 | 2024-01-20 | expense | food     | 30,000원 | 저녁 회식 | meal,team
  TX-000004 | 2024-01-15 | expense | food     | 15,000원 | 점심      | meal
  (3건)

  $ python3 -m budget_app summary --month 2024-01
  [2024-01 월별 요약]
  총 수입: 3,000,000원
  총 지출: 215,000원
  잔액: 2,785,000원
  예산: 미설정 (설정: budget set --month 2024-01 --amount 금액)

  지출 TOP 3
  1) rent 150,000원
  2) food 45,000원
  3) transport 20,000원
  ```

  `add` 로 1월 25일 거래를 넣은 뒤 다시 `list --limit 3` 을 하면, 방금 넣은 TX-000007 이 맨 위가 아니라 두 번째에 온다. 등록 순서가 아니라 날짜 순서이기 때문이다.

  ```text
  TX-000006 | 2024-02-01 | expense | food     |  8,000원 | 커피      | cafe
  TX-000007 | 2024-01-25 | expense | food     | 12,000원 | 김밥      | meal
  TX-000005 | 2024-01-20 | expense | food     | 30,000원 | 저녁 회식 | meal,team
  ```

  자동 테스트: `tests/test_cli.py` 의 `AddTests`, `ListTests`, `SearchTests`, `SummaryBudgetTests`, `UpdateDeleteTests`, `ImportExportTests`.

### 1-2. 다시 실행해도 거래/카테고리/예산이 유지되는가 (저장 파일 3개 이상) — 충족

> 이 프로그램은 명령 하나를 실행하고 끝나는 구조라서, 방금 추가한 거래가 다음 명령에서 보인다는 것 자체가 파일에서 읽어 왔다는 뜻입니다. 저장 파일은 거래, 카테고리, 예산 세 개이고 보너스인 반복 규칙까지 네 개입니다. 형식은 한 줄에 JSON 하나인 JSONL 입니다.

- **시연**

  ```bash
  ls data
  cat data/transactions.jsonl
  cat data/categories.jsonl
  python3 -m budget_app budget set --month 2024-01 --amount 500000
  cat data/budgets.jsonl
  python3 -m budget_app list        # 새로 실행한 프로세스가 파일에서 읽어 온다
  ```

- **근거**: 파일 이름은 [`Ledger.__init__`](../budget_app/services.py#L473) 한 곳에 있다. 없으면 [`ensure_file`](../budget_app/storage.py#L44) 이 만든다. 한 줄로 바꾸는 곳은 [`_to_line`](../budget_app/storage.py#L146).
- **확인 결과**: `ls data` → `app.log  budgets.jsonl  categories.jsonl  recurring.jsonl  transactions.jsonl`. 자동 테스트 `StorageTests.test_data_survives_restart` 가 명령마다 새 프로세스를 띄워 거래·카테고리·예산이 보이는지, jsonl 3개에 내용이 있는지 확인한다.

### 1-3. category add/list/remove 가 동작하는가 (사용 중인 카테고리 삭제 처리) — 충족

> 추가와 삭제는 이름을 물어보는 대화형이고, 목록은 가나다순입니다. 거래가 쓰고 있는 카테고리는 삭제를 막습니다. 지워 버리면 거래는 남았는데 카테고리는 없는 모순이 생기기 때문입니다. 막을 때 몇 건이 쓰고 있는지와 어떻게 하면 지울 수 있는지를 알려 줍니다.

- **시연**

  ```bash
  python3 -m budget_app category add        # cafe 입력
  python3 -m budget_app category list
  python3 -m budget_app category remove     # cafe 입력 → 삭제됨 (쓰는 거래가 없다)
  python3 -m budget_app category remove     # food 입력 → 막힘
  echo $?
  ```

- **근거**: [`CategoryService.remove`](../budget_app/services.py#L306) 가 거래 파일을 한 줄씩 읽으며 그 카테고리를 쓰는 건수를 센다. 거래 저장소를 직접 받기 때문에 가능하다 ([`CategoryService`](../budget_app/services.py#L280)).
- **확인 결과**

  ```text
  삭제할 카테고리명: food
  [오류] 사용 중인 카테고리는 삭제할 수 없습니다: food (거래 4건, 반복 규칙 0건)
  [힌트] search --category food 로 찾아 update 로 카테고리를 바꾸거나 delete 한 뒤 다시 시도하세요.
  ```

  종료 코드 1. 자동 테스트 `CategoryTests.test_remove_is_blocked_while_in_use`.

### 1-4. budget set 이 저장되고, summary 에 사용률/초과 여부가 나오는가 — 충족

> `budget set` 은 그 달의 예산을 `budgets.jsonl` 에 저장합니다. 같은 달에 다시 설정하면 줄이 늘지 않고 금액이 바뀝니다. 예산이 있으면 `summary` 에 사용률과 초과 여부 줄이 함께 나오고, 넘으면 경고 문구가 붙습니다.

- **시연**

  ```bash
  python3 -m budget_app budget set --month 2024-01 --amount 500000
  python3 -m budget_app summary --month 2024-01      # 사용률 42.0%, 초과 아님
  python3 -m budget_app budget set --month 2024-01 --amount 200000
  python3 -m budget_app summary --month 2024-01      # 사용률 105.0%, 경고
  cat data/budgets.jsonl                             # 한 줄뿐이다
  ```

- **근거**: [`set_budget`](../budget_app/services.py#L337) → [`upsert`](../budget_app/storage.py#L96)(같은 달이면 교체). 계산은 [`usage_percent`](../budget_app/models.py#L318), [`over_budget`](../budget_app/models.py#L324). 출력은 [`format_summary`](../budget_app/formatter.py#L88).
- **확인 결과**

  1-1 의 시연(추가 1건, 수정 1건, 삭제 1건)까지 한 상태라 1월 지출은 210,000원이다.

  ```text
  총 지출: 210,000원
  예산: 500,000원 (사용률 42.0%)
  초과 여부: 초과 아님 (남은 예산 290,000원)

  총 지출: 210,000원
  예산: 200,000원 (사용률 105.0%)
  초과 여부: 초과 - [경고] 예산보다 10,000원 더 썼습니다!

  $ cat data/budgets.jsonl
  {"month": "2024-01", "amount": 200000}
  ```

### 1-5. import/export 가 명시된 CSV 스키마(UTF-8, 헤더, 컬럼)로 동작하는가 — 충족

> CSV 는 UTF-8 이고 첫 줄이 헤더 `date,type,category,amount,memo,tags` 입니다. 앞의 네 개가 필수이고 memo 와 tags 는 선택입니다. export 는 `--month` 나 `--from`과 `--to` 중 하나가 꼭 있어야 하고, export 한 파일은 그대로 다시 import 할 수 있습니다. 태그가 여러 개면 쉼표가 들어가므로 csv 모듈이 따옴표로 감싸 줍니다.

- **시연**

  ```bash
  python3 -m budget_app export --out out.csv --month 2024-01
  cat out.csv
  python3 -m budget_app export --out out.csv                       # 조건이 없으면 오류
  python3 -m budget_app import --from docs/sample-import.csv       # 시연 준비에서 이미 했다
  ```

- **근거**: 컬럼 정의 [`CSV_COLUMNS`](../budget_app/storage.py#L204). 쓰기 [`write_transactions_csv`](../budget_app/storage.py#L239), 읽기 [`read_csv_rows`](../budget_app/storage.py#L208)(엑셀의 BOM 도 받도록 `utf-8-sig`). 조건 검사는 [`export_csv`](../budget_app/services.py#L259), 행 검증은 [`_from_csv_row`](../budget_app/services.py#L246).
- **확인 결과**

  ```text
  $ python3 -m budget_app export --out out.csv --month 2024-01
  [완료] out.csv (5 records)
  $ head -3 out.csv
  date,type,category,amount,memo,tags
  2024-01-05,expense,rent,150000,월세,"home,fixed"
  2024-01-14,income,salary,3000000,월급,
  $ python3 -m budget_app export --out out.csv
  [오류] export 에는 기간 조건이 필요합니다.
  [힌트] --month 2024-01 또는 --from 2024-01-01 --to 2024-01-31 을 붙이세요.
  ```

  자동 테스트 `ImportExportTests.test_export_then_import_into_another_ledger` 가 export → 다른 폴더에 import → 저장 파일이 같은지까지 본다.

### 1-6. 잘못된 입력/파일 오류에서 스택트레이스 없이 오류 메시지와 해결 힌트가 나오는가 — 충족 · 주의

> 오류는 항상 `[오류] 원인` 과 `[힌트] 해결 방법` 두 줄로 나옵니다. 예외 클래스가 원인과 힌트를 같이 들고 다니고, `main` 에 붙인 `handle_errors` 데코레이터 한 곳에서 받아 출력합니다. 예상하지 못한 오류, 즉 버그는 화면에 "예상하지 못한 오류가 발생했습니다" 만 보여 주고 자세한 내용은 `data/app.log` 에 남깁니다. 대화형 입력에서는 끝내지 않고 같은 질문을 다시 합니다.

- **시연** (네 종류)

  ```bash
  python3 -m budget_app add                          # 날짜에 2024-13-40 → 다시 묻는다 (Ctrl+C 로 빠져나온다)
  python3 -m budget_app delete --id TX-999999        # 없는 데이터
  python3 -m budget_app import --from nope.csv       # 없는 파일
  echo '깨진 줄' >> data/transactions.jsonl          # 저장 파일을 일부러 망가뜨린다
  python3 -m budget_app list                         # 몇 번째 줄이 손상됐는지 알려 준다
  ```

  마지막 시연 뒤에는 `data/transactions.jsonl` 을 열어 맨 끝의 `깨진 줄` 을 지운다.
- **근거**: [`AppError`](../budget_app/errors.py#L11)(`message` + `hint`), [`handle_errors`](../budget_app/decorators.py#L52), [`print_error`](../budget_app/formatter.py#L17), 다시 묻기는 [`ask`](../budget_app/cli.py#L64), 명령 형식 오류는 [`error`](../budget_app/cli.py#L297), 손상된 줄은 [`_damaged`](../budget_app/storage.py#L158).
- **확인 결과**

  ```text
  날짜(YYYY-MM-DD): 2024-13-40
  [오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
  [힌트] 예: 2024-01-15
  날짜(YYYY-MM-DD):

  [오류] CSV 파일을 찾을 수 없습니다: nope.csv
  [힌트] 경로와 파일 이름을 다시 확인하세요.

  [오류] transactions.jsonl 파일이 손상되었습니다 (7번째 줄).
  [힌트] data/transactions.jsonl 를 열어 해당 부분을 고치거나, backup 으로 만든 zip 에서 복구하세요.
  ```

  자동 테스트는 오류 상황 50여 가지에서 종료 코드가 0이 아니고, stderr 에 `[오류]`, `[힌트]` 가 있고, `Traceback` 이 없는지 본다 (`DecoratorAndErrorTests`, `RunAndInputTests.test_usage_errors`).
- **주의**: 명령 형식이 틀린 경우(없는 명령, 빠진 옵션)는 원인 부분에 argparse 가 만든 영어가 그대로 나온다. 물으면 "형식 오류는 argparse 가 잡는데, 그 출력도 같은 `[오류]/[힌트]` 모양과 종료 코드 2 로 맞췄고 문구 번역까지는 하지 않았다"고 답한다.

  ```text
  $ python3 -m budget_app delete
  [오류] 명령 형식이 올바르지 않습니다: the following arguments are required: --id
  [힌트] 사용법 보기: python -m budget_app delete --help
  ```

### 1-7. 오류 상황에서 종료 코드가 0이 아님을 확인할 수 있는가 — 충족

> `main` 함수가 돌려준 숫자를 `sys.exit` 에 넘겨서 종료 코드로 씁니다. 정상은 0, 오류는 1, 명령 형식 오류는 2, 입력 도중 중단은 130 입니다. 명령 바로 다음에 `echo $?` 로 확인할 수 있습니다.

- **시연**

  ```bash
  python3 -m budget_app list;                    echo "종료 코드 $?"    # 0
  python3 -m budget_app delete --id TX-999999;   echo "종료 코드 $?"    # 1
  python3 -m budget_app summary;                 echo "종료 코드 $?"    # 2 (--month 가 없다)
  python3 -m budget_app add                                             # 질문에서 Ctrl+C
  echo "종료 코드 $?"                                                    # 130
  ```

- **근거**: [`sys.exit(main())`](../budget_app/__main__.py#L11), 코드 값은 [`EXIT_OK`](../budget_app/decorators.py#L27) ~ [`EXIT_CANCELLED`](../budget_app/decorators.py#L30), 어떤 예외가 어떤 코드가 되는지는 [`handle_errors`](../budget_app/decorators.py#L52).
- **확인 결과**: 위 순서대로 0, 1, 2, 130 이 나왔다. 자동 테스트의 오류 검사는 전부 종료 코드까지 비교한다.

---

## 항목 2. 코드 구조 및 설계

### 2-1. 3개 이상 모듈로 분리했고, 각 모듈의 책임을 어떻게 나눴는가 — 충족

> "무엇이 바뀌면 이 파일을 고쳐야 하는가"를 기준으로 나눴습니다. 화면이나 명령 옵션이 바뀌면 `cli.py`, 업무 규칙이 바뀌면 `services.py`, 저장 형식이 바뀌면 `storage.py`, 데이터 항목이나 검증 규칙이 바뀌면 `models.py` 입니다. 의존은 위에서 아래로만 흐릅니다. 그래서 JSONL 을 SQLite 로 바꾸더라도 `storage.py` 만 고치면 되고, CLI 를 웹으로 바꾸더라도 서비스 아래는 그대로 씁니다. 여기에 여러 계층이 같이 쓰는 도구 세 개, 예외·데코레이터·출력 포맷터가 있습니다.

| 모듈 | 책임 | 하지 않는 일 |
| --- | --- | --- |
| `cli.py` | 명령줄 해석, 입력 받기, 서비스 호출, 출력 | 규칙 판단, 파일 접근 (`storage` 를 import 하지도 않는다) |
| `services.py` | 업무 규칙 | `print`/`input`, JSON·CSV 문법 |
| `storage.py` | 파일 읽기/쓰기 | 규칙 판단 |
| `models.py` | 데이터 모양과 값 검증 | 파일, 화면 |
| `errors.py` / `decorators.py` / `formatter.py` | 원인+힌트 예외 / 공통 관심사 / 출력 문자열 | — |

- **시연**: 각 파일 맨 위 설명글을 보여 준다. 그리고 구조를 코드로 확인하는 테스트를 돌린다.

  ```bash
  python3 -m unittest tests.test_spec_static.StructureTests -v
  ```

- **근거**: 조립은 [`Ledger`](../budget_app/services.py#L466) 한 곳. 흐름의 시작은 [`main`](../budget_app/cli.py#L487).
- **확인 결과**: `test_layers_depend_downward_only`(import 방향), `test_only_cli_talks_to_the_user`(`input` 은 cli 에만, 모델·저장소·서비스에는 `print` 도 없음), `test_only_storage_opens_files`(파일 열기는 storage 에만) 통과.
- **예를 하나 들어 달라고 하면**: "등록되지 않은 카테고리는 거부한다"는 규칙은 서비스의 [`registered_category`](../budget_app/services.py#L93) 에 있다. 모델에 두지 않은 이유는 모델이 파일(등록 목록)을 몰라야 하기 때문이고, CLI 에 두지 않은 이유는 `add`, `update`, `import` 세 경로가 같은 규칙을 써야 하기 때문이다.

### 2-2. 2개 이상의 클래스에 부여한 책임 경계를 어떻게 정했는가 — 충족

> 클래스는 세 종류입니다. 데이터의 모양과 검증을 가진 모델, 파일 하나를 읽고 쓰는 저장소, 규칙을 가진 서비스입니다. 같은 "거래"에 대해서도 `Transaction` 은 값이 올바른지만 알고, `TransactionRepository` 는 그것을 파일에 어떻게 쓰는지만 알고, `TransactionService` 는 언제 추가를 허용하는지를 압니다. 경계를 정한 기준은 "이 클래스가 몰라도 되는 것을 모르게 한다"입니다.

| 클래스 | 아는 것 | 모르는 것 |
| --- | --- | --- |
| [`Transaction`](../budget_app/models.py#L169) (dataclass) | 필드 7개, 값이 올바른지 (`__post_init__`) | 파일, 다른 거래, 등록된 카테고리 목록 |
| [`JsonlRepository`](../budget_app/storage.py#L30) 와 자식 4개 | 파일 경로, 한 줄 ↔ 객체 변환, 안전하게 다시 쓰기 | 어떤 거래가 허용되는지 |
| [`TransactionService`](../budget_app/services.py#L108) | 등록된 카테고리만 허용, 최신순, export 조건 | 화면, JSON 문법 |
| [`CategoryService`](../budget_app/services.py#L280) | 중복 금지, 사용 중이면 삭제 금지 | 〃 |
| [`BudgetService`](../budget_app/services.py#L330) | 예산 설정, 월별 요약 계산 | 〃 |
| [`Ledger`](../budget_app/services.py#L466) | 어떤 서비스가 어떤 파일을 쓰는지 (조립) | 규칙 |

- **덧붙일 말**: 서비스끼리는 서로를 부르지 않는다. 거래 서비스는 카테고리가, 카테고리 서비스는 거래가 필요해서 서로 부르게 하면 맞물린다. 그래서 필요한 **저장소**를 직접 받게 했다. 저장소 4개는 [`JsonlRepository`](../budget_app/storage.py#L30) 하나를 상속하고 `model` 과 `key_field` 두 가지만 다르게 정한다 ([`TransactionRepository`](../budget_app/storage.py#L165)).
- **확인 결과**: static `test_at_least_two_classes_and_dataclass`.

### 2-3. 파일 기반 update/delete 를 어떻게 안전하게 처리했는가 — 충족

> 텍스트 파일은 가운데 한 줄만 고칠 수 없어서 전체를 다시 써야 합니다. 원본에 바로 덮어쓰면 쓰는 도중에 꺼졌을 때 반만 쓰인 파일이 남습니다. 그래서 같은 폴더의 임시 파일에 새 내용을 전부 쓰고, 디스크에 확실히 내린 다음, `os.replace` 로 원본과 바꿔치기합니다. 바꿔치기는 운영체제가 한 번에 처리하는 동작이라 파일은 "옛 내용" 아니면 "새 내용" 둘 중 하나로만 존재합니다. 도중에 오류가 나면 임시 파일만 지우고 원본은 그대로 둡니다.

- **순서** ([`_rewrite`](../budget_app/storage.py#L120))
  1. `transactions.jsonl.tmp` 를 새로 연다.
  2. 원본을 제너레이터로 한 줄씩 읽으며, 고칠 줄은 새 값으로 바꿔서(수정) 또는 빼고(삭제) 임시 파일에 쓴다.
  3. `flush` (파이썬 → 운영체제), [`os.fsync`](../budget_app/storage.py#L135) (운영체제 → 디스크).
  4. [`os.replace`](../budget_app/storage.py#L136) 로 교체.
  5. 어디서 실패하든 `finally` 가 임시 파일을 지운다.
- **그 밖의 안전장치**
  - 없는 id 는 파일을 건드리기 전에 걸러 낸다 ([`get`](../budget_app/services.py#L170)).
  - 잘못된 값으로의 수정은 새 `Transaction` 을 만드는 순간 검증에 걸려 쓰기까지 가지 않는다 ([`update`](../budget_app/services.py#L183)).
  - 손상된 줄이 있으면 다시 쓰기를 하지 않고 멈춘다. 건너뛰고 다시 쓰면 그 줄이 사라지기 때문이다 ([`stream`](../budget_app/storage.py#L54)).
  - 추가(append)할 때 파일이 줄바꿈 없이 끝나 있으면 줄바꿈부터 넣는다 ([`_last_line_is_cut`](../budget_app/storage.py#L150)).
- **시연**

  ```bash
  python3 -m unittest tests.test_storage.SafeWriteTests -v
  ```

- **확인 결과**: 7개 통과. `test_rewrite_failure_keeps_original`(쓰다가 예외 → 원본이 바이트 단위로 그대로, 임시 파일 없음), `test_replace_failure_keeps_original`(마지막 교체가 실패해도 같음), `test_rewrite_goes_through_temp_file_then_replace`(`.tmp` → 원본 순서로 교체).
- **한계를 물으면**: 두 프로그램이 동시에 쓰는 경우는 막지 않는다(잠금 없음). 그리고 매번 전체를 다시 쓰므로 느리다(4-2).

---

## 항목 3. 핵심 기술 원리 적용

### 3-1. list/search 를 제너레이터로 스트리밍 처리한 방식과 유리한 이유 — 충족 · 주의

> 저장소의 `stream` 은 `yield` 를 쓰는 제너레이터입니다. 파일을 한 줄 읽어 객체로 바꿔서 넘기고, 다음 값을 달라고 할 때까지 멈춰 있습니다. 그래서 파일이 아무리 커도 메모리에는 한 줄씩만 올라옵니다. 문제는 list 가 최신순이라는 점인데, 전부 모아서 정렬하지 않고 `heapq.nlargest` 를 씁니다. 이 함수는 흘러오는 거래를 하나씩 받으면서 "지금까지 본 것 중 가장 최신 N건"만 들고 있습니다. search 는 그 사이에 조건으로 거르는 제너레이터가 하나 더 끼어 있습니다. 읽기, 거르기, 고르기가 한 건씩 흐르는 구조입니다.

- **흐름**: [`stream`](../budget_app/storage.py#L54) (한 줄 읽어 `yield`) → [`matching`](../budget_app/services.py#L161) (조건에 맞는 것만 통과, search 만) → [`newest_first`](../budget_app/services.py#L72) 의 [`heapq.nlargest`](../budget_app/services.py#L85) (N건만 유지) → 표 출력
- **시연 1** — 제너레이터는 달라고 할 때만 읽는다.

  ```bash
  python3 -c "
  from pathlib import Path
  from budget_app.storage import TransactionRepository
  g = TransactionRepository(Path('data/transactions.jsonl')).stream()
  print(g)
  print(next(g))
  print(next(g))
  "
  ```

  ```text
  <generator object JsonlRepository.stream at 0x1095fd070>
  Transaction(id='TX-000001', type='expense', date='2024-01-05', amount=150000, category='rent', memo='월세', tags=['home', 'fixed'])
  Transaction(id='TX-000002', type='expense', date='2024-01-12', amount=20000, category='transport', memo='버스 카드', tags=[])
  ```

- **시연 2** — 10만 건에서 메모리를 잰다 (약 25초 걸린다).

  ```bash
  python3 tests/benchmark.py --records 100000
  ```

- **확인 결과** (거래 10만 건, 파일 13.7MB)

  | 방식 | 최대 메모리 |
  | --- | ---: |
  | 전부 list 로 읽기 (비교용) | 55.08 MB |
  | `list --limit 10` | 0.05 MB |
  | `search` 한 달 + 카테고리 | 0.28 MB |
  | `summary` | 0.05 MB |
  | `export` 전체 기간 | 0.19 MB |

  자동 테스트 `tests/test_streaming.py` 가 2만 건 파일에서 같은 것을 확인한다 (list 는 0.5MB 미만, 전부 읽으면 5MB 이상). `test_stream_reads_lazily` 는 뒤쪽 줄이 깨져 있어도 앞에서 찾으면 오류가 안 난다는 것으로 "필요한 만큼만 읽는다"를 보인다.
- **왜 유리한가**: 메모리가 파일 크기가 아니라 `--limit` 에 비례한다. 그리고 `find` 처럼 찾는 순간 읽기를 멈출 수 있다 ([`find`](../budget_app/storage.py#L76)).
- **주의**: search 에 `--limit` 을 주지 않으면 정렬하려고 조건에 맞은 거래를 모두 모은다. 파일 전체가 아니라 맞은 것만이지만, 조건이 없으면 전부가 된다(10만 건에서 64.6MB). 정렬은 끝까지 봐야 순서를 알 수 있어서 스트리밍만으로는 안 된다. `--limit N` 을 주면 0.05MB 다. 스트리밍은 메모리를 줄이는 것이지 시간을 줄이는 것은 아니다. 끝까지 읽는 시간(0.35초)은 그대로다.

### 3-2. 데코레이터로 분리한 공통 기능과 분리가 필요했던 이유 — 충족

> 세 가지를 분리했습니다. 예외를 오류 메시지와 종료 코드로 바꾸는 `handle_errors`, 명령의 시작·성공·실패를 로그 파일에 남기는 `log_command`, 실행 시간을 재는 `measure_time` 입니다. 이 셋은 어느 명령에나 똑같이 필요하지만 명령이 하려는 일과는 상관이 없습니다. 데코레이터가 없다면 명령 함수 18개마다 try/except 와 로그 호출이 복사되어 들어갔을 것이고, 오류 문구 형식을 바꾸려면 18군데를 고쳐야 합니다. 지금은 명령 함수에 "무엇을 할지"만 남아 있습니다.

| 데코레이터 | 하는 일 | 붙인 곳 |
| --- | --- | --- |
| [`handle_errors`](../budget_app/decorators.py#L52) | 예외 → `[오류]/[힌트]` + 종료 코드 | `main` 한 곳 ([`@handle_errors`](../budget_app/cli.py#L486)). 모든 명령이 `main` 을 거치므로 한 번이면 된다 |
| [`log_command`](../budget_app/decorators.py#L92) | 시작/성공/실패를 `data/app.log` 에 | `cmd_*` 18개 ([예](../budget_app/cli.py#L116)) |
| [`measure_time`](../budget_app/decorators.py#L110) | 걸린 시간을 `data/app.log` 에 | 파일을 끝까지 읽는 서비스 메서드 5개 ([예](../budget_app/services.py#L156)) |

- **원리**: 데코레이터는 함수를 받아 새 함수(`wrapper`)를 돌려주는 함수다. `@log_command` 는 `cmd_list = log_command(cmd_list)` 와 같다. `wrapper` 는 원래 함수를 기억하고 있다가(클로저) 앞뒤에 일을 덧붙여 부른다. 어떤 인자를 받는 함수에도 붙일 수 있게 `*args, **kwargs` 로 받아 그대로 넘긴다. [`functools.wraps`](../budget_app/decorators.py#L55) 는 이름과 설명글을 원래 함수 것으로 유지해 준다.
- **시연**

  ```bash
  python3 -m budget_app list
  python3 -m budget_app delete --id TX-999999
  tail -5 data/app.log
  python3 -c "from budget_app.cli import cmd_list; print(cmd_list.__name__)"    # cmd_list (wrapper 가 아니다)
  ```

- **확인 결과**

  ```text
  2026-09-30 18:37:25,636 INFO [list] 시작
  2026-09-30 18:37:25,636 INFO TransactionService.list_recent 실행 시간: 0.09ms
  2026-09-30 18:37:25,636 INFO [list] 성공
  2026-09-30 18:37:25,679 INFO [delete] 시작
  2026-09-30 18:37:25,679 INFO [delete] 실패: NotFoundError
  ```

  자동 테스트: `tests/test_decorators.py` 13개, static `test_decorators_are_defined_and_applied`(18개 명령 전부에 붙어 있는지).
- **더 물으면**
  - `log_command` 가 예외를 잡고 다시 `raise` 하는 이유: 기록만 하고 처리는 `handle_errors` 에게 맡기려고.
  - `measure_time` 을 `stream` 에 붙이지 않은 이유: 제너레이터 함수는 부르자마자 제너레이터 객체만 돌려주고 끝나서 0ms 가 나온다. 그래서 끝까지 읽어 결과를 돌려주는 서비스 메서드에 붙였다.
  - 로그를 화면에 찍지 않는 이유: 스택트레이스 출력 금지. 자세한 내용은 파일로만 간다.

### 3-3. 타입 힌트를 적용해 얻는 이점을 실제 코드 예로 확인했는가 — 충족

> 타입 힌트는 실행 결과를 바꾸지 않습니다. 함수가 무엇을 받고 무엇을 돌려주는지 약속을 코드에 적어 두는 것이고, 검사기가 그 약속을 어긴 코드를 실행하기 전에 찾아 줍니다. mypy 라는 검사기로 확인했습니다. 프로그램 전체가 가장 엄격한 모드에서 문제없이 통과하고, 약속을 일부러 어긴 코드를 넣으면 잡아냅니다. 도움이 된 예는 세 가지입니다. 첫째, `find` 의 반환 타입이 `T | None` 이라서 못 찾았을 때의 처리를 빼먹을 수 없습니다. 둘째, 거래 타입을 `Literal["income", "expense"]` 로 적어서 아무 문자열이나 들어가는 것을 막았습니다. 셋째, 데코레이터에 `ParamSpec` 을 써서 데코레이터를 붙인 뒤에도 원래 함수의 매개변수와 반환 타입이 유지됩니다. 다만 파이썬은 실행 중에 타입 힌트를 검사하지 않으므로, 밖에서 들어오는 값은 `__post_init__` 에서 따로 검증합니다.

- **예 1 — None 가능성**: [`find`](../budget_app/storage.py#L76) 는 `T | None` 을 돌려준다. 그래서 [`get`](../budget_app/services.py#L170) 에 `if tx is None:` 이 있고, 그 뒤로는 `tx` 가 `Transaction` 으로 확정된다.
- **예 2 — 허용 값 제한**: [`TransactionType`](../budget_app/models.py#L24) `= Literal["income", "expense"]`. [`parse_type`](../budget_app/models.py#L66) 이 `str` 을 받아 이 타입으로 바꿔 돌려준다. 검증을 통과한 값과 아닌 값이 타입으로 구분된다.
- **예 3 — 데코레이터를 거쳐도 유지**: [`ParamSpec`](../budget_app/decorators.py#L24). `list_recent` 에 `@measure_time` 이 붙어 있어도 `(limit: int) -> list[Transaction]` 으로 보인다.
- **예 4 — 하나의 함수가 여러 타입에**: [`ask`](../budget_app/cli.py#L64) 는 `parse: Callable[[str], T]` 를 받아 `T` 를 돌려준다. `parse_amount` 를 넘기면 `int`, `parse_date` 를 넘기면 `str`. 저장소도 [`Generic[T]`](../budget_app/storage.py#L30) 라서 `TransactionRepository` 의 `stream` 은 `Transaction` 을 준다.
- **시연 1** — 프로그램 전체를 가장 엄격한 모드로 검사한다.

  ```bash
  uvx mypy budget_app --strict
  ```

  ```text
  Success: no issues found in 9 source files
  ```

- **시연 2** — 약속을 일부러 어긴 코드를 모아 둔 [docs/type_demo.py](type_demo.py) 를 검사한다. 실행하지 않고 읽기만 해서 다섯 군데를 찾아낸다.

  ```bash
  uvx mypy docs/type_demo.py
  ```

  ```text
  docs/type_demo.py:29: error: Item "None" of "Transaction | None" has no attribute "amount"  [union-attr]
  docs/type_demo.py:32: error: Argument "type" to "Transaction" has incompatible type "Literal['spend']"; expected "Literal['income', 'expense']"  [arg-type]
  docs/type_demo.py:36: note: Revealed type is "def (limit: int) -> list[budget_app.models.Transaction]"
  docs/type_demo.py:37: error: Argument 1 to "list_recent" of "TransactionService" has incompatible type "str"; expected "int"  [arg-type]
  docs/type_demo.py:40: note: Revealed type is "int"
  docs/type_demo.py:41: note: Revealed type is "str"
  docs/type_demo.py:42: note: Revealed type is "Literal['income'] | Literal['expense']"
  docs/type_demo.py:45: error: Argument 4 to "add" of "TransactionService" has incompatible type "str"; expected "int"  [arg-type]
  docs/type_demo.py:50: note: Revealed type is "budget_app.models.Transaction"
  docs/type_demo.py:51: error: "Transaction" has no attribute "amout"; maybe "amount"?  [attr-defined]
  Found 5 errors in 1 file (checked 1 source file)
  ```

  | 줄 | 검사기가 알려 준 것 | 어느 타입 힌트 덕분인가 |
  | ---: | --- | --- |
  | 29 | `find` 의 결과는 None 일 수 있는데 바로 `.amount` 를 썼다 | `-> T \| None` (예 1) |
  | 32 | `type="spend"` 는 허용된 값이 아니다 | `Literal` (예 2) |
  | 36, 37 | 데코레이터가 붙은 `list_recent` 의 타입이 그대로 보이고, 문자열 `"10"` 을 넘긴 호출을 잡았다 | `ParamSpec` (예 3) |
  | 40 ~ 42 | `ask` 의 결과가 넘겨준 함수에 따라 `int`, `str`, `Literal` 로 정해진다 | `TypeVar` (예 4) |
  | 45 | 금액 자리에 문자열을 넘겼다 | `amount: int` |
  | 50, 51 | `stream` 이 주는 것은 `Transaction` 이고, 오타 `amout` 을 잡으며 `amount` 를 제안한다 | `Generic[T]`, dataclass 필드 |

- **시연 3** (시간이 있으면) — `services.py` 의 `get` 에서 `if tx is None:` 부터 `raise` 끝까지를 주석으로 막고 `uvx mypy budget_app` 을 돌린다. 확인 후 되돌린다.

  ```text
  budget_app/services.py:179: error: Incompatible return value type (got "Transaction | None", expected "Transaction")  [return-value]
  Found 1 error in 1 file (checked 9 source files)
  ```

- **왜 도움이 되는가**
  - 그 코드가 실행되는 상황을 만들지 않아도 찾는다. 시연 3의 버그는 "없는 id 를 넣었을 때"만 터진다. 테스트가 그 경우를 빠뜨려도 검사기는 잡는다.
  - 오타와 인자 실수를 실행 전에 잡는다 (51번째 줄의 `amout`).
  - 함수의 첫 줄이 설명서가 된다. `list_recent(limit: int) -> list[Transaction]` 만 봐도 무엇을 넣고 무엇이 나오는지 안다.
  - `ParamSpec` 을 쓰지 않고 데코레이터를 `Callable[..., Any]` 로 적으면, 데코레이터를 붙인 함수의 타입이 `def (*Any, **Any) -> Any` 가 되어 `list_recent("10")` 같은 잘못된 호출이 검사를 그냥 통과한다. 따로 만들어 비교해서 확인했다.
- **검사기 없이 볼 수 있는 것**

  ```bash
  python3 -c "
  import inspect
  from budget_app.services import TransactionService
  from budget_app.storage import TransactionRepository
  print(inspect.signature(TransactionService.list_recent))
  print(inspect.signature(TransactionRepository.find))
  "
  ```

  ```text
  (self, limit: int) -> list[budget_app.models.Transaction]
  (self, key: str) -> Optional[~T]
  ```

- **확인 결과**: mypy 2.3.1 의 `--strict` 에서 `budget_app` 9개 파일 모두 문제 없음. 시연 2와 3의 출력은 실제로 나온 것이다. 모든 함수(122개)에 타입이 적혀 있는지는 자동 테스트(static `test_every_function_has_type_hints`)가 본다. mypy 는 개발할 때 쓰는 도구이고, 프로그램은 표준 라이브러리만 쓴다. VS Code 편집기 안에서 빨간 줄로 보이는지는 확인하지 않았다.
- **더 물으면**: 파이썬은 실행 중에 타입 힌트를 검사하지 않는다. `def double(x: int)` 에 문자열을 넘겨도 그대로 실행된다. 그래서 파일이나 사용자 입력처럼 밖에서 오는 값은 `parse_*` 와 [`__post_init__`](../budget_app/models.py#L180) 으로 실행 중에 검증한다. 타입 힌트는 "내가 쓴 코드끼리의 약속", 검증은 "밖에서 온 값에 대한 방어"다.

---

## 항목 4. 심층 인터뷰

### 4-1. JSONL 과 CSV 의 장단점, 그 포맷을 택한 근거 — 충족

> 내부 저장은 JSONL 을 골랐습니다. 가장 큰 이유는 태그가 리스트이고 메모가 자유 텍스트라는 점입니다. JSON 은 리스트를 그대로 담고, 쉼표·따옴표·줄바꿈 같은 특수문자를 알아서 이스케이프합니다. CSV 였다면 태그를 한 칸에 어떻게 넣을지, 메모에 쉼표가 있으면 어떻게 할지를 직접 정해야 합니다. 그리고 JSONL 은 한 줄이 기록 하나라서 추가할 때 파일 끝에 한 줄만 붙이면 되고, 한 줄씩 읽는 제너레이터와도 잘 맞습니다. 반대로 사람이나 엑셀과 주고받을 때는 CSV 가 편해서 import/export 는 CSV 로 했습니다. 내부 저장과 외부 교환의 역할을 나눈 것입니다.

| | JSONL | CSV |
| --- | --- | --- |
| 리스트(tags) | 그대로 담는다 `["meal","team"]` | 한 칸에 넣을 규칙을 따로 정해야 한다 |
| 특수문자(쉼표, 따옴표, 줄바꿈) | JSON 이 이스케이프 | 따옴표로 감싸는 규칙(RFC 4180)을 지켜야 한다 |
| 숫자와 문자 구분 | 된다 (`15000` 과 `"15000"`) | 전부 문자열 |
| 필드 이름 | 줄마다 반복 → 파일이 크다 | 헤더 한 번 → 작다 |
| 엑셀로 열기 | 안 된다 | 된다 |
| 한 줄 추가, 한 줄씩 읽기 | 쉽다 | 쉽다 |
| 필드 추가 | 줄마다 독립이라 유연 | 모든 행의 열이 맞아야 한다 |

- **근거**: 쓰기 [`_to_line`](../budget_app/storage.py#L146)(`ensure_ascii=False` 로 한글을 그대로 저장), 읽기 [`stream`](../budget_app/storage.py#L54). CSV 는 [`read_csv_rows`](../budget_app/storage.py#L208), [`write_transactions_csv`](../budget_app/storage.py#L239).
- **시연**: `cat data/transactions.jsonl` 과 `cat out.csv` 를 나란히 보여 준다. tags 가 JSONL 에서는 `["home", "fixed"]`, CSV 에서는 `"home,fixed"` 다.
- **JSONL 의 단점을 물으면**: 파일이 크다(10만 건 13.7MB). 줄마다 필드 이름이 반복되기 때문이다. 그리고 한 줄만 고칠 수 없어 수정·삭제는 전체를 다시 쓴다. 이것은 CSV 도 같다.

### 4-2. 거래가 10만 건이 되면 병목은 어디이고 어떻게 개선하나 — 충족

> 실제로 10만 건을 만들어 재 봤습니다. 메모리는 문제가 없습니다. 스트리밍 덕분에 list 가 0.05MB 입니다. 병목은 시간입니다. 첫째, 인덱스가 없어서 모든 조회가 파일을 처음부터 끝까지 읽습니다. 10만 건에서 0.35초쯤 걸립니다. 둘째, 수정과 삭제는 한 건을 바꾸려고 파일 전체를 다시 써서 1.3초가 걸립니다. 셋째, add 도 새 id 를 만들려고 전체를 읽습니다. 개선은 저장소 계층만 바꾸면 되는 것부터 하겠습니다. 마지막 id 번호를 따로 저장하면 add 가 바로 끝나고, 거래 파일을 월별로 나누면 summary 와 기간 검색이 그 달 파일만 읽습니다. 그 이상이 필요하면 표준 라이브러리에 있는 SQLite 로 저장소를 바꿉니다. 계층을 나눠 뒀기 때문에 서비스와 CLI 는 그대로 둘 수 있습니다.

- **측정** (`python3 tests/benchmark.py --records 100000`, 이 컴퓨터에서 잰 대략적인 값)

  | 기능 | 1만 건 | 10만 건 | 최대 메모리 (10만 건) | 이유 |
  | --- | ---: | ---: | ---: | --- |
  | `list --limit 10` | 35 ms | 355 ms | 0.05 MB | 끝까지 읽어야 최신 10건을 안다 |
  | `search` 한 달 + 카테고리 | 37 ms | 337 ms | 0.28 MB | 〃 |
  | `summary` | 36 ms | 353 ms | 0.05 MB | 〃 |
  | `add` 1건 | 42 ms | 354 ms | 0.05 MB | id 를 만들려고 전체를 읽는다 |
  | `update` 1건 | 132 ms | 1,242 ms | 0.06 MB | 찾기 + 파일 전체 다시 쓰기 |
  | `delete` 1건 | 122 ms | 1,310 ms | 0.06 MB | 〃 |
  | `search` 조건 없음, 전부 | 46 ms | 548 ms | 64.60 MB | 정렬하려고 다 모은다 |
  | (비교) 전부 list 로 읽기 | 36 ms | 389 ms | 55.08 MB | |

  건수가 10배가 되면 시간도 10배가 된다(전부 O(n)). 읽는 시간의 대부분은 줄마다 JSON 을 해석하고 검증하는 데 든다.
- **병목과 개선**

  | 병목 | 지금 | 개선 | 고칠 곳 |
  | --- | --- | --- | --- |
  | add 가 전체를 읽는다 | [`last_number`](../budget_app/storage.py#L171) 가 가장 큰 번호를 찾는다 | 마지막 번호를 작은 파일에 따로 저장 | 저장소 |
  | 모든 조회가 전체를 읽는다 | 파일 하나 | 월별 파일로 나눈다 (`transactions-2024-01.jsonl`). summary 와 기간 검색은 해당 달만 읽는다 | 저장소 |
  | 수정·삭제가 전체를 다시 쓴다 | [`_rewrite`](../budget_app/storage.py#L120) | 월별로 나누면 그 달 파일만 다시 쓴다. 또는 "삭제 표시" 줄을 끝에 덧붙이고 가끔 정리한다 | 저장소 |
  | id 로 찾기가 O(n) | [`find`](../budget_app/storage.py#L76) | id → 파일 위치 인덱스 | 저장소 |
  | search 전부 보기의 메모리 | [`newest_first`](../budget_app/services.py#L72) 가 모은다 | 기본 `--limit` 을 두거나 쪽(page) 단위로 | 서비스, CLI |
  | 그 이상 | | `sqlite3` (표준 라이브러리). 인덱스와 트랜잭션을 DB 가 해 준다 | 저장소만 |

- **근거**: [`tests/benchmark.py`](../tests/benchmark.py).
- **한마디로**: 지금 구조는 "개인 가계부 몇 천 건"에는 충분하고(1만 건에서 35ms), 10만 건부터는 수정·삭제가 1초를 넘는다.

### 4-3. import CSV 에 깨진 행이 섞이면 어떻게 처리해 신뢰를 지키나 — 충족

> 부분 성공과 보고를 택했습니다. 맞는 행은 넣고, 틀린 행은 건너뛰되 몇 번째 줄이 왜 틀렸는지를 하나하나 알려 줍니다. 말없이 건너뛰면 사용자는 다 들어간 줄 알기 때문에 보고가 핵심입니다. 그리고 두 단계로 나눴습니다. 먼저 파일을 끝까지 읽으며 검증만 하고, 다 끝난 뒤에 통과한 행을 한꺼번에 저장합니다. 그래서 파일 자체를 읽다가 실패하면, 예를 들어 UTF-8 이 아니거나 헤더가 틀리면 한 건도 들어가지 않습니다. "일부만 들어갔는지 아닌지 모르는 상태"가 생기지 않게 한 것입니다.

| 상황 | 동작 |
| --- | --- |
| 일부 행의 값이 틀림 (날짜, 금액, 타입, 등록 안 된 카테고리) | 그 행만 건너뛰고 줄 번호 + 이유 보고. 나머지는 저장. 종료 코드 0 |
| 헤더에 필수 컬럼이 없음 | 아무것도 저장하지 않고 오류. 종료 코드 1 |
| UTF-8 이 아님 (엑셀의 기본 CSV), 파일이 없음 | 〃 |
| 카테고리가 하나도 등록되지 않음 | 〃 (`category add` 안내) |

- **시연**: 시연 준비의 `import --from docs/sample-import.csv`. 8번째 줄(2월 30일)과 9번째 줄(등록 안 된 cafe)이 건너뛰어진다.
- **근거**: [`import_csv`](../budget_app/services.py#L222) — 검증 단계에서 [`skipped.append`](../budget_app/services.py#L240) 로 이유를 모으고, 끝난 뒤 [`self.transactions.append(valid)`](../budget_app/services.py#L242) 한 번으로 저장한다. 행 검증은 [`_from_csv_row`](../budget_app/services.py#L246) 가 `add` 와 같은 `parse_*` 함수로 한다.
- **확인 결과**: 자동 테스트 `test_import_skips_bad_rows_and_reports_them`(7줄 중 5줄이 틀린 파일 → 2건 저장, 줄 번호 3·4·5·6·8 보고), `test_import_unreadable_file_saves_nothing`(3번째 줄이 UTF-8 이 아닌 파일 → 저장 파일이 바이트 단위로 그대로).
- **롤백을 택하지 않은 이유를 물으면**: 명세의 출력 예시가 `imported=5, skipped=0` 형태라 건너뛰기를 전제로 한다. 그리고 1,000줄 중 한 줄 때문에 전체를 거부하면 불편하다. 대신 파일 단위의 실패는 전부 취소한다.
- **남은 약점**: CSV 에 id 가 없어서 같은 파일을 다시 넣으면 중복된다. 그래서 안내 문구로 "건너뛴 줄만 고쳐서 새 파일로" 넣으라고 알려 준다. 개선한다면 한 줄이라도 틀리면 전부 거부하는 `--strict` 옵션, 또는 건너뛴 행만 따로 파일로 내보내는 기능을 넣겠다.

---

## 부록 A. 과제 목표 5가지와 문항

명세 3장은 과제를 마친 뒤 아래를 스스로 설명할 수 있어야 한다고 적고 있다.

| 과제 목표 | 이 문서 |
| --- | --- |
| 파일 기반 저장(JSONL/CSV)으로 영구 저장하고 CRUD/검색/요약/입출력을 구현 | 1-1, 1-2, 1-5, 4-1 |
| 클래스/모듈로 구조화하고 각 계층(모델/저장소/서비스/CLI)의 책임을 설명 | 2-1, 2-2 |
| `yield` 기반 제너레이터로 스트리밍 처리하는 이유와 동작 방식 | 3-1 |
| 데코레이터로 공통 관심사를 분리한 구조와 이유 | 3-2 |
| 타입 힌트로 입출력 계약을 명확히 했을 때의 이점을 실제 코드 예로 | 3-3 |

## 부록 B. 문서에 고정한 선택

명세가 "하나를 골라 명확히 하라"고 한 것과, 구현하면서 정한 기준값이다. README 에도 같은 내용이 있다.

| 항목 | 선택 | 명세 |
| --- | --- | --- |
| 저장 포맷 | JSONL | 4.3 |
| 카테고리가 비어 있을 때 | 안 B: `category add` 를 안내하고 `add` 를 막는다 | 4.3 |
| `update` 입력 방식 | 안 A: 옵션 기반 | 4.6 |
| 사용 중인 카테고리 삭제 | 막는다 | 4.10 |
| `list --limit` 기본값 | 10 | 4.5 |
| `summary --top` 기본값 | 3 | 4.8 |
| 최신순의 뜻 | 날짜가 늦은 것 먼저, 같은 날이면 나중에 등록한 것 먼저 | 4.5 |
| 기본 저장 폴더 | `./data` (`--data-dir` 로 변경) | 4.3 |
| 종료 코드 | 0 정상 / 1 오류 / 2 명령 형식 오류 / 130 중단 | 4.13 |

## 부록 C. 나올 만한 추가 질문

- **서비스끼리 왜 서로 부르지 않나?** 거래 서비스는 카테고리가 등록됐는지, 카테고리 서비스는 거래가 쓰고 있는지를 알아야 한다. 서로 부르면 둘이 맞물린다. 그래서 필요한 저장소를 직접 받게 했고, 조립은 [`Ledger`](../budget_app/services.py#L466) 한 곳에서 한다.
- **summary 가 왜 BudgetService 에 있나?** 거래와 예산을 둘 다 읽어야 하고, 결과의 핵심이 예산 대비 사용률이기 때문이다 ([`summarize`](../budget_app/services.py#L348)).
- **id 는 어떻게 유일한가?** 저장된 번호 중 가장 큰 것 + 1 ([`make_id`](../budget_app/models.py#L137)). 그래서 가장 최근 거래를 지운 뒤 추가하면 그 번호가 다시 쓰인다. 같은 시점에 겹치는 id 는 없다. 번호를 재사용하지 않으려면 마지막 번호를 따로 저장해야 한다.
- **두 터미널에서 동시에 실행하면?** 잠금이 없어서 나중에 쓴 쪽이 이긴다. 수정·삭제는 원자적 교체라 파일이 깨지지는 않지만 한쪽 변경이 사라질 수 있다.
- **손상된 줄을 왜 건너뛰지 않나?** 건너뛰면 합계가 조용히 틀리고, 수정·삭제로 파일을 다시 쓸 때 그 줄이 사라진다. 멈추고 몇 번째 줄인지 알려 주는 쪽이 데이터를 지킨다.
- **argparse 의 `type=int` 를 왜 안 썼나?** 옵션 값은 전부 문자열로 받고 `models.py` 의 `parse_*` 로 검사한다 ([`parse_count`](../budget_app/models.py#L126)). 대화형·옵션·CSV 가 같은 검증 함수를 쓰게 되고, 오류 문구가 항상 `[오류]/[힌트]` 한국어로 나온다.
- **`-h` 는 왜 없나?** 명세가 옵션 표기를 `--` 로 통일하라고 해서 argparse 가 자동으로 만드는 `-h` 를 끄고 `--help` 만 넣었다 ([`Parser.__init__`](../budget_app/cli.py#L285)).
- **`tags: list[str] = []` 가 아니라 `field(default_factory=list)` 인 이유?** 기본값 리스트 하나를 모든 객체가 같이 쓰게 되는 것을 막는다. dataclass 는 `= []` 를 아예 오류로 막는다 ([`Transaction`](../budget_app/models.py#L169)).
- **파일에서 읽을 때도 검증하는 이유?** 파일은 사람이 편집기로 고칠 수 있다. 어떤 경로로 만들어지든 같은 검증을 통과해야 잘못된 값을 가진 객체가 프로그램 안을 돌아다니지 않는다 ([`__post_init__`](../budget_app/models.py#L180)).
- **금액이 왜 정수인가?** 원 단위는 소수가 없고, 실수(float)는 더할 때 오차가 생길 수 있다 ([`parse_amount`](../budget_app/models.py#L78)).
- **`python -m budget_app` 은 어떻게 실행되나?** 파이썬이 `budget_app` 폴더의 `__main__.py` 를 실행한다. 거기서 `main()` 을 부르고 반환값을 종료 코드로 넘긴다 ([`sys.exit(main())`](../budget_app/__main__.py#L11)).
