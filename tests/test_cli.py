"""E2E 테스트 — 진짜 프로그램(`python -m budget_app ...`)을 새 프로세스로 실행해 확인한다.

동료 평가에서 확인하는 것과 같은 방식이다: 명령을 치고, 화면 출력·종료 코드·저장 파일을 본다.
대괄호 번호는 project.md 의 조항 번호다. 예: [4.5] = "4.5 list (목록 조회)"
"""

import csv
import re
import unittest
import zipfile

from helpers import CATEGORIES, ROOT, TRANSACTIONS, CliCase, read_jsonl, run_cli, seed

# --help 를 확인할 모든 명령 (하위 명령 포함)
ALL_COMMANDS: list[list[str]] = [
    [],
    ["add"], ["list"], ["search"], ["summary"],
    ["budget"], ["budget", "set"], ["budget", "list"],
    ["category"], ["category", "add"], ["category", "list"], ["category", "remove"],
    ["update"], ["delete"], ["import"], ["export"],
    ["backup"],
    ["recurring"], ["recurring", "add"], ["recurring", "list"], ["recurring", "remove"], ["recurring", "apply"],
]

ADD_INPUT = "2024-01-15\nexpense\nfood\n15000\n점심\nmeal\n"  # add 의 질문 6개에 대한 답


def table_ids(stdout: str) -> list[str]:
    """목록 표에서 id 열만 위에서부터 뽑는다."""
    return re.findall(r"^(TX-\d+) \|", stdout, flags=re.MULTILINE)


class SeededCliCase(CliCase):
    def setUp(self) -> None:
        super().setUp()
        seed(self.data)


# ---------------------------------------------------------------------------
# 4.1 실행 및 입력 방식
# ---------------------------------------------------------------------------

class RunAndInputTests(CliCase):
    def test_every_command_has_help(self) -> None:
        """[4.1] 모든 명령은 --help 로 사용 방법이 출력된다"""
        for command in ALL_COMMANDS:
            with self.subTest(command=" ".join(command) or "(최상위)"):
                result = self.cli(*command, "--help")
                self.assert_ok(result)
                self.assertIn("usage: python -m budget_app", result.stdout)
                self.assertIn("--help", result.stdout)
        self.assertFalse(self.data.exists())  # 도움말만 봤을 때는 저장 폴더를 만들지 않는다

    def test_help_lists_the_ten_features(self) -> None:
        """[2] add/list/search/summary/budget/category/update/delete/import/export 명령이 있다"""
        stdout = self.cli("--help").stdout
        for command in ["add", "list", "search", "summary", "budget", "category", "update", "delete", "import", "export"]:
            self.assertRegex(stdout, rf"(?m)^\s+{command}\s")

    def test_short_options_do_not_exist(self) -> None:
        """[4.1][7] 옵션 표기는 -- 로 통일 (짧은 -h, -l 은 없다)"""
        self.assert_error(self.cli("-h"), code=2)
        self.assert_error(self.cli("list", "-l", "3"), code=2)
        for command in ALL_COMMANDS:
            help_text = self.cli(*command, "--help").stdout
            ours = help_text.replace("python -m budget_app", "")  # -m 은 파이썬의 옵션이지 이 앱의 옵션이 아니다
            self.assertEqual(re.findall(r"(?<![\w-])-[A-Za-z]\b", ours), [], msg=command)

    def test_add_is_interactive(self) -> None:
        """[4.1][4.4] add 는 input() 으로 날짜/타입/카테고리/금액/메모/태그를 차례로 입력받는다"""
        seed(self.data)
        result = self.cli("add", stdin=ADD_INPUT)
        self.assert_ok(result)
        prompts = ["날짜(YYYY-MM-DD): ", "타입(income/expense): ", "카테고리(", "금액(양수): ", "메모(선택): ", "태그("]
        positions = [result.stdout.index(prompt) for prompt in prompts]
        self.assertEqual(positions, sorted(positions))  # 질문이 이 순서로 나온다

    def test_usage_errors(self) -> None:
        """[4.13] 없는 명령·빠진 옵션도 [오류]+[힌트], 종료 코드는 0이 아니다"""
        self.assert_error(self.cli(), "--help", code=2)                 # 명령을 안 줌
        self.assert_error(self.cli("lst"), code=2)                      # 없는 명령
        self.assert_error(self.cli("budget"), code=2)                   # 하위 명령을 안 줌
        self.assert_error(self.cli("delete"), "--id", code=2)           # 필수 옵션 누락
        self.assert_error(self.cli("summary"), "--month", code=2)
        self.assert_error(self.cli("list", "--nope"), code=2)           # 없는 옵션
        self.assert_error(self.cli("delete", "--id"), code=2)           # 옵션 값 누락


# ---------------------------------------------------------------------------
# 4.2 데이터 모델 · 4.4 add
# ---------------------------------------------------------------------------

