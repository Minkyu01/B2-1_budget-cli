"""저장소 계층 테스트 — JSONL 읽기/쓰기, 제너레이터, 원자적 교체, CSV, 백업.

대괄호 번호는 project.md 의 조항 번호다.
"""

import inspect
import json
import re
import unittest
import zipfile
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

from helpers import TempDirCase, read_jsonl
from budget_app.errors import AppError, NotFoundError
from budget_app.models import Budget, Category, Transaction
from budget_app.storage import (
    CSV_COLUMNS,
    BudgetRepository,
    CategoryRepository,
    RecurringRepository,
    TransactionRepository,
    create_backup,
    read_csv_rows,
    write_transactions_csv,
)


def tx(number: int, **changes: object) -> Transaction:
    fields: dict = {
        "id": f"TX-{number:06d}",
        "type": "expense",
        "date": "2024-01-15",
        "amount": 1000 * number,
        "category": "food",
        "memo": f"메모 {number}",
        "tags": [],
    }
    fields.update(changes)
    return Transaction(**fields)


class RepositoryCase(TempDirCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = TransactionRepository(self.data / "transactions.jsonl")
        self.repo.ensure_file()


class ReadWriteTests(RepositoryCase):
    def test_ensure_file_creates_folder_and_file_once(self) -> None:
        """[4.3] 저장 파일이 없으면 자동으로 만든다"""
        repo = CategoryRepository(self.tmp / "deep" / "folder" / "categories.jsonl")
        self.assertTrue(repo.ensure_file())   # 새로 만들었으면 True
        self.assertTrue(repo.path.exists())
        self.assertFalse(repo.ensure_file())  # 이미 있으면 False, 내용은 건드리지 않는다

    def test_stream_of_missing_file_is_empty(self) -> None:
        """[4.3] 파일이 아직 없으면 빈 목록처럼 동작한다"""
        repo = TransactionRepository(self.tmp / "nothing.jsonl")
        self.assertEqual(list(repo.stream()), [])

    def test_append_then_stream_round_trip(self) -> None:
        """[4.3] JSONL: 한 줄 = 거래 하나"""
        self.assertEqual(self.repo.append([tx(1), tx(2, tags=["a", "b"])]), 2)
        self.assertEqual(list(self.repo.stream()), [tx(1), tx(2, tags=["a", "b"])])
        lines = self.repo.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["id"], "TX-000001")

    def test_korean_is_stored_readable(self) -> None:
        """[4.3] 한글을 그대로 저장한다 (UTF-8)"""
        self.repo.append([tx(1, memo="점심")])
        self.assertIn("점심", self.repo.path.read_text(encoding="utf-8"))  # \\uXXXX 로 바뀌지 않는다

    def test_blank_lines_are_skipped(self) -> None:
        """[4.3] 빈 줄은 건너뛴다"""
        self.repo.append([tx(1)])
        with self.repo.path.open("a", encoding="utf-8") as file:
            file.write("\n   \n")
        self.repo.append([tx(2)])
        self.assertEqual([item.id for item in self.repo.stream()], ["TX-000001", "TX-000002"])

    def test_find_exists_last_number(self) -> None:
        """[4.2] id 로 찾기, 가장 큰 번호 구하기"""
        self.assertEqual(self.repo.last_number(), 0)
        self.repo.append([tx(1), tx(7), tx(3)])
        self.assertEqual(self.repo.find("TX-000007"), tx(7))
        self.assertIsNone(self.repo.find("TX-000099"))
        self.assertTrue(self.repo.exists("TX-000003"))
        self.assertEqual(self.repo.last_number(), 7)  # 줄 순서가 아니라 가장 큰 번호

    def test_other_repositories_use_their_own_key(self) -> None:
        """[4.3] 카테고리는 name, 예산은 month 로 구분한다"""
        categories = CategoryRepository(self.data / "categories.jsonl")
        categories.append([Category("food"), Category("rent")])
        self.assertTrue(categories.exists("rent"))
        budgets = BudgetRepository(self.data / "budgets.jsonl")
        budgets.upsert(Budget(month="2024-01", amount=500000))
        budgets.upsert(Budget(month="2024-01", amount=200000))  # 같은 달 → 교체
        self.assertEqual(read_jsonl(budgets.path), [{"month": "2024-01", "amount": 200000}])
        self.assertEqual(RecurringRepository(self.data / "recurring.jsonl").last_number(), 0)


