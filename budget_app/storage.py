"""저장소 계층 — 파일 읽기/쓰기만 담당한다. (업무 규칙은 모른다)

저장 형식은 JSONL: 한 줄 = JSON 객체 하나 = 모델 객체 하나.
    {"id": "TX-000001", "type": "expense", "date": "2024-01-15", ...}

핵심 3가지
1. 읽기는 제너레이터(stream) : 한 줄 읽고 → 객체로 바꿔 yield → 다음 줄.
                               파일이 아무리 커도 메모리에는 한 줄씩만 올라온다.
2. 추가는 append             : 파일 끝에 줄만 덧붙인다. (기존 내용은 건드리지 않음)
3. 수정/삭제는 원자적 교체    : 임시 파일에 새 내용을 다 쓴 뒤 os.replace 로 한 번에 바꾼다.
                               중간에 프로그램이 죽어도 원본은 온전히 남는다.
"""

import csv
import json
import os
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, TypeVar

from budget_app.errors import AppError, NotFoundError
from budget_app.models import Budget, Category, RecurringRule, Transaction, id_number

T = TypeVar("T")  # 이 저장소가 다루는 모델 타입 (Transaction, Category, ...)


class JsonlRepository(Generic[T]):
    """JSONL 파일 1개를 다루는 공통 저장소. 4개 저장소가 모두 이 클래스를 상속한다.

    자식 클래스는 두 가지만 정하면 된다.
      model     : 한 줄을 어떤 dataclass 로 바꿀지
      key_field : 한 줄을 구분하는 식별자 필드 이름 (id / name / month)
    """

    model: type[T]
    key_field: str

    def __init__(self, path: Path) -> None:
        self.path = path

    def ensure_file(self) -> bool:
        """파일이 없으면 빈 파일을 만든다. 새로 만들었으면 True."""
        if self.path.exists():
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch()
        return True

    # ---- 읽기 -----------------------------------------------------------

    def stream(self) -> Iterator[T]:
        """파일을 한 줄씩 읽어 모델 객체로 yield 한다. (제너레이터)

        list 로 한꺼번에 읽지 않기 때문에, 호출한 쪽이 한 건을 처리하는 동안
        파일의 나머지는 아직 읽히지도 않은 상태다.
        """
        if not self.path.exists():
            return
        try:
            with self.path.open(encoding="utf-8") as file:
                for line_no, line in enumerate(file, start=1):
                    if not line.strip():
                        continue  # 빈 줄은 건너뛴다
                    try:
                        item = self.model(**json.loads(line))
                    except (json.JSONDecodeError, TypeError, AppError):
                        # JSON 이 아닌 줄 / 필드가 빠지거나 남는 줄 / 값 검증에 실패한 줄
                        raise self._damaged(f"{line_no}번째 줄") from None
                    yield item
        except UnicodeDecodeError:
            raise self._damaged("UTF-8 이 아닌 글자가 섞여 있음") from None

    def find(self, key: str) -> T | None:
        """식별자가 key 인 항목을 찾는다. 찾는 순간 읽기를 멈춘다."""
        return next((item for item in self.stream() if self._key(item) == key), None)

    def exists(self, key: str) -> bool:
        return self.find(key) is not None

    # ---- 쓰기 -----------------------------------------------------------

    def append(self, items: Iterable[T]) -> int:
        """항목들을 파일 끝에 추가하고, 추가한 개수를 돌려준다."""
        count = 0
        with self.path.open("a", encoding="utf-8") as file:
            if self._last_line_is_cut():
                file.write("\n")  # 잘린 줄 바로 뒤에 붙이면 새 줄까지 같이 깨지므로 줄부터 바꾼다
            for item in items:
                file.write(self._to_line(item))
                count += 1
        return count

    def upsert(self, item: T) -> None:
        """같은 식별자가 있으면 교체(수정), 없으면 끝에 추가한다. (원자적 재작성)"""
        key = self._key(item)

        def merged() -> Iterator[T]:
            replaced = False
            for old in self.stream():
                if self._key(old) == key:
                    replaced = True
                    yield item
                else:
                    yield old
            if not replaced:
                yield item

        self._rewrite(merged())

    def remove(self, key: str) -> bool:
        """식별자가 key 인 항목을 뺀 나머지로 파일을 다시 쓴다. 없었으면 False."""
        if not self.exists(key):
            return False
        self._rewrite(old for old in self.stream() if self._key(old) != key)
        return True

    def _rewrite(self, items: Iterable[T]) -> None:
        """원자적 교체 (보너스 4)

        1) 같은 폴더의 임시 파일(xxx.jsonl.tmp)에 새 내용을 전부 쓴다.
        2) flush + fsync 로 디스크에 확실히 기록한다.
        3) os.replace 로 원본과 바꿔치기한다. → 운영체제가 '한 번에' 처리하는 동작이라
           다른 프로그램은 '옛 파일' 아니면 '새 파일'만 보고, 반쯤 쓰인 파일은 절대 보지 못한다.
        중간에 오류가 나면 임시 파일만 지우고 원본은 그대로 둔다.
        """
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as file:
                for item in items:  # items 는 원본을 읽는 제너레이터여도 된다
                    file.write(self._to_line(item))
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp_path, self.path)
        finally:
            tmp_path.unlink(missing_ok=True)

    # ---- 내부 도우미 ----------------------------------------------------

    def _key(self, item: T) -> str:
        return str(getattr(item, self.key_field))

    @staticmethod
    def _to_line(item: Any) -> str:
        # ensure_ascii=False : 한글을 \uXXXX 가 아니라 그대로 저장 (파일을 열어봐도 읽힘)
        return json.dumps(asdict(item), ensure_ascii=False) + "\n"

    def _last_line_is_cut(self) -> bool:
        """파일이 줄바꿈 없이 끝났는가. (쓰다가 꺼졌거나, 편집기로 고치다 마지막 줄바꿈을 지운 경우)"""
        if self.path.stat().st_size == 0:
            return False
        with self.path.open("rb") as file:
            file.seek(-1, os.SEEK_END)  # 끝에서 1바이트 앞으로
            return file.read(1) != b"\n"

    def _damaged(self, where: str) -> AppError:
        return AppError(
            f"{self.path.name} 파일이 손상되었습니다 ({where}).",
            f"{self.path} 를 열어 해당 부분을 고치거나, backup 으로 만든 zip 에서 복구하세요.",
        )