class AddTests(SeededCliCase):
    def test_add_prints_success_and_id(self) -> None:
        """[4.4] 저장 완료 시 생성된 id 를 출력한다"""
        result = self.cli("add", stdin=ADD_INPUT)
        self.assert_ok(result)
        self.assertIn("[저장 완료] id=TX-000008", result.stdout)

    def test_added_record_has_all_fields(self) -> None:
        """[4.2] 거래는 id/type/date/amount/category/memo/tags 를 갖는다"""
        self.cli("add", stdin=ADD_INPUT)
        self.assertEqual(self.records()[-1], {
            "id": "TX-000008", "type": "expense", "date": "2024-01-15", "amount": 15000,
            "category": "food", "memo": "점심", "tags": ["meal"],
        })

    def test_memo_and_tags_are_optional(self) -> None:
        """[4.2] memo, tags 는 비워 둘 수 있다"""
        self.assert_ok(self.cli("add", stdin="2024-01-16\nincome\nsalary\n100\n\n\n"))
        self.assertEqual((self.records()[-1]["memo"], self.records()[-1]["tags"]), ("", []))

    def test_ids_are_unique(self) -> None:
        """[4.2] id 는 유일하다"""
        for _ in range(3):
            self.cli("add", stdin=ADD_INPUT)
        ids = [record["id"] for record in self.records()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[-3:], ["TX-000008", "TX-000009", "TX-000010"])

    def test_invalid_input_is_asked_again(self) -> None:
        """[4.2] 날짜 형식 오류 / 음수·0 금액 / 허용되지 않은 type / 없는 category → 재입력 요구"""
        answers = "\n".join([
            "2024-13-40", "20240115", "2024-01-16",  # 날짜: 두 번 틀리고 세 번째에 맞음
            "spend", "expense",                      # 타입
            "cafe", "food",                          # 카테고리 (등록되지 않은 이름)
            "-5", "0", "abc", "1500",                # 금액
            "", "",                                  # 메모, 태그
        ]) + "\n"
        result = self.cli("add", stdin=answers)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stderr.count("[오류]"), 7)
        self.assertEqual(result.stderr.count("[힌트]"), 7)
        self.assertEqual(result.stdout.count("날짜(YYYY-MM-DD): "), 3)  # 같은 질문을 다시 한다
        self.assertEqual(result.stdout.count("금액(양수): "), 4)
        self.assertIn("날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).", result.stderr)
        self.assertIn("등록되지 않은 카테고리입니다: cafe", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        saved = self.records()
        self.assertEqual(len(saved), len(TRANSACTIONS) + 1)  # 틀린 값은 하나도 저장되지 않았다
        self.assertEqual((saved[-1]["date"], saved[-1]["amount"]), ("2024-01-16", 1500))

    def test_input_ending_early_saves_nothing(self) -> None:
        """[4.13] 입력 도중에 끝나면(Ctrl+D) 아무것도 저장하지 않고 0이 아닌 코드로 끝난다"""
        result = self.cli("add", stdin="2024-01-16\nexpense\n")
        self.assert_error(result, code=130)
        self.assertEqual(len(self.records()), len(TRANSACTIONS))


# ---------------------------------------------------------------------------
# 4.3 저장 정책
# ---------------------------------------------------------------------------

class StorageTests(CliCase):
    def test_first_run_creates_files_and_says_so(self) -> None:
        """[4.3] 저장 파일이 없으면 자동 생성하고 안내 메시지를 출력한다"""
        result = self.cli("list")
        self.assert_ok(result)
        self.assertIn("[안내] 저장 파일을 새로 만들었습니다", result.stdout)
        for name in ["transactions.jsonl", "categories.jsonl", "budgets.jsonl"]:
            self.assertTrue((self.data / name).is_file(), msg=name)
        self.assertNotIn("[안내]", self.cli("list").stdout)  # 두 번째 실행부터는 안내가 없다

    def test_default_folder_is_data_under_current_directory(self) -> None:
        """[4.3] 기본 저장 폴더는 ./data"""
        result = run_cli("category", "list", cwd=self.tmp)  # --data-dir 없이, 임시 폴더에서 실행
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue((self.tmp / "data" / "transactions.jsonl").is_file())

    def test_data_dir_option_works_before_and_after_command(self) -> None:
        """[4.3] --data-dir 로 저장 폴더를 바꿀 수 있다"""
        first, second, third = self.tmp / "a", self.tmp / "b", self.tmp / "c"
        self.assertEqual(run_cli("--data-dir", str(first), "list").returncode, 0)
        self.assertEqual(run_cli("list", "--data-dir", str(second)).returncode, 0)
        self.assertEqual(run_cli("category", "--data-dir", str(third), "list").returncode, 0)
        for folder in (first, second, third):
            self.assertTrue((folder / "categories.jsonl").is_file(), msg=str(folder))
        self.assertFalse((ROOT / "a").exists())

    def test_add_is_blocked_until_a_category_exists(self) -> None:
        """[4.3] 카테고리가 비어 있으면 category add 를 먼저 하도록 안내하고 add 를 막는다 (안 B)"""
        result = self.cli("add", stdin=ADD_INPUT)
        self.assert_error(result, "등록된 카테고리가 없어", "category add")
        self.assertNotIn("날짜(YYYY-MM-DD)", result.stdout)  # 질문을 시작하지도 않는다
        self.assertEqual(self.records(), [])
        self.assertEqual(self.records("categories"), [])     # 기본 카테고리를 자동으로 만들지 않는다

        self.assert_ok(self.cli("category", "add", stdin="food\n"))
        self.assert_ok(self.cli("add", stdin=ADD_INPUT))
        self.assertEqual(len(self.records()), 1)

    def test_data_survives_restart(self) -> None:
        """[4.3] 프로그램을 다시 실행해도 거래/카테고리/예산이 유지된다 (저장 파일 3개 이상)"""
        self.cli("category", "add", stdin="food\n")
        self.cli("add", stdin=ADD_INPUT)
        self.cli("budget", "set", "--month", "2024-01", "--amount", "500000")
        # 아래 세 명령은 각각 새 프로세스다 — 메모리가 아니라 파일에서 읽어 와야 보인다
        self.assertIn("TX-000001", self.cli("list").stdout)
        self.assertIn("- food", self.cli("category", "list").stdout)
        self.assertIn("500,000원", self.cli("budget", "list").stdout)
        stored = sorted(path.name for path in self.data.glob("*.jsonl") if path.stat().st_size > 0)
        self.assertEqual(stored, ["budgets.jsonl", "categories.jsonl", "transactions.jsonl"])

    def test_files_are_jsonl(self) -> None:
        """[4.3] 저장 포맷은 JSONL — 한 줄이 JSON 객체 하나"""
        seed(self.data)
        for name in ["transactions", "categories"]:
            lines = (self.data / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), len(read_jsonl(self.data / f"{name}.jsonl")))
            self.assertTrue(all(line.startswith("{") and line.endswith("}") for line in lines))


