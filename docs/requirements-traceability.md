# 명세 대응표

과제 명세(`project.md`)의 조항 번호를 기준으로 **어디에 구현했고 어떻게 확인했는지**를 정리했다.

- 확인한 날: 2026-09-30
- 확인한 환경: macOS, Python 3.10.20 · 3.11.16 · 3.14.7 (세 버전 모두에서 테스트 205개 통과, 경고를 오류로 취급하는 `-W error -X dev` 로 실행)
- 다시 확인하려면: `python -m unittest discover -s tests -v`

구현 열의 링크는 그 코드가 있는 줄로 간다. 검증 열의 표기는 테스트 파일이다.

| 표기 | 파일 | 방식 |
| --- | --- | --- |
| `cli` | `tests/test_cli.py` | 진짜 프로그램을 새 프로세스로 실행해 화면 출력·종료 코드·저장 파일을 확인 |
| `services` | `tests/test_services.py` | 서비스를 직접 호출 |
| `storage` | `tests/test_storage.py` | 저장소를 직접 호출 |
| `models` | `tests/test_models.py` | 검증 함수와 dataclass |
| `decorators` | `tests/test_decorators.py` | 데코레이터 3개 |
| `streaming` | `tests/test_streaming.py` | 2만 건 파일에서 최대 메모리 측정 |
| `static` | `tests/test_spec_static.py` | 소스 코드를 읽어 구조 확인 |

## 결과 요약

