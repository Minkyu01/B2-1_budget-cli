"""데코레이터 테스트 — 오류 처리 / 실행 기록 / 시간 측정이 본래 함수와 분리되어 동작하는지.

대괄호 번호는 project.md 의 조항 번호다.
"""

import contextlib
import io
import logging
import unittest

from helpers import TempDirCase
from budget_app import decorators
from budget_app.decorators import (
    EXIT_CANCELLED,
    EXIT_ERROR,
    EXIT_OK,
    handle_errors,
    log_command,
    measure_time,
    setup_logging,
)
from budget_app.errors import AppError, NotFoundError, ValidationError


def run_and_capture(func) -> tuple[int, str, str]:  # type: ignore[no-untyped-def]
    """func 를 실행하고 (반환값, stdout, stderr) 를 돌려준다."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = func()
    return code, out.getvalue(), err.getvalue()


class HandleErrorsTests(unittest.TestCase):
    def test_return_value_passes_through(self) -> None:
        """[4.13] 정상 종료는 0"""

        @handle_errors
        def fine() -> int:
            return EXIT_OK

        self.assertEqual(run_and_capture(fine), (0, "", ""))

    def test_app_error_becomes_message_and_hint(self) -> None:
        """[4.13] 오류는 스택트레이스 대신 원인 + 해결 힌트, 종료 코드는 0이 아니다"""
        for error_class in (AppError, ValidationError, NotFoundError):

            @handle_errors
            def fails() -> int:
                raise error_class("원인 설명", "이렇게 해 보세요")

            with self.subTest(error_class=error_class.__name__):
                code, out, err = run_and_capture(fails)
                self.assertEqual(code, EXIT_ERROR)
                self.assertNotEqual(code, 0)
                self.assertEqual(err, "[오류] 원인 설명\n[힌트] 이렇게 해 보세요\n")
                self.assertEqual(out, "")  # 오류는 stdout 이 아니라 stderr 로만 나간다

    def test_unexpected_error_hides_traceback(self) -> None:
        """[4.13][7] 버그 같은 예상 못 한 오류도 스택트레이스를 화면에 찍지 않는다"""

        @handle_errors
        def buggy() -> int:
            raise RuntimeError("내부 사정")

        code, out, err = run_and_capture(buggy)
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("[오류]", err)
        self.assertIn("[힌트]", err)
        self.assertNotIn("Traceback", err + out)
        self.assertNotIn("RuntimeError", err + out)

    def test_os_error(self) -> None:
        """[4.13] 파일 오류(권한 없음 등)도 원인 + 힌트로 바꾼다"""

        @handle_errors
        def no_permission() -> int:
            raise PermissionError(13, "Permission denied", "data/transactions.jsonl")

        code, _, err = run_and_capture(no_permission)
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("data/transactions.jsonl", err)
        self.assertIn("Permission denied", err)
        self.assertIn("[힌트]", err)
        self.assertNotIn("Traceback", err)

    def test_interrupt_and_end_of_input(self) -> None:
        """[4.13] Ctrl+C / 입력 끝(EOF)도 0이 아닌 코드로 조용히 끝낸다"""
        for error in (KeyboardInterrupt(), EOFError()):

            @handle_errors
            def stopped() -> int:
                raise error

            with self.subTest(error=type(error).__name__):
                code, _, err = run_and_capture(stopped)
                self.assertEqual(code, EXIT_CANCELLED)
                self.assertIn("[오류]", err)
                self.assertNotIn("Traceback", err)

    def test_wraps_keeps_name_and_doc(self) -> None:
        """[4.12] functools.wraps 로 원래 함수의 이름과 설명이 유지된다"""

        @handle_errors
        def original() -> int:
            """설명"""
            return 0

        self.assertEqual((original.__name__, original.__doc__), ("original", "설명"))


class LoggingDecoratorTests(TempDirCase):
    def setUp(self) -> None:
        super().setUp()
        self.log_path = self.tmp / "app.log"
        before = list(decorators.logger.handlers)
        setup_logging(self.log_path)
        self.addCleanup(self.remove_new_handlers, before)

    def remove_new_handlers(self, before: list[logging.Handler]) -> None:
        for handler in list(decorators.logger.handlers):
            if handler not in before:
                decorators.logger.removeHandler(handler)
                handler.close()

    def log(self) -> str:
        return self.log_path.read_text(encoding="utf-8")

    def test_log_command_records_start_and_success(self) -> None:
        """[4.12] 실행 로그 데코레이터"""

        @log_command
        def cmd_list(value: int) -> int:
            return value * 2

        self.assertEqual(cmd_list(21), 42)  # 본래 함수의 결과는 그대로
        self.assertIn("[list] 시작", self.log())
        self.assertIn("[list] 성공", self.log())

    def test_log_command_records_failure_and_reraises(self) -> None:
        """[4.12] 실패도 기록하고, 예외는 그대로 위로 보낸다"""

        @log_command
        def cmd_delete() -> None:
            raise NotFoundError("없음", "확인")

        with self.assertRaises(NotFoundError):  # 기록만 하고 예외는 그대로 위로 보낸다
            cmd_delete()
        self.assertIn("[delete] 실패: NotFoundError", self.log())
        self.assertNotIn("[delete] 성공", self.log())

    def test_measure_time_records_elapsed(self) -> None:
        """[4.12] 실행 시간 측정 데코레이터"""

        class Service:
            @measure_time
            def scan(self, count: int) -> int:
                return sum(range(count))

        self.assertEqual(Service().scan(100), 4950)
        self.assertRegex(self.log(), r"Service\.scan 실행 시간: \d+\.\d\dms")

    def test_measure_time_records_even_on_error(self) -> None:
        """[4.12] 함수가 실패해도 걸린 시간은 기록한다"""

        @measure_time
        def explode() -> None:
            raise ValueError("실패")

        with self.assertRaises(ValueError):
            explode()
        self.assertIn("explode 실행 시간", self.log())

    def test_unexpected_error_detail_goes_to_log_only(self) -> None:
        """[4.13] 자세한 오류 내용(스택트레이스)은 화면이 아니라 로그 파일에만 남긴다"""

        @handle_errors
        def buggy() -> int:
            raise RuntimeError("내부 사정")

        _, out, err = run_and_capture(buggy)
        self.assertNotIn("내부 사정", out + err)
        self.assertIn("RuntimeError: 내부 사정", self.log())

    def test_nothing_is_printed_by_logging(self) -> None:
        """[4.12] 실행 기록은 파일에만 남고 화면에는 나오지 않는다"""

        @log_command
        def cmd_quiet() -> int:
            return 0

        code, out, err = run_and_capture(cmd_quiet)
        self.assertEqual((code, out, err), (0, "", ""))


class NoLogFileTests(unittest.TestCase):
    def test_logging_before_setup_prints_nothing(self) -> None:
        """로그 파일을 열기 전에 오류가 나도 파이썬 기본 동작(화면에 스택트레이스)이 나오지 않는다"""

        @handle_errors
        def fails_early() -> int:
            raise OSError("폴더를 만들 수 없음")

        code, out, err = run_and_capture(fails_early)
        self.assertEqual(code, EXIT_ERROR)
        self.assertNotIn("Traceback", out + err)
        self.assertEqual(err.count("\n"), 2)  # [오류] 한 줄 + [힌트] 한 줄뿐


if __name__ == "__main__":
    unittest.main()