# ---------------------------------------------------------------------------
# 4.5 list
# ---------------------------------------------------------------------------

class ListTests(SeededCliCase):
    def test_list_is_newest_first(self) -> None:
        """[4.5] list 는 최신순으로 출력한다"""
        result = self.cli("list")
        self.assert_ok(result)
        self.assertEqual(table_ids(result.stdout),
                         ["TX-000006", "TX-000005", "TX-000007", "TX-000004", "TX-000003", "TX-000002", "TX-000001"])

    def test_limit(self) -> None:
        """[4.5] --limit N"""
        result = self.cli("list", "--limit", "3")
        self.assert_ok(result)
        self.assertEqual(table_ids(result.stdout), ["TX-000006", "TX-000005", "TX-000007"])

    def test_limit_has_a_default(self) -> None:
        """[4.5] --limit 을 주지 않으면 기본값(10건)을 쓴다"""
        for _ in range(5):
            self.cli("add", stdin=ADD_INPUT)  # 총 12건
        self.assertEqual(len(table_ids(self.cli("list").stdout)), 10)
        self.assertEqual(len(table_ids(self.cli("list", "--limit", "50").stdout)), 12)

    def test_bad_limit(self) -> None:
        """[4.5] --limit 에 0, 음수, 글자를 주면 오류 메시지"""
        for wrong in ["0", "-1", "abc"]:
            with self.subTest(wrong=wrong):
                self.assert_error(self.cli("list", "--limit", wrong), "--limit")

    def test_row_shows_the_transaction(self) -> None:
        """[4.5] 한 행에 id·날짜·타입·카테고리·금액·메모·태그가 나온다"""
        line = next(line for line in self.cli("list").stdout.splitlines() if line.startswith("TX-000005"))
        self.assertEqual([cell.strip() for cell in line.split("|")],
                         ["TX-000005", "2024-01-20", "expense", "food", "30,000원", "저녁 회식", "meal,team"])

    def test_empty_list(self) -> None:
        """[4.5] 거래가 하나도 없을 때"""
        result = run_cli("list", data_dir=self.tmp / "empty")
        self.assertEqual(result.returncode, 0)
        self.assertIn("기록된 거래가 없습니다", result.stdout)


# ---------------------------------------------------------------------------
# 4.6 update / delete
# ---------------------------------------------------------------------------

