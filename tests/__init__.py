"""테스트 폴더.

어떤 방식으로 실행해도 테스트 파일들이 `helpers` 와 `budget_app` 을 import 할 수 있게 경로를 잡아 둔다.

    python -m unittest discover -s tests                 # 전체
    python -m unittest tests.test_cli -v                 # 파일 하나
    python -m unittest tests.test_storage.SafeWriteTests -v   # 클래스 하나
"""

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
for _path in (_TESTS_DIR, _TESTS_DIR.parent):  # tests 폴더(helpers 용), 프로젝트 폴더(budget_app 용)
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