| 구분 | 결과 |
| --- | --- |
| 2. 최종 결과물 (10가지) | 전부 충족 |
| 4. 기능 요구 사항 (4.1 ~ 4.14) | 전부 충족 |
| 5. 보너스 (4가지) | 전부 구현 |
| 6. 개발 환경, 7. 제약 사항 | 충족 |
| 1·3. 미션 소개와 과제 목표에 적힌 기술 (제너레이터, 데코레이터, 타입 힌트, 모듈 분리) | 충족. 타입 검사기 mypy `--strict` 통과 |
| 확인하지 못한 것 | Windows 에서의 실행. 맨 아래 [확인하지 못한 것](#확인하지-못한-것) 참고 |

## 1 · 3. 미션 소개와 과제 목표에 적힌 기술

명세 1장은 "제너레이터 스트리밍, 데코레이터 분리, 타입 힌트"와 모듈 분리를 요구하고, 3장은 그것을 설명할 수 있어야 한다고 적고 있다.

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| 저장 파일을 한 번에 읽지 않고 제너레이터로 스트리밍 | 4.5, 4.7 참고 | streaming 6개 (2만 건에서 최대 메모리 측정) |
| 데코레이터로 공통 기능(예외 처리, 실행 로그, 실행 시간 측정)을 분리 | 4.12 참고 | decorators 13개 |
| 타입 힌트로 함수와 데이터 구조의 계약을 명확히 | 모든 함수 122개의 매개변수·반환값에 타입. [`TransactionType`](../budget_app/models.py#L24)(Literal), [`Generic[T]`](../budget_app/storage.py#L30), [`ParamSpec`](../budget_app/decorators.py#L24) | static `test_every_function_has_type_hints`. `uvx mypy budget_app --strict` (mypy 2.3.1) → `Success: no issues found in 9 source files`. 약속을 어긴 코드는 `uvx mypy docs/type_demo.py` 가 5군데 잡는다 |
| 모듈 분리로 유지보수 가능한 구조 | 4.14 참고 | static `StructureTests` 6개 |

## 2. 최종 결과물

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| 1. `add` — 대화형 입력, 저장 성공 메시지 + id | [`cmd_add`](../budget_app/cli.py#L102), [`add`](../budget_app/services.py#L131) | cli `AddTests.test_add_prints_success_and_id`, `RunAndInputTests.test_add_is_interactive` |
| 2. `list` — `--limit`, 최신순, 스트리밍 | [`cmd_list`](../budget_app/cli.py#L117), [`list_recent`](../budget_app/services.py#L157) | cli `ListTests` 6개, streaming `test_list_keeps_only_limit_records` |
| 3. `search` — `--from/--to`, `--category`, `--type`, `--q`, `--tag` | [`cmd_search`](../budget_app/cli.py#L127), [`search`](../budget_app/services.py#L166) | cli `SearchTests.test_each_option` (조합 10가지) |
| 4. `summary` — `--month`, `--top`, 총수입/총지출/잔액/TOP N | [`cmd_summary`](../budget_app/cli.py#L142), [`summarize`](../budget_app/services.py#L348) | cli `SummaryBudgetTests.test_summary`, `test_top_option` |
| 5. `budget` — `budget set --month --amount`, summary 에 사용률/초과 경고 | [`cmd_budget_set`](../budget_app/cli.py#L150), [`cmd_budget_list`](../budget_app/cli.py#L156), [`set_budget`](../budget_app/services.py#L337) | cli `test_budget_set`, `test_summary_shows_usage_when_budget_is_set`, `test_summary_warns_when_over_budget` |
| 6. `category add/list/remove` (사용 중 처리 포함) | [`cmd_category_add`](../budget_app/cli.py#L165), [`cmd_category_list`](../budget_app/cli.py#L172), [`cmd_category_remove`](../budget_app/cli.py#L181), [`CategoryService`](../budget_app/services.py#L280) | cli `CategoryTests` 3개 |
| 7. `update` — `--id` 기반, 없는 id 처리 | [`cmd_update`](../budget_app/cli.py#L188), [`update`](../budget_app/services.py#L183) | cli `test_update_by_options`, `test_update_missing_id` |
| 8. `delete --id <id>` — 없는 id 처리 | [`cmd_delete`](../budget_app/cli.py#L204), [`delete`](../budget_app/services.py#L213) | cli `test_delete`, `test_delete_missing_id` |
| 9. `import --from <csv>`, `export --out <csv> --month` 또는 `--from/--to` — 처리 건수 출력 | [`cmd_import`](../budget_app/cli.py#L211), [`cmd_export`](../budget_app/cli.py#L223), [`import_csv`](../budget_app/services.py#L222), [`export_csv`](../budget_app/services.py#L259) | cli `ImportExportTests` 9개 |
| 10-1. 데이터는 3개 이상 파일로 영구 저장 | [`Ledger`](../budget_app/services.py#L466) 가 `transactions.jsonl`, `categories.jsonl`, `budgets.jsonl`(+`recurring.jsonl`)을 만든다 | cli `StorageTests.test_data_survives_restart`, services `test_initialize_creates_three_or_more_files` |
| 10-2. README 에 실행 방법, 저장 파일 위치/형식, 주요 명령 예시, import/export CSV 스키마 | `README.md` 의 같은 이름 섹션 4개 | static `ReadmeTests` 3개 |

## 4.1 실행 및 입력 방식

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| `python -m budget_app <command> [options]` | `budget_app/__main__.py`, [`main`](../budget_app/cli.py#L487) | cli 전체 (모든 테스트가 이 형태로 실행한다) |
| 모든 명령은 `--help` 로 사용 방법 출력 | [`Parser.__init__`](../budget_app/cli.py#L285) 이 모든 파서에 `--help` 를 넣는다 | cli `test_every_command_has_help` (최상위 + 명령·하위 명령 21개 = 22개) |
| 입력 기본 방식은 대화형 (`add` 는 `input()` 으로 순차 입력) | [`ask`](../budget_app/cli.py#L64), [`cmd_add`](../budget_app/cli.py#L102) | cli `test_add_is_interactive` (질문 6개가 순서대로 나옴) |
| search, list, summary, export, import, delete 는 옵션 인자 방식 허용 | [`build_parser`](../budget_app/cli.py#L337) | cli 각 명령의 테스트 |
| `update` 는 옵션/대화형 중 하나로 문서에 고정 | 옵션 방식. README "실행 방법"과 "프로젝트 한눈에 보기"에 적음 | static `test_fixed_choices_are_documented` |
| 옵션 표기는 `--` 로 통일 | [`add_help=False`](../budget_app/cli.py#L287) 로 `-h` 를 없애고 `--help` 만 추가. 모든 옵션이 `--` 로 시작 | cli `test_short_options_do_not_exist` (`-h`, `-l` 은 오류), static `test_options_are_double_dash_only` (파서 22개의 옵션 전수 검사) |

## 4.2 데이터 모델

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| Transaction 필드: id, type, date, amount, category, memo(선택), tags(선택) | [`Transaction`](../budget_app/models.py#L169) | models `test_transaction_is_dataclass_with_required_fields`, cli `test_added_record_has_all_fields`, `test_memo_and_tags_are_optional` |
| id 는 유일 | '가장 큰 번호 + 1': [`last_number`](../budget_app/storage.py#L171), [`make_id`](../budget_app/models.py#L137) | cli `test_ids_are_unique`, services `test_add_assigns_unique_sequential_ids` |
| type 은 income/expense | [`parse_type`](../budget_app/models.py#L66) | models `test_parse_type` |
| date 는 YYYY-MM-DD | [`parse_date`](../budget_app/models.py#L38) | models `test_parse_date_accepts_only_real_yyyy_mm_dd` |
| amount 는 양수 | [`parse_amount`](../budget_app/models.py#L78) | models `test_parse_amount_must_be_positive_integer` |
| `dataclass` 로 정의 | [`@dataclass`](../budget_app/models.py#L168) | static `test_at_least_two_classes_and_dataclass` |
| 최소 2개 이상의 클래스 | `Transaction`, `TransactionRepository`, `TransactionService`, `CategoryService`, `BudgetService` 등 | static `test_at_least_two_classes_and_dataclass` |
| 입력 검증: 날짜 형식 오류, 음수/0 금액, 허용되지 않은 type, 없는 category → 재입력 요구 또는 오류 메시지 | 대화형은 [`ask`](../budget_app/cli.py#L64) 가 다시 묻고, 옵션은 오류로 끝낸다. 모델도 [`__post_init__`](../budget_app/models.py#L180) 에서 다시 검증 | cli `test_invalid_input_is_asked_again` (7번 틀리고도 1건만 저장), `test_update_rejects_bad_values`, models `test_transaction_validates_itself` |

## 4.3 저장 정책

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| 저장 포맷은 JSONL 또는 CSV 중 1개 | JSONL: [`_to_line`](../budget_app/storage.py#L146), [`stream`](../budget_app/storage.py#L54) | cli `test_files_are_jsonl`, storage `test_append_then_stream_round_trip` |
| 저장 파일 3개 이상: `transactions.<fmt>`, `categories.<fmt>`, `budgets.<fmt>` | [`Ledger.__init__`](../budget_app/services.py#L473) | services `test_initialize_creates_three_or_more_files`, static `test_three_storage_files_are_separate_repositories` |
| 기본 저장 폴더 `./data`, 옵션으로 변경 (`--data-dir`) | [`DEFAULT_DATA_DIR`](../budget_app/cli.py#L51), [`--data-dir`](../budget_app/cli.py#L290) | cli `test_default_folder_is_data_under_current_directory`, `test_data_dir_option_works_before_and_after_command` |
| 초기 실행: 파일이 없으면 자동 생성하거나 초기화 안내 | 둘 다 한다: [`ensure_file`](../budget_app/storage.py#L44), [`initialize`](../budget_app/services.py#L486), `main` 의 `[안내]` | cli `test_first_run_creates_files_and_says_so` |
| 카테고리 파일이 비어 있을 때의 동작을 명확히 | 안 B: [`require_categories`](../budget_app/services.py#L117) 가 `add` 를 막고 `category add` 를 안내. README 에 적음 | cli `test_add_is_blocked_until_a_category_exists` (질문을 시작하지 않고, 기본 카테고리도 만들지 않음) |
| 프로그램 종료 후에도 유지 | 파일에만 저장 | cli `test_data_survives_restart` (명령마다 새 프로세스) |

## 4.4 add

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| 대화형으로 필드를 입력받아 저장 | [`cmd_add`](../budget_app/cli.py#L102) | cli `test_add_is_interactive`, `test_added_record_has_all_fields` |
| category 는 등록된 목록에 있어야 함 (없으면 안내 후 재입력/등록 유도) | [`check_category`](../budget_app/services.py#L125), [`registered_category`](../budget_app/services.py#L93) — 등록된 이름을 보여 주고 `category add` 를 안내한 뒤 다시 묻는다 | cli `test_invalid_input_is_asked_again`, services `test_add_rejects_unregistered_category` |
| 저장 완료 시 생성된 id 출력 | `[저장 완료] id=TX-000008` | cli `test_add_prints_success_and_id` |

## 4.5 list

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| 최신순 출력 | [`newest_first`](../budget_app/services.py#L72): 날짜가 늦은 것 먼저, 같은 날이면 나중에 등록한 것 먼저 | cli `test_list_is_newest_first`, services `test_list_recent_is_newest_first`, `test_newest_first_orders_by_number_not_by_text` |
| `--limit N` 지원 (기본값 제공) | [`DEFAULT_LIMIT`](../budget_app/cli.py#L53) = 10 | cli `test_limit`, `test_limit_has_a_default`, `test_bad_limit` |
| 파일 전체를 한 번에 로드하지 않고 제너레이터 기반 스트리밍 | [`stream`](../budget_app/storage.py#L54) 이 한 줄씩 `yield`, [`heapq.nlargest`](../budget_app/services.py#L85) 가 limit 건만 유지 | streaming `test_list_keeps_only_limit_records` (2만 건 파일에서 0.5MB 미만), storage `test_stream_is_a_generator`, `test_stream_reads_lazily`, static `test_nothing_reads_a_whole_file_at_once` |

## 4.6 update / delete

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| `delete --id <id>` 로 삭제 | [`cmd_delete`](../budget_app/cli.py#L204), [`delete`](../budget_app/services.py#L213), [`remove`](../budget_app/storage.py#L113) | cli `test_delete` |
| 없는 id 는 "없는 데이터"로 처리하고 메시지 출력 | [`get`](../budget_app/services.py#L170) 이 `없는 데이터입니다: ...` 로 알림, 종료 코드 1 | cli `test_delete_missing_id`, `test_update_missing_id` |
| `update` 는 안 A(옵션) 또는 안 B(대화형) 중 하나로 고정 | 안 A: `update --id <id> [--date] [--type] [--category] [--amount] [--memo] [--tags]` — [`cmd_update`](../budget_app/cli.py#L188), [`update`](../budget_app/services.py#L183) | cli `test_update_by_options`, `test_update_all_options`, `test_update_rejects_bad_values` |
| 전체 재작성/임시 파일/원자적 교체 등 안정성 고려 | [`_rewrite`](../budget_app/storage.py#L120): 임시 파일에 전부 쓰고 [`os.fsync`](../budget_app/storage.py#L135) 뒤 [`os.replace`](../budget_app/storage.py#L136) | storage `test_rewrite_failure_keeps_original`, `test_replace_failure_keeps_original`, `test_rewrite_goes_through_temp_file_then_replace`, `test_no_temp_file_is_left`, cli `test_file_is_whole_after_update_and_delete` |

## 4.7 search

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| 기간 `--from`, `--to` / 카테고리 `--category` / 타입 `--type` / 메모 키워드 `--q` / 태그 `--tag` | [`SearchFilter`](../budget_app/models.py#L247), [`matches`](../budget_app/models.py#L283), [`cmd_search`](../budget_app/cli.py#L127) | cli `test_each_option`, `test_bad_options`, models `test_each_condition` (14가지) |
| 결과는 최신순 | [`search`](../budget_app/services.py#L166) → `newest_first` | cli `test_each_option` (id 순서까지 비교) |
| 스트리밍 처리(제너레이터 기반) 유지 | [`matching`](../budget_app/services.py#L161) 이 제너레이터로 걸러 넘긴다 | services `test_matching_is_a_generator`, streaming `test_search_with_limit_is_bounded`, `test_search_without_limit_holds_only_matches` |

`--limit` 없이 검색하면 정렬을 위해 조건에 맞은 거래를 모은다. 파일 전체가 아니라 맞은 것만이다. `--limit N` 을 주면 N건만 유지한다.

## 4.8 summary

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| `summary --month YYYY-MM` | [`cmd_summary`](../budget_app/cli.py#L142), [`parse_month`](../budget_app/models.py#L52) | cli `test_summary`, `test_bad_month` |
| 총 수입, 총 지출, 잔액(총수입 − 총지출) | [`summarize`](../budget_app/services.py#L348), [`balance`](../budget_app/models.py#L314), [`format_summary`](../budget_app/formatter.py#L88) | cli `test_summary`, services `test_summary_totals` |
| 카테고리별 지출 합계 TOP N (`--top`) | [`DEFAULT_TOP`](../budget_app/cli.py#L54) = 3 | cli `test_top_option`, services `test_summary_top_n`, `test_summary_tie_is_ordered_by_name` |
| 데이터가 없는 달은 "데이터 없음" 출력 | [`데이터 없음`](../budget_app/formatter.py#L91) | cli `test_empty_month_says_no_data` |

## 4.9 budget

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| `budget set --month YYYY-MM --amount <금액>` 으로 저장 | [`cmd_budget_set`](../budget_app/cli.py#L150), [`set_budget`](../budget_app/services.py#L337), [`upsert`](../budget_app/storage.py#L96) | cli `test_budget_set`, `test_budget_list_and_bad_values` |
| summary 에 예산 대비 사용률(%) | [`usage_percent`](../budget_app/models.py#L318) | cli `test_summary_shows_usage_when_budget_is_set` (`사용률 44.0%`) |
| summary 에 초과 여부 (초과 시 경고 문구) | [`over_budget`](../budget_app/models.py#L324), [`초과 여부`](../budget_app/formatter.py#L105) | cli `test_summary_warns_when_over_budget` (`초과 여부: 초과`, `[경고]`) |
| 예산 데이터도 영구 저장 | [`BudgetRepository`](../budget_app/storage.py#L183) → `budgets.jsonl` | cli `test_budget_set`, `test_data_survives_restart`, services `test_budget_set_is_persisted_and_replaced` |

## 4.10 category

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| `category add/list/remove` 제공 | [`CategoryService`](../budget_app/services.py#L280) | cli `CategoryTests.test_add_list_remove`, `test_duplicate_missing_and_empty` |
| 삭제 시 사용하는 내역이 있으면 삭제를 막거나 대체 카테고리 요구 | 삭제를 막는다: [`remove`](../budget_app/services.py#L306) | cli `test_remove_is_blocked_while_in_use`, services `test_remove_is_blocked_while_in_use`, `test_remove_after_transactions_are_gone` |

## 4.11 import / export

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| `import --from <csv>` 로 일괄 등록 | [`cmd_import`](../budget_app/cli.py#L211), [`import_csv`](../budget_app/services.py#L222), [`read_csv_rows`](../budget_app/storage.py#L208) | cli `test_import`, `test_import_reports_broken_rows` |
| `export --out <csv>` 로 조건에 맞는 거래를 CSV 로 저장 | [`cmd_export`](../budget_app/cli.py#L223), [`export_csv`](../budget_app/services.py#L259), [`write_transactions_csv`](../budget_app/storage.py#L239) | cli `test_export_by_month`, `test_export_by_range` |
| export 는 `--month` 또는 `--from --to` 중 하나 이상 조건 필수 | [`has_period`](../budget_app/models.py#L279) 가 False 면 오류 | cli `test_export_needs_a_period`, services `test_export_requires_period`, `test_export_by_range_and_both` |
| CSV 스키마: date, type, category, amount 필수 / memo, tags 선택 | [`CSV_COLUMNS`](../budget_app/storage.py#L204), [`_from_csv_row`](../budget_app/services.py#L246) | cli `test_export_by_month` (헤더와 행 비교), `test_export_then_import_into_another_ledger` (왕복), storage `test_missing_required_column`, `test_short_row_gives_none` |
| category 는 등록된 카테고리, amount 는 양수 정수 | `_from_csv_row` 가 `add` 와 같은 검증 함수를 쓴다 | cli `test_import_reports_broken_rows` |
| 공통: UTF-8, 헤더 포함 | 쓰기 [`encoding="utf-8"`](../budget_app/storage.py#L243), 읽기 [`utf-8-sig`](../budget_app/storage.py#L217) (BOM 허용) | storage `test_write_csv`, `test_bom_is_accepted`, `test_not_utf8`, cli `test_import_file_errors` |

## 4.12 데코레이터

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| 공통 관심사 데코레이터를 1개 이상 구현 | 3개: [`handle_errors`](../budget_app/decorators.py#L52)(예외 처리), [`log_command`](../budget_app/decorators.py#L92)(실행 로그), [`measure_time`](../budget_app/decorators.py#L110)(시간 측정) | decorators 13개 |
| 실제 적용 | [`@handle_errors`](../budget_app/cli.py#L486) 는 `main` 에, `@log_command` 는 `cmd_*` 18개에, [`@measure_time`](../budget_app/services.py#L156) 은 서비스 메서드 5개에 | static `test_decorators_are_defined_and_applied`, cli `test_decorators_write_the_log` (실행 뒤 `app.log` 에 기록이 남는지) |

## 4.13 예외 처리 및 종료 코드

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| 오류는 스택트레이스 대신 원인 + 해결 힌트 | 예외가 원인과 힌트를 함께 가진다: [`AppError`](../budget_app/errors.py#L11). [`handle_errors`](../budget_app/decorators.py#L52) 가 받아 [`print_error`](../budget_app/formatter.py#L17) 로 출력. 명령 형식 오류는 [`error`](../budget_app/cli.py#L297) | cli `test_errors_exit_nonzero_without_traceback` (10가지), `test_usage_errors` (7가지), `test_damaged_data_file`, `test_unusable_data_dir`, `test_import_file_errors`, decorators `test_unexpected_error_hides_traceback` |
| 정상 종료는 0 | [`EXIT_OK`](../budget_app/decorators.py#L27), [`sys.exit(main())`](../budget_app/__main__.py#L11) | cli `test_success_exits_zero` |
| 오류 종료는 0이 아닌 값 | [`EXIT_ERROR`](../budget_app/decorators.py#L28) = 1, [`EXIT_USAGE`](../budget_app/decorators.py#L29) = 2, [`EXIT_CANCELLED`](../budget_app/decorators.py#L30) = 130 | cli 의 모든 오류 테스트가 종료 코드를 비교한다 (`assert_error`) |

## 4.14 모듈화

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| 최소 3개 이상 모듈로 분리 | 7개: `cli`, `services`, `storage`, `models`, `errors`, `decorators`, `formatter` | static `test_at_least_three_modules` |
| (권장) CLI / 서비스 / 저장소 / 모델로 책임 분리 | 위에서 아래로만 import. `input` 은 cli 에만, 파일 열기는 storage 에만 | static `test_layers_depend_downward_only`, `test_only_cli_talks_to_the_user`, `test_only_storage_opens_files` |

## 5. 보너스

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| 1. `backup` — 타임스탬프가 포함된 백업 파일 | [`cmd_backup`](../budget_app/cli.py#L231), [`backup`](../budget_app/services.py#L490), [`create_backup`](../budget_app/storage.py#L256) → `data/backups/backup-20260930-164408.zip` | cli `BonusTests.test_backup`, storage `BackupTests` 2개 |
| 2. 반복 내역 등록, 특정 월에 자동 생성 | [`RecurringRule`](../budget_app/models.py#L217), [`RecurringService`](../budget_app/services.py#L380), [`apply`](../budget_app/services.py#L428) | cli `BonusTests.test_recurring`, services `RecurringTests` 5개, models `test_recurring_rule_date_in` |
| 3. 외부 라이브러리 없이 표 정렬 | [`display_width`](../budget_app/formatter.py#L29), [`render_table`](../budget_app/formatter.py#L40) | cli `test_table_columns_line_up_with_korean` |
| 4. 임시 파일에 쓰고 rename 으로 교체 | [`_rewrite`](../budget_app/storage.py#L120) | storage `SafeWriteTests` 7개 |

## 6. 개발 환경 · 7. 제약 사항

| 요구 | 구현 | 검증 |
| --- | --- | --- |
| Python 3.10 이상 | 3.10 문법과 표준 라이브러리만 사용 | 전체 테스트를 3.10.20, 3.11.16, 3.14.7 에서 실행해 통과. static `test_source_is_python_3_10_syntax` |
| 표준 라이브러리만 사용 | `argparse`, `json`, `csv`, `dataclasses`, `logging`, `heapq`, `zipfile` 등 | static `test_only_standard_library` (모든 import 검사). 테스트도 `unittest` 만 쓴다 |
| JSONL 또는 CSV 중 1개, 저장 파일 3개 이상 | 4.3 참고 | 4.3 참고 |
| 옵션 표기는 `--` | 4.1 참고 | 4.1 참고 |
| 스택트레이스 출력 금지, 오류 종료 코드는 0이 아님 | 4.13 참고. 로그를 열기 전의 오류도 화면에 새지 않게 [`NullHandler`](../budget_app/decorators.py#L39) 를 걸어 둠 | 4.13 참고. static `test_no_traceback_printing`, decorators `test_logging_before_setup_prints_nothing` |

## 8. 결과 예시와 다른 점

명세의 예시는 "정답이 아니라 참고 예시"라고 되어 있다. 문구는 같게 맞췄고 모양만 아래처럼 다르다.

- 금액을 `15000` 대신 `15,000원` 으로 보여 준다.
- 목록에 헤더와 구분선이 있고, 태그 열이 있다.
- `add` 의 카테고리 질문에 등록된 이름을 함께 보여 준다. `카테고리(food, rent): `
- `summary` 에 `초과 여부:` 줄이 항상 있다 (명세 4.9 "초과 여부").

## 테스트가 정말 검사하는지 확인

코드를 일부러 한 군데씩 망가뜨린 뒤 테스트가 실패하는지 봤다. 변형은 36가지다 (정렬 제거, 0원 허용, 사용 중 카테고리 삭제 허용, export 조건 검사 제거, 원자적 교체 제거, 손상된 줄을 조용히 건너뜀, 종료 코드 0, 스택트레이스 노출, `-h` 추가, `--help` 제거 등).

| Python | 테스트가 잡은 변형 |
| --- | --- |
| 3.11.16 | 36 / 36 |
| 3.10.20 | 35 / 36 |

3.10 에서 못 잡은 하나는 "날짜 모양 검사 제거"다. 3.10 에서는 표준 라이브러리가 `20240115` 같은 값을 이미 거부해서 그 검사가 없어도 결과가 같다. 3.11 부터는 표준 라이브러리가 그런 값을 받아들이기 때문에 이 검사가 필요하고, 테스트도 그때 잡는다.

## 손으로 확인한 것

자동 테스트에 넣기 어려워 직접 실행해 확인한 것이다 (2026-09-30).

| 확인한 것 | 방법 | 결과 |
| --- | --- | --- |
| 입력 도중 Ctrl+C | `add` 실행 중인 프로세스에 SIGINT 를 보냄 | `[오류] 실행이 중단되었습니다.` + 힌트, 종료 코드 130, 스택트레이스 없음 |
| 출력을 받는 쪽이 먼저 끝남 | 2만 건에서 `search --type expense \| head -2` | 두 줄만 나오고 오류 메시지 없음, 종료 코드 0 |
| 쓰기 권한이 없는 저장 폴더 | 폴더를 읽기 전용으로 바꾸고 `list` | `[오류] 파일을 읽거나 쓰지 못했습니다 (...): Permission denied` + 힌트, 종료 코드 1 |
| 10만 건 | `python tests/benchmark.py --records 100000` | `list --limit 10` 0.36초·0.05MB, 전부 읽으면 55MB. 자세한 수치는 `docs/peer-review.md` 4-2 |
| README 의 실행 화면 | 빈 폴더에서 README 순서대로 실행 | README 에 실은 출력과 같음 |
| 타입 검사 | `uvx mypy budget_app --strict` (mypy 2.3.1) | `Success: no issues found in 9 source files` |
| 타입 힌트가 잡아 주는 것 | `uvx mypy docs/type_demo.py` (약속을 일부러 어긴 코드) | 오류 5개를 찾아냄: None 가능성, Literal 위반, 인자 타입 2건, 속성 오타 |
| `get` 의 None 검사를 지웠을 때 | 사본에서 그 블록을 주석 처리하고 `uvx mypy budget_app` | `services.py:179: error: Incompatible return value type (got "Transaction \| None", expected "Transaction")` |

## 확인하지 못한 것

- **Windows**: macOS 에서만 실행했다. 경로는 `pathlib`, 인코딩은 전부 UTF-8 로 명시했지만 Windows 에서 직접 돌려 보지는 않았다.
- **실제 전원 차단**: 쓰는 도중 실패하는 상황은 `os.replace` 가 실패하도록 바꿔치기한 테스트로 흉내 냈다.