class UpdateDeleteTests(SeededCliCase):
    def test_delete(self) -> None:
        """[4.6] delete --id <id> 로 거래를 삭제한다"""
        result = self.cli("delete", "--id", "TX-000002")
        self.assert_ok(result)
        self.assertIn("[삭제 완료] id=TX-000002", result.stdout)
        self.assertNotIn("TX-000002", [record["id"] for record in self.records()])
        self.assertEqual(len(self.records()), len(TRANSACTIONS) - 1)

    def test_delete_missing_id(self) -> None:
        """[4.6] 존재하지 않는 id 는 '없는 데이터'로 처리하고 메시지를 출력한다"""
        before = (self.data / "transactions.jsonl").read_bytes()
        self.assert_error(self.cli("delete", "--id", "TX-000099"), "없는 데이터", "TX-000099")
        self.assertEqual((self.data / "transactions.jsonl").read_bytes(), before)

    def test_update_by_options(self) -> None:
        """[4.6] update --id <id> [--date] [--type] [--category] [--amount] [--memo] [--tags] (옵션 방식)"""
        result = self.cli("update", "--id", "TX-000004", "--amount", "18000", "--memo", "점심 + 커피")
        self.assert_ok(result)
        self.assertIn("[수정 완료] id=TX-000004", result.stdout)
        record = self.records()[3]
        self.assertEqual(record, {"id": "TX-000004", "type": "expense", "date": "2024-01-15", "amount": 18000,
                                  "category": "food", "memo": "점심 + 커피", "tags": ["meal"]})

    def test_update_all_options(self) -> None:
        """[4.6] update 의 옵션 6개를 한꺼번에"""
        self.assert_ok(self.cli("update", "--id", "TX-000004", "--date", "2024-02-10", "--type", "income",
                                "--category", "salary", "--amount", "5", "--memo", "", "--tags", "a, b"))
        self.assertEqual(self.records()[3], {"id": "TX-000004", "type": "income", "date": "2024-02-10", "amount": 5,
                                             "category": "salary", "memo": "", "tags": ["a", "b"]})

    def test_update_missing_id(self) -> None:
        """[4.6] update 도 없는 id 는 '없는 데이터'"""
        self.assert_error(self.cli("update", "--id", "TX-000099", "--amount", "1"), "없는 데이터")

    def test_update_rejects_bad_values(self) -> None:
        """[4.6] 잘못된 값으로 수정하려 하면 오류이고 파일은 그대로다"""
        before = (self.data / "transactions.jsonl").read_bytes()
        self.assert_error(self.cli("update", "--id", "TX-000004", "--amount", "-1"), "금액")
        self.assert_error(self.cli("update", "--id", "TX-000004", "--date", "2024-02-30"), "날짜")
        self.assert_error(self.cli("update", "--id", "TX-000004", "--type", "spend"), "타입")
        self.assert_error(self.cli("update", "--id", "TX-000004", "--category", "cafe"), "등록되지 않은 카테고리")
        self.assert_error(self.cli("update", "--id", "TX-000004"), "바뀐 내용이 없습니다")
        self.assertEqual((self.data / "transactions.jsonl").read_bytes(), before)

    def test_file_is_whole_after_update_and_delete(self) -> None:
        """[4.6] 수정/삭제 뒤에도 파일은 온전하고 임시 파일이 남지 않는다 (임시 파일 + 원자적 교체)"""
        self.cli("update", "--id", "TX-000001", "--amount", "1")
        self.cli("delete", "--id", "TX-000003")
        self.assertEqual([record["id"] for record in self.records()],
                         ["TX-000001", "TX-000002", "TX-000004", "TX-000005", "TX-000006", "TX-000007"])
        self.assertEqual(list(self.data.glob("*.tmp")), [])


# ---------------------------------------------------------------------------
# 4.7 search
# ---------------------------------------------------------------------------

class SearchTests(SeededCliCase):
    def test_each_option(self) -> None:
        """[4.7] --from/--to, --category, --type, --q, --tag — 결과는 최신순"""
        cases = [
            (["--from", "2024-01-13", "--to", "2024-01-15"], ["TX-000007", "TX-000004", "TX-000003"]),
            (["--from", "2024-01-20"], ["TX-000006", "TX-000005"]),
            (["--to", "2024-01-05"], ["TX-000001"]),
            (["--category", "food"], ["TX-000006", "TX-000005", "TX-000004"]),
            (["--type", "income"], ["TX-000003"]),
            (["--q", "회식"], ["TX-000005"]),
            (["--tag", "meal"], ["TX-000005", "TX-000004"]),
            (["--category", "food", "--tag", "meal", "--to", "2024-01-15"], ["TX-000004"]),
            (["--category", "food", "--limit", "1"], ["TX-000006"]),
            ([], ["TX-000006", "TX-000005", "TX-000007", "TX-000004", "TX-000003", "TX-000002", "TX-000001"]),
        ]
        for options, expected in cases:
            with self.subTest(options=" ".join(options)):
                result = self.cli("search", *options)
                self.assert_ok(result)
                self.assertEqual(table_ids(result.stdout), expected)

    def test_no_match(self) -> None:
        """[4.7] 조건에 맞는 거래가 없을 때"""
        result = self.cli("search", "--category", "rent", "--type", "income")
        self.assert_ok(result)
        self.assertIn("조건에 맞는 거래가 없습니다", result.stdout)

    def test_bad_options(self) -> None:
        """[4.7] 잘못된 검색 옵션은 오류 메시지"""
        self.assert_error(self.cli("search", "--from", "2024-13-01"), "날짜")
        self.assert_error(self.cli("search", "--from", "2024-02-01", "--to", "2024-01-01"), "--from")
        self.assert_error(self.cli("search", "--type", "xx"), "타입")
        self.assert_error(self.cli("search", "--limit", "0"), "--limit")