class GeneratorTests(RepositoryCase):
    def test_stream_is_a_generator(self) -> None:
        """[4.5] 파일 전체를 한 번에 읽지 않고 제너레이터로 한 줄씩 흘려보낸다"""
        self.assertTrue(inspect.isgeneratorfunction(TransactionRepository.stream))
        stream = self.repo.stream()
        self.assertIsInstance(stream, Iterator)
        self.assertTrue(inspect.isgenerator(stream))

    def test_stream_reads_lazily(self) -> None:
        """[4.5] 필요한 만큼만 읽는다 — 뒤쪽 줄이 깨져 있어도 앞에서 찾으면 거기서 멈춘다"""
        self.repo.append([tx(1), tx(2)])
        with self.repo.path.open("a", encoding="utf-8") as file:
            file.write("이 줄은 JSON 이 아니다\n")

        self.assertEqual(self.repo.find("TX-000001"), tx(1))  # 3번째 줄까지 가지 않았으므로 성공
        first = next(self.repo.stream())
        self.assertEqual(first.id, "TX-000001")
        with self.assertRaises(AppError):  # 끝까지 읽으면 그제서야 깨진 줄을 만난다
            list(self.repo.stream())


class DamagedFileTests(RepositoryCase):
    def assert_damaged(self, *fragments: str) -> None:
        with self.assertRaises(AppError) as caught:
            list(self.repo.stream())
        self.assertIn("손상", caught.exception.message)
        self.assertTrue(caught.exception.hint)
        for fragment in fragments:
            self.assertIn(fragment, caught.exception.message)

    def test_broken_json_reports_line_number(self) -> None:
        """[4.13] 저장 파일이 깨져도 스택트레이스가 아니라 '몇 번째 줄'인지 알려 준다"""
        self.repo.append([tx(1)])
        with self.repo.path.open("a", encoding="utf-8") as file:
            file.write('{"id": "TX-000002", "type": "expense"\n')
        self.assert_damaged("transactions.jsonl", "2번째 줄")

    def test_missing_or_unknown_field(self) -> None:
        """[4.13] 필드가 빠지거나 남는 줄은 손상으로 본다"""
        self.repo.path.write_text('{"id": "TX-000001"}\n', encoding="utf-8")
        self.assert_damaged("1번째 줄")
        self.repo.path.write_text(json.dumps({**vars(tx(1)), "extra": 1}) + "\n", encoding="utf-8")
        self.assert_damaged("1번째 줄")

    def test_invalid_value_in_file(self) -> None:
        """[4.13] 파일 안의 값이 검증에 실패해도 손상으로 본다"""
        self.repo.path.write_text(json.dumps({**vars(tx(1)), "amount": -5}) + "\n", encoding="utf-8")
        self.assert_damaged("1번째 줄")

    def test_not_utf8(self) -> None:
        """[4.13] UTF-8 이 아닌 저장 파일"""
        self.repo.path.write_bytes('{"memo": "점심"}\n'.encode("cp949"))
        self.assert_damaged("UTF-8")