class TransactionRepository(JsonlRepository[Transaction]):
    """transactions.jsonl"""

    model = Transaction
    key_field = "id"

    def last_number(self) -> int:
        """저장된 id(TX-000012) 중 가장 큰 번호. 비어 있으면 0."""
        return max((id_number(tx.id) for tx in self.stream()), default=0)


class CategoryRepository(JsonlRepository[Category]):
    """categories.jsonl"""

    model = Category
    key_field = "name"


class BudgetRepository(JsonlRepository[Budget]):
    """budgets.jsonl"""

    model = Budget
    key_field = "month"


class RecurringRepository(JsonlRepository[RecurringRule]):
    """recurring.jsonl (보너스: 반복 내역)"""

    model = RecurringRule
    key_field = "id"

    def last_number(self) -> int:
        return max((id_number(rule.id) for rule in self.stream()), default=0)


# ---------------------------------------------------------------------------
# CSV (import / export 전용) — 내부 저장은 JSONL, 외부와 주고받을 때만 CSV
# ---------------------------------------------------------------------------

CSV_COLUMNS = ["date", "type", "category", "amount", "memo", "tags"]
CSV_REQUIRED = ["date", "type", "category", "amount"]


def read_csv_rows(path: Path) -> Iterator[tuple[int, dict[str, str | None]]]:
    """CSV 를 한 행씩 (줄 번호, {컬럼: 값}) 으로 yield 한다. 헤더가 1번째 줄이다.

    값이 None 인 경우: 그 행의 칸 수가 헤더보다 적을 때 (csv 모듈이 빈 칸을 None 으로 채운다)
    """
    if not path.is_file():
        raise NotFoundError(f"CSV 파일을 찾을 수 없습니다: {path}", "경로와 파일 이름을 다시 확인하세요.")
    try:
        # utf-8-sig : 엑셀이 붙이는 BOM(보이지 않는 첫 글자)이 있어도 헤더를 제대로 읽기 위해
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            missing = [col for col in CSV_REQUIRED if col not in (reader.fieldnames or [])]
            if missing:
                raise AppError(
                    f"CSV 헤더에 필수 컬럼이 없습니다: {', '.join(missing)}",
                    f"첫 줄(헤더)은 {','.join(CSV_COLUMNS)} 이어야 합니다.",
                )
            for row in reader:
                yield reader.line_num, row
    except UnicodeDecodeError:
        raise AppError(
            "CSV 파일이 UTF-8 이 아니어서 읽을 수 없습니다.",
            "엑셀이라면 '다른 이름으로 저장'에서 'CSV UTF-8(쉼표로 분리)' 형식을 고르세요.",
        ) from None
    except csv.Error as error:
        raise AppError(
            f"CSV 형식이 올바르지 않습니다: {error}",
            "따옴표가 닫히지 않았는지, 파일이 CSV 가 맞는지 확인하세요.",
        ) from None


def write_transactions_csv(path: Path, transactions: Iterable[Transaction]) -> int:
    """거래들을 CSV 로 한 행씩 쓴다. (받은 것도 제너레이터라 전체를 모으지 않는다)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(CSV_COLUMNS)
        for tx in transactions:
            writer.writerow([tx.date, tx.type, tx.category, tx.amount, tx.memo, ",".join(tx.tags)])
            count += 1
    return count


# ---------------------------------------------------------------------------
# 백업 (보너스 1)
# ---------------------------------------------------------------------------

def create_backup(backup_dir: Path, files: list[Path]) -> Path:
    """files 를 타임스탬프가 붙은 zip 파일 하나로 묶는다. 예: backup-20240115-093000.zip"""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = backup_dir / f"backup-{stamp}.zip"
    suffix = 1
    while path.exists():  # 같은 초에 두 번 실행해도 덮어쓰지 않도록
        suffix += 1
        path = backup_dir / f"backup-{stamp}-{suffix}.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            if file.exists():
                archive.write(file, arcname=file.name)
    return path