# ---------------------------------------------------------------------------
# 4.8 summary · 4.9 budget
# ---------------------------------------------------------------------------

class SummaryBudgetTests(SeededCliCase):
    def test_summary(self) -> None:
        """[4.8] 총 수입, 총 지출, 잔액, 카테고리별 지출 TOP N"""
        result = self.cli("summary", "--month", "2024-01", "--top", "3")
        self.assert_ok(result)
        for line in ["총 수입: 3,000,000원", "총 지출: 220,000원", "잔액: 2,780,000원", "지출 TOP 3",
                     "1) rent 150,000원", "2) food 45,000원", "3) transport 25,000원"]:
            self.assertIn(line, result.stdout.splitlines())

    def test_top_option(self) -> None:
        """[4.8] --top"""
        stdout = self.cli("summary", "--month", "2024-01", "--top", "1").stdout
        self.assertIn("지출 TOP 1", stdout)
        self.assertIn("1) rent 150,000원", stdout)
        self.assertNotIn("2) food", stdout)
        self.assertIn("지출 TOP 3", self.cli("summary", "--month", "2024-01").stdout)  # 기본값 3

    def test_empty_month_says_no_data(self) -> None:
        """[4.8] 데이터가 없는 달은 "데이터 없음"을 명확히 출력한다"""
        result = self.cli("summary", "--month", "2023-05")
        self.assert_ok(result)
        self.assertIn("데이터 없음", result.stdout)

    def test_bad_month(self) -> None:
        """[4.8] 잘못된 --month, --top 은 오류 메시지"""
        self.assert_error(self.cli("summary", "--month", "2024-1"), "YYYY-MM")
        self.assert_error(self.cli("summary", "--month", "2024-01", "--top", "0"), "--top")

    def test_budget_set(self) -> None:
        """[4.9] budget set --month YYYY-MM --amount <금액> 으로 월 예산을 저장한다"""
        result = self.cli("budget", "set", "--month", "2024-01", "--amount", "500000")
        self.assert_ok(result)
        self.assertIn("[저장 완료] 2024-01 예산 500,000원", result.stdout)
        self.assertEqual(self.records("budgets"), [{"month": "2024-01", "amount": 500000}])  # 영구 저장

    def test_summary_shows_usage_when_budget_is_set(self) -> None:
        """[4.9] 예산이 있으면 summary 가 사용률(%)과 초과 여부를 함께 출력한다"""
        self.assertIn("예산: 미설정", self.cli("summary", "--month", "2024-01").stdout)
        self.cli("budget", "set", "--month", "2024-01", "--amount", "500000")
        stdout = self.cli("summary", "--month", "2024-01").stdout
        self.assertIn("예산: 500,000원 (사용률 44.0%)", stdout)
        self.assertIn("초과 여부: 초과 아님", stdout)
        self.assertNotIn("[경고]", stdout)

    def test_summary_warns_when_over_budget(self) -> None:
        """[4.9] 예산을 초과하면 경고 문구를 출력한다"""
        self.cli("budget", "set", "--month", "2024-01", "--amount", "500000")
        self.cli("budget", "set", "--month", "2024-01", "--amount", "200000")  # 다시 설정하면 바뀐다
        self.assertEqual(self.records("budgets"), [{"month": "2024-01", "amount": 200000}])
        stdout = self.cli("summary", "--month", "2024-01").stdout
        self.assertIn("예산: 200,000원 (사용률 110.0%)", stdout)
        self.assertIn("초과 여부: 초과", stdout)
        self.assertIn("[경고]", stdout)
        self.assertIn("20,000원", stdout)

    def test_budget_list_and_bad_values(self) -> None:
        """[4.9] 예산 조회(budget list)와 잘못된 예산 값"""
        self.assertIn("설정된 예산이 없습니다", self.cli("budget", "list").stdout)
        self.cli("budget", "set", "--month", "2024-02", "--amount", "300,000")
        self.assertIn("2024-02 | 300,000원", self.cli("budget", "list").stdout)
        self.assert_error(self.cli("budget", "set", "--month", "2024-02", "--amount", "0"), "금액")
        self.assert_error(self.cli("budget", "set", "--month", "24-02", "--amount", "100"), "YYYY-MM")
        self.assert_error(self.cli("budget", "set", "--month", "2024-02"), "--amount", code=2)


# ---------------------------------------------------------------------------
# 4.10 category
# ---------------------------------------------------------------------------