class SafeWriteTests(RepositoryCase):
    def test_upsert_replaces_in_place_or_appends(self) -> None:
        """[4.6] 수정은 같은 id 줄을 교체한다 (순서 유지)"""
        self.repo.append([tx(1), tx(2), tx(3)])
        self.repo.upsert(tx(2, amount=999))
        self.assertEqual([(item.id, item.amount) for item in self.repo.stream()],
                         [("TX-000001", 1000), ("TX-000002", 999), ("TX-000003", 3000)])
        self.repo.upsert(tx(4))
        self.assertEqual(self.repo.last_number(), 4)

    def test_remove(self) -> None:
        """[4.6] 삭제는 그 줄만 뺀 나머지로 다시 쓴다. 없는 id 면 False"""
        self.repo.append([tx(1), tx(2), tx(3)])
        self.assertTrue(self.repo.remove("TX-000002"))
        self.assertEqual([item.id for item in self.repo.stream()], ["TX-000001", "TX-000003"])
        before = self.repo.path.read_bytes()
        self.assertFalse(self.repo.remove("TX-000099"))
        self.assertEqual(self.repo.path.read_bytes(), before)

    def test_no_temp_file_is_left(self) -> None:
        """[4.6] 수정·삭제 뒤에 임시 파일이 남지 않는다"""
        self.repo.append([tx(1), tx(2)])
        self.repo.upsert(tx(1, amount=5))
        self.repo.remove("TX-000002")
        self.assertEqual([path.name for path in self.data.iterdir()], ["transactions.jsonl"])

    def test_rewrite_failure_keeps_original(self) -> None:
        """[4.6][5-4] 다시 쓰다가 실패하면 원본은 그대로이고 임시 파일도 남지 않는다"""
        self.repo.append([tx(1), tx(2), tx(3)])
        before = self.repo.path.read_bytes()

        def fails_halfway() -> Iterator[Transaction]:
            yield tx(1)
            raise RuntimeError("쓰는 도중 문제가 생김")

        with self.assertRaises(RuntimeError):
            self.repo._rewrite(fails_halfway())
        self.assertEqual(self.repo.path.read_bytes(), before)
        self.assertEqual([path.name for path in self.data.iterdir()], ["transactions.jsonl"])

    def test_replace_failure_keeps_original(self) -> None:
        """[5-4] 마지막 바꿔치기(os.replace)가 실패해도 원본은 그대로다"""
        self.repo.append([tx(1), tx(2)])
        before = self.repo.path.read_bytes()
        with mock.patch("budget_app.storage.os.replace", side_effect=OSError("디스크 오류")):
            with self.assertRaises(OSError):
                self.repo.remove("TX-000001")
        self.assertEqual(self.repo.path.read_bytes(), before)
        self.assertEqual([path.name for path in self.data.iterdir()], ["transactions.jsonl"])

    def test_rewrite_goes_through_temp_file_then_replace(self) -> None:
        """[5-4] 임시 파일에 다 쓴 뒤 os.replace 로 교체한다"""
        self.repo.append([tx(1), tx(2)])
        with mock.patch("budget_app.storage.os.replace") as replace:
            self.repo.remove("TX-000001")
        (source, target), _ = replace.call_args
        self.assertEqual(Path(source).name, "transactions.jsonl.tmp")
        self.assertEqual(Path(target), self.repo.path)

    def test_append_after_cut_line_does_not_glue(self) -> None:
        """마지막 줄이 줄바꿈 없이 끝나 있어도 새 줄이 그 뒤에 붙어 깨지지 않는다"""
        self.repo.append([tx(1)])
        text = self.repo.path.read_text(encoding="utf-8").rstrip("\n")
        self.repo.path.write_text(text, encoding="utf-8")  # 편집기로 마지막 줄바꿈을 지운 상황
        self.repo.append([tx(2)])
        self.assertEqual([item.id for item in self.repo.stream()], ["TX-000001", "TX-000002"])


