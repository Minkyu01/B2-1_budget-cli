"""데코레이터 — 모든 명령에 똑같이 필요한 '공통 관심사'를 한 곳에 모은다.

명령 함수는 "무엇을 할지"만 쓰고, 아래 일은 데코레이터가 대신한다.
    handle_errors : 예외 → [오류]/[힌트] 출력 + 종료 코드   (cli.main 에 1번 적용)
    log_command   : 명령 시작/성공/실패를 app.log 에 기록     (cli 의 명령 함수마다 적용)
    measure_time  : 실행 시간을 app.log 에 기록              (서비스의 전체 스캔 메서드에 적용)

데코레이터가 없다면 모든 명령 함수에 try/except, logger.info, time.perf_counter 가
복사-붙여넣기로 흩어졌을 것이다.
"""

import functools
import logging
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import ParamSpec, TypeVar

from budget_app.errors import AppError
from budget_app.formatter import print_error

P = ParamSpec("P")  # 감싸는 함수의 '매개변수 목록'을 그대로 보존하기 위한 타입
R = TypeVar("R")    # 감싸는 함수의 '반환 타입'을 그대로 보존하기 위한 타입

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2        # 명령 형식이 틀렸을 때 (없는 명령, 빠진 옵션) — 리눅스 명령들의 관례
EXIT_CANCELLED = 130  # Ctrl+C 로 끝낸 프로그램의 관례적인 종료 코드


# ---- 실행 기록(로그) 설정 ------------------------------------------------------

logger = logging.getLogger("budget_app")
logger.setLevel(logging.INFO)
# 기록할 곳이 아직 없을 때(로그 파일을 열기 전)의 기록은 버린다.
# 이 두 줄이 없으면 파이썬이 오류 기록을 스택트레이스와 함께 화면(stderr)에 찍어 버린다.
logger.addHandler(logging.NullHandler())
logger.propagate = False


def setup_logging(log_path: Path) -> None:
    """이제부터 실행 기록을 log_path 파일에 남긴다. (화면에는 찍지 않는다)"""
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)


# ---- 데코레이터 3개 ------------------------------------------------------------

def handle_errors(func: Callable[P, int]) -> Callable[P, int]:
    """예외가 나면 스택트레이스 대신 원인+힌트를 출력하고, 0이 아닌 종료 코드를 반환한다."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> int:
        try:
            return func(*args, **kwargs)
        except AppError as error:  # 예상한 오류: 원인과 힌트를 그대로 보여준다
            print_error(error.message, error.hint)
            return EXIT_ERROR
        except (KeyboardInterrupt, EOFError):  # Ctrl+C 로 중단 / Ctrl+D 등으로 입력이 끝남
            print()
            print_error(
                "실행이 중단되었습니다.",
                "대화형 입력 도중이었다면 아무것도 저장되지 않았습니다. 처음부터 다시 실행하세요.",
            )
            return EXIT_CANCELLED
        except BrokenPipeError:  # `... | head` 처럼 출력을 받던 쪽이 먼저 끝난 경우 — 오류가 아니다
            # 파이썬이 종료하면서 남은 출력을 또 내보내다 실패하지 않도록 출력을 '버리는 곳'으로 돌린다.
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
            return EXIT_OK
        except OSError as error:  # 권한 없음, 디스크 가득 참 등 파일 시스템 오류
            logger.exception("파일 오류")
            target = f" ({error.filename})" if error.filename else ""
            print_error(
                f"파일을 읽거나 쓰지 못했습니다{target}: {error.strerror or error}",
                "경로가 맞는지, 쓰기 권한이 있는지 확인하세요.",
            )
            return EXIT_ERROR
        except Exception:  # 버그 등 예상 못 한 오류: 자세한 내용은 로그 파일에만 남긴다
            logger.exception("예상하지 못한 오류")
            print_error(
                "예상하지 못한 오류가 발생했습니다.",
                "저장 폴더의 app.log 에 자세한 내용이 기록되었습니다.",
            )
            return EXIT_ERROR

    return wrapper


def log_command(func: Callable[P, R]) -> Callable[P, R]:
    """명령 함수의 시작/성공/실패를 app.log 에 남긴다. (cmd_list → 'list')"""
    name = func.__name__.removeprefix("cmd_")

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        logger.info("[%s] 시작", name)
        try:
            result = func(*args, **kwargs)
        except BaseException as error:
            logger.info("[%s] 실패: %s", name, error.__class__.__name__)
            raise  # 기록만 하고 처리는 handle_errors 에게 넘긴다
        logger.info("[%s] 성공", name)
        return result

    return wrapper


def measure_time(func: Callable[P, R]) -> Callable[P, R]:
    """함수가 끝날 때까지 걸린 시간을 app.log 에 남긴다.

    주의: 제너레이터 함수에 붙이면 '제너레이터 객체를 만드는 시간(≈0ms)'만 재게 된다.
    그래서 제너레이터를 끝까지 소비하는 서비스 메서드(결과를 list/int 로 돌려주는 쪽)에 붙인다.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info("%s 실행 시간: %.2fms", func.__qualname__, elapsed_ms)

    return wrapper