class CategoryTests(SeededCliCase):
    def test_add_list_remove(self) -> None:
        """[4.10] category add / list / remove"""
        added = self.cli("category", "add", stdin="Cafe\n")
        self.assert_ok(added)
        self.assertIn("카테고리명: ", added.stdout)
        self.assertIn("[저장 완료] category=cafe", added.stdout)

        listed = self.cli("category", "list")
        self.assert_ok(listed)
        self.assertEqual(listed.stdout.splitlines(), ["- cafe", "- food", "- rent", "- salary", "- transport"])

        removed = self.cli("category", "remove", stdin="cafe\n")
        self.assert_ok(removed)
        self.assertIn("[삭제 완료] category=cafe", removed.stdout)
        self.assertNotIn("cafe", self.cli("category", "list").stdout)

    def test_remove_is_blocked_while_in_use(self) -> None:
        """[4.10] 사용 중인 카테고리는 삭제를 막는다"""
        result = self.cli("category", "remove", stdin="food\n")
        self.assert_error(result, "사용 중인 카테고리는 삭제할 수 없습니다", "거래 3건")
        self.assertEqual(len(self.records("categories")), len(CATEGORIES))
        self.assertIn("- food", self.cli("category", "list").stdout)

    def test_duplicate_missing_and_empty(self) -> None:
        """[4.10] 이미 있는 이름 추가, 없는 이름 삭제, 빈 이름 입력"""
        self.assert_error(self.cli("category", "add", stdin="food\n"), "이미 등록된 카테고리")
        self.assert_error(self.cli("category", "remove", stdin="nothing\n"), "없는 데이터")
        retried = self.cli("category", "add", stdin="\n  \ngym\n")  # 빈 이름은 다시 묻는다
        self.assertEqual(retried.returncode, 0)
        self.assertEqual(retried.stderr.count("[오류]"), 2)
        self.assertIn("category=gym", retried.stdout)


# ---------------------------------------------------------------------------
# 4.11 import / export
# ---------------------------------------------------------------------------

class ImportExportTests(SeededCliCase):
    def test_export_needs_a_period(self) -> None:
        """[4.11] export 는 --month 또는 --from/--to 중 하나 이상 조건이 필수"""
        out = self.tmp / "export.csv"
        self.assert_error(self.cli("export", "--out", str(out)), "기간 조건", "--month")
        self.assert_error(self.cli("export", "--out", str(out), "--from", "2024-01-01"), "기간 조건")
        self.assertFalse(out.exists())
        self.assert_error(self.cli("export", "--month", "2024-01"), "--out", code=2)

    def test_export_by_month(self) -> None:
        """[4.11] export --out <csv> --month YYYY-MM : 처리 건수 출력 + CSV 생성 (UTF-8, 헤더, 컬럼)"""
        out = self.tmp / "export.csv"
        result = self.cli("export", "--out", str(out), "--month", "2024-01")
        self.assert_ok(result)
        self.assertIn(f"[완료] {out} (6 records)", result.stdout)

        raw = out.read_bytes()
        self.assertEqual(raw.decode("utf-8").splitlines()[0], "date,type,category,amount,memo,tags")
        with out.open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0], {"date": "2024-01-05", "type": "expense", "category": "rent",
                                   "amount": "150000", "memo": "월세", "tags": "home,fixed"})

    def test_export_by_range(self) -> None:
        """[4.11] export --out <csv> --from YYYY-MM-DD --to YYYY-MM-DD"""
        out = self.tmp / "export.csv"
        result = self.cli("export", "--out", str(out), "--from", "2024-01-12", "--to", "2024-01-15")
        self.assert_ok(result)
        self.assertIn("(4 records)", result.stdout)
        self.assertEqual(len(out.read_text(encoding="utf-8").splitlines()), 5)

    def test_export_will_not_overwrite_data_file(self) -> None:
        """[4.11] export 가 저장 파일(transactions.jsonl)을 덮어쓰지 못하게 막는다"""
        target = self.data / "transactions.jsonl"
        before = target.read_bytes()
        self.assert_error(self.cli("export", "--out", str(target), "--month", "2024-01"), ".csv")
        self.assertEqual(target.read_bytes(), before)

    def test_import(self) -> None:
        """[4.11] import --from <csv> : 처리 건수 출력 + 거래 반영"""
        source = self.tmp / "import.csv"
        source.write_text(
            "date,type,category,amount,memo,tags\n"
            '2024-03-01,expense,food,12000,김밥,"meal,lunch"\n'
            "2024-03-02,income,salary,3000000,3월 월급,\n",
            encoding="utf-8",
        )
        result = self.cli("import", "--from", str(source))
        self.assert_ok(result)
        self.assertIn("[완료] imported=2, skipped=0", result.stdout)
        self.assertEqual(self.records()[-2], {"id": "TX-000008", "type": "expense", "date": "2024-03-01",
                                              "amount": 12000, "category": "food", "memo": "김밥",
                                              "tags": ["meal", "lunch"]})
        self.assertIn("TX-000009", self.cli("list", "--limit", "1").stdout)

    def test_import_reports_broken_rows(self) -> None:
        """[4.11] 깨진 행은 건너뛰고 줄 번호와 이유를 알려 준다 (부분 성공 + 리포트)"""
        source = self.tmp / "import.csv"
        source.write_text(
            "date,type,category,amount,memo,tags\n"
            "2024-03-01,expense,food,12000,정상,\n"
            "2024-03-32,expense,food,1000,날짜 오류,\n"
            "2024-03-03,expense,cafe,4500,등록되지 않은 카테고리,\n"
            "2024-03-04,expense,food,-100,음수,\n",
            encoding="utf-8",
        )
        result = self.cli("import", "--from", str(source))
        self.assert_ok(result)
        self.assertIn("[완료] imported=1, skipped=3", result.stdout)
        self.assertIn("3번째 줄 건너뜀: 날짜 형식", result.stdout)
        self.assertIn("4번째 줄 건너뜀: 등록되지 않은 카테고리입니다: cafe", result.stdout)
        self.assertIn("5번째 줄 건너뜀: 금액", result.stdout)
        self.assertEqual(len(self.records()), len(TRANSACTIONS) + 1)

    def test_import_file_errors(self) -> None:
        """[4.13] 파일 오류도 스택트레이스 없이 원인 + 힌트"""
        before = (self.data / "transactions.jsonl").read_bytes()
        self.assert_error(self.cli("import", "--from", str(self.tmp / "nope.csv")), "찾을 수 없습니다")

        no_header = self.tmp / "no_header.csv"
        no_header.write_text("a,b\n1,2\n", encoding="utf-8")
        self.assert_error(self.cli("import", "--from", str(no_header)), "필수 컬럼", "date,type,category,amount,memo,tags")

        cp949 = self.tmp / "cp949.csv"
        cp949.write_bytes("date,type,category,amount,memo,tags\n2024-03-01,expense,food,100,점심,\n".encode("cp949"))
        self.assert_error(self.cli("import", "--from", str(cp949)), "UTF-8")
        self.assertEqual((self.data / "transactions.jsonl").read_bytes(), before)

    def test_import_accepts_excel_utf8_bom(self) -> None:
        """[4.11] 엑셀의 'CSV UTF-8' (BOM 포함) 파일도 가져온다"""
        source = self.tmp / "bom.csv"
        source.write_text("date,type,category,amount,memo,tags\n2024-03-01,expense,food,100,점심,\n", encoding="utf-8-sig")
        self.assertIn("imported=1, skipped=0", self.cli("import", "--from", str(source)).stdout)

    def test_export_then_import_into_another_ledger(self) -> None:
        """[4.11] export 한 CSV 를 그대로 import 할 수 있다 (같은 스키마)"""
        out = self.tmp / "all.csv"
        self.cli("export", "--out", str(out), "--from", "2000-01-01", "--to", "2999-12-31")
        other = self.tmp / "other"
        for name in CATEGORIES:
            run_cli("category", "add", data_dir=other, stdin=f"{name}\n")
        result = run_cli("import", "--from", str(out), data_dir=other)
        self.assertIn(f"[완료] imported={len(TRANSACTIONS)}, skipped=0", result.stdout)
        self.assertEqual(read_jsonl(other / "transactions.jsonl"), self.records())