class CsvTests(TempDirCase):
    def write(self, text: str, name: str = "in.csv", encoding: str = "utf-8") -> Path:
        path = self.tmp / name
        path.write_text(text, encoding=encoding)
        return path

    def test_read_rows_with_line_numbers(self) -> None:
        """[4.11] 헤더가 1번째 줄, 데이터는 2번째 줄부터"""
        path = self.write("date,type,category,amount,memo,tags\n2024-01-15,expense,food,15000,점심,\"meal,lunch\"\n")
        rows = list(read_csv_rows(path))
        self.assertEqual(len(rows), 1)
        line_no, row = rows[0]
        self.assertEqual(line_no, 2)
        self.assertEqual(row["memo"], "점심")
        self.assertEqual(row["tags"], "meal,lunch")

    def test_read_is_a_generator(self) -> None:
        """[4.11] CSV 읽기도 제너레이터"""
        self.assertTrue(inspect.isgeneratorfunction(read_csv_rows))

    def test_bom_is_accepted(self) -> None:
        """[4.11] 엑셀이 저장한 UTF-8(BOM 포함) 파일도 읽는다"""
        path = self.write("date,type,category,amount\n2024-01-15,expense,food,100\n", encoding="utf-8-sig")
        self.assertEqual(next(read_csv_rows(path))[1]["date"], "2024-01-15")

    def test_short_row_gives_none(self) -> None:
        """[4.11] memo, tags 칸이 없는 행"""
        path = self.write("date,type,category,amount,memo,tags\n2024-01-15,expense,food,100\n")
        row = next(read_csv_rows(path))[1]
        self.assertIsNone(row["memo"])

    def test_missing_required_column(self) -> None:
        """[4.11] 헤더에 필수 컬럼이 없으면 오류"""
        path = self.write("date,type,amount\n2024-01-15,expense,100\n")
        with self.assertRaises(AppError) as caught:
            list(read_csv_rows(path))
        self.assertIn("category", caught.exception.message)
        self.assertIn("date,type,category,amount,memo,tags", caught.exception.hint)

    def test_empty_file(self) -> None:
        """[4.11] 빈 CSV 파일"""
        with self.assertRaises(AppError):
            list(read_csv_rows(self.write("")))

    def test_missing_file(self) -> None:
        """[4.13] 없는 CSV 파일"""
        with self.assertRaises(NotFoundError):
            list(read_csv_rows(self.tmp / "nope.csv"))

    def test_not_utf8(self) -> None:
        """[4.11] UTF-8 이 아닌 CSV 파일"""
        path = self.write("date,type,category,amount,memo,tags\n2024-01-15,expense,food,100,점심,\n", encoding="cp949")
        with self.assertRaises(AppError) as caught:
            list(read_csv_rows(path))
        self.assertIn("UTF-8", caught.exception.message)

    def test_write_csv(self) -> None:
        """[4.11] export: UTF-8, 헤더 포함, 컬럼 date,type,category,amount,memo,tags"""
        path = self.tmp / "sub" / "out.csv"
        count = write_transactions_csv(path, iter([tx(1, memo="점심", tags=["meal", "lunch"]), tx(2)]))
        self.assertEqual(count, 2)
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "date,type,category,amount,memo,tags")
        self.assertEqual(lines[0].split(","), CSV_COLUMNS)
        self.assertEqual(lines[1], '2024-01-15,expense,food,1000,점심,"meal,lunch"')
        self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))


class BackupTests(TempDirCase):
    def test_backup_has_timestamp_and_files(self) -> None:
        """[5-1] 타임스탬프가 들어간 백업 파일을 만든다"""
        self.data.mkdir()
        files = [self.data / "transactions.jsonl", self.data / "categories.jsonl", self.data / "missing.jsonl"]
        files[0].write_text("a\n", encoding="utf-8")
        files[1].write_text("b\n", encoding="utf-8")

        path = create_backup(self.data / "backups", files)
        self.assertRegex(path.name, r"^backup-\d{8}-\d{6}\.zip$")
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(sorted(archive.namelist()), ["categories.jsonl", "transactions.jsonl"])
            self.assertEqual(archive.read("transactions.jsonl"), b"a\n")

    def test_two_backups_in_the_same_second_do_not_overwrite(self) -> None:
        """[5-1] 같은 초에 백업을 여러 번 해도 덮어쓰지 않는다"""
        self.data.mkdir()
        file = self.data / "transactions.jsonl"
        file.write_text("a\n", encoding="utf-8")
        paths = {create_backup(self.data / "backups", [file]) for _ in range(3)}
        self.assertEqual(len(paths), 3)
        for path in paths:
            self.assertTrue(re.match(r"^backup-\d{8}-\d{6}(-\d+)?\.zip$", path.name))


if __name__ == "__main__":
    unittest.main()