# ---------------------------------------------------------------------------
# 4.12 데코레이터 · 4.13 예외 처리 및 종료 코드
# ---------------------------------------------------------------------------

class DecoratorAndErrorTests(SeededCliCase):
    def test_decorators_write_the_log(self) -> None:
        """[4.12] 공통 기능(실행 로그, 실행 시간)이 데코레이터로 실제 적용되어 있다"""
        self.cli("list")
        self.cli("delete", "--id", "TX-000099")
        log = (self.data / "app.log").read_text(encoding="utf-8")
        self.assertIn("[list] 시작", log)
        self.assertIn("[list] 성공", log)
        self.assertRegex(log, r"TransactionService\.list_recent 실행 시간: \d+\.\d\dms")
        self.assertIn("[delete] 실패: NotFoundError", log)

    def test_success_exits_zero(self) -> None:
        """[4.13] 정상 종료는 0"""
        for command in (["list"], ["search", "--q", "점심"], ["summary", "--month", "2024-01"],
                        ["category", "list"], ["budget", "list"], ["backup"]):
            with self.subTest(command=" ".join(command)):
                self.assertEqual(self.cli(*command).returncode, 0)

    def test_errors_exit_nonzero_without_traceback(self) -> None:
        """[4.13][7] 오류는 원인 + 힌트, 스택트레이스 없음, 종료 코드는 0이 아님"""
        commands = [
            ["delete", "--id", "TX-000099"],
            ["delete", "--id", "abc"],
            ["update", "--id", "TX-000001", "--amount", "0"],
            ["list", "--limit", "abc"],
            ["search", "--type", "xx"],
            ["summary", "--month", "2024-13"],
            ["budget", "set", "--month", "2024-01", "--amount", "-1"],
            ["import", "--from", "없는파일.csv"],
            ["export", "--out", "x.csv"],
            ["recurring", "apply", "--month", "x"],
        ]
        for command in commands:
            with self.subTest(command=" ".join(command)):
                self.assert_error(self.cli(*command))

    def test_error_goes_to_stderr_not_stdout(self) -> None:
        """[4.13] 오류 메시지는 stdout 이 아니라 stderr 로 나간다"""
        result = self.cli("delete", "--id", "TX-000099")
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.startswith("[오류] "))

    def test_damaged_data_file(self) -> None:
        """[4.13] 저장 파일이 손상되어도 스택트레이스 없이 몇 번째 줄인지 알려 준다"""
        with (self.data / "transactions.jsonl").open("a", encoding="utf-8") as file:
            file.write('{"id": "TX-000777", "type": "expense"\n')
        for command in (["list"], ["summary", "--month", "2024-01"], ["search"], ["delete", "--id", "TX-000777"]):
            with self.subTest(command=" ".join(command)):
                self.assert_error(self.cli(*command), "transactions.jsonl", "8번째 줄")

    def test_unusable_data_dir(self) -> None:
        """[4.13] 저장 폴더를 쓸 수 없을 때(폴더 자리에 파일이 있음)도 원인 + 힌트"""
        blocker = self.tmp / "not_a_folder"
        blocker.write_text("", encoding="utf-8")
        result = run_cli("list", data_dir=blocker)
        self.assert_error(result, "파일을 읽거나 쓰지 못했습니다")

    def test_data_file_replaced_by_folder(self) -> None:
        """[4.13] 저장 파일 자리에 폴더가 있어 쓸 수 없을 때도 원인 + 힌트"""
        (self.data / "budgets.jsonl").unlink()
        (self.data / "budgets.jsonl").mkdir()
        self.assert_error(self.cli("budget", "set", "--month", "2024-01", "--amount", "100"), "파일을 읽거나 쓰지 못했습니다")


# ---------------------------------------------------------------------------
# 5. 보너스
# ---------------------------------------------------------------------------

class BonusTests(SeededCliCase):
    def test_backup(self) -> None:
        """[5-1] backup 은 타임스탬프가 포함된 백업 파일을 만든다"""
        result = self.cli("backup")
        self.assert_ok(result)
        created = list((self.data / "backups").glob("*.zip"))
        self.assertEqual(len(created), 1)
        self.assertRegex(created[0].name, r"^backup-\d{8}-\d{6}\.zip$")
        self.assertIn(created[0].name, result.stdout)
        with zipfile.ZipFile(created[0]) as archive:
            self.assertEqual(archive.read("transactions.jsonl"), (self.data / "transactions.jsonl").read_bytes())
            self.assertIn("categories.jsonl", archive.namelist())
            self.assertIn("budgets.jsonl", archive.namelist())

    def test_recurring(self) -> None:
        """[5-2] 반복 내역을 등록하고, 특정 월에 자동 생성한다"""
        added = self.cli("recurring", "add", stdin="31\nexpense\nrent\n500000\n월세\nfixed\n")
        self.assert_ok(added)
        self.assertIn("[저장 완료] id=RC-000001", added.stdout)
        self.assertIn("RC-000001", self.cli("recurring", "list").stdout)

        applied = self.cli("recurring", "apply", "--month", "2024-02")
        self.assert_ok(applied)
        self.assertIn("2024-02 반복 내역 1건 생성", applied.stdout)
        self.assertEqual(self.records()[-1], {"id": "TX-000008", "type": "expense", "date": "2024-02-29",
                                              "amount": 500000, "category": "rent", "memo": "월세", "tags": ["fixed"]})

        again = self.cli("recurring", "apply", "--month", "2024-02")  # 같은 달에 다시 → 중복 없음
        self.assertIn("반복 내역 0건 생성", again.stdout)
        self.assertEqual(len(self.records()), len(TRANSACTIONS) + 1)

        self.assert_error(self.cli("category", "remove", stdin="rent\n"), "반복 규칙 1건")
        self.assert_ok(self.cli("recurring", "remove", "--id", "RC-000001"))
        self.assertIn("등록된 반복 규칙이 없습니다", self.cli("recurring", "list").stdout)
        self.assert_error(self.cli("recurring", "remove", "--id", "RC-000001"), "없는 데이터")

    def test_table_columns_line_up_with_korean(self) -> None:
        """[5-3] 외부 라이브러리 없이 표를 정렬한다 — 한글(2칸)이 섞여도 구분선 위치가 같다"""
        import unicodedata

        def column_positions(line: str) -> list[int]:
            positions, width = [], 0
            for char in line:
                if char in "|+":
                    positions.append(width)
                width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
            return positions

        lines = [line for line in self.cli("list").stdout.splitlines() if "|" in line or "+" in line]
        self.assertGreater(len(lines), 3)
        self.assertEqual(len({tuple(column_positions(line)) for line in lines}), 1)


if __name__ == "__main__":
    unittest.main()
